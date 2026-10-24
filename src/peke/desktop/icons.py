"""Peke application icon installer."""
import shutil
from pathlib import Path

from peke.desktop.paths import get_icon_dir


def install_app_icon() -> Path:
    """Install Peke SVG/PNG application icon into user icon directory."""
    target_dir = get_icon_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    icon_file = target_dir / "peke.svg"

    source_svg = Path(__file__).parent.parent / "gui" / "assets" / "peke.svg"
    if source_svg.is_file():
        shutil.copy2(source_svg, icon_file)
    else:
        # Fallback SVG content if source SVG not present
        icon_file.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
            '<circle cx="50" cy="50" r="45" fill="#C85A32"/>'
            '<text x="50" y="65" font-size="45" text-anchor="middle" fill="#FFFFFF" font-family="sans-serif" font-weight="bold">P</text>'
            '</svg>',
            encoding="utf-8",
        )
    return icon_file


def remove_app_icon() -> None:
    """Remove installed Peke application icon."""
    target_dir = get_icon_dir()
    icon_file = target_dir / "peke.svg"
    if icon_file.is_file():
        icon_file.unlink(missing_ok=True)
