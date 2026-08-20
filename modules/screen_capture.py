"""
modules/screen_capture.py — Screen Capture & Recording Module for DroidCommander.

Provides a comprehensive suite of visual capture and recording tools for Android devices:
- Single timestamped screenshot with immediate host saving
- Burst mode screenshot capture (multi-shot with customizable delay)
- Screen recording (default duration, custom duration up to 180s)
- Screen recording with custom bitrate (2 Mbps to 20 Mbps or custom)
- Screen recording with custom resolution / downscaling presets (720p, 1080p, half-scale)
- Multi-display screenshot capture by display ID
- Native host file explorer integration to open the captures folder
- Advanced recording wizard (touch visualization, bitrate, resolution, bugreport overlay)
- Capture gallery & history viewer with instant launch
- Remote temporary file cleanup
"""

import os
import subprocess
import sys
import time
from datetime import datetime
from typing import Optional, List, Tuple, Dict

from core.adb import adb
from core import ui
from core.device import ensure_device


# ─── File System & Directory Helpers ─────────────────────────────────────────

def _get_captures_dir(subfolder: str = "") -> str:
    """
    Get the absolute path to the local captures directory.

    Creates the directory if it does not already exist.

    Parameters
    ----------
    subfolder : str
        Optional subfolder name (e.g. 'screenshots', 'recordings').
    """
    base_dir = os.path.join(os.getcwd(), "captures")
    if subfolder:
        target_dir = os.path.join(base_dir, subfolder)
    else:
        target_dir = base_dir
    os.makedirs(target_dir, exist_ok=True)
    return target_dir


def _human_size(num_bytes: int) -> str:
    """Convert integer byte count to human-readable string."""
    if num_bytes < 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    unit_idx = 0
    while size >= 1024.0 and unit_idx < len(units) - 1:
        size /= 1024.0
        unit_idx += 1
    return f"{size:.2f} {units[unit_idx]}" if unit_idx > 0 else f"{int(size)} B"


def _open_folder(directory_path: str):
    """Open the specified folder in the operating system's default file manager."""
    try:
        abs_path = os.path.abspath(directory_path)
        if sys.platform.startswith("win"):
            os.startfile(abs_path)
        elif sys.platform.startswith("darwin"):
            subprocess.Popen(["open", abs_path])
        else:
            subprocess.Popen(["xdg-open", abs_path])
        ui.success(f"Opened capture folder: {abs_path}")
    except Exception as exc:
        ui.error(f"Failed to open folder: {exc}")


def _open_file(file_path: str):
    """Open an image or video file in the operating system's default viewer."""
    try:
        abs_path = os.path.abspath(file_path)
        if sys.platform.startswith("win"):
            os.startfile(abs_path)
        elif sys.platform.startswith("darwin"):
            subprocess.Popen(["open", abs_path])
        else:
            subprocess.Popen(["xdg-open", abs_path])
    except Exception as exc:
        ui.warning(f"Could not open file automatically: {exc}")


def _get_device_screen_size() -> Tuple[int, int]:
    """
    Query the native screen dimensions of the connected device.

    Returns
    -------
    Tuple[int, int]
        (width, height), e.g. (1080, 2400) or fallback (1080, 1920)
    """
    ok, output = adb.run(["shell", "wm", "size"])
    if ok and output:
        # Output format: "Physical size: 1080x2400" or "Override size: 720x1280"
        for line in output.splitlines():
            if "size:" in line:
                val = line.split("size:")[1].strip()
                if "x" in val:
                    parts = val.split("x")
                    try:
                        return int(parts[0]), int(parts[1])
                    except ValueError:
                        pass
    return 1080, 1920


# ─── Feature 1: Single Screenshot ────────────────────────────────────────────

def take_single_screenshot(display_id: Optional[int] = None) -> Optional[str]:
    """
    Capture a single screenshot from the device and save it locally.

    Parameters
    ----------
    display_id : int, optional
        Target display ID for multi-screen devices.

    Returns
    -------
    str | None
        Local path of saved screenshot, or None if failed.
    """
    if not ensure_device():
        return None

    ui.header("Capture Screenshot" + (f" (Display {display_id})" if display_id is not None else ""))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    remote_filename = f"screenshot_{timestamp}.png"
    remote_path = f"/sdcard/{remote_filename}"

    local_dir = _get_captures_dir("screenshots")
    local_filename = f"screenshot_{timestamp}.png"
    local_path = os.path.join(local_dir, local_filename)

    ui.info("Capturing screen on device...")

    screencap_cmd = ["shell", "screencap"]
    if display_id is not None:
        screencap_cmd.extend(["-d", str(display_id)])
    screencap_cmd.extend(["-p", remote_path])

    ok, cap_out = adb.run(screencap_cmd, timeout=20)
    if not ok:
        ui.error(f"Failed to capture screenshot: {cap_out}")
        return None

    ui.info("Transferring screenshot to host PC...")
    ok, pull_out = adb.run(["pull", remote_path, local_path], timeout=30)
    # Clean up remote temp file
    adb.run(["shell", "rm", "-f", remote_path])

    if ok and os.path.isfile(local_path):
        size = os.path.getsize(local_path)
        ui.success(f"Screenshot saved: {local_path} ({_human_size(size)})")
        if ui.confirm("Open screenshot in default viewer?"):
            _open_file(local_path)
        return local_path
    else:
        ui.error(f"Failed to pull screenshot: {pull_out}")
        return None


# ─── Feature 2: Burst Screenshots ────────────────────────────────────────────

def take_burst_screenshots():
    """Capture a series of screenshots with a configurable delay interval."""
    if not ensure_device():
        return

    ui.header("Burst Screenshot Capture")
    count_str = ui.get_choice("Enter number of screenshots to take (2-30, default: 5)")
    count = int(count_str) if count_str.isdigit() and 2 <= int(count_str) <= 30 else 5

    interval_str = ui.get_choice("Enter interval delay between shots in seconds (0.2 - 5.0, default: 1.0)")
    try:
        interval = float(interval_str)
        if interval < 0.2 or interval > 5.0:
            interval = 1.0
    except ValueError:
        interval = 1.0

    local_dir = _get_captures_dir("screenshots")
    batch_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ui.info(f"Starting burst capture: {count} shots with {interval:.1f}s delay...")

    saved_paths = []
    for i in range(1, count + 1):
        remote_path = f"/sdcard/burst_{batch_ts}_{i:02d}.png"
        local_path = os.path.join(local_dir, f"burst_{batch_ts}_{i:02d}.png")

        # Capture
        ok_cap, _ = adb.run(["shell", "screencap", "-p", remote_path], timeout=15)
        if ok_cap:
            # Pull
            ok_pull, _ = adb.run(["pull", remote_path, local_path], timeout=20)
            adb.run(["shell", "rm", "-f", remote_path])
            if ok_pull and os.path.isfile(local_path):
                saved_paths.append(local_path)

        ui.progress_bar(i, count, label=f"Burst Capture {i}/{count}")

        if i < count:
            time.sleep(interval)

    print()
    if saved_paths:
        ui.success(f"Burst capture complete! Saved {len(saved_paths)} of {count} screenshots.")
        ui.info(f"Directory: {local_dir}")
        if ui.confirm("Open screenshots folder?"):
            _open_folder(local_dir)
    else:
        ui.error("Failed to capture burst screenshots.")


# ─── Feature 3: Screen Recording (Default 10s) ────────────────────────────────

def record_screen_default():
    """Record screen for the default duration of 10 seconds."""
    if not ensure_device():
        return
    _record_screen(duration=10, label="Standard Screen Recording (10s)")


# ─── Feature 4: Screen Recording (Custom Duration) ───────────────────────────

def record_screen_custom_duration():
    """Record screen for a custom duration (1 to 180 seconds)."""
    if not ensure_device():
        return

    ui.header("Screen Recording (Custom Duration)")
    dur_str = ui.get_choice("Enter recording duration in seconds (1-180, default: 30)")

    duration = 30
    if dur_str.isdigit():
        val = int(dur_str)
        if 1 <= val <= 180:
            duration = val
        elif val > 180:
            ui.warning("Android screenrecord limit is 180s. Capped to 180 seconds.")
            duration = 180
        else:
            duration = 10

    _record_screen(duration=duration, label=f"Custom Screen Recording ({duration}s)")


# ─── Feature 5: Screen Recording with Custom Bitrate ─────────────────────────

def record_screen_custom_bitrate():
    """Record screen with user-selected video bitrate for quality/size optimization."""
    if not ensure_device():
        return

    ui.header("Screen Recording with Custom Bitrate")
    print(f"""
  {ui.Colors.CYAN}Select Video Bitrate:{ui.Colors.RESET}
    [1] 2 Mbps  (2,000,000 bps)  - Compact / Low bandwidth
    [2] 4 Mbps  (4,000,000 bps)  - Standard Android Default
    [3] 8 Mbps  (8,000,000 bps)  - High Definition (Recommended)
    [4] 12 Mbps (12,000,000 bps) - Very High Quality
    [5] 20 Mbps (20,000,000 bps) - Maximum Quality / Ultra HD
    [6] Custom bitrate (Mbps)
    """)

    bitrate_choice = ui.get_choice("Select bitrate option (1-5) or enter custom (default 3)")
    bitrate_bps = 8000000
    bitrate_label = "8 Mbps"

    if bitrate_choice == "1":
        bitrate_bps = 2000000
        bitrate_label = "2 Mbps"
    elif bitrate_choice == "2":
        bitrate_bps = 4000000
        bitrate_label = "4 Mbps"
    elif bitrate_choice == "3" or bitrate_choice == "":
        bitrate_bps = 8000000
        bitrate_label = "8 Mbps"
    elif bitrate_choice == "4":
        bitrate_bps = 12000000
        bitrate_label = "12 Mbps"
    elif bitrate_choice == "5":
        bitrate_bps = 20000000
        bitrate_label = "20 Mbps"
    elif bitrate_choice == "6":
        custom_val = ui.get_choice("Enter bitrate in Mbps (e.g. 6 or 16)")
        if custom_val.isdigit() and int(custom_val) > 0:
            bitrate_bps = int(custom_val) * 1000000
            bitrate_label = f"{custom_val} Mbps"

    dur_str = ui.get_choice("Enter duration in seconds (1-180, default: 15)")
    duration = int(dur_str) if dur_str.isdigit() and 1 <= int(dur_str) <= 180 else 15

    _record_screen(
        duration=duration,
        bitrate=bitrate_bps,
        label=f"Screen Recording ({duration}s @ {bitrate_label})",
    )


# ─── Feature 6: Screen Recording with Custom Resolution ──────────────────────

def record_screen_custom_resolution():
    """Record screen with customized resolution or downscaling presets."""
    if not ensure_device():
        return

    ui.header("Screen Recording with Custom Resolution")
    native_w, native_h = _get_device_screen_size()
    ui.info(f"Detected Native Display Resolution: {native_w}x{native_h}")

    half_w = native_w // 2
    half_h = native_h // 2

    # Determine portrait vs landscape presets
    if native_w <= native_h:
        res_720p = "720x1280"
        res_1080p = "1080x1920"
        res_480p = "480x854"
    else:
        res_720p = "1280x720"
        res_1080p = "1920x1080"
        res_480p = "854x480"

    print(f"""
  {ui.Colors.CYAN}Resolution Presets:{ui.Colors.RESET}
    [1] Native Device Size ({native_w}x{native_h})
    [2] 720p HD ({res_720p})
    [3] 1080p FHD ({res_1080p})
    [4] 50% Scale / Half-Resolution ({half_w}x{half_h})
    [5] 480p SD ({res_480p})
    [6] Custom Width x Height (e.g. 720x1520)
    """)

    res_choice = ui.get_choice("Select resolution preset (1-5) or 6 for custom (default 1)")
    selected_size: Optional[str] = None

    if res_choice == "1" or res_choice == "":
        selected_size = f"{native_w}x{native_h}"
    elif res_choice == "2":
        selected_size = res_720p
    elif res_choice == "3":
        selected_size = res_1080p
    elif res_choice == "4":
        selected_size = f"{half_w}x{half_h}"
    elif res_choice == "5":
        selected_size = res_480p
    elif res_choice == "6":
        custom = ui.get_choice("Enter resolution as WIDTHxHEIGHT (e.g. 720x1440)")
        if "x" in custom:
            selected_size = custom.strip()
        else:
            selected_size = f"{native_w}x{native_h}"

    dur_str = ui.get_choice("Enter duration in seconds (1-180, default: 15)")
    duration = int(dur_str) if dur_str.isdigit() and 1 <= int(dur_str) <= 180 else 15

    _record_screen(
        duration=duration,
        size=selected_size,
        label=f"Screen Recording ({duration}s @ {selected_size})",
    )


# ─── Feature 7: Screenshot of Specific Display ───────────────────────────────

def take_screenshot_specific_display():
    """Take a screenshot of a specific display on multi-display/foldable devices."""
    if not ensure_device():
        return

    ui.header("Multi-Display Screenshot")
    ui.info("Querying active display IDs on device...")

    ok, output = adb.run(["shell", "dumpsys", "SurfaceFlinger", "--display-id"], timeout=10)
    if not ok or not output:
        ok, output = adb.run(["shell", "dumpsys", "display"], timeout=10)

    print(f"""
  {ui.Colors.CYAN}Common Display IDs:{ui.Colors.RESET}
    [0] Display 0 — Main / Default Display
    [1] Display 1 — Secondary / Foldable / External Screen
    [2] Display 2 — Virtual / Cast Display
    """)

    disp_choice = ui.get_choice("Enter display ID to capture (default: 0)")
    display_id = 0
    if disp_choice.isdigit():
        display_id = int(disp_choice)

    take_single_screenshot(display_id=display_id)


# ─── Feature 8: Open Screenshot / Captures Folder ────────────────────────────

def open_captures_folder():
    """Open the local captures directory in the host file manager."""
    captures_dir = _get_captures_dir()
    _open_folder(captures_dir)


# ─── Feature 9: Advanced Screen Recorder Wizard ──────────────────────────────

def record_screen_advanced():
    """Advanced recording configuration wizard with touches, rotation, and overlays."""
    if not ensure_device():
        return

    ui.header("Advanced Screen Recorder Wizard")

    # 1. Duration
    dur_str = ui.get_choice("1. Enter duration in seconds (1-180, default: 20)")
    duration = int(dur_str) if dur_str.isdigit() and 1 <= int(dur_str) <= 180 else 20

    # 2. Bitrate
    bit_str = ui.get_choice("2. Enter bitrate in Mbps (default: 8)")
    bitrate = int(bit_str) * 1000000 if bit_str.isdigit() and int(bit_str) > 0 else 8000000

    # 3. Resolution
    native_w, native_h = _get_device_screen_size()
    res_str = ui.get_choice(f"3. Enter resolution WIDTHxHEIGHT (press Enter for native {native_w}x{native_h})")
    size = res_str.strip() if "x" in res_str else None

    # 4. Show visual touches
    show_touches = ui.confirm("4. Enable visual touch indicators on screen during recording?")

    # 5. Bugreport overlay
    bugreport = ui.confirm("5. Add debug overlay banner (timestamp & frame info)?")

    # 6. Rotate 90 degrees
    rotate = ui.confirm("6. Rotate video output by 90 degrees?")

    _record_screen(
        duration=duration,
        bitrate=bitrate,
        size=size,
        show_touches=show_touches,
        rotate=rotate,
        bugreport=bugreport,
        label=f"Advanced Screen Recording ({duration}s)",
    )


# ─── Feature 10: View Capture History & Gallery ──────────────────────────────

def view_capture_history():
    """View list of local screenshots and recordings with instant opening."""
    captures_base = _get_captures_dir()
    screenshots_dir = _get_captures_dir("screenshots")
    recordings_dir = _get_captures_dir("recordings")

    ui.header("Capture History & Gallery")

    all_files: List[Tuple[str, str, int, float]] = []

    # Gather screenshots
    if os.path.isdir(screenshots_dir):
        for f in os.listdir(screenshots_dir):
            fp = os.path.join(screenshots_dir, f)
            if os.path.isfile(fp) and f.lower().endswith((".png", ".jpg", ".jpeg")):
                stat = os.stat(fp)
                all_files.append((fp, "Screenshot", stat.st_size, stat.st_mtime))

    # Gather recordings
    if os.path.isdir(recordings_dir):
        for f in os.listdir(recordings_dir):
            fp = os.path.join(recordings_dir, f)
            if os.path.isfile(fp) and f.lower().endswith((".mp4", ".mkv")):
                stat = os.stat(fp)
                all_files.append((fp, "Recording", stat.st_size, stat.st_mtime))

    if not all_files:
        ui.info("No captured files found in local repository.")
        ui.info(f"Directory: {captures_base}")
        return

    # Sort descending by modification time
    all_files.sort(key=lambda x: x[3], reverse=True)

    table_rows = []
    for i, (fp, ftype, fsize, fmtime) in enumerate(all_files[:25], 1):
        dt_str = datetime.fromtimestamp(fmtime).strftime("%Y-%m-%d %H:%M:%S")
        type_str = f"{ui.Colors.CYAN}📸 Image{ui.Colors.RESET}" if ftype == "Screenshot" else f"{ui.Colors.YELLOW}🎥 Video{ui.Colors.RESET}"
        table_rows.append((f"[{i:>2}]", type_str, os.path.basename(fp), _human_size(fsize), dt_str))

    headers = ("#", "Type", "Filename", "Size", "Date Modified")
    print(f"\n  {ui.Colors.BOLD}Recent Captures ({len(all_files)} total):{ui.Colors.RESET}\n")
    ui.print_table(table_rows, headers=headers)

    pick = ui.get_choice("Enter file number to open (or press Enter to return)")
    if pick.isdigit():
        idx = int(pick) - 1
        if 0 <= idx < len(all_files[:25]):
            selected_fp = all_files[idx][0]
            ui.info(f"Opening: {selected_fp}")
            _open_file(selected_fp)


# ─── Feature 11: Clean Remote Temp Files ─────────────────────────────────────

def clean_remote_temp_files():
    """Scan and delete orphaned screenshot/recording temporary files on device."""
    if not ensure_device():
        return

    ui.header("Clean Remote Temporary Capture Files")
    ui.info("Scanning /sdcard/ for leftover screenshot and recording files...")

    ok, out = adb.run(["shell", "ls /sdcard/screenshot_*.png /sdcard/recording_*.mp4 /sdcard/burst_*.png 2>/dev/null"])
    if not ok or not out.strip():
        ui.success("Device is clean! No leftover capture artifacts found.")
        return

    files = [f.strip() for f in out.splitlines() if f.strip()]
    ui.warning(f"Found {len(files)} temporary capture file(s) on device:")
    for f in files[:10]:
        print(f"  • {f}")
    if len(files) > 10:
        print(f"  ... and {len(files) - 10} more.")

    if ui.confirm("Delete these temporary capture files from device?"):
        adb.run(["shell", "rm -f /sdcard/screenshot_*.png /sdcard/recording_*.mp4 /sdcard/burst_*.png"])
        ui.success("Temporary files cleaned successfully.")


# ─── Core Recording Runner ───────────────────────────────────────────────────

def _record_screen(
    duration: int = 10,
    bitrate: Optional[int] = None,
    size: Optional[str] = None,
    show_touches: bool = False,
    rotate: bool = False,
    bugreport: bool = False,
    label: str = "",
) -> bool:
    """
    Execute screenrecord on device, stream timer, pull video, and clean up.

    Parameters
    ----------
    duration : int
        Recording length in seconds (max 180).
    bitrate : int, optional
        Bitrate in bits per second (e.g. 8000000).
    size : str, optional
        Resolution string (e.g. '1280x720').
    show_touches : bool
        Whether to enable visual touch indicators during recording.
    rotate : bool
        Whether to rotate output 90 degrees.
    bugreport : bool
        Whether to add timestamp / frame debug info overlay.
    label : str
        Display header.

    Returns
    -------
    bool
        True if recording succeeded and video is saved locally.
    """
    if label:
        ui.header(label)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    remote_filename = f"recording_{timestamp}.mp4"
    remote_path = f"/sdcard/{remote_filename}"

    local_dir = _get_captures_dir("recordings")
    local_filename = f"screenrecord_{timestamp}.mp4"
    local_path = os.path.join(local_dir, local_filename)

    # Build screenrecord command
    cmd = ["shell", "screenrecord", "--time-limit", str(duration)]
    if bitrate:
        cmd.extend(["--bit-rate", str(bitrate)])
    if size:
        cmd.extend(["--size", size])
    if rotate:
        cmd.append("--rotate")
    if bugreport:
        cmd.append("--bugreport")
    cmd.append(remote_path)

    # Enable touch indicators if requested
    if show_touches:
        adb.run(["shell", "settings", "put", "system", "show_touches", "1"])

    ui.info(f"Recording started! Length: {duration}s | Destination: {remote_path}")
    ui.info("Interact with the device now...")

    # Run the recording with safety timeout buffer
    ok, rec_out = adb.run(cmd, timeout=duration + 20)

    # Restore touch indicators setting
    if show_touches:
        adb.run(["shell", "settings", "put", "system", "show_touches", "0"])

    if not ok and "No such file" in rec_out:
        ui.error(f"Recording failed: {rec_out}")
        return False

    ui.info("Finalizing video container on device...")
    time.sleep(1.5)

    ui.info("Transferring video to host PC...")
    ok_pull, pull_out = adb.run(["pull", remote_path, local_path], timeout=90)
    adb.run(["shell", "rm", "-f", remote_path])

    if ok_pull and os.path.isfile(local_path):
        size_bytes = os.path.getsize(local_path)
        ui.success(f"Video saved: {local_path} ({_human_size(size_bytes)})")
        if ui.confirm("Open recording in default video player?"):
            _open_file(local_path)
        return True
    else:
        ui.error(f"Failed to pull video: {pull_out}")
        return False


# ─── Main Menu Entry Point ───────────────────────────────────────────────────

def screen_capture_menu():
    """Public entry function and interactive loop for the Screen Capture module."""
    while True:
        ui.clear()
        ui.print_banner()
        ui.print_sub_banner("Screen Capture & Recording", icon="📸")

        options = [
            "Take single screenshot (timestamped)",
            "Take burst screenshots (series with delay)",
            "Record screen (default 10s)",
            "Record screen (custom duration, max 180s)",
            "Record screen with custom bitrate",
            "Record screen with custom resolution",
            "Take screenshot of specific display",
            "Open screenshot / capture folder",
            "Advanced recording (touches, bitrate, size)",
            "View capture history & media list",
            "Clean remote temporary capture files",
        ]

        ui.print_menu("Screen Capture Operations", options, columns=2)
        choice = ui.get_choice()

        if choice == "0":
            break
        elif choice == "1":
            take_single_screenshot()
        elif choice == "2":
            take_burst_screenshots()
        elif choice == "3":
            record_screen_default()
        elif choice == "4":
            record_screen_custom_duration()
        elif choice == "5":
            record_screen_custom_bitrate()
        elif choice == "6":
            record_screen_custom_resolution()
        elif choice == "7":
            take_screenshot_specific_display()
        elif choice == "8":
            open_captures_folder()
        elif choice == "9":
            record_screen_advanced()
        elif choice == "10":
            view_capture_history()
        elif choice == "11":
            clean_remote_temp_files()
        else:
            ui.error("Invalid option. Please choose a valid number from the menu.")

        ui.pause()
