"""Desktop integration package for Peke."""
from peke.desktop.integration import (
    install_desktop_integration,
    is_desktop_installed,
    uninstall_desktop_integration,
)

__all__ = [
    "install_desktop_integration",
    "uninstall_desktop_integration",
    "is_desktop_installed",
]
