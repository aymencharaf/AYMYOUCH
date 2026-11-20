"""IMEI, baseband and network identity inspection.

Real IMEI writing lives in the modem's NV partition. It is protected by the
baseband security model on every modern chipset, it is illegal in most
countries - and it destroys the phone's identity when it goes wrong. No ADB or
fastboot command can do it, and a tool that claims otherwise is either a paid
scam or a chip-level service that requires opening the device.

What a technician actually needs is here: read the identifiers the firmware
reports, prove whether the radio is alive (IMEI vs baseband vs SIM state), spot
blacklisted or duplicated identities, and produce a report that a repair
centre or the carrier will accept.
"""

from __future__ import annotations

import os
import re
from datetime import datetime

from .adb_tools import ADBTools

IMEI_PROPS = {
    "IMEI (slot 1)": "persist.radio.imei",
    "IMEI2 (slot 2)": "persist.radio.imei2",
    "IMEI (ro.ril)": "ril.gsm.imei",
    "MEID": "persist.radio.meid",
    "Serial": "ro.serialno",
    "Baseband": "gsm.version.baseband",
    "Radio state": "gsm.sim.state",
    "Operator": "gsm.operator.alpha",
    "Country": "gsm.operator.iso-country",
}

IMEI_RE = re.compile(r"\b(\d{15})\b")
LUN_LUHN_CHECK = True


def luhn_ok(number: str) -> bool:
    """IMEI uses the Luhn checksum; a wrong digit means a bad read or clone."""

    digits = [int(char) for char in number if char.isdigit()]
    if len(digits) != 15:
        return False
    checksum = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


class NetworkTools:

    # ------------------------------------------------------------------
    # identity reading
    # ------------------------------------------------------------------

    @staticmethod
    def identifiers(serial):
        values = {}
        for label, prop in IMEI_PROPS.items():
            ok, output = ADBTools.run(
                ["-s", serial, "shell", "getprop", prop], timeout=15
            )
            values[label] = output.strip() if ok else ""

        # service call is the most reliable IMEI source on many ROMs
        ok, service = ADBTools.run(
            ["-s", serial, "shell", "service", "call", "iphonesubinfo", "1"],
            timeout=20,
        )
        if ok:
            digits = "".join(char for char in service if char.isdigit())
            if len(digits) >= 15:
                values["IMEI (service call)"] = digits[:15]

        return values

    @staticmethod
    def identity_report(serial):
        values = NetworkTools.identifiers(serial)

        found = []
        for label, value in values.items():
            for candidate in IMEI_RE.findall(value or ""):
                if candidate not in [item[1] for item in found]:
                    found.append((label, candidate))

        baseband = values.get("Baseband", "")
        sim_state = values.get("Radio state", "")

        lines = ["=" * 60]
        lines.append("        AYMTECH PRO - IMEI / NETWORK IDENTITY")
        lines.append("=" * 60)
        lines.append(f"Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"ADB serial: {serial}")
        lines.append("")
        lines.append("-------------- IDENTIFIERS --------------")
        for label, value in values.items():
            shown = value if value else "not reported"
            lines.append(f"{label:20} {shown}")

        lines.append("")
        lines.append("-------------- IMEI ANALYSIS ------------")
        if not found:
            lines.append(
                "No IMEI was readable.\n\n"
                "Normal when the radio is off, the SIM is missing, or the\n"
                "ROM hides the identifier. It is also the signature of a\n"
                "damaged or erased (all-zero) modem NV partition."
            )
        for label, imei in found:
            verdict = "valid (Luhn OK)" if luhn_ok(imei) else "INVALID checksum"
            tac = imei[:8]
            lines.append(f"{imei}  from {label}")
            lines.append(f"{'':15}  TAC {tac}  ->  {verdict}")
            if set(imei) == {"0"}:
                lines.append(
                    f"{'':15}  All zeros: the modem NV data is erased. Only a\n"
                    f"{'':15}  modem/firmware repair at a service centre restores it."
                )
            elif not luhn_ok(imei):
                lines.append(
                    f"{'':15}  A bad checksum usually means a partial read or a\n"
                    f"{'':15}  cloned identity - check with the carrier."
                )

        if len(found) >= 2:
            lines.append("")
            lines.append("Dual SIM identifiers detected:")
            for label, imei in found[:2]:
                lines.append(f"  {label:18} {imei}")

        lines.append("")
        lines.append("-------------- RADIO HEALTH ------------")
        lines.append(f"Baseband        : {baseband or 'NOT REPORTED'}")
        lines.append(f"SIM state       : {sim_state or 'not reported'}")
        lines.append(f"Operator        : {values.get('Operator') or 'not reported'}")
        lines.append(f"Country         : {values.get('Country') or 'not reported'}")

        if not baseband:
            lines.append("")
            lines.append(
                "No baseband version: the modem firmware did not start.\n"
                "Typical causes: modem partition erased by a bad flash, an\n"
                "IC fault, or a CSC/CP mismatch. Calls and data will not work\n"
                "until the correct CP firmware is flashed."
            )
        elif sim_state and sim_state.upper() in ("ABSENT", ""):
            lines.append("")
            lines.append(
                "Baseband is alive but the SIM is absent: the IMEI is intact\n"
                "and the phone is fine - just insert a SIM to test the network."
            )
        else:
            lines.append("")
            lines.append(
                "Baseband is running and a SIM is reported: the radio path\n"
                "looks healthy. For network registration, check the signal\n"
                "strength and the carrier settings below."
            )

        lines.append("")
        lines.append("-------------- HONEST LIMITS -----------")
        lines.append(
            "ADB can only read what the firmware exposes. The IMEI lives in\n"
            "the modem NV partition, encrypted per-chipset; writing it needs a\n"
            "signed service tool or a hardware programmer, it is illegal in\n"
            "most countries, and a failed write leaves the phone with a\n"
            "permanently invalid identity."
        )
        return True, "\n".join(lines)

    # ------------------------------------------------------------------
    # network / radio diagnostics
    # ------------------------------------------------------------------

    @staticmethod
    def network_status(serial):
        lines = ["========== NETWORK STATUS ==========", ""]

        commands = [
            ("Radio state", ["shell", "getprop", "gsm.sim.state"]),
            ("Airplane mode", ["shell", "settings", "get", "global",
                               "airplane_mode_on"]),
            ("Data enabled", ["shell", "settings", "get", "global",
                              "mobile_data"]),
            ("Preferred network", ["shell", "settings", "get", "global",
                                   "preferred_network_mode"]),
            ("Wi-Fi state", ["shell", "settings", "get", "global", "wifi_on"]),
        ]
        for label, args in commands:
            ok, output = ADBTools.run(["-s", serial] + args, timeout=15)
            lines.append(f"{label:20} {(output or 'unknown').strip() if ok else 'unavailable'}")

        ok, signal = ADBTools.run(
            ["-s", serial, "shell", "dumpsys", "telephony.registry"], timeout=45
        )
        if ok:
            lines.append("")
            lines.append("-------------- SIGNAL --------------")
            for key in ("mSignalStrength", "mServiceState", "mDataConnectionState",
                        "mNetworkType", "mOperatorAlphaLong"):
                for raw in signal.splitlines():
                    if raw.strip().startswith(key):
                        lines.append(raw.strip()[:170])
                        break

        ok, ip = ADBTools.run(
            ["-s", serial, "shell", "ip", "-f", "inet", "addr", "show"], timeout=30
        )
        if ok:
            lines.append("")
            lines.append("-------------- ADDRESSES -----------")
            for raw in ip.splitlines():
                if "inet " in raw:
                    lines.append(raw.strip())

        return True, "\n".join(lines)

    # ------------------------------------------------------------------
    # report / service paths
    # ------------------------------------------------------------------

    @staticmethod
    def service_guide():
        return (
            "========== IMEI / BASEBAND SERVICE PATHS ==========\n\n"
            "1. IMEI shows 00000000000000 / not reported\n"
            "   -> the modem NV area is erased. Restore the CP (modem) firmware\n"
            "      for the exact model with Odin/Heimdall, then re-read.\n"
            "      If it stays empty, the modem IC needs a service centre.\n\n"
            "2. IMEI intact but no baseband version\n"
            "   -> CP partition damaged or mismatched: flash the matching CP.\n\n"
            "3. Baseband OK, SIM absent / no service\n"
            "   -> network or SIM problem, not an identity problem. Test another\n"
            "      SIM, check the carrier block, reset network settings.\n\n"
            "4. IMEI appears blocked by the operator (no registration although\n"
            "   everything else is fine)\n"
            "   -> only the carrier can lift a blacklist, usually with the\n"
            "      original purchase invoice or a police report.\n\n"
            "5. Phone bought second hand with a cloned/wrong IMEI\n"
            "   -> return it. Writing a different IMEI is illegal in most\n"
            "      countries and is not offered by this application."
        )

    @staticmethod
    def save_report(text, folder=None):
        folder = folder or os.path.join(os.getcwd(), "reports")
        os.makedirs(folder, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(folder, f"imei_report_{stamp}.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return True, path
