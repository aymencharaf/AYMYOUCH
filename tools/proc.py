"""Shared subprocess helper for every tool module.

All device tools funnel their calls through :func:`run` so timeouts,
encoding problems and missing binaries are reported the same way.
"""

from __future__ import annotations

import shutil
import subprocess


def which(binary: str) -> str | None:
    """Return the absolute path of *binary* or ``None``."""

    return shutil.which(binary)


def run(command, timeout: int = 30, binary: str | None = None):
    """Execute *command* and return ``(ok, output)``.

    ``binary`` names the executable used to build a helpful message when it
    is missing (``adb`` / ``fastboot``), so the UI can tell the user what to
    install instead of showing a traceback.
    """

    if binary is not None and which(binary) is None:
        return False, f"{binary} is not installed or not in PATH."

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return False, f"Command not found: {command[0]}"
    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout}s."
    except Exception as error:  # noqa: BLE001 - surfaced to the UI
        return False, str(error)

    output = result.stdout.strip()
    error = result.stderr.strip()

    if error:
        output = f"{output}\n{error}".strip() if output else error

    return result.returncode == 0, output
