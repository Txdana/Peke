"""Typer CLI application for Peke."""

import importlib.metadata
import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from peke.banner import print_banner
from peke.config import get_settings
from peke.discover import discover_target_profile, is_rea_available
from peke.pipeline import Pipeline, PipelineEvent, PipelineResult

app = typer.Typer(name="peke", help="Peke: Open-source data-extraction workbench", invoke_without_command=True)
console = Console()


def get_version() -> str:
    """Return package version."""
    try:
        return importlib.metadata.version("peke")
    except Exception:
        return "0.1.0"


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        settings = get_settings()
        mcp_status = is_rea_available(settings.rea_server_url)
        print_banner(console, mcp_active=mcp_status)
        console.print(f"Peke version {get_version()}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        help="Show Peke version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
    no_banner: bool = typer.Option(False, "--no-banner", help="Disable terminal banner display."),
    no_splash: bool = typer.Option(False, "--no-splash", help="Disable GUI splash screen at startup."),
) -> None:
    """Default entrypoint. If no subcommand is invoked, attempts to launch the PySide6 GUI."""
    ctx.ensure_object(dict)
    ctx.obj["no_banner"] = no_banner
    ctx.obj["no_splash"] = no_splash

    if ctx.invoked_subcommand is None:
        settings = get_settings()
        mcp_status = is_rea_available(settings.rea_server_url)
        if not no_banner:
            print_banner(console, mcp_active=mcp_status)
        try:
            from peke.gui.app import run_gui
            run_gui(no_splash=no_splash)
        except ImportError:
            console.print(
                "[bold yellow]GUI dependencies (PySide6) are not installed or GUI is unavailable.[/bold yellow]"
            )
            console.print("Use [bold cyan]peke run profiles/example.yaml -o out.json[/bold cyan] for headless CLI mode.")


@app.command()
def doctor() -> None:
    """Run diagnostic checks on system requirements and dependencies."""
    table = Table(title="Peke System Diagnostic (Doctor)", show_header=True, header_style="bold magenta")
    table.add_column("Component", style="cyan", width=25)
    table.add_column("Status", width=12)
    table.add_column("Details", style="dim")

    # 1. Python Version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    table.add_row("Python Environment", "[bold green]PASS[/bold green]", f"v{py_ver} (>=3.10 required)")

    # 2. PySide6 GUI
    try:
        import PySide6  # noqa: F401
        table.add_row("PySide6 GUI", "[bold green]PASS[/bold green]", "PySide6 is installed")
    except ImportError:
        table.add_row("PySide6 GUI", "[yellow]OPTIONAL[/yellow]", "PySide6 not installed (CLI mode only)")

    # 3. Scrapling
    try:
        import scrapling  # noqa: F401
        table.add_row("Scrapling Fetcher", "[bold green]PASS[/bold green]", "Scrapling fetchers available")
    except ImportError:
        table.add_row("Scrapling Fetcher", "[bold red]FAIL[/bold red]", "Scrapling dependency missing")

    # 4. llama.cpp / MODEL_PATH
    settings = get_settings()
    model_str = settings.model_path_str
    if model_str and Path(model_str).is_file():
        table.add_row("llama.cpp SLM Model", "[bold green]PASS[/bold green]", f"GGUF model found at {model_str}")
    else:
        m_val = model_str or "Not set"
        table.add_row("llama.cpp SLM Model", "[yellow]WARN[/yellow]", f"MODEL_PATH='{m_val}' (LLM fallback disabled until valid file set)")

    # 5. REA MCP Server
    mcp_status = is_rea_available(settings.rea_server_url)
    if mcp_status:
        table.add_row("REA Server (MCP)", "[bold green]PASS[/bold green]", f"Reachable at {settings.rea_server_url}")
    else:
        table.add_row("REA Server (MCP)", "[yellow]OPTIONAL[/yellow]", f"Unreachable at {settings.rea_server_url} (Standalone mode)")

    console.print(table)


@app.command()
def discover(
    ctx: typer.Context,
    url: str = typer.Argument(..., help="Target web application URL to inspect"),
    out: Path | None = typer.Option(
        None, "--out", "-o", help="Path to write the draft profile YAML file"
    ),
    schema: str = typer.Option("Article", "--schema", "-s", help="Target Pydantic schema model"),
) -> None:
    """Discover endpoints using REA and generate findings file and draft target profile YAML."""
    no_banner = ctx.obj.get("no_banner", False) if ctx.obj else False
    settings = get_settings()
    mcp_status = is_rea_available(settings.rea_server_url)
    if not no_banner:
        print_banner(console, mcp_active=mcp_status)

    console.print(f"[bold blue]Running discovery for target URL:[/bold blue] {url}")

    events: list[tuple[str, str]] = []
    def on_event(level: str, msg: str) -> None:
        events.append((level, msg))
        color = "yellow" if level == "WARNING" else "cyan"
        console.print(f"[{color}]{level}: {msg}[/{color}]")

    profile = discover_target_profile(url, rea_url=settings.rea_server_url, schema_name=schema, on_event=on_event)

    findings_payload = {
        "target_url": url,
        "endpoint_hints": profile.endpoint_hints,
        "headers": profile.headers,
        "params": profile.params,
        "schema_name": profile.schema_name,
        "note": "REA findings are hints that must be reviewed before use.",
    }

    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        import yaml
        with open(out, "w", encoding="utf-8") as f:
            yaml.safe_dump(profile.model_dump(), f, sort_keys=False)

        findings_file = out.with_suffix(".json")
        with open(findings_file, "w", encoding="utf-8") as f:
            json.dump(findings_payload, f, indent=2)

        console.print(f"\n[bold green]Success![/bold green] Saved draft profile to '{out}' and findings to '{findings_file}'.")
    else:
        console.print("\n[bold green]Discovered Profile YAML:[/bold green]")
        import yaml
        console.print(yaml.safe_dump(profile.model_dump(), sort_keys=False))


@app.command()
def run(
    ctx: typer.Context,
    profile_path: str = typer.Argument(
        ..., help="Path to profile YAML file or target URL"
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Path to save output JSON file"
    ),
    schema: str | None = typer.Option(
        None, "--schema", "-s", help="Target Pydantic schema model override"
    ),
) -> None:
    """Run data extraction pipeline headlessly with profile YAML or URL."""
    no_banner = ctx.obj.get("no_banner", False) if ctx.obj else False
    settings = get_settings()
    mcp_status = is_rea_available(settings.rea_server_url)
    if not no_banner:
        print_banner(console, mcp_active=mcp_status)

    def log_event(event: PipelineEvent) -> None:
        level_colors = {
            "INFO": "blue",
            "WARNING": "yellow",
            "ERROR": "bold red",
            "SUCCESS": "bold green",
        }
        color = level_colors.get(event.level, "white")
        console.print(f"[{event.timestamp}] [{event.stage}] [{color}]{event.message}[/{color}]")

    pipeline = Pipeline(event_callback=log_event)
    result: PipelineResult = pipeline.run(profile_path, schema_override=schema)

    if result.extraction_result and result.extraction_result.json_output:
        json_out = result.extraction_result.json_output
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            with open(output, "w", encoding="utf-8") as f:
                json.dump(json_out, f, indent=2)
            console.print(f"\n[bold green]Success![/bold green] Output written to '{output}'")
        else:
            console.print("\n[bold green]Extracted Data JSON:[/bold green]")
            console.print_json(json.dumps(json_out))
    else:
        console.print("\n[bold red]Pipeline completed but no extracted data was produced.[/bold red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
