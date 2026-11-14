from tools.adb_tools import ADBTools


class AndroidTools:

    @staticmethod
    def full_diagnostic(serial):
        results = []

        results.append("========== ANDROID DIAGNOSTIC ==========")

        # Connection
        ok, output = ADBTools.check_connection(serial)
        results.append(f"\n[CONNECTION]\n{output}")

        if not ok:
            return False, "\n".join(results)

        # Device information
        results.append("\n[DEVICE INFORMATION]")
        results.append(ADBTools.device_info(serial))

        # Battery
        ok, output = ADBTools.get_battery(serial)
        results.append(f"\n[BATTERY]\n{output}")

        # Storage
        ok, output = ADBTools.get_storage(serial)
        results.append(f"\n[STORAGE]\n{output}")

        # Android properties
        ok, output = ADBTools.run([
            "-s", serial,
            "shell", "getprop",
            "ro.build.version.release"
        ])

        results.append(
            f"\n[ANDROID VERSION]\n{output}"
        )

        return True, "\n".join(results)

    @staticmethod
    def battery_health(serial):
        return ADBTools.get_battery(serial)

    @staticmethod
    def storage_analysis(serial):
        return ADBTools.get_storage(serial)

    @staticmethod
    def installed_apps(serial):
        return ADBTools.list_apps(serial)

    @staticmethod
    def device_connection(serial):
        return ADBTools.check_connection(serial)