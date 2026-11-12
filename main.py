import sys
import shutil
import subprocess
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QStackedWidget,
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


# =========================================================
# CONFIGURATION
# =========================================================

APP_NAME = "AYMTECH PRO"
APP_VERSION = "1.1.0"

STYLE = """
QMainWindow, QWidget {
    background-color: #0b1120;
    color: #e5e7eb;
    font-family: Segoe UI;
    font-size: 10pt;
}

QFrame#Sidebar {
    background-color: #111827;
    border-right: 1px solid #263247;
}

QLabel#Logo {
    color: #38bdf8;
    font-size: 23pt;
    font-weight: bold;
}

QLabel#Subtitle {
    color: #94a3b8;
    font-size: 9pt;
}

QLabel#PageTitle {
    color: #f8fafc;
    font-size: 21pt;
    font-weight: bold;
}

QLabel#CardTitle {
    color: #94a3b8;
    font-size: 10pt;
}

QLabel#CardValue {
    color: #38bdf8;
    font-size: 23pt;
    font-weight: bold;
}

QPushButton {
    background-color: #1e293b;
    color: #e2e8f0;
    border: 1px solid #334155;
    border-radius: 7px;
    padding: 10px;
    text-align: left;
}

QPushButton:hover {
    background-color: #263b56;
    border: 1px solid #38bdf8;
}

QPushButton:checked {
    background-color: #075985;
    border: 1px solid #38bdf8;
    color: white;
}

QPushButton#Primary {
    background-color: #0284c7;
    color: white;
    border: none;
    font-weight: bold;
}

QPushButton#Primary:hover {
    background-color: #0369a1;
}

QLineEdit, QComboBox {
    background-color: #111827;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 9px;
    color: white;
}

QTableWidget {
    background-color: #111827;
    alternate-background-color: #172033;
    border: 1px solid #263247;
    border-radius: 7px;
    gridline-color: #263247;
}

QHeaderView::section {
    background-color: #1e293b;
    color: #38bdf8;
    padding: 9px;
    border: none;
    font-weight: bold;
}

QTextEdit {
    background-color: #080e1a;
    color: #a7f3d0;
    border: 1px solid #263247;
    border-radius: 7px;
    padding: 10px;
}

QLabel {
    background: transparent;
}
"""


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

        self.setWindowTitle(
            f"{APP_NAME} - Android & Mobile Service"
        )

        self.resize(1250, 780)
        self.setMinimumSize(1050, 650)

        self.device_table = None
        self.info_box = None
        self.search_box = None
        self.log_box = None
        self.pages = None

        # ADB interface widgets
        self.adb_device_combo = None
        self.adb_status_label = None
        self.adb_output = None

        self.navigation_buttons = []

        self.build_interface()
        self.refresh_devices()

    # =====================================================
    # INTERFACE
    # =====================================================

    def build_interface(self):

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(235)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(15, 25, 15, 15)
        sidebar_layout.setSpacing(9)

        logo = QLabel("AYMTECH PRO")
        logo.setObjectName("Logo")
        sidebar_layout.addWidget(logo)

        subtitle = QLabel("MOBILE SERVICE CENTER")
        subtitle.setObjectName("Subtitle")
        sidebar_layout.addWidget(subtitle)

        sidebar_layout.addSpacing(25)

        self.pages = QStackedWidget()

        navigation = [
            ("Dashboard", self.create_dashboard),
            ("Device Manager", self.create_device_manager),
            ("Device Information", self.create_device_information),
            ("ADB Tools", self.create_adb_page),
            ("Android Tools", lambda: self.create_tool_page("Android Tools")),
            ("Samsung Tools", lambda: self.create_tool_page("Samsung Tools")),
            ("Qualcomm Tools", lambda: self.create_tool_page("Qualcomm Tools")),
            ("MediaTek Tools", lambda: self.create_tool_page("MediaTek Tools")),
            ("Firmware Center", lambda: self.create_tool_page("Firmware Center")),
            ("iOS Tools", lambda: self.create_tool_page("iOS Tools")),
            ("Operation Logs", self.create_logs_page),
        ]

        for title, creator in navigation:

            button = QPushButton(title)
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)

            button.clicked.connect(
                lambda checked=False, t=title: self.navigate(t)
            )

            sidebar_layout.addWidget(button)
            self.navigation_buttons.append((title, button))

            page = creator()
            self.pages.addWidget(page)

        sidebar_layout.addStretch()

        version = QLabel(
            f"AYMTECH PRO v{APP_VERSION}\n"
            "Android Service Toolkit"
        )
        version.setObjectName("Subtitle")
        sidebar_layout.addWidget(version)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.pages, 1)

        self.navigate("Dashboard")

    # =====================================================
    # PAGE HEADER
    # =====================================================

    def create_page_header(self, title, description=""):

        layout = QVBoxLayout()

        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        layout.addWidget(title_label)

        if description:
            desc = QLabel(description)
            desc.setStyleSheet("color: #94a3b8;")
            layout.addWidget(desc)

        layout.addSpacing(15)

        return layout

    # =====================================================
    # DASHBOARD
    # =====================================================

    def create_dashboard(self):

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)

        layout.addLayout(
            self.create_page_header(
                "Dashboard",
                "Welcome to AYMTECH PRO Mobile Service Center."
            )
        )

        cards_layout = QGridLayout()
        cards_layout.setSpacing(15)

        cards = [
            ("Connected Devices", "ADB"),
            ("ADB Status", "READY"),
            ("Fastboot Status", "READY"),
            ("Software Version", APP_VERSION),
        ]

        for index, (title, value) in enumerate(cards):

            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background-color: #111827;
                    border: 1px solid #263247;
                    border-radius: 10px;
                }
            """)

            card_layout = QVBoxLayout(card)

            title_label = QLabel(title)
            title_label.setObjectName("CardTitle")

            value_label = QLabel(value)
            value_label.setObjectName("CardValue")

            card_layout.addWidget(title_label)
            card_layout.addWidget(value_label)
            card_layout.addStretch()

            cards_layout.addWidget(
                card,
                index // 2,
                index % 2
            )

        layout.addLayout(cards_layout)
        layout.addSpacing(20)

        section = QLabel("Quick Actions")
        section.setStyleSheet(
            "font-size: 15pt; font-weight: bold;"
        )
        layout.addWidget(section)

        actions = QHBoxLayout()

        refresh_button = QPushButton("Refresh Devices")
        refresh_button.setObjectName("Primary")
        refresh_button.clicked.connect(self.refresh_devices)

        tools_button = QPushButton("Check ADB / Fastboot")
        tools_button.clicked.connect(self.check_tools)

        adb_button = QPushButton("Open ADB Tools")
        adb_button.clicked.connect(
            lambda: self.navigate("ADB Tools")
        )

        actions.addWidget(refresh_button)
        actions.addWidget(tools_button)
        actions.addWidget(adb_button)

        layout.addLayout(actions)
        layout.addSpacing(20)

        info = QLabel(
            "AYMTECH PRO\n\n"
            "Professional mobile servicing interface.\n"
            "Connect an Android phone using USB debugging "
            "to access real device information.\n\n"
            "Demo Mode is enabled when no ADB device is detected."
        )

        info.setStyleSheet("""
            background-color: #111827;
            border: 1px solid #263247;
            border-radius: 10px;
            padding: 20px;
            color: #cbd5e1;
        """)

        layout.addWidget(info)
        layout.addStretch()

        return page

    # =====================================================
    # DEVICE MANAGER
    # =====================================================

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
        note.setStyleSheet("color: #94a3b8;")
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
        self.adb_status_label.setStyleSheet(
            "color: #fbbf24; font-weight: bold;"
        )

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
        output_title.setStyleSheet(
            "font-size: 13pt; font-weight: bold;"
        )

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
                "No Device",
                "No authorized Android device is connected.\n\n"
                "Connect your phone, enable USB Debugging, "
                "and authorize this computer."
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

            self.adb_status_label.setStyleSheet(
                "color: #f87171; font-weight: bold;"
            )

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

            self.adb_status_label.setStyleSheet(
                "color: #4ade80; font-weight: bold;"
            )

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

            self.adb_status_label.setStyleSheet(
                "color: #fbbf24; font-weight: bold;"
            )

        else:

            self.adb_device_combo.addItem(
                "No authorized device connected",
                None
            )

            self.adb_status_label.setText(
                "Status: No real Android device detected."
            )

            self.adb_status_label.setStyleSheet(
                "color: #fbbf24; font-weight: bold;"
            )

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
            "Confirm Reboot",
            f"Are you sure you want to reboot the device "
            f"into {mode_names[mode]}?",
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
            "Select APK File",
            "",
            "Android APK (*.apk)"
        )

        if not apk_path:
            return

        answer = QMessageBox.question(
            self,
            "Install APK",
            f"Install this application on the selected device?\n\n"
            f"{apk_path}",
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
            "Save Device Screenshot",
            "AYMTECH_screenshot.png",
            "PNG Image (*.png)"
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
                "Screenshot Saved",
                f"Screenshot saved successfully:\n{destination}"
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

        message.setStyleSheet("""
            background-color: #111827;
            border: 1px solid #263247;
            border-radius: 10px;
            padding: 25px;
            color: #cbd5e1;
        """)

        layout.addWidget(message)
        layout.addStretch()

        return page

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

    # =====================================================
    # NAVIGATION
    # =====================================================

    def navigate(self, title):

        for index, (name, button) in enumerate(
            self.navigation_buttons
        ):

            selected = name == title
            button.setChecked(selected)

            if selected:
                self.pages.setCurrentIndex(index)

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
            "Tool Status",
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

if __name__ == "__main__":

    app = QApplication(sys.argv)

    app.setApplicationName(APP_NAME)
    app.setStyleSheet(STYLE)

    window = AymtechPro()
    window.show()

    sys.exit(app.exec())
