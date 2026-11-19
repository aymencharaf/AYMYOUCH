"""Inline busy indicator used while a background task is running."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from . import theme as th


class BusySpinner(QWidget):
    """Small rotating arc; invisible (but layout-stable) when inactive."""

    def __init__(self, palette: th.Palette, size: int = 18, parent=None):
        super().__init__(parent)
        self.palette_ = palette
        self._angle = 0
        self._active = False
        self.setFixedSize(size, size)
        self.timer = QTimer(self)
        self.timer.setInterval(28)
        self.timer.timeout.connect(self._tick)

    # ---- state ----
    def set_palette(self, palette: th.Palette) -> None:
        self.palette_ = palette
        self.update()

    def set_active(self, active: bool) -> None:
        if active == self._active:
            return
        self._active = active
        if active:
            self.timer.start()
        else:
            self.timer.stop()
        self.update()

    def is_active(self) -> bool:
        return self._active

    def _tick(self) -> None:
        self._angle = (self._angle + 26) % 360
        self.update()

    # ---- painting ----
    def paintEvent(self, event):  # noqa: N802
        if not self._active:
            return
        p = self.palette_
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(2.5, 2.5, -2.5, -2.5)

        acc = th.hex_rgb(p.accent)
        painter.setPen(QPen(QColor(acc[0], acc[1], acc[2], 55), 2.0))
        painter.drawEllipse(rect)

        pen = QPen(QColor(acc[0], acc[1], acc[2], 235), 2.2)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, -self._angle * 16, 110 * 16)
        painter.end()


class BusyOverlay(QWidget):
    """Translucent scrim with a spinner, layered over a page."""

    def __init__(self, palette: th.Palette, parent=None):
        super().__init__(parent)
        self.palette_ = palette
        self.spinner = BusySpinner(palette, 34, self)
        self.label_text = ""
        # purely visual: the user can still interact with the page, which
        # matters because background tasks have no cancel button yet
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.hide()

    def set_palette(self, palette: th.Palette) -> None:
        self.palette_ = palette
        self.spinner.set_palette(palette)
        self.update()

    def set_message(self, text: str) -> None:
        self.label_text = text
        self.update()

    def setActive(self, active: bool) -> None:  # noqa: N802
        self.spinner.set_active(active)
        if active:
            self._centre()
            self.raise_()
            self.show()
        else:
            self.hide()

    def _centre(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.setGeometry(parent.rect())
        self.spinner.move(
            (self.width() - self.spinner.width()) // 2,
            self.height() // 2 - 44,
        )

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._centre()

    def paintEvent(self, event):  # noqa: N802
        if not self.spinner.is_active():
            return
        p = self.palette_
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        painter.fillRect(self.rect(), QColor(0, 0, 0, 80 if not p.light else 45))

        # small panel so the message stays readable on every theme
        cx = self.width() // 2
        cy = self.height() // 2
        panel = QRectF(cx - 130, cy - 62, 260, 108)
        fill = QColor(p.panel_bottom)
        fill.setAlpha(252)
        painter.setPen(QPen(QColor(p.accent), 1.0))
        painter.setBrush(fill)
        painter.drawRoundedRect(panel, 12, 12)

        if self.label_text:
            painter.setPen(QPen(QColor(p.text)))
            font = painter.font()
            font.setPointSizeF(9.5)
            painter.setFont(font)
            painter.drawText(
                QRectF(panel.left() + 10, panel.bottom() - 34,
                       panel.width() - 20, 22),
                Qt.AlignHCenter | Qt.AlignVCenter,
                self.label_text,
            )
        painter.end()
