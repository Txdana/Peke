"""Cross-platform desktop application registration and shortcut manager."""
import logging
import os
import shutil
import subprocess
import sys

from peke.desktop import paths
from peke.desktop.icons import install_app_icon, remove_app_icon

logger = logging.getLogger(__name__)


def is_desktop_installed() -> bool:
    if sys.platform.startswith("linux") or sys.platform == "darwin":
        return paths.get_desktop_entry_path().is_file()
    elif sys.platform == "win32":
        return paths.get_windows_start_menu_path().is_file()
    return True


def _create_windows_shortcut(target_exe: str, shortcut_path: paths.Path) -> None:
    ps_script = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{shortcut_path}')
$Shortcut.TargetPath = '{target_exe}'
$Shortcut.Arguments = 'launch'
$Shortcut.Save()
"""
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script], check=False)


def install_desktop_integration() -> dict[str, str]:
    """Register Peke as a native desktop application with icon and launcher shortcut."""
    created = {}
    icon_path = install_app_icon()
    created["icon"] = str(icon_path)

    peke_bin = shutil.which("peke") or f"{sys.executable} -m peke"

    if sys.platform.startswith("linux") or sys.platform == "darwin":
        entry_path = paths.get_desktop_entry_path()
        entry_path.parent.mkdir(parents=True, exist_ok=True)

        content = f"""[Desktop Entry]
Type=Application
Name=Peke
Comment=Local-first open-source data extraction workbench
Exec={peke_bin} launch
Icon={icon_path}
Terminal=false
Categories=Utility;Development;DataExtraction;
StartupWMClass=peke
"""
        entry_path.write_text(content, encoding="utf-8")
        if os.name != "nt":
            entry_path.chmod(0o755)
        created["desktop_entry"] = str(entry_path)

    elif sys.platform == "win32":
        shortcut_path = paths.get_windows_start_menu_path()
        shortcut_path.parent.mkdir(parents=True, exist_ok=True)
        _create_windows_shortcut(peke_bin, shortcut_path)
        created["start_menu_shortcut"] = str(shortcut_path)

    logger.info("Installed desktop integration for Peke: %s", created)
    return created


def uninstall_desktop_integration() -> list[str]:
    """Remove desktop shortcuts, icon files, and OS application registrations."""
    removed = []
    if sys.platform.startswith("linux") or sys.platform == "darwin":
        entry_path = paths.get_desktop_entry_path()
        if entry_path.is_file():
            entry_path.unlink(missing_ok=True)
            removed.append(str(entry_path))

    elif sys.platform == "win32":
        shortcut_path = paths.get_windows_start_menu_path()
        if shortcut_path.is_file():
            shortcut_path.unlink(missing_ok=True)
            removed.append(str(shortcut_path))

    remove_app_icon()
    removed.append("app_icon")
    return removed
