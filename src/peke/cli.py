"""Typer command-line interface for Peke's headless Phase 1 pipeline."""
import importlib.util
import json
import logging
import platform
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table

from peke import __version__
from peke.banner import print_banner
from peke.config import ConfigError, load_settings, save_user_settings, user_settings_path
from peke.discover import run_rea
from peke.mcp.cli import mcp_app
from peke.pipeline import Event, Pipeline
from peke.profile import ProfileError, load_profile
from peke.schemas import get_schema, list_schemas

app = typer.Typer(name="peke", help="Peke: local-first data extraction workbench", no_args_is_help=False)
app.add_typer(mcp_app, name="mcp", help="Peke MCP server management and agent registration")
console = Console()


def _event(event: Event) -> None:
    colors = {"info": "cyan", "ok": "green", "warn": "yellow", "error": "bold red"}
    tag = f" [{event.tag}]" if event.tag else ""
    console.print(f"[{event.ts}] [{event.stage}]{tag} [{colors[event.level]}]{event.message}[/{colors[event.level]}]")


@app.command()
def run(profile_path: Path = typer.Argument(..., exists=True, readable=True),
        output: Path | None = typer.Option(None, "-o", "--output"),
        format: str = typer.Option("json", "--format", help="Output format: json or md"),
        stealth: bool = typer.Option(False, "--stealth/--basic", help="Override profile fetcher"),
        verbose: bool = typer.Option(False, "--verbose")) -> None:
    """Run a target profile and save JSON or Markdown."""
    if format not in {"json", "md"}:
        console.print("[red]--format must be json or md[/red]")
        raise typer.Exit(2)
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    try:
        profile = load_profile(profile_path)
        profile = profile.model_copy(update={"fetcher": "stealthy" if stealth else "basic"})
        result = Pipeline(settings=load_settings(), on_event=_event).run(profile)
    except (ConfigError, ProfileError, ValueError) as exc:
        console.print(f"[red]Configuration/profile error: {exc}[/red]")
        raise typer.Exit(2) from exc
    if not result.records:
        error = next((event.message for event in result.events if event.level == "error"), "Pipeline failed")
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(3 if "Fetch" in error or "HTTP" in error or "Scrapling" in error else 4)
    if format == "json":
        payload = json.dumps([record.model_dump(mode="json") for record in result.records], indent=2, ensure_ascii=False)
    else:
        payload = result.markdown_summary
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
        console.print(f"[green]Saved {format.upper()} output to {output}[/green]")
    else:
        console.print(payload, markup=False)


@app.command()
def validate(profile_path: Path = typer.Argument(..., exists=True, readable=True)) -> None:
    """Validate a profile without making a network request."""
    try:
        profile = load_profile(profile_path)
        get_schema(profile.schema_name)
    except (ProfileError, ValueError) as exc:
        console.print(f"[red]Invalid profile: {exc}[/red]")
        raise typer.Exit(2) from exc
    console.print(f"[green]Valid profile:[/green] {profile.name} ({profile.schema_name})")


@app.command("schemas")
def schemas_command() -> None:
    """List built-in extraction schemas."""
    for name in list_schemas():
        console.print(name)


@app.command()
def doctor() -> None:
    """Report runtime and optional dependency availability."""
    settings = load_settings()
    table = Table(title="Peke doctor", show_header=True, header_style="bold")
    table.add_column("Check", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Details", overflow="fold")

    python_ok = tuple(map(int, platform.python_version_tuple()[:2])) >= (3, 10)
    table.add_row("Python", "PASS" if python_ok else "FAIL", platform.python_version())
    for package in ("scrapling", "llama_cpp", "yaml", "pydantic"):
        available = importlib.util.find_spec(package) is not None
        table.add_row(package, "PASS" if available else "FAIL",
                      "installed" if available else "required package is not installed")
    gui_available = importlib.util.find_spec("PySide6") is not None
    table.add_row("PySide6 GUI", "PASS" if gui_available else "OPTIONAL",
                  "installed" if gui_available else "install with pipx install 'peke\\[gui]'")
    try:
        model = settings.require_model()
        table.add_row("MODEL_PATH", "PASS", str(model))
    except ConfigError as exc:
        table.add_row("MODEL_PATH", "OPTIONAL", str(exc))
    gpu = importlib.util.find_spec("pynvml") is not None
    table.add_row("GPU telemetry", "OPTIONAL" if not gpu else "PASS",
                  "nvidia-ml-py detected" if gpu else "nvidia-ml-py not installed; CPU RAM fallback is used")
    if settings.rea_command:
        from peke.banner import rea_available
        rea_found = rea_available(settings.rea_command)
        table.add_row("REA CLI", "PASS" if rea_found else "FAIL",
                      settings.rea_command if rea_found else f"Executable not found for REA_COMMAND={settings.rea_command!r}")
        from peke.discover import _validate_cdp_endpoint
        try:
            endpoint = _validate_cdp_endpoint(settings.rea_cdp_endpoint)
            table.add_row("REA CDP endpoint", "CONFIGURED", f"{endpoint} (reachability not tested by doctor)")
        except ValueError as exc:
            table.add_row("REA CDP endpoint", "FAIL", str(exc))
    else:
        table.add_row("REA CLI", "OPTIONAL", "REA_COMMAND not set; Peke works without REA")

    from peke.mcp.clients.registrars import get_all_registrars
    mcp_regs = [r for r in get_all_registrars() if r.is_registered()]
    table.add_row("MCP Registrations", "PASS" if mcp_regs else "INFO",
                  f"{len(mcp_regs)} agent(s) registered ({', '.join(r.display_name for r in mcp_regs) if mcp_regs else 'none'})")
    console.print(table)


@app.command()
def discover(url: str = typer.Argument(..., help="Target website URL"),
            out: Path = typer.Option(Path("profiles/discovered.yaml"), "--out", help="Draft profile YAML path"),
            findings: Path | None = typer.Option(None, "--findings", help="Also save normalized findings JSON")) -> None:
    """Run optional REA discovery and create a reviewable draft profile."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        console.print("[red]Provide a valid http:// or https:// URL.[/red]")
        raise typer.Exit(2)
    settings = load_settings()
    hints = run_rea(url, settings, lambda event: _event(event))
    draft = {"name": f"Discovered target: {parsed.netloc}", "url": url, "fetcher": "basic",
             "headers": {}, "params": {}, "method": "GET", "endpoints": [h.model_dump(mode="json") for h in hints],
             "schema_name": "Article", "mode": "auto", "max_pages": 1}
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(yaml.safe_dump(draft, sort_keys=False, allow_unicode=True), encoding="utf-8")
        if findings:
            findings.parent.mkdir(parents=True, exist_ok=True)
            findings.write_text(json.dumps({"target_url": url, "endpoints": draft["endpoints"]}, indent=2), encoding="utf-8")
    except OSError as exc:
        console.print(f"[red]Could not write discovery files: {exc}[/red]")
        raise typer.Exit(2) from exc
    console.print(f"[green]Draft profile saved:[/green] {out}")
    console.print(f"REA returned {len(hints)} hint(s). Review all findings before use.")


@app.command()
def setup() -> None:
    """Configure Peke using local files; this command never downloads model weights."""
    from rich.prompt import Confirm, Prompt

    config_path = user_settings_path()
    config_dir = config_path.parent
    current = load_settings()
    console.print("[bold]Peke first-run setup[/bold]")
    console.print("Choose a local GGUF model, or skip model setup for now.")
    model = Prompt.ask("Path to a local .gguf file (blank to skip)", default="")
    if model and not Path(model).expanduser().is_file():
        console.print("[red]That file does not exist. No configuration was changed.[/red]")
        raise typer.Exit(2)
    if model and Path(model).suffix.lower() != ".gguf":
        console.print("[red]The selected file must have a .gguf extension.[/red]")
        raise typer.Exit(2)
    config_dir.mkdir(parents=True, exist_ok=True)
    values = {
        "MODEL_PATH": str(Path(model).expanduser()) if model else "",
        "N_CTX": current.n_ctx,
        "N_GPU_LAYERS": current.n_gpu_layers,
        "N_THREADS": current.n_threads,
        "MAX_INPUT_CHARS": current.max_input_chars,
        "TEMPERATURE": current.temperature,
        "REQUEST_DELAY_SECONDS": current.request_delay_seconds,
        "OUTPUT_DIR": str(current.output_dir),
        "REA_COMMAND": current.rea_command or "",
        "REA_CDP_ENDPOINT": current.rea_cdp_endpoint,
        "FETCH_TIMEOUT": current.fetch_timeout,
    }
    try:
        config_path = save_user_settings(values)
    except (OSError, ValueError) as exc:
        console.print(f"[red]Could not write config: {exc}[/red]")
        raise typer.Exit(2) from exc
    console.print(f"[green]Saved configuration:[/green] {config_path}")

    if Confirm.ask("Connect Peke to your AI agents?", default=False):
        from peke.mcp.cli import install_command
        try:
            install_command(client=None, scope="user", transport="stdio", port=8765, dry_run=False, yes=False, skill=True)
        except SystemExit:
            pass

    if not Confirm.ask("Open the GUI now?", default=True):
        return
    try:
        from peke.gui.app import run_gui
    except ImportError as exc:
        console.print("Install the GUI with: pipx install 'peke[gui]'", markup=False)
        raise typer.Exit(1) from exc
    raise typer.Exit(code=run_gui())


@app.command()
def launch() -> None:
    """Run first-time setup if needed, then open the desktop GUI."""
    config_path = user_settings_path()
    if not config_path.exists():
        setup()
        return
    try:
        from peke.gui.app import run_gui
    except ImportError as exc:
        console.print("Install the GUI with: pipx install 'peke[gui]'", markup=False)
        raise typer.Exit(1) from exc
    raise typer.Exit(code=run_gui())


@app.command()
def update(
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation"),
) -> None:
    """Update the pipx-managed Peke installation."""
    import shutil

    from rich.prompt import Confirm

    pipx = shutil.which("pipx")
    if not pipx:
        console.print("pipx was not found. Update Peke with the installer you used.", markup=False)
        raise typer.Exit(1)
    if not yes and not Confirm.ask("Update Peke using pipx?", default=False):
        raise typer.Exit()
    import subprocess

    result = subprocess.run([pipx, "upgrade", "peke"], check=False)
    if result.returncode:
        raise typer.Exit(result.returncode)

    # Re-validate agent registrations
    from peke.mcp.clients.registrars import get_all_registrars
    for reg in get_all_registrars():
        if reg.is_registered():
            reg.install(dry_run=False)
    console.print("[green]Re-validated Peke MCP agent registrations.[/green]")


@app.command()
def uninstall(
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation"),
) -> None:
    """Uninstall the pipx-managed package; user configuration is retained."""
    import shutil
    import subprocess

    from rich.prompt import Confirm

    pipx = shutil.which("pipx")
    if not pipx:
        console.print("pipx was not found. Remove Peke using the installer you used.", markup=False)
        raise typer.Exit(1)
    if not yes and not Confirm.ask("Uninstall Peke? User configuration will be retained.", default=False):
        raise typer.Exit()

    from peke.mcp.clients.registrars import get_all_registrars
    registered = [r for r in get_all_registrars() if r.is_registered()]
    if registered and (yes or Confirm.ask("Remove Peke MCP server registrations from local AI agents?", default=True)):
        for reg in registered:
            reg.uninstall()
        console.print("[green]Removed Peke MCP agent registrations.[/green]")

    result = subprocess.run([pipx, "uninstall", "peke"], check=False)
    if result.returncode:
        raise typer.Exit(result.returncode)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", is_eager=True, help="Show version and banner"),
    no_banner: bool = typer.Option(False, "--no-banner", help="Disable terminal branding"),
    no_splash: bool = typer.Option(False, "--no-splash", help="Disable the GUI startup splash"),
) -> None:
    """Launch the GUI by default, or dispatch to a headless subcommand."""
    ctx.ensure_object(dict)
    ctx.obj["no_splash"] = no_splash
    if version:
        if not no_banner:
            print_banner(console, load_settings().rea_command)
        console.print(f"peke {__version__}", markup=False, highlight=False)
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        if not no_banner:
            print_banner(console, load_settings().rea_command)
        try:
            from peke.gui.app import run_gui
        except ImportError as exc:
            console.print("Install the GUI with: pipx install 'peke[gui]'", markup=False)
            raise typer.Exit(code=1) from exc
        raise typer.Exit(code=run_gui(no_splash=no_splash))


@app.command()
def gui(
    ctx: typer.Context,
    no_splash: bool = typer.Option(False, "--no-splash", help="Disable the GUI startup splash"),
) -> None:
    """Launch the PySide6 desktop workbench explicitly."""
    try:
        from peke.gui.app import run_gui
    except ImportError as exc:
        console.print("Install the GUI with: pipx install 'peke[gui]'", markup=False)
        raise typer.Exit(code=1) from exc
    raise typer.Exit(code=run_gui(no_splash=no_splash or bool((ctx.parent.obj or {}).get("no_splash", False))))
