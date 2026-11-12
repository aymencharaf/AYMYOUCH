import subprocess
import shutil
import os


class ADBTools:

    @staticmethod
    def check_adb():
        """Check whether ADB is installed."""
        return shutil.which("adb") is not None

    @staticmethod
    def run(args, timeout=30):
        """Execute an ADB command."""

        if not ADBTools.check_adb():
            return False, "ADB is not installed or not in PATH."

        try:
            result = subprocess.run(
                ["adb"] + args,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace"
            )

            output = result.stdout.strip()

            if result.stderr.strip():
                output += "\n" + result.stderr.strip()

            return result.returncode == 0, output

        except subprocess.TimeoutExpired:
            return False, "Command timed out."

        except Exception as error:
            return False, str(error)

    @staticmethod
    def devices():
        """List connected Android devices."""
        return ADBTools.run(["devices", "-l"])

    @staticmethod
    def device_info(serial):
        """Read basic Android device information."""

        properties = {
            "Manufacturer": "ro.product.manufacturer",
            "Brand": "ro.product.brand",
            "Model": "ro.product.model",
            "Device": "ro.product.device",
            "Android Version": "ro.build.version.release",
            "SDK Version": "ro.build.version.sdk",
            "Build ID": "ro.build.display.id",
            "Security Patch": "ro.build.version.security_patch",
        }

        results = [
            "========== DEVICE INFORMATION ==========",
            f"Serial Number: {serial}",
            ""
        ]

        for name, prop in properties.items():

            ok, value = ADBTools.run([
                "-s", serial,
                "shell", "getprop", prop
            ])

            results.append(
                f"{name}: {value if ok and value else 'Unavailable'}"
            )

        return "\n".join(results)

    @staticmethod
    def reboot(serial, mode="system"):
        """Reboot an Android device."""

        commands = {
            "system": ["reboot"],
            "recovery": ["reboot", "recovery"],
            "bootloader": ["reboot", "bootloader"],
        }

        if mode not in commands:
            return False, "Unsupported reboot mode."

        return ADBTools.run([
            "-s", serial
        ] + commands[mode])

    @staticmethod
    def install_apk(serial, apk_path):
        """Install an APK on the connected device."""

        if not os.path.isfile(apk_path):
            return False, "APK file does not exist."

        return ADBTools.run([
            "-s", serial,
            "install", "-r", apk_path
        ], timeout=120)

    @staticmethod
    def screenshot(serial, destination):
        """Capture and save the device screen as PNG."""

        if not ADBTools.check_adb():
            return False, "ADB is not installed."

        try:
            result = subprocess.run(
                [
                    "adb", "-s", serial,
                    "exec-out", "screencap", "-p"
                ],
                capture_output=True,
                timeout=30
            )

            if result.returncode != 0:
                error = result.stderr.decode(
                    "utf-8", errors="replace"
                )
                return False, error or "Screenshot failed."

            if not result.stdout:
                return False, "No screenshot data received."

            with open(destination, "wb") as file:
                file.write(result.stdout)

            return True, f"Screenshot saved: {destination}"

        except Exception as error:
            return False, str(error)

    @staticmethod
    def list_apps(serial):
        """List installed application packages."""

        return ADBTools.run([
            "-s", serial,
            "shell", "pm", "list", "packages"
        ], timeout=60)

    @staticmethod
    def get_battery(serial):
        """Read battery information."""

        return ADBTools.run([
            "-s", serial,
            "shell", "dumpsys", "battery"
        ])

    @staticmethod
    def get_storage(serial):
        """Read device storage information."""

        return ADBTools.run([
            "-s", serial,
            "shell", "df", "-h"
        ])

    @staticmethod
    def check_connection(serial):
        """Check whether a device is authorized."""

        ok, output = ADBTools.run([
            "devices"
        ])

        if not ok:
            return False, output

        for line in output.splitlines()[1:]:

            parts = line.split()

            if len(parts) >= 2 and parts[0] == serial:

                if parts[1] == "device":
                    return True, "Device connected and authorized."

                if parts[1] == "unauthorized":
                    return False, "USB debugging authorization required."

                if parts[1] == "offline":
                    return False, "Device is offline."

        return False, "Device not found."