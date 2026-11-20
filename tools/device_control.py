"""ADB device control: navigation, text input, apps, files and logs.

These are the operations a technician actually repeats all day: wake the
screen, type a PIN, open settings, install or uninstall, pull a photo, read
logcat.  Everything returns ``(ok, output)`` and stays UI-free.
"""

from __future__ import annotations

import os

from .adb_tools import ADBTools


class DeviceControl:

    # ------------------------------------------------------------------
    # key events (KEYCODE_* names accepted, e.g. "KEYCODE_HOME")
    # ------------------------------------------------------------------

    @staticmethod
    def key(serial, keycode):
        code = str(keycode).strip().upper()
        if code.isdigit():
            args = ["shell", "input", "keyevent", code]
        else:
            args = ["shell", "input", "keyevent", code]
        ok, output = ADBTools.run(["-s", serial] + args, timeout=20)
        return ok, output or f"Key {code} sent."

    @staticmethod
    def text(serial, message):
        if not message:
            return False, "Nothing to type."
        # spaces must be escaped for the shell
        escaped = message.replace(" ", "%s").replace("'", "")
        ok, output = ADBTools.run(
            ["-s", serial, "shell", "input", "text", escaped], timeout=30
        )
        return ok, output or f"Typed {len(message)} character(s)."

    @staticmethod
    def tap(serial, x, y):
        ok, output = ADBTools.run(
            ["-s", serial, "shell", "input", "tap", str(int(x)), str(int(y))],
            timeout=20,
        )
        return ok, output or f"Tapped ({x}, {y})."

    @staticmethod
    def swipe(serial, x1, y1, x2, y2, duration=300):
        ok, output = ADBTools.run(
            ["-s", serial, "shell", "input", "swipe",
             str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(int(duration))],
            timeout=30,
        )
        return ok, output or "Swipe sent."

    @staticmethod
    def wake(serial):
        ADBTools.run(["-s", serial, "shell", "input", "keyevent", "KEYCODE_WAKEUP"])
        ok, output = ADBTools.run(
            ["-s", serial, "shell", "wm", "dismiss-keyguard"], timeout=20
        )
        return ok, output or "Screen woken."

    @staticmethod
    def screen_size(serial):
        ok, output = ADBTools.run(["-s", serial, "shell", "wm", "size"], timeout=20)
        return ok, output

    # ------------------------------------------------------------------
    # system settings shortcuts
    # ------------------------------------------------------------------

    @staticmethod
    def open_settings(serial, page="settings"):
        ok, output = ADBTools.run(
            ["-s", serial, "shell", "am", "start", "-a",
             f"android.settings.{page.upper()}"], timeout=25
        )
        return ok, output or "Settings opened."

    @staticmethod
    def open_url(serial, url):
        ok, output = ADBTools.run(
            ["-s", serial, "shell", "am", "start", "-a",
             "android.intent.action.VIEW", "-d", url], timeout=25
        )
        return ok, output or "Link opened on the phone."

    @staticmethod
    def airplane_mode(serial, enabled):
        state = "enable" if enabled else "disable"
        ok, output = ADBTools.run(
            ["-s", serial, "shell", "cmd", "connectivity", "airplane-mode", state],
            timeout=20,
        )
        return ok, output or f"Airplane mode {state}d."

    @staticmethod
    def wifi(serial, enabled):
        state = "enable" if enabled else "disable"
        ok, output = ADBTools.run(
            ["-s", serial, "shell", "svc", "wifi", state], timeout=20
        )
        return ok, output or f"Wi-Fi {state}d."

    @staticmethod
    def mobile_data(serial, enabled):
        state = "enable" if enabled else "disable"
        ok, output = ADBTools.run(
            ["-s", serial, "shell", "svc", "data", state], timeout=20
        )
        return ok, output or f"Mobile data {state}d."

    @staticmethod
    def stay_awake(serial, enabled):
        value = 7 if enabled else 0
        ok, output = ADBTools.run(
            ["-s", serial, "shell", "settings", "put", "global",
             "stay_on_while_plugged_in", str(value)], timeout=20
        )
        return ok, output or "Stay-awake updated."

    @staticmethod
    def animation_scale(serial, scale):
        value = str(scale)
        results = []
        for key in ("window_animation_scale", "transition_animation_scale",
                    "animator_duration_scale"):
            ok, output = ADBTools.run(
                ["-s", serial, "shell", "settings", "put", "global", key, value],
                timeout=15,
            )
            results.append(ok)
            if not ok:
                return False, output
        return True, f"Animation scales set to {value}."

    # ------------------------------------------------------------------
    # packages
    # ------------------------------------------------------------------

    @staticmethod
    def packages(serial, system=False):
        args = ["shell", "pm", "list", "packages"]
        if system:
            args.append("-s")
        else:
            args.append("-3")
        ok, output = ADBTools.run(["-s", serial] + args, timeout=45)
        if not ok:
            return False, output
        names = sorted(
            line.replace("package:", "").strip()
            for line in output.splitlines()
            if line.strip()
        )
        if not names:
            return True, "No packages found."
        header = (
            f"{len(names)} system packages:"
            if system else f"{len(names)} installed by the user:"
        )
        return True, header + "\n\n" + "\n".join(names)

    @staticmethod
    def package_info(serial, package):
        if not package:
            return False, "No package name provided."
        ok, output = ADBTools.run(
            ["-s", serial, "shell", "dumpsys", "package", package], timeout=60
        )
        if not ok:
            return False, output
        keys = ("versionName", "versionCode", "firstInstallTime",
                "lastUpdateTime", "targetSdk", "codePath", "flags=")
        lines = [f"========== {package} ==========", ""]
        for line in output.splitlines():
            stripped = line.strip()
            if stripped.startswith(keys):
                lines.append(stripped)
        lines.append("")
        lines.append(f"(full dumpsys output: {len(output.splitlines())} lines)")
        return True, "\n".join(lines)

    @staticmethod
    def install(serial, apk_path, reinstall=True):
        if not os.path.exists(apk_path):
            return False, f"File not found: {apk_path}"
        args = ["-s", serial, "install"]
        if reinstall:
            args.append("-r")
        args.append(apk_path)
        ok, output = ADBTools.run(args, timeout=600)
        return ok, output

    @staticmethod
    def uninstall(serial, package, keep_data=False):
        if not package:
            return False, "No package name provided."
        args = ["-s", serial, "uninstall"]
        if keep_data:
            args.append("-k")
        args.append(package)
        ok, output = ADBTools.run(args, timeout=180)
        return ok, output

    @staticmethod
    def disable_package(serial, package):
        if not package:
            return False, "No package name provided."
        ok, output = ADBTools.run(
            ["-s", serial, "shell", "pm", "disable-user", "--user", "0", package],
            timeout=120,
        )
        return ok, output or f"Disabled {package}."

    @staticmethod
    def enable_package(serial, package):
        if not package:
            return False, "No package name provided."
        ok, output = ADBTools.run(
            ["-s", serial, "shell", "pm", "enable", package], timeout=120
        )
        return ok, output or f"Enabled {package}."

    @staticmethod
    def clear_package(serial, package):
        if not package:
            return False, "No package name provided."
        ok, output = ADBTools.run(
            ["-s", serial, "shell", "pm", "clear", package], timeout=120
        )
        return ok, output or f"Cleared app data for {package}."

    # ------------------------------------------------------------------
    # files
    # ------------------------------------------------------------------

    @staticmethod
    def list_dir(serial, path="/sdcard"):
        ok, output = ADBTools.run(
            ["-s", serial, "shell", "ls", "-la", path], timeout=45
        )
        return ok, output

    @staticmethod
    def pull(serial, remote, local):
        ok, output = ADBTools.run(
            ["-s", serial, "pull", remote, local], timeout=900
        )
        return ok, output or f"Copied {remote} to {local}."

    @staticmethod
    def push(serial, local, remote):
        if not os.path.exists(local):
            return False, f"File not found: {local}"
        ok, output = ADBTools.run(
            ["-s", serial, "push", local, remote], timeout=900
        )
        return ok, output or f"Copied {local} to {remote}."

    @staticmethod
    def delete(serial, remote):
        if not remote or remote in ("/", "/sdcard"):
            return False, "Refusing to delete this path."
        ok, output = ADBTools.run(
            ["-s", serial, "shell", "rm", "-rf", remote], timeout=120
        )
        return ok, output or f"Deleted {remote}."

    @staticmethod
    def storage_map(serial):
        ok, output = ADBTools.run(["-s", serial, "shell", "df", "-h"], timeout=45)
        return ok, output

    # ------------------------------------------------------------------
    # logs
    # ------------------------------------------------------------------

    @staticmethod
    def logcat(serial, lines=300):
        ok, output = ADBTools.run(
            ["-s", serial, "logcat", "-d", "-t", str(int(lines))], timeout=90
        )
        return ok, output

    @staticmethod
    def clear_logcat(serial):
        ok, output = ADBTools.run(["-s", serial, "logcat", "-c"], timeout=30)
        return ok, output or "Log buffer cleared."

    @staticmethod
    def bugreport(serial, destination):
        ok, output = ADBTools.run(
            ["-s", serial, "bugreport", destination], timeout=1800
        )
        return ok, output or f"Bug report written to {destination}"

    # ------------------------------------------------------------------
    # connectivity helpers
    # ------------------------------------------------------------------

    @staticmethod
    def ip_address(serial):
        ok, output = ADBTools.run(
            ["-s", serial, "shell", "ip", "-f", "inet", "addr", "show", "wlan0"],
            timeout=30,
        )
        if not ok:
            return False, output
        for line in output.splitlines():
            if "inet " in line:
                return True, line.strip().split()[1].split("/")[0]
        return False, "No Wi-Fi address found (is Wi-Fi connected?)."

    @staticmethod
    def restart_adb_server(serial=None):
        from . import proc

        ok1, out1 = proc.run(["adb", "kill-server"], timeout=20, binary="adb")
        ok2, out2 = proc.run(["adb", "start-server"], timeout=40, binary="adb")
        return ok2, (out1 + "\n" + out2).strip() or "ADB server restarted."

    @staticmethod
    def wireless_connect(host, port=5555):
        from . import proc

        target = f"{host.strip()}:{port}"
        ok, output = proc.run(["adb", "connect", target], timeout=45, binary="adb")
        if not ok:
            return False, output
        return True, (
            f"{output}\n\nConnected to {target}.\n"
            "Keep the phone on the same Wi-Fi network."
        )
