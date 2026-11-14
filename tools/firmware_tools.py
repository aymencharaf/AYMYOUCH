import hashlib
from pathlib import Path
from datetime import datetime


class FirmwareTools:

    FIRMWARE_EXTENSIONS = {
        ".zip", ".img", ".bin", ".tar", ".md5",
        ".mbn", ".xml", ".ofp", ".kdz", ".ftf",
        ".ipsw", ".ops", ".pac", ".scatter",
        ".br", ".dat", ".lz4"
    }

    @staticmethod
    def get_firmware_files(folder):
        path = Path(folder)

        if not path.exists() or not path.is_dir():
            return False, "Firmware folder does not exist."

        files = []

        for item in path.iterdir():
            if item.is_file() and (
                item.suffix.lower() in FirmwareTools.FIRMWARE_EXTENSIONS
            ):
                files.append({
                    "name": item.name,
                    "path": str(item.resolve()),
                    "size": item.stat().st_size,
                    "extension": item.suffix.lower()
                })

        return True, files

    @staticmethod
    def file_information(file_path):
        path = Path(file_path)

        if not path.exists() or not path.is_file():
            return False, "Firmware file not found."

        stat = path.stat()

        size_mb = stat.st_size / (1024 * 1024)
        modified = datetime.fromtimestamp(
            stat.st_mtime
        ).strftime("%Y-%m-%d %H:%M:%S")

        information = [
            "========== FIRMWARE INFORMATION ==========",
            f"File Name: {path.name}",
            f"Extension: {path.suffix.lower()}",
            f"Full Path: {path.resolve()}",
            f"Size: {size_mb:.2f} MB",
            f"Modified: {modified}",
        ]

        return True, "\n".join(information)

    @staticmethod
    def calculate_sha256(file_path):

        path = Path(file_path)

        if not path.exists() or not path.is_file():
            return False, "Firmware file not found."

        sha256 = hashlib.sha256()

        try:
            with path.open("rb") as firmware:
                for chunk in iter(
                    lambda: firmware.read(1024 * 1024), b""
                ):
                    sha256.update(chunk)

            return True, sha256.hexdigest()

        except OSError as error:
            return False, str(error)

    @staticmethod
    def create_firmware_folder(folder):
        path = Path(folder)

        try:
            path.mkdir(parents=True, exist_ok=True)
            return True, f"Firmware folder ready: {path.resolve()}"
        except OSError as error:
            return False, str(error)
