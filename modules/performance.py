"""
modules/performance.py — Advanced Performance Monitoring module for DroidCommander.

Provides deep hardware inspection, real-time CPU & memory metrics, process monitoring,
storage breakdown, battery diagnostics, GPU profiling, network telemetry, and frame rendering stats.
"""

from typing import Optional, Any
import re
import time
from datetime import datetime, timedelta

from core.adb import adb
from core import ui
from core.device import ensure_device


# ─── Format Utilities ─────────────────────────────────────────────────────────

def _format_bytes(num_bytes: int) -> str:
    """Format integer bytes into a human-readable string (B, KB, MB, GB)."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.2f} KB"
    elif num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"


def _format_kb(kb: int) -> str:
    """Format integer kilobytes into a human-readable string."""
    return _format_bytes(kb * 1024)


def _render_bar(percent: float, width: int = 24) -> str:
    """Render an ANSI colored percentage progress bar."""
    pct = max(0.0, min(100.0, percent))
    filled = int(width * (pct / 100.0))
    empty = width - filled

    if pct < 60:
        color = ui.Colors.GREEN
    elif pct < 85:
        color = ui.Colors.YELLOW
    else:
        color = ui.Colors.RED

    bar = f"{color}{'█' * filled}{ui.Colors.DIM}{'░' * empty}{ui.Colors.RESET}"
    return f"[{bar}] {pct:5.1f}%"


def _get_focused_package() -> Optional[str]:
    """Return the package name of the currently focused foreground application."""
    ok, out = adb.run(["shell", "dumpsys", "window"])
    if ok and out:
        for line in out.splitlines():
            if "mCurrentFocus" in line or "mFocusedApp" in line:
                match = re.search(r"([a-zA-Z0-9_\.]+\/[a-zA-Z0-9_\.\$]+)", line)
                if match:
                    return match.group(1).split("/")[0]
    return None


# ─── 1. CPU Info ──────────────────────────────────────────────────────────────

def show_cpu_info():
    """Display comprehensive CPU architecture, cores, frequencies, and governors."""
    if not ensure_device():
        return

    ui.header("CPU Architecture & Real-Time Frequencies")
    print()

    # Query system properties
    abi = adb.getprop("ro.product.cpu.abi")
    abilist = adb.getprop("ro.product.cpu.abilist")
    platform = adb.getprop("ro.board.platform")
    soc_model = adb.getprop("ro.soc.model")
    hardware = adb.getprop("ro.hardware")

    # Read /proc/cpuinfo
    ok_cpu, cpuinfo_out = adb.run(["shell", "cat", "/proc/cpuinfo"], timeout=10)
    processor_name = "Unknown ARM Processor"
    hardware_name = hardware or platform or "Unknown SOC"
    core_count_cpuinfo = 0

    if ok_cpu and cpuinfo_out:
        for line in cpuinfo_out.splitlines():
            line_str = line.strip()
            if line_str.startswith("Processor") or line_str.startswith("model name"):
                processor_name = line_str.split(":", 1)[-1].strip()
            elif line_str.startswith("Hardware"):
                hardware_name = line_str.split(":", 1)[-1].strip()
            elif line_str.startswith("processor"):
                core_count_cpuinfo += 1

    # Check online cores from sysfs
    ok_present, present_out = adb.run(["shell", "cat", "/sys/devices/system/cpu/present"])
    ok_online, online_out = adb.run(["shell", "cat", "/sys/devices/system/cpu/online"])

    present_cores = present_out.strip() if ok_present else f"0-{core_count_cpuinfo - 1 if core_count_cpuinfo > 0 else 0}"
    online_cores = online_out.strip() if ok_online else "Unknown"

    ui.print_kv({
        "SoC / Platform": f"{hardware_name} ({soc_model})" if soc_model else hardware_name,
        "Processor Model": processor_name,
        "Primary ABI": abi,
        "Supported ABIs": abilist,
        "Present Cores Range": present_cores,
        "Online Cores Range": online_cores,
    })
    print()

    ui.header("Per-Core Frequency & Governor Telemetry:")
    print()

    # Enumerate CPU cores
    core_rows = []
    # Try up to 16 cores
    for i in range(16):
        cpu_path = f"/sys/devices/system/cpu/cpu{i}"
        ok_check, _ = adb.run(["shell", "ls", "-d", cpu_path])
        if not ok_check:
            if i > 0:
                break
            continue

        # Check online status
        ok_on, on_val = adb.run(["shell", "cat", f"{cpu_path}/online"])
        is_online = on_val.strip() == "1" if ok_on and on_val.strip() in ("0", "1") else (True if i == 0 else True)

        if not is_online:
            core_rows.append((f"CPU {i}", "OFFLINE", "—", "—", "—", "offline"))
            continue

        # Read frequencies
        ok_cur, cur_f = adb.run(["shell", "cat", f"{cpu_path}/cpufreq/scaling_cur_freq"])
        ok_min, min_f = adb.run(["shell", "cat", f"{cpu_path}/cpufreq/scaling_min_freq"])
        ok_max, max_f = adb.run(["shell", "cat", f"{cpu_path}/cpufreq/scaling_max_freq"])
        ok_gov, gov_v = adb.run(["shell", "cat", f"{cpu_path}/cpufreq/scaling_governor"])

        cur_str = f"{int(cur_f.strip()) // 1000} MHz" if ok_cur and cur_f.strip().isdigit() else "N/A"
        min_str = f"{int(min_f.strip()) // 1000} MHz" if ok_min and min_f.strip().isdigit() else "N/A"
        max_str = f"{int(max_f.strip()) // 1000} MHz" if ok_max and max_f.strip().isdigit() else "N/A"
        gov_str = gov_v.strip() if ok_gov and gov_v.strip() else "N/A"

        core_rows.append((f"CPU {i}", "ONLINE", cur_str, min_str, max_str, gov_str))

    if core_rows:
        headers = ("Core", "Status", "Current Freq", "Min Freq", "Max Freq", "Governor")
        ui.print_table(core_rows, headers)
    else:
        ui.info("Per-core sysfs cpufreq access is restricted on this device/ROM.")


# ─── 2. Memory Info ───────────────────────────────────────────────────────────

def show_memory_info():
    """Parse /proc/meminfo to display detailed RAM, Cache, Buffers, and ZRAM telemetry."""
    if not ensure_device():
        return

    ui.header("System RAM & Memory Breakdown")
    print()

    ok, out = adb.run(["shell", "cat", "/proc/meminfo"], timeout=10)
    if not ok or not out:
        ui.error("Failed to read /proc/meminfo")
        return

    mem_data = {}
    for line in out.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            v_clean = v.strip().split()[0]
            if v_clean.isdigit():
                mem_data[k.strip()] = int(v_clean)

    total_ram_kb = mem_data.get("MemTotal", 0)
    free_ram_kb = mem_data.get("MemFree", 0)
    avail_ram_kb = mem_data.get("MemAvailable", free_ram_kb)
    buffers_kb = mem_data.get("Buffers", 0)
    cached_kb = mem_data.get("Cached", 0)
    active_kb = mem_data.get("Active", 0)
    inactive_kb = mem_data.get("Inactive", 0)
    dirty_kb = mem_data.get("Dirty", 0)
    shmem_kb = mem_data.get("Shmem", 0)
    slab_kb = mem_data.get("Slab", 0)

    swap_total_kb = mem_data.get("SwapTotal", 0)
    swap_free_kb = mem_data.get("SwapFree", 0)
    swap_used_kb = swap_total_kb - swap_free_kb

    used_ram_kb = total_ram_kb - avail_ram_kb
    ram_pct = (used_ram_kb / total_ram_kb * 100) if total_ram_kb > 0 else 0
    swap_pct = (swap_used_kb / swap_total_kb * 100) if swap_total_kb > 0 else 0

    print(f"  {ui.Colors.BOLD}RAM Usage:{ui.Colors.RESET}  {_render_bar(ram_pct)}  ({_format_kb(used_ram_kb)} / {_format_kb(total_ram_kb)})")
    if swap_total_kb > 0:
        print(f"  {ui.Colors.BOLD}ZRAM/Swap:{ui.Colors.RESET}  {_render_bar(swap_pct)}  ({_format_kb(swap_used_kb)} / {_format_kb(swap_total_kb)})")
    print()

    ui.print_kv({
        "Total Physical RAM": f"{_format_kb(total_ram_kb)} ({total_ram_kb:,} KB)",
        "Used RAM": f"{_format_kb(used_ram_kb)} ({ram_pct:.1f}%)",
        "Available RAM": f"{_format_kb(avail_ram_kb)} ({100 - ram_pct:.1f}%)",
        "Free RAM (Uncached)": f"{_format_kb(free_ram_kb)}",
        "Page Cache": f"{_format_kb(cached_kb)}",
        "Kernel Buffers": f"{_format_kb(buffers_kb)}",
        "Active Memory": f"{_format_kb(active_kb)}",
        "Inactive Memory": f"{_format_kb(inactive_kb)}",
        "Dirty Memory (Pending Write)": f"{_format_kb(dirty_kb)}",
        "Shared Memory (Shmem)": f"{_format_kb(shmem_kb)}",
        "Kernel Slab": f"{_format_kb(slab_kb)}",
        "Total Swap / ZRAM": f"{_format_kb(swap_total_kb)}",
        "Used Swap / ZRAM": f"{_format_kb(swap_used_kb)} ({swap_pct:.1f}%)",
        "Free Swap / ZRAM": f"{_format_kb(swap_free_kb)}",
    })


# ─── 3. Storage Info ──────────────────────────────────────────────────────────

def show_storage_info():
    """Display storage partition usage (df -h) and dumpsys diskstats summary."""
    if not ensure_device():
        return

    ui.header("Storage Partitions & Disk Usage")
    print()

    ok, out = adb.run(["shell", "df", "-h"], timeout=10)
    if not ok or not out:
        ui.error("Failed to execute df -h")
        return

    rows = []
    # Filter for meaningful filesystems
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 6:
            fs, size, used, avail, use_pct, mount = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
            # Exclude noisy apex / tmpfs mounts if they are overly verbose, but keep primary mounts
            if mount in ("/", "/system", "/vendor", "/product", "/data", "/storage/emulated", "/sdcard", "/metadata", "/cache") or "/storage/" in mount or mount.startswith("/data"):
                rows.append((fs, mount, size, used, avail, use_pct))
            elif not mount.startswith("/apex") and not mount.startswith("/mnt/runtime"):
                rows.append((fs, mount, size, used, avail, use_pct))

    if rows:
        headers = ("Filesystem", "Mounted On", "Size", "Used", "Free", "Use%")
        ui.print_table(rows, headers)
    else:
        # Fallback to printing all lines
        for line in out.splitlines()[:25]:
            print(f"  {line}")

    print()
    ui.header("High-Level Disk Stats (dumpsys diskstats):")
    ok_ds, ds_out = adb.run(["shell", "dumpsys", "diskstats"], timeout=10)
    if ok_ds and ds_out:
        for line in ds_out.splitlines()[:12]:
            clean_l = line.strip()
            if clean_l and not clean_l.startswith("Package Names:"):
                print(f"  {ui.Colors.CYAN}•{ui.Colors.RESET} {clean_l}")


# ─── 4. Battery Stats Detailed ────────────────────────────────────────────────

def show_battery_stats():
    """Display rich battery telemetry, health, temperature, voltage, and charging state."""
    if not ensure_device():
        return

    ui.header("Battery Diagnostics & Telemetry")
    print()

    ok, out = adb.run(["shell", "dumpsys", "battery"])
    if not ok or not out:
        ui.error("Failed to query dumpsys battery")
        return

    battery_props: dict[str, str] = {}
    for line in out.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            battery_props[k.strip()] = v.strip()

    status_map = {
        "1": "Unknown",
        "2": "Charging ⚡",
        "3": "Discharging 🔋",
        "4": "Not Charging",
        "5": "Full 🟢"
    }

    health_map = {
        "1": "Unknown",
        "2": "Good 🟢",
        "3": "Overheat 🔥",
        "4": "Dead 💀",
        "5": "Over Voltage ⚠️",
        "6": "Unspecified Failure ❌",
        "7": "Cold ❄️"
    }

    level_val = int(battery_props.get("level", "0"))
    scale_val = int(battery_props.get("scale", "100"))
    pct = (level_val / scale_val * 100) if scale_val > 0 else level_val

    temp_raw = int(battery_props.get("temperature", "0"))
    temp_c = temp_raw / 10.0
    temp_f = (temp_c * 9 / 5) + 32

    volt_raw = int(battery_props.get("voltage", "0"))
    volt_v = volt_raw / 1000.0

    ac_pwr = battery_props.get("AC powered", "false").lower() == "true"
    usb_pwr = battery_props.get("USB powered", "false").lower() == "true"
    wl_pwr = battery_props.get("Wireless powered", "false").lower() == "true"

    pwr_src = []
    if ac_pwr:
        pwr_src.append("AC Wall Charger")
    if usb_pwr:
        pwr_src.append("USB Connection")
    if wl_pwr:
        pwr_src.append("Wireless Dock")
    pwr_src_str = ", ".join(pwr_src) if pwr_src else "Battery Only (No External Power)"

    print(f"  {ui.Colors.BOLD}Battery Level:{ui.Colors.RESET}  {_render_bar(pct)}  ({level_val}%)")
    print()

    charge_counter = battery_props.get("Charge counter", "")
    cc_str = f"{int(charge_counter) // 1000} mAh ({charge_counter} µAh)" if charge_counter.isdigit() else "N/A"

    ui.print_kv({
        "Status": status_map.get(battery_props.get("status", ""), battery_props.get("status", "Unknown")),
        "Health": health_map.get(battery_props.get("health", ""), battery_props.get("health", "Unknown")),
        "Power Source": pwr_src_str,
        "Voltage": f"{volt_v:.3f} V ({volt_raw} mV)",
        "Temperature": f"{temp_c:.1f} °C / {temp_f:.1f} °F",
        "Technology": battery_props.get("technology", "Li-ion / Li-poly"),
        "Charge Counter": cc_str,
        "Max Charging Current": f"{battery_props.get('Max charging current', 'N/A')} µA",
        "Max Charging Voltage": f"{battery_props.get('Max charging voltage', 'N/A')} µV",
    })


# ─── 5. GPU Info ──────────────────────────────────────────────────────────────

def show_gpu_info():
    """Display GPU renderer, vendor, driver version, and OpenGL ES / Vulkan properties."""
    if not ensure_device():
        return

    ui.header("GPU & Graphics Subsystem Details")
    print()

    # Query SurfaceFlinger for GLES details
    ok_sf, sf_out = adb.run(["shell", "dumpsys", "SurfaceFlinger"], timeout=10)
    gles_vendor = "Unknown"
    gles_renderer = "Unknown"
    gles_version = "Unknown"

    if ok_sf and sf_out:
        for line in sf_out.splitlines():
            line_str = line.strip()
            if line_str.startswith("GLES:") or "GLES:" in line_str:
                # e.g., GLES: Qualcomm, Adreno (TM) 730, OpenGL ES 3.2 V@0615.0
                parts = line_str.split("GLES:")[-1].split(",")
                if len(parts) >= 1:
                    gles_vendor = parts[0].strip()
                if len(parts) >= 2:
                    gles_renderer = parts[1].strip()
                if len(parts) >= 3:
                    gles_version = ", ".join(parts[2:]).strip()
                break

    # Properties
    egl_hw = adb.getprop("ro.hardware.egl")
    gles_prop = adb.getprop("ro.opengles.version")
    soc_mfg = adb.getprop("ro.soc.manufacturer")
    soc_model = adb.getprop("ro.soc.model")

    # Format OpenGL hex version
    gles_formatted = "Unknown"
    if gles_prop and gles_prop.isdigit():
        val = int(gles_prop)
        major = val >> 16
        minor = val & 0xFFFF
        gles_formatted = f"OpenGL ES {major}.{minor} (0x{val:08x})"

    # Query dumpsys gpu if available (Android 11+)
    driver_version = "N/A"
    ok_gpu, gpu_out = adb.run(["shell", "dumpsys", "gpu"], timeout=5)
    if ok_gpu and gpu_out:
        for line in gpu_out.splitlines():
            if "driverVersion" in line or "driverPackageName" in line:
                driver_version = line.strip()
                break

    # Check for Adreno sysfs clocks
    gpu_freq_str = "N/A"
    ok_gf, gf_out = adb.run(["shell", "cat", "/sys/class/kgsl/kgsl-3d0/gpuclk"])
    if ok_gf and gf_out.strip().isdigit():
        gpu_freq_str = f"{int(gf_out.strip()) // 1000000} MHz"

    ui.print_kv({
        "GPU Renderer": gles_renderer,
        "GPU Vendor": gles_vendor,
        "OpenGL ES Version": gles_version if gles_version != "Unknown" else gles_formatted,
        "EGL Hardware Driver": egl_hw if egl_hw else "Default Android EGL",
        "SoC Chipset": f"{soc_mfg} {soc_model}".strip() if soc_mfg or soc_model else "Generic ARM",
        "Current GPU Clock": gpu_freq_str,
        "Driver Package Info": driver_version,
    })
    print()

    ui.info("Tip: For real-time frame drop profiling, see 'Frame rendering stats'.")


# ─── 6. Running Processes (Top 25) ────────────────────────────────────────────

def show_running_processes():
    """Display top 25 processes sorted by Memory (RSS) or CPU."""
    if not ensure_device():
        return

    ui.header("Top 25 Running Processes")
    print()
    print("  Sort by:")
    print(f"    {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Memory Consumption (RSS)")
    print(f"    {ui.Colors.YELLOW}[2]{ui.Colors.RESET} CPU Usage (%)")
    print()

    sort_choice = ui.get_choice("Select sort order [1]")
    sort_flag = "-rss" if sort_choice in ("", "1") else "-%cpu"

    ui.info(f"Fetching process snapshot (sorted by {sort_flag})...")
    ok, out = adb.run(["shell", "ps", "-A", "-o", "PID,USER,%CPU,%MEM,VSZ,RSS,NAME", f"--sort={sort_flag}"], timeout=15)

    if not ok or not out:
        # Fallback to standard ps -A
        ok, out = adb.run(["shell", "ps", "-A"], timeout=10)
        if not ok or not out:
            ui.error("Failed to query process list.")
            return

    lines = [l for l in out.splitlines() if l.strip()]
    if len(lines) <= 1:
        ui.warning("No processes returned.")
        return

    table_rows = []
    # Skip header
    for line in lines[1:26]:
        parts = line.split(None, 6)
        if len(parts) >= 7:
            pid, user, cpu, mem, vsz, rss, name = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], parts[6]
            rss_formatted = _format_kb(int(rss)) if rss.isdigit() else rss
            vsz_formatted = _format_kb(int(vsz)) if vsz.isdigit() else vsz
            # Truncate long process names if needed
            name_trunc = name if len(name) <= 35 else name[:32] + "..."
            table_rows.append((pid, user, f"{cpu}%", f"{mem}%", rss_formatted, vsz_formatted, name_trunc))
        elif len(parts) >= 6:
            pid, user, vsz, rss, wchan, addr, name = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], parts[-1]
            rss_formatted = _format_kb(int(rss)) if rss.isdigit() else rss
            table_rows.append((pid, user, "—", "—", rss_formatted, vsz, name[:35]))

    if table_rows:
        headers = ("PID", "User", "CPU%", "MEM%", "RSS (Phys)", "VSZ (Virt)", "Process Name")
        ui.print_table(table_rows, headers)
    else:
        for line in lines[:25]:
            print(f"  {line}")


# ─── 7. App-Specific Memory Usage ─────────────────────────────────────────────

def show_app_memory_usage():
    """Deep memory breakdown of a specific package via dumpsys meminfo."""
    if not ensure_device():
        return

    ui.header("App-Specific Memory Usage (dumpsys meminfo)")
    print()

    focused = _get_focused_package()
    prompt = f"Enter package name [{focused}]" if focused else "Enter package name"
    pkg_input = ui.get_choice(prompt)
    package = pkg_input if pkg_input else (focused or "")

    if not package:
        ui.error("Package name is required.")
        return

    ui.info(f"Querying detailed meminfo for '{package}'...")
    ok, out = adb.run(["shell", "dumpsys", "meminfo", package], timeout=20)
    if not ok or not out:
        ui.error(f"Failed to get memory info for {package}: {out}")
        return

    print()
    ui.header(f"Memory Allocation Breakdown: {package}")
    print()

    # Parse and display memory sections
    summary_lines = []
    objects_lines = []
    capture_summary = False
    capture_objects = False

    for line in out.splitlines():
        line_s = line.strip()
        if "App Summary" in line or "** MEMINFO in pid" in line:
            capture_summary = True
        elif "Objects" in line:
            capture_objects = True
        elif "SQL" in line or "DATABASES" in line or "Asset Allocations" in line:
            capture_summary = False
            capture_objects = False

        if capture_summary and line_s:
            summary_lines.append(line)
        elif capture_objects and line_s:
            objects_lines.append(line)

    if summary_lines:
        for line in summary_lines[:25]:
            if "TOTAL" in line or "TOTAL PSS:" in line:
                print(f"  {ui.Colors.BOLD}{ui.Colors.GREEN}{line}{ui.Colors.RESET}")
            elif "Java Heap:" in line or "Native Heap:" in line or "Code:" in line or "Stack:" in line or "Graphics:" in line:
                print(f"  {ui.Colors.CYAN}{line}{ui.Colors.RESET}")
            else:
                print(f"  {line}")
    else:
        # If sectioning did not match, print first 30 lines of raw output
        for line in out.splitlines()[:30]:
            print(f"  {line}")

    if objects_lines:
        print()
        ui.header("Active Object Allocations:")
        for line in objects_lines[:10]:
            print(f"  {line}")


# ─── 8. CPU Usage By App ──────────────────────────────────────────────────────

def show_cpu_usage_by_app():
    """Display CPU usage breakdown by app and system threads via dumpsys cpuinfo."""
    if not ensure_device():
        return

    ui.header("Real-Time CPU Load & Per-App Utilization")
    print()
    ui.info("Sampling CPU utilization (dumpsys cpuinfo)...")

    ok, out = adb.run(["shell", "dumpsys", "cpuinfo"], timeout=15)
    if not ok or not out:
        ui.error("Failed to query CPU info.")
        return

    lines = [l for l in out.splitlines() if l.strip()]
    if not lines:
        ui.warning("No CPU information returned.")
        return

    # Look for total line (e.g., 23% TOTAL: 12% user + 8% kernel + 3% iowait)
    total_line = lines[-1] if "TOTAL" in lines[-1] else (lines[0] if "TOTAL" in lines[0] else "")
    if total_line:
        print(f"  {ui.Colors.BOLD}{ui.Colors.YELLOW}Overall Load:{ui.Colors.RESET} {total_line.strip()}")
        print()

    table_rows = []
    # Parse individual process lines (e.g. 15% 1234/com.example.app: 10% user + 5% kernel)
    for line in lines:
        line_clean = line.strip()
        if "TOTAL:" in line_clean or line_clean.startswith("Load:"):
            continue

        match = re.search(r"([\d\.]+)%\s+(\d+)\/([^:]+):\s+(.*)", line_clean)
        if match:
            total_pct = f"{match.group(1)}%"
            pid = match.group(2)
            name = match.group(3)
            breakdown = match.group(4)
            table_rows.append((pid, total_pct, name[:35], breakdown))
        elif "%" in line_clean:
            parts = line_clean.split(None, 2)
            if len(parts) >= 2:
                table_rows.append(("-", parts[0], parts[1][:35], parts[2] if len(parts) > 2 else ""))

    if table_rows:
        headers = ("PID", "CPU%", "Process / Package", "Load Breakdown (User / Kernel)")
        ui.print_table(table_rows[:20], headers)
    else:
        for line in lines[:25]:
            print(f"  {line}")


# ─── 9. Disk I/O Stats ────────────────────────────────────────────────────────

def show_disk_io_stats():
    """Read /proc/diskstats and display read/write throughput per block device."""
    if not ensure_device():
        return

    ui.header("Block Device Disk I/O Statistics")
    print()

    ok, out = adb.run(["shell", "cat", "/proc/diskstats"], timeout=10)
    if not ok or not out:
        ui.error("Failed to read /proc/diskstats")
        return

    rows = []
    # /proc/diskstats format:
    # 1: major, 2: minor, 3: dev_name, 4: reads_completed, 5: reads_merged, 6: sectors_read, 7: read_time_ms
    # 8: writes_completed, 9: writes_merged, 10: sectors_written, 11: write_time_ms, 12: ios_in_progress, 13: io_time_ms
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 14:
            dev = parts[2]
            reads = int(parts[3])
            sectors_read = int(parts[5])
            read_mb = (sectors_read * 512) / (1024 * 1024)

            writes = int(parts[7])
            sectors_written = int(parts[9])
            write_mb = (sectors_written * 512) / (1024 * 1024)

            io_prog = parts[11]
            io_time = f"{int(parts[12]) / 1000:.1f}s"

            # Filter for meaningful devices (sda, sdb, mmcblk, dm-0, etc.)
            if any(dev.startswith(prefix) for prefix in ("sd", "mmcblk", "dm-", "nvme", "vd")):
                if reads > 0 or writes > 0:
                    rows.append((dev, f"{reads:,}", f"{read_mb:.1f} MB", f"{writes:,}", f"{write_mb:.1f} MB", io_prog, io_time))

    if rows:
        headers = ("Device", "Reads", "Data Read", "Writes", "Data Written", "I/O Active", "Active Time")
        ui.print_table(rows[:20], headers)
    else:
        ui.info("No active block device statistics found.")


# ─── 10. Network Data Usage Stats ─────────────────────────────────────────────

def show_network_data_usage():
    """Read /proc/net/dev to display per-interface throughput (Wi-Fi, Mobile, Loopback)."""
    if not ensure_device():
        return

    ui.header("Network Interface Telemetry & Bandwidth")
    print()

    ok, out = adb.run(["shell", "cat", "/proc/net/dev"], timeout=10)
    if not ok or not out:
        ui.error("Failed to read /proc/net/dev")
        return

    rows = []
    wifi_rx, wifi_tx = 0, 0
    cell_rx, cell_tx = 0, 0

    # Line format: interface: rx_bytes rx_packets rx_errs ... tx_bytes tx_packets tx_errs
    for line in out.splitlines():
        if ":" in line:
            ifname, stats = line.split(":", 1)
            ifname = ifname.strip()
            parts = stats.split()
            if len(parts) >= 16:
                rx_b = int(parts[0])
                rx_p = int(parts[1])
                rx_e = int(parts[2])
                tx_b = int(parts[8])
                tx_p = int(parts[9])
                tx_e = int(parts[10])

                if rx_b > 0 or tx_b > 0:
                    rows.append((
                        ifname,
                        _format_bytes(rx_b),
                        f"{rx_p:,}",
                        str(rx_e),
                        _format_bytes(tx_b),
                        f"{tx_p:,}",
                        str(tx_e)
                    ))

                if "wlan" in ifname:
                    wifi_rx += rx_b
                    wifi_tx += tx_b
                elif "rmnet" in ifname or "ccmni" in ifname or "pdp" in ifname:
                    cell_rx += rx_b
                    cell_tx += tx_b

    if rows:
        headers = ("Interface", "RX Bytes", "RX Packets", "RX Errs", "TX Bytes", "TX Packets", "TX Errs")
        ui.print_table(rows, headers)
        print()

        ui.header("Cumulative Traffic Summary:")
        ui.print_kv({
            "Wi-Fi Download (RX)": _format_bytes(wifi_rx),
            "Wi-Fi Upload (TX)": _format_bytes(wifi_tx),
            "Total Wi-Fi Data": _format_bytes(wifi_rx + wifi_tx),
            "Mobile Download (RX)": _format_bytes(cell_rx),
            "Mobile Upload (TX)": _format_bytes(cell_tx),
            "Total Mobile Data": _format_bytes(cell_rx + cell_tx),
        })
    else:
        ui.warning("No active network interface statistics found.")


# ─── 11. Frame Rendering Stats (dumpsys gfxinfo) ──────────────────────────────

def show_frame_rendering_stats():
    """Profile UI frame rendering latency, janky frames, and missed VSYNCs."""
    if not ensure_device():
        return

    ui.header("UI Frame Rendering Performance (dumpsys gfxinfo)")
    print()

    focused = _get_focused_package()
    prompt = f"Enter package to profile [{focused}]" if focused else "Enter package to profile"
    pkg_input = ui.get_choice(prompt)
    package = pkg_input if pkg_input else (focused or "")

    if not package:
        ui.error("Package name is required.")
        return

    ui.info(f"Querying frame statistics for '{package}'...")
    ok, out = adb.run(["shell", "dumpsys", "gfxinfo", package], timeout=15)
    if not ok or not out:
        ui.error(f"Failed to query gfxinfo for {package}: {out}")
        return

    stats: dict[str, str] = {}
    for line in out.splitlines():
        line_s = line.strip()
        if ":" in line_s:
            k, v = line_s.split(":", 1)
            stats[k.strip()] = v.strip()

    total_frames_str = stats.get("Total frames rendered", "")
    janky_frames_str = stats.get("Janky frames", "")

    if total_frames_str and total_frames_str.isdigit():
        total_frames = int(total_frames_str)
        janky_frames = int(janky_frames_str.split()[0]) if janky_frames_str else 0
        jank_pct = (janky_frames / total_frames * 100) if total_frames > 0 else 0

        verdict = "EXCELLENT 🟢 (< 5% Jank)" if jank_pct < 5.0 else ("ACCEPTABLE 🟡" if jank_pct < 15.0 else "POOR / JANKY 🔴")

        print(f"  {ui.Colors.BOLD}Janky Frames:{ui.Colors.RESET}  {_render_bar(jank_pct)}  ({janky_frames} / {total_frames})")
        print()

        ui.print_kv({
            "Target Package": package,
            "Performance Rating": verdict,
            "Total Frames Rendered": f"{total_frames:,}",
            "Janky Frames (>16.6ms)": f"{janky_frames:,} ({jank_pct:.2f}%)",
            "50th Percentile Render Time": stats.get("50th percentile", "N/A"),
            "90th Percentile Render Time": stats.get("90th percentile", "N/A"),
            "95th Percentile Render Time": stats.get("95th percentile", "N/A"),
            "99th Percentile Render Time": stats.get("99th percentile", "N/A"),
            "Number Missed Vsync": stats.get("Number Missed Vsync", "N/A"),
            "Number High Input Latency": stats.get("Number High input latency", "N/A"),
            "Number Slow UI Thread": stats.get("Number Slow UI thread", "N/A"),
            "Number Slow Bitmap Uploads": stats.get("Number Slow bitmap uploads", "N/A"),
            "Number Slow Issue Draw Commands": stats.get("Number Slow issue draw commands", "N/A"),
        })
    else:
        # Raw snippet if structured lines not found
        ui.warning(f"No recent frame rendering profile data found for {package}.")
        ui.info("Interact with the application on the device screen first, then re-run.")
        print()
        for line in out.splitlines()[:25]:
            print(f"  {line}")


# ─── 12. System Uptime ────────────────────────────────────────────────────────

def show_system_uptime():
    """Display system uptime, idle time, and deep sleep telemetry."""
    if not ensure_device():
        return

    ui.header("System Uptime & Power State Breakdown")
    print()

    # Read /proc/uptime
    ok_up, up_out = adb.run(["shell", "cat", "/proc/uptime"])
    if not ok_up or not up_out:
        ui.error("Failed to read /proc/uptime")
        return

    parts = up_out.strip().split()
    if len(parts) >= 2:
        try:
            uptime_sec = float(parts[0])
            idle_sec = float(parts[1])

            td_uptime = timedelta(seconds=int(uptime_sec))
            days = td_uptime.days
            hours, remainder = divmod(td_uptime.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            uptime_formatted = f"{days} days, {hours:02d}h {minutes:02d}m {seconds:02d}s"

            # Check sleep time via power manager dumpsys if available
            ok_pw, pw_out = adb.run(["shell", "dumpsys", "power"], timeout=8)
            wake_state = "Unknown"
            if ok_pw and pw_out:
                for line in pw_out.splitlines():
                    if "mWakefulness=" in line:
                        wake_state = line.strip().split("mWakefulness=")[-1].split()[0]
                        break

            # Calculate boot timestamp
            boot_time = datetime.now() - td_uptime
            boot_str = boot_time.strftime("%Y-%m-%d %H:%M:%S")

            ui.print_kv({
                "Total System Uptime": uptime_formatted,
                "Uptime in Seconds": f"{uptime_sec:,.2f} s",
                "Total Core Idle Time": f"{idle_sec:,.2f} s",
                "System Boot Timestamp": boot_str,
                "Current Power State": f"{ui.Colors.GREEN if wake_state == 'Awake' else ui.Colors.YELLOW}{wake_state}{ui.Colors.RESET}",
            })
        except ValueError:
            ui.error(f"Error parsing uptime: {up_out}")
    else:
        ui.error(f"Unexpected uptime format: {up_out}")


# ─── Main Menu Loop ───────────────────────────────────────────────────────────

def performance_menu():
    """Main menu dispatch for Performance Monitor module."""
    while True:
        ui.clear()
        ui.print_banner()
        ui.print_device_status(adb.serial, adb.getprop("ro.product.model") if adb.serial else "")
        ui.print_sub_banner("Performance Monitor", "📊")

        options = [
            "CPU info (cores, architecture, frequencies)",
            "Memory info (RAM total/free/available)",
            "Storage info (df -h)",
            "Battery stats detailed (dumpsys battery)",
            "GPU info (renderer, version)",
            "Running processes (top 25 by memory)",
            "App-specific memory usage (dumpsys meminfo)",
            "CPU usage by app (top snapshot)",
            "Disk I/O stats (/proc/diskstats)",
            "Network data usage stats (/proc/net/dev)",
            "Frame rendering stats (dumpsys gfxinfo)",
            "System uptime (/proc/uptime)",
        ]

        ui.print_menu("Performance Monitor", options, columns=2)
        choice = ui.get_choice()

        if choice == "0":
            break
        elif choice == "1":
            show_cpu_info()
        elif choice == "2":
            show_memory_info()
        elif choice == "3":
            show_storage_info()
        elif choice == "4":
            show_battery_stats()
        elif choice == "5":
            show_gpu_info()
        elif choice == "6":
            show_running_processes()
        elif choice == "7":
            show_app_memory_usage()
        elif choice == "8":
            show_cpu_usage_by_app()
        elif choice == "9":
            show_disk_io_stats()
        elif choice == "10":
            show_network_data_usage()
        elif choice == "11":
            show_frame_rendering_stats()
        elif choice == "12":
            show_system_uptime()
        else:
            ui.error("Invalid option. Please try again.")

        ui.pause()
