"""iOS device servicing through libimobiledevice.

Nothing here bundles or patches Apple software: when the open-source
``libimobiledevice`` suite is installed the module talks to the phone with it,
otherwise it reports exactly which packages are missing and what each command
would do.  DFU / recovery restore always goes through Apple's own servers,
which is the only path that keeps the baseband and the activation intact.
"""

from __future__ import annotations

import os
import platform

from . import proc

TOOLS = {
    "idevice_id": "list attached iOS devices (USB)",
    "ideviceinfo": "device identity, model, iOS version, storage",
    "idevicediagnostics": "battery, hardware and IORegistry diagnostics",
    "idevicebackup2": "encrypted or plain backup to this computer",
    "idevicesyslog": "live system log stream",
    "idevicerestore": "restore / update firmware from Apple's servers",
    "idevicepair": "pair (trust) the device with this computer",
}

MODES = {
    "dfu": "DFU (Device Firmware Update)",
    "recovery": "Recovery mode",
    "normal": "Normal (booted iOS)",
}


class IOSTools:

    @staticmethod
    def available():
        return {name: proc.which(name) is not None for name in TOOLS}

    @staticmethod
    def _require(name):
        path = proc.which(name)
        if path is None:
            return False, (
                f"{name} is not installed.\n\n"
                "Install the libimobiledevice suite:\n"
                "  Windows : https://github.com/libimobiledevice/libimobiledevice\n"
                "  macOS   : brew install libimobiledevice ideviceinstaller\n"
                "  Linux   : sudo apt install libimobiledevice-utils\n\n"
                "AYMTECH PRO never bundles Apple software; only the open-source\n"
                "client tools are used, and the phone does the real work."
            )
        return True, path

    # ------------------------------------------------------------------
    # discovery / identity
    # ------------------------------------------------------------------

    @staticmethod
    def devices():
        ok, output = IOSTools._require("idevice_id")
        if not ok:
            return False, output

        ok2, listed = proc.run(["idevice_id", "-l"], timeout=20)
        if not ok2:
            return False, listed

        udids = [line.strip() for line in listed.splitlines() if line.strip()]
        if not udids:
            return True, (
                "No iOS device detected.\n\n"
                "Use a data-capable cable, unlock the phone and tap 'Trust'.\n"
                "An iPhone in DFU mode is only visible to idevicerestore."
            )

        lines = [f"{len(udids)} iOS device(s) attached:", ""]
        for udid in udids:
            ok3, info = proc.run(["ideviceinfo", "-u", udid], timeout=25)
            if not ok3:
                lines.append(f"  {udid}  (info unavailable)")
                continue
            wanted = {
                "ProductType": "Model",
                "ProductVersion": "iOS",
                "BuildVersion": "Build",
                "DeviceName": "Name",
                "UniqueDeviceID": "UDID",
                "SerialNumber": "Serial",
                "TotalDiskCapacity": "Storage",
                "PasswordProtected": "Passcode",
            }
            values = {}
            for line in info.splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    if key.strip() in wanted:
                        values[wanted[key.strip()]] = value.strip()

            lines.append(f"  {values.get('Name', 'iPhone')}  "
                         f"({values.get('Model', '?')}, iOS {values.get('iOS', '?')})")
            for label in ("Build", "UDID", "Serial", "Storage", "Passcode"):
                if label in values:
                    lines.append(f"    {label:9} {values[label]}")
            lines.append("")
        return True, "\n".join(lines)

    @staticmethod
    def info(udid=None):
        ok, output = IOSTools._require("ideviceinfo")
        if not ok:
            return False, output
        args = ["ideviceinfo"] + (["-u", udid] if udid else [])
        ok2, info = proc.run(args, timeout=30)
        if not ok2:
            return False, info
        keep = (
            "DeviceName", "ProductType", "ProductVersion", "BuildVersion",
            "UniqueDeviceID", "SerialNumber", "BasebandVersion",
            "ActivationState", "PasswordProtected", "BatteryCurrentCapacity",
            "TotalDiskCapacity", "TimeZone", "RegionInfo",
        )
        lines = ["========== iPhone INFORMATION ==========", ""]
        for line in info.splitlines():
            if any(line.startswith(key) for key in keep):
                lines.append(line)
        return True, "\n".join(lines)

    @staticmethod
    def diagnostics(udid=None):
        ok, output = IOSTools._require("idevicediagnostics")
        if not ok:
            return False, output
        args = ["idevicediagnostics", "diagnostics"]
        if udid:
            args = ["idevicediagnostics", "-u", udid, "diagnostics"]
        ok2, data = proc.run(args, timeout=45)
        if not ok2:
            return False, data
        lines = ["========== iPhone DIAGNOSTICS ==========", ""]
        for line in data.splitlines():
            if any(key in line for key in ("GasGauge", "Battery", "CycleCount",
                                           "AppleCare", "ChargerData")):
                lines.append(line.strip()[:160])
        if len(lines) == 2:
            lines.append("(raw diagnostics are available but not battery-specific)")
        return True, "\n".join(lines)

    # ------------------------------------------------------------------
    # pairing / backup / logs
    # ------------------------------------------------------------------

    @staticmethod
    def pair(udid=None):
        ok, output = IOSTools._require("idevicepair")
        if not ok:
            return False, output
        args = ["idevicepair"] + (["-u", udid] if udid else []) + ["pair"]
        ok2, result = proc.run(args, timeout=60)
        if ok2:
            return True, (
                f"{result}\n\n"
                "Trust is stored on the phone. If it was refused, unlock the\n"
                "phone and tap 'Trust' when the prompt appears."
            )
        return False, result

    @staticmethod
    def backup(destination, udid=None):
        ok, output = IOSTools._require("idevicebackup2")
        if not ok:
            return False, output
        os.makedirs(destination, exist_ok=True)
        args = ["idevicebackup2"] + (["-u", udid] if udid else [])
        args += ["backup", destination]
        ok2, result = proc.run(args, timeout=3600)
        return ok2, result or f"Backup written to {destination}"

    @staticmethod
    def backup_info(folder):
        if not os.path.isdir(folder):
            return False, f"Folder not found: {folder}"
        manifest = os.path.join(folder, "Manifest.plist")
        info = os.path.join(folder, "Info.plist")
        lines = [f"Backup folder: {folder}"]
        for path in (manifest, info):
            exists = os.path.exists(path)
            size = (
                f"{os.path.getsize(path) / 1024:.0f} KB"
                if exists else "missing"
            )
            lines.append(f"  {os.path.basename(path):16} {size}")
        return True, "\n".join(lines)

    @staticmethod
    def restore(udid=None):
        """Restore through Apple's own servers (libimobiledevice client)."""

        ok, output = IOSTools._require("idevicerestore")
        if not ok:
            return False, output
        args = ["idevicerestore"] + (["-u", udid] if udid else []) + ["-e"]
        ok2, result = proc.run(args, timeout=7200)
        return ok2, result

    @staticmethod
    def syslog(seconds=8, udid=None):
        ok, output = IOSTools._require("idevicesyslog")
        if not ok:
            return False, output

        import subprocess

        args = ["idevicesyslog"] + (["-u", udid] if udid else [])
        try:
            result = subprocess.run(
                args, capture_output=True, text=True,
                timeout=max(2, int(seconds)), encoding="utf-8", errors="replace",
            )
        except subprocess.TimeoutExpired as expired:
            partial = (expired.stdout or b"")
            if isinstance(partial, bytes):
                partial = partial.decode("utf-8", "replace")
            return True, (partial.strip() or "(no log lines in this window)")
        except Exception as error:  # noqa: BLE001
            return False, str(error)

        return True, (result.stdout.strip() or "(no log lines)")

    # ------------------------------------------------------------------
    # guidance / environment
    # ------------------------------------------------------------------

    @staticmethod
    def mode_guide():
        return (
            "========== HOW TO PUT AN IPHONE IN RECOVERY / DFU ==========\n\n"
            "iPhone 8 and newer (including all Face ID models):\n"
            "  1. Press and release Volume Up.\n"
            "  2. Press and release Volume Down.\n"
            "  3. Hold the Side button until the recovery screen appears\n"
            "     (keep holding for DFU: screen stays black).\n\n"
            "iPhone 7 / 7 Plus: hold Volume Down + Power.\n"
            "iPhone 6s and older: hold Home + Power.\n\n"
            "DFU vs Recovery:\n"
            "  Recovery shows the cable icon and allows 'Update' (keeps data).\n"
            "  DFU is a black screen and only allows a full restore (erases data).\n\n"
            "Activation Lock (Find My iPhone) cannot be bypassed: only the\n"
            "previous owner's Apple ID or an Apple proof-of-purchase request\n"
            "can remove it. Restoring a locked phone returns it to the same\n"
            "Activation Lock screen."
        )

    @staticmethod
    def environment():
        availability = IOSTools.available()
        lines = ["========== iOS SERVICE ENVIRONMENT ==========", ""]
        lines.append(f"Platform: {platform.system()} {platform.release()}")
        lines.append("")
        for name, description in TOOLS.items():
            path = proc.which(name)
            lines.append(f"{name:20} {path or 'not installed'}")
            lines.append(f"{'':20} {description}")
        missing = [n for n, found in availability.items() if not found]
        lines.append("")
        if missing:
            lines.append("Missing tools: " + ", ".join(missing))
            lines.append(
                "Install libimobiledevice to enable the device actions above."
            )
        else:
            lines.append("Every libimobiledevice tool is available.")
        return True, "\n".join(lines)
