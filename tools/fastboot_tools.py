"""Fastboot engine (bootloader / recovery operations).

Every method is a static function that returns ``(ok, output)`` and is safe
to call from a worker thread: no Qt objects, no global state.  Where a device
must be selected, ``serial`` may be ``None`` to use the only connected unit.

Bootloader operations are genuinely destructive, so the destructive helpers
are explicit (``flash``, ``erase``, ``format``) and the UI always asks for a
typed confirmation before calling them.
"""

from __future__ import annotations

from . import proc

ACTIONS = {
    "devices": ["devices"],
    "getvar_all": ["getvar", "all"],
    "getvar_unlocked": ["getvar", "unlocked"],
    "getvar_current-slot": ["getvar", "current-slot"],
    "getvar_product": ["getvar", "product"],
    "getvar_version-bootloader": ["getvar", "version-bootloader"],
    "getvar_secure": ["getvar", "secure"],
    "reboot_bootloader": ["reboot", "bootloader"],
    "reboot_recovery": ["reboot", "recovery"],
    "reboot_system": ["reboot"],
    "continue": ["continue"],
}


class FastbootTools:

    # ------------------------------------------------------------------
    # availability / discovery
    # ------------------------------------------------------------------

    @staticmethod
    def available() -> bool:
        return proc.which("fastboot") is not None

    @staticmethod
    def _with_serial(serial, args):
        base = ["fastboot"]
        if serial:
            base += ["-s", serial]
        return base + list(args)

    @staticmethod
    def run(args, serial=None, timeout: int = 60):
        if not FastbootTools.available():
            return False, (
                "fastboot was not found.\n\n"
                "Install Android Platform-Tools and add the folder to PATH:\n"
                "https://developer.android.com/tools/releases/platform-tools"
            )
        return proc.run(FastbootTools._with_serial(serial, args), timeout=timeout)

    @staticmethod
    def parse_devices(output: str):
        devices = []
        for line in output.splitlines():
            line = line.strip()
            if not line or line.lower().startswith("< waiting"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                devices.append(
                    {"serial": parts[0], "state": parts[1],
                     "details": " ".join(parts[2:])}
                )
        return devices

    @staticmethod
    def devices():
        ok, output = FastbootTools.run(["devices"], timeout=20)
        if not ok:
            return False, output
        found = FastbootTools.parse_devices(output)
        if not found:
            return True, (
                "No device in fastboot mode.\n\n"
                "To enter the bootloader, run:  adb reboot bootloader\n"
                "or hold Volume-Down + Power while the phone is off."
            )
        lines = [f"{len(found)} device(s) in fastboot mode:", ""]
        for device in found:
            lines.append(
                f"  {device['serial']}   {device['state']}  {device['details']}".rstrip()
            )
        return True, "\n".join(lines)

    # ------------------------------------------------------------------
    # information
    # ------------------------------------------------------------------

    @staticmethod
    def variables(serial=None):
        ok, output = FastbootTools.run(["getvar", "all"], serial, timeout=45)
        if not ok and not output:
            return False, "fastboot could not read the device variables."
        return True, FastbootTools.format_variables(output)

    @staticmethod
    def format_variables(output: str) -> str:
        """Turn the noisy ``getvar all`` stream into readable key/value lines."""

        values = {}
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.lower().startswith(("(bootloader)", "fastboot:")):
                line = line.split(")", 1)[-1].strip()
                line = line.replace("fastboot:", "", 1).strip()
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip().lower()
            if not key or " " in key:
                continue
            values[key] = value.strip()

        if not values:
            return "DEVICE VARIABLES\n" + output

        important = [
            "product", "variant", "serialno", "secure", "unlocked",
            "current-slot", "slot-count", "version-bootloader",
            "version-baseband", "hw-revision", "battery-voltage", "max-download-size",
        ]

        lines = []
        seen = set()
        for key in important:
            if key in values:
                lines.append(f"{key:24} {values[key]}")
                seen.add(key)
        remaining = sorted(k for k in values if k not in seen)
        if remaining:
            lines.append("")
            lines.append("---------------- other variables -----------------")
            for key in remaining:
                lines.append(f"{key:24} {values[key]}")
        return "\n".join(lines)

    @staticmethod
    def is_unlocked(serial=None):
        """Return ``(known, unlocked, raw)`` for the bootloader lock state."""

        for key in ("unlocked", "oem-unlock", "secure"):
            ok, output = FastbootTools.run(["getvar", key], serial, timeout=25)
            text = output.lower()
            if not ok and not text:
                continue
            if key == "secure":
                if "secure: yes" in text or "secure:yes" in text:
                    return True, False, output
                if "secure: no" in text or "secure:no" in text:
                    return True, True, output
                continue
            if "unlocked: yes" in text or "unlocked:yes" in text:
                return True, True, output
            if "unlocked: no" in text or "unlocked:no" in text:
                return True, False, output
        return False, None, "The bootloader lock state could not be read."

    # ------------------------------------------------------------------
    # modes
    # ------------------------------------------------------------------

    @staticmethod
    def reboot(mode, serial=None):
        args = {"bootloader": ["reboot", "bootloader"],
                "recovery": ["reboot", "recovery"],
                "system": ["reboot"],
                "fastbootd": ["reboot", "fastboot"]}.get(mode)
        if args is None:
            return False, f"Unknown reboot mode: {mode}"
        ok, output = FastbootTools.run(args, serial, timeout=30)
        return ok, output or f"Device is restarting into {mode}."

    # ------------------------------------------------------------------
    # destructive operations (UI must confirm first)
    # ------------------------------------------------------------------

    @staticmethod
    def flash(partition, image_path, serial=None):
        if not partition.strip():
            return False, "No partition selected."
        ok, output = FastbootTools.run(
            ["flash", partition.strip(), image_path], serial, timeout=600
        )
        if ok:
            return True, f"Flashed {partition} with:\n{image_path}\n\n{output}".strip()
        return False, output

    @staticmethod
    def erase(partition, serial=None):
        ok, output = FastbootTools.run(
            ["erase", partition.strip()], serial, timeout=180
        )
        if ok:
            return True, f"Erased partition: {partition}\n\n{output}".strip()
        return False, output

    @staticmethod
    def format_partition(partition, serial=None):
        ok, output = FastbootTools.run(
            ["format", partition.strip()], serial, timeout=300
        )
        if ok:
            return True, f"Formatted partition: {partition}\n\n{output}".strip()
        return False, output

    @staticmethod
    def set_active_slot(slot, serial=None):
        ok, output = FastbootTools.run(
            ["--set-active=" + slot.strip()], serial, timeout=60
        )
        return ok, output or f"Active slot set to {slot}."

    @staticmethod
    def unlock(serial=None):
        ok, output = FastbootTools.run(["flashing", "unlock"], serial, timeout=120)
        if not ok:
            return False, (
                f"{output}\n\n"
                "The unlock command may need to be confirmed on the phone "
                "screen, and it erases all user data."
            )
        return True, output

    @staticmethod
    def device_guide():
        """Explain honestly what a bootloader unlock can and cannot do."""

        return (
            "=========== BOOTLOADER UNLOCK - READ FIRST ===========\n\n"
            "A fastboot unlock only works when the manufacturer allows it.\n\n"
            "CAN be unlocked by the user (OEM unlocking switch in Developer options):\n"
            "  Pixel, Nothing, many Motorola, Sony, Xiaomi (after 168h waiting\n"
            "  period, via Mi Unlock), OnePlus and some ASUS models.\n\n"
            "CANNOT be unlocked through fastboot:\n"
            "  Samsung (Knox - only 'OEM LOCK : ON (U)' in download mode,\n"
            "  no unlock path), Huawei/Honor (needs a vendor code), most\n"
            "  Oppo/Realme/vivo units, and any device with a carrier lock.\n\n"
            "Consequences of unlocking:\n"
            "  - ALL user data is erased (wipes /data).\n"
            "  - Warranty is usually voided; Knox/Play Integrity may break.\n"
            "  - Some banking and DRM apps stop working.\n\n"
            "AYMTECH PRO never bypasses a lock that the manufacturer did not\n"
            "authorise. It reports the lock state and runs the official commands\n"
            "so you can see the real answer from the phone itself."
        )
