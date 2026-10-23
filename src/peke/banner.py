"""Terminal banner utility for Peke CLI and desktop application."""

import os
import sys

from rich.console import Console


def get_banner_string(mcp_active: bool = False) -> str:
    """Return plain-text representation of the banner."""
    mcp_chip = "[MCP Active]" if mcp_active else "[MCP Off]"
    return f"""┌──────────────────────────────────────────────────────┐
│  PEKE  {mcp_chip:<12}                local: llama.cpp  │
└──────────────────────────────────────────────────────┘
  │
  ├── [01] REA Analysis  ──▶  Discovered Endpoint
  ├── [02] Scrapling     ──▶  Cloudflare Bypassed
  └── [03] Local SLM     ──▶  Clean JSON Formatted"""


def print_banner(console: Console | None = None, mcp_active: bool = False) -> None:
    """Render terminal banner with rich monospace formatting.

    Respects NO_COLOR environment variable and non-TTY stdout.

    :param console: Optional Rich console instance.
    :param mcp_active: True if REA MCP server is active/reachable.
    """
    if console is None:
        console = Console()

    no_color = bool(os.environ.get("NO_COLOR")) or not sys.stdout.isatty() or console.no_color

    mcp_chip = "[MCP Active]" if mcp_active else "[MCP Off]"
    mcp_color = "bold #87A96B" if mcp_active else "dim gray"  # Sage green vs muted gray

    if no_color:
        banner_text = get_banner_string(mcp_active=mcp_active)
        console.print(banner_text)
    else:
        top_box = f"""[bold cyan]┌──────────────────────────────────────────────────────┐[/bold cyan]
[bold cyan]│[/bold cyan]  [bold white]PEKE[/bold white]  [{mcp_color}]{mcp_chip:<12}[/{mcp_color}]                [dim]local: llama.cpp[/dim]  [bold cyan]│[/bold cyan]
[bold cyan]└──────────────────────────────────────────────────────┘[/bold cyan]
  [cyan]│[/cyan]
  [cyan]├──[/cyan] [bold #D97706][01] REA Analysis[/bold #D97706]  [dim]──▶[/dim]  [dim]Discovered Endpoint[/dim]
  [cyan]├──[/cyan] [bold #D97706][02] Scrapling[/bold #D97706]     [dim]──▶[/dim]  [dim]Cloudflare Bypassed[/dim]
  [cyan]└──[/cyan] [bold #D97706][03] Local SLM[/bold #D97706]     [dim]──▶[/dim]  [dim]Clean JSON Formatted[/dim]"""
        console.print(top_box)
