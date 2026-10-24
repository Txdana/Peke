"""Desktop launcher entry point for Peke (also the frozen executable's single entry)."""
import faulthandler
import multiprocessing
import os
import runpy
import sys
import traceback
from pathlib import Path


def _log_dir() -> Path:
    from platformdirs import user_log_dir

    path = Path(user_log_dir("peke", "Peke"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _fix_windowed_streams() -> None:
    """A windowed (console=False) PyInstaller build has no stdout/stderr; libraries that
    print or log to them would crash at startup. Point them somewhere harmless."""
    try:
        log = open(_log_dir() / "peke-gui.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115
    except OSError:
        log = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    if sys.stdout is None:
        sys.stdout = log
    if sys.stderr is None:
        sys.stderr = log
    try:
        faulthandler.enable(file=log)
    except (RuntimeError, ValueError):
        pass


def _dispatch_frozen_child(argv: list[str]) -> int | None:
    """In the frozen build sys.executable is Peke.exe, so helper processes the app
    spawns (bundled SearXNG, MCP server) come back here instead of opening a GUI."""
    if len(argv) >= 3 and argv[1] == "-m":
        sys.argv = [argv[2], *argv[3:]]
        runpy.run_module(argv[2], run_name="__main__", alter_sys=True)
        return 0
    if len(argv) >= 2 and argv[1] != "launch" and not argv[1].startswith("--multiprocessing"):
        from peke.cli import app

        sys.argv = ["peke", *argv[1:]]
        app()
        return 0
    return None


def launch_desktop_app() -> int:
    """Entry point for OS desktop shortcuts to launch PySide6 workbench GUI."""
    multiprocessing.freeze_support()
    frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        _fix_windowed_streams()
        handled = _dispatch_frozen_child(sys.argv)
        if handled is not None:
            return handled
    try:
        from peke.gui.app import run_gui

        return run_gui()
    except BaseException as exc:  # noqa: BLE001 - last-resort crash report
        text = traceback.format_exc()
        try:
            (_log_dir() / "startup-error.log").write_text(text, encoding="utf-8")
        except OSError:
            pass
        if frozen and sys.platform == "win32":
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0, f"Peke could not start:\n\n{exc}\n\nDetails: {_log_dir() / 'startup-error.log'}", "Peke", 0x10)
        else:
            sys.stderr.write(f"Failed to launch Peke GUI: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(launch_desktop_app())
