"""
modules/app_manager.py — App Management Module for DroidCommander.

Provides package management tools: install, batch install, uninstall,
list/filter packages, search, launch, force-stop, clear data, inspect permissions,
extract APKs, enable/disable apps, view detailed version info, and manage settings.
"""

from datetime import datetime
import glob
import os
import re
import time
from typing import Dict, List, Optional, Set, Tuple

from core.adb import adb
from core import ui
from core.device import ensure_device


# ─── Helper Functions ────────────────────────────────────────────────────────

def _clean_path(path_str: str) -> str:
    """Clean quoted or escaped local paths."""
    cleaned = path_str.strip().strip('"').strip("'")
    return os.path.expanduser(cleaned)


def _get_installed_packages(filter_flag: str = "") -> List[str]:
    """
    Fetch sorted list of package names from device.

    Parameters
    ----------
    filter_flag : str
        Optional flag for `pm list packages` ('-3', '-s', '-d', '-e', etc.)
    """
    args = ["shell", "pm", "list", "packages"]
    if filter_flag:
        args.append(filter_flag)

    ok, output = adb.run(args, timeout=20)
    if not ok or not output:
        return []

    packages: List[str] = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            pkg = line.replace("package:", "").strip()
            if pkg:
                packages.append(pkg)

    return sorted(packages)


def _select_or_search_package(prompt: str = "Enter package name") -> Optional[str]:
    """
    Prompt user for a package name with interactive search fallback.

    Typing '?' or 's' triggers an interactive package search filter.
    """
    ui.info(f"{prompt} (or enter {ui.Colors.YELLOW}'?'{ui.Colors.CYAN} to search installed apps):{ui.Colors.RESET}")
    val = ui.get_choice(prompt)

    if not val:
        return None

    if val in ("?", "s", "search", "/"):
        query = ui.get_choice("Enter keyword to search installed packages")
        if not query:
            return None

        all_pkgs = _get_installed_packages()
        matches = [p for p in all_pkgs if query.lower() in p.lower()]

        if not matches:
            ui.warning(f"No packages found matching '{query}'.")
            return None

        ui.header(f"Matching Packages ({len(matches)} found):")
        print()
        for idx, pkg in enumerate(matches[:30], 1):
            print(f"  {ui.Colors.YELLOW}[{idx:>2}]{ui.Colors.RESET} {pkg}")
        print()

        sel = ui.get_choice("Select package number (or enter 0 to cancel)")
        try:
            sel_idx = int(sel) - 1
            if 0 <= sel_idx < len(matches):
                chosen = matches[sel_idx]
                ui.success(f"Selected: {chosen}")
                return chosen
        except ValueError:
            pass

        ui.error("Invalid selection.")
        return None

    return val


def _paginate_list(items: List[str], title: str, page_size: int = 40):
    """Display paginated list with search, export, and navigation options."""
    if not items:
        ui.info(f"No items found for {title}.")
        return

    total = len(items)
    current_page = 0
    total_pages = (total + page_size - 1) // page_size

    while True:
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, total)
        page_items = items[start_idx:end_idx]

        ui.clear()
        ui.print_banner()
        ui.print_device_status(adb.serial)
        ui.header(f"{title} — Page {current_page + 1}/{total_pages} (Items {start_idx + 1}-{end_idx} of {total}):")
        print()

        for idx, item in enumerate(page_items, start_idx + 1):
            print(f"  {ui.Colors.DIM}{idx:>4}.{ui.Colors.RESET} {item}")

        print(f"\n  {ui.Colors.CYAN}[N]{ui.Colors.RESET} Next  |  {ui.Colors.CYAN}[P]{ui.Colors.RESET} Prev  |  {ui.Colors.CYAN}[E]{ui.Colors.RESET} Export to file  |  {ui.Colors.CYAN}[Q]{ui.Colors.RESET} Back")
        action = ui.get_choice("Action").lower()

        if action in ("q", "0", "exit", "back"):
            break
        elif action in ("n", "next", " "):
            if current_page < total_pages - 1:
                current_page += 1
            else:
                ui.info("Already at the last page.")
                time.sleep(0.5)
        elif action in ("p", "prev"):
            if current_page > 0:
                current_page -= 1
            else:
                ui.info("Already at the first page.")
                time.sleep(0.5)
        elif action in ("e", "export", "save"):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            sanitized_title = re.sub(r'[^a-zA-Z0-9_]', '_', title.lower())
            filename = f"{sanitized_title}_{timestamp}.txt"
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(f"=== {title} ===\n")
                    f.write(f"Device: {adb.serial}\n")
                    f.write(f"Total: {len(items)}\n\n")
                    for it in items:
                        f.write(f"{it}\n")
                ui.success(f"Exported list to: {os.path.abspath(filename)}")
                ui.pause()
            except Exception as e:
                ui.error(f"Export failed: {e}")
                ui.pause()


# ─── 1. Install APK ──────────────────────────────────────────────────────────

def install_single_apk():
    """Install a single APK file onto the device."""
    if not ensure_device():
        return

    ui.print_sub_banner("Install Single APK", "📥")

    apk_path = ui.get_choice("Enter path to APK file (drag & drop supported)")
    if not apk_path:
        return

    clean_path = _clean_path(apk_path)
    if not os.path.isfile(clean_path):
        ui.error(f"File not found: {clean_path}")
        return

    if not clean_path.lower().endswith(".apk"):
        ui.warning("Warning: Selected file does not have a .apk extension.")
        if not ui.confirm("Do you want to proceed anyway?"):
            return

    file_size_mb = os.path.getsize(clean_path) / (1024 * 1024)
    ui.info(f"File: {os.path.basename(clean_path)} ({file_size_mb:.2f} MB)")

    print()
    allow_reinstall = ui.confirm("Replace existing application if already installed? (-r)")
    grant_perms = ui.confirm("Grant all runtime permissions automatically? (-g)")
    allow_downgrade = ui.confirm("Allow version downgrade if applicable? (-d)")

    install_args = ["install"]
    if allow_reinstall:
        install_args.append("-r")
    if grant_perms:
        install_args.append("-g")
    if allow_downgrade:
        install_args.append("-d")
    install_args.append(clean_path)

    ui.info("Installing APK onto device... Please wait.")
    ok, output = adb.run(install_args, timeout=180)

    if ok and "Success" in output:
        ui.success("APK installed successfully!")
    else:
        ui.error(f"Installation failed: {output}")
        if "INSTALL_FAILED_ALREADY_EXISTS" in output:
            ui.info("Tip: Re-run with replace flag (-r) enabled.")
        elif "INSTALL_FAILED_VERSION_DOWNGRADE" in output:
            ui.info("Tip: Re-run with downgrade flag (-d) enabled or uninstall previous version.")
        elif "INSTALL_FAILED_INSUFFICIENT_STORAGE" in output:
            ui.info("Tip: Free up internal storage on the target device.")
        elif "INSTALL_PARSE_FAILED" in output:
            ui.info("Tip: Corrupted APK file or incompatible minSdk version.")


# ─── 2. Batch Install APKs from Folder ───────────────────────────────────────

def batch_install_apks():
    """Batch install all APK files located in a local directory."""
    if not ensure_device():
        return

    ui.print_sub_banner("Batch Install APKs from Folder", "📦")

    folder_path = ui.get_choice("Enter directory path containing APK files")
    if not folder_path:
        return

    clean_dir = _clean_path(folder_path)
    if not os.path.isdir(clean_dir):
        ui.error(f"Directory not found: {clean_dir}")
        return

    apk_files = glob.glob(os.path.join(clean_dir, "*.apk"))
    if not apk_files:
        ui.warning("No .apk files found in the specified directory.")
        return

    ui.info(f"Found {len(apk_files)} APK files:")
    for i, apk in enumerate(apk_files[:10], 1):
        sz = os.path.getsize(apk) / (1024 * 1024)
        print(f"    {i}. {os.path.basename(apk)} ({sz:.2f} MB)")
    if len(apk_files) > 10:
        print(f"    ... and {len(apk_files) - 10} more APKs.")

    print()
    if not ui.confirm(f"Proceed with batch installation of {len(apk_files)} APKs?"):
        ui.info("Batch installation cancelled.")
        return

    grant_perms = ui.confirm("Grant all runtime permissions for each app? (-g)")

    results: List[Tuple[str, str, str]] = []
    total = len(apk_files)

    for idx, apk in enumerate(apk_files, 1):
        apk_name = os.path.basename(apk)
        ui.progress_bar(idx - 1, total, label=f"Installing {apk_name[:20]}...")

        cmd = ["install", "-r"]
        if grant_perms:
            cmd.append("-g")
        cmd.append(apk)

        ok, out = adb.run(cmd, timeout=180)
        status = "Success" if (ok and "Success" in out) else "Failed"
        reason = "Installed" if status == "Success" else (out.splitlines()[-1] if out else "Unknown error")
        results.append((apk_name, status, reason))

    ui.progress_bar(total, total, label="Completed batch install")
    print()

    headers = ("APK File Name", "Result", "Details")
    table_rows: List[Tuple[str, ...]] = []
    success_count = 0

    for name, status, reason in results:
        if status == "Success":
            success_count += 1
            status_disp = f"{ui.Colors.GREEN}✓ Success{ui.Colors.RESET}"
        else:
            status_disp = f"{ui.Colors.RED}✗ Failed{ui.Colors.RESET}"
        table_rows.append((name[:35], status_disp, reason[:40]))

    ui.print_table(table_rows, headers)
    print()
    ui.success(f"Batch install finished: {success_count}/{total} APKs successfully installed.")


# ─── 3. Uninstall App ────────────────────────────────────────────────────────

def uninstall_app():
    """Uninstall an application by package name."""
    if not ensure_device():
        return

    ui.print_sub_banner("Uninstall Application", "🗑️")

    pkg = _select_or_search_package("Enter package name to uninstall")
    if not pkg:
        return

    keep_data = ui.confirm(f"Keep application data & cache directories for '{pkg}'? (-k)")
    if not ui.confirm(f"Are you SURE you want to uninstall '{pkg}'?"):
        ui.info("Uninstallation cancelled.")
        return

    args = ["uninstall"]
    if keep_data:
        args.append("-k")
    args.append(pkg)

    ui.info(f"Uninstalling {pkg}...")
    ok, output = adb.run(args, timeout=45)

    if ok and "Success" in output:
        ui.success(f"Successfully uninstalled {pkg}")
    else:
        ui.error(f"Uninstallation failed: {output}")


# ─── 4. List All Installed Apps ──────────────────────────────────────────────

def list_all_installed_apps():
    """List all packages installed on device."""
    if not ensure_device():
        return

    ui.info("Fetching complete package list from device...")
    pkgs = _get_installed_packages()
    _paginate_list(pkgs, "All Installed Packages")


# ─── 5. List Third-Party Apps Only ───────────────────────────────────────────

def list_third_party_apps():
    """List only user-installed / third-party packages (-3)."""
    if not ensure_device():
        return

    ui.info("Fetching third-party package list from device...")
    pkgs = _get_installed_packages("-3")
    _paginate_list(pkgs, "Third-Party (User) Installed Packages")


# ─── 6. List System Apps Only ────────────────────────────────────────────────

def list_system_apps():
    """List only pre-installed system packages (-s)."""
    if not ensure_device():
        return

    ui.info("Fetching system package list from device...")
    pkgs = _get_installed_packages("-s")
    _paginate_list(pkgs, "System Pre-Installed Packages")


# ─── 7. Search Installed Apps ────────────────────────────────────────────────

def search_installed_apps():
    """Search installed apps by keyword and provide interactive actions."""
    if not ensure_device():
        return

    ui.print_sub_banner("Search Installed Apps", "🔍")

    query = ui.get_choice("Enter search keyword (e.g. 'camera', 'google', 'whatsapp')")
    if not query:
        return

    all_pkgs = _get_installed_packages()
    matches = [p for p in all_pkgs if query.lower() in p.lower()]

    if not matches:
        ui.warning(f"No packages found matching '{query}'.")
        return

    ui.header(f"Found {len(matches)} matching packages for '{query}':")
    print()
    headers = ("#", "Package Name")
    rows = [(str(i), p) for i, p in enumerate(matches, 1)]
    ui.print_table(rows, headers)
    print()

    sel = ui.get_choice("Select a package number for Quick Actions (or 0 to exit)")
    try:
        idx = int(sel) - 1
        if not (0 <= idx < len(matches)):
            return
    except ValueError:
        return

    target_pkg = matches[idx]
    _quick_actions_menu(target_pkg)


def _quick_actions_menu(pkg: str):
    """Submenu of operations for a selected package."""
    while True:
        ui.clear()
        ui.print_banner()
        ui.print_device_status(adb.serial)
        ui.header(f"Quick Actions for: {ui.Colors.CYAN}{pkg}{ui.Colors.RESET}")
        print()
        print(f"  {ui.Colors.YELLOW}[ 1]{ui.Colors.RESET} Launch App")
        print(f"  {ui.Colors.YELLOW}[ 2]{ui.Colors.RESET} Force Stop App")
        print(f"  {ui.Colors.YELLOW}[ 3]{ui.Colors.RESET} Clear App Data & Cache")
        print(f"  {ui.Colors.YELLOW}[ 4]{ui.Colors.RESET} View App Version & Details")
        print(f"  {ui.Colors.YELLOW}[ 5]{ui.Colors.RESET} View App Permissions")
        print(f"  {ui.Colors.YELLOW}[ 6]{ui.Colors.RESET} Get APK Path on Device")
        print(f"  {ui.Colors.YELLOW}[ 7]{ui.Colors.RESET} Extract / Pull APK to PC")
        print(f"  {ui.Colors.YELLOW}[ 8]{ui.Colors.RESET} Enable / Disable App")
        print(f"  {ui.Colors.YELLOW}[ 9]{ui.Colors.RESET} Open App Info in Device Settings")
        print(f"  {ui.Colors.YELLOW}[10]{ui.Colors.RESET} Uninstall App")
        print(f"\n  {ui.Colors.YELLOW}[ 0]{ui.Colors.RESET} ← Back to Search\n")

        sub_c = ui.get_choice()

        if sub_c == "0":
            break
        elif sub_c == "1":
            _launch_pkg(pkg)
        elif sub_c == "2":
            _force_stop_pkg(pkg)
        elif sub_c == "3":
            _clear_pkg_data(pkg)
        elif sub_c == "4":
            _show_pkg_version_info(pkg)
        elif sub_c == "5":
            _view_pkg_permissions(pkg)
        elif sub_c == "6":
            _get_pkg_apk_path(pkg)
        elif sub_c == "7":
            _extract_pkg_apk(pkg)
        elif sub_c == "8":
            _toggle_pkg_state(pkg)
        elif sub_c == "9":
            _open_pkg_settings(pkg)
        elif sub_c == "10":
            if ui.confirm(f"Are you sure you want to uninstall '{pkg}'?"):
                ok, out = adb.run(["uninstall", pkg])
                if ok and "Success" in out:
                    ui.success(f"Uninstalled {pkg}")
                    ui.pause()
                    break
                else:
                    ui.error(f"Uninstall failed: {out}")
        else:
            ui.error("Invalid choice.")

        ui.pause()


# ─── 8. Launch App ───────────────────────────────────────────────────────────

def _launch_pkg(pkg: str):
    """Launch package helper."""
    ui.info(f"Launching {pkg}...")
    ok, output = adb.run([
        "shell", "monkey",
        "-p", pkg,
        "-c", "android.intent.category.LAUNCHER",
        "1"
    ], timeout=15)

    if ok and ("Events injected: 1" in output or "monkey" in output.lower()):
        ui.success(f"App {pkg} launched successfully!")
    else:
        # Fallback to resolving intent
        ok_res, res_out = adb.run(["shell", "cmd", "package", "resolve-activity", "--brief", pkg])
        if ok_res and "/" in res_out:
            activity = res_out.splitlines()[-1].strip()
            ok_start, _ = adb.run(["shell", "am", "start", "-n", activity])
            if ok_start:
                ui.success(f"App launched via activity: {activity}")
                return
        ui.error(f"Failed to launch app: {output}")


def launch_app():
    """Launch app by package name."""
    if not ensure_device():
        return

    ui.print_sub_banner("Launch Application", "🚀")
    pkg = _select_or_search_package("Enter package name to launch")
    if pkg:
        _launch_pkg(pkg)


# ─── 9. Force Stop App ───────────────────────────────────────────────────────

def _force_stop_pkg(pkg: str):
    """Force stop helper."""
    ui.info(f"Force stopping {pkg}...")
    ok, output = adb.run(["shell", "am", "force-stop", pkg])
    if ok:
        ui.success(f"Force stopped process: {pkg}")
    else:
        ui.error(f"Failed to stop app: {output}")


def force_stop_app():
    """Force stop a running application."""
    if not ensure_device():
        return

    ui.print_sub_banner("Force Stop Application", "🛑")
    pkg = _select_or_search_package("Enter package name to force stop")
    if pkg:
        _force_stop_pkg(pkg)


# ─── 10. Clear App Data & Cache ──────────────────────────────────────────────

def _clear_pkg_data(pkg: str):
    """Clear package data helper."""
    if not ui.confirm(f"Clear all data, settings, accounts, and cache for '{pkg}'?"):
        ui.info("Cancelled.")
        return

    ui.info(f"Clearing data for {pkg}...")
    ok, output = adb.run(["shell", "pm", "clear", pkg])
    if ok and "Success" in output:
        ui.success(f"App data and cache cleared for {pkg}!")
    else:
        ui.error(f"Clear failed: {output}")


def clear_app_data():
    """Clear application data and cache."""
    if not ensure_device():
        return

    ui.print_sub_banner("Clear App Data & Cache", "🧹")
    pkg = _select_or_search_package("Enter package name to clear")
    if pkg:
        _clear_pkg_data(pkg)


# ─── 11. View App Permissions ────────────────────────────────────────────────

def _view_pkg_permissions(pkg: str):
    """Inspect permissions for package."""
    ui.info(f"Reading package manifest & permissions for {pkg}...")
    ok, output = adb.run(["shell", "dumpsys", "package", pkg], timeout=20)
    if not ok or not output:
        ui.error(f"Failed to dump package information for {pkg}.")
        return

    granted_perms: Set[str] = set()
    revoked_perms: Set[str] = set()
    install_perms: Set[str] = set()
    requested_perms: Set[str] = set()

    current_section = ""
    for line in output.splitlines():
        line_str = line.strip()
        if "requested permissions:" in line.lower():
            current_section = "requested"
        elif "install permissions:" in line.lower():
            current_section = "install"
        elif "runtime permissions:" in line.lower():
            current_section = "runtime"
        elif ":" in line_str and not line_str.startswith("android.permission.") and not line_str.startswith("com."):
            if not any(k in line_str.lower() for k in ("permission", "granted=")):
                current_section = ""

        if current_section == "requested" and line_str and not line_str.endswith(":"):
            requested_perms.add(line_str)
        elif current_section == "install" and line_str and ":" in line_str:
            perm_name = line_str.split(":")[0].strip()
            if "granted=true" in line_str:
                install_perms.add(perm_name)
        elif current_section == "runtime" and line_str and ":" in line_str:
            perm_name = line_str.split(":")[0].strip()
            if "granted=true" in line_str:
                granted_perms.add(perm_name)
            elif "granted=false" in line_str:
                revoked_perms.add(perm_name)

    headers = ("Permission Name", "Type", "Status")
    rows: List[Tuple[str, ...]] = []

    for p in sorted(granted_perms):
        rows.append((p.replace("android.permission.", ""), "Runtime", f"{ui.Colors.GREEN}✓ GRANTED{ui.Colors.RESET}"))
    for p in sorted(revoked_perms):
        rows.append((p.replace("android.permission.", ""), "Runtime", f"{ui.Colors.RED}✗ DENIED{ui.Colors.RESET}"))
    for p in sorted(install_perms):
        if p not in granted_perms and p not in revoked_perms:
            rows.append((p.replace("android.permission.", ""), "Install-time", f"{ui.Colors.CYAN}✓ Granted{ui.Colors.RESET}"))

    # Fallback if specific runtime dumps weren't matched
    if not rows and requested_perms:
        for p in sorted(requested_perms):
            rows.append((p.replace("android.permission.", ""), "Declared", "Requested"))

    if rows:
        ui.header(f"Permissions for {pkg} ({len(rows)} total):")
        print()
        ui.print_table(rows, headers)
    else:
        ui.info(f"No special permissions recorded for {pkg}.")


def view_app_permissions():
    """View permissions granted and requested by an app."""
    if not ensure_device():
        return

    ui.print_sub_banner("App Permissions Inspector", "🔐")
    pkg = _select_or_search_package("Enter package name to inspect")
    if pkg:
        _view_pkg_permissions(pkg)


# ─── 12. Get APK Path on Device ──────────────────────────────────────────────

def _get_pkg_apk_path(pkg: str) -> List[str]:
    """Retrieve device APK path(s) for a package."""
    ok, output = adb.run(["shell", "pm", "path", pkg])
    if not ok or not output:
        ui.error(f"Package '{pkg}' not found on device.")
        return []

    paths: List[str] = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            apk_p = line.replace("package:", "").strip()
            if apk_p:
                paths.append(apk_p)

    ui.header(f"APK Path(s) for {pkg}:")
    print()
    for idx, p in enumerate(paths, 1):
        # Query file size on device
        ok_sz, sz_out = adb.run(["shell", "ls", "-lh", p])
        sz_desc = sz_out.split()[4] if (ok_sz and len(sz_out.split()) >= 5) else "N/A"
        print(f"  {ui.Colors.CYAN}[{idx}]{ui.Colors.RESET} {p} {ui.Colors.DIM}(Size: {sz_desc}){ui.Colors.RESET}")
    print()
    return paths


def get_apk_path():
    """Get APK filesystem path on the Android device."""
    if not ensure_device():
        return

    ui.print_sub_banner("Get APK Device Path", "📍")
    pkg = _select_or_search_package("Enter package name to locate")
    if pkg:
        _get_pkg_apk_path(pkg)


# ─── 13. Extract / Pull APK from Device ──────────────────────────────────────

def _extract_pkg_apk(pkg: str):
    """Extract APK helper."""
    paths = _get_pkg_apk_path(pkg)
    if not paths:
        return

    default_dir = os.path.join(".", "extracted_apks", pkg)
    ui.info(f"Default extraction folder: {os.path.abspath(default_dir)}")
    custom_dir = ui.get_choice("Enter destination folder (or press Enter for default)")
    dest_dir = _clean_path(custom_dir) if custom_dir else default_dir

    os.makedirs(dest_dir, exist_ok=True)
    ui.info(f"Pulling {len(paths)} APK file(s) to: {dest_dir}...")

    pulled = 0
    for idx, remote_apk in enumerate(paths, 1):
        filename = os.path.basename(remote_apk)
        if filename == "base.apk" and len(paths) == 1:
            local_name = f"{pkg}.apk"
        else:
            local_name = f"{pkg}_{filename}"

        local_file = os.path.join(dest_dir, local_name)
        ok, out = adb.run(["pull", remote_apk, local_file], timeout=120)
        if ok and os.path.isfile(local_file):
            sz_mb = os.path.getsize(local_file) / (1024 * 1024)
            ui.success(f"Extracted: {local_name} ({sz_mb:.2f} MB)")
            pulled += 1
        else:
            ui.error(f"Failed to pull {filename}: {out}")

    if pulled == len(paths):
        ui.success(f"All {pulled} APK(s) successfully extracted to: {os.path.abspath(dest_dir)}")


def extract_pull_apk():
    """Extract and download APK file(s) from device to PC."""
    if not ensure_device():
        return

    ui.print_sub_banner("Extract / Pull APK to PC", "📤")
    pkg = _select_or_search_package("Enter package name to extract")
    if pkg:
        _extract_pkg_apk(pkg)


# ─── 14. Disable / Enable App ────────────────────────────────────────────────

def _toggle_pkg_state(pkg: str):
    """Toggle enabled/disabled state helper."""
    # Check current status
    ok, out = adb.run(["shell", "pm", "list", "packages", "-d"])
    is_disabled = ok and f"package:{pkg}" in out

    current_state_str = f"{ui.Colors.RED}Disabled / Frozen{ui.Colors.RESET}" if is_disabled else f"{ui.Colors.GREEN}Enabled / Active{ui.Colors.RESET}"
    ui.header(f"Package: {pkg}")
    ui.info(f"Current State: {current_state_str}")
    print()

    if is_disabled:
        if ui.confirm(f"Enable (unfreeze) package '{pkg}'?"):
            ok_en, en_out = adb.run(["shell", "pm", "enable", pkg])
            if ok_en and "enabled" in en_out.lower():
                ui.success(f"Successfully enabled {pkg}!")
            else:
                ui.error(f"Enable failed: {en_out}")
    else:
        if ui.confirm(f"Disable (freeze) package '{pkg}' for user 0?"):
            ok_dis, dis_out = adb.run(["shell", "pm", "disable-user", "--user", "0", pkg])
            if ok_dis and "disabled" in dis_out.lower():
                ui.success(f"Successfully disabled {pkg}!")
            else:
                ui.error(f"Disable failed: {dis_out}")


def toggle_app_state():
    """Enable or disable (freeze/unfreeze) an application."""
    if not ensure_device():
        return

    ui.print_sub_banner("Enable / Disable (Freeze) App", "❄️")
    pkg = _select_or_search_package("Enter package name to toggle")
    if pkg:
        _toggle_pkg_state(pkg)


# ─── 15. App Version & Detailed Info ─────────────────────────────────────────

def _show_pkg_version_info(pkg: str):
    """Parse and display detailed package version and installation metadata."""
    ui.info(f"Querying detailed package information for {pkg}...")
    ok, output = adb.run(["shell", "dumpsys", "package", pkg], timeout=20)
    if not ok or not output:
        ui.error(f"Could not retrieve details for package '{pkg}'.")
        return

    details: Dict[str, str] = {
        "Package Name": pkg,
        "Version Name": "Unknown",
        "Version Code": "Unknown",
        "Target SDK": "Unknown",
        "Min SDK": "Unknown",
        "First Install Time": "Unknown",
        "Last Update Time": "Unknown",
        "Installer Store / Source": "System / Sideloaded",
        "Data Directory": f"/data/user/0/{pkg}",
        "Code / APK Path": "Unknown",
        "Primary CPU ABI": "Unknown",
        "User / App ID": "Unknown",
    }

    for line in output.splitlines():
        line_str = line.strip()
        if "versionName=" in line_str:
            v_match = re.search(r"versionName=([^\s]+)", line_str)
            if v_match:
                details["Version Name"] = v_match.group(1)
        if "versionCode=" in line_str:
            v_code = re.search(r"versionCode=(\d+)", line_str)
            if v_code:
                details["Version Code"] = v_code.group(1)
        if "targetSdk=" in line_str:
            t_sdk = re.search(r"targetSdk=(\d+)", line_str)
            if t_sdk:
                details["Target SDK"] = t_sdk.group(1)
        if "minSdk=" in line_str:
            m_sdk = re.search(r"minSdk=(\d+)", line_str)
            if m_sdk:
                details["Min SDK"] = m_sdk.group(1)
        if "firstInstallTime=" in line_str:
            details["First Install Time"] = line_str.replace("firstInstallTime=", "").strip()
        if "lastUpdateTime=" in line_str:
            details["Last Update Time"] = line_str.replace("lastUpdateTime=", "").strip()
        if "installerPackageName=" in line_str:
            details["Installer Store / Source"] = line_str.replace("installerPackageName=", "").strip()
        if "codePath=" in line_str:
            details["Code / APK Path"] = line_str.replace("codePath=", "").strip()
        if "primaryCpuAbi=" in line_str:
            details["Primary CPU ABI"] = line_str.replace("primaryCpuAbi=", "").strip()
        if "userId=" in line_str or "appId=" in line_str:
            u_match = re.search(r"(?:userId|appId)=(\d+)", line_str)
            if u_match and details["User / App ID"] == "Unknown":
                details["User / App ID"] = u_match.group(1)

    ui.header(f"Application Details: {pkg}")
    print()
    ui.print_kv(details)


def show_app_version_info():
    """Display comprehensive version, target SDK, and install dates."""
    if not ensure_device():
        return

    ui.print_sub_banner("App Version & Package Details", "ℹ️")
    pkg = _select_or_search_package("Enter package name to inspect")
    if pkg:
        _show_pkg_version_info(pkg)


# ─── 16. Open App Settings Page on Device ────────────────────────────────────

def _open_pkg_settings(pkg: str):
    """Open app settings helper."""
    ui.info(f"Opening App Info settings screen on device for {pkg}...")
    ok, out = adb.run([
        "shell", "am", "start",
        "-a", "android.settings.APPLICATION_DETAILS_SETTINGS",
        "-d", f"package:{pkg}"
    ])
    if ok:
        ui.success(f"App Settings opened on device for {pkg}")
    else:
        ui.error(f"Failed to open settings: {out}")


def open_app_settings_page():
    """Open device system Settings page for the specified app."""
    if not ensure_device():
        return

    ui.print_sub_banner("Open App Info Settings", "⚙️")
    pkg = _select_or_search_package("Enter package name")
    if pkg:
        _open_pkg_settings(pkg)


# ─── Main Menu Loop ──────────────────────────────────────────────────────────

def app_manager_menu():
    """Application manager interactive submenu."""
    options = [
        "Install APK (with replace/downgrade flags)",
        "Install multiple APKs from local folder",
        "Uninstall app (with optional data preservation)",
        "List all installed apps (paginated overview)",
        "List third-party (user) apps only",
        "List system pre-installed apps only",
        "Search installed apps by keyword & quick actions",
        "Launch app (by package name)",
        "Force stop running app",
        "Clear app data & cache storage",
        "View app permissions (runtime & install-time)",
        "Get APK filesystem path on device",
        "Extract / pull APK from device to PC",
        "Disable / enable (freeze/unfreeze) app",
        "App version & package metadata info",
        "Open app details in device Settings UI",
    ]

    while True:
        ui.clear()
        ui.print_banner()
        ui.print_device_status(adb.serial)
        ui.print_menu("📦 Application Management", options, columns=2)

        choice = ui.get_choice()

        if choice == "0":
            break
        elif choice == "1":
            install_single_apk()
        elif choice == "2":
            batch_install_apks()
        elif choice == "3":
            uninstall_app()
        elif choice == "4":
            list_all_installed_apps()
        elif choice == "5":
            list_third_party_apps()
        elif choice == "6":
            list_system_apps()
        elif choice == "7":
            search_installed_apps()
        elif choice == "8":
            launch_app()
        elif choice == "9":
            force_stop_app()
        elif choice == "10":
            clear_app_data()
        elif choice == "11":
            view_app_permissions()
        elif choice == "12":
            get_apk_path()
        elif choice == "13":
            extract_pull_apk()
        elif choice == "14":
            toggle_app_state()
        elif choice == "15":
            show_app_version_info()
        elif choice == "16":
            open_app_settings_page()
        else:
            ui.error("Invalid option. Please choose a number from the menu.")

        ui.pause()
