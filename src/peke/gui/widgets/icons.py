"""Small SVG stroke icons used by the desktop shell."""
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QLabel
from peke.gui import theme

PATHS = {
    "target": '<circle cx="11" cy="11" r="7"/><circle cx="11" cy="11" r="2"/><path d="M16 16l4 4"/>',
    "scraper": '<path d="M4 5h16M4 11h10M4 17h16"/><circle cx="18" cy="11" r="2"/>',
    "model": '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M12 3v18M4 7.5l16 9"/>',
    "schema": '<path d="M7 4H4v16h3M17 4h3v16h-3M9 8h6M9 12h6M9 16h6"/>',
    "collapse": '<path d="M15 5l-7 7 7 7"/>',
    "copy": '<rect x="8" y="8" width="11" height="12" rx="2"/><path d="M16 8V5H5v12h3"/>',
    "export": '<path d="M12 3v12m-4-4l4 4 4-4M5 17v3h14v-3"/>',
    "play": '<path d="M7 4l13 8-13 8z"/>',
    "cancel": '<path d="M6 6l12 12M18 6L6 18"/>',
}


def svg_icon(name: str, color: str = theme.MUTED_TEXT, size: int = 18) -> QPixmap:
    """Render a simple inline SVG stroke icon to a transparent pixmap."""
    paths = PATHS.get(name, PATHS["schema"])
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{paths}</svg>'
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    from PySide6.QtGui import QPainter
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def icon_label(name: str, accessible_name: str, color: str = theme.MUTED_TEXT) -> QLabel:
    label = QLabel()
    label.setPixmap(svg_icon(name, color))
    label.setAccessibleName(accessible_name)
    return label
