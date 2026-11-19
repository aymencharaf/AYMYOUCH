from tools.firmware_tools import FirmwareTools
from tools.qualcomm_tools import QualcommTools
from tools.mediatek_tools import MediaTekTools
from tools.android_tools import AndroidTools
from tools.samsung_tools import SamsungTools
from PySide6.QtGui import QImage, QPixmap
import sys
import shutil
import subprocess
from datetime import datetime

from PySide6.QtCore import Qt, QSettings, QTimer, QProcess
from PySide6.QtWidgets import (
    QApplication,
    QScrollArea,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTextEdit,
    QMessageBox,
    QLineEdit,
    QComboBox,
    QFileDialog,
)

from tools.adb_tools import ADBTools
from tools.translations import translate_text

from ui import theme as ui_theme
from ui import icons as ui_icons
from ui.dashboard import DashboardPage
from ui.pages import PageShell
from ui.shell import AppShell
from ui.widgets import PageSubtitle, PageTitle


# =========================================================
# CONFIGURATION
# =========================================================

APP_NAME = "AYMTECH PRO"
APP_VERSION = "2.0.0"

# The application stylesheet is generated per theme by
# ui.theme.build_stylesheet(); see AymtechPro.apply_styles().
STYLE = ""


# =========================================================
# SYSTEM COMMAND
# =========================================================

def run_command(command, timeout=15):

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            encoding="utf-8",
            errors="replace"
        )

        output = result.stdout.strip()

        if result.stderr.strip():
            output += "\n" + result.stderr.strip()

        return result.returncode == 0, output

    except FileNotFoundError:
        return False, f"Command not found: {command[0]}"

    except subprocess.TimeoutExpired:
        return False, "Command timed out."

    except Exception as error:
        return False, str(error)


# =========================================================
# MAIN APPLICATION
# =========================================================

class AymtechPro(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(f"{APP_NAME} - Android Service Suite")

        self.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowMinMaxButtonsHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        self.resize(1560, 900)
        self.setMinimumSize(1280, 760)

        self.device_table = None
        self.info_box = None
        self.search_box = None
        self.log_box = None
        self.pages = None

        # ADB interface widgets
        self.adb_device_combo = None
        self.adb_status_label = None
        self.adb_output = None
        # Live Phone Screen
        self.phone_screen_label = None
        self.phone_screen_serial = None
        self.phone_screen_busy = False
        self.phone_screen_process = QProcess(self)
        self.phone_screen_process.finished.connect(
         self.phone_screen_capture_finished
        )
        self.phone_screen_status = None
        self.phone_screen_timer = QTimer(self)
        self.phone_screen_timer.setInterval(700)
        self.phone_screen_timer.timeout.connect(
            self.update_phone_screen
        )
        self.navigation_buttons = []
        self.nav_keys = {}

        self.settings = QSettings("AYMTECH", "AYMYOUCH")
        self.current_language = self.settings.value("language", "en")
        if self.current_language not in ("ar", "fr", "en"):
            self.current_language = "en"

        self.language_combo = None
        self.language_label = None

        saved_theme = self.settings.value("theme", ui_theme.DEFAULT_THEME)
        if saved_theme not in ui_theme.PALETTES:
            saved_theme = ui_theme.DEFAULT_THEME
        self.theme_key = saved_theme

        self.opacity = float(self.settings.value("transparency", 0.92) or 0.92)
        self.animations_enabled = (
            str(self.settings.value("animations", "true")).lower() == "true"
        )
        self.background_mode = self.settings.value("background", "circuit")

        self.shell = None
        self.dashboard_page = None
        self._arrow_color = None
        self.palette = ui_theme.PALETTES[self.theme_key]
        self._pending_widgets = []

        self.build_interface()
        self.refresh_devices()

    # =====================================================
    # INTERFACE
    # =====================================================

    def build_interface(self):

        self.palette = ui_theme.PALETTES[self.theme_key]

        self.panel_opacity = 0.92 if self.opacity > 0.5 else 1.0
        self.shell = AppShell(self.palette, self.panel_opacity)
        self.setCentralWidget(self.shell)

        self.shell.navigate.connect(self.navigate)
        self.shell.set_translator(self.tr)
        self.shell.language_selected.connect(self.change_language)
        self.shell.header.set_language(self.current_language)
        self.shell.theme_selected.connect(self.select_theme)
        self.shell.transparency_changed.connect(self.set_transparency)
        self.shell.animations = self.animations_enabled
        self.shell.animations_changed.connect(self.set_animations)
        self.shell.background_changed.connect(self.set_background_mode)
        self.shell.apply_theme.connect(self.apply_theme_now)

        # --- dashboard ---
        self.dashboard_page = DashboardPage(self.palette, self.panel_opacity)
        self.dashboard_page.navigate.connect(self.navigate)
        self.dashboard_page.settings_requested.connect(
            lambda: self.navigate("Settings")
        )
        self.shell.add_page(
            "Dashboard", "dashboard", "Dashboard", self.dashboard_page
        )

        # --- tool pages ---
        navigation = [
            ("Device Manager", "device_manager", self.create_device_manager),
            ("Device Information", "device_information", self.create_device_information),
            ("ADB Tools", "adb", self.create_adb_page),
            ("Live Phone Screen", "adb", self.create_phone_screen_page),
            ("Android Tools", "android", self.create_android_diagnostics_page),
            ("Screen Lock Service", "screen_lock", self.create_screen_lock_page),
            ("Samsung Tools", "samsung", self.create_samsung_tools_page),
            ("Qualcomm Tools", "qualcomm", self.create_qualcomm_tools_page),
            ("MediaTek Tools", "mediatek", self.create_mediatek_tools_page),
            ("Firmware Center", "firmware", self.create_firmware_center_page),
            ("iOS Tools", "ios", lambda: self.create_tool_page("iOS Tools")),
            ("Operation Logs", "logs", self.create_logs_page),
        ]

        for title, icon_name, creator in navigation:
            content = creator()
            page = PageShell(self.palette, content, self.panel_opacity)
            self.shell.add_page(title, icon_name, title, page)

        # --- settings ---
        settings_page = PageShell(
            self.palette, self.create_settings_page(), self.panel_opacity
        )
        self.shell.add_page("Settings", "settings", "Settings", settings_page)

        self.shell.finish_pages()
        self.setMouseTracking(True)
        self.shell.set_background_mode(self.background_mode)
        self.shell.theme_dock.transparency_switch.setChecked(self.opacity > 0.5)
        self.shell.theme_dock.animations_switch.setChecked(self.animations_enabled)

        self.navigation_buttons = list(self.shell.sidebar.buttons.items())

        self.apply_styles()
        self._collect_translatable_widgets()
        self.apply_language()
        self.navigate("Dashboard")
        self.start_clock()
        self.update_status_bar()

    # =====================================================
    # THEMING
    # =====================================================

    def apply_styles(self):

        import os
        from ui.widgets import ASSETS

        arrow = os.path.join(ASSETS, "arrow.png")
        if not os.path.exists(arrow) or self._arrow_color != self.palette.accent:
            ui_icons.write_arrow_asset(self.palette.accent, arrow)
            self._arrow_color = self.palette.accent

        QApplication.instance().setStyleSheet(
            ui_theme.build_stylesheet(
                self.palette, self.panel_opacity, arrow.replace(os.sep, "/")
            )
        )

    def select_theme(self, key):

        if key not in ui_theme.PALETTES:
            return

        self.theme_key = key
        self.palette = ui_theme.PALETTES[key]
        self.apply_theme_now()

    def retheme(self):

        self.shell.set_palette(self.palette, self.panel_opacity)
        pages = self.shell.pages
        for index in range(pages.count()):
            widget = pages.widget(index)
            if hasattr(widget, "set_palette"):
                try:
                    widget.set_palette(self.palette, self.panel_opacity)
                except TypeError:
                    widget.set_palette(self.palette)
        self.update_status_bar()

    def apply_theme_now(self):

        self.palette = ui_theme.PALETTES[self.theme_key]
        self.settings.setValue("theme", self.theme_key)

        self.apply_styles()
        self.retheme()
        self.shell.theme_dock.set_active_theme(self.theme_key)
        self.shell.theme_dock.apply_button.setStyleSheet(
            self.shell.theme_dock._apply_style(self.palette)
        )

        if self.dashboard_page is not None:
            self.dashboard_page.set_palette(self.palette, self.panel_opacity)

        self._retint_header_icons()
        self.shell.refresh_localized_texts()
        self.log(f"Theme applied: {self.palette.name}")

    def _retint_header_icons(self):

        for label, icon_name in getattr(self, "_header_icons", []):
            pixmap = ui_icons.make_pixmap(icon_name, self.palette.accent, 24)
            label.setPixmap(pixmap)
            label.setStyleSheet(
                "QLabel {{ background-color: {}; border: 1px solid {};"
                " border-radius: 11px; }}".format(
                    ui_theme.rgba(self.palette.accent_rgb, 0.14),
                    ui_theme.rgba(self.palette.accent_rgb, 0.45),
                )
            )

    def set_transparency(self, enabled):

        self.panel_opacity = 0.92 if enabled else 1.0
        self.settings.setValue("transparency", self.panel_opacity)
        self.apply_styles()
        self.retheme()

    def set_animations(self, enabled):

        self.animations_enabled = bool(enabled)
        self.settings.setValue("animations", "true" if enabled else "false")
        if self.shell is not None:
            self.shell.animations = self.animations_enabled

    def set_background_mode(self, mode):

        if not mode:
            return
        self.background_mode = mode
        self.settings.setValue("background", mode)
        self.shell.set_background_mode(mode)


    def change_language(self, language):
        if language not in ("ar", "fr", "en"):
            return

        self.current_language = language
        self.settings.setValue("language", language)
        self.apply_language()

    def _collect_translatable_widgets(self):
        self._translatable_widgets = []

        for widget in self.findChildren(QWidget):

            if isinstance(widget, QPushButton):
                original = widget.text()
                if original.strip():
                    self._translatable_widgets.append(
                        ("text", widget, original)
                    )

            elif isinstance(widget, QLabel):
                original = widget.text()
                if original.strip():
                    self._translatable_widgets.append(
                        ("text", widget, original)
                    )

            elif isinstance(widget, QLineEdit):
                original = widget.placeholderText()
                if original:
                    self._translatable_widgets.append(
                        ("placeholder", widget, original)
                    )

            elif isinstance(widget, QTextEdit):
                original = widget.placeholderText()
                if original:
                    self._translatable_widgets.append(
                        ("placeholder", widget, original)
                    )

            elif isinstance(widget, QTableWidget):
                for column in range(widget.columnCount()):
                    item = widget.horizontalHeaderItem(column)
                    if item and item.text().strip():
                        self._translatable_widgets.append(
                            ("table_header", item, item.text())
                        )

    def apply_language(self):
        language = self.current_language

        self.setLayoutDirection(
            Qt.RightToLeft if language == "ar"
            else Qt.LeftToRight
        )

        for kind, widget, original in self._translatable_widgets:
            translated = translate_text(original, language)

            if kind == "text":
                widget.setText(translated)

            elif kind == "placeholder":
                widget.setPlaceholderText(translated)

            elif kind == "table_header":
                widget.setText(translated)

        # Keep navigation identifiers in English internally.
        labels = {}
        for title in list(self.shell.sidebar.buttons):
            labels[title] = translate_text(title, language)
        self.shell.sidebar.set_labels(labels)

        if self.dashboard_page is not None:
            self.apply_dashboard_language()

        if self.shell is not None:
            self.shell.set_translator(self.tr)
            self.update_status_bar()

    def tr(self, text):
        return translate_text(text, self.current_language)

    def set_status(self, label, kind="info"):
        """Colour a status label from the active palette."""
        if label is None:
            return
        label.setProperty("status", kind)
        label.setStyleSheet("")
        label.style().unpolish(label)
        label.style().polish(label)
        label.update()

    # PAGE HEADER
    # =====================================================

    PAGE_ICONS = {
        "Dashboard": "dashboard",
        "Device Manager": "device_manager",
        "Device Information": "device_information",
        "ADB Tools": "adb",
        "Live Phone Screen": "adb",
        "Android Tools": "android",
        "Screen Lock Service": "screen_lock",
        "Samsung Tools": "samsung",
        "Qualcomm Tools": "qualcomm",
        "MediaTek Tools": "mediatek",
        "Firmware Center": "firmware",
        "iOS Tools": "ios",
        "Operation Logs": "logs",
        "Settings": "settings",
    }

    def create_page_header(self, title, description=""):

        layout = QVBoxLayout()
        layout.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        icon_name = self.PAGE_ICONS.get(title)
        if icon_name:
            icon_label = QLabel()
            icon_label.setFixedSize(38, 38)
            icon_label.setAlignment(Qt.AlignCenter)
            icon_label.setPixmap(
                ui_icons.make_pixmap(icon_name, self.palette.accent, 24)
            )
            icon_label.setStyleSheet(
                "QLabel {{ background-color: {}; border: 1px solid {};"
                " border-radius: 11px; }}".format(
                    ui_theme.rgba(self.palette.accent_rgb, 0.14),
                    ui_theme.rgba(self.palette.accent_rgb, 0.45),
                )
            )
            if not hasattr(self, "_header_icons"):
                self._header_icons = []
            self._header_icons.append((icon_label, icon_name))
            title_row.addWidget(icon_label)

        title_label = PageTitle(title)
        title_row.addWidget(title_label)
        title_row.addStretch()

        layout.addLayout(title_row)

        if description:
            desc = PageSubtitle(description)
            layout.addWidget(desc)

        layout.addSpacing(8)

        return layout

    # =====================================================
    # DASHBOARD
    # =====================================================

    def create_dashboard(self):

        # The dashboard is created directly by build_interface(); this
        # method returns a lightweight fallback for compatibility.
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.addLayout(
            self.create_page_header(
                "Dashboard",
                "Welcome to AYMTECH PRO."
            )
        )
        layout.addStretch()
        return page

    def apply_dashboard_language(self):

        language = self.current_language
        texts = [
            ("Flashing Tools", "Flash Firmware"),
            ("Unlock Tools", "Remove FRP & Unlock"),
            ("Screen Lock Service", "Diagnose & Recover"),
            ("Android Tools", "Advanced Features"),
            ("IMEI Tools", "Repair IMEI"),
            ("Settings", "Customize Your Experience"),
        ]
        translated = [
            (translate_text(t, language), translate_text(s, language))
            for t, s in texts
        ]
        self.dashboard_page.grid.set_texts(translated)

        features = [
            translate_text(t, language)
            for t in (
                "Fast & Reliable Tools",
                "Advanced Diagnostics",
                "Official Recovery Guides",
                "Safe & Professional",
            )
        ]
        self.dashboard_page.hero.set_texts(
            translate_text("Welcome to", language),
            translate_text(
                "Your Professional Android Repair Solution", language
            ),
            features,
        )


    # =====================================================
    # SETTINGS PAGE
    # =====================================================

    def create_settings_page(self):

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(14)

        layout.addLayout(
            self.create_page_header(
                "Settings",
                "Personalise language, appearance and service preferences."
            )
        )

        # ---- language ----
        language_group = QFrame()
        language_group.setObjectName("ToolCard")
        language_layout = QVBoxLayout(language_group)
        language_layout.setContentsMargins(18, 14, 18, 16)
        language_layout.setSpacing(8)

        language_title = QLabel("Language")
        language_title.setObjectName("CardTitle")
        language_layout.addWidget(language_title)

        language_hint = QLabel("Choose the interface language.")
        language_hint.setStyleSheet(f"color: {self.palette.text_muted};")
        language_layout.addWidget(language_hint)

        self.language_combo = QComboBox()
        self.language_combo.addItem("العربية", "ar")
        self.language_combo.addItem("Français", "fr")
        self.language_combo.addItem("English", "en")
        self.language_combo.setMinimumHeight(40)
        self.language_combo.setCurrentIndex(
            self.language_combo.findData(self.current_language)
        )
        self.language_combo.currentIndexChanged.connect(
            lambda index: self.change_language(
                self.language_combo.itemData(index)
            )
        )
        language_layout.addWidget(self.language_combo)
        layout.addWidget(language_group)

        # ---- appearance ----
        appearance_group = QFrame()
        appearance_group.setObjectName("ToolCard")
        appearance_layout = QVBoxLayout(appearance_group)
        appearance_layout.setContentsMargins(18, 14, 18, 16)
        appearance_layout.setSpacing(8)

        appearance_title = QLabel("Appearance")
        appearance_title.setObjectName("CardTitle")
        appearance_layout.addWidget(appearance_title)

        appearance_hint = QLabel(
            "Themes can also be changed from the Appearance panel on the right."
        )
        appearance_hint.setWordWrap(True)
        appearance_hint.setStyleSheet(f"color: {self.palette.text_muted};")
        appearance_layout.addWidget(appearance_hint)

        theme_combo = QComboBox()
        for key in ui_theme.THEME_ORDER:
            palette = ui_theme.PALETTES[key]
            theme_combo.addItem(palette.name, key)
        theme_combo.setMinimumHeight(40)
        theme_combo.setCurrentIndex(theme_combo.findData(self.theme_key))
        theme_combo.currentIndexChanged.connect(
            lambda index: self.select_theme(theme_combo.itemData(index))
        )
        appearance_layout.addWidget(theme_combo)
        layout.addWidget(appearance_group)

        # ---- diagnostics ----
        diagnostics_group = QFrame()
        diagnostics_group.setObjectName("ToolCard")
        diagnostics_layout = QVBoxLayout(diagnostics_group)
        diagnostics_layout.setContentsMargins(18, 14, 18, 16)
        diagnostics_layout.setSpacing(8)

        diagnostics_title = QLabel("Service Diagnostics")
        diagnostics_title.setObjectName("CardTitle")
        diagnostics_layout.addWidget(diagnostics_title)

        diagnostics_hint = QLabel(
            "Verify that ADB and Fastboot are available on this computer."
        )
        diagnostics_hint.setWordWrap(True)
        diagnostics_hint.setStyleSheet(f"color: {self.palette.text_muted};")
        diagnostics_layout.addWidget(diagnostics_hint)

        check_button = QPushButton("Check ADB / Fastboot")
        check_button.setObjectName("Primary")
        check_button.setMinimumHeight(42)
        check_button.setCursor(Qt.PointingHandCursor)
        check_button.clicked.connect(self.check_tools)
        diagnostics_layout.addWidget(check_button)

        logs_button = QPushButton("Open Operation Logs")
        logs_button.setMinimumHeight(42)
        logs_button.setCursor(Qt.PointingHandCursor)
        logs_button.clicked.connect(lambda: self.navigate("Operation Logs"))
        diagnostics_layout.addWidget(logs_button)

        layout.addWidget(diagnostics_group)
        layout.addStretch()

        return page

    # =====================================================
    # FRAMELESS WINDOW RESIZING
    # =====================================================

    MARGIN = 8

    def _edge_at(self, pos):
        rect = self.rect()
        left = pos.x() <= self.MARGIN
        right = pos.x() >= rect.width() - self.MARGIN
        top = pos.y() <= self.MARGIN
        bottom = pos.y() >= rect.height() - self.MARGIN
        return left, right, top, bottom

    def mouseMoveEvent(self, event):
        if self.isMaximized():
            super().mouseMoveEvent(event)
            return

        if getattr(self, "_resizing", False):
            delta = event.globalPosition().toPoint() - self._resize_origin
            geo = self._resize_geometry
            left, top, right, bottom = self._resize_edges

            x, y, w, h = geo.x(), geo.y(), geo.width(), geo.height()

            if left:
                x += delta.x()
                w -= delta.x()
            if right:
                w += delta.x()
            if top:
                y += delta.y()
                h -= delta.y()
            if bottom:
                h += delta.y()

            if w >= self.minimumWidth() and h >= self.minimumHeight():
                self.setGeometry(x, y, w, h)
            return

        left, right, top, bottom = self._edge_at(event.position().toPoint())
        if (left and top) or (right and bottom):
            self.setCursor(Qt.SizeFDiagCursor)
        elif (right and top) or (left and bottom):
            self.setCursor(Qt.SizeBDiagCursor)
        elif left or right:
            self.setCursor(Qt.SizeHorCursor)
        elif top or bottom:
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.isMaximized():
            edges = self._edge_at(event.position().toPoint())
            if any(edges):
                self._resizing = True
                self._resize_edges = edges
                self._resize_origin = event.globalPosition().toPoint()
                self._resize_geometry = self.geometry()
                return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._resizing = False
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        if not getattr(self, "_resizing", False):
            self.unsetCursor()
        super().leaveEvent(event)

    # =====================================================
    # STATUS BAR
    # =====================================================

    def update_status_bar(self):

        if self.shell is None:
            return

        footer = self.shell.footer
        footer.status.set_text(self.tr("Status: Ready"))

        device_text = "Device: Not Connected"
        connected = False

        try:
            if shutil.which("adb"):
                ok, output = run_command(["adb", "devices"])
                if ok:
                    for line in output.splitlines()[1:]:
                        parts = line.split()
                        if len(parts) >= 2 and parts[1] == "device":
                            connected = True
                            device_text = f"Device: {parts[0]}"
                            break
        except Exception:
            pass

        footer.device.set_text(self.tr(device_text))
        footer.device.set_kind("ok" if connected else "info")

        adb_available = shutil.which("adb") is not None
        footer.adb.set_text(
            self.tr("ADB: Available") if adb_available else self.tr("ADB: Not Installed")
        )
        footer.adb.set_kind("ok" if adb_available else "warn")

    def start_clock(self):

        if getattr(self, "_clock_timer", None) is not None:
            return

        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start()

    def _tick_clock(self):

        if self.shell is None:
            return

        now = datetime.now()
        self.shell.footer.motto.setText(
            now.strftime("%Y/%m/%d  %H:%M:%S") + "   •   "
            "Innovation Today ... A Better Tomorrow™"
        )

    def create_device_manager(self):

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)

        layout.addLayout(
            self.create_page_header(
                "Device Manager",
                "Detect and manage Android devices."
            )
        )

        toolbar = QHBoxLayout()

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(
            "Search device serial number..."
        )

        self.search_box.textChanged.connect(
            self.filter_devices
        )

        refresh_button = QPushButton("Refresh Devices")
        refresh_button.setObjectName("Primary")
        refresh_button.clicked.connect(self.refresh_devices)

        toolbar.addWidget(self.search_box, 1)
        toolbar.addWidget(refresh_button)

        layout.addLayout(toolbar)

        self.device_table = QTableWidget(0, 3)

        self.device_table.setHorizontalHeaderLabels([
            "Serial Number",
            "Status",
            "Device Information"
        ])

        self.device_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.device_table.setSelectionBehavior(
            QTableWidget.SelectRows
        )

        self.device_table.setSelectionMode(
            QTableWidget.SingleSelection
        )

        self.device_table.itemSelectionChanged.connect(
            self.load_device_information
        )

        layout.addWidget(self.device_table)

        note = QLabel(
            "Demo devices are simulated and cannot execute ADB commands."
        )
        note.setProperty("hint", "true")
        layout.addWidget(note)

        return page

    # =====================================================
    # DEVICE INFORMATION
    # =====================================================

    def create_device_information(self):

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)

        layout.addLayout(
            self.create_page_header(
                "Device Information",
                "Read Android device properties."
            )
        )

        self.info_box = QTextEdit()
        self.info_box.setReadOnly(True)

        self.info_box.setPlaceholderText(
            "Select a device to display its information."
        )

        layout.addWidget(self.info_box)

        return page

    # =====================================================
    # ADB TOOLS PAGE
    # =====================================================

    def create_adb_page(self):

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(12)

        layout.addLayout(
            self.create_page_header(
                "ADB Tools",
                "Android Debug Bridge - Device servicing tools."
            )
        )

        # Device selection
        device_layout = QHBoxLayout()

        device_label = QLabel("Connected Device:")

        self.adb_device_combo = QComboBox()
        self.adb_device_combo.setMinimumWidth(280)

        refresh_button = QPushButton("Refresh")
        refresh_button.setObjectName("Primary")
        refresh_button.clicked.connect(
            self.refresh_adb_device_list
        )

        device_layout.addWidget(device_label)
        device_layout.addWidget(self.adb_device_combo, 1)
        device_layout.addWidget(refresh_button)

        layout.addLayout(device_layout)

        self.adb_status_label = QLabel(
            "Status: Waiting for device..."
        )
        self.set_status(self.adb_status_label, "warn")

        layout.addWidget(self.adb_status_label)

        # Device information and reboot
        grid = QGridLayout()
        grid.setSpacing(10)

        actions = [
            ("Device Information", self.adb_device_information),
            ("Reboot System", lambda: self.adb_reboot("system")),
            ("Reboot Recovery", lambda: self.adb_reboot("recovery")),
            ("Reboot Bootloader", lambda: self.adb_reboot("bootloader")),
            ("Install APK", self.adb_install_apk),
            ("Take Screenshot", self.adb_screenshot),
            ("Installed Apps", self.adb_list_apps),
            ("Battery Information", self.adb_battery),
            ("Storage Information", self.adb_storage),
        ]

        for index, (title, function) in enumerate(actions):

            button = QPushButton(title)
            button.setMinimumHeight(48)
            button.clicked.connect(function)

            grid.addWidget(
                button,
                index // 3,
                index % 3
            )

        layout.addLayout(grid)

        output_title = QLabel("ADB Operation Output")
        output_title.setObjectName("SectionTitle")

        layout.addWidget(output_title)

        self.adb_output = QTextEdit()
        self.adb_output.setReadOnly(True)
        self.adb_output.setPlaceholderText(
            "ADB operation results will appear here..."
        )

        layout.addWidget(self.adb_output, 1)

        self.refresh_adb_device_list()

        return page

    # =====================================================
    # ADB DEVICE SELECTION
    # =====================================================

    def get_adb_serial(self):

        if self.adb_device_combo is None:
            return None

        serial = self.adb_device_combo.currentData()

        if not serial:
            QMessageBox.warning(
                self,
                self.tr("No Device"),
                self.tr(
                    "No authorized Android device is connected.\n\n"
                    "Connect your phone, enable USB Debugging, "
                    "and authorize this computer."
                )
            )
            return None

        return serial

    # =====================================================
    # REFRESH ADB DEVICE LIST
    # =====================================================

    def refresh_adb_device_list(self):

        if self.adb_device_combo is None:
            return

        self.adb_device_combo.clear()

        if not ADBTools.check_adb():

            self.adb_device_combo.addItem(
                "ADB not installed",
                None
            )

            self.adb_status_label.setText(
                "Status: ADB NOT FOUND"
            )

            self.set_status(self.adb_status_label, "danger")

            return

        ok, output = ADBTools.devices()

        authorized = []
        unauthorized = []

        if ok:

            for line in output.splitlines():

                parts = line.strip().split()

                if len(parts) >= 2:

                    serial = parts[0]
                    state = parts[1]

                    if state == "device":
                        authorized.append(serial)

                    elif state == "unauthorized":
                        unauthorized.append(serial)

        for serial in authorized:
            self.adb_device_combo.addItem(
                serial,
                serial
            )

        if authorized:

            self.adb_status_label.setText(
                f"Status: {len(authorized)} authorized device(s) connected."
            )

            self.set_status(self.adb_status_label, "ok")

            self.adb_output.append(
                "ADB device list refreshed."
            )

        elif unauthorized:

            self.adb_device_combo.addItem(
                "Device unauthorized",
                None
            )

            self.adb_status_label.setText(
                "Status: Authorize USB debugging on your phone."
            )

            self.set_status(self.adb_status_label, "warn")

        else:

            self.adb_device_combo.addItem(
                "No authorized device connected",
                None
            )

            self.adb_status_label.setText(
                "Status: No real Android device detected."
            )

            self.set_status(self.adb_status_label, "warn")

        self.log("ADB device list refreshed.")

    # =====================================================
    # ADB OUTPUT
    # =====================================================

    def show_adb_result(self, title, ok, output):

        result = (
            f"\n========== {title} ==========\n"
            f"Status: {'SUCCESS' if ok else 'FAILED'}\n\n"
            f"{output}\n"
        )

        if self.adb_output is not None:
            self.adb_output.append(result)

        self.log(
            f"{title}: {'SUCCESS' if ok else 'FAILED'}"
        )

    # =====================================================
    # ADB DEVICE INFORMATION
    # =====================================================

    def adb_device_information(self):

        serial = self.get_adb_serial()

        if not serial:
            return

        info = ADBTools.device_info(serial)

        self.show_adb_result(
            "DEVICE INFORMATION",
            True,
            info
        )

    # =====================================================
    # ADB REBOOT
    # =====================================================

    def adb_reboot(self, mode):

        serial = self.get_adb_serial()

        if not serial:
            return

        mode_names = {
            "system": "Normal System",
            "recovery": "Recovery",
            "bootloader": "Bootloader",
        }

        answer = QMessageBox.question(
            self,
            self.tr("Confirm Reboot"),
            self.tr("Are you sure you want to reboot the device into {mode}?").format(mode=self.tr(mode_names[mode])),
            QMessageBox.Yes | QMessageBox.No
        )

        if answer != QMessageBox.Yes:
            return

        ok, output = ADBTools.reboot(
            serial,
            mode
        )

        self.show_adb_result(
            f"REBOOT {mode.upper()}",
            ok,
            output or "Reboot command sent."
        )

    # =====================================================
    # INSTALL APK
    # =====================================================

    def adb_install_apk(self):

        serial = self.get_adb_serial()

        if not serial:
            return

        apk_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select APK File"),
            "",
            self.tr("Android APK (*.apk)")
        )

        if not apk_path:
            return

        answer = QMessageBox.question(
            self,
            self.tr("Install APK"),
            self.tr("Install this application on the selected device?\n\n{path}").format(path=apk_path),
            QMessageBox.Yes | QMessageBox.No
        )

        if answer != QMessageBox.Yes:
            return

        ok, output = ADBTools.install_apk(
            serial,
            apk_path
        )

        self.show_adb_result(
            "INSTALL APK",
            ok,
            output
        )

    # =====================================================
    # SCREENSHOT
    # =====================================================

    def adb_screenshot(self):

        serial = self.get_adb_serial()

        if not serial:
            return

        destination, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save Device Screenshot"),
            "AYMTECH_screenshot.png",
            self.tr("PNG Image (*.png)")
        )

        if not destination:
            return

        if not destination.lower().endswith(".png"):
            destination += ".png"

        ok, output = ADBTools.screenshot(
            serial,
            destination
        )

        self.show_adb_result(
            "SCREENSHOT",
            ok,
            output
        )

        if ok:

            QMessageBox.information(
                self,
                self.tr("Screenshot Saved"),
                self.tr("Screenshot saved successfully:\n{path}").format(path=destination)
            )

    # =====================================================
    # INSTALLED APPS
    # =====================================================

    def adb_list_apps(self):

        serial = self.get_adb_serial()

        if not serial:
            return

        ok, output = ADBTools.list_apps(serial)

        self.show_adb_result(
            "INSTALLED APPLICATIONS",
            ok,
            output
        )

    # =====================================================
    # BATTERY INFORMATION
    # =====================================================

    def adb_battery(self):

        serial = self.get_adb_serial()

        if not serial:
            return

        ok, output = ADBTools.get_battery(serial)

        self.show_adb_result(
            "BATTERY INFORMATION",
            ok,
            output
        )

    # =====================================================
    # STORAGE INFORMATION
    # =====================================================

    def adb_storage(self):

        serial = self.get_adb_serial()

        if not serial:
            return

        ok, output = ADBTools.get_storage(serial)

        self.show_adb_result(
            "STORAGE INFORMATION",
            ok,
            output
        )

    # =====================================================
    # OTHER TOOL PAGES
    # =====================================================

    def create_tool_page(self, title):

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)

        layout.addLayout(
            self.create_page_header(
                title,
                f"{title} module."
            )
        )

        message = QLabel(
            f"{title}\n\n"
            "This module is prepared for future integration.\n\n"
            "Available foundations:\n"
            "• ADB / Fastboot\n"
            "• Device detection\n"
            "• Device information\n"
            "• Operation logging\n\n"
            "Additional authorized servicing features "
            "will be added in future versions."
        )

        message.setObjectName("InfoPanel")
        message.setWordWrap(True)

        layout.addWidget(message)
        layout.addStretch()

        return page
        # =====================================================
    # SAMSUNG TOOLS PAGE
    # =====================================================

    def create_samsung_tools_page(self):

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)

        layout.addLayout(
            self.create_page_header(
                "Samsung Tools",
                "Samsung device diagnostics and firmware information."
            )
        )

        self.samsung_device_combo = QComboBox()

        layout.addWidget(QLabel("Connected Device"))
        layout.addWidget(self.samsung_device_combo)

        refresh_button = QPushButton("Refresh Devices")
        refresh_button.clicked.connect(self.refresh_samsung_devices)
        layout.addWidget(refresh_button)

        buttons = [
            ("Check Samsung Device", self.samsung_check_device),
            ("Device Information", self.samsung_device_information),
            ("Firmware Information", self.samsung_firmware_information),
            ("Connection Check", self.samsung_connection_check),
        ]

        for title, function in buttons:
            button = QPushButton(title)
            button.setObjectName("Primary")
            button.clicked.connect(function)
            layout.addWidget(button)

        self.samsung_result_box = QTextEdit()
        self.samsung_result_box.setReadOnly(True)
        layout.addWidget(self.samsung_result_box, 1)

        self.refresh_samsung_devices()

        return page

    def refresh_samsung_devices(self):

        self.samsung_device_combo.clear()

        ok, output = ADBTools.devices()

        if not ok:
            self.samsung_result_box.setPlainText(output)
            return

        for line in output.splitlines()[1:]:
            parts = line.split()

            if len(parts) >= 2 and parts[1] == "device":
                self.samsung_device_combo.addItem(parts[0])

        if self.samsung_device_combo.count() == 0:
            self.samsung_result_box.setPlainText(
                "No authorized Android devices found."
            )

    def get_samsung_device(self):

        serial = self.samsung_device_combo.currentText().strip()

        if not serial:
            QMessageBox.warning(
                self,
                self.tr("No Device"),
                self.tr("Please connect and select a device.")
            )
            return None

        return serial

    def samsung_check_device(self):

        serial = self.get_samsung_device()
        if not serial:
            return

        ok, output = SamsungTools.check_samsung_device(serial)

        self.samsung_result_box.setPlainText(output)

    def samsung_device_information(self):

        serial = self.get_samsung_device()
        if not serial:
            return

        ok, output = SamsungTools.device_information(serial)

        self.samsung_result_box.setPlainText(output)

    def samsung_firmware_information(self):

        serial = self.get_samsung_device()
        if not serial:
            return

        ok, output = SamsungTools.firmware_information(serial)

        self.samsung_result_box.setPlainText(output)

    def samsung_connection_check(self):

        serial = self.get_samsung_device()
        if not serial:
            return

        ok, output = SamsungTools.check_connection(serial)

        self.samsung_result_box.setPlainText(output)
         # =====================================================
    # QUALCOMM TOOLS PAGE
    # =====================================================

    def create_qualcomm_tools_page(self):

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)

        layout.addLayout(
            self.create_page_header(
                "Qualcomm Tools",
                "Qualcomm chipset diagnostics and device information."
            )
        )

        self.qualcomm_device_combo = QComboBox()

        layout.addWidget(QLabel("Connected Device"))
        layout.addWidget(self.qualcomm_device_combo)

        refresh_button = QPushButton("Refresh Devices")
        refresh_button.clicked.connect(self.refresh_qualcomm_devices)
        layout.addWidget(refresh_button)

        buttons = [
            ("Check Qualcomm Device", self.qualcomm_check_device),
            ("Device Information", self.qualcomm_device_information),
            ("Firmware Information", self.qualcomm_firmware_information),
            ("Connection Check", self.qualcomm_connection_check),
        ]

        for title, function in buttons:
            button = QPushButton(title)
            button.setObjectName("Primary")
            button.clicked.connect(function)
            layout.addWidget(button)

        self.qualcomm_result_box = QTextEdit()
        self.qualcomm_result_box.setReadOnly(True)
        layout.addWidget(self.qualcomm_result_box, 1)

        self.refresh_qualcomm_devices()

        return page

    def refresh_qualcomm_devices(self):

        self.qualcomm_device_combo.clear()

        ok, output = ADBTools.devices()

        if not ok:
            self.qualcomm_result_box.setPlainText(output)
            return

        for line in output.splitlines()[1:]:
            parts = line.split()

            if len(parts) >= 2 and parts[1] == "device":
                self.qualcomm_device_combo.addItem(parts[0])

        if self.qualcomm_device_combo.count() == 0:
            self.qualcomm_result_box.setPlainText(
                "No authorized Android devices found."
            )

    def get_qualcomm_device(self):

        serial = self.qualcomm_device_combo.currentText().strip()

        if not serial:
            QMessageBox.warning(
                self,
                self.tr("No Device"),
                self.tr("Please connect and select a device.")
            )
            return None

        return serial

    def qualcomm_check_device(self):

        serial = self.get_qualcomm_device()
        if not serial:
            return

        ok, output = QualcommTools.check_qualcomm_device(serial)
        self.qualcomm_result_box.setPlainText(output)

    def qualcomm_device_information(self):

        serial = self.get_qualcomm_device()
        if not serial:
            return

        ok, output = QualcommTools.device_information(serial)
        self.qualcomm_result_box.setPlainText(output)

    def qualcomm_firmware_information(self):

        serial = self.get_qualcomm_device()
        if not serial:
            return

        ok, output = QualcommTools.firmware_information(serial)
        self.qualcomm_result_box.setPlainText(output)

    def qualcomm_connection_check(self):

        serial = self.get_qualcomm_device()
        if not serial:
            return

        ok, output = QualcommTools.check_connection(serial)
        self.qualcomm_result_box.setPlainText(output)   
        # =====================================================

    # =====================================================
    # MEDIATEK TOOLS PAGE
    # =====================================================

    def create_mediatek_tools_page(self):

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)

        layout.addLayout(
            self.create_page_header(
                "MediaTek Tools",
                "MediaTek chipset diagnostics and device information."
            )
        )

        self.mediatek_device_combo = QComboBox()

        layout.addWidget(QLabel("Connected Device"))
        layout.addWidget(self.mediatek_device_combo)

        refresh_button = QPushButton("Refresh Devices")
        refresh_button.clicked.connect(self.refresh_mediatek_devices)
        layout.addWidget(refresh_button)

        buttons = [
            ("Check MediaTek Device", self.mediatek_check_device),
            ("Device Information", self.mediatek_device_information),
            ("Firmware Information", self.mediatek_firmware_information),
            ("Connection Check", self.mediatek_connection_check),
        ]

        for title, function in buttons:
            button = QPushButton(title)
            button.setObjectName("Primary")
            button.clicked.connect(function)
            layout.addWidget(button)

        self.mediatek_result_box = QTextEdit()
        self.mediatek_result_box.setReadOnly(True)
        layout.addWidget(self.mediatek_result_box, 1)

        self.refresh_mediatek_devices()
        return page

    def refresh_mediatek_devices(self):

        self.mediatek_device_combo.clear()
        ok, output = ADBTools.devices()

        if not ok:
            self.mediatek_result_box.setPlainText(output)
            return

        for line in output.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                self.mediatek_device_combo.addItem(parts[0])

        if self.mediatek_device_combo.count() == 0:
            self.mediatek_result_box.setPlainText(
                "No authorized Android devices found."
            )

    def get_mediatek_device(self):

        serial = self.mediatek_device_combo.currentText().strip()

        if not serial:
            QMessageBox.warning(
                self, self.tr("No Device"),
                self.tr("Please connect and select a device.")
            )
            return None

        return serial

    def mediatek_check_device(self):

        serial = self.get_mediatek_device()
        if not serial:
            return

        ok, output = MediaTekTools.check_mediatek_device(serial)
        self.mediatek_result_box.setPlainText(output)

    def mediatek_device_information(self):

        serial = self.get_mediatek_device()
        if not serial:
            return

        ok, output = MediaTekTools.device_information(serial)
        self.mediatek_result_box.setPlainText(output)

    def mediatek_firmware_information(self):

        serial = self.get_mediatek_device()
        if not serial:
            return

        ok, output = MediaTekTools.firmware_information(serial)
        self.mediatek_result_box.setPlainText(output)

    def mediatek_connection_check(self):

        serial = self.get_mediatek_device()
        if not serial:
            return

        ok, output = MediaTekTools.check_connection(serial)
        self.mediatek_result_box.setPlainText(output)


    # =====================================================
    # FIRMWARE CENTER
    # =====================================================

    def create_firmware_center_page(self):

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)

        layout.addLayout(
            self.create_page_header(
                "Firmware Center",
                "Manage firmware files and verify file integrity."
            )
        )

        self.firmware_file_path = ""

        self.firmware_path_label = QLabel("No firmware file selected")
        self.firmware_path_label.setWordWrap(True)
        layout.addWidget(self.firmware_path_label)

        buttons = [
            (self.tr("Select Firmware File"), self.select_firmware_file),
            ("File Information", self.firmware_file_information),
            ("Calculate SHA-256", self.firmware_calculate_sha256),
            ("Scan Firmware Folder", self.firmware_scan_folder),
        ]

        for title, function in buttons:
            button = QPushButton(title)
            button.setObjectName("Primary")
            button.clicked.connect(function)
            layout.addWidget(button)

        self.firmware_result_box = QTextEdit()
        self.firmware_result_box.setReadOnly(True)
        layout.addWidget(self.firmware_result_box, 1)

        return page

    def select_firmware_file(self):

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select Firmware File"),
            "",
            self.tr("Firmware Files") + " (*.zip *.img *.bin *.tar *.md5 *.mbn "
            "*.xml *.ofp *.kdz *.ftf *.ipsw *.ops *.pac *.br *.dat "
            "*.lz4);;All Files (*)"
        )

        if not file_path:
            return

        self.firmware_file_path = file_path
        self.firmware_path_label.setText(file_path)
        self.firmware_result_box.setPlainText(
            "Firmware file selected successfully."
        )

    def firmware_file_information(self):

        if not self.firmware_file_path:
            QMessageBox.warning(
                self, self.tr("No File"), self.tr("Please select a firmware file first.")
            )
            return

        ok, output = FirmwareTools.file_information(
            self.firmware_file_path
        )
        self.firmware_result_box.setPlainText(output)

    def firmware_calculate_sha256(self):

        if not self.firmware_file_path:
            QMessageBox.warning(
                self, self.tr("No File"), self.tr("Please select a firmware file first.")
            )
            return

        ok, output = FirmwareTools.calculate_sha256(
            self.firmware_file_path
        )

        if ok:
            output = (
                "========== SHA-256 CHECKSUM ==========\n"
                f"File: {self.firmware_file_path}\n"
                f"SHA-256: {output}\n\n"
                "Compare this value with the checksum from "
                "the official firmware source."
            )

        self.firmware_result_box.setPlainText(output)

    def firmware_scan_folder(self):

        folder = QFileDialog.getExistingDirectory(
            self, self.tr("Select Firmware Folder")
        )

        if not folder:
            return

        ok, files = FirmwareTools.get_firmware_files(folder)

        if not ok:
            self.firmware_result_box.setPlainText(str(files))
            return

        if not files:
            self.firmware_result_box.setPlainText(
                "No recognized firmware files found in this folder."
            )
            return

        lines = ["========== FIRMWARE FILES =========="]

        for item in files:
            size_mb = item["size"] / (1024 * 1024)
            lines.append(
                f"{item['name']} | {size_mb:.2f} MB | "
                f"{item['extension']}\n{item['path']}"
            )

        self.firmware_result_box.setPlainText("\n\n".join(lines))


    # =====================================================
    # ANDROID SCREEN LOCK SERVICE
    # =====================================================

    def create_screen_lock_page(self):

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(12)

        layout.addLayout(
            self.create_page_header(
                "Screen Lock Service",
                "Android device access and official recovery assistant."
            )
        )

        info = QLabel(
            "ANDROID SCREEN LOCK SERVICE\n\n"
            "This module helps technicians identify Android devices "
            "and guide customers through official account recovery.\n\n"
            "Available operations:\n"
            "• Detect connected Android devices\n"
            "• Display device brand and model\n"
            "• Check Android version\n"
            "• Open official recovery guidance\n\n"
            "Important: This tool does not bypass screen locks "
            "or remove device security."
        )
        info.setWordWrap(True)
        info.setObjectName("InfoPanel")
        layout.addWidget(info)

        brand_label = QLabel(self.tr("Select device brand:"))
        layout.addWidget(brand_label)

        self.screen_lock_brand = QComboBox()

        for brand in [
            "Samsung", "Xiaomi", "Redmi", "POCO",
            "OPPO", "Realme", "Huawei", "Motorola",
            "Google Pixel", "Other Android"
        ]:
            self.screen_lock_brand.addItem(self.tr(brand), brand)

        layout.addWidget(self.screen_lock_brand)

        detect_button = QPushButton("Detect Connected Device")
        detect_button.setCursor(Qt.PointingHandCursor)
        detect_button.clicked.connect(self.screen_lock_detect_device)
        layout.addWidget(detect_button)

        refresh_button = QPushButton("Refresh Device Detection")
        refresh_button.setCursor(Qt.PointingHandCursor)
        refresh_button.clicked.connect(self.screen_lock_detect_device)
        layout.addWidget(refresh_button)

        security_button = QPushButton("Android Security Diagnostics")
        security_button.setCursor(Qt.PointingHandCursor)
        security_button.clicked.connect(self.screen_lock_security_diagnostics)
        layout.addWidget(security_button)

        lock_info_button = QPushButton("Android Lock Information")
        lock_info_button.setCursor(Qt.PointingHandCursor)
        lock_info_button.clicked.connect(self.screen_lock_information)
        layout.addWidget(lock_info_button)

        recovery_button = QPushButton("Show Official Recovery Guidance")
        recovery_button.setCursor(Qt.PointingHandCursor)
        recovery_button.clicked.connect(self.screen_lock_recovery_guide)
        layout.addWidget(recovery_button)

        self.screen_lock_status = QLabel("Status: NOT CONNECTED")
        self.set_status(self.screen_lock_status, "danger")
        layout.addWidget(self.screen_lock_status)

        self.screen_lock_result = QTextEdit()
        self.screen_lock_result.setReadOnly(True)
        self.screen_lock_result.setPlaceholderText(
            self.tr(
                "Device information and recovery guidance will appear here..."
            )
        )
        layout.addWidget(self.screen_lock_result)

        layout.addStretch()
        return page

    def screen_lock_detect_device(self):
        try:
            ok, output = ADBTools.devices()

            if not ok:
                self.screen_lock_status.setText("Status: ADB ERROR")
                self.set_status(self.screen_lock_status, "danger")
                self.screen_lock_result.setPlainText(
                    "ADB ERROR\n\n" + output
                )
                return

            devices = []

            for line in output.splitlines():
                line = line.strip()

                if not line or line.startswith("List of devices"):
                    continue

                parts = line.split()

                if len(parts) >= 2:
                    devices.append((parts[0], parts[1]))

            if not devices:
                self.screen_lock_status.setText("Status: NOT CONNECTED")
                self.set_status(self.screen_lock_status, "danger")
                self.screen_lock_result.setPlainText(
                    "NO ANDROID DEVICE DETECTED\n\n"
                    "Connect an Android phone using USB.\n"
                    "Enable USB debugging if available."
                )
                return

            authorized = [d for d in devices if d[1] == "device"]
            unauthorized = [d for d in devices if d[1] == "unauthorized"]

            if authorized:
                status_text = "Status: CONNECTED"
                status_kind = "ok"
            elif unauthorized:
                status_text = "Status: UNAUTHORIZED"
                status_kind = "warn"
            else:
                status_text = "Status: OFFLINE"
                status_kind = "danger"

            self.screen_lock_status.setText(status_text)
            self.set_status(self.screen_lock_status, status_kind)

            results = ["SMART ANDROID DEVICE DETECTION\n"]

            for serial, status in devices:

                results.append("=" * 45)
                results.append(f"Serial: {serial}")
                results.append(f"ADB Status: {status.upper()}")

                if status != "device":
                    results.append(
                        "Device is not authorized for ADB diagnostics."
                    )
                    results.append("")
                    continue

                properties = {
                    "Manufacturer": "ro.product.manufacturer",
                    "Brand": "ro.product.brand",
                    "Model": "ro.product.model",
                    "Device": "ro.product.device",
                    "Android Version": "ro.build.version.release",
                    "SDK Version": "ro.build.version.sdk",
                    "Security Patch": "ro.build.version.security_patch",
                    "Board Platform": "ro.board.platform",
                    "Hardware": "ro.hardware",
                    "SoC Model": "ro.soc.model",
                }

                values = {}

                for name, prop in properties.items():
                    prop_ok, value = ADBTools.run([
                        "-s", serial, "shell", "getprop", prop
                    ])

                    values[name] = (
                        value.strip()
                        if prop_ok and value.strip()
                        else "Unavailable"
                    )

                platform = (
                    values["Board Platform"] + " " +
                    values["Hardware"] + " " +
                    values["SoC Model"]
                ).lower()

                if any(x in platform for x in ["qcom", "qualcomm"]):
                    chipset = "Qualcomm Snapdragon family (detected)"
                elif "mediatek" in platform or "mt" in platform:
                    chipset = "MediaTek family (possible)"
                elif "exynos" in platform:
                    chipset = "Samsung Exynos family (detected)"
                elif any(x in platform for x in ["kirin", "hisilicon"]):
                    chipset = "Huawei Kirin family (detected)"
                elif any(x in platform for x in ["unisoc", "spreadtrum"]):
                    chipset = "Unisoc family (detected)"
                elif "tensor" in platform:
                    chipset = "Google Tensor family (detected)"
                else:
                    chipset = "Unknown / Not confirmed"

                results.append("\nDEVICE INFORMATION")

                for name, value in values.items():
                    results.append(f"{name}: {value}")

                results.append(f"\nPROCESSOR FAMILY: {chipset}")
                results.append(
                    "\nDIAGNOSTIC LIMITATIONS:\n"
                    "ADB only provides information available to an "
                    "authorized debugging connection.\n"
                    "A locked phone may not authorize ADB access.\n"
                    "Processor detection is based on Android properties "
                    "and is not a hardware-level verification."
                )
                results.append("")

            self.screen_lock_result.setPlainText("\n".join(results))

        except Exception as e:
            self.screen_lock_status.setText("Status: ERROR")
            self.set_status(self.screen_lock_status, "danger")
            self.screen_lock_result.setPlainText(
                f"Device detection error:\n{e}"
            )


    def screen_lock_security_diagnostics(self):

        try:
            ok, output = ADBTools.devices()

            if not ok:
                self.screen_lock_result.setPlainText(
                    "ADB ERROR\n\n" + output
                )
                return

            devices = []

            for line in output.splitlines():
                parts = line.strip().split()

                if len(parts) >= 2 and parts[1] == "device":
                    devices.append(parts[0])

            if not devices:
                self.screen_lock_result.setPlainText(
                    "No authorized Android device detected.\n\n"
                    "Connect a device and authorize USB debugging."
                )
                return

            results = ["ANDROID SECURITY DIAGNOSTICS\n"]

            properties = {
                "USB Debugging Setting": "service.adb.tcp.port",
                "Bootloader Lock": "ro.boot.flash.locked",
                "Verified Boot State": "ro.boot.verifiedbootstate",
                "Bootloader State": "ro.boot.vbmeta.device_state",
                "Android Security Patch": "ro.build.version.security_patch",
                "Build Type": "ro.build.type",
                "SELinux Status": "ro.boot.selinux",
            }

            for serial in devices:

                results.append("=" * 45)
                results.append(f"Device Serial: {serial}")

                for name, prop in properties.items():

                    prop_ok, value = ADBTools.run([
                        "-s", serial, "shell", "getprop", prop
                    ])

                    value = value.strip() if prop_ok else ""
                    results.append(
                        f"{name}: {value if value else 'Unavailable / Not exposed'}"
                    )

                root_ok, root_output = ADBTools.run([
                    "-s", serial, "shell", "su", "-c", "id"
                ], timeout=10)

                if root_ok and "uid=0" in root_output:
                    root_status = "Root access available"
                else:
                    root_status = "Root access not confirmed"

                results.append(f"Root Indicator: {root_status}")

                results.append(
                    "\nNOTES:\n"
                    "These values are read-only diagnostic indicators.\n"
                    "Unavailable properties do not prove that a device "
                    "is locked or secure.\n"
                    "Root detection is not conclusive on every Android device."
                )

            self.screen_lock_result.setPlainText("\n".join(results))

        except Exception as e:
            self.screen_lock_result.setPlainText(
                f"Security diagnostics error:\n{e}"
            )


    def screen_lock_information(self):

        try:
            ok, output = ADBTools.devices()

            if not ok:
                self.screen_lock_result.setPlainText(
                    "ADB ERROR\n\n" + output
                )
                return

            devices = []

            for line in output.splitlines():
                parts = line.strip().split()

                if len(parts) >= 2 and parts[1] == "device":
                    devices.append(parts[0])

            if not devices:
                self.screen_lock_result.setPlainText(
                    "No authorized Android device detected."
                )
                return

            results = ["ANDROID LOCK INFORMATION\n"]

            for serial in devices:

                results.append("=" * 45)
                results.append(f"Device: {serial}")

                lock_ok, lock_output = ADBTools.run([
                    "-s", serial,
                    "shell", "dumpsys", "window"
                ], timeout=20)

                lock_state = "UNKNOWN"

                if lock_ok:
                    text = lock_output.lower()

                    if "mshowinglockscreen=true" in text:
                        lock_state = "LOCKED (reported by WindowManager)"
                    elif "mshowinglockscreen=false" in text:
                        lock_state = "NOT SHOWING LOCK SCREEN"

                results.append(f"Screen Lock State: {lock_state}")

                keyguard_ok, keyguard_output = ADBTools.run([
                    "-s", serial,
                    "shell", "dumpsys", "trust"
                ], timeout=20)

                if keyguard_ok:
                    trust_text = keyguard_output.lower()

                    if "device locked" in trust_text:
                        results.append(
                            "Trust Service: Device reports locked"
                        )
                    elif "device unlocked" in trust_text:
                        results.append(
                            "Trust Service: Device reports unlocked"
                        )
                    else:
                        results.append(
                            "Trust Service: State not confirmed"
                        )
                else:
                    results.append(
                        "Trust Service: Information unavailable"
                    )

                results.append(
                    "\nIMPORTANT:\n"
                    "ADB access does not prove that the screen is unlocked.\n"
                    "WindowManager output may vary across Android versions.\n"
                    "UNKNOWN means the lock state could not be verified."
                )

            self.screen_lock_result.setPlainText("\n".join(results))

        except Exception as e:
            self.screen_lock_result.setPlainText(
                f"Lock information error:\n{e}"
            )

    def screen_lock_recovery_guide(self):

        brand = self.screen_lock_brand.currentText()

        guides = {
            "Samsung":
                "Use Samsung's official support and account recovery "
                "options. A factory reset may erase user data.",
            "Xiaomi":
                "Use Xiaomi Account recovery and official support. "
                "Account verification may be required.",
            "Redmi":
                "Use Xiaomi Account recovery and official support. "
                "Account verification may be required.",
            "POCO":
                "Use Xiaomi Account recovery and official support. "
                "Account verification may be required.",
            "OPPO":
                "Contact OPPO official support with proof of ownership.",
            "Realme":
                "Contact realme official support with proof of ownership.",
            "Huawei":
                "Use Huawei ID recovery and official support.",
            "Motorola":
                "Use Google's official Android recovery guidance "
                "or Motorola support.",
            "Google Pixel":
                "Use Google's official account recovery and Pixel support.",
            "Other Android":
                "Identify the exact model and contact its manufacturer's "
                "official support."
        }

        self.screen_lock_result.setPlainText(
            f"OFFICIAL RECOVERY GUIDANCE\n\n"
            f"Brand: {brand}\n\n"
            f"{guides.get(brand, 'Contact the manufacturer support.')}\n\n"
            "WARNING:\n"
            "A factory reset can erase personal data and may still "
            "require the previously synchronized Google account "
            "after reset (Factory Reset Protection).\n\n"
            "Always obtain customer authorization and confirm "
            "data backup before any reset."
        )


        # ANDROID DIAGNOSTICS PAGE
    # =====================================================

    def create_android_diagnostics_page(self):

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)

        layout.addLayout(
            self.create_page_header(
                "Android Tools",
                "Android device diagnostics and servicing."
            )
        )

        self.android_device_combo = QComboBox()

        refresh_button = QPushButton("Refresh Devices")
        refresh_button.clicked.connect(
            self.refresh_android_devices
        )

        layout.addWidget(QLabel("Connected Android Device"))
        layout.addWidget(self.android_device_combo)
        layout.addWidget(refresh_button)

        buttons = [
            ("Full Diagnostic", self.android_full_diagnostic),
            ("Device Information", self.android_device_information),
            ("Battery Health", self.android_battery_health),
            ("Storage Analysis", self.android_storage_analysis),
            ("Installed Apps", self.android_installed_apps),
        ]

        for title, function in buttons:
            button = QPushButton(title)
            button.setObjectName("Primary")
            button.clicked.connect(function)
            layout.addWidget(button)

        self.android_result_box = QTextEdit()
        self.android_result_box.setReadOnly(True)

        layout.addWidget(self.android_result_box, 1)

        self.refresh_android_devices()

        return page

    # =====================================================
    # ANDROID DIAGNOSTICS ACTIONS
    # =====================================================

    def refresh_android_devices(self):

        self.android_device_combo.clear()

        ok, output = ADBTools.devices()

        if not ok:
            self.android_result_box.setPlainText(output)
            return

        for line in output.splitlines()[1:]:

            parts = line.split()

            if len(parts) >= 2 and parts[1] == "device":
                self.android_device_combo.addItem(parts[0])

        if self.android_device_combo.count() == 0:
            self.android_result_box.setPlainText(
                "No authorized Android devices found.\n"
                "Connect a phone and enable USB debugging."
            )

    def get_android_device(self):

        serial = self.android_device_combo.currentText().strip()

        if not serial:
            QMessageBox.warning(
                self,
                self.tr("No Device"),
                self.tr("Please connect and select an Android device.")
            )
            return None

        return serial

    def android_full_diagnostic(self):

        serial = self.get_android_device()
        if not serial:
            return

        ok, output = AndroidTools.full_diagnostic(serial)
        self.android_result_box.setPlainText(output)
        self.log("Android full diagnostic completed.")

    def android_device_information(self):

        serial = self.get_android_device()
        if not serial:
            return

        output = ADBTools.device_info(serial)
        self.android_result_box.setPlainText(output)
        self.log("Android device information requested.")

    def android_battery_health(self):

        serial = self.get_android_device()
        if not serial:
            return

        ok, output = AndroidTools.battery_health(serial)
        self.android_result_box.setPlainText(output)
        self.log("Android battery information requested.")

    def android_storage_analysis(self):

        serial = self.get_android_device()
        if not serial:
            return

        ok, output = AndroidTools.storage_analysis(serial)
        self.android_result_box.setPlainText(output)
        self.log("Android storage analysis requested.")

    def android_installed_apps(self):

        serial = self.get_android_device()
        if not serial:
            return

        ok, output = AndroidTools.installed_apps(serial)
        self.android_result_box.setPlainText(output)
        self.log("Android installed apps listed.")
    # =====================================================
    # LOGS PAGE
    # =====================================================

    def create_logs_page(self):

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)

        layout.addLayout(
            self.create_page_header(
                "Operation Logs",
                "Application activity and command history."
            )
        )

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)

        layout.addWidget(self.log_box)

        clear_button = QPushButton("Clear Logs")
        clear_button.clicked.connect(
            lambda: self.log_box.clear()
        )

        layout.addWidget(clear_button)

        return page
    def create_phone_screen_page(self):

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(12)

        title = QLabel("Live Phone Screen")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        self.phone_screen_status = QLabel(
            "Status: Waiting for Android device"
        )
        layout.addWidget(self.phone_screen_status)

        controls = QHBoxLayout()

        start_button = QPushButton("Start Preview")
        start_button.clicked.connect(self.start_phone_screen)
        controls.addWidget(start_button)

        stop_button = QPushButton("Stop Preview")
        stop_button.clicked.connect(self.stop_phone_screen)
        controls.addWidget(stop_button)

        layout.addLayout(controls)

        self.phone_screen_label = QLabel(
            "Connect an Android device and start preview"
        )
        self.phone_screen_label.setAlignment(Qt.AlignCenter)
        self.phone_screen_label.setMinimumSize(360, 500)
        self.phone_screen_label.setObjectName("PhoneFrame")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.phone_screen_label)

        layout.addWidget(scroll, 1)

        return page
    def start_phone_screen(self):

        serial = self.get_adb_serial()
        if not serial:
            return

        if not shutil.which("adb"):
            QMessageBox.warning(
                self,
                "ADB Missing",
                "ADB was not found. Install Android Platform Tools."
            )
            return

        self.phone_screen_serial = serial
        self.phone_screen_status.setText(
            "Status: Starting phone screen preview..."
        )

        self.phone_screen_timer.start()

    def stop_phone_screen(self):

        self.phone_screen_timer.stop()

        if self.phone_screen_process.state() != QProcess.NotRunning:
            self.phone_screen_process.kill()

        self.phone_screen_busy = False
        self.phone_screen_status.setText(
            "Status: Preview stopped"
        )

    def update_phone_screen(self):

        if self.phone_screen_busy:
            return

        if not self.phone_screen_serial:
            self.stop_phone_screen()
            return

        self.phone_screen_busy = True

        self.phone_screen_process.start(
            "adb",
            [
                "-s",
                self.phone_screen_serial,
                "exec-out",
                "screencap",
                "-p"
            ]
        )

    def phone_screen_capture_finished(
        self, exit_code, exit_status
    ):

        self.phone_screen_busy = False

        if exit_code != 0:
            self.phone_screen_status.setText(
                "Status: Device disconnected or ADB error"
            )
            self.stop_phone_screen()
            return

        data = self.phone_screen_process.readAllStandardOutput()

        image = QImage.fromData(bytes(data), "PNG")

        if image.isNull():
            self.phone_screen_status.setText(
                "Status: Could not read phone screenshot"
            )
            return

        pixmap = QPixmap.fromImage(image)

        self.phone_screen_label.setPixmap(
            pixmap.scaled(
                self.phone_screen_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        )

        self.phone_screen_status.setText(
            f"Status: Connected - {image.width()} x {image.height()}"
        )
    # =====================================================
    # NAVIGATION
    # =====================================================

    def navigate(self, title):

        if title not in self.shell.sidebar.buttons:
            title = "Dashboard"

        self.shell.show_page(title)
        self.log(f"Opened page: {title}")

    # =====================================================
    # LOGGING
    # =====================================================

    def log(self, message):

        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"

        if self.log_box is not None:
            self.log_box.append(line)

        print(line)

    # =====================================================
    # CHECK ADB AND FASTBOOT
    # =====================================================

    def check_tools(self):

        results = []

        for tool, args in [
            ("ADB", ["adb", "version"]),
            ("Fastboot", ["fastboot", "--version"]),
        ]:

            path = shutil.which(args[0])

            if path:

                ok, output = run_command(args)

                results.append(
                    f"{tool}: {'AVAILABLE' if ok else 'ERROR'}\n"
                    f"Path: {path}\n"
                    f"{output}"
                )

            else:

                results.append(
                    f"{tool}: NOT FOUND\n"
                    "Install Android Platform Tools."
                )

        QMessageBox.information(
            self,
            self.tr("Tool Status"),
            "\n\n".join(results)
        )

        self.log("Checked ADB and Fastboot.")

    # =====================================================
    # REFRESH DEVICE MANAGER
    # =====================================================

    def refresh_devices(self):

        if self.device_table is None:
            return

        self.device_table.setRowCount(0)
        self.log("Scanning Android devices...")

        devices = []

        if shutil.which("adb"):

            ok, output = run_command([
                "adb",
                "devices",
                "-l"
            ])

            if ok:

                for line in output.splitlines()[1:]:

                    line = line.strip()

                    if not line or line.startswith("*"):
                        continue

                    parts = line.split()

                    if len(parts) >= 2:

                        devices.append({
                            "serial": parts[0],
                            "state": parts[1],
                            "details": " ".join(parts[2:])
                        })

        self.show_devices(
            devices,
            "ADB scan completed."
        )

        if not devices:

            row = self.device_table.rowCount()
            self.device_table.insertRow(row)

            values = [
                "DEMO-ANDROID-001",
                "demo",
                "Samsung Galaxy S24 (Virtual)"
            ]

            for col, value in enumerate(values):

                self.device_table.setItem(
                    row,
                    col,
                    QTableWidgetItem(value)
                )

            self.device_table.selectRow(row)
            self.log("Demo Android device loaded.")

        self.filter_devices()

    # =====================================================
    # DISPLAY DEVICES
    # =====================================================

    def show_devices(self, devices, output):

        self.device_table.setRowCount(0)

        for device in devices:

            row = self.device_table.rowCount()
            self.device_table.insertRow(row)

            values = [
                device["serial"],
                device["state"],
                device["details"]
            ]

            for col, value in enumerate(values):

                self.device_table.setItem(
                    row,
                    col,
                    QTableWidgetItem(value)
                )

        self.log(output)

    # =====================================================
    # FILTER DEVICES
    # =====================================================

    def filter_devices(self):

        if self.device_table is None:
            return

        if self.search_box is None:
            return

        query = self.search_box.text().lower().strip()

        for row in range(self.device_table.rowCount()):

            item = self.device_table.item(row, 0)

            serial = (
                item.text().lower()
                if item else ""
            )

            self.device_table.setRowHidden(
                row,
                query not in serial
            )

    # =====================================================
    # LOAD DEVICE INFORMATION
    # =====================================================

    def load_device_information(self):

        if self.device_table is None:
            return

        if self.info_box is None:
            return

        row = self.device_table.currentRow()

        if row < 0:
            return

        serial_item = self.device_table.item(row, 0)
        state_item = self.device_table.item(row, 1)

        if not serial_item or not state_item:
            return

        serial = serial_item.text()
        state = state_item.text()

        if state == "demo":

            demo_info = """
========================================
          AYMTECH PRO
          DEMO DEVICE
========================================

Manufacturer : Samsung
Brand        : Samsung
Model        : SM-S921B
Device       : Galaxy S24
Android      : 14
SDK Version  : 34
Build ID     : UP1A.231005.007

Connection   : DEMO MODE
Status       : SIMULATED DEVICE

----------------------------------------

This is a virtual device for testing
the AYMTECH PRO interface.

No real phone is connected.
"""

            self.info_box.setPlainText(demo_info)
            self.log("Demo device information displayed.")
            return

        if state != "device":

            self.info_box.setPlainText(
                f"Serial Number: {serial}\n"
                f"State: {state}\n\n"
                "Device authorization is required."
            )
            return

        properties = [
            ("Manufacturer", "ro.product.manufacturer"),
            ("Brand", "ro.product.brand"),
            ("Model", "ro.product.model"),
            ("Device", "ro.product.device"),
            ("Android Version", "ro.build.version.release"),
            ("SDK Version", "ro.build.version.sdk"),
            ("Build ID", "ro.build.display.id"),
            ("Security Patch", "ro.build.version.security_patch"),
            ("Serial Number", "ro.serialno"),
        ]

        lines = [
            "========================================",
            "       AYMTECH PRO - DEVICE INFO",
            "========================================",
            f"ADB Serial: {serial}",
            ""
        ]

        for label, prop in properties:

            ok, value = run_command([
                "adb",
                "-s",
                serial,
                "shell",
                "getprop",
                prop
            ])

            lines.append(
                f"{label}: "
                f"{value if ok and value else 'Unavailable'}"
            )

        self.info_box.setPlainText("\n".join(lines))

        self.log(
            f"Read device information: {serial}"
        )


# =========================================================
# APPLICATION ENTRY POINT
# =========================================================

def _export_screenshots() -> None:
    """Headless screenshot export used for visual regression checks."""
    from PySide6.QtCore import QTimer

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.aboutToQuit.connect(ui_icons.clear_caches)

    window = AymtechPro()
    window.resize(1560, 900)
    window.show()
    window.set_animations(False)

    target = os.environ.get("AYMTECH_SHOT_DIR", "screenshots")
    os.makedirs(target, exist_ok=True)

    def capture() -> None:
        window.select_theme("dark_blue")
        window.navigate("Dashboard")
        app.processEvents()
        window.grab().save(os.path.join(target, "dashboard_dark_blue.jpg"))

        window.select_theme("platinum_light")
        app.processEvents()
        window.grab().save(os.path.join(target, "dashboard_platinum_light.jpg"))

        window.select_theme("dark_blue")
        window.navigate("Screen Lock Service")
        app.processEvents()
        window.grab().save(os.path.join(target, "screen_lock_service.jpg"))

        window.navigate("Device Manager")
        app.processEvents()
        window.grab().save(os.path.join(target, "device_manager.jpg"))

        app.quit()

    QTimer.singleShot(600, capture)
    app.exec()


if __name__ == "__main__":

    import os

    if "--export-screenshots" in sys.argv:
        _export_screenshots()
        sys.exit(0)

    app = QApplication(sys.argv)

    app.setApplicationName(APP_NAME)
    app.setWindowIcon(ui_icons.make_icon("android", ui_theme.DARK_BLUE.accent, 48))
    app.aboutToQuit.connect(ui_icons.clear_caches)

    window = AymtechPro()
    window.show()

    sys.exit(app.exec())
