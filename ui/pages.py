"""Factory helpers that turn the existing tool pages into themed pages."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from . import theme as th
from .widgets import Panel


class PageShell(QWidget):
    """Wraps an existing page in the standard glass panel."""

    def __init__(self, palette: th.Palette, content: QWidget, opacity: float = 0.9, parent=None):
        super().__init__(parent)
        self.palette_ = palette
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.panel = Panel(palette, radius=16.0, opacity=opacity)
        layout.addWidget(self.panel)

        inner = QVBoxLayout(self.panel)
        inner.setContentsMargins(14, 14, 14, 14)
        inner.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        inner.addWidget(scroll)
        self.scroll = scroll

    def set_palette(self, palette: th.Palette, opacity: float) -> None:
        self.palette_ = palette
        self.panel.set_palette(palette, opacity)
