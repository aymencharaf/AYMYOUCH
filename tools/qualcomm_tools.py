from tools.adb_tools import ADBTools


class QualcommTools:

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
            "Baseband": "gsm.version.baseband",
            "Bootloader": "ro.bootloader",
        }

        results = ["========== QUALCOMM DEVICE INFORMATION =========="]

        for label, prop in properties.items():
            ok, output = ADBTools.run([
                "-s", serial, "shell", "getprop", prop
            ])

            value = output.strip() if ok else "Not available"
            results.append(f"{label}: {value or 'Not available'}")

        return True, "\n".join(results)

    @staticmethod
    def check_qualcomm_device(serial):
        ok, platform = ADBTools.run([
            "-s", serial, "shell", "getprop", "ro.board.platform"
        ])

        if not ok:
            return False, platform

        ok, manufacturer = ADBTools.run([
            "-s", serial, "shell", "getprop", "ro.product.manufacturer"
        ])

        if not ok:
            return False, manufacturer

        platform = platform.strip()
        manufacturer = manufacturer.strip()

        if "qcom" in platform.lower() or "qualcomm" in platform.lower():
            return True, f"Qualcomm platform detected: {platform}"

        return False, (
            "Qualcomm platform not confirmed.\n"
            f"Platform: {platform or 'Unknown'}\n"
            f"Manufacturer: {manufacturer or 'Unknown'}"
        )

    @staticmethod
    def check_connection(serial):
        return ADBTools.check_connection(serial)

    @staticmethod
    def firmware_information(serial):
        return QualcommTools.device_information(serial)
