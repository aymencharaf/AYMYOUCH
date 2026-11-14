from tools.adb_tools import ADBTools


class SamsungTools:

    @staticmethod
    def device_information(serial):
        properties = {
            "Brand": "ro.product.brand",
            "Manufacturer": "ro.product.manufacturer",
            "Model": "ro.product.model",
            "Device": "ro.product.device",
            "Android Version": "ro.build.version.release",
            "Build ID": "ro.build.id",
            "Build Fingerprint": "ro.build.fingerprint",
            "Security Patch": "ro.build.version.security_patch",
            "Baseband": "gsm.version.baseband",
            "Bootloader": "ro.bootloader",
        }

        results = ["========== SAMSUNG DEVICE INFORMATION =========="]

        for label, prop in properties.items():
            ok, output = ADBTools.run([
                "-s", serial, "shell", "getprop", prop
            ])
            value = output.strip() if ok else "Not available"
            results.append(f"{label}: {value or 'Not available'}")

        return True, "\n".join(results)

    @staticmethod
    def check_samsung_device(serial):
        ok, output = ADBTools.run([
            "-s", serial, "shell", "getprop",
            "ro.product.manufacturer"
        ])

        if not ok:
            return False, output

        manufacturer = output.strip().lower()

        if "samsung" in manufacturer:
            return True, "Samsung device detected."

        return False, f"Not a Samsung device: {manufacturer}"

    @staticmethod
    def check_connection(serial):
        return ADBTools.check_connection(serial)

    @staticmethod
    def firmware_information(serial):
        return SamsungTools.device_information(serial)
