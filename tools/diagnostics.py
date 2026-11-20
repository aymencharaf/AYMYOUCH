"""Device diagnostics: integrity, locks, FRP state and service reports.

The goal is to tell a technician **what the phone's own firmware says** about
its security state, and to explain what that means, instead of pretending to
bypass protections.  Every value here comes from properties or dumpsys text
that Android exposes to an authorised ADB session.
"""

from __future__ import annotations

import os
from datetime import datetime

from .adb_tools import ADBTools

# properties that describe the security posture of the device
SECURITY_PROPS = {
    "Manufacturer": "ro.product.manufacturer",
    "Brand": "ro.product.brand",
    "Model": "ro.product.model",
    "Device": "ro.product.device",
    "Android": "ro.build.version.release",
    "SDK": "ro.build.version.sdk",
    "Build ID": "ro.build.id",
    "Fingerprint": "ro.build.fingerprint",
    "Security patch": "ro.build.version.security_patch",
    "Verified boot": "ro.boot.verifiedbootstate",
    "Verity mode": "ro.boot.veritymode",
    "Bootloader locked": "ro.boot.flash.locked",
    "vbmeta state": "ro.boot.vbmeta.device_state",
    "Warranty bit (Knox)": "ro.boot.warranty_bit",
    "FRP partition": "ro.frp.pst",
    "First API level": "ro.product.first_api_level",
    "Encryption": "ro.crypto.state",
    "SELinux": "ro.boot.selinux",
}


def _fmt(value: str) -> str:
    return value.strip() if value and value.strip() else "not reported"


class Diagnostics:

    # ------------------------------------------------------------------
    # property reading
    # ------------------------------------------------------------------

    @staticmethod
    def read_props(serial, props=None):
        props = props or SECURITY_PROPS
        values = {}
        for label, prop in props.items():
            ok, output = ADBTools.run(
                ["-s", serial, "shell", "getprop", prop], timeout=15
            )
            values[label] = output.strip() if ok else ""
        return values

    # ------------------------------------------------------------------
    # interpretation
    # ------------------------------------------------------------------

    @staticmethod
    def bootloader_state(values):
        locked = _fmt(values.get("Bootloader locked", "")).lower()
        verified = _fmt(values.get("Verified boot", "")).lower()
        if locked == "1" and verified in ("green", "yellow"):
            return "LOCKED (stock firmware)"
        if locked == "0":
            return "UNLOCKED"
        if verified == "orange":
            return "UNLOCKED (verified boot is orange)"
        if verified == "red":
            return "UNVERIFIED (custom or corrupted firmware)"
        return "UNKNOWN"

    @staticmethod
    def knox_state(values):
        raw = values.get("Warranty bit (Knox)", "").strip()
        if raw == "1":
            return "TRIPPED (Knox warranty bit = 1)"
        if raw == "0":
            return "INTACT (Knox warranty bit = 0)"
        return "NOT APPLICABLE / NOT REPORTED"

    @staticmethod
    def frp_state(values, device_provisioned, setup_complete):
        frp = values.get("FRP partition", "").strip()
        lines = []
        if frp:
            lines.append(f"FRP partition present: {frp}")
        else:
            lines.append("FRP partition: not reported (device may not use one)")

        lines.append(f"Device provisioned: {device_provisioned or 'unknown'}")
        lines.append(f"Setup wizard completed: {setup_complete or 'unknown'}")

        if device_provisioned == "1" and setup_complete == "1":
            lines.append("State: device already set up -> FRP is not pending.")
        elif device_provisioned == "0" or setup_complete == "0":
            lines.append(
                "State: setup is incomplete -> the previous Google account is "
                "still required (Factory Reset Protection is active)."
            )
        else:
            lines.append("State: could not be determined from ADB.")
        return lines

    # ------------------------------------------------------------------
    # full report
    # ------------------------------------------------------------------

    @staticmethod
    def security_report(serial):
        ok, connection = ADBTools.check_connection(serial)
        if not ok:
            return False, (
                "The device is not answering to ADB.\n\n"
                f"{connection}\n\n"
                "On a freshly reset or locked phone, unlock it and accept the "
                "'Allow USB debugging' prompt if it appears."
            )

        values = Diagnostics.read_props(serial)

        provisioned = ADBTools.run(
            ["-s", serial, "shell", "settings", "get", "global", "device_provisioned"]
        )
        setup = ADBTools.run(
            ["-s", serial, "shell", "settings", "get", "secure", "user_setup_complete"]
        )
        provisioned = provisioned[1].strip() if provisioned[0] else ""
        setup = setup[1].strip() if setup[0] else ""

        # device admins / knox enrolment, best effort
        admin_ok, admin_out = ADBTools.run(
            ["-s", serial, "shell", "dumpsys", "device_policy"], timeout=45
        )
        admin_lines = []
        if admin_ok:
            for line in admin_out.splitlines():
                if "Admin" in line or "admin=" in line or "knox" in line.lower():
                    stripped = line.strip()
                    if stripped and stripped not in admin_lines:
                        admin_lines.append(stripped)
        admin_lines = admin_lines[:12]

        root_ok, root_out = ADBTools.run(
            ["-s", serial, "shell", "su", "-c", "id"], timeout=15
        )
        root_state = (
            "AVAILABLE (su returned uid=0)"
            if root_ok and "uid=0" in root_out
            else "NOT AVAILABLE (no root shell)"
        )

        lines = []
        lines.append("=" * 62)
        lines.append("            AYMTECH PRO - DEVICE SECURITY REPORT")
        lines.append("=" * 62)
        lines.append(f"Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"ADB serial: {serial}")
        lines.append("")
        lines.append("-------------- IDENTITY --------------")
        for label in ("Manufacturer", "Brand", "Model", "Device", "Android",
                      "SDK", "Build ID", "Fingerprint", "Security patch"):
            lines.append(f"{label:20} {_fmt(values.get(label, ''))}")

        lines.append("")
        lines.append("-------------- INTEGRITY --------------")
        lines.append(f"{'Bootloader':20} {Diagnostics.bootloader_state(values)}")
        lines.append(f"{'Verified boot':20} {_fmt(values.get('Verified boot', ''))}")
        lines.append(f"{'Verity mode':20} {_fmt(values.get('Verity mode', ''))}")
        lines.append(f"{'Encryption':20} {_fmt(values.get('Encryption', ''))}")
        lines.append(f"{'SELinux':20} {_fmt(values.get('SELinux', ''))}")
        lines.append(f"{'Knox':20} {Diagnostics.knox_state(values)}")
        lines.append(f"{'Root':20} {root_state}")

        lines.append("")
        lines.append("-------------- LOCKS ----------------")
        lines.extend(Diagnostics.frp_state(values, provisioned, setup))

        lock_ok, lock_out = DeviceLockState.read(serial)
        lines.append("")
        lines.extend(lock_out)

        if admin_lines:
            lines.append("")
            lines.append("-------------- MANAGED / ADMIN APPS --------")
            lines.extend(admin_lines)

        lines.append("")
        lines.append("-------------- WHAT THIS MEANS --------------")
        lines.append(
            "Locked bootloader + green verified boot + intact Knox means the\n"
            "phone runs stock, unmodified firmware: normal for a healthy unit."
        )
        lines.append(
            "An unlocked or orange/red bootloader means the phone was modified\n"
            "(custom recovery, patched vbmeta, or a corrupted image)."
        )
        lines.append(
            "FRP cannot be removed by ADB. It is cleared only by the original\n"
            "Google account, a proof-of-purchase request to the manufacturer,\n"
            "or a signed service firmware repair at an authorised centre."
        )
        return True, "\n".join(lines)

    # ------------------------------------------------------------------
    # battery / health
    # ------------------------------------------------------------------

    @staticmethod
    def battery_report(serial):
        ok, output = ADBTools.run(
            ["-s", serial, "shell", "dumpsys", "battery"], timeout=45
        )
        if not ok:
            return False, output

        interesting = (
            "level", "health", "status", "temperature", "voltage",
            "charge counter", "capacity", "cycle", "Charge time remaining",
            "Present", "Technology",
        )
        lines = ["========== BATTERY HEALTH ==========", ""]
        for line in output.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith(tuple(k.lower() for k in interesting)):
                lines.append(stripped)

        ok2, props = ADBTools.run(
            ["-s", serial, "shell", "dumpsys", "batterystats", "--charged"],
            timeout=60,
        )
        if ok2:
            for line in props.splitlines():
                if "Estimated battery capacity" in line or "cycle" in line.lower():
                    lines.append(line.strip())

        lines.append("")
        lines.append(
            "Android health scale: 1 unknown, 2 good, 3 overheat, 4 dead,\n"
            "5 over-voltage, 6 failure, 7 cold."
        )
        return True, "\n".join(lines)

    # ------------------------------------------------------------------
    # export
    # ------------------------------------------------------------------

    @staticmethod
    def export_report(text, folder=None):
        folder = folder or os.path.join(os.getcwd(), "reports")
        os.makedirs(folder, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(folder, f"aymtech_report_{stamp}.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return True, path


class DeviceLockState:
    """Best-effort screen-lock / keyguard inspection."""

    @staticmethod
    def read(serial):
        lines = []
        ok, window = ADBTools.run(
            ["-s", serial, "shell", "dumpsys", "window"], timeout=60
        )
        state = "UNKNOWN"
        if ok:
            text = window.lower()
            if "mshowinglockscreen=true" in text:
                state = "LOCKED (keyguard is showing)"
            elif "mshowinglockscreen=false" in text:
                state = "UNLOCKED (keyguard is not showing)"
        lines.append(f"{'Screen lock':20} {state}")

        ok2, secure = ADBTools.run(
            ["-s", serial, "shell", "dumpsys", "trust"], timeout=45
        )
        if ok2:
            text = secure.lower()
            if "device locked" in text:
                lines.append(f"{'Trust service':20} phone reports LOCKED")
            elif "device unlocked" in text:
                lines.append(f"{'Trust service':20} phone reports UNLOCKED")

        ok3, lsenabled = ADBTools.run(
            ["-s", serial, "shell", "settings", "get", "secure", "lockscreen.disabled"],
            timeout=20,
        )
        if ok3 and lsenabled.strip():
            value = lsenabled.strip()
            lines.append(
                f"{'Lockscreen disabled':20} {value}"
                "   (1 = lock screen skipped on wake)"
            )

        ok4, secure_lock = ADBTools.run(
            ["-s", serial, "shell", "settings", "get", "global", "secure_frp_mode"],
            timeout=20,
        )
        if ok4 and secure_lock.strip():
            lines.append(f"{'secure_frp_mode':20} {secure_lock.strip()}")

        lines.append(
            "\nNote: Android does not expose the PIN/pattern itself. If the\n"
            "phone is locked, ADB usually cannot be authorised at all, which\n"
            "is why a locked device shows 'not connected' here."
        )
        return True, lines
