"""Custom painted widgets that give AYMTECH PRO its neon glass look.

QSS alone cannot reproduce the reference design (glowing borders,
gradient cards, clipped corners, the holo ring behind the mascot), so
the main surfaces are painted with ``QPainter`` and re-painted whenever
the active :class:`~ui.theme.Palette` changes.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QWidget,
)

from . import icons as icon_lib
from . import theme as th

def _assets_dir() -> str:
    """Resolve the assets folder for both source and frozen builds."""
    import sys

    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
        return os.path.join(base, "assets")
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets"
    )


ASSETS = _assets_dir()


def asset(name: str) -> str:
    return os.path.join(ASSETS, name)


def _color(value, alpha: Optional[int] = None) -> QColor:
    if isinstance(value, (tuple, list)):
        c = QColor(int(value[0]), int(value[1]), int(value[2]))
    elif isinstance(value, QColor):
        c = QColor(value)
    else:
        c = QColor(value)
    if alpha is not None:
        c.setAlpha(alpha)
    return c


def draw_glow_rect(
    painter: QPainter,
    rect: QRectF,
    color: QColor,
    radius: float = 12.0,
    width: float = 1.0,
    glow: float = 3.0,
) -> None:
    """Draw a rounded rectangle with a soft outer glow."""
    painter.save()
    painter.setBrush(Qt.NoBrush)
    steps = 4
    for i in range(steps, 0, -1):
        alpha = int(color.alpha() * (glow / (i * steps * 1.6)))
        if alpha <= 0:
            continue
        c = QColor(color)
        c.setAlpha(alpha)
        pen = QPen(c)
        pen.setWidthF(width + i * 0.9)
        painter.setPen(pen)
        r = rect.adjusted(-i * 0.6, -i * 0.6, i * 0.6, i * 0.6)
        painter.drawRoundedRect(r, radius, radius)
    painter.setPen(QPen(color, width))
    painter.drawRoundedRect(rect, radius, radius)
    painter.restore()


# ---------------------------------------------------------------
# BACKGROUND
# ---------------------------------------------------------------

class TechBackground(QWidget):
    """Full window backdrop: tech image + gradient + neon frame."""

    MODES = ("circuit", "space", "grid")

    def __init__(self, palette: th.Palette, opacity: float = 0.9, parent=None):
        super().__init__(parent)
        self.palette_ = palette
        self.opacity = opacity
        self.mode = "circuit"
        self._pixmap: Optional[QPixmap] = None
        self._source: Optional[QPixmap] = None
        self._load_image(palette)

    def set_mode(self, mode: str) -> None:
        if mode in self.MODES:
            self.mode = mode
            self._load_image(self.palette_)
            self._pixmap = None
            self.resizeEvent(None) if False else None
            if self._source is not None:
                self._pixmap = self._source.scaled(
                    self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
                )
            self.update()

    def _load_image(self, palette: th.Palette) -> None:
        if palette.light:
            name = "bg_light.jpg"
        else:
            name = {
                "circuit": "bg_tech.jpg",
                "space": "AZED.jpg",
                "grid": "bg_grid.jpg",
            }.get(self.mode, "bg_tech.jpg")
        path = asset(name)
        if not os.path.exists(path):
            path = asset("bg_tech.jpg")
        pix = QPixmap(path)
        self._source = pix if not pix.isNull() else None

    def set_palette(self, palette: th.Palette, opacity: float) -> None:
        reload = palette.light != self.palette_.light
        self.palette_ = palette
        self.opacity = opacity
        if reload:
            self._load_image(palette)
        self.update()

    def resizeEvent(self, event):  # noqa: N802
        if self._source is not None:
            self._pixmap = self._source.scaled(
                self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
        super().resizeEvent(event)

    def paintEvent(self, event):  # noqa: N802
        p = self.palette_
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        painter.fillRect(self.rect(), _color(p.window))

        if self._pixmap is not None:
            painter.setOpacity(0.55 if p.light else 0.85)
            x = (self.width() - self._pixmap.width()) // 2
            y = (self.height() - self._pixmap.height()) // 2
            painter.drawPixmap(x, y, self._pixmap)
            painter.setOpacity(1.0)

        # vertical gradient overlay keeps text readable
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, _color(p.window, p.overlay_top))
        grad.setColorAt(0.5, _color(p.window, p.overlay_bottom))
        grad.setColorAt(1.0, _color(p.window, p.overlay_top))
        painter.fillRect(self.rect(), grad)

        # subtle accent glow bottom-left
        rad = QRadialGradient(
            QPointF(self.width() * 0.16, self.height() * 0.95),
            self.width() * 0.45,
        )
        rad.setColorAt(0.0, _color(p.accent, 46))
        rad.setColorAt(1.0, _color(p.accent, 0))
        painter.fillRect(self.rect(), rad)

        painter.end()


# ---------------------------------------------------------------
# PANEL
# ---------------------------------------------------------------

class Panel(QFrame):
    """Translucent rounded panel used by the header, sidebar and dock."""

    def __init__(
        self,
        palette: th.Palette,
        radius: float = 14.0,
        opacity: float = 0.9,
        accent: bool = False,
        glow: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.palette_ = palette
        self.radius = radius
        self.opacity = opacity
        self.accent_border = accent
        self.glow = glow
        self.setAttribute(Qt.WA_StyledBackground, False)

    def set_palette(self, palette: th.Palette, opacity: float) -> None:
        self.palette_ = palette
        self.opacity = opacity
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = self.palette_
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(1.2, 1.2, -1.2, -1.2)

        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, _color(p.panel_top, int(255 * self.opacity)))
        grad.setColorAt(0.55, _color(p.panel_bottom, int(250 * self.opacity)))
        grad.setColorAt(1.0, _color(p.panel_top, int(215 * self.opacity)))

        path = QPainterPath()
        path.addRoundedRect(rect, self.radius, self.radius)
        painter.fillPath(path, grad)

        border = p.accent if self.accent_border else p.border
        if self.glow:
            draw_glow_rect(painter, rect, _color(border, 120), self.radius, 1.0, 2.6)
        else:
            painter.setPen(QPen(_color(border, 165), 1.0))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect, self.radius, self.radius)

        # top highlight line
        painter.setPen(QPen(_color(p.accent, 70), 1.0))
        painter.drawLine(
            QPointF(rect.left() + self.radius, rect.top() + 1),
            QPointF(rect.right() - self.radius, rect.top() + 1),
        )
        painter.end()


# ---------------------------------------------------------------
# BRAND LOGO
# ---------------------------------------------------------------

class LogoMark(QWidget):
    """The 'A' emblem with a soft neon halo."""

    def __init__(self, palette: th.Palette, size: int = 62, parent=None):
        super().__init__(parent)
        self.palette_ = palette
        self.setFixedSize(size, size)
        src = QPixmap(asset("logo_a.png"))
        self._pix = (
            src.scaled(
                int(size * 0.86),
                int(size * 0.86),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            if not src.isNull()
            else None
        )

    def set_palette(self, palette: th.Palette) -> None:
        self.palette_ = palette
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = self.palette_
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        c = QRectF(self.rect()).center()
        rad = QRadialGradient(c, self.width() * 0.5)
        rad.setColorAt(0.0, _color(p.accent, 110))
        rad.setColorAt(0.55, _color(p.accent, 42))
        rad.setColorAt(1.0, _color(p.accent, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(rad)
        painter.drawEllipse(QRectF(self.rect()).adjusted(1, 1, -1, -1))

        if self._pix:
            painter.drawPixmap(
                int(c.x() - self._pix.width() / 2),
                int(c.y() - self._pix.height() / 2),
                self._pix,
            )
        painter.end()


# ---------------------------------------------------------------
# NAVIGATION
# ---------------------------------------------------------------

class NavButton(QWidget):
    """Sidebar entry with a soft-blue pill and icon chip."""

    clicked = Signal(str)

    def __init__(self, key: str, icon_name: str, label: str, parent=None):
        super().__init__(parent)
        self.key = key
        self.icon_name = icon_name
        self.label = label
        self.checked = False
        self.hovered = False
        self.palette_ = th.DARK_BLUE
        self.opacity = 0.9
        self._icon = None
        self._icon_color = None
        self.setMinimumHeight(41)
        self.setMaximumHeight(41)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _icon_pixmap(self, color: str, size: int = 16):
        if self._icon is None or self._icon_color != color:
            self._icon = icon_lib.make_pixmap(self.icon_name, color, size)
            self._icon_color = color
        return self._icon

    def set_palette(self, palette: th.Palette, opacity: float) -> None:
        self.palette_ = palette
        self.opacity = opacity
        self.update()

    def set_label(self, label: str) -> None:
        self.label = label
        self.update()

    def set_checked(self, checked: bool) -> None:
        if self.checked != checked:
            self.checked = checked
            self.update()

    def enterEvent(self, event):  # noqa: N802
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self.hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.key)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):  # noqa: N802
        p = self.palette_
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(1, 2, -1, -2)
        radius = 9.0

        if self.checked:
            grad = QLinearGradient(rect.topLeft(), rect.topRight())
            grad.setColorAt(0.0, _color(p.nav_top, 250))
            grad.setColorAt(0.55, _color(p.nav_top, 190))
            grad.setColorAt(1.0, _color(p.nav_bottom, 140))
            path = QPainterPath()
            path.addRoundedRect(rect, radius, radius)
            painter.fillPath(path, grad)
            painter.setPen(QPen(_color(p.accent, 215), 1.2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect, radius, radius)
            icon_bg = _color("#ffffff", 40)
            text_color = _color("#ffffff")
        elif self.hovered:
            painter.setPen(QPen(_color(p.accent, 120), 1.0))
            painter.setBrush(_color(p.accent_rgb, 26))
            painter.drawRoundedRect(rect, radius, radius)
            icon_bg = _color(p.accent, 40)
            text_color = _color(p.text)
        else:
            painter.setPen(QPen(_color(p.border, 46), 1.0))
            painter.setBrush(_color(p.panel_top, 90))
            painter.drawRoundedRect(rect, radius, radius)
            icon_bg = _color(p.accent, 26)
            text_color = _color(p.text_dim)

        rtl = self.layoutDirection() == Qt.RightToLeft

        # icon chip
        chip_x = rect.right() - 34 if rtl else rect.left() + 6
        chip = QRectF(chip_x, rect.center().y() - 13, 26, 26)
        painter.setPen(Qt.NoPen)
        painter.setBrush(icon_bg)
        painter.drawRoundedRect(chip, 7, 7)
        glyph = QRectF(
            chip.center().x() - 8, chip.center().y() - 8, 16, 16
        )
        icon_color = "#ffffff" if self.checked else (
            p.accent if self.hovered else p.text_dim
        )
        pm = self._icon_pixmap(icon_color, 15)
        if pm is not None and not pm.isNull():
            painter.drawPixmap(
                int(glyph.center().x() - 8), int(glyph.center().y() - 8), pm
            )
        else:
            painter.setPen(QPen(text_color))
            painter.drawText(chip, Qt.AlignCenter, "•")

        font = QFont(self.font())
        font.setPointSizeF(9.5)
        font.setBold(self.checked)
        painter.setFont(font)
        painter.setPen(QPen(text_color))
        if rtl:
            text_rect = QRectF(rect.left() + 6, rect.top(), rect.width() - 50, rect.height())
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignRight, self.label)
        else:
            text_rect = QRectF(rect.left() + 44, rect.top(), rect.width() - 50, rect.height())
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.label)

        if self.checked:
            painter.setPen(Qt.NoPen)
            painter.setBrush(_color(p.accent))
            bar_x = rect.right() - 3.2 if rtl else rect.left()
            painter.drawRoundedRect(
                QRectF(bar_x, rect.top() + 9, 3.2, rect.height() - 18), 2, 2
            )
        painter.end()


# ---------------------------------------------------------------
# ACTION CARD (dashboard)
# ---------------------------------------------------------------

class ActionCard(QWidget):
    """Large gradient action tile, e.g. 'Flashing Tools'."""

    clicked = Signal(str)

    def __init__(
        self,
        key: str,
        icon: QIcon,
        title: str,
        subtitle: str,
        colors: Tuple[str, str],
        parent=None,
    ):
        super().__init__(parent)
        self.key = key
        self.icon = icon
        self.title = title
        self.subtitle = subtitle
        self.colors = colors
        self.hovered = False
        self._icon_pixmap = icon.pixmap(24, 24) if not icon.isNull() else None
        self.setMinimumHeight(96)
        self.setMinimumWidth(160)
        self.setCursor(Qt.PointingHandCursor)
        self.compact = False

    def set_compact(self, compact: bool) -> None:
        if compact != self.compact:
            self.compact = compact
            self.update()

    def set_colors(self, colors: Tuple[str, str]) -> None:
        self.colors = colors
        self.update()

    def set_texts(self, title: str, subtitle: str) -> None:
        self.title, self.subtitle = title, subtitle
        self.update()

    def enterEvent(self, event):  # noqa: N802
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self.hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.key)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        radius = 13.0

        start, end = self.colors
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, _color(start, 255 if self.hovered else 236))
        grad.setColorAt(1.0, _color(end, 250 if self.hovered else 224))

        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.fillPath(path, grad)

        # glossy top sweep
        gloss = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        gloss.setColorAt(0.0, _color("#ffffff", 58))
        gloss.setColorAt(0.55, _color("#ffffff", 0))
        painter.save()
        painter.setClipPath(path)
        painter.fillRect(rect, gloss)
        # diagonal light streak
        painter.setPen(QPen(_color("#ffffff", 16 if not self.hovered else 30), 16))
        painter.drawLine(
            QPointF(rect.left() + rect.width() * 0.55, rect.top() + 6),
            QPointF(rect.left() + rect.width() * 0.72, rect.bottom() - 6),
        )
        painter.restore()

        painter.setPen(QPen(_color("#ffffff", 90), 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, radius, radius)

        rtl = self.layoutDirection() == Qt.RightToLeft

        # icon in a glass tile
        chip_size = 36.0 if self.compact else 42.0
        chip_x = (
            rect.right() - chip_size - 14 if rtl else rect.left() + 14
        )
        chip = QRectF(
            chip_x, rect.center().y() - chip_size / 2, chip_size, chip_size
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(_color("#ffffff", 32))
        painter.drawRoundedRect(chip, 10, 10)
        pm = self._icon_pixmap
        if pm is not None and not pm.isNull():
            icon_size = pm.width() / max(1.0, pm.devicePixelRatio())
            painter.drawPixmap(
                int(chip.center().x() - icon_size / 2),
                int(chip.center().y() - icon_size / 2),
                pm,
            )

        # texts
        gap = 10 if self.compact else 14
        if rtl:
            text_x = rect.left() + 12
            text_width = chip.left() - rect.left() - gap - 12
            align = Qt.AlignVCenter | Qt.AlignRight
        else:
            text_x = chip.right() + gap
            text_width = rect.width() - (text_x - rect.left()) - (10 if self.compact else 12)
            align = Qt.AlignVCenter | Qt.AlignLeft

        title_font = QFont(self.font())
        title_font.setPointSizeF(10.0 if self.compact else 11.0)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QPen(_color("#ffffff", 248)))
        metrics = QFontMetrics(title_font)
        title_text = metrics.elidedText(
            self.title, Qt.ElideRight, int(text_width)
        )
        line_height = 26.0 if not self.compact else 24.0

        if self.compact:
            block = line_height + 18
            top = rect.center().y() - block / 2
        else:
            top = rect.top() + 20

        painter.drawText(
            QRectF(text_x, top, text_width, line_height), align, title_text
        )

        sub_font = QFont(self.font())
        sub_font.setPointSizeF(8.2 if self.compact else 8.8)
        painter.setFont(sub_font)
        painter.setPen(QPen(_color("#ffffff", 196)))
        sub_metrics = QFontMetrics(sub_font)
        sub_text = sub_metrics.elidedText(
            self.subtitle, Qt.ElideRight, int(text_width)
        )
        painter.drawText(
            QRectF(text_x, top + line_height, text_width, 22), align, sub_text
        )
        painter.end()


# ---------------------------------------------------------------
# FEATURE ROW  (hero check list)
# ---------------------------------------------------------------

class FeatureRow(QWidget):
    def __init__(self, text: str, palette: th.Palette, parent=None):
        super().__init__(parent)
        self.text = text
        self.palette_ = palette
        self.setFixedHeight(32)
        self.setMinimumWidth(240)

    def set_palette(self, palette: th.Palette) -> None:
        self.palette_ = palette
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = self.palette_
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rtl = self.layoutDirection() == Qt.RightToLeft
        y = self.height() / 2
        bx = self.width() - 20 if rtl else 2
        painter.setPen(Qt.NoPen)
        painter.setBrush(_color(p.ok))
        painter.drawEllipse(QRectF(bx, y - 9, 18, 18))
        check = QPen(_color("#062015" if p.light else "#04121a"), 2.0)
        check.setCapStyle(Qt.RoundCap)
        painter.setPen(check)
        painter.drawLine(QPointF(bx + 4.5, y), QPointF(bx + 7.8, y + 3.4))
        painter.drawLine(QPointF(bx + 7.8, y + 3.4), QPointF(bx + 13.6, y - 3.6))

        font = QFont(self.font())
        font.setPointSizeF(10.2)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(_color(p.text)))
        if rtl:
            painter.drawText(
                QRectF(2, 0, self.width() - 30, self.height()),
                Qt.AlignVCenter | Qt.AlignRight,
                self.text,
            )
        else:
            painter.drawText(
                QRectF(28, 0, self.width() - 30, self.height()),
                Qt.AlignVCenter | Qt.AlignLeft,
                self.text,
            )
        painter.end()


# ---------------------------------------------------------------
# THEME PREVIEW CARD (right dock)
# ---------------------------------------------------------------

class ThemePreviewCard(QWidget):
    """Mini theme card with a tiny mock UI preview."""

    clicked = Signal(str)

    def __init__(self, palette: th.Palette, preview: th.Palette, selected: bool, parent=None):
        super().__init__(parent)
        self.palette_ = palette
        self.preview = preview
        self.selected = selected
        self.hovered = False
        self.setFixedHeight(60)
        self.setCursor(Qt.PointingHandCursor)

    def set_state(self, palette: th.Palette, selected: bool) -> None:
        self.palette_ = palette
        self.selected = selected
        self.update()

    def set_preview_names(self, name: str, subtitle: str) -> None:
        base = self.preview
        self.preview = th.Palette(**{
            **base.__dict__, "name": name, "subtitle": subtitle
        })
        self.update()

    def enterEvent(self, event):  # noqa: N802
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self.hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.preview.key)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        outer = QRectF(self.rect()).adjusted(1, 1.5, -1, -1.5)

        active = self.selected or self.hovered
        painter.setPen(
            QPen(_color(self.palette_.accent, 230 if self.selected else 110), 1.4)
        )
        painter.setBrush(
            _color(self.palette_.accent_rgb, 34 if self.selected else 16)
        )
        painter.drawRoundedRect(outer, 10, 10)

        # preview thumbnail
        thumb = QRectF(outer.left() + 8, outer.top() + 7, 62, outer.height() - 14)
        g = QLinearGradient(thumb.topLeft(), thumb.bottomRight())
        g.setColorAt(0.0, _color(self.preview.accent_2))
        g.setColorAt(1.0, _color(self.preview.window))
        painter.setPen(QPen(_color("#ffffff", 60), 1))
        painter.setBrush(g)
        painter.drawRoundedRect(thumb, 7, 7)

        # tiny mock panels inside thumbnail
        painter.setPen(Qt.NoPen)
        painter.setBrush(_color(self.preview.accent, 210))
        painter.drawRoundedRect(
            QRectF(thumb.left() + 6, thumb.top() + 7, thumb.width() - 12, 4), 2, 2
        )
        painter.setBrush(_color("#ffffff", 45))
        painter.drawRoundedRect(
            QRectF(thumb.left() + 6, thumb.top() + 16, thumb.width() - 12, 18), 3, 3
        )
        painter.setBrush(_color(self.preview.accent, 160))
        painter.drawRoundedRect(
            QRectF(thumb.left() + 6, thumb.bottom() - 12, thumb.width() - 12, 5), 2, 2
        )

        # texts
        name_font = QFont(self.font())
        name_font.setPointSizeF(9.4)
        name_font.setBold(True)
        painter.setFont(name_font)
        painter.setPen(QPen(_color(self.palette_.text)))
        text_x = thumb.right() + 12
        painter.drawText(
            QRectF(text_x, outer.top() + 10, outer.width() - (text_x - outer.left()) - 34, 20),
            Qt.AlignVCenter | Qt.AlignLeft,
            self.preview.name,
        )

        sub_font = QFont(self.font())
        sub_font.setPointSizeF(8.2)
        painter.setFont(sub_font)
        painter.setPen(QPen(_color(self.palette_.text_muted)))
        painter.drawText(
            QRectF(text_x, outer.top() + 29, outer.width() - (text_x - outer.left()) - 34, 20),
            Qt.AlignVCenter | Qt.AlignLeft,
            self.preview.subtitle,
        )

        # selector ring
        ring = QRectF(outer.right() - 26, outer.center().y() - 8, 16, 16)
        if self.selected:
            painter.setPen(QPen(_color(self.palette_.accent), 2.0))
            painter.setBrush(_color(self.palette_.accent_rgb, 40))
            painter.drawEllipse(ring)
            painter.setPen(Qt.NoPen)
            painter.setBrush(_color(self.palette_.accent))
            painter.drawEllipse(ring.adjusted(4.2, 4.2, -4.2, -4.2))
        else:
            painter.setPen(QPen(_color(self.palette_.text_muted, 190), 1.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(ring)

        if active:
            pass
        painter.end()


# ---------------------------------------------------------------
# STAT PILL (status bar)
# ---------------------------------------------------------------

class StatusLabel(QWidget):
    """Small 'icon + text' pair used in the footer."""

    def __init__(self, text: str, palette: th.Palette, kind: str = "info", parent=None):
        super().__init__(parent)
        self.text = text
        self.palette_ = palette
        self.kind = kind
        self.icon: Optional[QIcon] = None
        self.setMinimumHeight(26)

    def set_palette(self, palette: th.Palette) -> None:
        self.palette_ = palette
        self.update()

    def set_text(self, text: str) -> None:
        self.text = text
        self.update()

    def set_kind(self, kind: str) -> None:
        self.kind = kind
        self.update()

    def set_icon(self, icon: QIcon) -> None:
        self.icon = icon
        self.update()

    def sizeHint(self):  # noqa: N802
        fm = QFontMetrics(self.font())
        base = fm.horizontalAdvance(self.text) + (38 if self.icon else 16)
        return QSize(int(base), 26)

    def paintEvent(self, event):  # noqa: N802
        p = self.palette_
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        color = {
            "ok": p.ok,
            "warn": p.warn,
            "danger": p.danger,
            "info": p.accent,
        }.get(self.kind, p.accent)

        x = 0
        if self.icon is not None:
            painter.setPen(QPen(_color(color), 1.6))
            painter.setBrush(_color(color, 40))
            painter.drawEllipse(QRectF(0, self.height() / 2 - 8, 16, 16))
            if self.kind == "ok":
                painter.setPen(QPen(_color(color), 2.0))
                y = self.height() / 2
                painter.drawLine(QPointF(4.6, y), QPointF(7.4, y + 3))
                painter.drawLine(QPointF(7.4, y + 3), QPointF(11.8, y - 3.2))
            x = 24

        font = QFont(self.font())
        font.setPointSizeF(9.2)
        painter.setFont(font)
        painter.setPen(QPen(_color(p.text_dim)))
        painter.drawText(
            QRectF(x, 0, self.width() - x, self.height()),
            Qt.AlignVCenter | Qt.AlignLeft,
            self.text,
        )
        painter.end()


# ---------------------------------------------------------------
# SEPARATOR
# ---------------------------------------------------------------

class VSeparator(QWidget):
    def __init__(self, palette: th.Palette, parent=None):
        super().__init__(parent)
        self.palette_ = palette
        self.setFixedWidth(1)

    def set_palette(self, palette: th.Palette) -> None:
        self.palette_ = palette
        self.update()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setPen(QPen(_color(self.palette_.border, 150), 1))
        painter.drawLine(
            int(self.width() / 2), 5, int(self.width() / 2), self.height() - 5
        )
        painter.end()


# ---------------------------------------------------------------
# SECTION TITLE
# ---------------------------------------------------------------

class PageTitle(QLabel):
    """Large page heading used by every tool page."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("PageTitle")


class PageSubtitle(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("PageSubtitle")
        self.setWordWrap(True)


class SectionTitle(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("SectionTitle")


# ---------------------------------------------------------------
# TOGGLE SWITCH
# ---------------------------------------------------------------

class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self, checked: bool, palette: th.Palette, parent=None):
        super().__init__(parent)
        self._checked = checked
        self.palette_ = palette
        self.setFixedSize(46, 24)
        self.setCursor(Qt.PointingHandCursor)

    def isChecked(self) -> bool:  # noqa: N802
        return self._checked

    def setChecked(self, value: bool) -> None:  # noqa: N802
        if self._checked != value:
            self._checked = value
            self.update()

    def set_palette(self, palette: th.Palette) -> None:
        self.palette_ = palette
        self.update()

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._checked = not self._checked
            self.update()
            self.toggled.emit(self._checked)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):  # noqa: N802
        p = self.palette_
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(1, 2, -1, -2)

        if self._checked:
            grad = QLinearGradient(rect.topLeft(), rect.topRight())
            grad.setColorAt(0.0, _color(p.accent_2))
            grad.setColorAt(1.0, _color(p.accent))
            painter.setBrush(grad)
            painter.setPen(QPen(_color(p.accent), 1))
        else:
            painter.setBrush(_color(p.text_muted, 70))
            painter.setPen(QPen(_color(p.border), 1))
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)

        knob_d = rect.height() - 6
        knob_x = (
            rect.right() - knob_d - 4 if self._checked else rect.left() + 4
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(_color("#ffffff", 245))
        painter.drawEllipse(QRectF(knob_x, rect.top() + 3, knob_d, knob_d))
        painter.end()
