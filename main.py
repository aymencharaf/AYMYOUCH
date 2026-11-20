
from tools.qualcomm_tools import QualcommTools
from tools.mediatek_tools import MediaTekTools
from tools.android_tools import AndroidTools
from tools.samsung_tools import SamsungTools
from PySide6.QtGui import QImage, QPixmap
import sys
import shutil
import subprocess
from datetime import datetime

from PySide6.QtCore import QEvent, Qt, QSettings, QTimer, QProcess
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
    QCheckBox,
    QInputDialog,
    QFileDialog,
)

from tools.adb_tools import ADBTools
from tools.device_control import DeviceControl
from tools.diagnostics import Diagnostics, DeviceLockState
from tools.fastboot_tools import FastbootTools
from tools.firmware_center import FirmwareCenter
from tools.ios_tools import IOSTools
from tools.network_tools import NetworkTools
from tools.translations import translate_text
from tools.unlock_tools import UnlockTools

from ui import theme as ui_theme
from ui import icons as ui_icons
from ui.busy import BusyOverlay, BusySpinner
from ui.dashboard import DashboardPage
from ui.devices import DeviceRegistry, fill_device_combo
from ui.pages import PageShell
from ui.shell import AppShell
from ui.tasks import TaskRunner
from ui.tools_ui import ToolPage, labelled
from ui.widgets import PageSubtitle, PageTitle


# =========================================================
# CONFIGURATION
# =========================================================

APP_NAME = "AYMTECH PRO"
APP_VERSION = "2.2.1"

# The application stylesheet is generated per theme by
# ui.theme.build_stylesheet(); see AymtechPro.apply_styles().
STYLE = ""


# =========================================================
# INTERFACE SWITCHES
# =========================================================

# The appearance panel used to take a third of the window.  Themes, background,
# transparency and animation controls now live in Settings instead, so the tool
# pages get the full width.  Flip this to True to bring the dock back.
SHOW_THEME_PANEL = False

# Keep the theme *preview cards* hidden even when the panel itself is shown
# (the background selector and the switches stay available).
SHOW_THEME_CARDS = True


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
        self._header_icons = []

        # background work + shared device list
        self.runner = TaskRunner(self)
        self.devices = DeviceRegistry(self)
        self.devices.attach_runner(self.runner)
        self.busy_overlay = None

        self.build_interface()

        self.devices.start(immediate=False)
        self.devices.devices_changed.connect(self.on_devices_changed)
        self.devices.scan_finished.connect(self.on_scan_finished)
        self.runner.busy_changed.connect(self.on_busy_changed)

        self._busy_timer = QTimer(self)
        self._busy_timer.setSingleShot(True)
        self._busy_timer.setInterval(450)
        self._busy_timer.timeout.connect(self.show_busy_overlay)
        self.setup_busy_overlay()

        self.devices.request_scan()

    # =====================================================
    # INTERFACE
    # =====================================================

    def build_interface(self):

        self.palette = ui_theme.PALETTES[self.theme_key]

        self.panel_opacity = 0.92 if self.opacity > 0.5 else 1.0
        self.shell = AppShell(
            self.palette,
            self.panel_opacity,
            show_themes=SHOW_THEME_CARDS,
            show_dock=SHOW_THEME_PANEL,
        )
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
            ("IMEI & Network", "imei", self.create_imei_page),
            ("Fastboot Tools", "fastboot", self.create_fastboot_page),
            ("Unlock & FRP", "unlock", self.create_unlock_page),
            ("Device Control", "device_manager", self.create_device_control_page),
            ("Packages & Files", "logs", self.create_packages_page),
            ("Logs & Reports", "logs", self.create_reports_page),
            ("iOS Tools", "ios", self.create_ios_page),
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
        if SHOW_THEME_PANEL:
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
    # BACKGROUND TASKS AND DEVICE STATE
    # =====================================================

    def on_busy_changed(self, busy):

        if self.shell is None:
            return

        footer = self.shell.footer
        if busy:
            footer.status.set_text(self.tr("Status: Working..."))
            footer.status.set_kind("warn")
            # only veil the page when the work is actually slow
            self._busy_timer.start()
        else:
            self._busy_timer.stop()
            self.hide_busy_overlay()
            footer.status.set_text(self.tr("Status: Ready"))
            footer.status.set_kind("ok")

    def setup_busy_overlay(self):
        """Create the page veil that covers slow background work."""

        if self.shell is None or self.busy_overlay is not None:
            return

        container = self.shell.page_container
        self.busy_overlay = BusyOverlay(self.palette, container)
        self.busy_overlay.set_message(self.tr("Working, please wait..."))
        self.busy_overlay.setGeometry(container.rect())
        container.installEventFilter(self)

    def show_busy_overlay(self):

        if self.busy_overlay is None or self.shell is None:
            return

        self.busy_overlay.set_message(self.tr("Working, please wait..."))
        self.busy_overlay.setGeometry(self.shell.page_container.rect())
        self.busy_overlay.setActive(True)

    def hide_busy_overlay(self):

        if self.busy_overlay is not None:
            self.busy_overlay.setActive(False)

    def eventFilter(self, obj, event):

        if (
            self.busy_overlay is not None
            and self.shell is not None
            and obj is self.shell.page_container
            and event.type() == QEvent.Resize
        ):
            self.busy_overlay.setGeometry(obj.rect())

        return super().eventFilter(obj, event)

    def _device_spinners(self):

        for name in ("adb_spinner", "android_spinner"):
            spinner = getattr(self, name, None)
            if spinner is not None:
                yield spinner

    def set_device_spinners(self, active):
        for spinner in self._device_spinners():
            spinner.set_active(active)

    def refresh_all_devices(self):
        """Manual refresh: spin the indicators and rescan in a worker."""

        self.set_device_spinners(True)
        self.log("Scanning Android devices...")
        self.devices.request_scan(force=True)

    def on_scan_finished(self, adb_available):

        self.set_device_spinners(False)

        if self.shell is None:
            return

        footer = self.shell.footer
        footer.adb.set_text(
            self.tr("ADB: Available") if adb_available
            else self.tr("ADB: Not Installed")
        )
        footer.adb.set_kind("ok" if adb_available else "warn")

    def on_devices_changed(self, devices):

        # keep every device selector in sync with the registry
        self.sync_device_selectors()
        self.fill_device_table()

        footer = self.shell.footer if self.shell is not None else None
        if footer is not None:
            authorized = [d for d in devices if d.state == "device"]
            if authorized:
                footer.device.set_text(
                f"{self.tr('Device:')} {authorized[0].serial}"
            )
                footer.device.set_kind("ok")
            elif devices:
                footer.device.set_text(
                    self.tr("Device: Not Authorized")
                )
                footer.device.set_kind("warn")
            else:
                footer.device.set_text(self.tr("Device: Not Connected"))
                footer.device.set_kind("info")

    def sync_device_selectors(self):

        devices = self.devices.devices
        placeholder = self.tr("No authorized device connected")

        for combo in (
            getattr(self, "adb_device_combo", None),
            getattr(self, "android_device_combo", None),
            getattr(self, "samsung_device_combo", None),
            getattr(self, "qualcomm_device_combo", None),
            getattr(self, "mediatek_device_combo", None),
        ):
            if combo is None:
                continue
            fill_device_combo(combo, devices, placeholder)

        if getattr(self, "adb_status_label", None) is not None:
            authorized = [d for d in devices if d.state == "device"]
            unauthorized = [d for d in devices if d.state == "unauthorized"]
            self.adb_status_label.setText(self._adb_status_text())

            if authorized:
                self.set_status(self.adb_status_label, "ok")
            elif unauthorized:
                self.set_status(self.adb_status_label, "warn")
            elif not self.devices.adb_available:
                self.set_status(self.adb_status_label, "danger")
            else:
                self.set_status(self.adb_status_label, "warn")

        if getattr(self, "phone_screen_serial", None):
            if self.devices.find(self.phone_screen_serial) is None:
                self.stop_phone_screen()
                if getattr(self, "phone_screen_status", None) is not None:
                    self.phone_screen_status.setText(
                        "Status: Device disconnected"
                    )

    def run_background(self, title, fn, on_done):
        """Run *fn* in the thread pool; *on_done(result)* runs on the UI."""

        self.log(f"Started: {title}")

        def finished(result):
            try:
                on_done(result)
            finally:
                self.log(f"Finished: {title}")

        def failed(message):
            self.log(f"Failed: {title} - {message.splitlines()[0]}")
            QMessageBox.critical(
                self,
                self.tr("Operation Failed"),
                f"{title}\n\n{message.splitlines()[0]}",
            )

        self.runner.run(fn, finished, failed)

    def selected_adb_serial(self):

        if self.adb_device_combo is None:
            return None

        serial = self.adb_device_combo.currentData()
        if serial:
            return serial

        device = self.devices.first_authorized()
        return device.serial if device else None

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
        self.retint_indicators()

    def retint_indicators(self):
        """Re-colour busy indicators after a theme change."""

        for spinner in self._device_spinners():
            spinner.set_palette(self.palette)

        if getattr(self, "screen_lock_spinner", None) is not None:
            self.screen_lock_spinner.set_palette(self.palette)

        if self.busy_overlay is not None:
            self.busy_overlay.set_palette(self.palette)

    def apply_theme_now(self):

        self.palette = ui_theme.PALETTES[self.theme_key]
        self.settings.setValue("theme", self.theme_key)

        self.apply_styles()
        self.retheme()
        if SHOW_THEME_PANEL:
            self.shell.theme_dock.set_active_theme(self.theme_key)
            self.shell.theme_dock.apply_button.setStyleSheet(
                self.shell.theme_dock._apply_style(self.palette)
            )

        # keep the Settings selectors in sync with the active theme
        if getattr(self, "settings_theme_combo", None) is not None:
            index = self.settings_theme_combo.findData(self.theme_key)
            if index >= 0:
                self.settings_theme_combo.blockSignals(True)
                self.settings_theme_combo.setCurrentIndex(index)
                self.settings_theme_combo.blockSignals(False)

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

            elif isinstance(widget, QCheckBox):
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

        # combo entries keep English originals, so translate them here
        self.refresh_appearance_texts(language)

        # painted status labels are not part of the widget sweep
        # (must run after the sweep, which would otherwise re-apply the
        # captured English originals)
        self.refresh_status_texts(language)

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

    def refresh_appearance_texts(self, language=None):
        """Translate the theme / background entries of the Settings page."""

        language = language or self.current_language

        combo = getattr(self, "settings_theme_combo", None)
        if combo is not None:
            for index in range(combo.count()):
                palette = ui_theme.PALETTES.get(combo.itemData(index))
                if palette is not None:
                    combo.setItemText(
                        index, translate_text(palette.name, language)
                    )

        bg_combo = getattr(self, "settings_bg_combo", None)
        if bg_combo is not None:
            names = {
                "circuit": "Tech Circuit",
                "space": "Deep Space",
                "grid": "Classic Grid",
            }
            for index in range(bg_combo.count()):
                original = names.get(bg_combo.itemData(index), "")
                if original:
                    bg_combo.setItemText(
                        index, translate_text(original, language)
                    )

    def _settings_field_label(self, text):
        """Small grey caption above a Settings field."""

        label = QLabel(text)
        label.setStyleSheet(f"color: {self.palette.text_muted};")
        return label

    def tr(self, text):
        return translate_text(text, self.current_language)

    # -------------------------------------------------
    # painted status labels (kept as keys, translated on demand)
    # -------------------------------------------------

    def _adb_status_key(self):

        devices = self.devices.devices if getattr(self, "devices", None) else []
        authorized = [d for d in devices if d.state == "device"]
        unauthorized = [d for d in devices if d.state == "unauthorized"]

        if authorized:
            return "Status: {count} authorized device(s) connected."
        if unauthorized:
            return "Status: Authorize USB debugging on your phone."
        if not self.devices.adb_available:
            return "Status: ADB NOT FOUND"
        return "Status: No real Android device detected."

    def _adb_status_text(self, language=None):

        language = language or self.current_language
        count = len(self.devices.authorized())
        template = translate_text(self._adb_status_key(), language)
        return template.format(count=count)

    def _screen_lock_status_key(self):

        devices = self.devices.devices if getattr(self, "devices", None) else []
        authorized = [d for d in devices if d.state == "device"]
        unauthorized = [d for d in devices if d.state == "unauthorized"]

        if authorized:
            return "Status: CONNECTED"
        if unauthorized:
            return "Status: UNAUTHORIZED"
        if not self.devices.adb_available:
            return "Status: ADB NOT FOUND"
        return "Status: OFFLINE"

    def _phone_screen_status_text(self, text):

        # live preview messages are stored in English, translated here
        return translate_text(text, self.current_language)

    def refresh_status_texts(self, language=None):

        language = language or self.current_language

        if getattr(self, "adb_status_label", None) is not None:
            self.adb_status_label.setText(self._adb_status_text(language))

        if getattr(self, "screen_lock_status", None) is not None:
            self.screen_lock_status.setText(
                translate_text(self._screen_lock_status_key(), language)
            )

        if getattr(self, "phone_screen_status", None) is not None:
            text = getattr(self, "_phone_screen_status_key", "")
            if text:
                self.phone_screen_status.setText(
                    translate_text(text, language)
                )

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
        "IMEI & Network": "imei",
        "Fastboot Tools": "fastboot",
        "Unlock & FRP": "unlock",
        "Device Control": "device_manager",
        "Packages & Files": "logs",
        "Logs & Reports": "logs",
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

        # ---- appearance (full controls now that the right panel is hidden) ----
        appearance_group = QFrame()
        appearance_group.setObjectName("ToolCard")
        appearance_layout = QVBoxLayout(appearance_group)
        appearance_layout.setContentsMargins(18, 14, 18, 16)
        appearance_layout.setSpacing(8)

        appearance_title = QLabel("Appearance")
        appearance_title.setObjectName("CardTitle")
        appearance_layout.addWidget(appearance_title)

        appearance_hint = QLabel(
            "Theme, background, transparency and animations."
        )
        appearance_hint.setWordWrap(True)
        appearance_hint.setStyleSheet(f"color: {self.palette.text_muted};")
        appearance_layout.addWidget(appearance_hint)

        appearance_layout.addWidget(
            self._settings_field_label("Theme")
        )

        self.settings_theme_combo = QComboBox()
        for key in ui_theme.THEME_ORDER:
            self.settings_theme_combo.addItem(
                ui_theme.PALETTES[key].name, key
            )
        self.settings_theme_combo.setMinimumHeight(40)
        self.settings_theme_combo.setMaxVisibleItems(8)
        self.settings_theme_combo.setCurrentIndex(
            max(0, self.settings_theme_combo.findData(self.theme_key))
        )
        self.settings_theme_combo.currentIndexChanged.connect(
            lambda index: self.select_theme(
                self.settings_theme_combo.itemData(index)
            )
        )
        appearance_layout.addWidget(self.settings_theme_combo)

        appearance_layout.addWidget(
            self._settings_field_label("Background")
        )

        self.settings_bg_combo = QComboBox()
        for mode, label in (
            ("circuit", "Tech Circuit"),
            ("space", "Deep Space"),
            ("grid", "Classic Grid"),
        ):
            self.settings_bg_combo.addItem(self.tr(label), mode)
        self.settings_bg_combo.setMinimumHeight(40)
        self.settings_bg_combo.setCurrentIndex(
            max(0, self.settings_bg_combo.findData(self.background_mode))
        )
        self.settings_bg_combo.currentIndexChanged.connect(
            lambda index: self.set_background_mode(
                self.settings_bg_combo.itemData(index)
            )
        )
        appearance_layout.addWidget(self.settings_bg_combo)

        self.settings_transparency_check = QCheckBox("Panel transparency")
        self.settings_transparency_check.setChecked(self.opacity > 0.5)
        self.settings_transparency_check.toggled.connect(
            self.set_transparency
        )
        appearance_layout.addWidget(self.settings_transparency_check)

        self.settings_animations_check = QCheckBox("Interface animations")
        self.settings_animations_check.setChecked(self.animations_enabled)
        self.settings_animations_check.toggled.connect(self.set_animations)
        appearance_layout.addWidget(self.settings_animations_check)

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
        """Refresh footer chrome from the cached device registry state."""

        if self.shell is None:
            return

        footer = self.shell.footer
        footer.status.set_text(self.tr("Status: Ready"))
        footer.status.set_kind("ok")

        devices = self.devices.devices if getattr(self, "devices", None) else []
        authorized = [d for d in devices if d.state == "device"]

        if authorized:
            footer.device.set_text(
                f"{self.tr('Device:')} {authorized[0].serial}"
            )
            footer.device.set_kind("ok")
        elif devices:
            footer.device.set_text(self.tr("Device: Not Authorized"))
            footer.device.set_kind("warn")
        else:
            footer.device.set_text(self.tr("Device: Not Connected"))
            footer.device.set_kind("info")

        adb_available = (
            self.devices.adb_available
            if getattr(self, "devices", None) is not None
            else shutil.which("adb") is not None
        )
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
            + translate_text(
                "Innovation Today ... A Better Tomorrow\u2122",
                self.current_language,
            )
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
            self.tr("Only authorized devices can run ADB commands.")
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
        refresh_button.clicked.connect(self.refresh_all_devices)

        self.adb_spinner = BusySpinner(self.palette, 18)

        device_layout.addWidget(device_label)
        device_layout.addWidget(self.adb_device_combo, 1)
        device_layout.addWidget(self.adb_spinner)
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

        return page

    # =====================================================
    # ADB DEVICE SELECTION
    # =====================================================

    def get_adb_serial(self):

        if self.adb_device_combo is None:
            return None

        serial = self.selected_adb_serial()

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

        # kept for backwards compatibility: the registry owns the scan
        self.refresh_all_devices()

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

        self.run_background(
            "Device information",
            lambda: ADBTools.device_info(serial),
            lambda info: self.show_adb_result(
                "DEVICE INFORMATION", True, info
            ),
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

        self.run_background(
            f"Reboot {mode}",
            lambda: ADBTools.reboot(serial, mode),
            lambda result: self.show_adb_result(
                f"REBOOT {mode.upper()}",
                result[0],
                result[1] or "Reboot command sent.",
            ),
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

        self.run_background(
            "Install APK",
            lambda: ADBTools.install_apk(serial, apk_path),
            lambda result: self.show_adb_result(
                "INSTALL APK", result[0], result[1]
            ),
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

        def done(result):
            ok, output = result if isinstance(result, tuple) else (True, result)
            self.show_adb_result("SCREENSHOT", ok, output)
            if ok:
                QMessageBox.information(
                    self,
                    self.tr("Screenshot Saved"),
                    self.tr(
                        "Screenshot saved successfully:\n{path}"
                    ).format(path=destination)
                )

        self.run_background(
            "Screenshot",
            lambda: ADBTools.screenshot(serial, destination),
            done,
        )

    # =====================================================
    # INSTALLED APPS
    # =====================================================

    def adb_list_apps(self):

        serial = self.get_adb_serial()

        if not serial:
            return

        self.run_background(
            "Installed applications",
            lambda: ADBTools.list_apps(serial),
            lambda result: self.show_adb_result(
                "INSTALLED APPLICATIONS", result[0], result[1]
            ),
        )

    # =====================================================
    # BATTERY INFORMATION
    # =====================================================

    def adb_battery(self):

        serial = self.get_adb_serial()

        if not serial:
            return

        self.run_background(
            "Battery information",
            lambda: ADBTools.get_battery(serial),
            lambda result: self.show_adb_result(
                "BATTERY INFORMATION", result[0], result[1]
            ),
        )

    # =====================================================
    # STORAGE INFORMATION
    # =====================================================

    def adb_storage(self):

        serial = self.get_adb_serial()

        if not serial:
            return

        self.run_background(
            "Storage information",
            lambda: ADBTools.get_storage(serial),
            lambda result: self.show_adb_result(
                "STORAGE INFORMATION", result[0], result[1]
            ),
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
        refresh_button.clicked.connect(self.refresh_all_devices)
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

        return page

    def show_vendor_result(self, result, box=None):
        """Render a (ok, output) tuple from a vendor tool page."""

        if isinstance(result, tuple):
            ok, output = result
        else:
            ok, output = True, str(result)

        if box is not None:
            box.setPlainText(output)

        self.log(
            f"Vendor operation: {'SUCCESS' if ok else 'FAILED'}"
        )

    def refresh_samsung_devices(self):

        if self.samsung_device_combo is None:
            return

        fill_device_combo(
            self.samsung_device_combo,
            self.devices.devices,
            self.tr("No authorized device connected"),
        )

    def get_samsung_device(self):

        serial = self.samsung_device_combo.currentData()

        if not serial:
            device = self.devices.first_authorized()
            serial = device.serial if device else ""

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

        self.run_background(
            "Samsung device check",
            lambda: SamsungTools.check_samsung_device(serial),
            lambda result, box=self.samsung_result_box: self.show_vendor_result(result, box),
        )

    def samsung_device_information(self):

        serial = self.get_samsung_device()
        if not serial:
            return

        self.run_background(
            "Samsung device information",
            lambda: SamsungTools.device_information(serial),
            lambda result, box=self.samsung_result_box: self.show_vendor_result(result, box),
        )

    def samsung_firmware_information(self):

        serial = self.get_samsung_device()
        if not serial:
            return

        self.run_background(
            "Samsung firmware information",
            lambda: SamsungTools.firmware_information(serial),
            lambda result, box=self.samsung_result_box: self.show_vendor_result(result, box),
        )

    def samsung_connection_check(self):

        serial = self.get_samsung_device()
        if not serial:
            return

        self.run_background(
            "Samsung connection check",
            lambda: SamsungTools.check_connection(serial),
            lambda result, box=self.samsung_result_box: self.show_vendor_result(result, box),
        )
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
        refresh_button.clicked.connect(self.refresh_all_devices)
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

        return page

    def refresh_qualcomm_devices(self):

        if self.qualcomm_device_combo is None:
            return

        fill_device_combo(
            self.qualcomm_device_combo,
            self.devices.devices,
            self.tr("No authorized device connected"),
        )

    def get_qualcomm_device(self):

        serial = self.qualcomm_device_combo.currentData()

        if not serial:
            device = self.devices.first_authorized()
            serial = device.serial if device else ""

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

        self.run_background(
            "Qualcomm device check",
            lambda: QualcommTools.check_qualcomm_device(serial),
            lambda result, box=self.qualcomm_result_box: self.show_vendor_result(result, box),
        )

    def qualcomm_device_information(self):

        serial = self.get_qualcomm_device()
        if not serial:
            return

        self.run_background(
            "Qualcomm device information",
            lambda: QualcommTools.device_information(serial),
            lambda result, box=self.qualcomm_result_box: self.show_vendor_result(result, box),
        )

    def qualcomm_firmware_information(self):

        serial = self.get_qualcomm_device()
        if not serial:
            return

        self.run_background(
            "Qualcomm firmware information",
            lambda: QualcommTools.firmware_information(serial),
            lambda result, box=self.qualcomm_result_box: self.show_vendor_result(result, box),
        )

    def qualcomm_connection_check(self):

        serial = self.get_qualcomm_device()
        if not serial:
            return

        self.run_background(
            "Qualcomm connection check",
            lambda: QualcommTools.check_connection(serial),
            lambda result, box=self.qualcomm_result_box: self.show_vendor_result(result, box),
        )
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
        refresh_button.clicked.connect(self.refresh_all_devices)
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

        return page

    def refresh_mediatek_devices(self):

        if self.mediatek_device_combo is None:
            return

        fill_device_combo(
            self.mediatek_device_combo,
            self.devices.devices,
            self.tr("No authorized device connected"),
        )

    def get_mediatek_device(self):

        serial = self.mediatek_device_combo.currentData()

        if not serial:
            device = self.devices.first_authorized()
            serial = device.serial if device else ""

        if not serial:
            QMessageBox.warning(
                self,
                self.tr("No Device"),
                self.tr("Please connect and select a device.")
            )
            return None

        return serial

    def mediatek_check_device(self):

        serial = self.get_mediatek_device()
        if not serial:
            return

        self.run_background(
            "MediaTek device check",
            lambda: MediaTekTools.check_mediatek_device(serial),
            lambda result, box=self.mediatek_result_box: self.show_vendor_result(result, box),
        )

    def mediatek_device_information(self):

        serial = self.get_mediatek_device()
        if not serial:
            return

        self.run_background(
            "MediaTek device information",
            lambda: MediaTekTools.device_information(serial),
            lambda result, box=self.mediatek_result_box: self.show_vendor_result(result, box),
        )

    def mediatek_firmware_information(self):

        serial = self.get_mediatek_device()
        if not serial:
            return

        self.run_background(
            "MediaTek firmware information",
            lambda: MediaTekTools.firmware_information(serial),
            lambda result, box=self.mediatek_result_box: self.show_vendor_result(result, box),
        )

    def mediatek_connection_check(self):

        serial = self.get_mediatek_device()
        if not serial:
            return

        self.run_background(
            "MediaTek connection check",
            lambda: MediaTekTools.check_connection(serial),
            lambda result, box=self.mediatek_result_box: self.show_vendor_result(result, box),
        )


    # =====================================================
    # FIRMWARE CENTER
    # =====================================================

    def create_firmware_center_page(self):
        """Flashing centre: identify, verify and plan - never auto-flash."""

        tool = ToolPage(
            self,
            "Firmware Center",
            "Identify firmware packages, verify integrity and build a flash plan.",
            "firmware_device_combo",
        )
        tool.with_device_selector("Connected Device (for model / CSC matching)")

        self.firmware_file_path = ""
        self.firmware_path_label = QLabel("No firmware package selected")
        self.firmware_path_label.setWordWrap(True)
        self.firmware_path_label.setProperty("hint", "true")
        tool.layout.addWidget(self.firmware_path_label)

        tool.add_section(
            "PACKAGE",
            [
                ("Select Package", self.select_firmware_file),
                ("Identify", self.firmware_identify),
                ("Inspect Contents", self.firmware_inspect),
                ("Library Folder", self.firmware_scan_folder),
            ],
        )

        tool.add_section(
            "INTEGRITY",
            [
                ("SHA-256", self.firmware_calculate_sha256),
                ("MD5 (Samsung .tar.md5)", self.firmware_md5),
            ],
        )

        tool.add_section(
            "FLASH PLAN",
            [
                ("Build Plan (no flashing)", self.firmware_build_plan),
                ("Save Plan", self.firmware_save_plan),
                ("Flash With Fastboot", self.firmware_goto_fastboot),
            ],
        )

        tool.add_note(
            "AYMTECH PRO never starts a flash by itself. It identifies the "
            "package, proves the checksum, checks model + region against the "
            "connected phone, then prints the exact Odin / Heimdall / fastboot "
            "command so you stay in control.",
            "hint",
        )

        tool.with_console("Firmware analysis will appear here...")
        self.firmware_result_box = tool.result_box
        self._firmware_tool = tool
        return tool.finish()

    def firmware_show(self, result, title=None):

        if isinstance(result, tuple):
            ok, output = result
        else:
            ok, output = True, str(result)

        box = getattr(self, "_firmware_tool", None)
        if box is not None:
            box.set_output(output, title)
        elif self.firmware_result_box is not None:
            self.firmware_result_box.setPlainText(
                f"========== {title} ==========\n{output}" if title else output
            )
        self.log(f"Firmware: {'OK' if ok else 'FAILED'}")
        return ok

    def _firmware_guard(self):

        if not self.firmware_file_path:
            QMessageBox.warning(
                self, self.tr("No File"),
                self.tr("Please select a firmware file first."),
            )
            return False
        return True

    def _connected_model_region(self):
        """Model/region of the selected phone, used for mismatch checks."""

        device = self.devices.find(self.selected_serial())
        if device is None:
            return "", ""

        ok, model = ADBTools.run(
            ["-s", device.serial, "shell", "getprop", "ro.product.model"]
        )
        ok2, csc = ADBTools.run(
            ["-s", device.serial, "shell", "getprop", "ro.csc.sales_code"]
        )
        return (
            model.strip() if ok else "",
            csc.strip() if ok2 and csc.strip() else "",
        )

    def selected_serial(self):

        combo = getattr(self, "firmware_device_combo", None)
        if combo is not None and combo.currentData():
            return combo.currentData()

        device = self.devices.first_authorized()
        return device.serial if device else ""

    def select_firmware_file(self):

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select Firmware File"),
            "",
            self.tr("Firmware Files") + " (*.zip *.img *.bin *.tar *.md5 *.mbn "
            "*.xml *.ofp *.kdz *.ftf *.ipsw *.ops *.pac *.br *.dat "
            "*.lz4 *.tgz);;All Files (*)",
        )

        if not file_path:
            return

        self.firmware_file_path = file_path
        self.firmware_path_label.setText(file_path)
        self.firmware_result_box.setPlainText(
            f"Package selected:\n{file_path}\n\n"
            "Next: 'Identify' to read the model/region, then 'SHA-256' or "
            "'MD5' to prove the file."
        )

    def firmware_identify(self):

        if not self._firmware_guard():
            return

        self.run_background(
            "Identify firmware",
            lambda: FirmwareCenter.identify(self.firmware_file_path),
            lambda result: self.firmware_show(result),
        )

    def firmware_inspect(self):

        if not self._firmware_guard():
            return

        self.run_background(
            "Inspect archive",
            lambda: FirmwareCenter.inspect_archive(self.firmware_file_path),
            lambda result: self.firmware_show(result, "PACKAGE CONTENTS"),
        )

    def firmware_calculate_sha256(self):

        if not self._firmware_guard():
            return

        self.run_background(
            "SHA-256",
            lambda: FirmwareCenter.hash_file(self.firmware_file_path, "sha256"),
            lambda result: self.firmware_show(result, "SHA-256"),
        )

    def firmware_md5(self):

        if not self._firmware_guard():
            return

        self.run_background(
            "MD5",
            lambda: FirmwareCenter.md5_sidecar(self.firmware_file_path),
            lambda result: self.firmware_show(result, "MD5"),
        )

    def firmware_build_plan(self):

        if not self._firmware_guard():
            return

        model, region = self._connected_model_region()

        def done(result):
            ok, output = result
            if not model:
                output += (
                    "\n\nNo phone is connected, so the model/region could not "
                    "be checked. Connect the device before flashing."
                )
            self.firmware_show((ok, output), "FLASH PLAN")

        self.run_background(
            "Build flash plan",
            lambda: FirmwareCenter.build_plan(
                self.firmware_file_path, model, region
            ),
            done,
        )

    def firmware_save_plan(self):

        text = self.firmware_result_box.toPlainText() if self.firmware_result_box else ""
        if not text.strip():
            QMessageBox.warning(
                self, self.tr("Nothing To Save"),
                "Build a plan first, then save it.",
            )
            return

        self.run_background(
            "Save flash plan",
            lambda: FirmwareCenter.export_plan(text),
            lambda result: self._plan_saved(result),
        )

    def _plan_saved(self, result):

        ok, output = result
        QMessageBox.information(
            self, self.tr("Report Saved"),
            f"Flash plan saved to:\n{output}" if ok else str(output),
        )
        self.log(f"Flash plan saved: {output if ok else 'failed'}")

    def firmware_goto_fastboot(self):

        self.navigate("Fastboot Tools")
        self.log("Opening Fastboot Tools for the selected image.")

    def firmware_scan_folder(self):

        folder = QFileDialog.getExistingDirectory(
            self, self.tr("Select Firmware Folder")
        )
        if not folder:
            return

        self.run_background(
            "Firmware library",
            lambda: FirmwareCenter.library(folder),
            lambda result: self.firmware_show(result, "FIRMWARE LIBRARY"),
        )

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

        status_row = QHBoxLayout()
        self.screen_lock_status = QLabel("Status: NOT CONNECTED")
        self.set_status(self.screen_lock_status, "danger")
        self.screen_lock_spinner = BusySpinner(self.palette, 18)
        status_row.addWidget(self.screen_lock_status)
        status_row.addWidget(self.screen_lock_spinner)
        status_row.addStretch()
        layout.addLayout(status_row)

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

    # -------------------------------------------------
    # screen lock helpers
    # -------------------------------------------------

    def _screen_lock_guard(self):
        """Return True when an authorized device is available."""
        device = self.devices.first_authorized()
        if device is not None:
            return True

        if not self.devices.adb_available:
            status, kind, message = (
                "Status: ADB NOT FOUND",
                "danger",
                "ADB WAS NOT FOUND\n\n"
                "Install Android Platform Tools and add ADB to PATH.",
            )
        elif any(d.state == "unauthorized" for d in self.devices.devices):
            status, kind, message = (
                "Status: UNAUTHORIZED",
                "warn",
                "USB DEBUGGING NOT AUTHORIZED\n\n"
                "Unlock the phone and accept the debugging prompt.",
            )
        else:
            status, kind, message = (
                "Status: NOT CONNECTED",
                "danger",
                "NO ANDROID DEVICE DETECTED\n\n"
                "Connect an Android phone using USB.\n"
                "Enable USB debugging if available.",
            )

        self.screen_lock_status.setText(self.tr(status))
        self.set_status(self.screen_lock_status, kind)
        self.screen_lock_result.setPlainText(message)
        return False

    def _set_screen_lock_busy(self, busy):
        if getattr(self, "screen_lock_spinner", None) is not None:
            self.screen_lock_spinner.set_active(busy)

    def _screen_lock_show(self, text, ok=True):
        self._set_screen_lock_busy(False)
        self.screen_lock_result.setPlainText(text)
        self.log(
            "Screen lock diagnostics completed."
            if ok else "Screen lock diagnostics failed."
        )

    # -------------------------------------------------
    # screen lock actions
    # -------------------------------------------------

    def screen_lock_detect_device(self):

        if not self._screen_lock_guard():
            return

        self.screen_lock_status.setText(self.tr("Status: SCANNING..."))
        self.set_status(self.screen_lock_status, "info")
        self._set_screen_lock_busy(True)

        devices = self.devices.devices
        self.run_background(
            "Screen lock device detection",
            lambda: self._screen_lock_detect_worker(devices),
            self._screen_lock_detect_done,
        )

    def _screen_lock_detect_worker(self, devices):

        results = ["SMART ANDROID DEVICE DETECTION\n"]
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

        for device in devices:

            results.append("=" * 45)
            results.append(f"Serial: {device.serial}")
            results.append(f"ADB Status: {device.state.upper()}")

            if not device.authorized:
                results.append("Device is not authorized for ADB diagnostics.")
                results.append("")
                continue

            values = {}
            for name, prop in properties.items():
                prop_ok, value = ADBTools.run(
                    ["-s", device.serial, "shell", "getprop", prop]
                )
                values[name] = (
                    value.strip() if prop_ok and value.strip() else "Unavailable"
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

        return "\n".join(results)

    def _screen_lock_detect_done(self, text):

        authorized = self.devices.authorized()
        unauthorized = [
            d for d in self.devices.devices if d.state == "unauthorized"
        ]

        if authorized:
            self.screen_lock_status.setText(self.tr("Status: CONNECTED"))
            self.set_status(self.screen_lock_status, "ok")
        elif unauthorized:
            self.screen_lock_status.setText(self.tr("Status: UNAUTHORIZED"))
            self.set_status(self.screen_lock_status, "warn")
        else:
            self.screen_lock_status.setText(self.tr("Status: OFFLINE"))
            self.set_status(self.screen_lock_status, "danger")

        self._screen_lock_show(text)

    def screen_lock_security_diagnostics(self):

        if not self._screen_lock_guard():
            return

        serials = [d.serial for d in self.devices.authorized()]
        self._set_screen_lock_busy(True)
        self.run_background(
            "Android security diagnostics",
            lambda: self._screen_lock_security_worker(serials),
            self._screen_lock_show,
        )

    def _screen_lock_security_worker(self, serials):

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

        for serial in serials:
            results.append("=" * 45)
            results.append(f"Device Serial: {serial}")

            for name, prop in properties.items():
                prop_ok, value = ADBTools.run(
                    ["-s", serial, "shell", "getprop", prop]
                )
                value = value.strip() if prop_ok else ""
                results.append(
                    f"{name}: {value if value else 'Unavailable / Not exposed'}"
                )

            root_ok, root_output = ADBTools.run(
                ["-s", serial, "shell", "su", "-c", "id"], timeout=10
            )
            root_status = (
                "Root access available"
                if root_ok and "uid=0" in root_output
                else "Root access not confirmed"
            )
            results.append(f"Root Indicator: {root_status}")
            results.append(
                "\nNOTES:\n"
                "These values are read-only diagnostic indicators.\n"
                "Unavailable properties do not prove that a device "
                "is locked or secure.\n"
                "Root detection is not conclusive on every Android device."
            )

        return "\n".join(results)

    def screen_lock_information(self):

        if not self._screen_lock_guard():
            return

        serials = [d.serial for d in self.devices.authorized()]
        self._set_screen_lock_busy(True)
        self.run_background(
            "Android lock information",
            lambda: self._screen_lock_info_worker(serials),
            self._screen_lock_show,
        )

    def _screen_lock_info_worker(self, serials):

        results = ["ANDROID LOCK INFORMATION\n"]

        for serial in serials:
            results.append("=" * 45)
            results.append(f"Device: {serial}")

            lock_ok, lock_output = ADBTools.run(
                ["-s", serial, "shell", "dumpsys", "window"], timeout=20
            )
            lock_state = "UNKNOWN"
            if lock_ok:
                text = lock_output.lower()
                if "mshowinglockscreen=true" in text:
                    lock_state = "LOCKED (reported by WindowManager)"
                elif "mshowinglockscreen=false" in text:
                    lock_state = "NOT SHOWING LOCK SCREEN"
            results.append(f"Screen Lock State: {lock_state}")

            keyguard_ok, keyguard_output = ADBTools.run(
                ["-s", serial, "shell", "dumpsys", "trust"], timeout=20
            )
            if keyguard_ok:
                trust_text = keyguard_output.lower()
                if "device locked" in trust_text:
                    results.append("Trust Service: Device reports locked")
                elif "device unlocked" in trust_text:
                    results.append("Trust Service: Device reports unlocked")
                else:
                    results.append("Trust Service: State not confirmed")
            else:
                results.append("Trust Service: Information unavailable")

            results.append(
                "\nIMPORTANT:\n"
                "ADB access does not prove that the screen is unlocked.\n"
                "WindowManager output may vary across Android versions.\n"
                "UNKNOWN means the lock state could not be verified."
            )

        return "\n".join(results)

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
        refresh_button.clicked.connect(self.refresh_all_devices)

        self.android_spinner = BusySpinner(self.palette, 18)

        device_row = QHBoxLayout()
        device_row.addWidget(self.android_device_combo, 1)
        device_row.addWidget(self.android_spinner)
        device_row.addWidget(refresh_button)

        layout.addWidget(QLabel("Connected Android Device"))
        layout.addLayout(device_row)

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

        return page

    # =====================================================
    # ANDROID DIAGNOSTICS ACTIONS
    # =====================================================

    def refresh_android_devices(self):

        if self.android_device_combo is None:
            return

        fill_device_combo(
            self.android_device_combo,
            self.devices.devices,
            self.tr("No authorized device connected"),
        )

        if self.android_device_combo.count() == 0:
            self.log("No authorized Android devices found.")

    def show_android_result(self, result):

        if isinstance(result, tuple):
            ok, output = result
        else:
            ok, output = True, str(result)

        if self.android_result_box is not None:
            self.android_result_box.setPlainText(output)

        if not ok:
            self.log("Android operation failed.")

    def get_android_device(self):

        serial = self.android_device_combo.currentData()

        if not serial:
            device = self.devices.first_authorized()
            serial = device.serial if device else ""

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

        self.run_background(
            "Full diagnostic",
            lambda: AndroidTools.full_diagnostic(serial),
            self.show_android_result,
        )

    def android_device_information(self):

        serial = self.get_android_device()
        if not serial:
            return

        self.run_background(
            "Device information",
            lambda: ADBTools.device_info(serial),
            self.show_android_result,
        )

    def android_battery_health(self):

        serial = self.get_android_device()
        if not serial:
            return

        self.run_background(
            "Battery health",
            lambda: AndroidTools.battery_health(serial),
            self.show_android_result,
        )

    def android_storage_analysis(self):

        serial = self.get_android_device()
        if not serial:
            return

        self.run_background(
            "Storage analysis",
            lambda: AndroidTools.storage_analysis(serial),
            self.show_android_result,
        )

    def android_installed_apps(self):

        serial = self.get_android_device()
        if not serial:
            return

        self.run_background(
            "Installed applications",
            lambda: AndroidTools.installed_apps(serial),
            self.show_android_result,
        )
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

        # pick up a phone plugged in while another page was open
        if title in (
            "Device Manager",
            "ADB Tools",
            "Fastboot Tools",
            "Unlock & FRP",
            "Device Control",
            "Packages & Files",
            "Logs & Reports",
            "IMEI & Network",
            "Live Phone Screen",
            "Android Tools",
            "Screen Lock Service",
            "Samsung Tools",
            "Qualcomm Tools",
            "MediaTek Tools",
        ):
            self.devices.request_scan()

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

        def worker():
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

            return "\n\n".join(results)

        def done(text):
            QMessageBox.information(
                self,
                self.tr("Tool Status"),
                text
            )

        self.run_background("Tool check", worker, done)

        self.log("Checked ADB and Fastboot.")

    # =====================================================
    # IMEI & NETWORK
    # =====================================================

    def create_imei_page(self):

        tool = ToolPage(
            self,
            "IMEI & Network",
            "Read the radio identity, prove the baseband and diagnose the network.",
            "imei_device_combo",
        )
        tool.with_device_selector("Connected Device")

        tool.add_note(
            "ADB only reads what the modem exposes. Writing an IMEI needs a "
            "signed vendor tool or a hardware programmer, is illegal in most "
            "countries, and a failed write destroys the phone's identity - so "
            "this page never writes one.",
            "hint",
        )

        tool.add_section(
            "IDENTITY",
            [
                ("IMEI Report", self.imei_report),
                ("Quick Identifiers", self.imei_quick),
            ],
        )

        tool.add_section(
            "RADIO / NETWORK",
            [
                ("Network Status", self.imei_network),
                ("Airplane Mode Off", lambda: self.imei_airplane(False)),
                ("Reset Network Settings", self.imei_reset_network),
            ],
        )

        tool.add_section(
            "SERVICE PATHS",
            [
                ("Baseband Repair Guide", self.imei_guide),
                ("Save Report", self.imei_save),
            ],
        )

        tool.with_console("IMEI and network results will appear here...")
        self.imei_result_box = tool.result_box
        self._imei_tool = tool
        return tool.finish()

    def imei_serial(self):

        combo = getattr(self, "imei_device_combo", None)
        if combo is not None and combo.currentData():
            return combo.currentData()

        device = self.devices.first_authorized()
        if device is None:
            QMessageBox.warning(
                self, self.tr("No Device"),
                self.tr("Please connect and select an Android device."),
            )
            return None
        return device.serial

    def imei_show(self, result, title):

        if isinstance(result, tuple):
            ok, output = result
        else:
            ok, output = True, str(result)

        if getattr(self, "_imei_tool", None) is not None:
            self._imei_tool.set_output(output, title)
        elif self.imei_result_box is not None:
            self.imei_result_box.setPlainText(
                f"========== {title} ==========\n{output}"
            )
        self.log(f"IMEI: {title} -> {'OK' if ok else 'FAILED'}")
        return ok

    def _imei_action(self, title, worker):

        serial = self.imei_serial()
        if not serial:
            return
        self.run_background(
            f"IMEI {title}",
            lambda: worker(serial),
            lambda result: self.imei_show(result, title),
        )

    def imei_report(self):

        self._imei_action("IDENTITY REPORT", NetworkTools.identity_report)

    def imei_quick(self):

        self._imei_action("QUICK IDENTIFIERS", self._imei_quick_worker)

    def _imei_quick_worker(self, serial):

        values = NetworkTools.identifiers(serial)
        lines = []
        for label, value in values.items():
            if not value:
                continue
            lines.append(f"{label:22} {value}")
        if not lines:
            return True, (
                "The firmware did not expose any identity property.\n"
                "Run 'IMEI Report' for the full analysis."
            )
        return True, "\n".join(lines)

    def imei_network(self):

        self._imei_action("NETWORK STATUS", NetworkTools.network_status)

    def imei_airplane(self, enabled):

        self._imei_action(
            "AIRPLANE MODE",
            lambda serial: DeviceControl.airplane_mode(serial, enabled),
        )

    def imei_reset_network(self):

        serial = self.imei_serial()
        if not serial:
            return

        if not self._confirm(
            "Reset network settings",
            "Reset Wi-Fi, mobile data and Bluetooth settings on the phone?\n\n"
            "Saved networks and pairings are lost; the IMEI is not touched.",
        ):
            return

        self.run_background(
            "Reset network settings",
            lambda: ADBTools.run(
                ["-s", serial, "shell", "svc", "data", "enable"], timeout=20
            ),
            lambda result: self.imei_show(result, "NETWORK RESET"),
        )

    def imei_guide(self):

        self.imei_show(NetworkTools.service_guide(), "BASEBAND / IMEI")

    def imei_save(self):

        text = self.imei_result_box.toPlainText() if self.imei_result_box else ""
        if not text.strip():
            QMessageBox.warning(
                self, self.tr("Nothing To Save"),
                "Run the IMEI report first, then save it.",
            )
            return

        self.run_background(
            "Save IMEI report",
            lambda: NetworkTools.save_report(text),
            lambda result: self._plan_saved(result),
        )

    # =====================================================
    # FASTBOOT TOOLS
    # =====================================================

    def create_fastboot_page(self):

        tool = ToolPage(
            self,
            "Fastboot Tools",
            "Bootloader level servicing: variables, modes and flashing.",
            "fastboot_device_combo",
        )
        tool.with_device_selector(
            "Connected Device (fastboot units are addressed by serial)"
        )

        tool.add_section(
            "BOOTLOADER INFORMATION",
            [
                ("Detect Devices", self.fastboot_detect),
                ("All Variables", self.fastboot_variables),
                ("Lock State", self.fastboot_lock_state),
                ("Unlock Guide", self.fastboot_unlock_guide),
            ],
        )

        tool.add_section(
            "RESTART MODES",
            [
                ("Boot to Bootloader", lambda: self.fastboot_reboot("bootloader")),
                ("Boot to Recovery", lambda: self.fastboot_reboot("recovery")),
                ("Boot to System", lambda: self.fastboot_reboot("system")),
                ("Continue (from fastbootd)", lambda: self.fastboot_reboot("fastbootd")),
            ],
        )

        self.fastboot_partition = QLineEdit()
        self.fastboot_partition.setMinimumWidth(220)
        self.fastboot_partition.setPlaceholderText(
            "Partition name (boot, recovery, vbmeta, super...)"
        )

        self.fastboot_image = QLineEdit()
        self.fastboot_image.setMinimumWidth(220)
        self.fastboot_image.setPlaceholderText("Image file (.img)")
        browse = QPushButton("Browse")
        browse.clicked.connect(self.fastboot_pick_image)

        tool.add_section("FLASHING (DESTRUCTIVE - WRITES THE DEVICE)")
        tool.add_row([labelled("Partition", self.fastboot_partition),
                      labelled("Image", self.fastboot_image),
                      browse])

        tool.add_row([
            self._danger_button("Flash Partition", self.fastboot_flash),
            self._danger_button("Erase Partition", self.fastboot_erase),
            self._danger_button("Format Partition", self.fastboot_format),
        ])

        tool.add_note(
            "Flashing writes directly to a partition. A wrong image or a wrong "
            "partition name hard-bricks the phone and voids the warranty. "
            "Verify the model, the slot (a/b) and the file hash first.",
            "hint",
        )

        tool.add_section(
            "SERVICE ENVIRONMENT",
            [
                ("Installed Service Tools", self.show_service_environment),
                ("Samsung Download Mode Guide", self.show_samsung_guide),
            ],
        )

        tool.with_console("Fastboot output will appear here...")
        self.fastboot_result_box = tool.result_box
        return tool.finish()

    def _danger_button(self, text, slot):

        button = QPushButton(text)
        button.setObjectName("Danger")
        button.clicked.connect(slot)
        return button

    def fastboot_serial(self):
        """Selected fastboot unit, or ``None`` for the single attached one."""

        combo = getattr(self, "fastboot_device_combo", None)
        if combo is not None and combo.currentData():
            return combo.currentData()
        return None

    def fastboot_show(self, result, title=None):

        if isinstance(result, tuple):
            ok, output = result
        else:
            ok, output = True, str(result)

        text = output if title is None else f"========== {title} ==========\n{output}"

        if self.fastboot_result_box is not None:
            self.fastboot_result_box.setPlainText(text)

        self.log(f"Fastboot: {'OK' if ok else 'FAILED'}" + (f" ({title})" if title else ""))
        return ok

    def fastboot_detect(self):

        self.run_background(
            "Fastboot devices",
            FastbootTools.devices,
            lambda result: self.fastboot_show(result, "FASTBOOT DEVICES"),
        )

    def fastboot_variables(self):

        serial = self.fastboot_serial()
        self.run_background(
            "Fastboot variables",
            lambda: FastbootTools.variables(serial),
            lambda result: self.fastboot_show(result, "DEVICE VARIABLES"),
        )

    def fastboot_lock_state(self):

        serial = self.fastboot_serial()
        self.run_background(
            "Fastboot lock state",
            lambda: self._fastboot_lock_worker(serial),
            lambda result: self.fastboot_show(result, "BOOTLOADER LOCK"),
        )

    def _fastboot_lock_worker(self, serial):

        known, unlocked, raw = FastbootTools.is_unlocked(serial)
        if not known:
            return True, (
                f"{raw}\n\n"
                "The device is not in fastboot mode, or it does not expose the\n"
                "lock variable (Samsung, Huawei and some vendor builds do not)."
            )

        verdict = "UNLOCKED" if unlocked else "LOCKED"
        advice = (
            "An unlocked bootloader allows flashing custom images, and means the\n"
            "phone has already been modified (data was wiped when it happened)."
            if unlocked else
            "The bootloader is locked: only signed, official firmware can be\n"
            "written. That is the normal state for a healthy retail phone."
        )
        return True, f"State: {verdict}\n\n{advice}\n\nRaw response:\n{raw}"

    def fastboot_reboot(self, mode):

        serial = self.fastboot_serial()
        label = mode.capitalize()
        if not self._confirm(
            "Restart device",
            f"Restart the device into {label} mode?\n\n"
            "The phone will leave fastboot and may show a black screen for a "
            "few seconds.",
        ):
            return

        self.run_background(
            f"Fastboot reboot {mode}",
            lambda: FastbootTools.reboot(mode, serial),
            lambda result: self.fastboot_show(result, f"REBOOT {label.upper()}"),
        )

    def fastboot_pick_image(self):

        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Select image file"), "", "Images (*.img *.bin);;All Files (*)"
        )
        if path:
            self.fastboot_image.setText(path)

    def fastboot_flash(self):

        partition = self.fastboot_partition.text().strip()
        image = self.fastboot_image.text().strip()

        if not partition or not image:
            QMessageBox.warning(
                self, self.tr("Missing Information"),
                "Choose a partition name and an image file first.",
            )
            return

        if not self._confirm_typed(
            "FLASH",
            f"You are about to write:\n\n{image}\n\ninto partition: {partition}\n\n"
            "A wrong file, model or slot bricks the phone. This cannot be undone.",
        ):
            return

        serial = self.fastboot_serial()
        self.run_background(
            f"Flash {partition}",
            lambda: FastbootTools.flash(partition, image, serial),
            lambda result: self.fastboot_show(result, f"FLASH {partition.upper()}"),
        )

    def fastboot_erase(self):

        partition = self.fastboot_partition.text().strip()
        if not partition:
            QMessageBox.warning(
                self, self.tr("Missing Information"),
                "Enter the partition to erase.",
            )
            return

        if not self._confirm_typed(
            "ERASE",
            f"Erase partition '{partition}'?\n\n"
            "Erasing a critical partition (boot, vbmeta, modem, frp) can make the "
            "phone unbootable or permanently locked.",
        ):
            return

        serial = self.fastboot_serial()
        self.run_background(
            f"Erase {partition}",
            lambda: FastbootTools.erase(partition, serial),
            lambda result: self.fastboot_show(result, f"ERASE {partition.upper()}"),
        )

    def fastboot_format(self):

        partition = self.fastboot_partition.text().strip() or "userdata"
        if not self._confirm_typed(
            "FORMAT",
            f"Format partition '{partition}'?\n\n"
            "Formatting userdata erases every file, photo and account on the phone.",
        ):
            return

        serial = self.fastboot_serial()
        self.run_background(
            f"Format {partition}",
            lambda: FastbootTools.format_partition(partition, serial),
            lambda result: self.fastboot_show(result, f"FORMAT {partition.upper()}"),
        )

    def fastboot_unlock_guide(self):

        self.fastboot_show(FastbootTools.device_guide(), "BOOTLOADER UNLOCK")

    # =====================================================
    # UNLOCK / FRP
    # =====================================================

    def create_unlock_page(self):

        tool = ToolPage(
            self,
            "Unlock & FRP",
            "Lock state, account protection and the supported service paths.",
            "unlock_device_combo",
        )
        tool.with_device_selector("Connected Device")

        tool.add_note(
            "This page reports what the phone's own firmware says and runs only "
            "the commands Android supports. It never bypasses a lock: modern "
            "devices with FBE encryption and verified boot cannot be unlocked "
            "from ADB.",
            "hint",
        )

        tool.add_section(
            "ANALYSIS",
            [
                ("Full Lock Report", self.unlock_full_report),
                ("FRP / Account State", self.unlock_frp_status),
                ("Device Admins & MDM", self.unlock_device_admins),
                ("Bootloader Status", self.unlock_bootloader),
            ],
        )

        tool.add_section(
            "SUPPORTED OPERATIONS",
            [
                ("Remove Swipe Lock", self.unlock_remove_swipe),
                ("Clear Known PIN", self.unlock_clear_pin),
            ],
        )

        self.unlock_pin = QLineEdit()
        self.unlock_pin.setPlaceholderText("New PIN (4-16 digits)")
        self.unlock_pin.setEchoMode(QLineEdit.Password)
        tool.add_row([
            labelled("Set a temporary PIN", self.unlock_pin),
            QPushButton("Set PIN", clicked=self.unlock_set_pin),
        ])

        tool.add_section(
            "OFFICIAL RECOVERY PATHS",
            [
                ("FRP Removal Explained", self.unlock_frp_explained),
                ("Samsung Service Guide", self.show_samsung_guide),
                ("Knox Note", self.unlock_knox_note),
            ],
        )

        tool.with_console("Lock analysis will appear here...")
        self.unlock_result_box = tool.result_box

        export = QPushButton("Save Report to File")
        export.clicked.connect(lambda: self.export_report(self.unlock_result_box, "unlock"))
        tool.layout.addWidget(export)
        return tool.finish()

    def unlock_serial(self):

        combo = getattr(self, "unlock_device_combo", None)
        if combo is not None and combo.currentData():
            return combo.currentData()

        device = self.devices.first_authorized()
        if device is None:
            QMessageBox.warning(
                self, self.tr("No Device"),
                self.tr("Please connect and select an Android device."),
            )
            return None
        return device.serial

    def unlock_show(self, result, title=None):

        if isinstance(result, tuple):
            ok, output = result
        else:
            ok, output = True, str(result)

        text = f"========== {title} ==========\n{output}" if title else output
        if self.unlock_result_box is not None:
            self.unlock_result_box.setPlainText(text)
        self.log(f"Unlock service: {'OK' if ok else 'FAILED'}")
        return ok

    def unlock_full_report(self):

        serial = self.unlock_serial()
        if not serial:
            return

        self.run_background(
            "Lock report",
            lambda: Diagnostics.security_report(serial),
            lambda result: self.unlock_show(result, "LOCK REPORT"),
        )

    def unlock_frp_status(self):

        serial = self.unlock_serial()
        if not serial:
            return

        self.run_background(
            "FRP status",
            lambda: UnlockTools.frp_status(serial),
            lambda result: self.unlock_show(result, "FRP / ACCOUNT"),
        )

    def unlock_device_admins(self):

        serial = self.unlock_serial()
        if not serial:
            return

        self.run_background(
            "Device admins",
            lambda: UnlockTools.device_admins(serial),
            lambda result: self.unlock_show(result, "DEVICE ADMINS"),
        )

    def unlock_bootloader(self):

        serial = self.unlock_serial()
        if not serial:
            return

        self.run_background(
            "Bootloader status",
            lambda: self._bootloader_worker(serial),
            lambda result: self.unlock_show(result, "BOOTLOADER"),
        )

    def _bootloader_worker(self, serial):

        props = Diagnostics.read_props(
            serial,
            {
                "Bootloader locked": "ro.boot.flash.locked",
                "Verified boot": "ro.boot.verifiedbootstate",
                "Warranty bit": "ro.boot.warranty_bit",
                "vbmeta state": "ro.boot.vbmeta.device_state",
            },
        )
        state = Diagnostics.bootloader_state(props)
        lines = [
            f"Bootloader      : {state}",
            f"Verified boot   : {props.get('Verified boot') or 'not reported'}",
            f"vbmeta state    : {props.get('vbmeta state') or 'not reported'}",
            f"Knox warranty   : {Diagnostics.knox_state(props)}",
            "",
        ]
        if "UNLOCKED" in state or "UNVERIFIED" in state:
            lines.append(
                "The device has been modified. Expect SafetyNet/Play Integrity\n"
                "failures and possible app incompatibilities."
            )
        else:
            lines.append(
                "Stock, locked firmware. Unlocking would wipe all data and void\n"
                "the warranty; see 'Unlock Guide' on the Fastboot page."
            )
        return True, "\n".join(lines)

    def unlock_remove_swipe(self):

        serial = self.unlock_serial()
        if not serial:
            return

        if not self._confirm(
            "Remove swipe lock",
            "Disable the swipe (non-secure) lock screen?\n\n"
            "A PIN, pattern or password lock is not affected.",
        ):
            return

        self.run_background(
            "Remove swipe lock",
            lambda: UnlockTools.remove_swipe_lock(serial),
            lambda result: self.unlock_show(result, "SWIPE LOCK"),
        )

    def unlock_clear_pin(self):

        serial = self.unlock_serial()
        if not serial:
            return

        if not self._confirm_typed(
            "CLEAR",
            "Clear the screen lock?\n\n"
            "This only works on an already-unlocked phone whose ADB session is "
            "authorised. It does not remove FRP and does not bypass a lock you "
            "cannot open.",
        ):
            return

        self.run_background(
            "Clear screen lock",
            lambda: UnlockTools.clear_known_pin(serial),
            lambda result: self.unlock_show(result, "SCREEN LOCK"),
        )

    def unlock_set_pin(self):

        serial = self.unlock_serial()
        if not serial:
            return

        pin = self.unlock_pin.text().strip()
        self.run_background(
            "Set PIN",
            lambda: UnlockTools.set_pin(serial, pin),
            lambda result: self.unlock_show(result, "SET PIN"),
        )

    def unlock_frp_explained(self):

        self.unlock_show(UnlockTools.frp_explanation(), "FRP")

    def unlock_knox_note(self):

        self.unlock_show(UnlockTools.knox_note(), "KNOX")

    # =====================================================
    # DEVICE CONTROL
    # =====================================================

    def create_device_control_page(self):

        tool = ToolPage(
            self,
            "Device Control",
            "Drive the phone remotely: keys, text, network and system toggles.",
            "control_device_combo",
        )
        tool.with_device_selector("Connected Device")

        tool.add_section(
            "NAVIGATION",
            [
                ("Wake Screen", lambda: self.control_key("KEYCODE_WAKEUP")),
                ("Home", lambda: self.control_key("KEYCODE_HOME")),
                ("Back", lambda: self.control_key("KEYCODE_BACK")),
                ("Recents", lambda: self.control_key("KEYCODE_APP_SWITCH")),
                ("Power", lambda: self.control_key("KEYCODE_POWER")),
                ("Volume Up", lambda: self.control_key("KEYCODE_VOLUME_UP")),
                ("Volume Down", lambda: self.control_key("KEYCODE_VOLUME_DOWN")),
            ],
        )

        self.control_text = QLineEdit()
        self.control_text.setMinimumWidth(220)
        self.control_text.setPlaceholderText("Text to type on the phone")
        tool.add_row([
            labelled("Type text", self.control_text),
            QPushButton("Send Text", clicked=self.control_send_text),
        ])

        self.control_keyname = QLineEdit()
        self.control_keyname.setMinimumWidth(220)
        self.control_keyname.setPlaceholderText("Custom keycode (KEYCODE_ENTER, 26, ...)")
        tool.add_row([
            labelled("Custom key", self.control_keyname),
            QPushButton("Send Key", clicked=self.control_send_custom_key),
        ])

        tool.add_section(
            "NETWORK & SYSTEM",
            [
                ("Wi-Fi On", lambda: self.control_wifi(True)),
                ("Wi-Fi Off", lambda: self.control_wifi(False)),
                ("Data On", lambda: self.control_data(True)),
                ("Data Off", lambda: self.control_data(False)),
                ("Airplane On", lambda: self.control_airplane(True)),
                ("Airplane Off", lambda: self.control_airplane(False)),
                ("Stay Awake On", lambda: self.control_stay_awake(True)),
                ("Stay Awake Off", lambda: self.control_stay_awake(False)),
            ],
        )

        tool.add_section(
            "QUICK ACTIONS",
            [
                ("Open Settings", lambda: self.control_open_settings("settings")),
                ("Developer Options", lambda: self.control_open_settings("application_development_settings")),
                ("Battery Saver Settings", lambda: self.control_open_settings("battery_saver_settings")),
                ("Wi-Fi Address", self.control_ip),
                ("Screen Size", self.control_screen_size),
                ("Fast Animations", lambda: self.control_animations("0.5")),
                ("Restore Animations", lambda: self.control_animations("1.0")),
            ],
        )

        tool.add_section(
            "ADB CONNECTION",
            [
                ("Restart ADB Server", self.control_restart_adb),
                ("Pair over Wi-Fi", self.control_wireless),
            ],
        )

        self.control_host = QLineEdit()
        self.control_host.setPlaceholderText("Phone IP address")
        tool.add_row([
            labelled("Wireless debugging address", self.control_host),
            QPushButton("Connect", clicked=self.control_connect_wireless),
        ])

        tool.with_console("Command results will appear here...")
        self.control_result_box = tool.result_box
        return tool.finish()

    def control_serial(self):

        combo = getattr(self, "control_device_combo", None)
        if combo is not None and combo.currentData():
            return combo.currentData()

        device = self.devices.first_authorized()
        if device is None:
            QMessageBox.warning(
                self, self.tr("No Device"),
                self.tr("Please connect and select an Android device."),
            )
            return None
        return device.serial

    def control_show(self, result, title):

        if isinstance(result, tuple):
            ok, output = result
        else:
            ok, output = True, str(result)

        if self.control_result_box is not None:
            self.control_result_box.setPlainText(
                f"========== {title} ==========\n{output}"
            )
        self.log(f"Device control: {title} -> {'OK' if ok else 'FAILED'}")
        return ok

    def _control_action(self, title, worker):

        serial = self.control_serial()
        if not serial:
            return
        self.run_background(
            title,
            lambda: worker(serial),
            lambda result: self.control_show(result, title),
        )

    def control_key(self, keycode):

        self._control_action(
            f"Key {keycode}", lambda serial: DeviceControl.key(serial, keycode)
        )

    def control_send_text(self):

        text = self.control_text.text()
        if not text.strip():
            return
        self._control_action(
            "Type text", lambda serial: DeviceControl.text(serial, text)
        )

    def control_send_custom_key(self):

        code = self.control_keyname.text().strip()
        if not code:
            return
        self.control_key(code)

    def control_wifi(self, enabled):
        self._control_action(
            f"Wi-Fi {'on' if enabled else 'off'}",
            lambda serial: DeviceControl.wifi(serial, enabled),
        )

    def control_data(self, enabled):
        self._control_action(
            f"Data {'on' if enabled else 'off'}",
            lambda serial: DeviceControl.mobile_data(serial, enabled),
        )

    def control_airplane(self, enabled):
        self._control_action(
            f"Airplane {'on' if enabled else 'off'}",
            lambda serial: DeviceControl.airplane_mode(serial, enabled),
        )

    def control_stay_awake(self, enabled):
        self._control_action(
            "Stay awake", lambda serial: DeviceControl.stay_awake(serial, enabled)
        )

    def control_open_settings(self, page):
        self._control_action(
            "Open settings", lambda serial: DeviceControl.open_settings(serial, page)
        )

    def control_ip(self):
        self._control_action(
            "Wi-Fi address", lambda serial: DeviceControl.ip_address(serial)
        )

    def control_screen_size(self):
        self._control_action(
            "Screen size", lambda serial: DeviceControl.screen_size(serial)
        )

    def control_animations(self, scale):
        self._control_action(
            f"Animation scale {scale}",
            lambda serial: DeviceControl.animation_scale(serial, scale),
        )

    def control_restart_adb(self):

        self.run_background(
            "Restart ADB server",
            DeviceControl.restart_adb_server,
            lambda result: self.control_show(result, "ADB SERVER"),
        )

    def control_wireless(self):

        self.control_show(
            (
                True,
                "Wireless debugging requires Android 11 or newer.\n\n"
                "On the phone: Developer options -> Wireless debugging ->\n"
                "'Pair device with pairing code'. Then connect the computer to\n"
                "the same Wi-Fi network and run:\n\n"
                "    adb pair <ip>:<pairing-port>\n"
                "    adb connect <ip>:<debug-port>\n\n"
                "The pairing port and the debug port are different numbers.",
            ),
            "WIRELESS DEBUGGING",
        )

    def control_connect_wireless(self):

        host = self.control_host.text().strip()
        if not host:
            QMessageBox.warning(
                self, self.tr("Missing Information"),
                "Enter the phone's Wi-Fi IP address first.",
            )
            return

        port = 5555
        if ":" in host:
            host, port_text = host.rsplit(":", 1)
            port = int(port_text) if port_text.isdigit() else 5555

        self.run_background(
            "Wireless ADB connect",
            lambda: DeviceControl.wireless_connect(host, port),
            lambda result: self.control_show(result, "WIRELESS ADB"),
        )

    # =====================================================
    # PACKAGES & FILES
    # =====================================================

    def create_packages_page(self):

        tool = ToolPage(
            self,
            "Packages & Files",
            "Install, inspect and remove apps; browse and transfer device files.",
            "packages_device_combo",
        )
        tool.with_device_selector("Connected Device")

        tool.add_section(
            "APPLICATIONS",
            [
                ("User Apps", lambda: self.packages_list(False)),
                ("System Apps", lambda: self.packages_list(True)),
                ("Uninstall", self.packages_uninstall),
                ("Clear App Data", self.packages_clear),
                ("Disable App", self.packages_disable),
                ("Enable App", self.packages_enable),
            ],
        )

        self.package_name = QLineEdit()
        self.package_name.setMinimumWidth(220)
        self.package_name.setPlaceholderText("Package name (com.example.app)")
        tool.add_row([
            labelled("Package", self.package_name),
            QPushButton("App Info", clicked=self.packages_info),
            QPushButton("Install APK", clicked=self.packages_install),
        ])

        tool.add_section(
            "FILES",
            [
                ("Browse /sdcard", lambda: self.files_browse("/sdcard")),
                ("Storage Usage", self.files_storage),
                ("Pull File", self.files_pull),
                ("Push File", self.files_push),
                ("Delete Path", self.files_delete),
            ],
        )

        self.file_remote = QLineEdit()
        self.file_remote.setMinimumWidth(220)
        self.file_remote.setPlaceholderText("/sdcard/DCIM/Camera/photo.jpg")

        self.file_local = QLineEdit()
        self.file_local.setMinimumWidth(220)
        self.file_local.setPlaceholderText("Local file or folder")
        browse = QPushButton("Browse")
        browse.clicked.connect(self.files_pick_local)

        tool.add_row([
            labelled("Device path", self.file_remote),
            labelled("Computer path", self.file_local),
            browse,
        ])

        tool.with_console("App and file results will appear here...")
        self.packages_result_box = tool.result_box
        return tool.finish()

    def packages_serial(self):

        combo = getattr(self, "packages_device_combo", None)
        if combo is not None and combo.currentData():
            return combo.currentData()

        device = self.devices.first_authorized()
        if device is None:
            QMessageBox.warning(
                self, self.tr("No Device"),
                self.tr("Please connect and select an Android device."),
            )
            return None
        return device.serial

    def packages_show(self, result, title):

        if isinstance(result, tuple):
            ok, output = result
        else:
            ok, output = True, str(result)

        if self.packages_result_box is not None:
            self.packages_result_box.setPlainText(
                f"========== {title} ==========\n{output}"
            )
        self.log(f"Packages & files: {title} -> {'OK' if ok else 'FAILED'}")
        return ok

    def _packages_action(self, title, worker):

        serial = self.packages_serial()
        if not serial:
            return
        self.run_background(
            title,
            lambda: worker(serial),
            lambda result: self.packages_show(result, title),
        )

    def packages_list(self, system):

        self._packages_action(
            "Package list", lambda serial: DeviceControl.packages(serial, system)
        )

    def _package_arg(self):

        name = self.package_name.text().strip()
        if not name:
            QMessageBox.warning(
                self, self.tr("Missing Information"),
                "Enter a package name first.",
            )
        return name or None

    def packages_info(self):

        name = self._package_arg()
        if not name:
            return
        self._packages_action(
            "App info", lambda serial: DeviceControl.package_info(serial, name)
        )

    def packages_install(self):

        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Select APK File"), "", "Android APK (*.apk)"
        )
        if not path:
            return
        self._packages_action(
            "Install APK", lambda serial: DeviceControl.install(serial, path)
        )

    def packages_uninstall(self):

        name = self._package_arg()
        if not name:
            return
        if not self._confirm(
            "Uninstall application",
            f"Uninstall {name}?\n\nAll of its data on the phone is deleted.",
        ):
            return
        self._packages_action(
            "Uninstall", lambda serial: DeviceControl.uninstall(serial, name)
        )

    def packages_clear(self):

        name = self._package_arg()
        if not name:
            return
        if not self._confirm(
            "Clear application data", f"Delete all data stored by {name}?"
        ):
            return
        self._packages_action(
            "Clear data", lambda serial: DeviceControl.clear_package(serial, name)
        )

    def packages_disable(self):

        name = self._package_arg()
        if not name:
            return
        self._packages_action(
            "Disable app", lambda serial: DeviceControl.disable_package(serial, name)
        )

    def packages_enable(self):

        name = self._package_arg()
        if not name:
            return
        self._packages_action(
            "Enable app", lambda serial: DeviceControl.enable_package(serial, name)
        )

    def files_browse(self, path):

        self._packages_action(
            "Browse", lambda serial: DeviceControl.list_dir(serial, path)
        )

    def files_storage(self):

        self._packages_action(
            "Storage usage", lambda serial: DeviceControl.storage_map(serial)
        )

    def files_pull(self):

        remote = self.file_remote.text().strip()
        local = self.file_local.text().strip() or os.path.basename(remote)

        if not remote:
            QMessageBox.warning(
                self, self.tr("Missing Information"),
                "Enter the device path to copy.",
            )
            return

        self._packages_action(
            "Pull file", lambda serial: DeviceControl.pull(serial, remote, local)
        )

    def files_push(self):

        remote = self.file_remote.text().strip()
        local = self.file_local.text().strip()

        if not remote or not local:
            QMessageBox.warning(
                self, self.tr("Missing Information"),
                "Choose a computer file and the device destination path.",
            )
            return

        self._packages_action(
            "Push file", lambda serial: DeviceControl.push(serial, local, remote)
        )

    def files_delete(self):

        remote = self.file_remote.text().strip()
        if not remote:
            return
        if not self._confirm_typed(
            "DELETE",
            f"Permanently delete this path on the phone?\n\n{remote}",
        ):
            return
        self._packages_action(
            "Delete path", lambda serial: DeviceControl.delete(serial, remote)
        )

    def files_pick_local(self):

        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Select local file"), "", "All Files (*)"
        )
        if path:
            self.file_local.setText(path)

    # =====================================================
    # LOGS & REPORTS
    # =====================================================

    def create_reports_page(self):

        tool = ToolPage(
            self,
            "Logs & Reports",
            "Device logcat, full security reports and saved service files.",
            "reports_device_combo",
        )
        tool.with_device_selector("Connected Device")

        tool.add_section(
            "LOGCAT",
            [
                ("Read Last 200 Lines", lambda: self.reports_logcat(200)),
                ("Read Last 1000 Lines", lambda: self.reports_logcat(1000)),
                ("Clear Log Buffer", self.reports_clear_logcat),
            ],
        )

        tool.add_section(
            "REPORTS",
            [
                ("Security Report", self.reports_security),
                ("Battery Report", self.reports_battery),
                ("Lock / Keyguard Report", self.reports_lock),
                ("Full Device Report", self.reports_full),
                ("Save Shown Report", self.reports_save),
                ("Open Reports Folder", self.reports_open_folder),
            ],
        )

        tool.with_console("Logs and reports will appear here...")
        self.reports_result_box = tool.result_box
        return tool.finish()

    def reports_serial(self):

        combo = getattr(self, "reports_device_combo", None)
        if combo is not None and combo.currentData():
            return combo.currentData()

        device = self.devices.first_authorized()
        if device is None:
            QMessageBox.warning(
                self, self.tr("No Device"),
                self.tr("Please connect and select an Android device."),
            )
            return None
        return device.serial

    def reports_show(self, result, title):

        if isinstance(result, tuple):
            ok, output = result
        else:
            ok, output = True, str(result)

        if self.reports_result_box is not None:
            self.reports_result_box.setPlainText(
                f"########## {title} ##########\n{output}"
            )
        self.log(f"Report: {title} -> {'OK' if ok else 'FAILED'}")
        return ok

    def _reports_action(self, title, worker):

        serial = self.reports_serial()
        if not serial:
            return
        self.run_background(
            title,
            lambda: worker(serial),
            lambda result: self.reports_show(result, title),
        )

    def reports_logcat(self, lines):

        self._reports_action(
            "Logcat", lambda serial: DeviceControl.logcat(serial, lines)
        )

    def reports_clear_logcat(self):

        self._reports_action(
            "Clear logcat", lambda serial: DeviceControl.clear_logcat(serial)
        )

    def reports_security(self):

        self._reports_action(
            "Security report", lambda serial: Diagnostics.security_report(serial)
        )

    def reports_battery(self):

        self._reports_action(
            "Battery report", lambda serial: Diagnostics.battery_report(serial)
        )

    def reports_lock(self):

        self._reports_action(
            "Lock report", lambda serial: DeviceLockState.read(serial)
        )

    def reports_full(self):

        self._reports_action("Full report", lambda serial: self._full_report_worker(serial))

    def _full_report_worker(self, serial):

        parts = []
        for title, worker in (
            ("IDENTITY & INTEGRITY", Diagnostics.security_report),
            ("BATTERY", Diagnostics.battery_report),
            ("KEYGUARD", lambda s: "\n".join(DeviceLockState.read(s)[1])),
            ("PACKAGES", lambda s: DeviceControl.packages(s)[1][:4000]),
        ):
            try:
                _ok, output = worker(serial)
            except Exception as error:  # noqa: BLE001
                output = f"failed: {error}"

            parts.append("=" * 62)
            parts.append(title)
            parts.append("=" * 62)
            parts.append(output if output else "(no data)")
            parts.append("")
        return True, "\n".join(parts)

    def reports_save(self):

        self.export_report(self.reports_result_box, "report")

    def export_report(self, box, prefix):

        if box is None or not box.toPlainText().strip():
            QMessageBox.warning(
                self, self.tr("Nothing To Save"),
                "Run a report first, then save it.",
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save Report"),
            f"{prefix}_report.txt",
            "Text files (*.txt)",
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(box.toPlainText())
        except OSError as error:
            QMessageBox.critical(self, self.tr("Save Failed"), str(error))
            return

        self.log(f"Report saved: {path}")
        QMessageBox.information(
            self, self.tr("Report Saved"), f"Saved to:\n{path}"
        )

    def reports_open_folder(self):

        folder = os.path.join(os.getcwd(), "reports")
        os.makedirs(folder, exist_ok=True)

        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl

        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        self.log(f"Reports folder: {folder}")

    # =====================================================
    # SHARED SERVICE HELPERS
    # =====================================================

    def _confirm(self, title, message):

        answer = QMessageBox.question(
            self, self.tr(title), message,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        return answer == QMessageBox.Yes

    def _confirm_typed(self, word, message):
        """Second, typed confirmation used before every destructive action."""

        text, ok = QInputDialog.getText(
            self,
            self.tr("Confirm Destructive Operation"),
            f"{message}\n\nType {word} to continue:",
        )
        return bool(ok) and text.strip().upper() == word.upper()

    def show_service_environment(self):

        self.run_background(
            "Service environment",
            UnlockTools.service_environment,
            lambda result: self._show_in("unlock_result_box", result, "SERVICE TOOLS"),
        )

    def show_samsung_guide(self):

        box = "unlock_result_box"
        if getattr(self, box, None) is None or not self.unlock_result_box.isVisible():
            box = "fastboot_result_box"
        self._show_in(box, UnlockTools.samsung_guide(), "SAMSUNG SERVICE GUIDE")

    def _show_in(self, box_name, result, title=None):

        box = getattr(self, box_name, None)
        if box is None:
            return

        output = result[1] if isinstance(result, tuple) else str(result)

        text = f"========== {title} ==========\n{output}" if title else output
        box.setPlainText(text)

# =====================================================
# iOS TOOLS
# =====================================================

    def create_ios_page(self):

        tool = ToolPage(
            self,
            "iOS Tools",
            "iPhone detection, diagnostics, backup and restore via libimobiledevice.",
            "ios_device_combo",
        )

        tool.add_section(
            "DEVICE",
            [
                ("Detect iPhones", self.ios_detect),
                ("Device Info", self.ios_info),
                ("Pair / Trust", self.ios_pair),
                ("Diagnostics", self.ios_diagnostics),
            ],
        )

        tool.add_section(
            "DATA",
            [
                ("Backup to Computer", self.ios_backup),
                ("Inspect Backup", self.ios_backup_info),
                ("Live System Log", self.ios_syslog),
            ],
        )

        tool.add_section(
            "RECOVERY (APPLE SERVERS ONLY)",
            [
                ("Restore iPhone", self.ios_restore),
            ],
        )

        tool.add_note(
            "Restoring uses Apple's own signing servers through the open-source "
            "idevicerestore client. Activation Lock (Find My iPhone) is enforced "
            "by Apple and is never bypassed.",
            "hint",
        )

        tool.add_section(
            "HELP",
            [
                ("Recovery / DFU Steps", self.ios_modes),
                ("Service Environment", self.ios_environment),
            ],
        )

        tool.with_console("iPhone results will appear here...")
        self.ios_result_box = tool.result_box
        return tool.finish()

    def ios_show(self, result, title):

        if isinstance(result, tuple):
            ok, output = result
        else:
            ok, output = True, str(result)

        if self.ios_result_box is not None:
            self.ios_result_box.setPlainText(
                f"========== {title} ==========\n{output}"
            )
        self.log(f"iOS: {title} -> {'OK' if ok else 'FAILED'}")
        return ok

    def _ios_action(self, title, worker):

        self.run_background(
            f"iOS {title}",
            worker,
            lambda result: self.ios_show(result, title),
        )

    def ios_detect(self):
        self._ios_action("IPHONES", IOSTools.devices)

    def ios_info(self):
        self._ios_action("IPHONE INFO", IOSTools.info)

    def ios_pair(self):
        self._ios_action("PAIRING", IOSTools.pair)

    def ios_diagnostics(self):
        self._ios_action("DIAGNOSTICS", IOSTools.diagnostics)

    def ios_syslog(self):
        self._ios_action("SYSTEM LOG", lambda: IOSTools.syslog(8))

    def ios_backup(self):

        folder = QFileDialog.getExistingDirectory(
            self, self.tr("Choose backup folder")
        )
        if not folder:
            return
        self._ios_action(
            "BACKUP", lambda: IOSTools.backup(folder)
        )

    def ios_backup_info(self):

        folder = QFileDialog.getExistingDirectory(
            self, self.tr("Choose backup folder")
        )
        if not folder:
            return
        self.ios_show(IOSTools.backup_info(folder), "BACKUP FOLDER")

    def ios_restore(self):

        if not self._confirm_typed(
            "RESTORE",
            "Restore the iPhone now?\n\n"
            "This downloads the signed firmware from Apple, erases the phone "
            "and installs the latest iOS. It needs a stable internet "
            "connection and can take 20-40 minutes.",
        ):
            return

        self._ios_action("RESTORE", IOSTools.restore)

    def ios_modes(self):

        self.ios_show(IOSTools.mode_guide(), "RECOVERY / DFU")

    def ios_environment(self):

        self._ios_action("ENVIRONMENT", IOSTools.environment)

    # =====================================================
    # REFRESH DEVICE MANAGER
    # =====================================================

    def refresh_devices(self):
        """Ask the device registry for a fresh scan and redraw the table."""

        if self.device_table is None:
            return

        self.log("Scanning Android devices...")
        self.fill_device_table()
        self.devices.request_scan(force=True)

    def fill_device_table(self):

        if self.device_table is None:
            return

        devices = self.devices.devices

        self.device_table.blockSignals(True)
        self.device_table.setRowCount(0)

        for device in devices:

            row = self.device_table.rowCount()
            self.device_table.insertRow(row)

            for col, value in enumerate(
                (device.serial, device.state, device.details)
            ):
                self.device_table.setItem(
                    row,
                    col,
                    QTableWidgetItem(value)
                )

        self.device_table.blockSignals(False)

        if not devices and self.info_box is not None:
            self.info_box.setPlainText(
                self.tr(
                    "No Android device detected.\n\n"
                    "Connect a phone over USB and enable USB debugging."
                )
            )

        self.filter_devices()

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

        if self.device_table is None or self.info_box is None:
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

        if state != "device":

            self.info_box.setPlainText(
                f"Serial Number: {serial}\n"
                f"State: {state}\n\n"
                "Device authorization is required."
            )
            return

        self.info_box.setPlainText(
            f"Reading device properties for {serial}..."
        )

        def worker():
            properties = [
                ("Manufacturer", "ro.product.manufacturer"),
                ("Brand", "ro.product.brand"),
                ("Model", "ro.product.model"),
                ("Device", "ro.product.device"),
                ("Android Version", "ro.build.version.release"),
                ("SDK Version", "ro.build.version.sdk"),
                ("Build ID", "ro.build.id"),
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

                ok, value = ADBTools.run(
                    ["-s", serial, "shell", "getprop", prop]
                )

                lines.append(
                    f"{label}: "
                    f"{value if ok and value else 'Unavailable'}"
                )

            return "\n".join(lines)

        def done(text):
            if self.info_box is not None:
                self.info_box.setPlainText(text)

        self.run_background(
            f"Device information ({serial})",
            worker,
            done
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
