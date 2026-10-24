"""Base definitions for MCP client registrars."""

import shutil
import sys
from pathlib import Path
from typing import Any


def get_peke_launcher() -> str:
    """Return absolute path to peke launcher executable."""
    which_peke = shutil.which("peke")
    if which_peke:
        return str(Path(which_peke).resolve())
    return str(Path(sys.executable).resolve())


class ClientRegistrar:
    """Base class for registering Peke MCP server with local AI agents."""

    client_id: str = "base"
    display_name: str = "Base Client"

    def detect_installed(self) -> bool:
        """Return True if the AI agent client is detected on this machine."""
        path = self.get_config_path()
        if path and (path.exists() or path.parent.exists()):
            return True
        return False

    def get_config_path(self) -> Path | None:
        """Return canonical config file path for this client, or None if inapplicable."""
        return None

    def is_registered(self) -> bool:
        """Return True if Peke is registered with this client."""
        return False

    def plan_install(self, scope: str = "user", transport: str = "stdio", port: int = 8765) -> tuple[dict[str, Any] | None, str]:
        """Return planned config dict and human-readable diff text."""
        return None, ""

    def install(
        self,
        scope: str = "user",
        transport: str = "stdio",
        port: int = 8765,
        dry_run: bool = False,
    ) -> bool:
        """Execute installation with backup."""
        return False

    def uninstall(self, dry_run: bool = False) -> bool:
        """Remove Peke registration from client config."""
        return False
