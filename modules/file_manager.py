"""
modules/file_manager.py — File Management Module for DroidCommander.

Provides a comprehensive suite of file and directory operations between the
host PC and connected Android device via ADB:
- Push / pull individual files and full directory trees
- Directory listing (ls -la) with formatted tabular inspection
- Deep file search (find) with filters
- Disk usage and storage partition analysis (df / du)
- Directory creation (mkdir -p), file deletion (rm -rf), and moving/renaming (mv)
- File content viewer (cat, head, tail, grep)
- File metadata and SELinux permission inspector (stat / ls -ldZ)
- Permission modification (chmod) with common presets and recursive support
- Cryptographic hash verification (md5sum, sha256sum)
"""

import os
import time
from datetime import datetime
from typing import Optional, List, Tuple, Dict

from core.adb import adb
from core import ui
from core.device import ensure_device


# ─── Helper Utilities ────────────────────────────────────────────────────────

def _clean_path(path: str) -> str:
    """
    Sanitize and normalize user input path.

    Strips quotes, trailing/leading whitespace, and normalizes separators.
    """
    if not path:
        return ""
    cleaned = path.strip().strip("'\"").strip()
    return os.path.expanduser(cleaned)


def _clean_remote_path(path: str) -> str:
    """
    Sanitize remote Android path.

    Ensures forward slashes and removes surrounding quotes.
    """
    if not path:
        return ""
    cleaned = path.strip().strip("'\"").strip()
    return cleaned.replace("\\", "/")


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


def _count_local_files(directory: str) -> Tuple[int, int]:
    """
    Count files and compute total size in bytes for a local directory.

    Returns
    -------
    Tuple[int, int]
        (file_count, total_bytes)
    """
    total_files = 0
    total_bytes = 0
    for root, _, files in os.walk(directory):
        for f in files:
            total_files += 1
            fp = os.path.join(root, f)
            try:
                total_bytes += os.path.getsize(fp)
            except OSError:
                pass
    return total_files, total_bytes


def _is_critical_path(remote_path: str) -> bool:
    """Check if the given remote path is a system-critical root location."""
    normalized = remote_path.rstrip("/")
    critical_roots = [
        "",
        "/",
        "/system",
        "/vendor",
        "/product",
        "/system_ext",
        "/data",
        "/boot",
        "/etc",
        "/sdcard",
        "/storage",
        "/storage/emulated",
        "/storage/emulated/0",
    ]
    return normalized in critical_roots


# ─── Feature 1: Push File to Device ──────────────────────────────────────────

def push_file():
    """Push a single file from the host PC to the connected device."""
    if not ensure_device():
        return

    ui.header("Push File to Device")
    local_path = _clean_path(ui.get_choice("Enter local file path (or drag & drop file)"))
    if not local_path:
        ui.warning("Operation cancelled: No file path provided.")
        return

    if not os.path.isfile(local_path):
        ui.error(f"Local file does not exist or is not a file: {local_path}")
        return

    file_size = os.path.getsize(local_path)
    file_name = os.path.basename(local_path)

    remote_dest = _clean_remote_path(ui.get_choice("Enter device destination folder or path (default: /sdcard/Download/)"))
    if not remote_dest:
        remote_dest = "/sdcard/Download/"

    # If destination is a directory, append the filename
    if remote_dest.endswith("/"):
        remote_dest = remote_dest + file_name

    ui.info(f"Source:      {local_path} ({_human_size(file_size)})")
    ui.info(f"Destination: {remote_dest}")
    ui.info("Pushing file to device...")

    start_time = time.time()
    ok, output = adb.run(["push", local_path, remote_dest], timeout=600)
    elapsed = time.time() - start_time

    if ok:
        ui.success(f"File pushed successfully in {elapsed:.2f}s!")
        if output:
            ui.info(f"Details: {output}")
    else:
        ui.error(f"Push failed: {output}")


# ─── Feature 2: Pull File from Device ────────────────────────────────────────

def pull_file():
    """Pull a single file from the connected device to the host PC."""
    if not ensure_device():
        return

    ui.header("Pull File from Device")
    remote_path = _clean_remote_path(ui.get_choice("Enter device file path (e.g. /sdcard/Download/sample.pdf)"))
    if not remote_path:
        ui.warning("Operation cancelled: No remote path provided.")
        return

    # Check if remote file exists
    ok_check, _ = adb.run(["shell", "ls", remote_path])
    if not ok_check:
        ui.warning(f"Remote file '{remote_path}' may not exist or cannot be accessed.")

    default_dest = os.path.join(os.getcwd(), "downloads")
    local_dest = _clean_path(ui.get_choice(f"Enter local destination folder or path (default: {default_dest})"))
    if not local_dest:
        local_dest = default_dest

    # If destination folder does not exist, create it
    if not os.path.splitext(local_dest)[1]:
        os.makedirs(local_dest, exist_ok=True)
    else:
        os.makedirs(os.path.dirname(os.path.abspath(local_dest)), exist_ok=True)

    ui.info(f"Source:      {remote_path}")
    ui.info(f"Destination: {local_dest}")
    ui.info("Pulling file from device...")

    start_time = time.time()
    ok, output = adb.run(["pull", remote_path, local_dest], timeout=600)
    elapsed = time.time() - start_time

    if ok:
        ui.success(f"File pulled successfully in {elapsed:.2f}s!")
        if output:
            ui.info(f"Details: {output}")
    else:
        ui.error(f"Pull failed: {output}")


# ─── Feature 3: Push Entire Folder ───────────────────────────────────────────

def push_folder():
    """Push an entire folder recursively from the host PC to the device."""
    if not ensure_device():
        return

    ui.header("Push Folder to Device (Recursive)")
    local_folder = _clean_path(ui.get_choice("Enter local directory path to push"))
    if not local_folder:
        ui.warning("Operation cancelled: No folder path provided.")
        return

    if not os.path.isdir(local_folder):
        ui.error(f"Local folder does not exist: {local_folder}")
        return

    file_count, total_size = _count_local_files(local_folder)
    folder_name = os.path.basename(os.path.normpath(local_folder))

    ui.info(f"Folder: {folder_name} | Files: {file_count} | Total Size: {_human_size(total_size)}")

    remote_dest = _clean_remote_path(ui.get_choice("Enter device destination directory (default: /sdcard/)"))
    if not remote_dest:
        remote_dest = "/sdcard/"

    if not ui.confirm(f"Push folder '{folder_name}' ({file_count} files, {_human_size(total_size)}) to '{remote_dest}'?"):
        ui.info("Push cancelled.")
        return

    ui.info("Transferring folder... This may take some time.")
    start_time = time.time()
    ok, output = adb.run(["push", local_folder, remote_dest], timeout=1800)
    elapsed = time.time() - start_time

    if ok:
        ui.success(f"Folder pushed successfully in {elapsed:.2f}s!")
        if output:
            lines = output.splitlines()
            for line in lines[-5:]:
                ui.info(line)
    else:
        ui.error(f"Folder push failed: {output}")


# ─── Feature 4: Pull Entire Folder ───────────────────────────────────────────

def pull_folder():
    """Pull an entire folder recursively from the device to the host PC."""
    if not ensure_device():
        return

    ui.header("Pull Folder from Device (Recursive)")
    remote_folder = _clean_remote_path(ui.get_choice("Enter remote directory path on device (e.g. /sdcard/DCIM/Camera)"))
    if not remote_folder:
        ui.warning("Operation cancelled: No remote folder provided.")
        return

    default_dest = os.path.join(os.getcwd(), "pulled_data")
    local_dest = _clean_path(ui.get_choice(f"Enter local destination directory (default: {default_dest})"))
    if not local_dest:
        local_dest = default_dest

    os.makedirs(local_dest, exist_ok=True)

    ui.info(f"Remote folder: {remote_folder}")
    ui.info(f"Local destination: {local_dest}")
    ui.info("Pulling folder contents... Please wait.")

    start_time = time.time()
    ok, output = adb.run(["pull", remote_folder, local_dest], timeout=1800)
    elapsed = time.time() - start_time

    if ok:
        ui.success(f"Folder pulled successfully in {elapsed:.2f}s!")
        if output:
            lines = output.splitlines()
            for line in lines[-5:]:
                ui.info(line)
    else:
        ui.error(f"Folder pull failed: {output}")


# ─── Feature 5: List Files in Directory (ls -la) ─────────────────────────────

def list_directory():
    """List files in a specified directory with permissions, sizes, and timestamps."""
    if not ensure_device():
        return

    ui.header("Directory Browser (ls -la)")
    print(f"""
  {ui.Colors.CYAN}Common Presets:{ui.Colors.RESET}
    [1] /sdcard/                 (Primary Internal Storage)
    [2] /sdcard/Download/        (Downloads Folder)
    [3] /sdcard/DCIM/Camera/     (Camera Photos & Videos)
    [4] /sdcard/Pictures/        (Images & Screenshots)
    [5] /sdcard/Documents/       (Documents)
    [6] /data/local/tmp/         (App Staging / Scratch Area)
    [7] /storage/emulated/0/     (Emulated Storage Root)
    [8] /system/app/             (System Installed Apps)
    [9] Custom directory path
    """)

    preset = ui.get_choice("Select preset or enter custom path")
    target_path = "/sdcard/"

    if preset == "1":
        target_path = "/sdcard/"
    elif preset == "2":
        target_path = "/sdcard/Download/"
    elif preset == "3":
        target_path = "/sdcard/DCIM/Camera/"
    elif preset == "4":
        target_path = "/sdcard/Pictures/"
    elif preset == "5":
        target_path = "/sdcard/Documents/"
    elif preset == "6":
        target_path = "/data/local/tmp/"
    elif preset == "7":
        target_path = "/storage/emulated/0/"
    elif preset == "8":
        target_path = "/system/app/"
    elif preset == "9" or preset.startswith("/"):
        if preset == "9":
            custom = _clean_remote_path(ui.get_choice("Enter remote directory path"))
            target_path = custom if custom else "/sdcard/"
        else:
            target_path = _clean_remote_path(preset)
    else:
        target_path = _clean_remote_path(preset) if preset else "/sdcard/"

    ui.info(f"Listing contents of: {target_path}")
    ok, output = adb.run(["shell", "ls", "-la", target_path], timeout=20)
    if not ok:
        ui.error(f"Failed to list directory: {output}")
        return

    lines = output.splitlines()
    if not lines:
        ui.info("Directory is empty.")
        return

    table_rows = []
    dir_count = 0
    file_count = 0

    print(f"\n  {ui.Colors.BOLD}Contents of {target_path} ({len(lines)} entries):{ui.Colors.RESET}\n")

    for line in lines:
        parts = line.split(maxsplit=7)
        if len(parts) >= 8:
            perms = parts[0]
            owner = parts[2]
            group = parts[3]
            size = parts[4]
            date_time = f"{parts[5]} {parts[6]}"
            name = parts[7]

            if perms.startswith("d"):
                dir_count += 1
                name_display = f"{ui.Colors.CYAN}📁 {name}/{ui.Colors.RESET}"
            elif perms.startswith("l"):
                name_display = f"{ui.Colors.MAGENTA}🔗 {name}{ui.Colors.RESET}"
            elif "x" in perms:
                file_count += 1
                name_display = f"{ui.Colors.GREEN}⚡ {name}{ui.Colors.RESET}"
            else:
                file_count += 1
                name_display = f"📄 {name}"

            table_rows.append((perms, owner, group, size, date_time, name_display))
        else:
            # Fallback for non-standard line formats
            print(f"  {line}")

    if table_rows:
        headers = ("Permissions", "Owner", "Group", "Size", "Date Time", "Name")
        ui.print_table(table_rows, headers=headers)
        ui.info(f"Summary: {dir_count} directories, {file_count} files.")


# ─── Feature 6: Search Files by Name (find) ──────────────────────────────────

def search_files():
    """Search for files and directories on the device matching a pattern."""
    if not ensure_device():
        return

    ui.header("Search Files by Name (find)")
    search_root = _clean_remote_path(ui.get_choice("Enter search root directory (default: /sdcard/)"))
    if not search_root:
        search_root = "/sdcard/"

    pattern = ui.get_choice("Enter search pattern/keyword (e.g. *.pdf, *log*, backup)")
    if not pattern:
        ui.warning("Operation cancelled: No search pattern provided.")
        return

    print(f"""
  {ui.Colors.CYAN}Filter by File Type:{ui.Colors.RESET}
    [1] All Types (files, directories, links)
    [2] Regular Files Only (-type f)
    [3] Directories Only (-type d)
    """)
    type_choice = ui.get_choice("Select file type filter (default 1)")
    type_arg = []
    if type_choice == "2":
        type_arg = ["-type", "f"]
    elif type_choice == "3":
        type_arg = ["-type", "d"]

    depth_choice = ui.get_choice("Enter max search depth (press Enter for unlimited)")
    depth_arg = []
    if depth_choice.isdigit() and int(depth_choice) > 0:
        depth_arg = ["-maxdepth", depth_choice]

    # Handle wildcards cleanly
    search_pattern = pattern if ("*" in pattern or "?" in pattern) else f"*{pattern}*"
    find_cmd = ["shell", "find", search_root] + depth_arg + type_arg + ["-iname", f"'{search_pattern}'"]

    ui.info(f"Searching in '{search_root}' for '{search_pattern}'... (may take a moment)")

    ok, output = adb.run(find_cmd, timeout=60)
    if not ok and not output:
        # Fallback if quotes or flags are not supported by toybox find
        fallback_cmd = ["shell", f"find {search_root} -iname '*{pattern}*' 2>/dev/null"]
        ok, output = adb.run(fallback_cmd, timeout=60)

    if not output.strip():
        ui.info(f"No files matching '{search_pattern}' found in {search_root}.")
        return

    results = [l.strip() for l in output.splitlines() if l.strip() and not "Permission denied" in l]
    if not results:
        ui.info(f"No matching files found (or access was restricted).")
        return

    print(f"\n  {ui.Colors.BOLD}Search Results ({len(results)} matches):{ui.Colors.RESET}\n")
    for i, path in enumerate(results[:50], 1):
        if path.endswith("/") or "/" in path:
            print(f"  {ui.Colors.YELLOW}[{i:>2}]{ui.Colors.RESET} {path}")
        else:
            print(f"  {ui.Colors.YELLOW}[{i:>2}]{ui.Colors.RESET} {path}")

    if len(results) > 50:
        ui.info(f"Showing first 50 of {len(results)} results.")


# ─── Feature 7: Disk Usage Analysis (du / df) ────────────────────────────────

def disk_usage_analysis():
    """Analyze disk partitions and folder sizes on the device."""
    if not ensure_device():
        return

    ui.header("Disk & Storage Usage Analysis")
    print(f"""
  {ui.Colors.CYAN}Analysis Modes:{ui.Colors.RESET}
    [1] Partition Filesystem Overview (df -h)
    [2] Primary Storage Breakdown (du -h /sdcard/ folders)
    [3] Custom Directory Disk Usage (du -d 1 -h <path>)
    [4] Scan for Large Files (> 50MB on /sdcard/)
    """)

    choice = ui.get_choice("Select analysis option (default 1)")

    if choice in ("1", ""):
        ui.info("Querying partition storage (df -h)...")
        ok, output = adb.run(["shell", "df", "-h"], timeout=15)
        if not ok:
            ui.error(f"Failed to query df: {output}")
            return

        lines = output.splitlines()
        rows = []
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 6:
                fs = parts[0]
                size = parts[1]
                used = parts[2]
                avail = parts[3]
                use_pct = parts[4]
                mounted = parts[5]
                rows.append((fs, size, used, avail, use_pct, mounted))
            elif len(parts) == 5:
                rows.append((parts[0], parts[1], parts[2], parts[3], parts[4], "—"))

        if rows:
            headers = ("Filesystem", "Size", "Used", "Avail", "Use%", "Mounted On")
            ui.print_table(rows, headers=headers)
        else:
            print(f"\n{output}")

    elif choice == "2":
        ui.info("Analyzing /sdcard/ top-level directories (this may take 10-30s)...")
        ok, output = adb.run(["shell", "du", "-d", "1", "-h", "/sdcard/"], timeout=45)
        if not ok:
            # Fallback for older Android toys
            ok, output = adb.run(["shell", "du", "-sh", "/sdcard/*"], timeout=45)

        if ok and output.strip():
            print(f"\n  {ui.Colors.BOLD}Directory Sizes in /sdcard/:{ui.Colors.RESET}\n")
            rows = []
            for line in output.splitlines():
                parts = line.strip().split(maxsplit=1)
                if len(parts) == 2:
                    rows.append((parts[0], parts[1]))
            if rows:
                ui.print_table(rows, headers=("Size", "Directory Path"))
            else:
                print(output)
        else:
            ui.error(f"Failed to calculate folder sizes: {output}")

    elif choice == "3":
        custom_path = _clean_remote_path(ui.get_choice("Enter directory path to analyze (e.g. /data/local/tmp)"))
        if not custom_path:
            return
        ui.info(f"Analyzing disk usage for '{custom_path}'...")
        ok, output = adb.run(["shell", "du", "-d", "1", "-h", custom_path], timeout=45)
        if ok and output.strip():
            rows = []
            for line in output.splitlines():
                parts = line.strip().split(maxsplit=1)
                if len(parts) == 2:
                    rows.append((parts[0], parts[1]))
            ui.print_table(rows, headers=("Size", "Directory Path"))
        else:
            ui.error(f"Failed: {output}")

    elif choice == "4":
        ui.info("Scanning /sdcard/ for files larger than 50MB...")
        ok, output = adb.run(["shell", "find /sdcard/ -type f -size +50000k -exec ls -lh {} + 2>/dev/null"], timeout=60)
        if ok and output.strip():
            print(f"\n  {ui.Colors.BOLD}Large Files Found (>50MB):{ui.Colors.RESET}\n")
            for line in output.splitlines()[:30]:
                print(f"  {line}")
        else:
            ui.info("No files larger than 50MB found on /sdcard/.")


# ─── Feature 8: Create Directory on Device ───────────────────────────────────

def create_directory():
    """Create a new directory on the device (mkdir -p)."""
    if not ensure_device():
        return

    ui.header("Create Directory on Device")
    dir_path = _clean_remote_path(ui.get_choice("Enter full directory path to create (e.g. /sdcard/TestFolder)"))
    if not dir_path:
        ui.warning("Operation cancelled: No path provided.")
        return

    ui.info(f"Creating directory: {dir_path}")
    ok, output = adb.run(["shell", "mkdir", "-p", dir_path])
    if ok:
        # Verify creation
        ok_chk, chk_out = adb.run(["shell", "ls", "-ld", dir_path])
        if ok_chk:
            ui.success(f"Directory created successfully: {dir_path}")
            ui.info(f"Attributes: {chk_out}")
        else:
            ui.success(f"Directory created: {dir_path}")
    else:
        ui.error(f"Failed to create directory: {output}")


# ─── Feature 9: Delete File or Folder on Device ──────────────────────────────

def delete_file_or_folder():
    """Delete a file or directory on the connected device with safety checks."""
    if not ensure_device():
        return

    ui.header("Delete File or Folder on Device")
    target_path = _clean_remote_path(ui.get_choice("Enter remote path to delete (e.g. /sdcard/Download/old.zip)"))
    if not target_path:
        ui.warning("Operation cancelled: No path provided.")
        return

    # Safety Guard
    if _is_critical_path(target_path):
        ui.error(f"CRITICAL SAFETY ABORT: Refusing to delete system-critical path: '{target_path}'")
        return

    # Inspect target type
    ok_type, type_out = adb.run(["shell", "ls", "-ld", target_path])
    if not ok_type or "No such file" in type_out:
        ui.error(f"Target path does not exist: {target_path}")
        return

    is_directory = type_out.startswith("d")
    item_type = "directory (and all its contents)" if is_directory else "file"

    ui.warning(f"Target: {target_path}")
    ui.warning(f"Type:   {item_type}")
    ui.warning("This action cannot be undone!")

    if not ui.confirm(f"Are you absolutely sure you want to PERMANENTLY DELETE '{target_path}'?"):
        ui.info("Deletion cancelled.")
        return

    cmd = ["shell", "rm", "-rf" if is_directory else "-f", target_path]
    ok, output = adb.run(cmd, timeout=30)

    if ok:
        # Verify removal
        ok_verify, _ = adb.run(["shell", "ls", "-ld", target_path])
        if not ok_verify:
            ui.success(f"Successfully deleted {item_type}: {target_path}")
        else:
            ui.warning(f"Deletion command ran, but item still exists (may require root or write permissions).")
    else:
        ui.error(f"Delete failed: {output}")


# ─── Feature 10: Move / Rename File on Device ────────────────────────────────

def move_rename_file():
    """Move or rename a file or directory on the device (mv)."""
    if not ensure_device():
        return

    ui.header("Move or Rename File / Folder")
    src_path = _clean_remote_path(ui.get_choice("Enter source path on device (e.g. /sdcard/Download/test.txt)"))
    if not src_path:
        ui.warning("Operation cancelled: No source path provided.")
        return

    # Check source
    ok_src, src_out = adb.run(["shell", "ls", "-ld", src_path])
    if not ok_src:
        ui.error(f"Source does not exist: {src_path}")
        return

    dst_path = _clean_remote_path(ui.get_choice("Enter destination path on device (e.g. /sdcard/Documents/test_renamed.txt)"))
    if not dst_path:
        ui.warning("Operation cancelled: No destination path provided.")
        return

    ui.info(f"Moving '{src_path}' -> '{dst_path}'...")
    ok, output = adb.run(["shell", "mv", src_path, dst_path], timeout=30)

    if ok:
        ui.success(f"Successfully moved / renamed to: {dst_path}")
    else:
        ui.error(f"Move/Rename failed: {output}")


# ─── Feature 11: View File Contents (cat / head / tail) ──────────────────────

def view_file_contents():
    """Display the text content of a file on the device."""
    if not ensure_device():
        return

    ui.header("View File Contents (cat / head / tail)")
    file_path = _clean_remote_path(ui.get_choice("Enter remote file path to view (e.g. /sdcard/build.prop or /data/local/tmp/log.txt)"))
    if not file_path:
        ui.warning("Operation cancelled: No file path provided.")
        return

    print(f"""
  {ui.Colors.CYAN}Display Modes:{ui.Colors.RESET}
    [1] Entire File (first 100 lines)
    [2] First N lines (head -n)
    [3] Last N lines (tail -n)
    [4] Search text pattern in file (grep -n)
    """)

    mode = ui.get_choice("Select viewing mode (default 1)")

    if mode in ("1", ""):
        ok, output = adb.run(["shell", "cat", file_path], timeout=20)
        if not ok:
            ui.error(f"Failed to read file: {output}")
            return
        lines = output.splitlines()
        print(f"\n  {ui.Colors.BOLD}File: {file_path} ({len(lines)} lines):{ui.Colors.RESET}\n")
        for i, line in enumerate(lines[:100], 1):
            print(f"  {ui.Colors.DIM}{i:>4} │{ui.Colors.RESET} {line}")
        if len(lines) > 100:
            ui.info(f"File truncated. Showing first 100 of {len(lines)} lines.")

    elif mode == "2":
        num_str = ui.get_choice("Enter number of lines to display from top (default: 25)")
        n_lines = int(num_str) if num_str.isdigit() else 25
        ok, output = adb.run(["shell", "head", "-n", str(n_lines), file_path], timeout=15)
        if ok:
            print(f"\n  {ui.Colors.BOLD}First {n_lines} lines of {file_path}:{ui.Colors.RESET}\n")
            for i, line in enumerate(output.splitlines(), 1):
                print(f"  {ui.Colors.DIM}{i:>4} │{ui.Colors.RESET} {line}")
        else:
            ui.error(f"Failed: {output}")

    elif mode == "3":
        num_str = ui.get_choice("Enter number of lines to display from bottom (default: 25)")
        n_lines = int(num_str) if num_str.isdigit() else 25
        ok, output = adb.run(["shell", "tail", "-n", str(n_lines), file_path], timeout=15)
        if ok:
            print(f"\n  {ui.Colors.BOLD}Last {n_lines} lines of {file_path}:{ui.Colors.RESET}\n")
            for i, line in enumerate(output.splitlines(), 1):
                print(f"  {ui.Colors.DIM}{i:>4} │{ui.Colors.RESET} {line}")
        else:
            ui.error(f"Failed: {output}")

    elif mode == "4":
        pattern = ui.get_choice("Enter search string / keyword")
        if not pattern:
            return
        ok, output = adb.run(["shell", "grep", "-in", pattern, file_path], timeout=15)
        if ok and output.strip():
            print(f"\n  {ui.Colors.BOLD}Matches for '{pattern}' in {file_path}:{ui.Colors.RESET}\n")
            for line in output.splitlines()[:50]:
                print(f"  {ui.Colors.GREEN}→{ui.Colors.RESET} {line}")
        else:
            ui.info(f"No matches found for '{pattern}'.")


# ─── Feature 12: Check File Permissions & Metadata ───────────────────────────

def check_file_permissions():
    """Inspect detailed permissions, ownership, and SELinux security context."""
    if not ensure_device():
        return

    ui.header("Check File Info & Permissions")
    target_path = _clean_remote_path(ui.get_choice("Enter file or directory path on device"))
    if not target_path:
        ui.warning("Operation cancelled: No path provided.")
        return

    # Run stat and ls -ldZ
    ok_ls, ls_out = adb.run(["shell", "ls", "-ldZ", target_path])
    ok_stat, stat_out = adb.run(["shell", "stat", target_path])

    if not ok_ls and not ok_stat:
        ui.error(f"Could not inspect path '{target_path}': File not found or inaccessible.")
        return

    details = {"Target Path": target_path}

    if ok_ls:
        # Format of ls -ldZ: perms user group selinux_context name
        parts = ls_out.split()
        if len(parts) >= 5:
            details["Symbolic Mode"] = parts[0]
            details["Owner User"] = parts[1]
            details["Owner Group"] = parts[2]
            details["SELinux Context"] = parts[3]

    if ok_stat:
        for line in stat_out.splitlines():
            line = line.strip()
            if line.startswith("Size:"):
                details["Stat Summary"] = line
            elif line.startswith("Access: ("):
                details["Access & Octal"] = line
            elif line.startswith("Modify:"):
                details["Last Modified"] = line
            elif line.startswith("Change:"):
                details["Status Changed"] = line
    else:
        details["Directory Details"] = ls_out

    print(f"\n  {ui.Colors.BOLD}File Metadata & Security Context:{ui.Colors.RESET}\n")
    ui.print_kv(details)


# ─── Feature 13: Change File Permissions (chmod) ─────────────────────────────

def change_file_permissions():
    """Modify permissions for a file or directory on the device (chmod)."""
    if not ensure_device():
        return

    ui.header("Change File Permissions (chmod)")
    target_path = _clean_remote_path(ui.get_choice("Enter file or directory path on device"))
    if not target_path:
        ui.warning("Operation cancelled: No path provided.")
        return

    # Check current status
    ok_stat, stat_out = adb.run(["shell", "ls", "-ld", target_path])
    if not ok_stat:
        ui.error(f"Target does not exist: {target_path}")
        return

    ui.info(f"Current permissions: {stat_out.strip()}")

    print(f"""
  {ui.Colors.CYAN}Common Permission Presets:{ui.Colors.RESET}
    [1] 755  (rwxr-xr-x - Standard executable / directory)
    [2] 644  (rw-r--r-- - Standard readable file)
    [3] 777  (rwxrwxrwx - Read/Write/Execute for all)
    [4] 600  (rw------- - Private owner-only read/write)
    [5] 700  (rwx------ - Private owner-only executable)
    [6] +x   (Make file executable)
    [7] Custom chmod mode
    """)

    mode_choice = ui.get_choice("Select permission preset (1-6) or enter custom mode")
    mode = "644"

    if mode_choice == "1":
        mode = "755"
    elif mode_choice == "2":
        mode = "644"
    elif mode_choice == "3":
        mode = "777"
    elif mode_choice == "4":
        mode = "600"
    elif mode_choice == "5":
        mode = "700"
    elif mode_choice == "6":
        mode = "+x"
    elif mode_choice == "7":
        custom = ui.get_choice("Enter custom chmod string (e.g. 664, u+rw, a+r)")
        mode = custom if custom else "644"
    else:
        mode = mode_choice if mode_choice else "644"

    recursive = False
    if stat_out.startswith("d"):
        recursive = ui.confirm("Target is a directory. Apply permissions recursively (-R)?")

    cmd = ["shell", "chmod"]
    if recursive:
        cmd.append("-R")
    cmd.extend([mode, target_path])

    ui.info(f"Applying 'chmod {'-R ' if recursive else ''}{mode}' to {target_path}...")
    ok, output = adb.run(cmd, timeout=20)

    if ok:
        ok_verify, verify_out = adb.run(["shell", "ls", "-ld", target_path])
        ui.success(f"Permissions updated successfully!")
        if ok_verify:
            ui.info(f"New attributes: {verify_out.strip()}")
    else:
        ui.error(f"Failed to change permissions: {output}")


# ─── Feature 14: Verify File Checksum / Hash (MD5 / SHA256) ──────────────────

def verify_file_checksum():
    """Calculate and verify MD5, SHA1, or SHA256 cryptographic hash of a remote file."""
    if not ensure_device():
        return

    ui.header("Verify File Checksum / Hash")
    remote_path = _clean_remote_path(ui.get_choice("Enter remote file path on device"))
    if not remote_path:
        ui.warning("Operation cancelled: No path provided.")
        return

    print(f"""
  {ui.Colors.CYAN}Hash Algorithms:{ui.Colors.RESET}
    [1] MD5     (md5sum)
    [2] SHA-256 (sha256sum)
    [3] SHA-1   (sha1sum)
    """)

    algo_choice = ui.get_choice("Select hash algorithm (default 1)")
    cmd_name = "md5sum"
    algo_name = "MD5"

    if algo_choice == "2":
        cmd_name = "sha256sum"
        algo_name = "SHA-256"
    elif algo_choice == "3":
        cmd_name = "sha1sum"
        algo_name = "SHA-1"

    ui.info(f"Computing {algo_name} hash for '{remote_path}'...")
    ok, output = adb.run(["shell", cmd_name, remote_path], timeout=60)

    if ok and output.strip():
        hash_val = output.split()[0] if output.split() else output.strip()
        print(f"\n  {ui.Colors.BOLD}{algo_name} Hash:{ui.Colors.RESET} {ui.Colors.GREEN}{hash_val}{ui.Colors.RESET}")
        print(f"  {ui.Colors.DIM}Target:{ui.Colors.RESET}    {remote_path}\n")

        compare_hash = ui.get_choice("Enter expected hash to compare (optional, press Enter to skip)").strip()
        if compare_hash:
            if hash_val.lower() == compare_hash.lower():
                ui.success("MATCH: File integrity verified! Hashes match perfectly.")
            else:
                ui.error(f"MISMATCH: Expected '{compare_hash}' but got '{hash_val}'.")
    else:
        ui.error(f"Failed to compute hash: {output}")


# ─── Feature 15: Create Empty File (touch) ───────────────────────────────────

def touch_file():
    """Create an empty file or update its timestamp on the device."""
    if not ensure_device():
        return

    ui.header("Create Empty File (touch)")
    file_path = _clean_remote_path(ui.get_choice("Enter remote file path to create (e.g. /sdcard/Download/newfile.txt)"))
    if not file_path:
        ui.warning("Operation cancelled: No path provided.")
        return

    ok, output = adb.run(["shell", "touch", file_path])
    if ok:
        ui.success(f"File created / timestamp updated: {file_path}")
    else:
        ui.error(f"Failed to touch file: {output}")


# ─── Main Menu Entry Point ───────────────────────────────────────────────────

def file_manager_menu():
    """Public entry function and interactive loop for the File Manager module."""
    while True:
        ui.clear()
        ui.print_banner()
        ui.print_sub_banner("File Manager", icon="📁")

        options = [
            "Push file to device",
            "Pull file from device",
            "Push entire folder (recursive)",
            "Pull entire folder (recursive)",
            "List directory contents (ls -la)",
            "Search files by name (find)",
            "Disk & storage usage (df / du)",
            "Create directory on device",
            "Delete file or folder on device",
            "Move / rename file or folder",
            "View file contents (cat / head / tail)",
            "Check file info & permissions",
            "Change file permissions (chmod)",
            "Verify file checksum (MD5 / SHA256)",
            "Create empty file (touch)",
        ]

        ui.print_menu("File Management Operations", options, columns=2)
        choice = ui.get_choice()

        if choice == "0":
            break
        elif choice == "1":
            push_file()
        elif choice == "2":
            pull_file()
        elif choice == "3":
            push_folder()
        elif choice == "4":
            pull_folder()
        elif choice == "5":
            list_directory()
        elif choice == "6":
            search_files()
        elif choice == "7":
            disk_usage_analysis()
        elif choice == "8":
            create_directory()
        elif choice == "9":
            delete_file_or_folder()
        elif choice == "10":
            move_rename_file()
        elif choice == "11":
            view_file_contents()
        elif choice == "12":
            check_file_permissions()
        elif choice == "13":
            change_file_permissions()
        elif choice == "14":
            verify_file_checksum()
        elif choice == "15":
            touch_file()
        else:
            ui.error("Invalid option. Please choose a valid number from the menu.")

        ui.pause()
