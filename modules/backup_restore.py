"""
modules/backup_restore.py — Android Backup and Restore Management Module.

Provides comprehensive backup and restore capabilities for DroidCommander including
full device backup, single app backup, data-only backup, shared storage archiving,
contacts extraction (vCard / CSV), SMS/Call logs dump, backup cataloging,
and .ab archive inspection.
"""

import csv
from datetime import datetime
import json
import os
import re
import shutil
import time
from typing import Any, Dict, List, Optional, Tuple

from core.adb import adb
from core import ui
from core.device import ensure_device


# ─── File & Path Helpers ──────────────────────────────────────────────────────

BACKUP_DIR = "backups"


def ensure_backup_dir() -> str:
    """Ensure the local backup storage directory exists and return its path."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    return BACKUP_DIR


def format_file_size(size_bytes: int) -> str:
    """Format byte count into human-readable string (KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_default_backup_path(prefix: str, extension: str = "ab") -> str:
    """Generate a standardized timestamped backup file path."""
    ensure_backup_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    serial_tag = adb.serial.replace(":", "_").replace(".", "_") if adb.serial else "device"
    filename = f"{prefix}_{serial_tag}_{timestamp}.{extension}"
    return os.path.join(BACKUP_DIR, filename)


def parse_ab_header(filepath: str) -> Dict[str, Any]:
    """
    Parse the header of an Android Backup (.ab) file.

    Parameters
    ----------
    filepath : str
        Local path to the .ab file.

    Returns
    -------
    dict[str, Any]
        Dictionary containing header metadata.
    """
    if not os.path.isfile(filepath):
        return {"Error": "File does not exist"}

    header_info: Dict[str, Any] = {
        "File Path": os.path.abspath(filepath),
        "File Size": format_file_size(os.path.getsize(filepath)),
        "Last Modified": datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        with open(filepath, "rb") as f:
            magic = f.readline().decode("utf-8", errors="ignore").strip()
            if magic != "ANDROID BACKUP":
                header_info["Valid Android Backup"] = "No (Invalid Magic)"
                return header_info

            header_info["Valid Android Backup"] = "Yes"
            header_info["Backup Version"] = f.readline().decode("utf-8", errors="ignore").strip()

            comp_flag = f.readline().decode("utf-8", errors="ignore").strip()
            header_info["Compressed"] = "Yes (zlib Deflated)" if comp_flag == "1" else "No (Raw tar)"

            enc_algo = f.readline().decode("utf-8", errors="ignore").strip()
            header_info["Encryption"] = enc_algo if enc_algo else "none"

            if enc_algo and enc_algo.lower() != "none":
                header_info["User Salt"] = f.readline().decode("utf-8", errors="ignore").strip()[:16] + "..."
                header_info["Checksum Salt"] = f.readline().decode("utf-8", errors="ignore").strip()[:16] + "..."
                header_info["PBKDF2 Rounds"] = f.readline().decode("utf-8", errors="ignore").strip()
                header_info["IV"] = f.readline().decode("utf-8", errors="ignore").strip()[:16] + "..."

    except Exception as e:
        header_info["Read Error"] = str(e)

    return header_info


# ─── Feature 1: Full Device Backup ───────────────────────────────────────────

def full_device_backup() -> None:
    """Create a complete device backup including installed APKs, app data, and shared storage."""
    if not ensure_device():
        return

    default_path = get_default_backup_path("backup_full")
    print(f"\n  {ui.Colors.CYAN}Default output path: {default_path}{ui.Colors.RESET}")
    custom_path = ui.get_choice("Enter output file path (Press Enter for default)")
    filepath = custom_path if custom_path else default_path

    # Options customization
    include_system = ui.confirm("Include system apps data? (y/n, default n)")
    system_flag = "-system" if include_system else "-nosystem"

    include_shared = ui.confirm("Include shared storage (/sdcard)? (y/n, default y)")
    shared_flag = "-shared" if include_shared else "-noshared"

    args = ["backup", "-apk", "-obb", shared_flag, "-all", system_flag, "-f", filepath]

    print(f"""
  {ui.Colors.BOLD}{ui.Colors.YELLOW}══════════════════════════════════════════════════════════════════{ui.Colors.RESET}
  {ui.Colors.BOLD}📱 ACTION REQUIRED ON YOUR ANDROID DEVICE:{ui.Colors.RESET}
    1. Unlock your device screen now.
    2. A full backup prompt will appear on your device screen.
    3. (Optional) Enter a desktop backup password to encrypt the backup.
    4. Tap {ui.Colors.GREEN}'Back up my data'{ui.Colors.RESET} to begin the backup process.
    5. Do {ui.Colors.RED}NOT{ui.Colors.RESET} disconnect the USB cable until finished.
  {ui.Colors.BOLD}{ui.Colors.YELLOW}══════════════════════════════════════════════════════════════════{ui.Colors.RESET}
    """)

    ui.info(f"Starting full device backup to: {filepath}...")
    start_time = time.time()

    # Run backup without capturing stdout so user sees live connection
    ok, _ = adb.run(args, timeout=3600, capture=False)
    duration = time.time() - start_time

    if os.path.isfile(filepath) and os.path.getsize(filepath) > 0:
        file_size = os.path.getsize(filepath)
        ui.success(f"Full device backup completed in {duration:.1f}s!")
        ui.print_kv({
            "Backup File": os.path.abspath(filepath),
            "Size": format_file_size(file_size),
            "Flags": f"-apk -obb {shared_flag} -all {system_flag}",
            "Status": "Verified on disk",
        })
    else:
        ui.error("Backup failed or was cancelled on the device.")
        if os.path.isfile(filepath) and os.path.getsize(filepath) == 0:
            os.remove(filepath)


# ─── Feature 2: Backup Specific App ──────────────────────────────────────────

def backup_specific_app() -> None:
    """Create a backup of a single specific application package."""
    if not ensure_device():
        return

    print(f"\n  {ui.Colors.CYAN}Options: Enter package name directly or type 'list' to browse 3rd-party apps.{ui.Colors.RESET}")
    pkg_input = ui.get_choice("Enter package name (e.g. com.whatsapp)")
    if not pkg_input:
        ui.error("Package name cannot be empty.")
        return

    if pkg_input.lower() == "list":
        ok, out = adb.run(["shell", "pm", "list", "packages", "-3"])
        if ok and out:
            packages = sorted([line.replace("package:", "").strip() for line in out.splitlines() if line.strip()])
            ui.header(f"Installed Third-Party Apps ({len(packages)}):")
            for i, p in enumerate(packages[:40], 1):
                print(f"    {ui.Colors.YELLOW}[{i:>2}]{ui.Colors.RESET} {p}")
            if len(packages) > 40:
                ui.info(f"...and {len(packages) - 40} more.")
            selected_idx = ui.get_choice("Select package number or enter name")
            if selected_idx.isdigit() and 1 <= int(selected_idx) <= len(packages):
                package = packages[int(selected_idx) - 1]
            else:
                package = selected_idx
        else:
            ui.error("Failed to query package list.")
            return
    else:
        package = pkg_input.strip()

    if not package:
        ui.error("Invalid package selection.")
        return

    include_apk = ui.confirm("Include APK installer file in backup? (y/n, default y)")
    apk_flag = "-apk" if include_apk else "-noapk"

    include_obb = ui.confirm("Include OBB expansion data? (y/n, default y)")
    obb_flag = "-obb" if include_obb else "-noobb"

    clean_pkg = re.sub(r"[^a-zA-Z0-9._-]", "_", package)
    default_path = get_default_backup_path(f"backup_{clean_pkg}")
    custom_path = ui.get_choice(f"Enter output path (Press Enter for '{default_path}')")
    filepath = custom_path if custom_path else default_path

    args = ["backup", apk_flag, obb_flag, "-f", filepath, package]

    print(f"""
  {ui.Colors.BOLD}{ui.Colors.YELLOW}══════════════════════════════════════════════════════════════════{ui.Colors.RESET}
  {ui.Colors.BOLD}📱 ACTION REQUIRED ON DEVICE:{ui.Colors.RESET}
    Unlock device and tap {ui.Colors.GREEN}'Back up my data'{ui.Colors.RESET} for {package}.
  {ui.Colors.BOLD}{ui.Colors.YELLOW}══════════════════════════════════════════════════════════════════{ui.Colors.RESET}
    """)

    ui.info(f"Backing up '{package}' to {filepath}...")
    start_time = time.time()
    adb.run(args, timeout=600, capture=False)
    duration = time.time() - start_time

    if os.path.isfile(filepath) and os.path.getsize(filepath) > 0:
        file_size = os.path.getsize(filepath)
        ui.success(f"Backup of '{package}' finished in {duration:.1f}s!")
        ui.print_kv({
            "Package": package,
            "Backup File": os.path.abspath(filepath),
            "Size": format_file_size(file_size),
            "Included APK": "Yes" if include_apk else "No",
        })
    else:
        ui.error(f"Backup of '{package}' failed or was cancelled.")
        if os.path.isfile(filepath) and os.path.getsize(filepath) == 0:
            os.remove(filepath)


# ─── Feature 3: Backup Without APKs (Data Only) ──────────────────────────────

def backup_data_only() -> None:
    """Create a lightweight data-only backup without embedding APK binaries."""
    if not ensure_device():
        return

    print(f"""
  {ui.Colors.BOLD}Data-Only Backup Scope:{ui.Colors.RESET}
    {ui.Colors.YELLOW}[1]{ui.Colors.RESET} All Applications (Data Only, No APKs)
    {ui.Colors.YELLOW}[2]{ui.Colors.RESET} Specific Application (Data Only, No APKs)
    """)

    scope = ui.get_choice("Select scope [1-2] (default 1)")
    if scope == "2":
        package = ui.get_choice("Enter package name to backup data for")
        if not package:
            ui.error("Package name cannot be empty.")
            return
        clean_pkg = re.sub(r"[^a-zA-Z0-9._-]", "_", package)
        default_path = get_default_backup_path(f"backup_data_{clean_pkg}")
        args = ["backup", "-noapk", "-obb", "-f", default_path, package]
        target_name = package
    else:
        default_path = get_default_backup_path("backup_data_all")
        args = ["backup", "-noapk", "-obb", "-all", "-nosystem", "-f", default_path]
        target_name = "All user applications"

    custom_path = ui.get_choice(f"Enter output path (Press Enter for '{default_path}')")
    filepath = custom_path if custom_path else default_path
    args[args.index(default_path)] = filepath

    print(f"""
  {ui.Colors.BOLD}{ui.Colors.YELLOW}══════════════════════════════════════════════════════════════════{ui.Colors.RESET}
  {ui.Colors.BOLD}📱 ACTION REQUIRED ON DEVICE:{ui.Colors.RESET}
    Unlock device and tap {ui.Colors.GREEN}'Back up my data'{ui.Colors.RESET}.
  {ui.Colors.BOLD}{ui.Colors.YELLOW}══════════════════════════════════════════════════════════════════{ui.Colors.RESET}
    """)

    ui.info(f"Starting data-only backup for: {target_name}...")
    start_time = time.time()
    adb.run(args, timeout=1800, capture=False)
    duration = time.time() - start_time

    if os.path.isfile(filepath) and os.path.getsize(filepath) > 0:
        file_size = os.path.getsize(filepath)
        ui.success(f"Data-only backup finished in {duration:.1f}s!")
        ui.print_kv({
            "Target": target_name,
            "Backup File": os.path.abspath(filepath),
            "Size": format_file_size(file_size),
            "Type": "App Data Only (-noapk)",
        })
    else:
        ui.error("Backup failed or was cancelled.")
        if os.path.isfile(filepath) and os.path.getsize(filepath) == 0:
            os.remove(filepath)


# ─── Feature 4: Backup Shared Storage ────────────────────────────────────────

def backup_shared_storage() -> None:
    """Backup files, photos, and media from shared internal storage (/sdcard)."""
    if not ensure_device():
        return

    print(f"""
  {ui.Colors.BOLD}Select Shared Storage Backup Method:{ui.Colors.RESET}
    {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Direct File Pull (Pull folders: DCIM, Pictures, Documents, Download)
    {ui.Colors.YELLOW}[2]{ui.Colors.RESET} Full /sdcard/ Directory Pull
    {ui.Colors.YELLOW}[3]{ui.Colors.RESET} ADB Backup Archive (.ab format: adb backup -shared)
    """)

    method = ui.get_choice("Select backup method [1-3] (default 1)")

    if method == "3":
        # ADB Backup archive method
        default_path = get_default_backup_path("backup_shared_storage")
        filepath = ui.get_choice(f"Enter backup file path (default '{default_path}')") or default_path
        args = ["backup", "-shared", "-noapk", "-nosystem", "-f", filepath]

        print(f"""
  {ui.Colors.BOLD}{ui.Colors.YELLOW}══════════════════════════════════════════════════════════════════{ui.Colors.RESET}
  {ui.Colors.BOLD}📱 ACTION REQUIRED ON DEVICE:{ui.Colors.RESET}
    Unlock device and tap {ui.Colors.GREEN}'Back up my data'{ui.Colors.RESET}.
  {ui.Colors.BOLD}{ui.Colors.YELLOW}══════════════════════════════════════════════════════════════════{ui.Colors.RESET}
        """)
        ui.info(f"Creating shared storage archive at: {filepath}...")
        adb.run(args, timeout=3600, capture=False)

        if os.path.isfile(filepath) and os.path.getsize(filepath) > 0:
            ui.success(f"Shared storage archive created ({format_file_size(os.path.getsize(filepath))}).")
        else:
            ui.error("Shared storage backup failed.")
        return

    # Direct Pull methods
    ensure_backup_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    serial_tag = adb.serial.replace(":", "_") if adb.serial else "device"
    dest_dir = os.path.join(BACKUP_DIR, f"storage_{serial_tag}_{timestamp}")
    os.makedirs(dest_dir, exist_ok=True)

    if method == "2":
        folders = ["/sdcard/"]
    else:
        folders = [
            "/sdcard/DCIM",
            "/sdcard/Pictures",
            "/sdcard/Documents",
            "/sdcard/Download",
            "/sdcard/Music",
            "/sdcard/Movies",
        ]

    ui.info(f"Pulling media files to local destination: {os.path.abspath(dest_dir)}")
    total_pulled = 0

    for folder in folders:
        folder_name = os.path.basename(folder.rstrip("/"))
        local_target = os.path.join(dest_dir, folder_name) if folder != "/sdcard/" else dest_dir
        ui.info(f"Pulling {folder}...")
        ok, out = adb.run(["pull", folder, local_target], timeout=1800, capture=False)
        if ok:
            total_pulled += 1

    ui.success(f"Media & storage backup completed!")
    ui.print_kv({
        "Local Directory": os.path.abspath(dest_dir),
        "Folders Processed": str(len(folders)),
    })


# ─── Feature 5: Restore from Backup File ─────────────────────────────────────

def restore_from_backup() -> None:
    """Restore device state, apps, or data from an existing .ab backup archive."""
    if not ensure_device():
        return

    # Scan available .ab files
    ensure_backup_dir()
    ab_files: List[str] = []
    for root, _, files in os.walk(BACKUP_DIR):
        for f in files:
            if f.endswith(".ab"):
                ab_files.append(os.path.join(root, f))

    # Also check current directory
    for f in os.listdir("."):
        if f.endswith(".ab") and os.path.isfile(f):
            ab_files.append(f)

    # Deduplicate and sort
    ab_files = sorted(list(set(ab_files)))

    selected_file: Optional[str] = None

    if ab_files:
        ui.header("Available Backup Archives (.ab):")
        print()
        headers = ("#", "Filename", "Size", "Modified Date")
        rows = []
        for i, path in enumerate(ab_files, 1):
            sz = format_file_size(os.path.getsize(path))
            mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")
            rows.append((f"{i}", os.path.basename(path), sz, mtime))
        ui.print_table(rows, headers)
        print()

        choice = ui.get_choice("Select backup file number or enter custom file path")
        if choice.isdigit() and 1 <= int(choice) <= len(ab_files):
            selected_file = ab_files[int(choice) - 1]
        elif choice:
            selected_file = choice.strip()
    else:
        selected_file = ui.get_choice("Enter full path to .ab backup file to restore")

    if not selected_file or not os.path.isfile(selected_file):
        ui.error(f"Backup file not found: {selected_file}")
        return

    # Inspect backup header before starting
    header = parse_ab_header(selected_file)
    if header.get("Valid Android Backup") == "No (Invalid Magic)":
        ui.warning("File does not appear to have a valid 'ANDROID BACKUP' magic header!")
        if not ui.confirm("Do you still wish to attempt restore?"):
            return

    print(f"""
  {ui.Colors.BOLD}{ui.Colors.YELLOW}══════════════════════════════════════════════════════════════════{ui.Colors.RESET}
  {ui.Colors.BOLD}📱 ACTION REQUIRED ON DEVICE SCREEN:{ui.Colors.RESET}
    1. Unlock your device.
    2. A full restore prompt will appear.
    3. If this backup was encrypted, enter the encryption password.
    4. Tap {ui.Colors.GREEN}'Restore my data'{ui.Colors.RESET} to begin restoration.
    5. Keep device connected until completed.
  {ui.Colors.BOLD}{ui.Colors.YELLOW}══════════════════════════════════════════════════════════════════{ui.Colors.RESET}
    """)

    ui.info(f"Restoring from '{os.path.abspath(selected_file)}'...")
    start_time = time.time()
    ok, _ = adb.run(["restore", selected_file], timeout=3600, capture=False)
    duration = time.time() - start_time

    if ok:
        ui.success(f"Restore operation finished in {duration:.1f}s!")
        ui.info("Check device screen for any app-specific restore completion notices.")
    else:
        ui.error("Restore operation encountered an error or was aborted.")


# ─── Feature 6: Backup Contacts ──────────────────────────────────────────────

def backup_contacts() -> None:
    """Dump contacts from device content provider into vCard (.vcf) and CSV formats."""
    if not ensure_device():
        return

    ui.info("Querying Android Contacts Content Provider...")
    ensure_backup_dir()

    # Query phones provider
    ok, out = adb.run_shell("content query --uri content://contacts/phones/ 2>/dev/null", timeout=15)
    if not ok or not out.strip() or "No result found" in out or "SecurityException" in out:
        # Try alternate URI
        ok, out = adb.run_shell("content query --uri content://com.android.contacts/data/phones 2>/dev/null", timeout=15)

    if not ok or not out.strip() or "SecurityException" in out or "Permission Denial" in out:
        ui.error("Failed to query contacts via ADB content provider.")
        print(f"""
  {ui.Colors.YELLOW}ℹ Explanation:{ui.Colors.RESET}
    On modern Android versions (Android 10+), direct shell access to Contacts Provider
    is protected by the READ_CONTACTS runtime permission.
    Alternative: If the device is rooted or has contacts sync enabled, you can export
    contacts from the device Contacts App -> Settings -> Export to .vcf.
        """)
        return

    # Parse content query rows
    # Format of content query:
    # Row: 0 _id=1, display_name=John Doe, number=+1234567890, type=2, ...
    contacts_list: List[Dict[str, str]] = []
    lines = out.splitlines()

    for line in lines:
        if not line.startswith("Row:"):
            continue
        # Extract fields
        record: Dict[str, str] = {}
        # Remove "Row: N "
        content_part = re.sub(r"^Row:\s*\d+\s*", "", line)
        tokens = content_part.split(", ")
        for token in tokens:
            if "=" in token:
                k, v = token.split("=", 1)
                record[k.strip()] = v.strip()

        name = record.get("display_name") or record.get("name") or record.get("data1") or "Unknown"
        number = record.get("number") or record.get("data1") or record.get("data4") or ""
        contact_type = record.get("type", "1")

        if number:
            contacts_list.append({
                "name": name,
                "number": number,
                "type": contact_type,
            })

    if not contacts_list:
        ui.warning("No contacts found in content provider dump.")
        return

    # Save to VCF (vCard 3.0) and CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    serial_tag = adb.serial.replace(":", "_") if adb.serial else "device"
    vcf_path = os.path.join(BACKUP_DIR, f"contacts_{serial_tag}_{timestamp}.vcf")
    csv_path = os.path.join(BACKUP_DIR, f"contacts_{serial_tag}_{timestamp}.csv")

    try:
        # Write VCF
        with open(vcf_path, "w", encoding="utf-8") as f:
            for c in contacts_list:
                f.write("BEGIN:VCARD\n")
                f.write("VERSION:3.0\n")
                f.write(f"FN:{c['name']}\n")
                f.write(f"TEL;TYPE=CELL:{c['number']}\n")
                f.write("END:VCARD\n")

        # Write CSV
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["name", "number", "type"])
            writer.writeheader()
            writer.writerows(contacts_list)

        ui.success(f"Successfully extracted {len(contacts_list)} contacts!")
        ui.print_kv({
            "Total Contacts": str(len(contacts_list)),
            "vCard (VCF)": os.path.abspath(vcf_path),
            "CSV Spreadsheet": os.path.abspath(csv_path),
        })

        # Preview table
        print()
        ui.header("Contacts Preview (First 15 entries):")
        headers = ("#", "Name", "Phone Number")
        rows = [(f"{i}", c["name"], c["number"]) for i, c in enumerate(contacts_list[:15], 1)]
        ui.print_table(rows, headers)

    except OSError as e:
        ui.error(f"Failed to write contacts file: {e}")


# ─── Feature 7: List Available Backups ────────────────────────────────────────

def list_available_backups() -> None:
    """Catalog and inspect all backup archives, exports, and dumps in the workspace."""
    ensure_backup_dir()
    backup_entries: List[Tuple[str, str, str, str]] = []

    search_dirs = [BACKUP_DIR, "."]
    seen_files = set()

    for directory in search_dirs:
        if not os.path.isdir(directory):
            continue
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if not os.path.isfile(filepath):
                continue
            abs_path = os.path.abspath(filepath)
            if abs_path in seen_files:
                continue

            # Identify backup file types
            ext = os.path.splitext(filename)[1].lower()
            if ext in (".ab", ".vcf", ".csv", ".json", ".tar", ".gz") or filename.startswith("backup_"):
                seen_files.add(abs_path)
                sz = format_file_size(os.path.getsize(filepath))
                mtime = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%Y-%m-%d %H:%M")

                type_desc = "Unknown"
                if ext == ".ab":
                    type_desc = "Android Backup Archive"
                elif ext == ".vcf":
                    type_desc = "vCard Contacts"
                elif ext == ".csv":
                    type_desc = "CSV Export (Data/SMS)"
                elif ext == ".json":
                    type_desc = "Package Manifest / JSON"
                elif ext in (".tar", ".gz"):
                    type_desc = "Tar / Media Archive"

                backup_entries.append((filename, sz, mtime, type_desc))

    if not backup_entries:
        ui.info(f"No backup files found in './{BACKUP_DIR}' or current directory.")
        return

    ui.header(f"Catalog of Available Backups ({len(backup_entries)} files):")
    print()
    headers = ("File Name", "Size", "Modified Date", "Backup Type")
    ui.print_table(backup_entries, headers)
    print()

    # Offer to inspect an .ab file
    if any(e[0].endswith(".ab") for e in backup_entries):
        if ui.confirm("Would you like to inspect header details of an .ab backup file?"):
            inspect_ab_file()


# ─── Feature 8: Backup Encryption Guide & Notes ──────────────────────────────

def backup_encryption_guide() -> None:
    """Display in-depth guide on Android desktop backup password and encryption mechanisms."""
    ui.header("🔒 Android Backup Encryption & Security Guide")
    print(f"""
  {ui.Colors.CYAN}{ui.Colors.BOLD}1. Desktop Backup Password:{ui.Colors.RESET}
     • You can configure a desktop backup password on your Android device under:
       {ui.Colors.YELLOW}Settings ➔ System ➔ Developer Options ➔ Desktop backup password{ui.Colors.RESET}
     • When set, ADB backup commands will enforce encryption using your secret password.
     • Encrypted backups use {ui.Colors.GREEN}AES-256-CBC{ui.Colors.RESET} encryption with {ui.Colors.GREEN}PBKDF2{ui.Colors.RESET} key derivation.

  {ui.Colors.CYAN}{ui.Colors.BOLD}2. Why Use Password Encryption:{ui.Colors.RESET}
     • Without a desktop backup password, backups are stored in plaintext (compressed tar).
     • Some application developers restrict unencrypted backups; setting a password allows
       backing up apps that forbid plaintext extraction.

  {ui.Colors.CYAN}{ui.Colors.BOLD}3. Android 12+ (API 31+) Backup Restrictions:{ui.Colors.RESET}
     • In Android 12 and newer, Google introduced `android:dataExtractionRules`.
     • Apps configured with `allowBackup="false"` or cloud-only extraction cannot be
       dumped via `adb backup` on standard production builds unless the app is debuggable.

  {ui.Colors.CYAN}{ui.Colors.BOLD}4. Extracting / Unpacking .ab Archives:{ui.Colors.RESET}
     • {ui.Colors.BOLD}Unencrypted .ab files:{ui.Colors.RESET}
       The file consists of a 24-byte header followed by standard deflated (zlib) tar.
       Extraction command (Linux/macOS):
       `dd if=backup.ab bs=24 skip=1 | zlib-flate -uncompress | tar -xvf -`

     • {ui.Colors.BOLD}Encrypted .ab files:{ui.Colors.RESET}
       Use Android Backup Extractor (ABE):
       `java -jar abe.jar unpack backup.ab backup.tar <password>`

  {ui.Colors.CYAN}{ui.Colors.BOLD}5. Best Practices:{ui.Colors.RESET}
     • Always verify the generated `.ab` file size is non-zero after backing up.
     • Store backup archives in secure, encrypted storage.
    """)


# ─── Feature 9: Backup SMS & Call Logs ───────────────────────────────────────

def backup_sms_and_call_logs() -> None:
    """Dump SMS messages and Call history from Android content providers."""
    if not ensure_device():
        return

    ui.info("Querying SMS messages and Call Log content providers...")
    ensure_backup_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    serial_tag = adb.serial.replace(":", "_") if adb.serial else "device"

    # 1. SMS Query
    ok_sms, sms_out = adb.run_shell("content query --uri content://sms 2>/dev/null", timeout=20)
    sms_count = 0
    sms_path = os.path.join(BACKUP_DIR, f"sms_{serial_tag}_{timestamp}.csv")

    if ok_sms and sms_out.strip() and "SecurityException" not in sms_out:
        sms_rows = []
        for line in sms_out.splitlines():
            if not line.startswith("Row:"):
                continue
            content = re.sub(r"^Row:\s*\d+\s*", "", line)
            record: Dict[str, str] = {}
            for item in content.split(", "):
                if "=" in item:
                    k, v = item.split("=", 1)
                    record[k.strip()] = v.strip()
            sms_rows.append({
                "address": record.get("address", ""),
                "body": record.get("body", ""),
                "date": record.get("date", ""),
                "type": record.get("type", ""),
                "read": record.get("read", ""),
            })

        if sms_rows:
            sms_count = len(sms_rows)
            with open(sms_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["address", "body", "date", "type", "read"])
                writer.writeheader()
                writer.writerows(sms_rows)

    # 2. Call Logs Query
    ok_calls, call_out = adb.run_shell("content query --uri content://call_log/calls 2>/dev/null", timeout=20)
    call_count = 0
    call_path = os.path.join(BACKUP_DIR, f"calls_{serial_tag}_{timestamp}.csv")

    if ok_calls and call_out.strip() and "SecurityException" not in call_out:
        call_rows = []
        for line in call_out.splitlines():
            if not line.startswith("Row:"):
                continue
            content = re.sub(r"^Row:\s*\d+\s*", "", line)
            record = {}
            for item in content.split(", "):
                if "=" in item:
                    k, v = item.split("=", 1)
                    record[k.strip()] = v.strip()
            call_rows.append({
                "number": record.get("number", ""),
                "name": record.get("name", ""),
                "duration": record.get("duration", ""),
                "type": record.get("type", ""),
                "date": record.get("date", ""),
            })

        if call_rows:
            call_count = len(call_rows)
            with open(call_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["number", "name", "duration", "type", "date"])
                writer.writeheader()
                writer.writerows(call_rows)

    if sms_count > 0 or call_count > 0:
        ui.success(f"Extracted {sms_count} SMS message(s) and {call_count} Call log entry(ies)!")
        info_dict = {}
        if sms_count > 0:
            info_dict["SMS CSV File"] = os.path.abspath(sms_path)
            info_dict["Total SMS"] = str(sms_count)
        if call_count > 0:
            info_dict["Call Log CSV File"] = os.path.abspath(call_path)
            info_dict["Total Calls"] = str(call_count)
        ui.print_kv(info_dict)
    else:
        ui.warning("SMS / Call Log queries returned no entries or were blocked by Android runtime permissions.")


# ─── Feature 10: Export Installed Packages Manifest ──────────────────────────

def export_package_manifest() -> None:
    """Export a complete JSON & TXT manifest of all installed apps, version codes, and paths."""
    if not ensure_device():
        return

    ui.info("Generating installed package inventory...")
    ensure_backup_dir()

    ok, output = adb.run(["shell", "pm", "list", "packages", "-f", "-u"])
    if not ok:
        ui.error("Failed to query package manager.")
        return

    package_list: List[Dict[str, str]] = []
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("package:"):
            continue
        raw = line.replace("package:", "")
        if "=" in raw:
            apk_path, pkg_name = raw.rsplit("=", 1)
            is_system = apk_path.startswith("/system") or apk_path.startswith("/product") or apk_path.startswith("/apex")
            package_list.append({
                "package": pkg_name,
                "apk_path": apk_path,
                "type": "system" if is_system else "third_party",
            })

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    serial_tag = adb.serial.replace(":", "_") if adb.serial else "device"
    json_path = os.path.join(BACKUP_DIR, f"packages_manifest_{serial_tag}_{timestamp}.json")
    txt_path = os.path.join(BACKUP_DIR, f"packages_list_{serial_tag}_{timestamp}.txt")

    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({
                "device_serial": adb.serial,
                "timestamp": timestamp,
                "total_packages": len(package_list),
                "packages": package_list,
            }, f, indent=2)

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"# DroidCommander Package Manifest - {datetime.now()}\n")
            f.write(f"# Total: {len(package_list)} packages\n\n")
            for p in package_list:
                f.write(f"{p['package']} [{p['type']}] -> {p['apk_path']}\n")

        ui.success(f"Exported manifest for {len(package_list)} installed packages!")
        ui.print_kv({
            "JSON Manifest": os.path.abspath(json_path),
            "Text List": os.path.abspath(txt_path),
            "Total Packages": str(len(package_list)),
        })
    except OSError as e:
        ui.error(f"Failed to write package manifest: {e}")


# ─── Feature 11: Inspect & Analyze .ab Backup File ───────────────────────────

def inspect_ab_file() -> None:
    """Inspect and decode the header metadata of an Android Backup (.ab) file."""
    ensure_backup_dir()

    # Find .ab files
    ab_files = [
        os.path.join(BACKUP_DIR, f)
        for f in os.listdir(BACKUP_DIR)
        if f.endswith(".ab") and os.path.isfile(os.path.join(BACKUP_DIR, f))
    ]
    for f in os.listdir("."):
        if f.endswith(".ab") and os.path.isfile(f):
            ab_files.append(f)
    ab_files = sorted(list(set(ab_files)))

    selected_file = ""
    if ab_files:
        ui.header("Select .ab File to Inspect:")
        for i, f in enumerate(ab_files, 1):
            print(f"    {ui.Colors.YELLOW}[{i}]{ui.Colors.RESET} {f}")
        choice = ui.get_choice("Enter file number or path")
        if choice.isdigit() and 1 <= int(choice) <= len(ab_files):
            selected_file = ab_files[int(choice) - 1]
        elif choice:
            selected_file = choice
    else:
        selected_file = ui.get_choice("Enter path to .ab file")

    if not selected_file or not os.path.isfile(selected_file):
        ui.error("File not found.")
        return

    ui.info(f"Parsing header for: {selected_file}...")
    header_data = parse_ab_header(selected_file)

    ui.header("Android Backup Header Breakdown:")
    print()
    ui.print_kv(header_data)
    print()


# ─── Main Menu Loop ──────────────────────────────────────────────────────────

def backup_restore_menu() -> None:
    """Main Backup & Restore submenu."""
    while True:
        ui.clear()
        ui.print_banner()
        ui.print_device_status(adb.serial, adb.getprop("ro.product.model") if adb.serial else "")
        ui.print_menu("💾 Backup & Restore Manager", [
            "Full device backup (apps + data + storage)",
            "Backup specific app",
            "Backup without APKs (data only)",
            "Backup shared storage (media/files)",
            "Restore from backup file (.ab)",
            "Backup contacts (vCard & CSV export)",
            "List available backups in directory",
            "Backup encryption note & security guide",
            "Backup SMS & Call logs (content dump)",
            "Export installed packages manifest",
            "Inspect & analyze .ab backup file",
        ], columns=2)

        choice = ui.get_choice()

        if choice == "0":
            break
        elif choice == "1":
            full_device_backup()
        elif choice == "2":
            backup_specific_app()
        elif choice == "3":
            backup_data_only()
        elif choice == "4":
            backup_shared_storage()
        elif choice == "5":
            restore_from_backup()
        elif choice == "6":
            backup_contacts()
        elif choice == "7":
            list_available_backups()
        elif choice == "8":
            backup_encryption_guide()
        elif choice == "9":
            backup_sms_and_call_logs()
        elif choice == "10":
            export_package_manifest()
        elif choice == "11":
            inspect_ab_file()
        else:
            ui.error("Invalid option. Try again.")

        ui.pause()
