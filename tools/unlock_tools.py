"""Unlock / FRP service helpers.

This module deliberately contains **no bypass**: modern Android releases
(Credential-Encrypted / File-Based Encryption, verified boot, FRP) cannot be
unlocked from ADB, and any tool that claims so is either a paid scam or a
chip-level service that requires opening the phone.

What the module does provide is the real service workflow:

* tell the technician exactly which lock state the phone is in,
* clear a *known* PIN/pattern with the supported ``locksettings`` command,
* remove a non-secure swipe lock,
* detect FRP, MDM and device-admin enrolment,
* list the manufacturer's official recovery paths.
"""

from __future__ import annotations

import shutil
from datetime import datetime

from .adb_tools import ADBTools


class UnlockTools:

    # ------------------------------------------------------------------
    # supported, non-destructive operations
    # ------------------------------------------------------------------

    @staticmethod
    def remove_swipe_lock(serial):
        """Disable a *non-secure* swipe/None lock screen."""

        ok, output = ADBTools.run(
            ["-s", serial, "shell", "locksettings", "set-disabled", "true"],
            timeout=30,
        )
        ok2, output2 = ADBTools.run(
            ["-s", serial, "shell", "settings", "put", "secure",
             "lockscreen.disabled", "1"], timeout=20,
        )
        if ok or ok2:
            return True, (
                "Swipe lock disabled.\n\n"
                f"{output}\n{output2}\n\n"
                "A PIN, pattern or password lock is NOT removable this way."
            ).strip()
        return False, (output or output2)

    @staticmethod
    def clear_known_pin(serial):
        """Remove a secure lock when the phone is already unlocked over ADB."""

        ok, output = ADBTools.run(
            ["-s", serial, "shell", "locksettings", "clear"], timeout=30
        )
        if ok:
            return True, (
                "Screen lock cleared.\n\n"
                f"{output}\n\n"
                "This only works when the phone is unlocked and ADB is already "
                "authorised, i.e. you know the current credential."
            )
        return False, (
            f"{output}\n\n"
            "locksettings clear needs an unlocked, authorised session. "
            "A device parked on the lock screen cannot be cleared from ADB."
        )

    @staticmethod
    def set_pin(serial, pin):
        """Set a temporary PIN (useful before handing a refurbished phone back)."""

        if not pin.isdigit() or not 4 <= len(pin) <= 16:
            return False, "The PIN must be 4 to 16 digits."
        ok, output = ADBTools.run(
            ["-s", serial, "shell", "locksettings", "set-pin", pin], timeout=30
        )
        return ok, output or "Lock PIN updated."

    # ------------------------------------------------------------------
    # FRP / account state
    # ------------------------------------------------------------------

    @staticmethod
    def frp_status(serial):
        results = ["========== FACTORY RESET PROTECTION ==========", ""]

        _ok, frp_prop = ADBTools.run(
            ["-s", serial, "shell", "getprop", "ro.frp.pst"], timeout=15
        )
        results.append(f"FRP partition    : {(frp_prop or 'not reported').strip()}")

        queries = [
            ("Device provisioned", "settings", "get", "global", "device_provisioned"),
            ("Setup wizard done", "settings", "get", "secure", "user_setup_complete"),
            ("OEM unlocking", "settings", "get", "global", "oem_unlock_allowed"),
            ("ADB enabled", "settings", "get", "global", "adb_enabled"),
            ("Developer options", "settings", "get", "global",
             "development_settings_enabled"),
        ]
        values = {}
        for label, *args in queries:
            ok, output = ADBTools.run(
                ["-s", serial, "shell"] + list(args), timeout=20
            )
            values[label] = output.strip() if ok else ""
            results.append(f"{label:20}: {values[label] or 'unknown'}")

        # accounts signed in
        ok, accounts = ADBTools.run(
            ["-s", serial, "shell", "dumpsys", "account"], timeout=45
        )
        emails = []
        if ok:
            for line in accounts.splitlines():
                if "Account {" in line or "@" in line:
                    cleaned = line.strip()
                    if any(char in cleaned for char in ("@", "type=")):
                        emails.append(cleaned)
        emails = emails[:10]
        results.append("")
        results.append("Signed-in accounts:")
        results.extend([f"  {line}" for line in emails] or ["  none reported"])

        results.append("")
        provisioned = values.get("Device provisioned", "")
        setup = values.get("Setup wizard done", "")
        if provisioned == "1" and setup == "1":
            results.append("VERDICT: the phone is fully provisioned; FRP is not pending.")
        elif provisioned == "0" or setup == "0":
            results.append(
                "VERDICT: setup is incomplete. The previous Google/Huawei/Samsung\n"
                "account still protects this device (FRP active)."
            )
        else:
            results.append("VERDICT: not determinable from ADB.")

        results.append("")
        results.append(UnlockTools.frp_explanation())
        return True, "\n".join(results)

    @staticmethod
    def frp_explanation():
        return (
            "========== WHAT ACTUALLY REMOVES FRP ==========\n"
            "1. The original account credentials (sign in normally), or\n"
            "2. A proof-of-purchase request to Google / Samsung / Xiaomi\n"
            "   support, who can clear the lock server-side, or\n"
            "3. A signed service firmware repair (authorised service centre),\n"
            "   or a chip-level (EDL/JTAG) procedure on the physical board.\n\n"
            "FRP is enforced by the bootloader against a server-signed lock\n"
            "state. No ADB command, apk or 'FRP tool' can clear it, and tools\n"
            "that claim otherwise either steal the account or damage the unit."
        )

    # ------------------------------------------------------------------
    # enrolment / MDM
    # ------------------------------------------------------------------

    @staticmethod
    def device_admins(serial):
        ok, output = ADBTools.run(
            ["-s", serial, "shell", "dumpsys", "device_policy"], timeout=60
        )
        if not ok:
            return False, output
        interesting = []
        for line in output.splitlines():
            stripped = line.strip()
            if any(key in stripped for key in (
                "Admin ", "admin=", "Device Owner", "Profile Owner",
                "knox", "Knox", "deviceOwner", "profileOwner",
            )):
                if stripped not in interesting:
                    interesting.append(stripped)
        lines = ["========== DEVICE ADMINS / MDM ==========", ""]
        lines.extend(interesting[:25] or ["No device administrator reported."])
        lines.append("")
        lines.append(
            "If an app is Device Owner (common on company phones), removing it\n"
            "requires the organisation's management console. A factory reset\n"
            "while it is still enrolled re-applies the policy at setup."
        )
        return True, "\n".join(lines)

    @staticmethod
    def remove_device_admin(serial, package):
        if not package:
            return False, "No package name provided."
        ok, output = ADBTools.run(
            ["-s", serial, "shell", "pm", "remove-active-admin",
             "--user", "0", package], timeout=60,
        )
        if not ok:
            return False, (
                f"{output}\n\n"
                "Only apps whose manifest declares android:testOnly or that\n"
                "belong to you can be removed this way."
            )
        return True, output

    # ------------------------------------------------------------------
    # Samsung download mode / vendor tooling presence
    # ------------------------------------------------------------------

    @staticmethod
    def service_environment():
        """Report which vendor tools exist on this workstation."""

        tools = {
            "adb": "Android Platform-Tools",
            "fastboot": "Android Platform-Tools",
            "heimdall": "Heimdall (Samsung, cross-platform Odin)",
            "odin": "Odin (Samsung, Windows)",
            "edl": "EDL.py (Qualcomm 9008)",
            "spflash": "SP Flash Tool (MediaTek)",
            "ideviceinfo": "libimobiledevice (iOS)",
            "idevicerestore": "libimobiledevice (iOS restore)",
        }
        lines = ["========== WORKSTATION SERVICE TOOLS ==========", ""]
        for binary, description in tools.items():
            found = shutil.which(binary)
            status = found if found else "not installed"
            lines.append(f"{binary:16} {status}")
            lines.append(f"{'':16} {description}")
        lines.append("")
        lines.append(
            "AYMTECH PRO uses these external tools when they exist and falls\n"
            "back to clear instructions when they do not. Nothing is bundled\n"
            "in order to respect each vendor's licence."
        )
        return True, "\n".join(lines)

    @staticmethod
    def samsung_guide():
        return (
            "========== SAMSUNG - OFFICIAL SERVICE PATH ==========\n\n"
            "1. Power off, then hold Volume-Up + Volume-Down and plug USB\n"
            "   (or Volume-Down + Bixby + Power) to reach Download Mode.\n"
            "2. The screen shows 'OEM LOCK : ON (U)' when the bootloader is\n"
            "   locked. Samsungs cannot be bootloader-unlocked through fastboot.\n"
            "3. FRP removal on a Samsung is a Heimdall/Odin operation using a\n"
            "   signed combination firmware for the exact model, followed by an\n"
            "   official firmware flash. Using the wrong file bricks the phone.\n"
            "4. Always match: model (SM-XXXX), CSC region, and firmware build.\n\n"
            "Use 'Firmware Center' to verify the file hash before flashing."
        )

    @staticmethod
    def knox_note():
        return (
            "Knox warranty bit = 1 means the phone was rooted or flashed with a\n"
            "non-samsung image at some point. Samsung Pay, Secure Folder and\n"
            "some banking apps will stay disabled - this cannot be reversed."
        )

    # ------------------------------------------------------------------
    # report
    # ------------------------------------------------------------------

    @staticmethod
    def write_report(sections, folder="./reports"):
        import os

        os.makedirs(folder, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(folder, f"unlock_report_{stamp}.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n\n".join(sections))
        return True, path
