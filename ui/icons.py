"""Vector icons drawn with QPainter.

Keeping the icons vector means they stay crisp at any DPI and are
recoloured automatically for every theme.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)


def _pen(color: QColor, width: float = 2.0) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


# ---------------------------------------------------------------
# individual glyph painters (draw inside a 24x24 box scaled to rect)
# ---------------------------------------------------------------

def _home(p: QPainter, r: QRectF, c: QColor) -> None:
    p.setPen(_pen(c, 2.0))
    p.setBrush(Qt.NoBrush)
    path = QPainterPath()
    path.moveTo(r.left() + r.width() * 0.12, r.top() + r.height() * 0.46)
    path.lineTo(r.center().x(), r.top() + r.height() * 0.16)
    path.lineTo(r.right() - r.width() * 0.12, r.top() + r.height() * 0.46)
    p.drawPath(path)
    p.drawRoundedRect(
        QRectF(r.left() + r.width() * 0.22, r.top() + r.height() * 0.46,
               r.width() * 0.56, r.height() * 0.40), 2, 2,
    )


def _gear(p: QPainter, r: QRectF, c: QColor) -> None:
    import math
    p.setPen(_pen(c, 1.9))
    p.setBrush(Qt.NoBrush)
    cx, cy = r.center().x(), r.center().y()
    outer, inner = r.width() * 0.40, r.width() * 0.30
    path = QPainterPath()
    teeth = 8
    for i in range(teeth * 2):
        ang = math.pi * i / teeth
        rad = outer if i % 2 == 0 else inner
        x = cx + math.cos(ang) * rad
        y = cy + math.sin(ang) * rad
        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    path.closeSubpath()
    p.drawPath(path)
    p.drawEllipse(QRectF(cx - r.width() * 0.13, cy - r.width() * 0.13,
                         r.width() * 0.26, r.width() * 0.26))


def _info(p: QPainter, r: QRectF, c: QColor) -> None:
    p.setPen(_pen(c, 1.9))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(r.adjusted(r.width() * 0.14, r.height() * 0.14,
                             -r.width() * 0.14, -r.height() * 0.14))
    p.drawLine(QPointF(r.center().x(), r.top() + r.height() * 0.42),
               QPointF(r.center().x(), r.top() + r.height() * 0.70))
    p.setPen(Qt.NoPen)
    p.setBrush(c)
    p.drawEllipse(QRectF(r.center().x() - 1.3, r.top() + r.height() * 0.30, 2.6, 2.6))


def _phone(p: QPainter, r: QRectF, c: QColor) -> None:
    p.setPen(_pen(c, 1.9))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(
        QRectF(r.left() + r.width() * 0.28, r.top() + r.height() * 0.08,
               r.width() * 0.44, r.height() * 0.84), 3.5, 3.5)
    p.drawLine(QPointF(r.center().x() - r.width() * 0.06, r.bottom() - r.height() * 0.16),
               QPointF(r.center().x() + r.width() * 0.06, r.bottom() - r.height() * 0.16))


def _android(p: QPainter, r: QRectF, c: QColor) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(c)
    head = QPainterPath()
    body = QRectF(r.left() + r.width() * 0.18, r.top() + r.height() * 0.30,
                  r.width() * 0.64, r.height() * 0.34)
    head.addRoundedRect(body, body.height() / 2, body.height() / 2)
    p.drawPath(head)
    p.drawRoundedRect(
        QRectF(r.left() + r.width() * 0.20, r.top() + r.height() * 0.55,
               r.width() * 0.60, r.height() * 0.26), 2.5, 2.5)
    p.setPen(_pen(c, 1.8))
    p.drawLine(QPointF(r.left() + r.width() * 0.34, r.top() + r.height() * 0.16),
               QPointF(r.left() + r.width() * 0.28, r.top() + r.height() * 0.26))
    p.drawLine(QPointF(r.left() + r.width() * 0.66, r.top() + r.height() * 0.16),
               QPointF(r.left() + r.width() * 0.72, r.top() + r.height() * 0.26))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(4, 14, 30, 210))
    p.drawEllipse(QRectF(r.left() + r.width() * 0.36, r.top() + r.height() * 0.40, 2.4, 2.4))
    p.drawEllipse(QRectF(r.left() + r.width() * 0.60, r.top() + r.height() * 0.40, 2.4, 2.4))


def _lock(p: QPainter, r: QRectF, c: QColor) -> None:
    p.setPen(_pen(c, 1.9))
    p.setBrush(Qt.NoBrush)
    shackle = QRectF(r.left() + r.width() * 0.30, r.top() + r.height() * 0.16,
                     r.width() * 0.40, r.height() * 0.34)
    p.drawArc(shackle, 0, 180 * 16)
    p.drawLine(QPointF(shackle.left(), shackle.center().y()),
               QPointF(shackle.left(), shackle.bottom()))
    p.drawLine(QPointF(shackle.right(), shackle.center().y()),
               QPointF(shackle.right(), shackle.bottom()))
    p.drawRoundedRect(
        QRectF(r.left() + r.width() * 0.20, r.top() + r.height() * 0.44,
               r.width() * 0.60, r.height() * 0.42), 3, 3)


def _unlock(p: QPainter, r: QRectF, c: QColor) -> None:
    p.setPen(_pen(c, 1.9))
    p.setBrush(Qt.NoBrush)
    shackle = QRectF(r.left() + r.width() * 0.40, r.top() + r.height() * 0.14,
                     r.width() * 0.40, r.height() * 0.34)
    p.drawArc(shackle, 20 * 16, 160 * 16)
    p.drawLine(QPointF(shackle.left(), shackle.center().y()),
               QPointF(shackle.left(), shackle.bottom()))
    p.drawRoundedRect(
        QRectF(r.left() + r.width() * 0.16, r.top() + r.height() * 0.44,
               r.width() * 0.60, r.height() * 0.42), 3, 3)


def _shield(p: QPainter, r: QRectF, c: QColor) -> None:
    p.setPen(_pen(c, 1.9))
    p.setBrush(Qt.NoBrush)
    path = QPainterPath()
    path.moveTo(r.center().x(), r.top() + r.height() * 0.12)
    path.lineTo(r.right() - r.width() * 0.18, r.top() + r.height() * 0.26)
    path.lineTo(r.right() - r.width() * 0.22, r.top() + r.height() * 0.62)
    path.cubicTo(
        r.right() - r.width() * 0.26, r.bottom() - r.height() * 0.14,
        r.center().x(), r.bottom() - r.height() * 0.04,
        r.center().x(), r.bottom() - r.height() * 0.04,
    )
    path.cubicTo(
        r.left() + r.width() * 0.26, r.bottom() - r.height() * 0.14,
        r.left() + r.width() * 0.22, r.top() + r.height() * 0.62,
        r.left() + r.width() * 0.18, r.top() + r.height() * 0.26,
    )
    path.closeSubpath()
    p.drawPath(path)


def _chip(p: QPainter, r: QRectF, c: QColor) -> None:
    p.setPen(_pen(c, 1.8))
    p.setBrush(Qt.NoBrush)
    body = QRectF(r.left() + r.width() * 0.24, r.top() + r.height() * 0.24,
                  r.width() * 0.52, r.height() * 0.52)
    p.drawRoundedRect(body, 3, 3)
    p.drawRoundedRect(body.adjusted(r.width() * 0.14, r.height() * 0.14,
                                    -r.width() * 0.14, -r.height() * 0.14), 1.5, 1.5)
    for f in (0.36, 0.5, 0.64):
        p.drawLine(QPointF(r.left() + r.width() * 0.24, r.top() + r.height() * f),
                   QPointF(r.left() + r.width() * 0.08, r.top() + r.height() * f))
        p.drawLine(QPointF(r.right() - r.width() * 0.24, r.top() + r.height() * f),
                   QPointF(r.right() - r.width() * 0.08, r.top() + r.height() * f))
        p.drawLine(QPointF(r.left() + r.width() * f, r.top() + r.height() * 0.24),
                   QPointF(r.left() + r.width() * f, r.top() + r.height() * 0.08))
        p.drawLine(QPointF(r.left() + r.width() * f, r.bottom() - r.height() * 0.24),
                   QPointF(r.left() + r.width() * f, r.bottom() - r.height() * 0.08))


def _barcode(p: QPainter, r: QRectF, c: QColor) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(c)
    widths = [1.6, 1.0, 2.4, 1.0, 1.6, 1.0, 2.0, 1.2, 1.6, 1.0, 2.2, 1.0]
    total = sum(widths) + (len(widths) - 1) * 1.4
    x = r.center().x() - total / 2
    for w in widths:
        p.drawRect(QRectF(x, r.top() + r.height() * 0.2, w, r.height() * 0.6))
        x += w + 1.4


def _list(p: QPainter, r: QRectF, c: QColor) -> None:
    p.setPen(_pen(c, 1.8))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(
        QRectF(r.left() + r.width() * 0.18, r.top() + r.height() * 0.14,
               r.width() * 0.64, r.height() * 0.72), 3, 3)
    for f in (0.34, 0.5, 0.66):
        p.drawLine(QPointF(r.left() + r.width() * 0.32, r.top() + r.height() * f),
                   QPointF(r.right() - r.width() * 0.30, r.top() + r.height() * f))


def _apple(p: QPainter, r: QRectF, c: QColor) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(c)
    path = QPainterPath()
    cx = r.center().x()
    path.addEllipse(QRectF(cx - r.width() * 0.26, r.top() + r.height() * 0.34,
                           r.width() * 0.30, r.height() * 0.32))
    path.addEllipse(QRectF(cx - r.width() * 0.02, r.top() + r.height() * 0.34,
                           r.width() * 0.30, r.height() * 0.32))
    path.addEllipse(QRectF(cx - r.width() * 0.26, r.top() + r.height() * 0.36,
                           r.width() * 0.52, r.height() * 0.50))
    p.drawPath(path)
    p.setPen(_pen(c, 1.8))
    p.drawLine(QPointF(cx, r.top() + r.height() * 0.36),
               QPointF(cx + r.width() * 0.04, r.top() + r.height() * 0.18))
    p.setBrush(c)
    p.setPen(Qt.NoPen)
    p.drawEllipse(QRectF(cx + r.width() * 0.04, r.top() + r.height() * 0.14,
                         r.width() * 0.22, r.height() * 0.11))


def _letter(letter: str):
    def painter(p: QPainter, r: QRectF, c: QColor) -> None:
        p.setPen(_pen(c, 1.9))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(r.adjusted(r.width() * 0.14, r.height() * 0.14,
                                 -r.width() * 0.14, -r.height() * 0.14))
        font = p.font()
        font.setBold(True)
        font.setPointSizeF(r.height() * 0.46)
        p.setFont(font)
        p.setPen(QPen(c))
        p.drawText(r, Qt.AlignCenter, letter)
    return painter


def _globe(p: QPainter, r: QRectF, c: QColor) -> None:
    p.setPen(_pen(c, 1.7))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(r.adjusted(r.width() * 0.16, r.height() * 0.16,
                             -r.width() * 0.16, -r.height() * 0.16))
    p.drawLine(QPointF(r.left() + r.width() * 0.28, r.center().y()),
               QPointF(r.right() - r.width() * 0.28, r.center().y()))
    p.drawEllipse(QRectF(r.center().x() - r.width() * 0.11, r.top() + r.height() * 0.18,
                         r.width() * 0.22, r.height() * 0.64))


def _download(p: QPainter, r: QRectF, c: QColor) -> None:
    p.setPen(_pen(c, 1.9))
    p.setBrush(Qt.NoBrush)
    p.drawLine(QPointF(r.center().x(), r.top() + r.height() * 0.18),
               QPointF(r.center().x(), r.top() + r.height() * 0.62))
    path = QPainterPath()
    path.moveTo(r.center().x() - r.width() * 0.16, r.top() + r.height() * 0.44)
    path.lineTo(r.center().x(), r.top() + r.height() * 0.62)
    path.lineTo(r.center().x() + r.width() * 0.16, r.top() + r.height() * 0.44)
    p.drawPath(path)
    p.drawLine(QPointF(r.left() + r.width() * 0.24, r.bottom() - r.height() * 0.2),
               QPointF(r.right() - r.width() * 0.24, r.bottom() - r.height() * 0.2))


def _wrench(p: QPainter, r: QRectF, c: QColor) -> None:
    p.setPen(_pen(c, 1.9))
    p.setBrush(Qt.NoBrush)
    p.save()
    p.translate(r.center())
    p.rotate(-42)
    p.translate(-r.center())
    p.drawRoundedRect(
        QRectF(r.center().x() - r.width() * 0.09, r.top() + r.height() * 0.36,
               r.width() * 0.18, r.height() * 0.52), 2, 2)
    p.drawArc(QRectF(r.center().x() - r.width() * 0.22, r.top() + r.height() * 0.14,
                     r.width() * 0.44, r.height() * 0.36), 40 * 16, 280 * 16)
    p.restore()


def _minimize(p: QPainter, r: QRectF, c: QColor) -> None:
    p.setPen(_pen(c, 1.8))
    p.drawLine(QPointF(r.left() + r.width() * 0.2, r.center().y()),
               QPointF(r.right() - r.width() * 0.2, r.center().y()))


def _maximize(p: QPainter, r: QRectF, c: QColor) -> None:
    p.setPen(_pen(c, 1.7))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(r.left() + r.width() * 0.2, r.top() + r.height() * 0.2,
                      r.width() * 0.6, r.height() * 0.6))


def _close(p: QPainter, r: QRectF, c: QColor) -> None:
    p.setPen(_pen(c, 1.9))
    p.drawLine(QPointF(r.left() + r.width() * 0.24, r.top() + r.height() * 0.24),
               QPointF(r.right() - r.width() * 0.24, r.bottom() - r.height() * 0.24))
    p.drawLine(QPointF(r.right() - r.width() * 0.24, r.top() + r.height() * 0.24),
               QPointF(r.left() + r.width() * 0.24, r.bottom() - r.height() * 0.24))


def _refresh(p: QPainter, r: QRectF, c: QColor) -> None:
    p.setPen(_pen(c, 1.9))
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(r.left() + r.width() * 0.18, r.top() + r.height() * 0.18,
                     r.width() * 0.64, r.height() * 0.64), 30 * 16, 290 * 16)
    path = QPainterPath()
    x = r.right() - r.width() * 0.24
    y = r.top() + r.height() * 0.24
    path.moveTo(x, y - r.height() * 0.16)
    path.lineTo(x + r.width() * 0.16, y)
    path.lineTo(x - r.width() * 0.02, y + r.height() * 0.04)
    p.setPen(Qt.NoPen)
    p.setBrush(c)
    p.drawPath(path)


def _palette(p: QPainter, r: QRectF, c: QColor) -> None:
    p.setPen(_pen(c, 1.7))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(r.adjusted(r.width() * 0.12, r.height() * 0.12,
                             -r.width() * 0.12, -r.height() * 0.12))
    p.setPen(Qt.NoPen)
    for dx, dy, col in [
        (-0.14, -0.14, "#ff5f6d"), (0.16, -0.10, "#ffd166"),
        (-0.18, 0.16, "#4cc9f0"), (0.12, 0.18, "#9b5de5"),
    ]:
        dot = QColor(col)
        p.setBrush(QBrush(dot))
        p.drawEllipse(QRectF(
            r.center().x() + dx * r.width() - 2.0,
            r.center().y() + dy * r.height() - 2.0, 4.0, 4.0))


def _bootloader(p: QPainter, r: QRectF, c: QColor) -> None:
    """Lightning bolt over a chip: fastboot / flashing."""

    p.setPen(_pen(c, 1.8))
    p.setBrush(Qt.NoBrush)
    body = QRectF(r.left() + 1.5, r.top() + 3.0, r.width() - 3.0, r.height() - 6.0)
    p.drawRoundedRect(body, 3.0, 3.0)

    for x in (0.28, 0.72):
        top = QPointF(r.left() + body.width() * x, body.top())
        p.drawLine(top, QPointF(top.x(), r.top() + 0.6))
        bottom = QPointF(top.x(), body.bottom())
        p.drawLine(bottom, QPointF(bottom.x(), r.bottom() - 0.6))

    bolt = QPolygonF([
        QPointF(r.center().x() + 1.8, r.center().y() - 5.2),
        QPointF(r.center().x() - 2.6, r.center().y() + 0.4),
        QPointF(r.center().x() + 0.2, r.center().y() + 0.4),
        QPointF(r.center().x() - 1.4, r.center().y() + 5.2),
        QPointF(r.center().x() + 3.0, r.center().y() - 0.8),
        QPointF(r.center().x() + 0.2, r.center().y() - 0.8),
    ])
    p.setBrush(c)
    p.setPen(Qt.NoPen)
    p.drawPolygon(bolt)


PAINTERS = {
    "dashboard": _home,
    "device_manager": _gear,
    "device_information": _info,
    "adb": _phone,
    "android": _android,
    "screen_lock": _lock,
    "unlock": _unlock,
    "shield": _shield,
    "samsung": _letter("S"),
    "qualcomm": _letter("Q"),
    "mediatek": _letter("M"),
    "firmware": _chip,
    "fastboot": _bootloader,
    "ios": _apple,
    "logs": _list,
    "imei": _barcode,
    "settings": _gear,
    "globe": _globe,
    "download": _download,
    "wrench": _wrench,
    "minimize": _minimize,
    "maximize": _maximize,
    "close": _close,
    "refresh": _refresh,
    "palette": _palette,
}


_CACHE: dict = {}


def make_pixmap(name: str, color: str, size: int = 20) -> QPixmap:
    key = (name, color, size)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    painter_fn = PAINTERS.get(name)
    pix = QPixmap(size * 2, size * 2)
    pix.setDevicePixelRatio(2.0)
    pix.fill(Qt.transparent)
    if painter_fn is None:
        return pix
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    painter_fn(painter, QRectF(0, 0, size, size), QColor(color))
    painter.end()
    _CACHE[key] = pix
    return pix


_ICON_CACHE: dict = {}


def clear_caches() -> None:
    """Drop cached pixmaps while Qt is still alive.

    Newer PySide releases crash at interpreter shutdown when QPixmap
    objects are collected after the QApplication has been destroyed, so
    the caches are flushed from an ``aboutToQuit`` handler.
    """
    _CACHE.clear()
    _ICON_CACHE.clear()


def make_icon(name: str, color: str, size: int = 20) -> QIcon:
    key = (name, color, size)
    cached = _ICON_CACHE.get(key)
    if cached is not None:
        return cached
    icon = QIcon(make_pixmap(name, color, size))
    _ICON_CACHE[key] = icon
    return icon


def write_arrow_asset(color: str, path: str, width: int = 20, height: int = 12) -> None:
    """Save a small chevron used by QComboBox::down-arrow."""
    from PySide6.QtGui import QPolygonF
    from PySide6.QtCore import QPointF

    pix = QPixmap(width, height)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    polygon = QPolygonF([
        QPointF(1, 3), QPointF(width / 2, height - 2),
        QPointF(width - 1, 3), QPointF(width - 4, 3),
        QPointF(width / 2, height - 6), QPointF(4, 3),
    ])
    painter.drawPolygon(polygon)
    painter.end()
    pix.save(path)
