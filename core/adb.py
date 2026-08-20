"""
core/adb.py — ADB command execution wrapper.

Provides a centralized interface for running ADB and Fastboot commands
with timeout handling, error capture, and multi-device routing.
"""

import subprocess
import shutil
import os
from typing import Optional


class ADBError(Exception):
    """Raised when an ADB command fails."""
    pass


class ADB:
    """
    ADB command wrapper with multi-device support.

    All ADB commands are routed through this class so that the
    active device serial is automatically injected via ``-s``.
    """

    def __init__(self):
        self._serial: Optional[str] = None

    # ── Device targeting ──────────────────────────────────────────────

    @property
    def serial(self) -> Optional[str]:
        """Currently selected device serial."""
        return self._serial

    @serial.setter
    def serial(self, value: Optional[str]):
        self._serial = value

    # ── Pre-flight checks ─────────────────────────────────────────────

    @staticmethod
    def is_installed() -> bool:
        """Return *True* if ``adb`` is on PATH."""
        return shutil.which("adb") is not None

    @staticmethod
    def is_fastboot_installed() -> bool:
        """Return *True* if ``fastboot`` is on PATH."""
        return shutil.which("fastboot") is not None

    # ── Command runners ───────────────────────────────────────────────

    def run(
        self,
        args: list[str],
        timeout: int = 30,
        capture: bool = True,
        serial: Optional[str] = None,
    ) -> tuple[bool, str]:
        """
        Execute an ADB command.

        Parameters
        ----------
        args : list[str]
            Command arguments *without* the leading ``adb`` token.
        timeout : int
            Seconds before the command is killed.
        capture : bool
            If *True* stdout/stderr are captured and returned;
            otherwise the command streams to the terminal.
        serial : str | None
            Override the active device serial for this call.

        Returns
        -------
        tuple[bool, str]
            ``(success, output_or_error)``
        """
        target = serial or self._serial
        cmd = ["adb"]
        if target:
            cmd += ["-s", target]
        cmd += args

        try:
            if capture:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                out = result.stdout.strip()
                if result.returncode != 0:
                    err = result.stderr.strip()
                    return False, err if err else "Command failed."
                return True, out
            else:
                result = subprocess.run(cmd, timeout=timeout)
                return result.returncode == 0, ""
        except subprocess.TimeoutExpired:
            return False, f"Command timed out after {timeout}s."
        except FileNotFoundError:
            return False, "ADB not found. Install Android SDK Platform Tools."

    def run_shell(
        self,
        cmd: str,
        timeout: int = 30,
        serial: Optional[str] = None,
    ) -> tuple[bool, str]:
        """Shortcut for ``adb shell <cmd>``."""
        return self.run(["shell"] + cmd.split(), timeout=timeout, serial=serial)

    def run_interactive_shell(self):
        """Open an interactive ADB shell session."""
        cmd = ["adb"]
        if self._serial:
            cmd += ["-s", self._serial]
        cmd += ["shell"]
        subprocess.run(cmd)

    def run_fastboot(
        self,
        args: list[str],
        timeout: int = 30,
        capture: bool = True,
        serial: Optional[str] = None,
    ) -> tuple[bool, str]:
        """
        Execute a fastboot command.

        Same interface as :meth:`run` but uses ``fastboot``.
        """
        target = serial or self._serial
        cmd = ["fastboot"]
        if target:
            cmd += ["-s", target]
        cmd += args

        try:
            if capture:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                out = result.stdout.strip()
                if result.returncode != 0:
                    err = result.stderr.strip()
                    return False, err if err else "Command failed."
                return True, out
            else:
                result = subprocess.run(cmd, timeout=timeout)
                return result.returncode == 0, ""
        except subprocess.TimeoutExpired:
            return False, f"Fastboot command timed out after {timeout}s."
        except FileNotFoundError:
            return False, "Fastboot not found. Install Android SDK Platform Tools."

    # ── Device enumeration ────────────────────────────────────────────

    def list_devices(self) -> list[dict]:
        """
        Return a list of connected devices.

        Each entry is a dict with keys ``serial``, ``state``, and
        optionally ``model``, ``device``, ``transport_id``.
        """
        ok, output = self.run(["devices", "-l"], serial="")
        if not ok:
            return []
        devices = []
        for line in output.splitlines()[1:]:
            parts = line.split()
            if len(parts) < 2:
                continue
            entry = {"serial": parts[0], "state": parts[1]}
            for token in parts[2:]:
                if ":" in token:
                    k, v = token.split(":", 1)
                    entry[k] = v
            devices.append(entry)
        return devices

    def get_connected_serials(self) -> list[str]:
        """Return serial numbers of devices in *device* state."""
        return [d["serial"] for d in self.list_devices() if d["state"] == "device"]

    def has_device(self) -> bool:
        """Return *True* if at least one device is connected."""
        return len(self.get_connected_serials()) > 0

    # ── Property helpers ──────────────────────────────────────────────

    def getprop(self, prop: str) -> str:
        """Read a single system property."""
        ok, val = self.run(["shell", "getprop", prop])
        return val if ok else ""

    def get_all_props(self) -> dict[str, str]:
        """Read all system properties into a dict."""
        ok, output = self.run(["shell", "getprop"], timeout=15)
        if not ok:
            return {}
        props = {}
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("[") and "]: [" in line:
                key = line.split("]: [")[0][1:]
                val = line.split("]: [")[1].rstrip("]")
                props[key] = val
        return props


# Module-level singleton
adb = ADB()
