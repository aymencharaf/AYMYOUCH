from tools.adb_tools import ADBTools


class MediaTekTools:

    @staticmethod
    def device_information(serial):
        properties = {
            "Manufacturer": "ro.product.manufacturer",
            "Model": "ro.product.model",
            "Device": "ro.product.device",
            "Android Version": "ro.build.version.release",
            "Build ID": "ro.build.id",
            "Security Patch": "ro.build.version.security_patch",
            "Hardware": "ro.hardware",
            "Platform": "ro.board.platform",
            "CPU Architecture": "ro.product.cpu.abi",
            "Bootloader": "ro.bootloader",
            "Baseband": "gsm.version.baseband",
        }

        results = ["========== MEDIATEK DEVICE INFORMATION =========="]

        for label, prop in properties.items():
            ok, output = ADBTools.run([
                "-s", serial, "shell", "getprop", prop
            ])

            value = output.strip() if ok else "Not available"
            results.append(f"{label}: {value or 'Not available'}")

        return True, "\n".join(results)

    @staticmethod
    def check_mediatek_device(serial):
        ok, platform = ADBTools.run([
            "-s", serial, "shell", "getprop", "ro.board.platform"
        ])

        if not ok:
            return False, platform

        ok, hardware = ADBTools.run([
            "-s", serial, "shell", "getprop", "ro.hardware"
        ])

        if not ok:
            return False, hardware

        platform = platform.strip()
        hardware = hardware.strip()

        indicators = ("mt", "mediatek")

        if any(x in platform.lower() for x in indicators):
            return True, f"MediaTek platform detected: {platform}"

        if any(x in hardware.lower() for x in indicators):
            return True, f"MediaTek hardware detected: {hardware}"

        return False, (
            "MediaTek chipset not confirmed.\n"
            f"Platform: {platform or 'Unknown'}\n"
            f"Hardware: {hardware or 'Unknown'}"
        )

    @staticmethod
    def check_connection(serial):
        return ADBTools.check_connection(serial)

    @staticmethod
    def firmware_information(serial):
        return MediaTekTools.device_information(serial)
