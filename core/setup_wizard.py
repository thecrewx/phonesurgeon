"""
core/setup_wizard.py — Auto-detection, download, and installation of prerequisites.

Ensures Python version, ADB, Fastboot, and device connectivity are all
ready before the user enters the main menu.  Downloads Android SDK
Platform Tools automatically on Windows, macOS, and Linux when ADB
is missing.
"""

import os
import sys
import shutil
import platform
import subprocess
import zipfile
import stat
import json
from pathlib import Path
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError


# ─── Constants ────────────────────────────────────────────────────────────────

MIN_PYTHON = (3, 8)

PLATFORM_TOOLS_URLS = {
    "Windows": "https://dl.google.com/android/repository/platform-tools-latest-windows.zip",
    "Darwin":  "https://dl.google.com/android/repository/platform-tools-latest-darwin.zip",
    "Linux":   "https://dl.google.com/android/repository/platform-tools-latest-linux.zip",
}

APP_DIR = Path.home() / ".phonesurgeon"
TOOLS_DIR = APP_DIR / "platform-tools"
CONFIG_FILE = APP_DIR / "config.json"


# ─── ANSI helpers (standalone — no dependency on core.ui) ─────────────────────

class _C:
    G = "\033[92m"   # green
    R = "\033[91m"   # red
    Y = "\033[93m"   # yellow
    C = "\033[96m"   # cyan
    B = "\033[1m"    # bold
    D = "\033[2m"    # dim
    X = "\033[0m"    # reset


def _ok(msg: str):
    print(f"  {_C.G}✓{_C.X} {msg}")

def _fail(msg: str):
    print(f"  {_C.R}✗{_C.X} {msg}")

def _info(msg: str):
    print(f"  {_C.C}ℹ{_C.X} {msg}")

def _warn(msg: str):
    print(f"  {_C.Y}⚠{_C.X} {msg}")

def _step(num: int, total: int, msg: str):
    print(f"\n  {_C.B}[{num}/{total}]{_C.X} {msg}")

def _bar(current: int, total: int, width: int = 30):
    pct = current / total if total else 0
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    print(f"\r  {_C.C}[{bar}]{_C.X} {pct*100:5.1f}%", end="", flush=True)
    if current >= total:
        print()


# ─── Config persistence ──────────────────────────────────────────────────────

def _load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_config(cfg: dict):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


# ─── Python check ────────────────────────────────────────────────────────────

def check_python() -> bool:
    """Verify Python version meets the minimum requirement."""
    ver = sys.version_info[:2]
    if ver >= MIN_PYTHON:
        _ok(f"Python {ver[0]}.{ver[1]} detected  (minimum {MIN_PYTHON[0]}.{MIN_PYTHON[1]})")
        return True
    else:
        _fail(f"Python {ver[0]}.{ver[1]} is too old — need {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+")
        _info("Download the latest Python from https://www.python.org/downloads/")
        return False


# ─── ADB check / install ─────────────────────────────────────────────────────

def _which_adb() -> Optional[str]:
    """Find ADB on PATH or in our managed install."""
    # Check system PATH first
    system_adb = shutil.which("adb")
    if system_adb:
        return system_adb

    # Check our own managed install
    if os.name == "nt":
        local_adb = TOOLS_DIR / "adb.exe"
    else:
        local_adb = TOOLS_DIR / "adb"

    if local_adb.exists():
        return str(local_adb)
    return None


def _get_adb_version(adb_path: str) -> str:
    """Return the ADB version string."""
    try:
        result = subprocess.run(
            [adb_path, "version"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if "Android Debug Bridge" in line:
                return line.strip()
        return result.stdout.splitlines()[0].strip() if result.stdout else "unknown"
    except Exception:
        return "unknown"


def _download_platform_tools() -> bool:
    """Download and extract Android SDK Platform Tools."""
    system = platform.system()
    url = PLATFORM_TOOLS_URLS.get(system)
    if not url:
        _fail(f"Unsupported OS: {system}")
        _info("Manually install ADB from https://developer.android.com/studio/releases/platform-tools")
        return False

    APP_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = APP_DIR / "platform-tools.zip"

    print(f"\n  {_C.B}Downloading Android SDK Platform Tools...{_C.X}")
    _info(f"URL: {url}")
    _info(f"Destination: {APP_DIR}")

    try:
        req = Request(url, headers={"User-Agent": "PhoneSurgeon/2.0"})
        response = urlopen(req, timeout=60)
        total = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 65536

        with open(zip_path, "wb") as f:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    _bar(downloaded, total)

        if total > 0:
            _bar(total, total)

        _ok(f"Downloaded ({downloaded / (1024*1024):.1f} MB)")

    except URLError as e:
        _fail(f"Download failed: {e}")
        _info("Check your internet connection and try again.")
        _info("Or manually download from: https://developer.android.com/studio/releases/platform-tools")
        return False
    except Exception as e:
        _fail(f"Download error: {e}")
        return False

    # Extract
    print(f"\n  {_C.B}Extracting...{_C.X}")
    try:
        # Remove old install if present
        if TOOLS_DIR.exists():
            shutil.rmtree(TOOLS_DIR)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(APP_DIR)

        # Make binaries executable on Unix
        if os.name != "nt":
            for binary in ["adb", "fastboot"]:
                bin_path = TOOLS_DIR / binary
                if bin_path.exists():
                    bin_path.chmod(bin_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

        _ok("Extracted successfully!")

    except Exception as e:
        _fail(f"Extraction failed: {e}")
        return False
    finally:
        # Clean up zip
        if zip_path.exists():
            zip_path.unlink()

    return True


def _add_to_path():
    """Add Platform Tools to the current session PATH."""
    tools_str = str(TOOLS_DIR)
    if tools_str not in os.environ.get("PATH", ""):
        os.environ["PATH"] = tools_str + os.pathsep + os.environ.get("PATH", "")

    # Save to config for future sessions
    cfg = _load_config()
    cfg["platform_tools_path"] = tools_str
    _save_config(cfg)


def _add_to_system_path_hint():
    """Print instructions for permanently adding to system PATH."""
    tools_str = str(TOOLS_DIR)
    system = platform.system()

    print(f"\n  {_C.Y}To make this permanent, add to your system PATH:{_C.X}\n")

    if system == "Windows":
        print(f"  {_C.D}Option 1 (PowerShell — run as Admin):{_C.X}")
        print(f"  {_C.C}[Environment]::SetEnvironmentVariable('Path',")
        print(f"    [Environment]::GetEnvironmentVariable('Path', 'User') + ';{tools_str}', 'User'){_C.X}")
        print()
        print(f"  {_C.D}Option 2 (GUI):{_C.X}")
        print(f"  {_C.C}System Properties → Environment Variables → Path → Add: {tools_str}{_C.X}")
    elif system == "Darwin":
        print(f"  {_C.C}echo 'export PATH=\"{tools_str}:$PATH\"' >> ~/.zshrc && source ~/.zshrc{_C.X}")
    else:
        print(f"  {_C.C}echo 'export PATH=\"{tools_str}:$PATH\"' >> ~/.bashrc && source ~/.bashrc{_C.X}")


def check_adb() -> bool:
    """Check if ADB is installed; offer to download if not."""
    adb_path = _which_adb()

    if adb_path:
        version = _get_adb_version(adb_path)
        _ok(f"ADB found: {adb_path}")
        _ok(f"Version: {version}")
        # Ensure it's on PATH for this session
        adb_dir = str(Path(adb_path).parent)
        if adb_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = adb_dir + os.pathsep + os.environ.get("PATH", "")
        return True

    _fail("ADB not found on system PATH.")
    print()

    # Offer to install
    try:
        answer = input(f"  {_C.G}➤ Download & install ADB automatically? (y/n): {_C.X}").strip().lower()
    except (KeyboardInterrupt, EOFError):
        return False

    if answer not in ("y", "yes"):
        _info("You can install manually from:")
        _info("https://developer.android.com/studio/releases/platform-tools")
        return False

    if _download_platform_tools():
        _add_to_path()
        adb_path = _which_adb()
        if adb_path:
            version = _get_adb_version(adb_path)
            _ok(f"ADB installed: {adb_path}")
            _ok(f"Version: {version}")
            _add_to_system_path_hint()
            return True
        else:
            _fail("ADB installed but not found. Try restarting your terminal.")
            return False
    return False


# ─── Fastboot check ──────────────────────────────────────────────────────────

def check_fastboot() -> bool:
    """Check if Fastboot is available (optional)."""
    fb = shutil.which("fastboot")
    if not fb:
        # Check our managed install
        if os.name == "nt":
            local_fb = TOOLS_DIR / "fastboot.exe"
        else:
            local_fb = TOOLS_DIR / "fastboot"
        if local_fb.exists():
            fb = str(local_fb)

    if fb:
        _ok(f"Fastboot found: {fb}")
        return True
    else:
        _warn("Fastboot not found (optional — needed only for bootloader operations)")
        return False


# ─── USB Driver check (Windows only) ─────────────────────────────────────────

def check_usb_drivers() -> bool:
    """On Windows, check if Google USB driver is likely installed."""
    if platform.system() != "Windows":
        _ok("USB drivers: not needed on this OS")
        return True

    # Try to detect via ADB devices
    adb_path = _which_adb()
    if not adb_path:
        _warn("Cannot check USB drivers — ADB not available")
        return False

    try:
        result = subprocess.run(
            [adb_path, "devices"],
            capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.strip().splitlines()
        # Check for unauthorized or device lines
        device_lines = [l for l in lines[1:] if l.strip()]
        if not device_lines:
            _warn("No devices detected — USB drivers may need to be installed")
            _info("Download Google USB Driver from:")
            _info("https://developer.android.com/studio/run/win-usb")
            _info("Or install your device manufacturer's USB drivers")
            return False

        has_unauthorized = any("unauthorized" in l for l in device_lines)
        if has_unauthorized:
            _warn("Device detected but unauthorized — accept the USB debugging prompt on your phone")
            return False

        _ok("USB drivers: working (device detected)")
        return True

    except Exception:
        _warn("Could not verify USB drivers")
        return False


# ─── Device connectivity check ────────────────────────────────────────────────

def check_device_connection() -> tuple[bool, int]:
    """
    Check for connected devices.

    Returns (any_device_found, device_count).
    """
    adb_path = _which_adb()
    if not adb_path:
        return False, 0

    try:
        result = subprocess.run(
            [adb_path, "devices"],
            capture_output=True, text=True, timeout=10
        )
        devices = []
        for line in result.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])

        if devices:
            _ok(f"Connected devices: {len(devices)}")
            for d in devices:
                print(f"    {_C.C}🔌 {d}{_C.X}")
            return True, len(devices)
        else:
            _warn("No devices connected right now (you can connect later)")
            return False, 0

    except Exception:
        _warn("Could not check for devices")
        return False, 0


# ─── USB Debugging guide ─────────────────────────────────────────────────────

def print_usb_debugging_guide():
    """Print instructions to enable USB debugging."""
    print(f"""
  {_C.B}{_C.C}┌─ How to Enable USB Debugging ─────────────────────────────┐{_C.X}
  {_C.C}│{_C.X}                                                            {_C.C}│{_C.X}
  {_C.C}│{_C.X}  {_C.B}Step 1:{_C.X} Open {_C.Y}Settings{_C.X} on your Android phone            {_C.C}│{_C.X}
  {_C.C}│{_C.X}  {_C.B}Step 2:{_C.X} Go to {_C.Y}About Phone{_C.X}                              {_C.C}│{_C.X}
  {_C.C}│{_C.X}  {_C.B}Step 3:{_C.X} Tap {_C.Y}Build Number{_C.X} {_C.B}7 times{_C.X}                     {_C.C}│{_C.X}
  {_C.C}│{_C.X}          (You'll see "You are now a developer!")          {_C.C}│{_C.X}
  {_C.C}│{_C.X}  {_C.B}Step 4:{_C.X} Go back to {_C.Y}Settings → Developer Options{_C.X}         {_C.C}│{_C.X}
  {_C.C}│{_C.X}  {_C.B}Step 5:{_C.X} Enable {_C.Y}USB Debugging{_C.X}                            {_C.C}│{_C.X}
  {_C.C}│{_C.X}  {_C.B}Step 6:{_C.X} Connect phone via USB cable                    {_C.C}│{_C.X}
  {_C.C}│{_C.X}  {_C.B}Step 7:{_C.X} Tap {_C.Y}Allow{_C.X} on the USB debugging prompt           {_C.C}│{_C.X}
  {_C.C}│{_C.X}                                                            {_C.C}│{_C.X}
  {_C.C}└───────────────────────────────────────────────────────────┘{_C.X}
""")


# ─── ADB Server ──────────────────────────────────────────────────────────────

def start_adb_server() -> bool:
    """Start the ADB server if not already running."""
    adb_path = _which_adb()
    if not adb_path:
        return False

    try:
        result = subprocess.run(
            [adb_path, "start-server"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            _ok("ADB server is running")
            return True
        else:
            _warn(f"ADB server issue: {result.stderr.strip()}")
            return False
    except Exception as e:
        _warn(f"Could not start ADB server: {e}")
        return False


# ─── Master setup wizard ─────────────────────────────────────────────────────

def run_setup_wizard(force: bool = False) -> bool:
    """
    Run the full setup wizard.

    Parameters
    ----------
    force : bool
        If True, run even if setup was completed before.

    Returns
    -------
    bool
        True if all critical checks pass and the tool is ready to use.
    """
    # Check if setup was already done
    cfg = _load_config()
    if not force and cfg.get("setup_complete"):
        # Still verify ADB is available
        adb_path = _which_adb()
        if adb_path:
            adb_dir = str(Path(adb_path).parent)
            if adb_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = adb_dir + os.pathsep + os.environ.get("PATH", "")
            return True
        # ADB gone — re-run setup
        cfg["setup_complete"] = False
        _save_config(cfg)

    # ── Banner ────────────────────────────────────────────────────────
    if os.name == "nt":
        os.system("cls")
    else:
        os.system("clear")

    print(f"""
{_C.C}{_C.B}
    ╔══════════════════════════════════════════════════════╗
    ║                                                      ║
    ║       🏥  P H O N E   S U R G E O N  🏥             ║
    ║       ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━               ║
    ║            First-Time Setup Wizard                    ║
    ║                                                      ║
    ╚══════════════════════════════════════════════════════╝
{_C.X}""")

    print(f"  {_C.D}Checking prerequisites...{_C.X}\n")

    total_steps = 5
    all_ok = True
    critical_fail = False

    # ── Step 1: Python ────────────────────────────────────────────────
    _step(1, total_steps, "Checking Python version...")
    if not check_python():
        critical_fail = True

    # ── Step 2: ADB ───────────────────────────────────────────────────
    _step(2, total_steps, "Checking ADB (Android Debug Bridge)...")
    if not check_adb():
        critical_fail = True

    # ── Step 3: Fastboot ──────────────────────────────────────────────
    _step(3, total_steps, "Checking Fastboot (optional)...")
    check_fastboot()  # Non-critical

    # ── Step 4: ADB Server ────────────────────────────────────────────
    _step(4, total_steps, "Starting ADB server...")
    if not critical_fail:
        start_adb_server()

    # ── Step 5: Device connectivity ───────────────────────────────────
    _step(5, total_steps, "Checking device connectivity...")
    if not critical_fail:
        has_device, count = check_device_connection()
        if not has_device:
            print_usb_debugging_guide()
            all_ok = False

    # ── Check USB drivers (Windows) ───────────────────────────────────
    if platform.system() == "Windows" and not critical_fail:
        print()
        check_usb_drivers()

    # ── Summary ───────────────────────────────────────────────────────
    print(f"\n  {'━' * 50}")

    if critical_fail:
        print(f"""
  {_C.R}{_C.B}✗ Setup incomplete — critical components missing.{_C.X}
  {_C.R}  Please install the required tools and try again.{_C.X}
        """)
        return False

    if all_ok:
        print(f"""
  {_C.G}{_C.B}✓ All checks passed! PhoneSurgeon is ready.{_C.X}
        """)
    else:
        print(f"""
  {_C.Y}{_C.B}⚠ Setup complete with warnings.{_C.X}
  {_C.Y}  You can connect a device later.{_C.X}
        """)

    # Mark setup as complete
    cfg = _load_config()
    cfg["setup_complete"] = True
    cfg["setup_os"] = platform.system()
    cfg["setup_python"] = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    _save_config(cfg)

    # Pause before continuing
    try:
        input(f"\n  {_C.D}Press Enter to launch PhoneSurgeon...{_C.X}")
    except (KeyboardInterrupt, EOFError):
        return False

    return True


def run_quick_check() -> bool:
    """
    Fast check for returning users — skips the wizard UI.

    Returns True if ADB is available.
    """
    cfg = _load_config()

    # Restore managed PATH if saved
    saved_path = cfg.get("platform_tools_path")
    if saved_path and saved_path not in os.environ.get("PATH", ""):
        os.environ["PATH"] = saved_path + os.pathsep + os.environ.get("PATH", "")

    adb_path = _which_adb()
    if adb_path:
        # Ensure dir is on PATH
        adb_dir = str(Path(adb_path).parent)
        if adb_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = adb_dir + os.pathsep + os.environ.get("PATH", "")
        return True

    return False
