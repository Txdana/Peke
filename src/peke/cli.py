"""Typer command-line interface for Peke's workbench and headless pipeline."""
import importlib.util
import json
import logging
import platform
import shutil
import subprocess
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

from peke import __version__
from peke.banner import print_banner
from peke.config import (
    ConfigError,
    load_settings,
    save_user_settings,
    user_config_toml_path,
    user_settings_path,
)
from peke.desktop import (
    install_desktop_integration,
    is_desktop_installed,
    uninstall_desktop_integration,
)
from peke.discover import run_rea
from peke.mcp.cli import mcp_app
from peke.models import DEFAULT_MODEL_FILE, DEFAULT_MODEL_REPO, ModelManager, ModelManagerError
from peke.pipeline import Event, Pipeline
from peke.profile import ProfileError, load_profile
from peke.schemas import get_schema, list_schemas
from peke.updates import check_for_updates

app = typer.Typer(name="peke", help="Peke: local-first data extraction workbench", no_args_is_help=False)
app.add_typer(mcp_app, name="mcp", help="Peke MCP server management and agent registration")

models_app = typer.Typer(name="models", help="Managed GGUF model downloads and selection")
app.add_typer(models_app, name="models")

desktop_app = typer.Typer(name="desktop", help="OS desktop application integration and launcher shortcuts")
app.add_typer(desktop_app, name="desktop")

console = Console()


@desktop_app.command("install")
def desktop_install_command() -> None:
    """Register OS desktop application entry and shortcuts."""
    res = install_desktop_integration()
    console.print(f"[green]Installed desktop application shortcuts:[/green] {res}")


@desktop_app.command("uninstall")
def desktop_uninstall_command() -> None:
    """Remove OS desktop application entry and shortcuts."""
    removed = uninstall_desktop_integration()
    console.print(f"[green]Removed desktop application shortcuts:[/green] {removed}")


@models_app.command("list")
def models_list_command() -> None:
    """List managed local GGUF models."""
    manager = ModelManager()
    models = manager.list_models()
    if not models:
        console.print("No downloaded models found in managed store.")
        return
    table = Table(title="Managed GGUF Models", show_header=True, header_style="bold")
    table.add_column("Active", justify="center")
    table.add_column("Repository")
    table.add_column("File")
    table.add_column("Size (MB)", justify="right")
    table.add_column("Path")
    for m in models:
        active_str = "[green]*[/green]" if m.active else ""
        table.add_row(
            active_str,
            m.repo,
            m.file,
            f"{m.size_bytes / (1024 * 1024):.1f}",
            m.local_path,
        )
    console.print(table)


@models_app.command("download")
def models_download_command(
    repo: str = typer.Argument(DEFAULT_MODEL_REPO, help="Hugging Face repository ID"),
    file: str = typer.Argument(DEFAULT_MODEL_FILE, help="GGUF filename in repository"),
) -> None:
    """Download a GGUF model from Hugging Face Hub."""
    from rich.progress import (
        BarColumn,
        DownloadColumn,
        Progress,
        TextColumn,
        TimeRemainingColumn,
        TransferSpeedColumn,
    )

    manager = ModelManager()
    console.print(f"Downloading model [bold]{repo}/{file}[/bold]...")

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Downloading", total=100)

        def _cb(downloaded: int, total: int, speed: float, eta: float) -> None:
            if total > 0:
                progress.update(task, completed=downloaded, total=total)

        try:
            info = manager.download_model(repo=repo, file=file, progress_callback=_cb)
            console.print(f"[green]Model ready and activated:[/green] {info.local_path}")
        except ModelManagerError as exc:
            console.print(f"[red]Download failed: {exc}[/red]")
            raise typer.Exit(1) from exc


@models_app.command("remove")
def models_remove_command(
    target: str = typer.Argument(..., help="Model repository/file or filename to remove"),
) -> None:
    """Remove a downloaded GGUF model."""
    manager = ModelManager()
    if manager.remove_model(target):
        console.print(f"[green]Removed model:[/green] {target}")
    else:
        console.print(f"[red]Model not found in store:[/red] {target}")
        raise typer.Exit(1)


@models_app.command("use")
def models_use_command(
    target: str = typer.Argument(..., help="Model key (repo/file) or local file path"),
) -> None:
    """Set the active model for local LLM extraction."""
    manager = ModelManager()
    try:
        info = manager.set_active_model(target)
        save_user_settings({"MODEL_PATH": info.local_path})
        console.print(f"[green]Active model set to:[/green] {info.local_path}")
    except ModelManagerError as exc:
        console.print(f"[red]Failed to activate model: {exc}[/red]")
        raise typer.Exit(1) from exc


@models_app.command("gc")
def models_gc_command(
    keep_last: int = typer.Option(1, "--keep-last", help="Number of recently used models to retain"),
) -> None:
    """Garbage collect older, non-active downloaded models."""
    manager = ModelManager()
    removed = manager.gc(keep_last=keep_last)
    if removed:
        console.print(f"[green]Removed {len(removed)} old model(s):[/green] {', '.join(removed)}")
    else:
        console.print("No models were removed by garbage collection.")


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

    desktop_ok = is_desktop_installed()
    table.add_row("Desktop Integration", "PASS" if desktop_ok else "OPTIONAL",
                  "Launcher registered" if desktop_ok else "Run 'peke desktop install' to register application")

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
    console.print("[dim]To remove Peke completely, run: peke uninstall --purge[/dim]")


@app.command()
def discover(
    url: str = typer.Argument(..., help="Target website URL"),
    out: Path = typer.Option(Path("profiles/discovered.yaml"), "--out", help="Draft profile YAML path"),
    findings: Path | None = typer.Option(None, "--findings", help="Also save normalized findings JSON"),
    deep: bool = typer.Option(False, "--deep", help="Run multi-agent deep discovery reconnaissance"),
    subagent_provider: str | None = typer.Option(None, "--subagent-provider", help="Override sub-agent provider"),
) -> None:
    """Run optional REA or deep sub-agent discovery and create a reviewable draft profile."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        console.print("[red]Provide a valid http:// or https:// URL.[/red]")
        raise typer.Exit(2)
    settings = load_settings()

    if deep:
        from peke.agents import Orchestrator
        from peke.providers import get_provider

        prov = get_provider(subagent_provider, settings=settings) if subagent_provider else None
        orchestrator = Orchestrator(settings=settings, on_event=_event)
        recon_result = orchestrator.run_reconnaissance(url, subagent_provider=prov)
        hints_data = recon_result.bundle.get("endpoints", [])
        console.print(f"[green]Deep discovery completed (Run ID: {recon_result.run_id}).[/green]")
    else:
        hints = run_rea(url, settings, lambda event: _event(event))
        hints_data = [h.model_dump(mode="json") for h in hints]

    draft = {
        "name": f"Discovered target: {parsed.netloc}",
        "url": url,
        "fetcher": "basic",
        "headers": {},
        "params": {},
        "method": "GET",
        "endpoints": hints_data,
        "schema_name": "Article",
        "mode": "auto",
        "max_pages": 1,
    }
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
    console.print(f"Returned {len(hints_data)} endpoint hint(s). Review all findings before use.")


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
    check: bool = typer.Option(False, "--check", help="Check for available updates without installing"),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation"),
) -> None:
    """Check for updates or update the Peke installation."""
    if check:
        res = check_for_updates()
        console.print(res.message)
        return

    pipx = shutil.which("pipx")
    if not pipx:
        console.print("pipx was not found. Update Peke with the installer you used.", markup=False)
        raise typer.Exit(1)
    if not yes and not Confirm.ask("Update Peke using pipx?", default=False):
        raise typer.Exit()

    result = subprocess.run([pipx, "upgrade", "peke"], check=False)
    if result.returncode:
        raise typer.Exit(result.returncode)

    from peke.mcp.clients.registrars import get_all_registrars
    for reg in get_all_registrars():
        if reg.is_registered():
            reg.install(dry_run=False)
    console.print("[green]Re-validated Peke MCP agent registrations.[/green]")


@app.command()
def uninstall(
    purge: bool = typer.Option(False, "--purge", help="Completely purge Peke installation and configuration"),
    keep_models: bool = typer.Option(False, "--keep-models", help="Retain downloaded GGUF models"),
    keep_config: bool = typer.Option(False, "--keep-config", help="Retain user configuration settings"),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation prompt"),
) -> None:
    """Uninstall Peke, desktop shortcuts, and optionally purge user configuration/models."""
    console.print("[bold red]Peke Removal Plan[/bold red]")
    plan_items = [
        "- Desktop shortcuts and application registration",
        "- MCP agent server registrations",
    ]
    if purge:
        if not keep_config:
            plan_items.append("- User settings and secrets (~/.peke/settings.json, config.toml, secrets.toml)")
        if not keep_models:
            plan_items.append("- Downloaded GGUF models (~/.peke/models)")
        plan_items.append("- Run history and logs (~/.peke/runs)")
    plan_items.append("- Managed Python package environment")

    for item in plan_items:
        console.print(item)

    if not yes and not Confirm.ask("Proceed with removal?", default=False):
        console.print("Uninstall cancelled.")
        raise typer.Exit()

    # 1. Desktop integration removal
    uninstall_desktop_integration()
    console.print("[green]Removed desktop application shortcuts.[/green]")

    # 2. MCP cleanup
    from peke.mcp.clients.registrars import get_all_registrars
    registered = [r for r in get_all_registrars() if r.is_registered()]
    if registered:
        for reg in registered:
            reg.uninstall()
        console.print("[green]Removed Peke MCP agent registrations.[/green]")

    # 3. Purge user data if requested
    if purge:
        peke_dir = Path.home() / ".peke"
        if peke_dir.is_dir():
            if not keep_models:
                models_dir = peke_dir / "models"
                if models_dir.is_dir():
                    shutil.rmtree(models_dir, ignore_errors=True)
            if not keep_config:
                settings_file = user_settings_path()
                settings_file.unlink(missing_ok=True)
                config_file = user_config_toml_path()
                config_file.unlink(missing_ok=True)
                secrets_file = peke_dir / "secrets.toml"
                secrets_file.unlink(missing_ok=True)
            runs_dir = peke_dir / "runs"
            if runs_dir.is_dir():
                shutil.rmtree(runs_dir, ignore_errors=True)
        console.print("[green]Purged requested Peke data and history.[/green]")

    # 4. Pipx uninstall
    pipx = shutil.which("pipx")
    if pipx:
        result = subprocess.run([pipx, "uninstall", "peke"], check=False)
        if result.returncode == 0:
            console.print("[green]Successfully uninstalled Peke package.[/green]")


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
