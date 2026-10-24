"""OS-specific desktop application path resolution."""
import os
import sys
from pathlib import Path


def get_desktop_entry_path() -> Path:
    """Return XDG desktop entry path for Linux."""
    data_dir = os.getenv("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    return Path(data_dir) / "applications" / "peke.desktop"


def get_icon_dir() -> Path:
    """Return user-level icon directory."""
    if sys.platform.startswith("linux"):
        data_dir = os.getenv("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
        return Path(data_dir) / "icons" / "hicolor" / "scalable" / "apps"
    elif sys.platform == "win32":
        appdata = os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return Path(appdata) / "Peke" / "icons"
    else: # darwin / macOS
        return Path.home() / "Applications" / "Peke.app" / "Contents" / "Resources"


def get_windows_start_menu_path() -> Path:
    """Return Windows Start Menu Programs shortcut path."""
    appdata = os.getenv("APPDATA", str(Path.home() / "AppData" / "Roaming"))
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Peke.lnk"
