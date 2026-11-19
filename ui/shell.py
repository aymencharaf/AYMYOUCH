"""Application shell: header, navigation sidebar, theme dock and footer.

The shell is intentionally independent from the business pages: it only
receives a page stack and a navigation description, so pages can be
added or reordered without touching the chrome.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QComboBox,
    QMenu,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import icons
from . import theme as th
from .widgets import (
    FeatureRow,
    LogoMark,
    NavButton,
    Panel,
    StatusLabel,
    TechBackground,
    ThemePreviewCard,
    ToggleSwitch,
    VSeparator,
    asset,
)


# ---------------------------------------------------------------
# WINDOW CONTROLS
# ---------------------------------------------------------------

class WindowButton(QPushButton):
    def __init__(self, glyph: str, palette: th.Palette, danger: bool = False, parent=None):
        super().__init__(parent)
        self.glyph = glyph
        self.danger = danger
        self.palette_ = palette
        self.setFixedSize(30, 24)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("WindowClose" if danger else "WindowButton")
        self.setFocusPolicy(Qt.NoFocus)
        self._apply(palette)

    def _apply(self, palette: th.Palette) -> None:
        color = palette.danger if self.danger else palette.text_dim
        self.setIcon(icons.make_icon(self.glyph, color, 14))
        self.setIconSize(QSize(14, 14))

    def set_palette(self, palette: th.Palette) -> None:
        self.palette_ = palette
        self._apply(palette)


# ---------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------

class Header(Panel):
    """Top bar: brand identity, tagline and window controls."""

    language_selected = Signal(str)

    def __init__(self, palette: th.Palette, opacity: float, parent=None):
        super().__init__(palette, radius=16.0, opacity=opacity, glow=True, parent=parent)
        self.setFixedHeight(96)
        self._drag_pos: Optional[QPoint] = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 10, 14, 10)
        layout.setSpacing(12)

        self.logo = LogoMark(palette, 64)
        layout.addWidget(self.logo)
        layout.addSpacing(4)

        brand_box = QVBoxLayout()
        brand_box.setSpacing(0)
        brand_box.setContentsMargins(0, 0, 0, 0)

        self.brand = QLabel()
        self.brand.setObjectName("Brand")
        self.brand.setTextFormat(Qt.RichText)
        brand_box.addWidget(self.brand)

        self.brand_sub = QLabel()
        self.brand_sub.setObjectName("BrandSubtitle")
        brand_box.addWidget(self.brand_sub)

        layout.addLayout(brand_box)
        layout.addStretch(2)

        # tagline block
        tag_box = QVBoxLayout()
        tag_box.setSpacing(2)
        self.tagline = QLabel()
        self.tagline.setObjectName("Tagline")
        self.tagline.setAlignment(Qt.AlignRight)
        self.tagline_sub = QLabel()
        self.tagline_sub.setObjectName("TaglineSub")
        self.tagline_sub.setAlignment(Qt.AlignRight)
        tag_box.addStretch()
        tag_box.addWidget(self.tagline)
        tag_box.addWidget(self.tagline_sub)
        tag_box.addStretch()
        layout.addLayout(tag_box)
        layout.addStretch(1)

        self.lang_btn = QPushButton()
        self.lang_btn.setObjectName("HeaderButton")
        self.lang_btn.setIcon(icons.make_icon("globe", palette.text_dim, 15))
        self.lang_btn.setIconSize(QSize(15, 15))
        self.lang_btn.setCursor(Qt.PointingHandCursor)
        self.lang_btn.setFixedHeight(28)
        self.lang_btn.setMinimumWidth(96)
        self.lang_btn.setFocusPolicy(Qt.NoFocus)
        self.lang_menu = QMenu(self)
        for label, code in (("العربية", "ar"),
                            ("Français", "fr"),
                            ("English", "en")):
            action = self.lang_menu.addAction(label)
            action.setData(code)
            action.triggered.connect(
                lambda checked=False, c=code: self.language_selected.emit(c)
            )
        self.lang_btn.setMenu(self.lang_menu)
        layout.addWidget(self.lang_btn, 0, Qt.AlignVCenter)
        layout.addSpacing(6)

        self.min_btn = WindowButton("minimize", palette)
        self.max_btn = WindowButton("maximize", palette)
        self.close_btn = WindowButton("close", palette, danger=True)
        for b in (self.min_btn, self.max_btn, self.close_btn):
            layout.addWidget(b, 0, Qt.AlignTop)

        self.set_brand_texts()
        self.set_palette(palette, opacity)

    # ---- texts ----
    def tr(self, text: str) -> str:
        translator = getattr(self, "translator", None)
        return translator(text) if translator else text

    def set_translator(self, translator) -> None:
        self.translator = translator

    def set_brand_texts(self) -> None:
        p = self.palette_
        self.brand.setText(
            '<span style="color:{text}; font-size:25pt; font-weight:900; '
            'font-style:italic; letter-spacing:1px;">AYMTECH</span>'
            '<span style="color:{accent}; font-size:25pt; font-weight:900; '
            'font-style:italic; letter-spacing:1px;">&nbsp;PRO</span>'
            '<span style="color:{accent}; font-size:9pt; vertical-align:super;">&#174;</span>'
            .format(text=p.text, accent=p.accent)
        )
        self.brand_sub.setText(
            self.tr("Mobile Solutions  \u2022  Professional Tools")
        )
        self.tagline.setText(self.tr("The Ultimate Android Service Suite"))
        self.tagline_sub.setText(
            self.tr("Repair  \u2022  Unlock  \u2022  Diagnose  \u2022  Optimize")
        )

    def set_language(self, code: str) -> None:
        names = {"ar": "العربية", "fr": "Français", "en": "English"}
        self.lang_btn.setText(names.get(code, "English"))

    def set_palette(self, palette: th.Palette, opacity: float) -> None:
        super().set_palette(palette, opacity)
        self.set_brand_texts()
        for b in (self.min_btn, self.max_btn, self.close_btn):
            b.set_palette(palette)
        self.lang_btn.setIcon(icons.make_icon("globe", palette.accent, 15))
        self.lang_btn.setStyleSheet(
            "QPushButton#HeaderButton {{"
            "background-color: {bg}; color: {fg}; border: 1px solid {bd};"
            "border-radius: 8px; padding: 2px 8px; font-size: 9pt;"
            "font-weight: 600;"
            "}}"
            "QPushButton#HeaderButton:hover {{"
            "border: 1px solid {accent}; color: {accent};"
            "}}"
            "QPushButton#HeaderButton::menu-indicator {{ image: none; width: 0; }}"
            .format(
                bg=th.rgba(palette.accent_rgb, 0.12),
                fg=palette.text_dim,
                bd=palette.border,
                accent=palette.accent,
            )
        )

    # ---- window dragging ----
    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            )
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            if self.window().isMaximized():
                self.window().showNormal()
            self.window().move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            window = self.window()
            window.showNormal() if window.isMaximized() else window.showMaximized()
        super().mouseDoubleClickEvent(event)


# ---------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------

class Sidebar(Panel):
    def __init__(self, palette: th.Palette, opacity: float, parent=None):
        super().__init__(palette, radius=16.0, opacity=opacity, parent=parent)
        self.setFixedWidth(262)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 10, 8, 10)
        outer.setSpacing(4)

        from PySide6.QtWidgets import QScrollArea

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setStyleSheet("background: transparent;")

        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self.layout_ = QVBoxLayout(self._content)
        self.layout_.setContentsMargins(2, 0, 2, 0)
        self.layout_.setSpacing(3)
        self._scroll.setWidget(self._content)
        outer.addWidget(self._scroll, 1)

        self.buttons: Dict[str, NavButton] = {}
        self.icon_names: Dict[str, str] = {}
        self._footer: Optional[_SidebarFooter] = None
        self._footer_layout = outer

    def add_entry(self, key: str, icon_name: str, label: str) -> None:
        button = NavButton(key, icon_name, label)
        button.set_palette(self.palette_, self.opacity)
        self.icon_names[key] = icon_name
        self.layout_.addWidget(button)
        self.buttons[key] = button

    def finish(self) -> None:
        self.layout_.addStretch()
        self._footer = _SidebarFooter(self.palette_, self.opacity)
        self._footer_layout.addWidget(self._footer)

    def set_active(self, key: str) -> None:
        for k, b in self.buttons.items():
            b.set_checked(k == key)
            b.set_palette(self.palette_, self.opacity)

    def set_palette(self, palette: th.Palette, opacity: float) -> None:
        super().set_palette(palette, opacity)
        for key, b in self.buttons.items():
            b.set_palette(palette, opacity)
        if self._footer is not None:
            self._footer.set_palette(palette)

    def set_labels(self, texts: Dict[str, str]) -> None:
        for key, label in texts.items():
            if key in self.buttons:
                self.buttons[key].set_label(label)


class _SidebarFooter(QWidget):
    """Version plate at the bottom of the sidebar."""

    def __init__(self, palette: th.Palette, opacity: float, parent=None):
        super().__init__(parent)
        self.palette_ = palette
        self.setFixedHeight(54)

    def set_palette(self, palette: th.Palette) -> None:
        self.palette_ = palette
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = self.palette_
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)

        if p.light:
            gold = QColor("#b07b16")
            text_color = QColor("#6d4a00")
            sub_color = QColor("#8a6416")
            fill_alpha = 70
        else:
            gold = QColor("#e9b949")
            text_color = QColor("#ffe9a8")
            sub_color = QColor(gold.red(), gold.green(), gold.blue(), 220)
            fill_alpha = 34

        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, QColor(gold.red(), gold.green(), gold.blue(), fill_alpha))
        grad.setColorAt(
            1.0,
            QColor(255, 255, 255, 90) if p.light else QColor(6, 20, 44, 120),
        )
        painter.setBrush(grad)
        painter.setPen(QPen(QColor(gold.red(), gold.green(), gold.blue(), 170), 1.2))
        painter.drawRoundedRect(rect, 9, 9)

        # crown
        crown = QRectF(rect.left() + 10, rect.center().y() - 9, 22, 18)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#f2c14e") if not p.light else gold)
        path = QPainterPath()
        path.moveTo(crown.left(), crown.bottom())
        path.lineTo(crown.left(), crown.top() + 4)
        path.lineTo(crown.left() + crown.width() * 0.28, crown.top() + 10)
        path.lineTo(crown.center().x(), crown.top())
        path.lineTo(crown.left() + crown.width() * 0.72, crown.top() + 10)
        path.lineTo(crown.right(), crown.top() + 4)
        path.lineTo(crown.right(), crown.bottom())
        path.closeSubpath()
        painter.drawPath(path)

        font = QFont(self.font())
        font.setPointSizeF(9.4)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(text_color))
        painter.drawText(
            QRectF(rect.left() + 40, rect.top() + 8, rect.width() - 48, 20),
            Qt.AlignVCenter | Qt.AlignLeft,
            "AYMTECH PRO  v2.0.0",
        )
        font.setPointSizeF(8.0)
        font.setBold(False)
        font.setItalic(True)
        painter.setFont(font)
        painter.setPen(QPen(sub_color))
        painter.drawText(
            QRectF(rect.left() + 40, rect.top() + 28, rect.width() - 48, 20),
            Qt.AlignVCenter | Qt.AlignLeft,
            "Professional Edition",
        )
        painter.end()


# ---------------------------------------------------------------
# THEME DOCK
# ---------------------------------------------------------------

class ThemeDock(Panel):
    """Right hand panel: appearance, themes and display switches."""

    theme_selected = Signal(str)
    language_selected = Signal(str)
    transparency_changed = Signal(bool)
    animations_changed = Signal(bool)
    background_changed = Signal(str)
    apply_clicked = Signal()

    def __init__(self, palette: th.Palette, opacity: float, parent=None):
        super().__init__(palette, radius=16.0, opacity=opacity, parent=parent)
        self.setFixedWidth(352)
        self.palette_ = palette

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.palette_icon = QLabel()
        self.palette_icon.setFixedSize(24, 24)
        head.addWidget(self.palette_icon)
        self.title = QLabel(self.tr("Appearance & Themes"))
        self.title.setObjectName("DockTitle")
        head.addWidget(self.title)
        head.addStretch()
        layout.addLayout(head)

        self.cards: Dict[str, ThemePreviewCard] = {}
        for key in th.THEME_ORDER:
            preview = th.PALETTES[key]
            preview = th.Palette(**{
                **preview.__dict__,
                "name": self.tr(preview.name),
                "subtitle": self.tr(preview.subtitle),
            })
            card = ThemePreviewCard(palette, preview, selected=(key == palette.key))
            card.clicked.connect(self.theme_selected.emit)
            layout.addWidget(card)
            self.cards[key] = card

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background: rgba(120,170,220,60); max-height:1px;")
        layout.addWidget(sep)

        # background chooser
        bg_row = QHBoxLayout()
        bg_label = QLabel("Background")
        bg_label.setText(self.tr("Background"))
        self.bg_label = bg_label
        bg_label.setObjectName("DockLabel")
        bg_row.addWidget(bg_label)
        bg_row.addStretch()
        self.bg_preview = QLabel()
        self.bg_preview.setFixedSize(92, 40)
        self.bg_preview.setScaledContents(True)
        bg_row.addWidget(self.bg_preview)
        layout.addLayout(bg_row)

        self.bg_combo = QComboBox()
        self.bg_combo.addItem(self.tr("Tech Circuit"), "circuit")
        self.bg_combo.addItem(self.tr("Deep Space"), "space")
        self.bg_combo.addItem(self.tr("Classic Grid"), "grid")
        self.bg_combo.currentIndexChanged.connect(self._on_background_change)
        layout.addWidget(self.bg_combo)

        # switches
        self.transparency_switch = self._switch_row(
            layout, self.tr("Transparency"), True
        )
        self.animations_switch = self._switch_row(
            layout, self.tr("Animations"), True
        )

        layout.addStretch()

        self.apply_button = QPushButton(self.tr("Apply Theme"))
        self.apply_button.setObjectName("ApplyTheme")
        self.apply_button.setMinimumHeight(44)
        self.apply_button.setCursor(Qt.PointingHandCursor)
        self.apply_button.clicked.connect(self.apply_clicked.emit)
        layout.addWidget(self.apply_button)

        self._refresh_icons()
        self._refresh_bg_preview()

    def _on_background_change(self, _index: int) -> None:
        self._refresh_bg_preview()
        self.background_changed.emit(self.bg_combo.currentData())

    def tr(self, text: str) -> str:
        translator = getattr(self, "translator", None)
        return translator(text) if translator else text

    def set_translator(self, translator) -> None:
        self.translator = translator

    def _switch_row(self, layout: QVBoxLayout, label: str, checked: bool) -> ToggleSwitch:
        row = QHBoxLayout()
        lbl = QLabel(label)
        if not hasattr(self, "_switch_labels"):
            self._switch_labels = []
        self._switch_labels.append((lbl, label))
        lbl.setObjectName("DockLabel")
        row.addWidget(lbl)
        row.addStretch()
        switch = ToggleSwitch(checked, self.palette_)
        row.addWidget(switch)
        layout.addLayout(row)
        return switch

    def _refresh_icons(self) -> None:
        self.palette_icon.setPixmap(icons.make_pixmap("palette", self.palette_.accent, 22))
        self.apply_button.setIcon(icons.make_icon("refresh", "#ffffff", 16))
        self.apply_button.setIconSize(QSize(16, 16))

    def _refresh_bg_preview(self) -> None:
        if self.palette_.light:
            name = "bg_light.jpg"
        else:
            name = {
                "circuit": "bg_tech.jpg",
                "space": "AZED.jpg",
                "grid": "bg_grid.jpg",
            }.get(self.bg_combo.currentData() or "circuit", "bg_tech.jpg")
        pix = QPixmap(asset(name))
        if not pix.isNull():
            self.bg_preview.setPixmap(
                pix.scaled(92, 40, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            )

    def refresh_theme_names(self, translator) -> None:
        for key, card in self.cards.items():
            base = th.PALETTES[key]
            card.set_preview_names(translator(base.name), translator(base.subtitle))

    # ---- state ----
    def set_active_theme(self, key: str) -> None:
        for k, card in self.cards.items():
            card.set_state(self.palette_, k == key)

    def set_palette(self, palette: th.Palette, opacity: float) -> None:
        super().set_palette(palette, opacity)
        self.palette_ = palette
        for card in self.cards.values():
            card.set_state(palette, card.preview.key == palette.key)
        self.transparency_switch.set_palette(palette)
        self.animations_switch.set_palette(palette)
        self._refresh_icons()
        self._refresh_bg_preview()
        self.apply_button.setStyleSheet(self._apply_style(palette))
        self.bg_preview.setStyleSheet(
            "border: 1px solid {}; border-radius: 6px;".format(palette.border)
        )

    @staticmethod
    def _apply_style(p: th.Palette) -> str:
        return (
            "QPushButton#ApplyTheme {{"
            "background-color: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "stop:0 {top}, stop:1 {bottom});"
            "color: {text}; border: 1px solid {accent}; border-radius: 11px;"
            "font-size: 10.5pt; font-weight: 700; padding: 10px;"
            "}}"
            "QPushButton#ApplyTheme:hover {{"
            "background-color: {accent}; color: {hover_text};"
            "}}"
        ).format(
            top=p.nav_top,
            bottom=p.nav_bottom,
            text="#ffffff" if not p.light else "#ffffff",
            accent=p.accent,
            hover_text="#ffffff",
        )


# ---------------------------------------------------------------
# FOOTER
# ---------------------------------------------------------------

class Footer(Panel):
    def tr(self, text: str) -> str:
        translator = getattr(self, "translator", None)
        return translator(text) if translator else text

    def __init__(self, palette: th.Palette, opacity: float, parent=None):
        super().__init__(palette, radius=12.0, opacity=opacity, parent=parent)
        self.setFixedHeight(46)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 4, 16, 4)
        layout.setSpacing(12)

        self.status = StatusLabel(self.tr("Status: Ready"), palette, "ok")
        self.status.set_icon(icons.make_icon("shield", palette.ok, 14))
        self.device = StatusLabel(self.tr("Device: Not Connected"), palette, "info")
        self.device.set_icon(icons.make_icon("android", palette.accent, 14))
        self.adb = StatusLabel(self.tr("ADB: Checking..."), palette, "info")
        self.adb.set_icon(icons.make_icon("wrench", palette.text_dim, 14))
        self.motto = QLabel(self.tr("Innovation Today ... A Better Tomorrow\u2122"))
        self.motto.setObjectName("Motto")
        self.motto.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.separators = [VSeparator(palette), VSeparator(palette)]

        layout.addWidget(self.status)
        layout.addWidget(self.separators[0])
        layout.addWidget(self.device)
        layout.addWidget(self.separators[1])
        layout.addWidget(self.adb)
        layout.addStretch()
        layout.addWidget(self.motto)

    def set_translator(self, translator) -> None:
        self.translator = translator

    def set_palette(self, palette: th.Palette, opacity: float) -> None:
        super().set_palette(palette, opacity)
        for w in (self.status, self.device, self.adb):
            w.set_palette(palette)
        for s in self.separators:
            s.set_palette(palette)
        self.status.set_icon(icons.make_icon("shield", palette.ok, 14))
        self.device.set_icon(icons.make_icon("android", palette.accent, 14))
        self.adb.set_icon(icons.make_icon("wrench", palette.accent, 14))
        self._motto_style(palette)

    def _motto_style(self, p: th.Palette) -> None:
        self.motto.setStyleSheet(
            "color: {}; font-style: italic; font-weight: 600; font-size: 9.5pt;".format(
                th.mix(p.accent, p.text, 0.35)
            )
        )


# ---------------------------------------------------------------
# DASHBOARD VIEW
# ---------------------------------------------------------------

class _MascotStage(QWidget):
    """Circular holo spotlight with the Android mascot artwork."""

    def __init__(self, palette: th.Palette, parent=None):
        super().__init__(parent)
        self.palette_ = palette
        self._source = QPixmap(asset("mascot_android.png"))
        self._scaled: Optional[QPixmap] = None
        self._scaled_for = QSize()

    def set_palette(self, palette: th.Palette) -> None:
        self.palette_ = palette
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = self.palette_
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        side = min(self.width(), self.height()) - 6
        if side <= 10 or self._source.isNull():
            painter.end()
            return

        target = QSize(int(side), int(side))
        if self._scaled_for != target or self._scaled is None:
            self._scaled = self._source.scaled(
                target, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            self._scaled_for = target

        centre = QRectF(
            self.width() / 2 - side / 2,
            self.height() / 2 - side / 2,
            side,
            side,
        )

        acc = th.hex_rgb(p.accent)
        halo = QRadialGradient(centre.center(), side * 0.52)
        halo.setColorAt(0.0, QColor(acc[0], acc[1], acc[2], 60))
        halo.setColorAt(0.62, QColor(acc[0], acc[1], acc[2], 18))
        halo.setColorAt(1.0, QColor(acc[0], acc[1], acc[2], 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(centre.adjusted(-side * 0.04, -side * 0.04,
                                           side * 0.04, side * 0.04))

        # soft circular crop of the artwork
        clip = QPainterPath()
        clip.addEllipse(centre)
        painter.setClipPath(clip)
        painter.drawPixmap(centre.toRect(), self._scaled)
        painter.setClipping(False)

        ring_pen = QPen(QColor(acc[0], acc[1], acc[2], 90), 1.2)
        painter.setPen(ring_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(centre.adjusted(0.5, 0.5, -0.5, -0.5))

        dash = QPen(QColor(acc[0], acc[1], acc[2], 70), 1.0)
        dash.setStyle(Qt.DashLine)
        painter.setPen(dash)
        painter.drawEllipse(
            centre.adjusted(-side * 0.045, -side * 0.045,
                            side * 0.045, side * 0.045)
        )
        painter.end()


class HeroBlock(QWidget):
    """Welcome block with feature list and the mascot artwork."""

    def __init__(self, palette: th.Palette, parent=None):
        super().__init__(parent)
        self.palette_ = palette
        self.setMinimumHeight(250)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 0, 0)
        layout.setSpacing(10)

        left = QVBoxLayout()
        left.setSpacing(2)
        left.setContentsMargins(0, 0, 0, 0)

        self.welcome = QLabel("Welcome to")
        self.welcome.setObjectName("HeroWelcome")

        self.title = QLabel()
        self.title.setObjectName("HeroTitle")
        self.title.setTextFormat(Qt.RichText)

        self.subtitle = QLabel("Your Professional Android Repair Solution")
        self.subtitle.setObjectName("HeroSubtitle")
        self.subtitle.setWordWrap(True)

        left.addWidget(self.welcome)
        left.addWidget(self.title)
        left.addWidget(self.subtitle)
        left.addSpacing(10)

        self.features: List[FeatureRow] = []
        for text in (
            "Fast & Reliable Tools",
            "Advanced Diagnostics",
            "Official Recovery Guides",
            "Safe & Professional",
        ):
            row = FeatureRow(text, palette)
            left.addWidget(row)
            self.features.append(row)

        left.addStretch()
        layout.addLayout(left, 5)

        self.mascot = _MascotStage(palette)
        self.mascot.setMinimumSize(320, 280)
        self.mascot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.mascot, 5)

        self._set_title()

    def _set_title(self) -> None:
        p = self.palette_
        self.title.setText(
            '<span style="color:{text}; font-size:27pt; font-weight:900; '
            'font-style:italic;">AYMTECH</span>'
            '<span style="color:{accent}; font-size:27pt; font-weight:900; '
            'font-style:italic;">&nbsp;PRO</span>'
            .format(text=p.text, accent=p.accent)
        )

    def set_palette(self, palette: th.Palette) -> None:
        self.palette_ = palette
        self._set_title()
        for row in self.features:
            row.set_palette(palette)
        if isinstance(self.mascot, _MascotStage):
            self.mascot.set_palette(palette)
        self.update()

    def set_texts(self, welcome: str, subtitle: str, features: Sequence[str]) -> None:
        self.welcome.setText(welcome)
        self.subtitle.setText(subtitle)
        for row, text in zip(self.features, features):
            row.text = text
            row.update()


# ---------------------------------------------------------------
# SHELL CONTAINER
# ---------------------------------------------------------------

class _Translatable:
    """Mixin providing a swappable translator."""

    def set_translator(self, translator) -> None:
        self.translator = translator

    def tr(self, text: str) -> str:
        translator = getattr(self, "translator", None)
        return translator(text) if translator else text


class AppShell(QWidget):
    """Assembles header, sidebar, page stack, dock and footer."""

    navigate = Signal(str)
    theme_selected = Signal(str)
    language_selected = Signal(str)
    transparency_changed = Signal(bool)
    animations_changed = Signal(bool)
    background_changed = Signal(str)
    apply_theme = Signal()

    def __init__(self, palette: th.Palette, opacity: float, parent=None):
        super().__init__(parent)
        self.palette_ = palette
        self.opacity = opacity
        self.animations = True

        self.background = TechBackground(palette, opacity)
        self.background.setParent(self)
        self.background.lower()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(9)

        self.header = Header(palette, opacity)
        outer.addWidget(self.header)

        middle = QHBoxLayout()
        middle.setSpacing(11)

        self.sidebar = Sidebar(palette, opacity)
        self.theme_dock = ThemeDock(palette, opacity)

        self.pages: Optional[QStackedWidget] = None
        self.page_container = QWidget()
        self.page_layout = QVBoxLayout(self.page_container)
        self.page_layout.setContentsMargins(0, 0, 0, 0)
        self.page_layout.setSpacing(0)

        middle.addWidget(self.sidebar)
        middle.addWidget(self.page_container, 1)
        middle.addWidget(self.theme_dock)
        outer.addLayout(middle, 1)

        self.footer = Footer(palette, opacity)
        outer.addWidget(self.footer)

        # wiring
        self.header.language_selected.connect(self.language_selected.emit)
        self.theme_dock.theme_selected.connect(self.theme_selected.emit)
        self.theme_dock.transparency_changed.connect(self.transparency_changed.emit)
        self.theme_dock.animations_changed.connect(self.animations_changed.emit)
        self.theme_dock.background_changed.connect(self.background_changed.emit)
        self.theme_dock.apply_clicked.connect(self.apply_theme.emit)
        self.header.min_btn.clicked.connect(lambda: self.window().showMinimized())
        self.header.max_btn.clicked.connect(self.toggle_maximized)
        self.header.close_btn.clicked.connect(lambda: self.window().close())

    # ---- structure ----
    def add_page(self, key: str, icon_name: str, label: str, page: QWidget) -> None:
        if self.pages is None:
            self.pages = QStackedWidget()
            self.pages.setStyleSheet("background: transparent;")
            self.page_layout.addWidget(self.pages)
        index = self.pages.addWidget(page)
        self.sidebar.add_entry(key, icon_name, label)
        self.sidebar.buttons[key].clicked.connect(self.navigate.emit)
        self.sidebar.buttons[key].setProperty("page_index", index)

    def finish_pages(self) -> None:
        self.sidebar.finish()

    def show_page(self, key: str, animate: bool = True) -> None:
        if self.pages is None:
            return
        button = self.sidebar.buttons.get(key)
        if button is None:
            return
        changed = self.pages.currentIndex() != button.property("page_index")
        self.pages.setCurrentIndex(button.property("page_index"))
        self.sidebar.set_active(key)
        if animate and changed and self.animations:
            self._fade_page()

    def _fade_page(self) -> None:
        from PySide6.QtCore import QPropertyAnimation
        from PySide6.QtWidgets import QGraphicsOpacityEffect

        effect = QGraphicsOpacityEffect(self.pages)
        effect.setOpacity(0.15)
        self.pages.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(230)
        animation.setStartValue(0.15)
        animation.setEndValue(1.0)
        animation.finished.connect(lambda: self.pages.setGraphicsEffect(None))
        animation.start()
        self._fade_animation = animation

    def toggle_maximized(self) -> None:
        window = self.window()
        window.showNormal() if window.isMaximized() else window.showMaximized()

    # ---- theming ----
    def set_palette(self, palette: th.Palette, opacity: float) -> None:
        self.palette_ = palette
        self.opacity = opacity
        self.background.set_palette(palette, opacity)
        self.header.set_palette(palette, opacity)
        self.sidebar.set_palette(palette, opacity)
        self.theme_dock.set_palette(palette, opacity)
        self.footer.set_palette(palette, opacity)

    def set_translator(self, translator) -> None:
        self.translator = translator
        self.header.set_translator(translator)
        self.theme_dock.set_translator(translator)
        self.footer.set_translator(translator)
        self.refresh_localized_texts()

    def tr(self, text: str) -> str:
        translator = getattr(self, "translator", None)
        return translator(text) if translator else text

    def refresh_localized_texts(self) -> None:
        """Re-apply translated chrome texts (header, dock, footer)."""
        self.header.set_brand_texts()
        self.footer.motto.setText(
            self.tr("Innovation Today ... A Better Tomorrow\u2122")
        )
        self.footer.status.set_text(self.tr("Status: Ready"))
        dock = self.theme_dock
        dock.title.setText(self.tr("Appearance & Themes"))
        dock.bg_label.setText(self.tr("Background"))
        dock.apply_button.setText(self.tr("Apply Theme"))
        for label, original in getattr(dock, "_switch_labels", []):
            label.setText(self.tr(original))
        names = {
            "circuit": "Tech Circuit",
            "space": "Deep Space",
            "grid": "Classic Grid",
        }
        for index in range(dock.bg_combo.count()):
            original = names.get(dock.bg_combo.itemData(index), "")
            if original:
                dock.bg_combo.setItemText(index, self.tr(original))
        dock.refresh_theme_names(self.tr)
        dock.set_active_theme(self.palette_.key)

    def set_background_mode(self, mode: str) -> None:
        self.background.set_mode(mode)

    def paintEvent(self, event):  # noqa: N802
        p = self.palette_
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.8, 0.8, -0.8, -0.8)
        acc = th.hex_rgb(p.accent)
        painter.setPen(QPen(QColor(acc[0], acc[1], acc[2], 120), 1.4))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, 9, 9)
        painter.end()

    def resizeEvent(self, event):  # noqa: N802
        self.background.setGeometry(self.rect())
        super().resizeEvent(event)
