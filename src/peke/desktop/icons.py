"""Peke application icon installer."""
import shutil
from pathlib import Path

from peke.desktop.paths import get_icon_dir


def install_app_icon() -> Path:
    """Install Peke SVG/PNG application icon into user icon directory."""
    target_dir = get_icon_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    source_png = Path(__file__).parent.parent / "gui" / "assets" / "peke.png"
    source_svg = Path(__file__).parent.parent / "gui" / "assets" / "peke.svg"

    if source_png.is_file():
        icon_file = target_dir / "peke.png"
        shutil.copy2(source_png, icon_file)
        return icon_file
    elif source_svg.is_file():
        icon_file = target_dir / "peke.svg"
        shutil.copy2(source_svg, icon_file)
        return icon_file
    else:
        icon_file = target_dir / "peke.svg"
        # Fallback SVG content if source icon not present
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
    for name in ("peke.png", "peke.svg"):
        icon_file = target_dir / name
        if icon_file.is_file():
            icon_file.unlink(missing_ok=True)
