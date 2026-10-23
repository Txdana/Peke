"""Terminal branding for Peke."""
from __future__ import annotations

import os
import shlex
import shutil
from rich.console import Console
from rich.text import Text


def rea_available(command: str | None) -> bool:
    """Best-effort check that the configured REA command's executable exists."""
    if not command:
        return False
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    return bool(parts and shutil.which(parts[0]))


def print_banner(console: Console, rea_command: str | None = None) -> None:
    """Render the startup banner, using plain text when color is disabled."""
    active = rea_available(rea_command)
    status = "[REA CLI Found]" if active else "[REA CLI Missing]"
    lines = [
        "┌──────────────────────────────────────────────────────┐",
        f"│  PEKE  {status:<20} local: llama.cpp  │",
        "└──────────────────────────────────────────────────────┘",
        "  │",
        "  ├── [01] REA Analysis  ──▶  Discovered Endpoint",
        "  ├── [02] Scrapling     ──▶  Page Retrieved",
        "  └── [03] Local SLM     ──▶  Clean JSON Formatted",
    ]
    plain = not console.is_terminal or bool(os.environ.get("NO_COLOR")) or console.no_color
    if plain:
        console.file.write("\n".join(lines) + "\n")
        console.file.flush()
        return
    for index, line in enumerate(lines):
        if index == 1:
            text = Text("│  PEKE  ")
            text.append(status, style="bold #2D5A4C" if active else "#6B5F57")
            text.append("                 local: llama.cpp  │")
            console.print(text)
        else:
            console.print(line, style="bold" if index == 0 else None, markup=False)
