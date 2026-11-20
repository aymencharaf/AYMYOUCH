"""Dashboard page: hero block with mascot and the action card grid."""

from __future__ import annotations

from typing import List, Sequence, Tuple

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from . import icons
from . import theme as th
from .shell import HeroBlock
from .widgets import ActionCard


DEFAULT_CARDS: Sequence[Tuple[str, str, str, str]] = (
    # key, icon, title, subtitle
    ("Firmware Center", "firmware", "Flashing Tools", "Flash Firmware"),
    ("Screen Lock Service", "unlock", "Unlock Tools", "Remove FRP & Unlock"),
    ("Screen Lock Service", "shield", "Screen Lock Service", "Diagnose & Recover"),
    ("Android Tools", "android", "Android Tools", "Advanced Features"),
    ("IMEI & Network", "imei", "IMEI Tools", "Repair IMEI"),
    ("Settings", "settings", "Settings", "Customize Your Experience"),
)


class CardGrid(QWidget):
    """2 x 3 responsive grid of gradient action cards."""

    navigate = Signal(str)
    settings_requested = Signal()

    def __init__(self, palette: th.Palette, parent=None):
        super().__init__(parent)
        self.palette_ = palette
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(14)
        self.cards: List[ActionCard] = []

        for index, (target, icon_name, title, subtitle) in enumerate(DEFAULT_CARDS):
            colors = th.CARD_COLORS[index % len(th.CARD_COLORS)]
            card = ActionCard(
                target,
                icons.make_icon(icon_name, "#ffffff", 24),
                title,
                subtitle,
                colors,
            )
            card.setMinimumHeight(92)
            card.clicked.connect(self._on_card)
            self.grid.addWidget(card, index // 3, index % 3)
            self.cards.append(card)

        for col in range(3):
            self.grid.setColumnStretch(col, 1)

    def set_available_width(self, width: int) -> None:
        """Choose the column count from the *viewport* width.

        Using the widget's own width would be circular: the cards define
        the minimum width, which in turn widens the widget.
        """
        columns = 3
        if width < 400:
            columns = 1
        elif width < 660:
            columns = 2
        if columns != getattr(self, "_columns", 3):
            self._relayout(columns)
        compact = width < 960
        for card in self.cards:
            card.set_compact(compact)

    def _relayout(self, columns: int) -> None:
        self._columns = columns
        for index, card in enumerate(self.cards):
            self.grid.addWidget(card, index // columns, index % columns)
        for col in range(3):
            self.grid.setColumnStretch(col, 1 if col < columns else 0)

    def _on_card(self, target: str) -> None:
        if target == "Settings":
            self.settings_requested.emit()
        else:
            self.navigate.emit(target)

    def set_palette(self, palette: th.Palette) -> None:
        self.palette_ = palette

    def set_texts(self, texts: Sequence[Tuple[str, str]]) -> None:
        for card, (title, subtitle) in zip(self.cards, texts):
            card.set_texts(title, subtitle)


class DashboardPage(QWidget):
    """Hero + action cards, clipped inside a glass panel."""

    navigate = Signal(str)
    settings_requested = Signal()

    def __init__(self, palette: th.Palette, opacity: float = 0.9, parent=None):
        super().__init__(parent)
        self.palette_ = palette

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        scroll.setWidget(body)

        inner = QVBoxLayout(body)
        inner.setContentsMargins(16, 6, 8, 4)
        inner.setSpacing(14)

        self.hero = HeroBlock(palette)
        inner.addWidget(self.hero, 4)

        self.grid = CardGrid(palette)
        self.grid.navigate.connect(self.navigate.emit)
        self.grid.settings_requested.connect(self.settings_requested.emit)
        inner.addWidget(self.grid, 4)
        self.body = body
        self.scroll = scroll
        QTimer.singleShot(0, self._refresh_layout)

    def _refresh_layout(self) -> None:
        self.grid.set_available_width(self.scroll.viewport().width() - 28)

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "scroll"):
            self.grid.set_available_width(self.scroll.viewport().width() - 28)

    def set_palette(self, palette: th.Palette, opacity: float) -> None:
        self.palette_ = palette
        self.hero.set_palette(palette)
        self.grid.set_palette(palette)
