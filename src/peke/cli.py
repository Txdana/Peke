"""Typer CLI application for Peke."""

import json
from pathlib import Path

import typer
from rich.console import Console

from peke.config import get_settings
from peke.discover import discover_target_profile, is_rea_available
from peke.pipeline import Pipeline, PipelineEvent, PipelineResult

app = typer.Typer(name="peke", help="Peke: Open-source data-extraction workbench", invoke_without_command=True)
console = Console()


def print_startup_splash(mcp_active: bool = False) -> None:
    """Print terminal-style startup banner as specified in Peke GUI/CLI spec.

    :param mcp_active: True if REA MCP server is active/reachable.
    """
    mcp_chip = "[MCP Active]" if mcp_active else "[MCP Off]"
    splash_text = f"""
┌──────────────────────────────────────────────────────┐
│  PEKE  {mcp_chip:<12}                local: llama.cpp  │
└──────────────────────────────────────────────────────┘
  │
  ├── [01] REA Analysis  ──▶  Discovered Endpoint
  ├── [02] Scrapling     ──▶  Cloudflare Bypassed
  └── [03] Local SLM     ──▶  Clean JSON Formatted
"""
    console.print(f"[bold cyan]{splash_text}[/bold cyan]")


@app.callback()
def main(
    ctx: typer.Context,
) -> None:
    """Default entrypoint. If no subcommand is invoked, attempts to launch the PySide6 GUI."""
    if ctx.invoked_subcommand is None:
        try:
            from peke.gui.app import run_gui
            run_gui()
        except ImportError:
            settings = get_settings()
            mcp_status = is_rea_available(settings.rea_server_url)
            print_startup_splash(mcp_active=mcp_status)
            console.print(
                "[bold yellow]GUI dependencies (PySide6) are not installed or GUI is unavailable.[/bold yellow]"
            )
            console.print("Use [bold cyan]peke run profiles/example.yaml -o out.json[/bold cyan] for headless CLI mode.")


@app.command()
def discover(
    url: str = typer.Argument(..., help="Target web application URL to inspect"),
    out: Path | None = typer.Option(
        None, "--out", "-o", help="Path to write the draft profile YAML file"
    ),
    schema: str = typer.Option("Article", "--schema", "-s", help="Target Pydantic schema model"),
) -> None:
    """Discover endpoints using REA and generate findings file and draft target profile YAML."""
    settings = get_settings()
    mcp_status = is_rea_available(settings.rea_server_url)
    print_startup_splash(mcp_active=mcp_status)

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
    settings = get_settings()
    mcp_status = is_rea_available(settings.rea_server_url)
    print_startup_splash(mcp_active=mcp_status)

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
