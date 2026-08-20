"""
modules/fastboot_tools.py — Fastboot operations and bootloader management.

Provides a comprehensive suite of fastboot commands including device detection,
bootloader variable inspection, partition flashing, partition erasing, rebooting,
OEM unlocking/locking, temporary booting, and A/B slot switching.
"""

import os
import time
from datetime import datetime
from typing import Optional, List, Dict, Tuple

from core.adb import adb
from core import ui
from core.device import ensure_device


# ─── Pre-flight & Fastboot Helpers ────────────────────────────────────────────

def _check_fastboot() -> bool:
    """
    Verify that fastboot is installed and accessible on PATH.

    Returns:
        bool: True if fastboot binary exists, False otherwise.
    """
    if not adb.is_fastboot_installed():
        ui.error("Fastboot is not installed or not found on PATH!")
        print(f"\n  {ui.Colors.CYAN}To use Fastboot:{ui.Colors.RESET}")
        print("  1. Download Android SDK Platform-Tools from:")
        print(f"     {ui.Colors.UNDERLINE}https://developer.android.com/studio/releases/platform-tools{ui.Colors.RESET}")
        print("  2. Ensure fastboot is added to your system PATH.")
        print("  3. Install OEM USB Fastboot drivers on Windows (e.g., Google USB Driver).")
        return False
    return True


def _get_fastboot_devices() -> List[Dict[str, str]]:
    """
    Query connected devices in fastboot or fastbootd mode.

    Returns:
        List[Dict[str, str]]: List of dicts with 'serial' and 'mode'.
    """
    ok, output = adb.run_fastboot(["devices"])
    if not ok or not output.strip():
        return []

    devices = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            devices.append({"serial": parts[0], "mode": parts[1]})
        elif len(parts) == 1:
            devices.append({"serial": parts[0], "mode": "fastboot"})
    return devices


def _clean_path(path_str: str) -> str:
    """Strip quotes and expand user home directory in a file path."""
    clean = path_str.strip().strip("'\"")
    return os.path.expanduser(clean)


def _validate_image_file(path_str: str) -> Optional[str]:
    """
    Validate that an image file path exists and is a readable file.

    Returns:
        Optional[str]: Cleaned absolute path if valid, None otherwise.
    """
    cleaned = _clean_path(path_str)
    if not cleaned:
        ui.error("No file path provided.")
        return None
    if not os.path.isfile(cleaned):
        ui.error(f"File not found: {cleaned}")
        return None
    return os.path.abspath(cleaned)


def _format_bytes(size_bytes: int) -> str:
    """Format byte count into human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


# ─── 1. Check Fastboot Devices ────────────────────────────────────────────────

def check_fastboot_devices():
    """List all devices connected in Fastboot / Fastbootd mode."""
    if not _check_fastboot():
        return

    ui.header("Scanning for Fastboot Devices...")
    fb_devs = _get_fastboot_devices()

    # Also check normal ADB devices for context
    adb_serials = adb.get_connected_serials()

    if fb_devs:
        ui.success(f"Found {len(fb_devs)} device(s) in Fastboot mode:")
        rows = []
        for i, d in enumerate(fb_devs, 1):
            rows.append((f"  {i}", d["serial"], d["mode"].upper(), "Ready for Fastboot commands"))
        ui.print_table(rows, headers=("  #", "Serial Number", "Mode", "Status"))
    else:
        ui.warning("No devices found in Fastboot mode.")
        if adb_serials:
            ui.info(f"Detected {len(adb_serials)} device(s) in normal ADB mode: {', '.join(adb_serials)}")
            print(f"  {ui.Colors.CYAN}Tip:{ui.Colors.RESET} Use option 14 to reboot your device into Fastboot/Bootloader mode.")
        else:
            print(f"\n  {ui.Colors.DIM}Troubleshooting:{ui.Colors.RESET}")
            print("  • Power off device, hold Volume Down + Power button.")
            print("  • Ensure OEM Fastboot / Bootloader USB drivers are installed.")
            print("  • Try a different USB cable or rear USB 2.0/3.0 port.")


# ─── 2. Get Bootloader Variables ──────────────────────────────────────────────

def get_bootloader_variables():
    """Retrieve and categorize all bootloader variables via fastboot getvar all."""
    if not _check_fastboot():
        return

    fb_devs = _get_fastboot_devices()
    if not fb_devs:
        ui.warning("No device in Fastboot mode detected. Fastboot commands may hang if no device is connected.")
        if not ui.confirm("Do you want to attempt 'fastboot getvar all' anyway?"):
            return

    ui.header("Querying Bootloader Variables (fastboot getvar all)...")
    ok, output = adb.run_fastboot(["getvar", "all"], timeout=20)

    if not ok and not output.strip():
        ui.error("Failed to read bootloader variables. Ensure device is in fastboot mode.")
        return

    # Fastboot output typically comes on stderr or formatted lines like:
    # (bootloader) product: sweet
    # (bootloader) version-bootloader: 1.0
    # or key: value
    raw_lines = output.splitlines()
    var_dict: Dict[str, str] = {}

    for line in raw_lines:
        line = line.strip()
        if not line or "finished. total time" in line.lower():
            continue
        if line.startswith("(bootloader)"):
            line = line[len("(bootloader)"):].strip()
        if ":" in line:
            k, v = line.split(":", 1)
            var_dict[k.strip()] = v.strip()

    if not var_dict:
        ui.info("Raw output received:")
        for line in raw_lines:
            print(f"  {line}")
        return

    # Categorize key variables
    hw_keys = ["product", "hw-revision", "variant", "board", "version-bootloader", "version-baseband", "soc-id"]
    sec_keys = ["unlocked", "secure", "off-mode-charge", "charger-screen-enabled", "snapshot-update-status", "warranty-void"]
    slot_keys = ["slot-count", "current-slot", "slot-successful:a", "slot-successful:b", "slot-unbootable:a", "slot-unbootable:b", "slot-retry-count:a", "slot-retry-count:b"]
    pwr_keys = ["battery-voltage", "battery-soc-ok", "max-download-size", "partition-size:boot", "partition-type:boot"]

    ui.success(f"Retrieved {len(var_dict)} bootloader variables:")

    # Hardware Section
    hw_data = {k: var_dict[k] for k in hw_keys if k in var_dict}
    if hw_data:
        ui.header("  ⚙️  Hardware & Firmware")
        ui.print_kv(hw_data, indent=6)

    # Security Section
    sec_data = {k: var_dict[k] for k in sec_keys if k in var_dict}
    if sec_data:
        ui.header("  🔒  Bootloader Security")
        ui.print_kv(sec_data, indent=6)

    # Slot & Partition Section
    slot_data = {k: var_dict[k] for k in slot_keys if k in var_dict}
    if slot_data:
        ui.header("  🔀  A/B Slots & Bootability")
        ui.print_kv(slot_data, indent=6)

    # Power & Limits Section
    pwr_data = {k: var_dict[k] for k in pwr_keys if k in var_dict}
    if pwr_data:
        ui.header("  ⚡  Power & Download Limits")
        ui.print_kv(pwr_data, indent=6)

    # Offer to dump all variables
    print()
    if ui.confirm("Would you like to view all remaining raw variables or export to file?"):
        sub = ui.get_choice("[1] View all in console  |  [2] Export to text file")
        if sub == "1":
            print(f"\n{ui.Colors.BOLD}  All Bootloader Variables ({len(var_dict)} items):{ui.Colors.RESET}\n")
            for k, v in sorted(var_dict.items()):
                print(f"    {ui.Colors.CYAN}{k:<35}{ui.Colors.RESET} : {v}")
        elif sub == "2":
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"fastboot_vars_{ts}.txt"
            try:
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(f"=== FASTBOOT GETVAR ALL DUMP ({datetime.now().isoformat()}) ===\n\n")
                    for k, v in sorted(var_dict.items()):
                        f.write(f"{k} = {v}\n")
                ui.success(f"Variables exported to: {os.path.abspath(fname)}")
            except Exception as e:
                ui.error(f"Failed to export: {e}")


# ─── 3. Get Specific Bootloader Variable ──────────────────────────────────────

def get_specific_variable():
    """Query a single bootloader variable (e.g. unlocked, product, current-slot)."""
    if not _check_fastboot():
        return

    common_vars = [
        "product",
        "unlocked",
        "secure",
        "current-slot",
        "slot-count",
        "version-bootloader",
        "version-baseband",
        "max-download-size",
        "battery-voltage",
        "battery-soc-ok",
    ]

    print(f"\n  {ui.Colors.BOLD}Common fastboot variables:{ui.Colors.RESET}")
    print("  " + ", ".join(common_vars))

    var_name = ui.get_choice("Enter variable name to query (or type custom)")
    if not var_name:
        ui.error("Variable name cannot be empty.")
        return

    ui.header(f"Querying variable '{var_name}'...")
    ok, output = adb.run_fastboot(["getvar", var_name], timeout=15)
    if ok or output:
        clean_lines = [l.replace("(bootloader)", "").strip() for l in output.splitlines() if l.strip() and "finished" not in l]
        if clean_lines:
            for l in clean_lines:
                ui.info(l)
        else:
            ui.info(f"{var_name}: {output}")
    else:
        ui.error(f"Failed to query '{var_name}'.")


# ─── 4. Flash Boot Image ──────────────────────────────────────────────────────

def flash_boot_image():
    """Flash a boot image (boot.img or Magisk-patched boot) to the device."""
    if not _check_fastboot():
        return

    ui.header("Flash Boot Image (boot.img)")
    print(f"  {ui.Colors.DIM}Note: Flashing custom boot images can root device or enable custom kernels.{ui.Colors.RESET}")

    path = ui.get_choice("Enter path to boot image file (.img)")
    valid_path = _validate_image_file(path)
    if not valid_path:
        return

    file_size = os.path.getsize(valid_path)
    ui.info(f"Selected file: {valid_path} ({_format_bytes(file_size)})")

    # Check for slot option
    slot_choice = ui.get_choice("Target partition: [1] boot (active/default)  [2] boot_a  [3] boot_b  [4] init_boot")
    target = "boot"
    if slot_choice == "2":
        target = "boot_a"
    elif slot_choice == "3":
        target = "boot_b"
    elif slot_choice == "4":
        target = "init_boot"

    if not ui.confirm(f"Are you sure you want to flash '{os.path.basename(valid_path)}' to partition '{target}'?"):
        ui.warning("Operation cancelled.")
        return

    ui.header(f"Flashing '{valid_path}' to '{target}'...")
    start_t = time.time()
    ok, output = adb.run_fastboot(["flash", target, valid_path], timeout=120)
    elapsed = time.time() - start_t

    if ok:
        ui.success(f"Boot image flashed successfully in {elapsed:.2f}s!")
        if output:
            print(f"  {output}")
    else:
        ui.error(f"Flashing failed: {output}")


# ─── 5. Flash Recovery Image ──────────────────────────────────────────────────

def flash_recovery_image():
    """Flash a custom recovery image (TWRP, OrangeFox, PBRP, etc.) to recovery."""
    if not _check_fastboot():
        return

    ui.header("Flash Recovery Image (recovery.img)")
    path = ui.get_choice("Enter path to recovery image file (.img)")
    valid_path = _validate_image_file(path)
    if not valid_path:
        return

    file_size = os.path.getsize(valid_path)
    ui.info(f"Selected file: {valid_path} ({_format_bytes(file_size)})")

    slot_choice = ui.get_choice("Target partition: [1] recovery  [2] recovery_a  [3] recovery_b")
    target = "recovery"
    if slot_choice == "2":
        target = "recovery_a"
    elif slot_choice == "3":
        target = "recovery_b"

    if not ui.confirm(f"Flash recovery image to '{target}'?"):
        ui.warning("Operation cancelled.")
        return

    ui.header(f"Flashing recovery image to '{target}'...")
    start_t = time.time()
    ok, output = adb.run_fastboot(["flash", target, valid_path], timeout=120)
    elapsed = time.time() - start_t

    if ok:
        ui.success(f"Recovery image flashed successfully in {elapsed:.2f}s!")
        if output:
            print(f"  {output}")
    else:
        ui.error(f"Recovery flashing failed: {output}")
        print(f"  {ui.Colors.CYAN}Tip:{ui.Colors.RESET} Devices using A/B seamless updates often do not have a dedicated recovery partition. Try flashing to boot or use option 11 (fastboot boot).")


# ─── 6. Flash System Image ────────────────────────────────────────────────────

def flash_system_image():
    """Flash a system image (GSI or ROM system.img) to system partition."""
    if not _check_fastboot():
        return

    ui.header("Flash System Image (system.img / GSI)")
    ui.warning("Flashing system.img modifies core OS files. Ensure bootloader is unlocked.")

    path = ui.get_choice("Enter path to system image file (.img)")
    valid_path = _validate_image_file(path)
    if not valid_path:
        return

    file_size = os.path.getsize(valid_path)
    ui.info(f"Selected file: {valid_path} ({_format_bytes(file_size)})")

    slot_choice = ui.get_choice("Target partition: [1] system  [2] system_a  [3] system_b")
    target = "system"
    if slot_choice == "2":
        target = "system_a"
    elif slot_choice == "3":
        target = "system_b"

    if not ui.confirm(f"CRITICAL: Flash system image to '{target}' ({_format_bytes(file_size)})?"):
        ui.warning("Operation cancelled.")
        return

    ui.header(f"Flashing system image to '{target}' (this may take 2-5 minutes)...")
    start_t = time.time()
    ok, output = adb.run_fastboot(["flash", target, valid_path], timeout=600)
    elapsed = time.time() - start_t

    if ok:
        ui.success(f"System partition flashed successfully in {elapsed:.2f}s!")
        if output:
            print(f"  {output}")
    else:
        ui.error(f"System flashing failed: {output}")
        print(f"  {ui.Colors.CYAN}Tip:{ui.Colors.RESET} On Android 10+ devices with Dynamic Partitions (super), you may need to enter fastbootd (option 8 -> Reboot Fastbootd).")


# ─── 7. Flash Custom Partition ────────────────────────────────────────────────

def flash_custom_partition():
    """Flash an image to any arbitrary partition (vendor, vbmeta, dtbo, etc.)."""
    if not _check_fastboot():
        return

    ui.header("Flash Custom Partition")
    print(f"  {ui.Colors.BOLD}Common partitions:{ui.Colors.RESET} vendor, vbmeta, dtbo, radio, modem, userdata, cache, splash, logo, product")

    partition = ui.get_choice("Enter partition name to flash").strip().lower()
    if not partition:
        ui.error("Partition name cannot be empty.")
        return

    path = ui.get_choice(f"Enter path to image file for partition '{partition}'")
    valid_path = _validate_image_file(path)
    if not valid_path:
        return

    file_size = os.path.getsize(valid_path)
    ui.info(f"Partition: {partition}  |  File: {valid_path} ({_format_bytes(file_size)})")

    # Extra flags for vbmeta (AVB verification disable)
    extra_flags = []
    if "vbmeta" in partition:
        if ui.confirm("Disable AVB/dm-verity and verification flags (--disable-verity --disable-verification)?"):
            extra_flags = ["--disable-verity", "--disable-verification"]
            ui.info("Added: --disable-verity --disable-verification")

    if not ui.confirm(f"Confirm flashing '{os.path.basename(valid_path)}' to '{partition}'?"):
        ui.warning("Operation cancelled.")
        return

    cmd = extra_flags + ["flash", partition, valid_path]
    ui.header(f"Executing: fastboot {' '.join(cmd)}...")
    start_t = time.time()
    ok, output = adb.run_fastboot(cmd, timeout=300)
    elapsed = time.time() - start_t

    if ok:
        ui.success(f"Partition '{partition}' flashed successfully in {elapsed:.2f}s!")
        if output:
            print(f"  {output}")
    else:
        ui.error(f"Flashing failed: {output}")


# ─── 8. Erase / Wipe Partition ────────────────────────────────────────────────

def erase_partition():
    """Erase (format/wipe) a specified partition."""
    if not _check_fastboot():
        return

    ui.header("Erase / Wipe Partition")
    print(f"  {ui.Colors.RED}{ui.Colors.BOLD}WARNING: Erasing partitions irreversibly destroys stored data!{ui.Colors.RESET}")
    print(f"  {ui.Colors.BOLD}Common wipe targets:{ui.Colors.RESET} userdata, cache, metadata, misc, boot, recovery")

    partition = ui.get_choice("Enter partition name to erase").strip().lower()
    if not partition:
        ui.error("Partition name cannot be empty.")
        return

    if partition in ("system", "vendor", "super", "bootloader", "xbl", "abl"):
        ui.error(f"SAFETY GUARD: Erasing critical partition '{partition}' can permanently brick device!")
        if not ui.confirm(f"Are you ABSOLUTELY certain you want to proceed with erasing '{partition}'?"):
            ui.warning("Operation aborted.")
            return

    if not ui.confirm(f"Are you sure you want to ERASE partition '{partition}'?"):
        ui.warning("Operation cancelled.")
        return

    ui.header(f"Erasing partition '{partition}'...")
    ok, output = adb.run_fastboot(["erase", partition], timeout=60)
    if ok:
        ui.success(f"Partition '{partition}' erased successfully.")
        if output:
            print(f"  {output}")
    else:
        ui.error(f"Erase failed: {output}")


# ─── 9. Reboot Options ────────────────────────────────────────────────────────

def reboot_from_fastboot():
    """Reboot device from fastboot into various targets."""
    if not _check_fastboot():
        return

    while True:
        ui.clear()
        ui.print_banner()
        ui.print_menu("🔄 Fastboot Reboot Menu", [
            "Normal Reboot (System)",
            "Reboot to Recovery Mode",
            "Reboot to Bootloader / Fastboot",
            "Reboot to Fastbootd (Userspace Fastboot)",
            "Continue Normal Boot Sequence (fastboot continue)",
            "OEM Power Off Device",
        ])
        choice = ui.get_choice()

        if choice == "0":
            break
        elif choice == "1":
            ui.header("Rebooting to System (fastboot reboot)...")
            ok, out = adb.run_fastboot(["reboot"])
            if ok:
                ui.success("Device is rebooting to System.")
            else:
                ui.error(f"Reboot failed: {out}")
            ui.pause()
            break
        elif choice == "2":
            ui.header("Rebooting to Recovery (fastboot reboot recovery)...")
            ok, out = adb.run_fastboot(["reboot", "recovery"])
            if ok:
                ui.success("Device is rebooting to Recovery.")
            else:
                ui.error(f"Reboot failed: {out}")
            ui.pause()
            break
        elif choice == "3":
            ui.header("Rebooting to Bootloader (fastboot reboot bootloader)...")
            ok, out = adb.run_fastboot(["reboot", "bootloader"])
            if ok:
                ui.success("Device is rebooting to Bootloader.")
            else:
                ui.error(f"Reboot failed: {out}")
            ui.pause()
            break
        elif choice == "4":
            ui.header("Rebooting to Fastbootd (fastboot reboot fastboot)...")
            ok, out = adb.run_fastboot(["reboot", "fastboot"])
            if ok:
                ui.success("Device is rebooting to Fastbootd (userspace fastboot).")
            else:
                ui.error(f"Reboot failed: {out}")
            ui.pause()
            break
        elif choice == "5":
            ui.header("Continuing Boot (fastboot continue)...")
            ok, out = adb.run_fastboot(["continue"])
            if ok:
                ui.success("Boot sequence continued.")
            else:
                ui.error(f"Command failed: {out}")
            ui.pause()
            break
        elif choice == "6":
            ui.header("Powering off device...")
            ok, out = adb.run_fastboot(["oem", "poweroff"])
            if ok:
                ui.success("Device powering off.")
            else:
                ui.error(f"Power off failed: {out}")
            ui.pause()
            break
        else:
            ui.error("Invalid option.")
            ui.pause()


# ─── 10. OEM Unlock ───────────────────────────────────────────────────────────

def oem_unlock():
    """Perform OEM / Bootloader unlock with comprehensive safety checks."""
    if not _check_fastboot():
        return

    ui.clear()
    ui.print_banner()
    print(f"\n{ui.Colors.BG_RED}{ui.Colors.WHITE}{ui.Colors.BOLD}                 ⚠️  CRITICAL WARNING: OEM BOOTLOADER UNLOCK  ⚠️                 {ui.Colors.RESET}\n")
    print(f"  {ui.Colors.RED}1. Unlocking the bootloader will COMPLETELY FACTORY RESET your device.{ui.Colors.RESET}")
    print(f"  {ui.Colors.RED}2. All photos, apps, messages, and user data WILL BE WIPED IRREVERSIBLY.{ui.Colors.RESET}")
    print(f"  {ui.Colors.YELLOW}3. OEM unlocking may void your manufacturer warranty.{ui.Colors.RESET}")
    print(f"  {ui.Colors.YELLOW}4. Ensure 'OEM Unlocking' was enabled in Developer Options inside Android OS.{ui.Colors.RESET}")
    print(f"  {ui.Colors.CYAN}5. You may need to confirm the unlock physically on your device screen using volume keys.{ui.Colors.RESET}\n")

    if not ui.confirm("Do you understand all risks and want to proceed with Bootloader Unlock?"):
        ui.warning("OEM Unlock aborted by user.")
        return

    double_check = ui.get_choice("Type 'UNLOCK' in uppercase to confirm")
    if double_check != "UNLOCK":
        ui.warning("Confirmation phrase did not match. Aborted.")
        return

    method = ui.get_choice("Unlock command method: [1] Modern (fastboot flashing unlock)  [2] Legacy (fastboot oem unlock)  [3] Critical partitions (fastboot flashing unlock_critical)")
    cmd = ["flashing", "unlock"]
    if method == "2":
        cmd = ["oem", "unlock"]
    elif method == "3":
        cmd = ["flashing", "unlock_critical"]

    ui.header(f"Sending unlock command: fastboot {' '.join(cmd)}...")
    ok, output = adb.run_fastboot(cmd, timeout=60)

    if ok:
        ui.success("Unlock command dispatched successfully!")
        print(f"  {ui.Colors.CYAN}👉 LOOK AT YOUR DEVICE SCREEN NOW!{ui.Colors.RESET}")
        print("  Use the Volume Up / Volume Down keys to select 'Unlock Bootloader' and press Power.")
        if output:
            print(f"  {output}")
    else:
        ui.error(f"Unlock command failed: {output}")
        print(f"\n  {ui.Colors.DIM}Possible causes:{ui.Colors.RESET}")
        print("  • 'OEM unlocking' is disabled in Android Developer Options.")
        print("  • The device requires an OEM unlock token/key (Xiaomi, Motorola, Sony, etc.).")
        print("  • Carrier-locked device (Verizon, AT&T) does not permit bootloader unlock.")


# ─── 11. OEM Lock ─────────────────────────────────────────────────────────────

def oem_lock():
    """Relock the bootloader with verification warnings."""
    if not _check_fastboot():
        return

    ui.clear()
    ui.print_banner()
    print(f"\n{ui.Colors.BG_RED}{ui.Colors.WHITE}{ui.Colors.BOLD}                 ⚠️  CRITICAL WARNING: OEM BOOTLOADER LOCK  ⚠️                   {ui.Colors.RESET}\n")
    print(f"  {ui.Colors.RED}1. Relocking the bootloader WILL FACTORY RESET the device.{ui.Colors.RESET}")
    print(f"  {ui.Colors.RED}2. WARNING: You MUST ensure 100% STOCK FIRMWARE is flashed before relocking!{ui.Colors.RESET}")
    print(f"  {ui.Colors.RED}   If a custom ROM, custom recovery, or modified boot/vbmeta is installed,{ui.Colors.RESET}")
    print(f"  {ui.Colors.RED}   relocking will cause a HARD BRICK (device will refuse to boot).{ui.Colors.RESET}\n")

    if not ui.confirm("Is 100% clean official stock firmware currently flashed?"):
        ui.warning("OEM Lock aborted. Flash official stock firmware first!")
        return

    if not ui.confirm("Do you want to proceed with relocking the bootloader?"):
        ui.warning("OEM Lock cancelled.")
        return

    method = ui.get_choice("Lock command method: [1] Modern (fastboot flashing lock)  [2] Legacy (fastboot oem lock)")
    cmd = ["flashing", "lock"] if method != "2" else ["oem", "lock"]

    ui.header(f"Sending lock command: fastboot {' '.join(cmd)}...")
    ok, output = adb.run_fastboot(cmd, timeout=60)

    if ok:
        ui.success("Lock command dispatched. Confirm on device screen if prompted.")
        if output:
            print(f"  {output}")
    else:
        ui.error(f"Lock command failed: {output}")


# ─── 12. Boot Image Without Flashing ──────────────────────────────────────────

def boot_image_temporarily():
    """Boot a kernel / recovery image in RAM without writing to flash (fastboot boot)."""
    if not _check_fastboot():
        return

    ui.header("Boot Image Without Flashing (fastboot boot)")
    print(f"  {ui.Colors.CYAN}ℹ Info:{ui.Colors.RESET} This loads the image directly into RAM and boots it once.")
    print("  Your device flash partitions remain completely untouched.")
    print("  Ideal for testing custom recoveries (TWRP) or rooted boot images without permanent modification.\n")

    path = ui.get_choice("Enter path to boot / recovery image (.img)")
    valid_path = _validate_image_file(path)
    if not valid_path:
        return

    file_size = os.path.getsize(valid_path)
    ui.info(f"Image file: {valid_path} ({_format_bytes(file_size)})")

    if not ui.confirm("Send image and boot temporarily?"):
        ui.warning("Operation cancelled.")
        return

    ui.header(f"Sending '{os.path.basename(valid_path)}' to RAM and booting...")
    start_t = time.time()
    ok, output = adb.run_fastboot(["boot", valid_path], timeout=120)
    elapsed = time.time() - start_t

    if ok:
        ui.success(f"Device booted image successfully in {elapsed:.2f}s!")
        if output:
            print(f"  {output}")
    else:
        ui.error(f"Boot command failed: {output}")
        print(f"  {ui.Colors.DIM}Note: Some modern devices (Android 12+) disabled 'fastboot boot' support at bootloader level.{ui.Colors.RESET}")


# ─── 13. Switch Active Slot (A/B Partitioning) ────────────────────────────────

def switch_active_slot():
    """Inspect and change active A/B slot on seamless update devices."""
    if not _check_fastboot():
        return

    ui.header("A/B Slot Management")
    ok, out = adb.run_fastboot(["getvar", "current-slot"], timeout=10)
    curr_slot = "unknown"
    if ok or out:
        for line in out.splitlines():
            if "current-slot" in line:
                parts = line.replace("(bootloader)", "").split(":")
                if len(parts) >= 2:
                    curr_slot = parts[1].strip()

    ui.info(f"Current active slot: {ui.Colors.BOLD}{curr_slot.upper()}{ui.Colors.RESET}")

    choice = ui.get_choice("Select action: [1] Set Slot A  [2] Set Slot B  [3] Toggle to other slot")
    target_slot = None
    if choice == "1":
        target_slot = "a"
    elif choice == "2":
        target_slot = "b"
    elif choice == "3":
        target_slot = "other"
    else:
        ui.warning("Invalid choice.")
        return

    ui.header(f"Setting active slot to '{target_slot}'...")
    ok, output = adb.run_fastboot(["--set-active=" + target_slot], timeout=15)
    if not ok:
        # Try alternate syntax
        ok, output = adb.run_fastboot(["set_active", target_slot], timeout=15)

    if ok:
        ui.success(f"Active slot switched to '{target_slot}'.")
        if output:
            print(f"  {output}")
    else:
        ui.error(f"Failed to switch slot: {output}")


# ─── 14. Reboot Device from ADB to Fastboot / Bootloader ─────────────────────

def reboot_adb_to_fastboot():
    """Reboot connected ADB device into Bootloader / Fastboot mode."""
    if not ensure_device():
        return

    ui.header(f"Rebooting ADB Device '{adb.serial}' to Bootloader...")
    target = ui.get_choice("Target mode: [1] Bootloader / Fastboot  [2] Fastbootd (userspace)  [3] Recovery")

    cmd = ["reboot", "bootloader"]
    if target == "2":
        cmd = ["reboot", "fastboot"]
    elif target == "3":
        cmd = ["reboot", "recovery"]

    ok, out = adb.run(cmd)
    if ok:
        ui.success(f"Reboot command sent to device: adb {' '.join(cmd)}")
        ui.info("Waiting 5 seconds for device to enter bootloader...")
        time.sleep(5)
        fb_devs = _get_fastboot_devices()
        if fb_devs:
            ui.success(f"Fastboot device detected: {fb_devs[0]['serial']}")
        else:
            ui.info("Device is rebooting. Run option 1 to detect fastboot devices once boot completes.")
    else:
        ui.error(f"Reboot failed: {out}")


# ─── Main Menu Loop ───────────────────────────────────────────────────────────

def fastboot_tools_menu():
    """Fastboot tools interactive submenu."""
    options = [
        "Check Fastboot Devices",
        "Get All Bootloader Variables (getvar all)",
        "Get Specific Bootloader Variable",
        "Flash Boot Image (boot.img)",
        "Flash Recovery Image (recovery.img)",
        "Flash System Image (system.img)",
        "Flash Custom Partition (vendor/vbmeta/etc.)",
        "Erase / Wipe Partition",
        "Reboot Options (System/Recovery/Bootloader)",
        "OEM Bootloader Unlock (flashing unlock)",
        "OEM Bootloader Lock (flashing lock)",
        "Boot Image Without Flashing (fastboot boot)",
        "Switch Active Slot (A/B Partitioning)",
        "Reboot Device from ADB into Fastboot",
    ]

    while True:
        ui.clear()
        ui.print_banner()
        ui.print_menu("⚡ Fastboot & Bootloader Tools", options, columns=2)

        choice = ui.get_choice()

        if choice == "0":
            break
        elif choice == "1":
            check_fastboot_devices()
        elif choice == "2":
            get_bootloader_variables()
        elif choice == "3":
            get_specific_variable()
        elif choice == "4":
            flash_boot_image()
        elif choice == "5":
            flash_recovery_image()
        elif choice == "6":
            flash_system_image()
        elif choice == "7":
            flash_custom_partition()
        elif choice == "8":
            erase_partition()
        elif choice == "9":
            reboot_from_fastboot()
        elif choice == "10":
            oem_unlock()
        elif choice == "11":
            oem_lock()
        elif choice == "12":
            boot_image_temporarily()
        elif choice == "13":
            switch_active_slot()
        elif choice == "14":
            reboot_adb_to_fastboot()
        else:
            ui.error("Invalid option. Please choose a valid number.")

        ui.pause()
