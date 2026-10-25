"""Central color palette and QSS loader for the Peke desktop UI."""
from pathlib import Path

BACKGROUND = "#FBF9F5"
SURFACE = "#F2EEE7"
DIVIDER = "#E5DFD5"
BORDER = "#E2D9CC"
SIDEBAR = "#EAE4DC"
TEXT = "#2C2523"
MUTED_TEXT = "#6B5F57"
TERRACOTTA = "#C85A32"
TERRACOTTA_TEXT = "#B04420"
BUTTON = "#B94E27"
SAGE = "#2D5A4C"
CONSOLE_BG = "#1A1615"
CONSOLE_TIMESTAMP = "#8FC4AF"
CONSOLE_HIGHLIGHT = "#F09872"
CONSOLE_MUTED_TEXT = "#B7AAA1"
JSON_NUMBER = "#B04A24"
WHITE = "#FFFFFF"


def load_stylesheet() -> str:
    """Load the QSS file and replace named color tokens with palette constants."""
    path = Path(__file__).with_name("theme.qss")
    source = path.read_text(encoding="utf-8")
    palette = {
        "@BACKGROUND": BACKGROUND, "@SURFACE": SURFACE, "@DIVIDER": DIVIDER,
        "@BORDER": BORDER, "@SIDEBAR": SIDEBAR, "@TEXT": TEXT,
        "@MUTED_TEXT": MUTED_TEXT, "@TERRACOTTA": TERRACOTTA,
        "@BUTTON": BUTTON, "@SAGE": SAGE, "@CONSOLE_BG": CONSOLE_BG,
        "@CONSOLE_TIMESTAMP": CONSOLE_TIMESTAMP, "@CONSOLE_HIGHLIGHT": CONSOLE_HIGHLIGHT, "@JSON_NUMBER": JSON_NUMBER, "@TERRACOTTA_TEXT": TERRACOTTA_TEXT, "@CONSOLE_MUTED_TEXT": CONSOLE_MUTED_TEXT,
        "@WHITE": WHITE,
    }
    # Longest token first, so "@TERRACOTTA" cannot clobber "@TERRACOTTA_TEXT".
    for token, color in sorted(palette.items(), key=lambda item: len(item[0]), reverse=True):
        source = source.replace(token, color)
    return source
