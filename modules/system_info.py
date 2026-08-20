"""
modules/system_info.py — Android System Internals and Deep Diagnostics.

Provides low-level inspection of kernel details, SELinux enforcement, block partitions,
mount points, system features, running system services, init daemons, system uptime,
shared libraries, multi-user profiles, input hardware devices, and boot timing.
"""

import os
import time
from datetime import datetime
from typing import Optional, List, Dict, Tuple

from core.adb import adb
from core import ui
from core.device import ensure_device


# ─── Helper Functions ─────────────────────────────────────────────────────────

def _format_seconds(seconds: float) -> str:
    """Convert float seconds into human-readable DDd HHh MMm SSs format."""
    total_sec = int(seconds)
    days = total_sec // 86400
    hours = (total_sec % 86400) // 3600
    minutes = (total_sec % 3600) // 60
    secs = total_sec % 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0 or days > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def _format_size_kb(size_kb: int) -> str:
    """Format block count in KB to human-readable size."""
    if size_kb < 1024:
        return f"{size_kb} KB"
    elif size_kb < 1024 * 1024:
        return f"{size_kb / 1024:.2f} MB"
    else:
        return f"{size_kb / (1024 * 1024):.2f} GB"


# ─── 1. Kernel Version ────────────────────────────────────────────────────────

def show_kernel_version():
    """Inspect Linux kernel release, compiler info, and architecture."""
    if not ensure_device():
        return

    ui.header("Linux Kernel & Architecture Information")

    # Read /proc/version
    ok1, proc_ver = adb.run_shell("cat /proc/version")
    ok2, uname_a = adb.run_shell("uname -a")
    ok3, kernel_rel = adb.run_shell("cat /proc/sys/kernel/osrelease")

    arch = adb.getprop("ro.product.cpu.abi")
    abi_list = adb.getprop("ro.product.cpu.abilist")
    board_platform = adb.getprop("ro.board.platform")
    soc_model = adb.getprop("ro.soc.model")

    info_dict = {
        "Kernel Release": kernel_rel.strip() if ok3 and kernel_rel else "Unknown",
        "Primary Architecture": arch if arch else "Unknown",
        "Supported ABIs": abi_list if abi_list else arch,
        "SoC Platform": board_platform if board_platform else "Unknown",
        "SoC Model": soc_model if soc_model else "Unknown",
    }

    ui.print_kv(info_dict, indent=4)

    if ok1 and proc_ver:
        print(f"\n  {ui.Colors.BOLD}Kernel Build Details (/proc/version):{ui.Colors.RESET}")
        print(f"  {ui.Colors.DIM}{proc_ver.strip()}{ui.Colors.RESET}")

    if ok2 and uname_a:
        print(f"\n  {ui.Colors.BOLD}System Name & Architecture (uname -a):{ui.Colors.RESET}")
        print(f"  {ui.Colors.DIM}{uname_a.strip()}{ui.Colors.RESET}")


# ─── 2. SELinux Status ────────────────────────────────────────────────────────

def show_selinux_status():
    """Inspect SELinux enforcement mode and policy configurations."""
    if not ensure_device():
        return

    ui.header("SELinux (Security-Enhanced Linux) Status")

    ok, getenforce_out = adb.run_shell("getenforce")
    status = getenforce_out.strip() if ok else "Unknown"

    boot_selinux = adb.getprop("ro.boot.selinux")
    build_selinux = adb.getprop("ro.build.selinux")

    # Check /sys/fs/selinux/enforce if accessible
    ok_node, node_val = adb.run_shell("cat /sys/fs/selinux/enforce")
    node_desc = "1 (Enforcing)" if node_val.strip() == "1" else ("0 (Permissive)" if node_val.strip() == "0" else node_val.strip())

    color = ui.Colors.GREEN if "enforc" in status.lower() else (ui.Colors.YELLOW if "permissive" in status.lower() else ui.Colors.RED)

    print(f"\n  Current Enforcement Mode: {color}{ui.Colors.BOLD}{status.upper()}{ui.Colors.RESET}\n")

    details = {
        "Runtime Mode (getenforce)": status,
        "Kernel Node (/sys/fs/selinux/enforce)": node_desc if ok_node else "Restricted / Protected",
        "Boot Parameter (ro.boot.selinux)": boot_selinux if boot_selinux else "default",
        "Build Default (ro.build.selinux)": build_selinux if build_selinux else "1",
    }
    ui.print_kv(details, indent=4)

    print(f"\n  {ui.Colors.BOLD}Security Context Explanation:{ui.Colors.RESET}")
    if "enforc" in status.lower():
        print(f"  {ui.Colors.GREEN}✓ Enforcing Mode:{ui.Colors.RESET} Mandatory Access Control (MAC) policies are active and actively blocking unauthorized access.")
    elif "permissive" in status.lower():
        print(f"  {ui.Colors.YELLOW}⚠ Permissive Mode:{ui.Colors.RESET} SELinux policies are loaded, but violations are only logged, NOT blocked. Reduced security!")
    else:
        print(f"  {ui.Colors.RED}✗ Disabled Mode:{ui.Colors.RESET} SELinux is inactive. Device is vulnerable to privilege escalation.")


# ─── 3. Partition Layout ──────────────────────────────────────────────────────

def show_partition_layout():
    """Inspect block partition table and mounted filesystem usage."""
    if not ensure_device():
        return

    ui.header("Block Partitions (/proc/partitions) & Disk Storage")

    ok_part, part_out = adb.run_shell("cat /proc/partitions")
    ok_df, df_out = adb.run_shell("df -h")

    if ok_part and part_out:
        lines = part_out.splitlines()
        part_rows = []
        for line in lines[2:]:  # Skip header lines
            parts = line.split()
            if len(parts) >= 4:
                major, minor, blocks, name = parts[0], parts[1], parts[2], parts[3]
                try:
                    size_formatted = _format_size_kb(int(blocks))
                except ValueError:
                    size_formatted = f"{blocks} blocks"
                part_rows.append((name, major, minor, size_formatted))

        if part_rows:
            print(f"\n  {ui.Colors.BOLD}Detected Block Devices ({len(part_rows)} partitions):{ui.Colors.RESET}\n")
            headers = ("Partition Name", "Major", "Minor", "Capacity")
            # Show first 30 if long
            display_rows = part_rows[:30]
            ui.print_table(display_rows, headers=headers)
            if len(part_rows) > 30:
                ui.info(f"Showing first 30 of {len(part_rows)} block partitions.")

    if ok_df and df_out:
        print(f"\n  {ui.Colors.BOLD}Mounted Filesystems Usage (df -h):{ui.Colors.RESET}\n")
        df_lines = df_out.splitlines()
        df_rows = []
        for line in df_lines[1:]:
            parts = line.split()
            if len(parts) >= 6:
                fs, size, used, free, pct, mount = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
                # Filter out raw pseudo mounts for clean view
                if not fs.startswith("/dev/fuse") and not mount.startswith("/mnt/installer"):
                    df_rows.append((mount, fs, size, used, free, pct))

        if df_rows:
            headers = ("Mount Point", "Filesystem", "Total", "Used", "Available", "Use %")
            ui.print_table(df_rows[:25], headers=headers)


# ─── 4. Mount Points ──────────────────────────────────────────────────────────

def show_mount_points():
    """Inspect active mount points and filesystem attributes."""
    if not ensure_device():
        return

    ui.header("Active System Mount Points")

    ok, mount_out = adb.run_shell("mount")
    if not ok or not mount_out:
        ok, mount_out = adb.run_shell("cat /proc/mounts")

    if not ok or not mount_out:
        ui.error("Unable to read mount points.")
        return

    lines = mount_out.splitlines()
    storage_mounts = []
    pseudo_mounts = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Expected format: device on mount_point type fstype (options)
        # or /dev/block/... /system ext4 ro,seclabel,... 0 0
        if " on " in line and " type " in line:
            left, rest = line.split(" on ", 1)
            mpoint, right = rest.split(" type ", 1)
            fstype = right.split()[0]
            opts = right.split("(", 1)[1].rstrip(")") if "(" in right else ""
        else:
            parts = line.split()
            if len(parts) >= 4:
                left = parts[0]
                mpoint = parts[1]
                fstype = parts[2]
                opts = parts[3]
            else:
                continue

        entry = (mpoint, fstype, left, opts[:30] + "..." if len(opts) > 30 else opts)
        if fstype in ("ext4", "f2fs", "erofs", "vfat", "sdcardfs", "fuse", "overlay", "tmpfs"):
            storage_mounts.append(entry)
        else:
            pseudo_mounts.append(entry)

    print(f"\n  {ui.Colors.BOLD}Primary Storage & System Partitions ({len(storage_mounts)} mounts):{ui.Colors.RESET}\n")
    ui.print_table(storage_mounts, headers=("Mount Point", "FS Type", "Source Device", "Mount Options"))

    if ui.confirm("Show pseudo/virtual kernel mounts (sysfs, proc, devtmpfs)?"):
        print(f"\n  {ui.Colors.BOLD}Virtual & Kernel Mounts ({len(pseudo_mounts)} entries):{ui.Colors.RESET}\n")
        ui.print_table(pseudo_mounts[:40], headers=("Mount Point", "FS Type", "Source Device", "Mount Options"))


# ─── 5. Running Services List ─────────────────────────────────────────────────

def show_running_services():
    """List registered Android Binder system services (service list)."""
    if not ensure_device():
        return

    ui.header("Android Binder System Services (service list)")

    ok, output = adb.run_shell("service list")
    if not ok or not output.strip():
        ui.error("Failed to query service list.")
        return

    lines = output.splitlines()
    service_entries: List[Tuple[str, str, str]] = []

    # First line is often: "Found N services:"
    total_str = lines[0] if lines and "Found" in lines[0] else f"Found {len(lines)} services"

    for line in lines:
        line = line.strip()
        if not line or line.startswith("Found"):
            continue
        # Format: 0   accessibility: [android.view.accessibility.IAccessibilityManager]
        parts = line.split(":", 1)
        if len(parts) == 2:
            num_name = parts[0].strip().split()
            idx = num_name[0] if len(num_name) > 1 else ""
            name = num_name[1] if len(num_name) > 1 else num_name[0]
            interface = parts[1].strip().strip("[]")
            service_entries.append((idx, name, interface))

    ui.success(f"{total_str} registered in ServiceManager.")

    # Search / Filter
    query = ui.get_choice("Filter services by name/interface (leave empty to view all)").strip().lower()

    if query:
        filtered = [s for s in service_entries if query in s[1].lower() or query in s[2].lower()]
        ui.info(f"Matched {len(filtered)} service(s) for query '{query}':")
        rows = [(f"  {s[0]}", s[1], s[2]) for s in filtered]
        ui.print_table(rows, headers=("  #", "Service Name", "Interface Descriptor"))
    else:
        # Show paginated
        rows = [(f"  {s[0]}", s[1], s[2]) for s in service_entries[:40]]
        ui.print_table(rows, headers=("  #", "Service Name", "Interface Descriptor"))
        if len(service_entries) > 40:
            ui.info(f"Displaying 40 of {len(service_entries)} services. Use filtering for specific services.")


# ─── 6. System Features ───────────────────────────────────────────────────────

def show_system_features():
    """List and categorize hardware and software features reported by PackageManager."""
    if not ensure_device():
        return

    ui.header("System Features (pm list features)")

    ok, output = adb.run_shell("pm list features")
    if not ok or not output.strip():
        ui.error("Failed to query system features.")
        return

    features = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("feature:"):
            feat = line[len("feature:"):].strip()
            if feat:
                features.append(feat)

    if not features:
        ui.warning("No features returned.")
        return

    # Categorize features
    hw_features = [f for f in features if f.startswith("android.hardware.")]
    sw_features = [f for f in features if f.startswith("android.software.")]
    gl_features = [f for f in features if "gl" in f.lower() or "vulkan" in f.lower()]
    other_features = [f for f in features if f not in hw_features and f not in sw_features and f not in gl_features]

    ui.success(f"Total Features Supported: {len(features)}")
    print(f"  • Hardware Capabilities: {len(hw_features)}")
    print(f"  • Software Capabilities: {len(sw_features)}")
    print(f"  • Graphics (GL / Vulkan): {len(gl_features)}")
    print(f"  • OEM / Custom Features:  {len(other_features)}")

    cat_choice = ui.get_choice("Select category to view: [1] Hardware  [2] Software  [3] Graphics/Vulkan  [4] Search  [5] View All")

    if cat_choice == "1":
        ui.header(f"Hardware Capabilities ({len(hw_features)}):")
        for f in sorted(hw_features):
            short = f.replace("android.hardware.", "")
            print(f"  • {ui.Colors.CYAN}{short:<35}{ui.Colors.RESET} ({f})")
    elif cat_choice == "2":
        ui.header(f"Software Capabilities ({len(sw_features)}):")
        for f in sorted(sw_features):
            short = f.replace("android.software.", "")
            print(f"  • {ui.Colors.GREEN}{short:<35}{ui.Colors.RESET} ({f})")
    elif cat_choice == "3":
        ui.header(f"Graphics Capabilities ({len(gl_features)}):")
        for f in sorted(gl_features):
            print(f"  • {ui.Colors.YELLOW}{f}{ui.Colors.RESET}")
    elif cat_choice == "4":
        term = ui.get_choice("Enter keyword to search").lower()
        matched = [f for f in features if term in f.lower()]
        ui.info(f"Found {len(matched)} match(es) for '{term}':")
        for m in matched:
            print(f"  • {m}")
    else:
        for f in sorted(features):
            print(f"  • {f}")


# ─── 7. Init Properties & Daemons ─────────────────────────────────────────────

def show_init_properties():
    """Inspect init daemon service states and boot properties."""
    if not ensure_device():
        return

    ui.header("Init System & Daemon Service Statuses")

    props = adb.get_all_props()
    if not props:
        ui.error("Failed to read system properties.")
        return

    # Extract init.svc.* properties
    init_services = {}
    boot_props = {}
    crypto_props = {}

    for k, v in props.items():
        if k.startswith("init.svc."):
            svc_name = k[len("init.svc."):]
            init_services[svc_name] = v
        elif k.startswith("ro.boot."):
            boot_props[k] = v
        elif k.startswith("ro.crypto."):
            crypto_props[k] = v

    if init_services:
        running_cnt = sum(1 for v in init_services.values() if v == "running")
        stopped_cnt = sum(1 for v in init_services.values() if v == "stopped")
        ui.success(f"Init Daemons: {len(init_services)} total ({running_cnt} running, {stopped_cnt} stopped)")

        rows = []
        for svc, state in sorted(init_services.items()):
            color_state = f"{ui.Colors.GREEN}{state}{ui.Colors.RESET}" if state == "running" else f"{ui.Colors.DIM}{state}{ui.Colors.RESET}"
            rows.append((svc, color_state))

        # Show first 25
        ui.print_table(rows[:25], headers=("Daemon Service", "State"))
        if len(rows) > 25:
            ui.info(f"Showing 25 of {len(rows)} init services.")

    if boot_props:
        print(f"\n  {ui.Colors.BOLD}Boot Parameters (ro.boot.*):{ui.Colors.RESET}\n")
        ui.print_kv(boot_props, indent=4)


# ─── 8. System Uptime & CPU Load ──────────────────────────────────────────────

def show_system_uptime():
    """Display detailed system uptime, idle time, and load averages."""
    if not ensure_device():
        return

    ui.header("System Uptime & Processor Load")

    ok1, uptime_raw = adb.run_shell("uptime")
    ok2, proc_uptime = adb.run_shell("cat /proc/uptime")
    ok3, loadavg = adb.run_shell("cat /proc/loadavg")

    if ok2 and proc_uptime:
        parts = proc_uptime.strip().split()
        if len(parts) >= 2:
            try:
                up_sec = float(parts[0])
                idle_sec = float(parts[1])
                up_formatted = _format_seconds(up_sec)
                idle_formatted = _format_seconds(idle_sec)
                # Calculate active vs idle percent
                uptime_data = {
                    "System Uptime": f"{ui.Colors.GREEN}{up_formatted}{ui.Colors.RESET} ({up_sec:.1f} seconds)",
                    "CPU Idle Time (all cores)": f"{idle_formatted} ({idle_sec:.1f} seconds)",
                }
                ui.print_kv(uptime_data, indent=4)
            except ValueError:
                pass

    if ok3 and loadavg:
        parts = loadavg.strip().split()
        if len(parts) >= 5:
            load_data = {
                "1-min Load Average": parts[0],
                "5-min Load Average": parts[1],
                "15-min Load Average": parts[2],
                "Active / Total Threads": parts[3],
                "Last Created PID": parts[4],
            }
            print(f"\n  {ui.Colors.BOLD}CPU Load Averages (/proc/loadavg):{ui.Colors.RESET}\n")
            ui.print_kv(load_data, indent=4)

    if ok1 and uptime_raw:
        print(f"\n  {ui.Colors.DIM}Raw uptime: {uptime_raw.strip()}{ui.Colors.RESET}")


# ─── 9. Available Shared Libraries ────────────────────────────────────────────

def show_shared_libraries():
    """List all shared Java and native runtime libraries available to apps."""
    if not ensure_device():
        return

    ui.header("Available Shared Libraries (pm list libraries)")

    ok, output = adb.run_shell("pm list libraries")
    if not ok or not output.strip():
        ui.error("Failed to query shared libraries.")
        return

    libs = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("data:") or line.startswith("library:"):
            lib_name = line.split(":", 1)[1].strip()
            if lib_name:
                libs.append(lib_name)
        elif line:
            libs.append(line)

    ui.success(f"Found {len(libs)} shared runtime libraries:")

    # Sort and group by vendor/framework
    android_libs = [l for l in libs if l.startswith("android.") or l.startswith("androidx.")]
    google_libs = [l for l in libs if "google" in l.lower() or "gms" in l.lower()]
    oem_libs = [l for l in libs if l not in android_libs and l not in google_libs]

    rows = []
    for i, lib in enumerate(sorted(libs), 1):
        category = "Android Core" if lib in android_libs else ("Google Play / GMS" if lib in google_libs else "OEM / Vendor")
        rows.append((f"  {i}", lib, category))

    ui.print_table(rows, headers=("  #", "Library Name", "Provider"))


# ─── 10. List Users & Profiles ────────────────────────────────────────────────

def show_user_accounts():
    """Inspect multi-user profiles, work accounts, and user management."""
    if not ensure_device():
        return

    ui.header("User Profiles & Accounts (pm list users)")

    ok_users, users_out = adb.run_shell("pm list users")
    ok_dump, dump_out = adb.run_shell("dumpsys user")

    if ok_users and users_out:
        print(f"\n  {ui.Colors.BOLD}Configured User Profiles:{ui.Colors.RESET}\n")
        lines = users_out.splitlines()
        user_rows = []
        for line in lines:
            line = line.strip()
            # Format: UserInfo{0:Owner:13} running
            # or UserInfo{10:Work profile:30} running
            if line.startswith("UserInfo{"):
                inside = line[len("UserInfo{"):line.find("}")]
                running_status = line[line.find("}") + 1:].strip() if "}" in line else "unknown"
                parts = inside.split(":")
                if len(parts) >= 3:
                    u_id, u_name, u_flags = parts[0], parts[1], parts[2]
                    user_rows.append((u_id, u_name, u_flags, running_status if running_status else "stopped"))

        if user_rows:
            headers = ("User ID", "User / Profile Name", "Flags (Bitmask)", "State")
            ui.print_table(user_rows, headers=headers)
        else:
            for l in lines:
                print(f"  {l}")

    # Check sync accounts count
    ok_acc, acc_out = adb.run_shell("dumpsys account")
    if ok_acc and acc_out:
        acc_lines = [l.strip() for l in acc_out.splitlines() if "Account {" in l or "name=" in l]
        if acc_lines:
            print(f"\n  {ui.Colors.BOLD}Device Sync Accounts ({len(acc_lines)} found):{ui.Colors.RESET}")
            for a in acc_lines[:10]:
                print(f"  • {a}")


# ─── 11. List Input Devices ───────────────────────────────────────────────────

def show_input_devices():
    """Inspect hardware input devices (touchscreen, hardware keys, sensors)."""
    if not ensure_device():
        return

    ui.header("Input Hardware Devices & Sensors")

    ok, output = adb.run_shell("cat /proc/bus/input/devices")
    if not ok or not output.strip():
        ok, output = adb.run_shell("getevent -S")

    if not ok or not output.strip():
        ui.error("Unable to read input devices.")
        return

    # Parse /proc/bus/input/devices blocks
    # N: Name="fts_ts"
    # H: Handlers=event2
    devices = []
    current_dev = {}

    for line in output.splitlines():
        line = line.strip()
        if not line:
            if current_dev:
                devices.append(current_dev)
                current_dev = {}
            continue

        if line.startswith("N: Name="):
            name = line.split("Name=", 1)[1].strip('"')
            current_dev["name"] = name
        elif line.startswith("H: Handlers="):
            handlers = line.split("Handlers=", 1)[1].strip()
            current_dev["handlers"] = handlers
        elif line.startswith("P: Phys="):
            current_dev["phys"] = line.split("Phys=", 1)[1].strip()
        elif line.startswith("I: Bus="):
            current_dev["bus"] = line[3:]

    if current_dev:
        devices.append(current_dev)

    if devices:
        ui.success(f"Detected {len(devices)} input device interface(s):")
        rows = []
        for i, d in enumerate(devices, 1):
            rows.append((
                f"  {i}",
                d.get("name", "Unknown"),
                d.get("handlers", "—"),
                d.get("phys", "—")
            ))
        ui.print_table(rows, headers=("  #", "Device Name", "Event Handler", "Physical Path"))
    else:
        ui.info("Raw Input Devices Output:")
        for line in output.splitlines()[:30]:
            print(f"  {line}")


# ─── 12. View Boot Completed Status & Boot Times ──────────────────────────────

def show_boot_completed_status():
    """Inspect boot completion state and system initialization milestones."""
    if not ensure_device():
        return

    ui.header("System Boot Milestones & Completion Timing")

    boot_completed = adb.getprop("sys.boot_completed")
    dev_bootcomplete = adb.getprop("dev.bootcomplete")
    first_boot = adb.getprop("ro.runtime.firstboot")

    is_complete = boot_completed == "1" or dev_bootcomplete == "1"
    status_str = f"{ui.Colors.GREEN}YES (Boot Sequence Complete){ui.Colors.RESET}" if is_complete else f"{ui.Colors.YELLOW}NO (Device Still Booting){ui.Colors.RESET}"

    first_boot_dt = "Unknown"
    if first_boot and first_boot.isdigit():
        try:
            ts = int(first_boot) / 1000 if len(first_boot) > 10 else int(first_boot)
            first_boot_dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            first_boot_dt = first_boot

    summary_data = {
        "Boot Completed (sys.boot_completed)": status_str,
        "Framework Ready (dev.bootcomplete)": "1" if dev_bootcomplete == "1" else ("0" if dev_bootcomplete else "N/A"),
        "First Boot Timestamp": first_boot_dt,
    }
    ui.print_kv(summary_data, indent=4)

    # Check ro.boottime.* properties for breakdown
    props = adb.get_all_props()
    boottimes = {k[len("ro.boottime."):]: v for k, v in props.items() if k.startswith("ro.boottime.")}

    if boottimes:
        print(f"\n  {ui.Colors.BOLD}Subsystem Boot Latencies (nanoseconds):{ui.Colors.RESET}\n")
        rows = []
        for k, v in sorted(boottimes.items()):
            try:
                ms = float(v) / 1_000_000
                rows.append((k, f"{ms:,.2f} ms"))
            except ValueError:
                rows.append((k, v))
        ui.print_table(rows[:20], headers=("Subsystem / Stage", "Boot Duration"))


# ─── 13. CPU & Memory Architecture Summary ───────────────────────────────────

def show_cpu_memory_summary():
    """Inspect CPU core topology and system RAM / ZRAM allocation."""
    if not ensure_device():
        return

    ui.header("CPU Topology & Memory Architecture Summary")

    ok_cpu, cpu_out = adb.run_shell("cat /proc/cpuinfo")
    ok_mem, mem_out = adb.run_shell("cat /proc/meminfo")

    if ok_cpu and cpu_out:
        processors = [l for l in cpu_out.splitlines() if l.strip().startswith("processor")]
        hardware = [l.split(":", 1)[1].strip() for l in cpu_out.splitlines() if l.strip().startswith("Hardware")]
        cpu_model = hardware[0] if hardware else adb.getprop("ro.soc.model") or adb.getprop("ro.board.platform")

        cpu_data = {
            "Total CPU Cores": str(len(processors)) if processors else "Unknown",
            "SoC / Platform": cpu_model if cpu_model else "Unknown",
            "Architecture": adb.getprop("ro.product.cpu.abi"),
        }
        print(f"\n  {ui.Colors.BOLD}Processor Details:{ui.Colors.RESET}\n")
        ui.print_kv(cpu_data, indent=4)

    if ok_mem and mem_out:
        mem_dict = {}
        for line in mem_out.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                mem_dict[k.strip()] = v.strip()

        print(f"\n  {ui.Colors.BOLD}Memory Allocations (/proc/meminfo):{ui.Colors.RESET}\n")
        keys = ["MemTotal", "MemFree", "MemAvailable", "Buffers", "Cached", "SwapTotal", "SwapFree", "ZRamTotal"]
        show_mem = {k: mem_dict[k] for k in keys if k in mem_dict}
        ui.print_kv(show_mem, indent=4)


# ─── 14. Export Full System Report ────────────────────────────────────────────

def export_full_system_report():
    """Generate and save a comprehensive system internals report to a file."""
    if not ensure_device():
        return

    ui.header("Generating Comprehensive System Report...")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"system_report_{adb.serial}_{ts}.txt"

    report_lines = [
        "=" * 70,
        f"  DROIDCOMMANDER — SYSTEM INTERNALS REPORT",
        f"  Device Serial : {adb.serial}",
        f"  Device Model  : {adb.getprop('ro.product.model')} ({adb.getprop('ro.product.manufacturer')})",
        f"  Android Ver   : {adb.getprop('ro.build.version.release')} (SDK {adb.getprop('ro.build.version.sdk')})",
        f"  Generated On  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 70,
        "",
    ]

    sections = [
        ("KERNEL & OS RELEASE", "cat /proc/version"),
        ("SELINUX STATUS", "getenforce"),
        ("SYSTEM UPTIME & LOAD", "cat /proc/loadavg"),
        ("PARTITIONS", "cat /proc/partitions"),
        ("STORAGE MOUNTS", "df -h"),
        ("MEMORY INFO", "cat /proc/meminfo"),
        ("CPU INFO", "cat /proc/cpuinfo"),
        ("SYSTEM FEATURES", "pm list features"),
        ("SHARED LIBRARIES", "pm list libraries"),
        ("CONFIGURED USERS", "pm list users"),
    ]

    for title, cmd in sections:
        report_lines.append("-" * 60)
        report_lines.append(f"  SECTION: {title} (cmd: {cmd})")
        report_lines.append("-" * 60)
        ok, out = adb.run_shell(cmd)
        report_lines.append(out if ok else f"Command failed: {out}")
        report_lines.append("")

    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))
        ui.success(f"Full system report written to: {os.path.abspath(filename)}")
    except Exception as e:
        ui.error(f"Failed to write report file: {e}")


# ─── Main Menu Loop ───────────────────────────────────────────────────────────

def system_info_menu():
    """System information interactive submenu."""
    options = [
        "Kernel Version & Architecture",
        "SELinux Enforcement Status",
        "Partition Layout (/proc/partitions)",
        "Mount Points & Filesystems",
        "Running System Services (service list)",
        "System Features (pm list features)",
        "Init Daemons & Boot Properties",
        "System Uptime & Processor Load",
        "Available Shared Libraries (pm list libraries)",
        "List User Profiles & Accounts",
        "List Input Hardware Devices",
        "Boot Completed Status & Timing",
        "CPU Topology & Memory Architecture",
        "Export Full System Diagnostics Report",
    ]

    while True:
        ui.clear()
        ui.print_banner()
        ui.print_menu("🖥️ System Internals & Diagnostics", options, columns=2)

        choice = ui.get_choice()

        if choice == "0":
            break
        elif choice == "1":
            show_kernel_version()
        elif choice == "2":
            show_selinux_status()
        elif choice == "3":
            show_partition_layout()
        elif choice == "4":
            show_mount_points()
        elif choice == "5":
            show_running_services()
        elif choice == "6":
            show_system_features()
        elif choice == "7":
            show_init_properties()
        elif choice == "8":
            show_system_uptime()
        elif choice == "9":
            show_shared_libraries()
        elif choice == "10":
            show_user_accounts()
        elif choice == "11":
            show_input_devices()
        elif choice == "12":
            show_boot_completed_status()
        elif choice == "13":
            show_cpu_memory_summary()
        elif choice == "14":
            export_full_system_report()
        else:
            ui.error("Invalid option. Please choose a valid number.")

        ui.pause()
