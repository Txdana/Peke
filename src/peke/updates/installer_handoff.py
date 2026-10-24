"""Installer handoff for safely applying updates using pipx."""
import logging
import shutil
import subprocess
from pathlib import Path

from peke.updates.updater import UpdateError

logger = logging.getLogger(__name__)


def perform_pipx_upgrade(wheel_path: Path, req_path: Path) -> bool:
    """Execute pipx install --force --pip-args='--no-deps' and pipx runpip."""
    pipx = shutil.which("pipx")
    if not pipx:
        raise UpdateError("pipx is not available in system PATH")

    try:
        # 1. Install wheel
        res1 = subprocess.run([pipx, "install", "--force", "--pip-args=--no-deps", str(wheel_path)], check=False, capture_output=True)
        if res1.returncode != 0:
            err = res1.stderr.decode("utf-8", errors="replace")
            raise UpdateError(f"pipx install failed: {err}")

        # 2. Install locked dependencies
        res2 = subprocess.run([pipx, "runpip", "peke", "install", "--require-hashes", "-r", str(req_path)], check=False, capture_output=True)
        if res2.returncode != 0:
            err = res2.stderr.decode("utf-8", errors="replace")
            raise UpdateError(f"pipx locked dependency installation failed: {err}")

        return True
    except Exception as exc:
        if isinstance(exc, UpdateError):
            raise
        raise UpdateError(f"Pipx upgrade execution failed: {exc}") from exc
