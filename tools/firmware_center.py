"""Firmware library and matching for the flashing centre.

A flashing job is only safe when four things agree: the model, the region
(CSC), the ROM family and the file itself.  This module identifies a firmware
package, extracts the model/region it belongs to, checks its integrity and
builds the exact command a technician would run with Odin / Heimdall /
idevicerestore / SP Flash — without ever executing anything.
"""

from __future__ import annotations

import hashlib
import os
import re
import zipfile
from datetime import datetime
from pathlib import Path

# Samsung: PDA/version + CSC in the archive name, e.g.
#   AP_G973FXXSGHWC1_CL22642592_QB60812345_REV00_user_low_ship.tar.md5
SAMSUNG_CSC = (
    "ACR", "AFR", "ARB", "BKD", "BNG", "BTC", "BVO", "CAC", "CEL", "COO",
    "DBT", "DKR", "EGY", "ETL", "EVR", "FWD", "GLB", "ILO", "INS", "ITV",
    "KSA", "LYS", "MAT", "MID", "MOT", "MWD", "NEE", "NPL", "O2U", "OJM",
    "OMN", "ORX", "PAK", "PHE", "PHN", "SEB", "SEE", "SER", "SFR", "SIM",
    "SIO", "TPH", "TUN", "TUR", "XAA", "XEF", "XEO", "XEU", "XFA", "XFE",
    "XFV", "XME", "XNZ", "XSA", "XSG", "XSP", "XTC", "XEF",
)

SAMSUNG_MODEL = re.compile(r"SM-[A-Z]\d{3,4}[A-Z0-9]?", re.IGNORECASE)
# Samsung packages often drop the SM- prefix: AP_G973FXXSGHWC1_CL22642592...
SAMSUNG_AP_NAME = re.compile(
    r"^(?:AP|BL|CP|CSC|HOME_CSC)_([A-Z]\d{3,4}[A-Z0-9]?)([A-Z0-9]{4,})_", re.IGNORECASE
)
# regional all-in-one package: G973FXXSGHWC1_G973FOXAGWHB_XEF.tar.md5
SAMSUNG_COMBINED = re.compile(r"^([A-Z]\d{3,4}[A-Z0-9]?)[A-Z]{3}[A-Z0-9]{4,}_", re.IGNORECASE)
SAMSUNG_VERSION = re.compile(r"\b([A-Z]\d{3}[A-Z0-9]{5,})\b")
SAMSUNG_BUILD_DATE = re.compile(r"_(?:QB|CL)\d+")
CSC_TOKEN = re.compile(r"\b([A-Z]{3})\b")


class FlashJob:
    """One planned operation, ready to be shown or exported."""

    def __init__(self, title, command, notes, risk="medium"):
        self.title = title
        self.command = command
        self.notes = notes
        self.risk = risk

    def render(self):
        lines = [f"### {self.title}", "", "Command:", f"  {self.command}", ""]
        if self.notes:
            lines.append("Notes:")
            for note in self.notes:
                lines.append(f"  - {note}")
            lines.append("")
        lines.append(f"Risk: {self.risk.upper()}")
        return "\n".join(lines)


class FirmwareCenter:

    # ------------------------------------------------------------------
    # identification
    # ------------------------------------------------------------------

    @staticmethod
    def identify(path):
        """Read model / region / version out of a package name."""

        name = os.path.basename(path)
        upper = name.upper()

        info = {
            "name": name,
            "size_mb": 0.0,
            "model": "",
            "region": "",
            "version": "",
            "vendor": FirmwareCenter.vendor_of(name),
            "family": "",
        }

        if os.path.isfile(path):
            info["size_mb"] = os.path.getsize(path) / (1024 * 1024)

        model = SAMSUNG_MODEL.search(upper)
        if model:
            info["model"] = model.group(0).upper()
        else:
            ap_name = SAMSUNG_AP_NAME.search(name)
            if ap_name:
                info["model"] = f"SM-{ap_name.group(1).upper()}"

        info["region"] = FirmwareCenter.region_of(name)

        version = SAMSUNG_VERSION.search(upper)
        if version:
            info["version"] = version.group(1)
        else:
            ap_name = SAMSUNG_AP_NAME.search(name)
            if ap_name:
                info["version"] = ap_name.group(2)

        info["family"] = FirmwareCenter.family_of(info)

        lines = [
            "================ FIRMWARE IDENTIFICATION ================",
            f"File      : {info['name']}",
            f"Size      : {info['size_mb']:.1f} MB",
            f"Vendor    : {info['vendor'] or 'not detected'}",
            f"Model     : {info['model'] or 'not detected'}",
            f"Region    : {info['region'] or 'not detected'}",
            f"Version   : {info['version'] or 'not detected'}",
            f"Family    : {info['family'] or 'unknown'}",
            "",
            "Check the model and the region against the phone before flashing:",
            "a mismatched CSC flashes but breaks calls/updates, and a wrong",
            "model hard-bricks the device.",
        ]
        return True, "\n".join(lines)

    @staticmethod
    def region_of(name):
        """Region/CSC code inside a package name (``_XEF_``, ``XXV``, ...)."""

        upper = os.path.basename(name or "").upper()
        # a CSC standing alone between separators is the strongest signal
        for token in re.split(r"[_\-.]", upper):
            if token in SAMSUNG_CSC:
                return token
        for token in CSC_TOKEN.findall(upper):
            if token in SAMSUNG_CSC:
                return token
        return ""

    @staticmethod
    def model_of(name_or_model):
        """Normalise ``SM-G973F`` / ``G973F`` / a package name to ``SM-G973F``."""

        text = os.path.basename(name_or_model or "").upper()
        match = SAMSUNG_MODEL.search(text)
        if match:
            return match.group(0).upper()
        match = SAMSUNG_AP_NAME.search(text)
        if match:
            return f"SM-{match.group(1).upper()}"
        match = SAMSUNG_COMBINED.search(text)
        if match:
            return f"SM-{match.group(1).upper()}"
        bare = re.fullmatch(r"([A-Z]\d{3,4}[A-Z0-9]?)", text)
        if bare:
            return f"SM-{bare.group(1)}"
        return ""

    @staticmethod
    def vendor_of(name):
        lower = name.lower()
        if lower.startswith("sm-") or "samsung" in lower or lower.endswith(
            (".tar.md5", ".tar", ".kdz", ".ofp")
        ):
            return "Samsung"
        if lower.endswith(".ftf"):
            return "Sony"
        if lower.endswith((".tgz", "fastboot")) or "xiaomi" in lower or "miui" in lower:
            return "Xiaomi"
        if lower.endswith(".pac") or "spreadtrum" in lower:
            return "MediaTek / Unisoc (SP Flash)"
        if lower.endswith(".ipsw"):
            return "Apple"
        if "factory" in lower or "boot.img" in lower or lower.endswith(".img"):
            return "Generic Android"
        return ""

    @staticmethod
    def family_of(info):
        vendor = info.get("vendor", "")
        if vendor == "Samsung":
            return "Samsung Odin / Heimdall"
        if vendor == "Apple":
            return "Apple restore (idevicerestore / Finder)"
        if vendor.startswith("MediaTek"):
            return "SP Flash Tool (scatter)"
        if vendor == "Sony":
            return "Sony Flashtool (FTF)"
        if vendor == "Xiaomi":
            return "Xiaomi fastboot ROM"
        return "Generic fastboot images"

    # ------------------------------------------------------------------
    # integrity
    # ------------------------------------------------------------------

    @staticmethod
    def hash_file(path, algorithm="sha256", progress=None):
        if not os.path.isfile(path):
            return False, f"File not found: {path}"

        digest = hashlib.new(algorithm)
        total = max(1, os.path.getsize(path))
        done = 0

        try:
            with open(path, "rb") as handle:
                while True:
                    chunk = handle.read(4 * 1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                    done += len(chunk)
                    if progress is not None:
                        progress(int(done * 100 / total))
        except OSError as error:
            return False, str(error)

        return True, digest.hexdigest()

    @staticmethod
    def md5_sidecar(path):
        """Samsung packages ship as ``*.tar.md5``; the name is the checksum."""

        name = os.path.basename(path)
        match = re.search(r"\.tar\.md5$", name, re.IGNORECASE)
        if not match:
            return False, (
                "This file is not a .tar.md5 package, so its name does not "
                "carry a checksum. Use the SHA-256 check instead."
            )

        ok, md5 = FirmwareCenter.hash_file(path, "md5")
        if not ok:
            return False, md5
        return True, (
            f"MD5 of the file:\n  {md5}\n\n"
            "Compare it with the checksum published by the firmware source\n"
            "(SamMobile / Frija / the vendor portal). A mismatch means the\n"
            "download was corrupted or tampered with: do not flash it."
        )

    @staticmethod
    def inspect_archive(path):
        """List the partitions inside a flashable archive."""

        if not os.path.isfile(path):
            return False, f"File not found: {path}"

        lower = path.lower()

        if lower.endswith(".zip"):
            try:
                with zipfile.ZipFile(path) as archive:
                    entries = [
                        (info.filename, info.file_size)
                        for info in archive.infolist()
                        if not info.is_dir()
                    ]
            except zipfile.BadZipFile:
                return False, "The archive is not a valid ZIP file."
            except OSError as error:
                return False, str(error)
        elif lower.endswith((".tar", ".tar.md5")):
            return True, (
                "TAR package (Samsung Odin format).\n\n"
                "Partitions are not listed to avoid loading the whole file;\n"
                "flash it with the Odin/Heimdall plan below. A correct package\n"
                "contains BL, AP, CP and CSC/HOME_CSC files.\n\n"
                "Expected slots:\n"
                "  BL  bootloader      (risky - never flash a BL from another model)\n"
                "  AP  system + boot   (the main firmware)\n"
                "  CP  modem           (needed for calls)\n"
                "  CSC user data + region settings (wipes data)\n"
                "  HOME_CSC keeps user data"
            )
        else:
            return False, "Not an archive. Use the information panel for single images."

        lines = [f"{len(entries)} file(s) inside {os.path.basename(path)}:", ""]
        for name, size in sorted(entries, key=lambda item: -item[1])[:40]:
            lines.append(f"  {size / (1024 * 1024):9.1f} MB  {name}")

        ap = [n for n, _ in entries if os.path.basename(n).upper().startswith("AP_")]
        bl = [n for n, _ in entries if os.path.basename(n).upper().startswith("BL_")]
        cp = [n for n, _ in entries if os.path.basename(n).upper().startswith("CP_")]
        csc = [n for n, _ in entries if "CSC" in os.path.basename(n).upper()]

        lines.append("")
        for label, found in (("BL", bl), ("AP", ap), ("CP", cp), ("CSC", csc)):
            lines.append(f"{label:4} {'present' if found else 'MISSING'}")

        if not (bl and ap):
            lines.append("")
            lines.append(
                "A flashable Samsung package needs at least BL and AP.\n"
                "Do not flash a partial package."
            )
        return True, "\n".join(lines)

    # ------------------------------------------------------------------
    # plan builder
    # ------------------------------------------------------------------

    @staticmethod
    def build_plan(path, model="", region=""):
        if not os.path.isfile(path):
            return False, f"File not found: {path}"

        info = {
            "name": os.path.basename(path),
            "vendor": FirmwareCenter.vendor_of(path),
        }
        family = FirmwareCenter.family_of(info)
        name = os.path.basename(path)
        warnings = []

        if model:
            package_model = FirmwareCenter.model_of(name)
            phone_model = FirmwareCenter.model_of(model)
            if package_model and phone_model and package_model != phone_model:
                warnings.append(
                    f"MODEL MISMATCH: the package is for {package_model} "
                    f"but the phone reports {phone_model}."
                )

        if region:
            detected_region = FirmwareCenter.region_of(name)
            if detected_region and detected_region != region.strip().upper():
                warnings.append(
                    f"REGION MISMATCH: package CSC {detected_region} vs phone "
                    f"{region.strip().upper()}. Calls, updates or OTA may fail."
                )

        if family == "Samsung Odin / Heimdall":
            if os.path.isdir(path):
                jobs = [
                    FlashJob(
                        "Heimdall (Linux / macOS / Windows)",
                        "heimdall flash --BL bootloader.img --AP firmware.img "
                        "--CP modem.bin --CSC csc.img --no-reboot",
                        [
                            "Extract the .tar.md5 first and map each file to its slot.",
                            "Add --no-reboot while you verify the log, then reboot manually.",
                            "A wrong BL from another model bricks the phone.",
                        ],
                        "high",
                    ),
                    FlashJob(
                        "Odin (Windows)",
                        "Odin3.exe  (AP / BL / CP / CSC slots)",
                        [
                            "Load AP, BL, CP and CSC in their matching slots only.",
                            "Use HOME_CSC to keep user data, CSC to wipe it.",
                            "Enable 'F. Reset Time' only; never tick repartition.",
                        ],
                        "high",
                    ),
                ]
                body = "\n\n".join(job.render() for job in jobs)
            else:
                body = FlashJob(
                    "Samsung package",
                    "Extract the archive, then flash BL / AP / CP / CSC with "
                    "Odin (Windows) or Heimdall (any OS).",
                    [
                        "AP holds the system and boot images.",
                        "CP is the modem: calls fail if it is skipped.",
                        "CSC wipes data; HOME_CSC keeps it.",
                    ],
                    "high",
                ).render()

        elif family == "Generic fastboot images":
            slot = ""
            body = FlashJob(
                "Fastboot images",
                "fastboot flash boot boot.img && fastboot flash system system.img "
                "&& fastboot reboot",
                [
                    "Confirm the device is unlocked: fastboot getvar unlocked.",
                    "A/B devices need --slot=all or the active slot explicitly.",
                    "Never flash a system image signed for another model.",
                ],
                "high",
            ).render()
            if slot:
                body += f"\n\n{slot}"

        elif family == "Xiaomi fastboot ROM":
            body = FlashJob(
                "Xiaomi fastboot ROM",
                "Extract the tgz, run flash_all.bat (erases data) or "
                "flash_all_except_storage.bat (keeps internal storage).",
                [
                    "The device must be bootloader-unlocked (Mi Unlock).",
                    "Do not mix a China ROM and a Global ROM on a locked unit.",
                ],
                "high",
            ).render()

        elif family == "SP Flash Tool (scatter)":
            body = FlashJob(
                "SP Flash Tool",
                "SPFlashTool  ->  Download tab  ->  select scatter file  "
                "->  Download Only / Firmware Upgrade",
                [
                    "Use 'Firmware Upgrade' only for a full repair; it wipes data.",
                    "A wrong preloader brick the phone permanently.",
                    "Keep the battery charged and never unplug during download.",
                ],
                "high",
            ).render()

        elif family == "Apple restore (idevicerestore / Finder)":
            body = FlashJob(
                "iPhone restore",
                "idevicerestore -e   (or Finder -> Restore iPhone)",
                [
                    "Only Apple-signed firmware is accepted; older IPSWs fail.",
                    "DFU is required for a full restore.",
                    "Activation Lock survives a restore - it is not bypassed.",
                ],
                "high",
            ).render()

        else:
            body = FlashJob(
                "Unknown package",
                "(no command generated)",
                ["The vendor of this file could not be identified."],
                "high",
            ).render()

        header = [
            "================ FLASH PLAN ================",
            f"Package : {name}",
            f"Family  : {family}",
            "",
        ]
        if warnings:
            header.append("!! " + "\n!! ".join(warnings))
            header.append("")
        else:
            header.append("Package name matches the phone. Verify the file hash next.")
            header.append("")

        return True, "\n".join(header) + body

    # ------------------------------------------------------------------
    # workspace
    # ------------------------------------------------------------------

    @staticmethod
    def library(folder):
        """List firmware packages in a folder with their identity."""

        path = Path(folder)
        if not path.is_dir():
            return False, f"Folder not found: {folder}"

        entries = []
        for item in sorted(path.iterdir()):
            if not item.is_file():
                continue
            if item.suffix.lower() not in (
                ".zip", ".tar", ".md5", ".img", ".bin", ".kdz", ".ofp",
                ".ftf", ".tgz", ".pac", ".ipsw", ".lz4", ".mbn",
            ):
                continue
            size_mb = item.stat().st_size / (1024 * 1024)
            model = SAMSUNG_MODEL.search(item.name.upper())
            entries.append(
                {
                    "name": item.name,
                    "path": str(item),
                    "size_mb": size_mb,
                    "model": model.group(0).upper() if model else "",
                    "vendor": FirmwareCenter.vendor_of(item.name),
                }
            )

        if not entries:
            return True, (
                f"No firmware packages in:\n{folder}\n\n"
                "Put the .tar.md5 / .zip / .img packages there and refresh."
            )

        lines = [f"{len(entries)} package(s) in {folder}", ""]
        for entry in entries:
            model = f" [{entry['model']}]" if entry["model"] else ""
            lines.append(
                f"  {entry['size_mb']:8.1f} MB  {entry['name']}{model}"
            )
        return True, "\n".join(lines)

    @staticmethod
    def export_plan(text, folder=None):
        folder = folder or os.path.join(os.getcwd(), "reports")
        os.makedirs(folder, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(folder, f"flash_plan_{stamp}.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return True, path
