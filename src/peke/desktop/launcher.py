"""Desktop launcher entry point for launching Peke GUI."""
import sys


def launch_desktop_app() -> int:
    """Entry point for OS desktop shortcuts to launch PySide6 workbench GUI."""
    try:
        from peke.gui.app import run_gui

        return run_gui()
    except Exception as exc:
        sys.stderr.write(f"Failed to launch Peke GUI: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(launch_desktop_app())
