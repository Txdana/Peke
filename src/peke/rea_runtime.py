"""Locate the REA CLI that ships inside the Peke installer.

The Windows installer places a private Node.js runtime and the pinned ``rea-agents``
package under ``<install dir>/rea``. Nothing is downloaded at run time, and the
user's PATH is never modified. A user-configured REA_COMMAND always wins.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


def _bundle_roots() -> list[Path]:
    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent / "rea")
    # Source checkouts / pip installs: <repo>/build/rea created by scripts/embed_rea.ps1
    roots.append(Path(__file__).resolve().parents[2] / "build" / "rea")
    return roots


def bundled_rea_command() -> str | None:
    """Return a shell-style command string for the bundled REA, or None."""
    for root in _bundle_roots():
        node = root / "node" / ("node.exe" if sys.platform == "win32" else "bin/node")
        entry = root / "app" / "node_modules" / "rea-agents" / "scripts" / "rea.mjs"
        if node.is_file() and entry.is_file():
            # Forward slashes survive shlex.split on Windows and are accepted by node.
            return f'"{node.as_posix()}" "{entry.as_posix()}"'
    return None


def default_rea_command() -> str | None:
    return bundled_rea_command() or (("rea") if shutil.which("rea") else None)
