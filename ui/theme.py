"""Theme definitions and stylesheet generation for AYMTECH PRO.

Every visual surface of the application (panels, cards, navigation,
status bar) is painted from a :class:`Palette`, so switching theme
recolors the whole application consistently.
"""

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class Palette:
    key: str
    name: str
    subtitle: str
    light: bool

    window: str          # deepest background colour
    panel_top: str       # panel gradient start
    panel_bottom: str    # panel gradient end
    border: str          # regular panel border
    border_strong: str   # highlighted border

    accent: str
    accent_2: str
    accent_rgb: Tuple[int, int, int]

    text: str
    text_dim: str
    text_muted: str

    ok: str
    warn: str
    danger: str

    nav_top: str
    nav_bottom: str

    overlay_top: int     # alpha of the background image overlay
    overlay_bottom: int


# ---------------------------------------------------------------
# PALETTES
# ---------------------------------------------------------------

DARK_BLUE = Palette(
    key="dark_blue",
    name="Dark Blue Neon",
    subtitle="Modern & Professional",
    light=False,
    window="#020a1e",
    panel_top="#061a3c",
    panel_bottom="#03102a",
    border="#0a4c8f",
    border_strong="#00c8ff",
    accent="#00d3ff",
    accent_2="#0a6bff",
    accent_rgb=(0, 211, 255),
    text="#eaf6ff",
    text_dim="#9fc6e8",
    text_muted="#6f93b8",
    ok="#2ee6a8",
    warn="#ffc247",
    danger="#ff5c7a",
    nav_top="#0a4fa8",
    nav_bottom="#052a5e",
    overlay_top=190,
    overlay_bottom=232,
)

BLACK_RED = Palette(
    key="black_red",
    name="Black & Red",
    subtitle="Powerful & Bold",
    light=False,
    window="#0b0304",
    panel_top="#1d0709",
    panel_bottom="#100305",
    border="#5e1215",
    border_strong="#ff3b30",
    accent="#ff4436",
    accent_2="#ff8a1f",
    accent_rgb=(255, 68, 54),
    text="#ffeceb",
    text_dim="#d8a6a3",
    text_muted="#a4736f",
    ok="#35e08a",
    warn="#ffb020",
    danger="#ff2d55",
    nav_top="#a01818",
    nav_bottom="#4a0a0c",
    overlay_top=200,
    overlay_bottom=238,
)

PURPLE_NEON = Palette(
    key="purple_neon",
    name="Purple Neon",
    subtitle="Stylish & Elegant",
    light=False,
    window="#08040f",
    panel_top="#1a0b3a",
    panel_bottom="#0c0422",
    border="#4a2196",
    border_strong="#b96bff",
    accent="#bb6bff",
    accent_2="#ff45c8",
    accent_rgb=(187, 107, 255),
    text="#f2e9ff",
    text_dim="#c3a9e6",
    text_muted="#8a72ab",
    ok="#3ee6b0",
    warn="#ffc247",
    danger="#ff5c9a",
    nav_top="#6a23c4",
    nav_bottom="#2c0a5e",
    overlay_top=200,
    overlay_bottom=240,
)

PLATINUM_LIGHT = Palette(
    key="platinum_light",
    name="Platinum Light",
    subtitle="Clean & Bright",
    light=True,
    window="#eef2f8",
    panel_top="#ffffff",
    panel_bottom="#eef3fa",
    border="#c6d6e8",
    border_strong="#0a84ff",
    accent="#0a7bff",
    accent_2="#00c2c7",
    accent_rgb=(10, 123, 255),
    text="#0f2137",
    text_dim="#43607f",
    text_muted="#6d839c",
    ok="#0fa968",
    warn="#c47a00",
    danger="#d92b45",
    nav_top="#0a7bff",
    nav_bottom="#0a5ad4",
    overlay_top=214,
    overlay_bottom=236,
)


PALETTES: Dict[str, Palette] = {
    p.key: p for p in (DARK_BLUE, BLACK_RED, PURPLE_NEON, PLATINUM_LIGHT)
}

THEME_ORDER = ["dark_blue", "black_red", "purple_neon", "platinum_light"]

DEFAULT_THEME = "dark_blue"


# ---------------------------------------------------------------
# DASHBOARD ACTION CARDS
# ---------------------------------------------------------------

# (start colour, end colour) for the six quick action cards
CARD_COLORS = [
    ("#0a86ff", "#044ba8"),   # Flashing Tools   - blue
    ("#a326e0", "#5c1090"),   # Unlock Tools     - purple
    ("#22b04b", "#0f7a33"),   # Screen Lock      - green
    ("#ff8d0a", "#c05500"),   # Android Tools    - orange
    ("#11b0a8", "#0a6e79"),   # IMEI Tools       - teal
    ("#a326e0", "#6a1499"),   # Settings         - violet
]


def rgba(rgb: Tuple[int, int, int], alpha: float) -> str:
    """Return a Qt CSS rgba() string."""
    return "rgba({}, {}, {}, {})".format(rgb[0], rgb[1], rgb[2], alpha)


def hex_rgb(value: str) -> Tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def mix(color: str, other: str, factor: float) -> str:
    """Blend two hex colours (factor 0 -> color, 1 -> other)."""
    a = hex_rgb(color)
    b = hex_rgb(other)
    out = tuple(int(round(a[i] + (b[i] - a[i]) * factor)) for i in range(3))
    return "#%02x%02x%02x" % out


def build_stylesheet(p: Palette, opacity: float = 0.9, arrow: str = "") -> str:
    """Application wide stylesheet for *p*.

    ``opacity`` is driven by the *Transparency* switch in the theme
    panel; panels are painted by custom widgets so only secondary
    widgets (inputs, tables, dialogs, scrollbars) are styled here.
    """

    panel = rgba(hex_rgb(p.panel_top), opacity)
    input_bg = rgba(hex_rgb(p.panel_bottom), min(1.0, opacity + 0.05))
    row_alt = mix(p.panel_top, p.panel_bottom, 0.5)
    dim = p.text_dim
    muted = p.text_muted

    return f"""
    QMainWindow, QDialog {{
        background-color: {p.window};
        color: {p.text};
    }}

    QWidget {{
        color: {p.text};
        font-family: "Segoe UI", "Noto Sans", "DejaVu Sans";
        font-size: 10pt;
    }}

    QLabel {{
        background: transparent;
        color: {p.text};
    }}

    QLabel#PageTitle {{
        font-size: 19pt;
        font-weight: 800;
        color: {p.text};
    }}

    QLabel#PageSubtitle {{
        font-size: 9.6pt;
        color: {muted};
    }}

    QLabel#SectionTitle {{
        font-size: 11.5pt;
        font-weight: 700;
        color: {p.accent};
    }}

    QLabel#CardTitle {{
        font-size: 10.6pt;
        font-weight: 700;
        color: {p.text};
    }}

    QLabel#DockTitle {{
        font-size: 11pt;
        font-weight: 700;
        color: {p.text};
    }}

    QLabel#DockLabel {{
        font-size: 9.4pt;
        color: {dim};
    }}

    QLabel#BrandSubtitle {{
        font-size: 9.4pt;
        font-weight: 700;
        color: {dim};
    }}

    QLabel#Tagline {{
        font-size: 10.4pt;
        font-weight: 700;
        font-style: italic;
        color: {p.accent};
    }}

    QLabel#TaglineSub {{
        font-size: 9.2pt;
        color: {dim};
    }}

    QFrame#ToolCard {{
        background-color: {panel};
        border: 1px solid {p.border};
        border-radius: 12px;
    }}

    QFrame#ToolCard QLabel {{
        background: transparent;
    }}

    QPushButton#HeaderButton {{
        background-color: {rgba(p.accent_rgb, 0.10)};
        color: {dim};
        border: 1px solid {p.border};
        border-radius: 8px;
        padding: 3px 10px;
        font-size: 9.2pt;
        font-weight: 600;
        text-align: center;
    }}

    QPushButton#HeaderButton:hover {{
        border: 1px solid {p.accent};
        color: {p.accent};
        background-color: {rgba(p.accent_rgb, 0.20)};
    }}

    QPushButton#HeaderButton::menu-indicator {{
        image: none;
        width: 0;
    }}

    QPushButton#WindowButton, QPushButton#WindowClose {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 7px;
        padding: 0;
    }}

    QPushButton#WindowButton:hover {{
        background-color: {rgba(p.accent_rgb, 0.22)};
        border: 1px solid {p.border};
    }}

    QPushButton#WindowClose:hover {{
        background-color: {rgba(hex_rgb(p.danger), 0.85)};
        border: 1px solid {p.danger};
    }}

    QToolTip {{
        background-color: {p.panel_top};
        color: {p.text};
        border: 1px solid {p.border_strong};
        border-radius: 6px;
        padding: 6px 8px;
    }}

    QPushButton {{
        background-color: {rgba(hex_rgb(p.panel_top), min(1.0, opacity + 0.03))};
        color: {p.text};
        border: 1px solid {p.border};
        border-radius: 9px;
        padding: 10px 14px;
        text-align: left;
        font-weight: 600;
    }}

    QPushButton:hover {{
        background-color: {rgba(p.accent_rgb, 0.22)};
        border: 1px solid {p.accent};
        color: {p.text};
    }}

    QPushButton:pressed {{
        background-color: {rgba(p.accent_rgb, 0.34)};
    }}

    QPushButton:disabled {{
        color: {muted};
        border: 1px solid {rgba(hex_rgb(p.border), 0.5)};
    }}

    QPushButton#Primary {{
        background-color: {p.accent_2};
        color: #ffffff;
        border: 1px solid {p.accent};
        border-radius: 10px;
        padding: 11px 18px;
        text-align: center;
        font-weight: 700;
    }}

    QPushButton#Primary:hover {{
        background-color: {p.accent};
        border: 1px solid {mix(p.accent, "#ffffff", 0.45)};
    }}

    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background-color: {input_bg};
        border: 1px solid {p.border};
        border-radius: 9px;
        padding: 9px 12px;
        color: {p.text};
        selection-background-color: {p.accent_2};
        selection-color: #ffffff;
    }}

    QLineEdit:focus, QComboBox:focus {{
        border: 1px solid {p.border_strong};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}

    QComboBox::down-arrow {{
        image: url("{arrow}");
        width: 10px;
        height: 6px;
        margin-right: 10px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {p.panel_top};
        color: {p.text};
        border: 1px solid {p.border_strong};
        border-radius: 8px;
        selection-background-color: {rgba(p.accent_rgb, 0.3)};
        outline: none;
        padding: 4px;
    }}

    QTableWidget, QTableView {{
        background-color: {input_bg};
        alternate-background-color: {row_alt};
        border: 1px solid {p.border};
        border-radius: 10px;
        gridline-color: {rgba(hex_rgb(p.border), 0.7)};
        selection-background-color: {rgba(p.accent_rgb, 0.3)};
        selection-color: {p.text};
        color: {p.text};
    }}

    QHeaderView::section {{
        background-color: {panel};
        color: {p.accent};
        padding: 10px;
        border: none;
        border-bottom: 2px solid {p.accent_2};
        font-weight: 700;
    }}

    QTableCornerButton::section {{
        background-color: {panel};
        border: none;
    }}

    QTextEdit, QPlainTextEdit {{
        background-color: {input_bg};
        color: {p.text};
        border: 1px solid {p.border};
        border-radius: 10px;
        padding: 10px;
        selection-background-color: {p.accent_2};
        selection-color: #ffffff;
    }}

    QScrollArea {{
        border: none;
        background: transparent;
    }}

    QScrollBar:vertical {{
        background: {rgba(hex_rgb(p.window), 0.45)};
        width: 6px;
        margin: 3px 1px;
        border-radius: 3px;
    }}

    QScrollBar::handle:vertical {{
        background: {rgba(p.accent_rgb, 0.40)};
        min-height: 28px;
        border-radius: 3px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {rgba(p.accent_rgb, 0.85)};
    }}

    QScrollArea > QWidget > QWidget {{
        background: transparent;
    }}

    QScrollArea QWidget#qt_scrollarea_viewport {{
        background: transparent;
    }}

    QScrollBar:horizontal {{
        background: {rgba(hex_rgb(p.window), 0.6)};
        height: 10px;
        margin: 2px;
        border-radius: 5px;
    }}

    QScrollBar::handle:horizontal {{
        background: {rgba(p.accent_rgb, 0.55)};
        min-width: 28px;
        border-radius: 5px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background: {p.accent};
    }}

    QScrollBar::add-line, QScrollBar::sub-line {{
        height: 0;
        width: 0;
    }}

    QScrollBar::add-page, QScrollBar::sub-page {{
        background: none;
    }}

    QProgressBar {{
        background-color: {input_bg};
        border: 1px solid {p.border};
        border-radius: 6px;
        text-align: center;
        color: {p.text};
    }}

    QProgressBar::chunk {{
        background-color: {p.accent_2};
        border-radius: 5px;
    }}

    QCheckBox, QRadioButton {{
        color: {p.text};
        spacing: 8px;
    }}

    QMenu {{
        background-color: {p.panel_top};
        color: {p.text};
        border: 1px solid {p.border};
        border-radius: 8px;
        padding: 6px;
    }}

    QMenu::item:selected {{
        background-color: {rgba(p.accent_rgb, 0.25)};
        border-radius: 6px;
    }}

    QMessageBox {{
        background-color: {p.panel_top};
    }}

    QMessageBox QLabel {{
        color: {p.text};
    }}

    QSizeGrip {{
        background: transparent;
        width: 14px;
        height: 14px;
    }}

    QLabel#InfoPanel {{
        background-color: {rgba(p.accent_rgb, 0.07)};
        border: 1px solid {rgba(p.accent_rgb, 0.35)};
        border-left: 3px solid {p.accent};
        border-radius: 12px;
        padding: 14px 16px;
        color: {dim};
        font-size: 9.6pt;
    }}

    QLabel#PageTitle:disabled {{
        color: {p.text};
    }}

    QLabel#PhoneFrame {{
        background-color: {input_bg};
        border: 1px solid {p.border};
        border-radius: 12px;
        color: {muted};
    }}

    QLabel[status="ok"] {{
        color: {p.ok};
        font-weight: 700;
    }}

    QLabel[status="warn"] {{
        color: {p.warn};
        font-weight: 700;
    }}

    QLabel[status="danger"] {{
        color: {p.danger};
        font-weight: 700;
    }}

    QLabel[status="info"] {{
        color: {p.accent};
        font-weight: 700;
    }}

    QLabel[hint="true"] {{
        color: {muted};
    }}
    """
