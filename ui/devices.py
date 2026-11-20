"""Single source of truth for connected Android devices.

Every page used to parse ``adb devices`` on its own, so the ADB Tools,
Android Tools, Screen Lock and Live Screen pages could disagree, and a
phone connected after start-up was never noticed.  ``DeviceRegistry``
scans once, caches the result and notifies listeners; widgets keep their
selection by serial so a refresh does not reset the combo boxes.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Iterable, List, Optional

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QComboBox

from tools.adb_tools import ADBTools


@dataclass(frozen=True)
class Device:
    serial: str
    state: str
    details: str = ""

    @property
    def authorized(self) -> bool:
        return self.state == "device"

    @property
    def label(self) -> str:
        if self.state == "device":
            return self.serial
        return f"{self.serial}  ({self.state})"


class DeviceRegistry(QObject):
    """Periodic ADB scanner shared by the whole application."""

    devices_changed = Signal(list)   # list[Device]
    scan_finished = Signal(bool)     # adb available?

    def __init__(self, parent=None, interval_ms: int = 5000):
        super().__init__(parent)
        self._devices: List[Device] = []
        self._adb_available = shutil.which("adb") is not None
        self._scanning = False
        self._generation = 0
        self._interval = interval_ms
        self.timer = QTimer(self)
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self.request_scan)

    # ---- state ----
    @property
    def devices(self) -> List[Device]:
        return list(self._devices)

    @property
    def adb_available(self) -> bool:
        return self._adb_available

    def authorized(self) -> List[Device]:
        return [d for d in self._devices if d.authorized]

    def first_authorized(self) -> Optional[Device]:
        devices = self.authorized()
        return devices[0] if devices else None

    def find(self, serial: str) -> Optional[Device]:
        for device in self._devices:
            if device.serial == serial:
                return device
        return None

    # ---- polling ----
    def start(self, immediate: bool = True) -> None:
        self.timer.start()
        if immediate:
            self.request_scan()

    def stop(self) -> None:
        self.timer.stop()

    def set_interval(self, interval_ms: int) -> None:
        self._interval = interval_ms
        self.timer.setInterval(interval_ms)

    def request_scan(self, force: bool = False) -> None:
        """Scan in a background thread (safe to call repeatedly)."""
        if self._scanning and not force:
            return
        self._scanning = True
        self._generation += 1
        generation = self._generation
        self.runner.run(
            lambda: (generation, self._scan_worker()),
            self._on_scan_done,
            self._on_scan_error,
            quiet=True,
        )

    def attach_runner(self, runner) -> None:
        self.runner = runner

    # ---- worker ----
    @staticmethod
    def parse(output: str) -> List[Device]:
        devices: List[Device] = []
        for line in output.splitlines():
            line = line.strip()
            if not line or line.startswith("*") or line.startswith("List of devices"):
                continue
            if line.startswith("adb server") or "daemon" in line.lower():
                continue
            parts = line.split()
            if len(parts) >= 2:
                devices.append(
                    Device(parts[0], parts[1], " ".join(parts[2:]))
                )
        return devices

    def _scan_worker(self) -> tuple:
        available = shutil.which("adb") is not None
        if not available:
            return available, []
        ok, output = ADBTools.devices()
        if not ok:
            return available, []
        return available, self.parse(output)

    def _on_scan_done(self, result: tuple) -> None:
        generation, (available, devices) = result
        if generation != self._generation:
            # a newer scan already answered; drop this stale one
            return
        self._scanning = False
        self._adb_available = available
        self.scan_finished.emit(available)
        if devices != self._devices:
            self._devices = devices
            self.devices_changed.emit(list(devices))

    def _on_scan_error(self, message: str) -> None:
        self._scanning = False
        self.scan_finished.emit(self._adb_available)


# ---------------------------------------------------------------
# combo box binding
# ---------------------------------------------------------------

def fill_device_combo(
    combo: QComboBox,
    devices: Iterable[Device],
    placeholder: str = "No authorized device connected",
) -> Optional[str]:
    """Repopulate *combo*, preserving the current selection by serial.

    Returns the serial still selected (``None`` when nothing usable).
    """
    previous = combo.currentData()
    combo.blockSignals(True)
    combo.clear()

    usable = [d for d in devices if d.authorized]
    if not usable:
        combo.addItem(placeholder, None)
        combo.blockSignals(False)
        return None

    for device in usable:
        combo.addItem(device.label, device.serial)

    index = combo.findData(previous)
    if index >= 0:
        combo.setCurrentIndex(index)

    combo.blockSignals(False)
    return combo.currentData()
