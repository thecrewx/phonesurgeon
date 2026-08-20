"""
modules/device_info.py — Device Information Module for DroidCommander.

Provides in-depth hardware, software, battery, network, display,
telephony, sensors, thermal, storage, and build property diagnostics.
"""

from datetime import datetime
import os
import re
import time
from typing import Dict, List, Optional, Tuple

from core.adb import adb
from core import ui
from core.device import ensure_device


# ─── Android Version Code Names Mapping ──────────────────────────────────────

ANDROID_VERSION_NAMES: Dict[str, str] = {
    "1": "Base (API 1)",
    "2": "Donut (API 4) / Eclair (API 5-7)",
    "3": "Honeycomb (API 11-13)",
    "4.0": "Ice Cream Sandwich (API 14-15)",
    "4.1": "Jelly Bean (API 16)",
    "4.2": "Jelly Bean (API 17)",
    "4.3": "Jelly Bean (API 18)",
    "4.4": "KitKat (API 19)",
    "5.0": "Lollipop (API 21)",
    "5.1": "Lollipop (API 22)",
    "6.0": "Marshmallow (API 23)",
    "7.0": "Nougat (API 24)",
    "7.1": "Nougat (API 25)",
    "8.0": "Oreo (API 26)",
    "8.1": "Oreo (API 27)",
    "9": "Pie (API 28)",
    "10": "Android 10 (Quince Tart, API 29)",
    "11": "Android 11 (Red Velvet Cake, API 30)",
    "12": "Android 12 (Snow Cone, API 31)",
    "12L": "Android 12L (Sv2, API 32)",
    "13": "Android 13 (Tiramisu, API 33)",
    "14": "Android 14 (Upside Down Cake, API 34)",
    "15": "Android 15 (Vanilla Ice Cream, API 35)",
    "16": "Android 16 (Baklava, API 36)",
}

SDK_TO_VERSION_NAME: Dict[str, str] = {
    "21": "Android 5.0 (Lollipop)",
    "22": "Android 5.1 (Lollipop)",
    "23": "Android 6.0 (Marshmallow)",
    "24": "Android 7.0 (Nougat)",
    "25": "Android 7.1 (Nougat MR1)",
    "26": "Android 8.0 (Oreo)",
    "27": "Android 8.1 (Oreo MR1)",
    "28": "Android 9.0 (Pie)",
    "29": "Android 10 (Q)",
    "30": "Android 11 (R)",
    "31": "Android 12 (S)",
    "32": "Android 12L (Sv2)",
    "33": "Android 13 (Tiramisu)",
    "34": "Android 14 (Upside Down Cake)",
    "35": "Android 15 (Vanilla Ice Cream)",
    "36": "Android 16 (Baklava)",
}


def _get_android_codename(release: str, sdk: str) -> str:
    """Return descriptive Android release code name."""
    if sdk in SDK_TO_VERSION_NAME:
        return SDK_TO_VERSION_NAME[sdk]
    for ver_key, name in ANDROID_VERSION_NAMES.items():
        if release == ver_key or release.startswith(ver_key + "."):
            return name
    return f"Android {release} (API {sdk})" if release else "Unknown"


# ─── 1. List Connected Devices ───────────────────────────────────────────────

def list_connected_devices():
    """List all connected ADB devices with detailed connection information."""
    ui.print_sub_banner("Connected Devices List", "📱")
    devices = adb.list_devices()

    if not devices:
        ui.warning("No devices detected by ADB.")
        ui.info("Troubleshooting tips:")
        print("    1. Enable 'Developer Options' & 'USB Debugging' on your device.")
        print("    2. Reconnect USB cable or try a different port.")
        print("    3. Check device prompt to authorize RSA USB debugging.")
        return

    headers = ("#", "Serial", "State", "Product / Model", "Device", "Transport ID", "Type")
    rows: List[Tuple[str, ...]] = []

    for i, dev in enumerate(devices, 1):
        serial = dev.get("serial", "Unknown")
        state = dev.get("state", "unknown")
        model = dev.get("model", "—")
        device_name = dev.get("device", "—")
        transport = dev.get("transport_id", "—")

        conn_type = "WiFi / TCP" if (":" in serial and not serial.startswith("emulator")) else "USB"
        if serial.startswith("emulator-"):
            conn_type = "Emulator"

        active_marker = "★ " if adb.serial == serial else "  "
        num_label = f"{active_marker}{i}"

        # Color status
        if state == "device":
            state_str = f"{ui.Colors.GREEN}{state}{ui.Colors.RESET}"
        elif state == "unauthorized":
            state_str = f"{ui.Colors.YELLOW}{state}{ui.Colors.RESET}"
        elif state == "offline":
            state_str = f"{ui.Colors.RED}{state}{ui.Colors.RESET}"
        else:
            state_str = state

        rows.append((
            num_label,
            serial,
            state_str,
            model,
            device_name,
            transport,
            conn_type,
        ))

    ui.print_table(rows, headers)
    print()
    if adb.serial:
        ui.info(f"Currently active target: {ui.Colors.BOLD}{adb.serial}{ui.Colors.RESET} (marked with ★)")
    ui.info(f"Total devices found: {len(devices)}")


# ─── 2. Device Model & Build Info ────────────────────────────────────────────

def show_device_model_build_info():
    """Display comprehensive device identity, Android version, and build info."""
    if not ensure_device():
        return

    ui.print_sub_banner("Device Model & Build Information", "ℹ️")

    props = adb.get_all_props()
    if not props:
        ui.error("Failed to read system properties from device.")
        return

    release = props.get("ro.build.version.release", "Unknown")
    sdk = props.get("ro.build.version.sdk", "Unknown")
    codename = _get_android_codename(release, sdk)

    # 1. Device Hardware Identity
    ui.header("Device Identity:")
    identity_data = {
        "Manufacturer": props.get("ro.product.manufacturer", "Unknown"),
        "Brand": props.get("ro.product.brand", "Unknown"),
        "Model": props.get("ro.product.model", "Unknown"),
        "Device Codename": props.get("ro.product.device", "Unknown"),
        "Product Name": props.get("ro.product.name", "Unknown"),
        "Board": props.get("ro.product.board", props.get("ro.board.platform", "Unknown")),
        "Hardware": props.get("ro.hardware", "Unknown"),
    }
    ui.print_kv(identity_data)

    # 2. Android OS Details
    print()
    ui.header("Android OS & Platform:")
    os_data = {
        "Android Version": f"{release} ({codename})",
        "API / SDK Level": sdk,
        "Security Patch": props.get("ro.build.version.security_patch", "Unknown"),
        "Base OS": props.get("ro.build.version.base_os", "Stock"),
        "Preview SDK": props.get("ro.build.version.preview_sdk", "0"),
        "Incremental Version": props.get("ro.build.version.incremental", "Unknown"),
    }
    ui.print_kv(os_data)

    # 3. Build Details
    print()
    ui.header("Build Information:")
    build_data = {
        "Build ID": props.get("ro.build.id", "Unknown"),
        "Display ID": props.get("ro.build.display.id", "Unknown"),
        "Build Type": props.get("ro.build.type", "Unknown"),
        "Build Tags": props.get("ro.build.tags", "Unknown"),
        "Build User / Host": f"{props.get('ro.build.user', '')}@{props.get('ro.build.host', '')}",
        "Build Date": props.get("ro.build.date", "Unknown"),
        "Fingerprint": props.get("ro.build.fingerprint", "Unknown"),
    }
    ui.print_kv(build_data)

    # 4. System Architecture & Partitions
    print()
    ui.header("System & Boot Architecture:")
    boot_data = {
        "Bootloader": props.get("ro.bootloader", props.get("ro.boot.bootloader", "Unknown")),
        "Radio / Baseband": props.get("gsm.version.baseband", props.get("ro.boot.baseband", "Unknown")),
        "Primary ABI": props.get("ro.product.cpu.abi", "Unknown"),
        "Supported ABIs": props.get("ro.product.cpu.abilist", "Unknown"),
        "Treble Support": "Enabled" if props.get("ro.treble.enabled") == "true" else "Disabled",
        "A/B Slot": props.get("ro.boot.slot_suffix", "Non-A/B").strip("_"),
    }
    ui.print_kv(boot_data)


# ─── 3. Hardware Information ─────────────────────────────────────────────────

def show_hardware_info():
    """Display chipset, CPU architecture, core topology, GPU, and RAM."""
    if not ensure_device():
        return

    ui.print_sub_banner("Hardware & Architecture Diagnostics", "⚙️")

    props = adb.get_all_props()

    # CPU & Chipset info
    ui.header("Processor & Chipset:")
    soc_vendor = props.get("ro.soc.manufacturer", props.get("ro.hardware", "Unknown"))
    soc_model = props.get("ro.soc.model", props.get("ro.board.platform", "Unknown"))
    cpu_abi = props.get("ro.product.cpu.abi", "Unknown")
    cpu_abilist = props.get("ro.product.cpu.abilist", cpu_abi)

    chipset_data = {
        "SoC Manufacturer": soc_vendor,
        "Chipset / Platform": soc_model,
        "Primary CPU ABI": cpu_abi,
        "Supported ABIs": cpu_abilist,
        "32-Bit ABIs": props.get("ro.product.cpu.abilist32", "None"),
        "64-Bit ABIs": props.get("ro.product.cpu.abilist64", "None"),
    }
    ui.print_kv(chipset_data)

    # Core topology from /proc/cpuinfo
    print()
    ui.header("CPU Core Topology & Frequency:")
    ok_cpu, cpuinfo_out = adb.run(["shell", "cat", "/proc/cpuinfo"])
    core_count = 0
    hardware_name = ""
    features_list = ""

    if ok_cpu:
        for line in cpuinfo_out.splitlines():
            line = line.strip()
            if line.startswith("processor"):
                core_count += 1
            elif line.startswith("Hardware") and ":" in line:
                hardware_name = line.split(":", 1)[1].strip()
            elif line.startswith("Features") and ":" in line:
                features_list = line.split(":", 1)[1].strip()

    # Check online cores
    ok_online, online_out = adb.run(["shell", "cat", "/sys/devices/system/cpu/online"])
    online_str = online_out.strip() if ok_online and online_out else "0-0"

    # Read CPU0 scaling frequencies if accessible
    ok_cur, cur_freq = adb.run(["shell", "cat", "/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"])
    ok_max, max_freq = adb.run(["shell", "cat", "/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq"])
    ok_min, min_freq = adb.run(["shell", "cat", "/sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq"])

    freq_desc = "Unknown"
    if ok_cur and cur_freq.isdigit():
        cur_mhz = int(cur_freq) // 1000
        min_mhz = (int(min_freq) // 1000) if (ok_min and min_freq.isdigit()) else 0
        max_mhz = (int(max_freq) // 1000) if (ok_max and max_freq.isdigit()) else 0
        freq_desc = f"{cur_mhz} MHz (Range: {min_mhz} MHz - {max_mhz} MHz)"

    cpu_details = {
        "Total CPU Cores": f"{core_count} Cores" if core_count > 0 else "Unknown",
        "Online Cores": online_str,
        "CPU0 Frequency": freq_desc,
        "CPU Features": (features_list[:60] + "...") if len(features_list) > 60 else (features_list or "N/A"),
    }
    if hardware_name:
        cpu_details["CPU Hardware"] = hardware_name
    ui.print_kv(cpu_details)

    # GPU Diagnostics
    print()
    ui.header("Graphics Processing Unit (GPU):")
    gpu_vendor = "Unknown"
    gpu_renderer = "Unknown"
    gles_version = props.get("ro.opengles.version", "")

    # Parse GLES version hex
    gles_str = "Unknown"
    if gles_version.isdigit():
        val = int(gles_version)
        major = val >> 16
        minor = val & 0xFFFF
        gles_str = f"OpenGL ES {major}.{minor}"

    # Query SurfaceFlinger for GPU details
    ok_sf, sf_out = adb.run(["shell", "dumpsys", "SurfaceFlinger"], timeout=10)
    if ok_sf:
        for line in sf_out.splitlines():
            line_str = line.strip()
            if "GLES:" in line_str:
                gpu_renderer = line_str.replace("GLES:", "").strip()
            elif "OpenGL ES" in line_str and gles_str == "Unknown":
                gles_str = line_str

    gpu_data = {
        "GPU Renderer / Driver": gpu_renderer,
        "Supported OpenGL ES": gles_str,
        "Vulkan Version": props.get("ro.hardware.vulkan", "Supported" if "vulkan" in props.get("ro.product.cpu.abilist", "") else "N/A"),
    }
    ui.print_kv(gpu_data)

    # RAM Memory Breakdown
    print()
    ui.header("System RAM Memory Breakdown:")
    ok_mem, mem_out = adb.run(["shell", "cat", "/proc/meminfo"])
    if ok_mem:
        mem_dict = {}
        for line in mem_out.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                mem_dict[k.strip()] = v.strip()

        total_kb = int(mem_dict.get("MemTotal", "0 kB").split()[0])
        free_kb = int(mem_dict.get("MemFree", "0 kB").split()[0])
        avail_kb = int(mem_dict.get("MemAvailable", "0 kB").split()[0])
        cached_kb = int(mem_dict.get("Cached", "0 kB").split()[0])
        swap_total_kb = int(mem_dict.get("SwapTotal", "0 kB").split()[0])
        swap_free_kb = int(mem_dict.get("SwapFree", "0 kB").split()[0])

        total_mb = total_kb / 1024
        total_gb = total_mb / 1024
        avail_mb = avail_kb / 1024
        used_mb = (total_kb - avail_kb) / 1024
        pct_used = (used_mb / total_mb * 100) if total_mb > 0 else 0

        ram_data = {
            "Total Physical RAM": f"{total_gb:.2f} GB ({total_mb:.0f} MB)",
            "Used Memory": f"{used_mb:.0f} MB ({pct_used:.1f}%)",
            "Available Memory": f"{avail_mb:.0f} MB",
            "Free Memory": f"{free_kb / 1024:.0f} MB",
            "Cached Memory": f"{cached_kb / 1024:.0f} MB",
            "ZRAM / Swap Total": f"{swap_total_kb / 1024:.0f} MB (Free: {swap_free_kb / 1024:.0f} MB)",
        }
        ui.print_kv(ram_data)
        print()
        ui.progress_bar(int(used_mb), int(total_mb), label="RAM Usage:")
    else:
        ui.warning("Could not read /proc/meminfo.")


# ─── 4. Battery Status ───────────────────────────────────────────────────────

def show_battery_info():
    """Display battery level, health, voltage, temperature, and charging status."""
    if not ensure_device():
        return

    ui.print_sub_banner("Battery & Power Diagnostics", "🔋")

    ok, output = adb.run(["shell", "dumpsys", "battery"])
    if not ok:
        ui.error(f"Failed to query battery status: {output}")
        return

    battery_raw: Dict[str, str] = {}
    for line in output.splitlines():
        line = line.strip()
        if ":" in line:
            k, v = line.split(":", 1)
            battery_raw[k.strip().lower()] = v.strip()

    # Status mapping
    status_map = {
        "1": "Unknown",
        "2": f"{ui.Colors.GREEN}Charging ⚡{ui.Colors.RESET}",
        "3": f"{ui.Colors.YELLOW}Discharging 🔋{ui.Colors.RESET}",
        "4": "Not Charging",
        "5": f"{ui.Colors.GREEN}Full 💯{ui.Colors.RESET}",
    }
    health_map = {
        "1": "Unknown",
        "2": f"{ui.Colors.GREEN}Good (Healthy){ui.Colors.RESET}",
        "3": f"{ui.Colors.RED}Overheat ⚠️{ui.Colors.RESET}",
        "4": f"{ui.Colors.RED}Dead 💀{ui.Colors.RESET}",
        "5": f"{ui.Colors.RED}Over Voltage ⚡{ui.Colors.RESET}",
        "6": f"{ui.Colors.YELLOW}Unspecified Failure{ui.Colors.RESET}",
        "7": f"{ui.Colors.CYAN}Cold ❄️{ui.Colors.RESET}",
    }

    raw_status = battery_raw.get("status", "1")
    raw_health = battery_raw.get("health", "1")
    status_str = status_map.get(raw_status, f"Status Code {raw_status}")
    health_str = health_map.get(raw_health, f"Health Code {raw_health}")

    level_val = int(battery_raw.get("level", "0"))
    scale_val = int(battery_raw.get("scale", "100"))
    level_pct = int((level_val / scale_val) * 100) if scale_val > 0 else level_val

    # Power Sources
    power_sources: List[str] = []
    if battery_raw.get("ac powered") == "true":
        power_sources.append("AC Wall Adapter")
    if battery_raw.get("usb powered") == "true":
        power_sources.append("USB Cable")
    if battery_raw.get("wireless powered") == "true":
        power_sources.append("Wireless Qi Charger")
    if battery_raw.get("dock powered") == "true":
        power_sources.append("Dock Station")
    if not power_sources:
        power_sources.append("Battery Only (Unplugged)")

    # Voltage & Temperature
    voltage_raw = battery_raw.get("voltage", "0")
    voltage_v = (int(voltage_raw) / 1000.0) if voltage_raw.isdigit() else 0.0

    temp_raw = battery_raw.get("temperature", "0")
    temp_c = (int(temp_raw) / 10.0) if temp_raw.isdigit() else 0.0
    temp_f = (temp_c * 9 / 5) + 32

    # Colorize temperature
    if temp_c >= 45.0:
        temp_str = f"{ui.Colors.RED}{temp_c:.1f} °C / {temp_f:.1f} °F (High!){ui.Colors.RESET}"
    elif temp_c >= 37.0:
        temp_str = f"{ui.Colors.YELLOW}{temp_c:.1f} °C / {temp_f:.1f} °F (Warm){ui.Colors.RESET}"
    else:
        temp_str = f"{ui.Colors.GREEN}{temp_c:.1f} °C / {temp_f:.1f} °F (Normal){ui.Colors.RESET}"

    # Charge counter / Capacity
    charge_counter = battery_raw.get("charge counter", "")
    capacity_mah_str = f"{int(charge_counter) // 1000} mAh" if charge_counter.isdigit() else "N/A"

    ui.header("Battery Status Overview:")
    b_data = {
        "Battery Level": f"{level_pct}%",
        "Health State": health_str,
        "Charging Status": status_str,
        "Power Source(s)": ", ".join(power_sources),
        "Voltage": f"{voltage_v:.3f} V ({voltage_raw} mV)",
        "Temperature": temp_str,
        "Technology": battery_raw.get("technology", "Li-ion"),
        "Charge Counter": capacity_mah_str,
        "Battery Present": "Yes" if battery_raw.get("present") == "true" else "No",
    }
    ui.print_kv(b_data)
    print()
    ui.progress_bar(level_pct, 100, label="Battery Charge:")


# ─── 5. Screen Info ──────────────────────────────────────────────────────────

def show_screen_info():
    """Display screen resolution, density, refresh rate, orientation, and display state."""
    if not ensure_device():
        return

    ui.print_sub_banner("Screen & Display Diagnostics", "🖥️")

    # 1. Window Manager Size & Density
    ok_size, size_out = adb.run(["shell", "wm", "size"])
    ok_dens, dens_out = adb.run(["shell", "wm", "density"])

    phys_res = "Unknown"
    over_res = "None"
    if ok_size:
        for line in size_out.splitlines():
            if "Physical size:" in line:
                phys_res = line.replace("Physical size:", "").strip()
            elif "Override size:" in line:
                over_res = line.replace("Override size:", "").strip()

    phys_dpi = "Unknown"
    over_dpi = "None"
    if ok_dens:
        for line in dens_out.splitlines():
            if "Physical density:" in line:
                phys_dpi = line.replace("Physical density:", "").strip()
            elif "Override density:" in line:
                over_dpi = line.replace("Override density:", "").strip()

    # Determine DPI bucket
    dpi_bucket = "Unknown"
    if phys_dpi.isdigit():
        val = int(phys_dpi)
        if val <= 120:
            dpi_bucket = "ldpi (~120 dpi)"
        elif val <= 160:
            dpi_bucket = "mdpi (~160 dpi)"
        elif val <= 240:
            dpi_bucket = "hdpi (~240 dpi)"
        elif val <= 320:
            dpi_bucket = "xhdpi (~320 dpi)"
        elif val <= 480:
            dpi_bucket = "xxhdpi (~480 dpi)"
        elif val <= 640:
            dpi_bucket = "xxxhdpi (~640 dpi)"
        else:
            dpi_bucket = f"ultra-high ({val} dpi)"

    # 2. Refresh Rate & Display Specs
    refresh_rate = "Unknown"
    hdr_support = "Unknown"
    display_state = "Unknown"
    ok_disp, disp_out = adb.run(["shell", "dumpsys", "display"], timeout=10)

    if ok_disp:
        for line in disp_out.splitlines():
            line_str = line.strip()
            if "mDefaultModeId=" in line_str or "renderFrameRate" in line_str or "fps=" in line_str:
                fps_match = re.search(r"(\d+(?:\.\d+)?)\s*fps", line_str, re.IGNORECASE)
                if fps_match and refresh_rate == "Unknown":
                    refresh_rate = f"{fps_match.group(1)} Hz"
            if "state=" in line_str and ("ON" in line_str or "OFF" in line_str or "DOZE" in line_str):
                if "state=ON" in line_str:
                    display_state = "ON (Active)"
                elif "state=OFF" in line_str:
                    display_state = "OFF (Suspended)"
                elif "state=DOZE" in line_str:
                    display_state = "DOZE (Always-On Display)"
            if "hdrCapabilities" in line_str or "HDR" in line_str:
                hdr_support = "Supported" if "supported" in line_str.lower() else hdr_support

    # 3. Brightness & Screen Timeout Settings
    ok_b, b_val = adb.run(["shell", "settings", "get", "system", "screen_brightness"])
    ok_t, t_val = adb.run(["shell", "settings", "get", "system", "screen_off_timeout"])

    brightness_str = f"{b_val}/255 ({int(int(b_val)/255*100)}%)" if (ok_b and b_val.isdigit()) else (b_val or "Auto")
    timeout_str = "Unknown"
    if ok_t and t_val.isdigit():
        sec = int(t_val) // 1000
        if sec >= 60:
            timeout_str = f"{sec // 60} min {sec % 60} sec" if sec % 60 else f"{sec // 60} minutes"
        else:
            timeout_str = f"{sec} seconds"

    # 4. Orientation
    ok_ori, ori_out = adb.run(["shell", "dumpsys", "input"], timeout=5)
    orientation_str = "Portrait (0°)"
    if ok_ori:
        if "SurfaceOrientation: 1" in ori_out:
            orientation_str = "Landscape (90°)"
        elif "SurfaceOrientation: 2" in ori_out:
            orientation_str = "Reverse Portrait (180°)"
        elif "SurfaceOrientation: 3" in ori_out:
            orientation_str = "Reverse Landscape (270°)"

    ui.header("Display Specifications:")
    disp_data = {
        "Physical Resolution": phys_res,
        "Custom Resolution Override": over_res,
        "Physical Screen Density": f"{phys_dpi} dpi ({dpi_bucket})",
        "Custom Density Override": over_dpi,
        "Refresh Rate": refresh_rate,
        "Current Orientation": orientation_str,
        "Display State": display_state,
        "Screen Brightness": brightness_str,
        "Screen Timeout": timeout_str,
    }
    ui.print_kv(disp_data)


# ─── 6. Network Info ─────────────────────────────────────────────────────────

def show_network_info():
    """Display IP addresses, WiFi SSID, MAC address, routes, and network state."""
    if not ensure_device():
        return

    ui.print_sub_banner("Network & Connectivity Information", "🌐")

    props = adb.get_all_props()

    # 1. IP Addresses (wlan0, cellular, lo)
    ui.header("Network Interfaces & IP Addresses:")
    ok_ip, ip_out = adb.run(["shell", "ip", "-4", "addr", "show"])
    if not ok_ip or not ip_out:
        ok_ip, ip_out = adb.run(["shell", "ifconfig"])

    if ok_ip and ip_out:
        for line in ip_out.splitlines():
            line_str = line.strip()
            if line_str and ("inet " in line_str or "flags=" in line_str or ": " in line_str):
                print(f"    {line_str}")
    else:
        ui.warning("Could not enumerate network interfaces.")

    # 2. WiFi Details
    print()
    ui.header("Wi-Fi & Wireless Parameters:")
    ok_wifi, wifi_out = adb.run(["shell", "dumpsys", "wifi"], timeout=10)

    wifi_ssid = "Not Connected / Hidden"
    wifi_bssid = "Unknown"
    wifi_rssi = "Unknown"
    wifi_link_speed = "Unknown"
    wifi_mac = "Unknown"

    # Try reading MAC from sysfs
    ok_mac, mac_out = adb.run(["shell", "cat", "/sys/class/net/wlan0/address"])
    if ok_mac and mac_out.strip():
        wifi_mac = mac_out.strip()

    if ok_wifi:
        for line in wifi_out.splitlines():
            line_str = line.strip()
            if "mWifiInfo" in line_str or "SSID:" in line_str:
                ssid_match = re.search(r'SSID:\s*"?([^",]+)"?', line_str)
                if ssid_match and ssid_match.group(1) and ssid_match.group(1) != "<unknown ssid>":
                    wifi_ssid = ssid_match.group(1)

                bssid_match = re.search(r'BSSID:\s*([0-9a-fA-F:]{17})', line_str)
                if bssid_match:
                    wifi_bssid = bssid_match.group(1)

                rssi_match = re.search(r'RSSI:\s*(-?\d+)', line_str)
                if rssi_match:
                    wifi_rssi = f"{rssi_match.group(1)} dBm"

                speed_match = re.search(r'Link speed:\s*(\d+\s*Mbps)', line_str, re.IGNORECASE)
                if speed_match:
                    wifi_link_speed = speed_match.group(1)

                if wifi_mac == "Unknown":
                    mac_match = re.search(r'MAC:\s*([0-9a-fA-F:]{17})', line_str)
                    if mac_match:
                        wifi_mac = mac_match.group(1)

    wifi_data = {
        "Wi-Fi SSID": wifi_ssid,
        "BSSID (Access Point)": wifi_bssid,
        "Signal Strength (RSSI)": wifi_rssi,
        "Link Speed": wifi_link_speed,
        "Wi-Fi MAC Address": wifi_mac,
        "Hostname": props.get("net.hostname", "Android"),
        "Primary DNS": props.get("net.dns1", "N/A"),
        "Secondary DNS": props.get("net.dns2", "N/A"),
    }
    ui.print_kv(wifi_data)

    # 3. Bluetooth Address
    print()
    ui.header("Bluetooth Configuration:")
    ok_bt, bt_addr = adb.run(["shell", "settings", "get", "secure", "bluetooth_address"])
    bt_str = bt_addr.strip() if (ok_bt and bt_addr.strip() and bt_addr.strip() != "null") else "Unavailable / Protected"
    ui.print_kv({"Bluetooth MAC": bt_str})


# ─── 7. SIM & Telephony Info ─────────────────────────────────────────────────

def show_telephony_sim_info():
    """Display carrier, SIM state, network generation, telephony properties."""
    if not ensure_device():
        return

    ui.print_sub_banner("SIM & Telephony Information", "📶")

    props = adb.get_all_props()

    sim_state = props.get("gsm.sim.state", "Unknown")
    operator_alpha = props.get("gsm.sim.operator.alpha", props.get("gsm.operator.alpha", "Unknown"))
    operator_numeric = props.get("gsm.sim.operator.numeric", props.get("gsm.operator.numeric", "Unknown"))
    network_type = props.get("gsm.network.type", "Unknown")
    data_state = props.get("gsm.data.state", "Unknown")
    voice_type = props.get("gsm.voice.network.type", "Unknown")
    default_sub = props.get("ro.telephony.default_network", "Unknown")

    # Android ID as a standard hardware/instance identifier
    ok_aid, android_id = adb.run(["shell", "settings", "get", "secure", "android_id"])
    android_id_val = android_id.strip() if ok_aid and android_id.strip() else "Unknown"

    ui.header("Cellular & SIM Identity:")
    tel_data = {
        "SIM State": sim_state,
        "Carrier / Operator Name": operator_alpha,
        "Operator Numeric (MCC+MNC)": operator_numeric,
        "Network Data Technology": network_type,
        "Voice Network Technology": voice_type,
        "Mobile Data Connection State": data_state,
        "Default Telephony Mode": default_sub,
        "Android Secure ID": android_id_val,
        "IMEI / Device Serial Identifier": "Protected (Android 10+ requires privileged system rights)",
    }
    ui.print_kv(tel_data)

    print()
    ui.info("Note: Since Android 10 (API 29), hardware IMEI and Serial Number")
    ui.info("are strictly restricted to privileged system applications for user privacy.")


# ─── 8. Sensor List ──────────────────────────────────────────────────────────

def show_sensor_list():
    """List all hardware and virtual sensors present on the device."""
    if not ensure_device():
        return

    ui.print_sub_banner("Hardware & Virtual Sensors", "🧭")

    ok, output = adb.run(["shell", "dumpsys", "sensorservice"], timeout=10)
    if not ok:
        ui.error(f"Failed to query sensorservice: {output}")
        return

    headers = ("#", "Sensor Name", "Vendor", "Type / Category", "Power (mA)")
    rows: List[Tuple[str, ...]] = []

    # Sensor line matching in dumpsys sensorservice
    in_active_section = False
    count = 0

    for line in output.splitlines():
        line_str = line.strip()
        if "Active sensors:" in line_str or "Total" in line_str or "Sensor List:" in line_str:
            in_active_section = True

        # Matches lines like: 0x00000001) ICM42607 Accelerometer | TDK-InvenSense | ver: 1 | type: android.sensor.accelerometer(1) | ...
        if "|" in line_str and ("android.sensor." in line_str or "type:" in line_str):
            parts = [p.strip() for p in line_str.split("|")]
            if len(parts) >= 3:
                count += 1
                name_part = parts[0]
                # strip handle hex if present
                if ")" in name_part:
                    name_part = name_part.split(")", 1)[1].strip()

                vendor_part = parts[1]
                type_part = "Sensor"
                power_part = "—"

                for p in parts[2:]:
                    if "type:" in p:
                        type_part = p.replace("type:", "").strip()
                        if "(" in type_part:
                            type_part = type_part.split("(")[0].replace("android.sensor.", "")
                    elif "power" in p.lower():
                        power_part = p.strip()

                rows.append((
                    str(count),
                    name_part[:32],
                    vendor_part[:18],
                    type_part[:24],
                    power_part,
                ))

    if rows:
        ui.print_table(rows[:50], headers)
        print()
        ui.info(f"Total sensors discovered: {len(rows)} (showing up to 50)")
    else:
        # Fallback summary
        ui.header("Sensor Service Summary:")
        lines = output.splitlines()
        for line in lines[:25]:
            print(f"    {line}")
        if len(lines) > 25:
            ui.info(f"Showing first 25 of {len(lines)} lines from SensorService.")


# ─── 9. Thermal Zones / Temperature ──────────────────────────────────────────

def show_thermal_info():
    """Display temperatures across CPU, GPU, battery, and skin thermal zones."""
    if not ensure_device():
        return

    ui.print_sub_banner("Thermal Zones & Temperature Diagnostics", "🌡️")

    # Read thermal zones from sysfs
    ok, zone_list = adb.run(["shell", "ls", "-d", "/sys/class/thermal/thermal_zone*"])
    headers = ("#", "Zone Type / Component", "Raw Value", "Temperature (°C)", "Temperature (°F)", "Status")
    rows: List[Tuple[str, ...]] = []

    if ok and zone_list:
        zones = zone_list.split()
        for i, zone in enumerate(zones[:40], 1):
            ok_type, z_type = adb.run(["shell", "cat", f"{zone}/type"])
            ok_temp, z_temp = adb.run(["shell", "cat", f"{zone}/temp"])

            if ok_type and ok_temp and z_temp.strip().lstrip("-").isdigit():
                raw_val = int(z_temp.strip())
                # Some devices report in millidegrees (e.g. 42000), some in direct degrees (42)
                temp_c = raw_val / 1000.0 if abs(raw_val) > 200 else float(raw_val)
                temp_f = (temp_c * 9.0 / 5.0) + 32.0

                if temp_c >= 65.0:
                    status = f"{ui.Colors.RED}CRITICAL HOT ⚠️{ui.Colors.RESET}"
                elif temp_c >= 48.0:
                    status = f"{ui.Colors.YELLOW}WARM 🔥{ui.Colors.RESET}"
                elif temp_c <= 0.0:
                    status = f"{ui.Colors.CYAN}COLD ❄️{ui.Colors.RESET}"
                else:
                    status = f"{ui.Colors.GREEN}NORMAL{ui.Colors.RESET}"

                rows.append((
                    str(i),
                    z_type.strip(),
                    str(raw_val),
                    f"{temp_c:.1f} °C",
                    f"{temp_f:.1f} °F",
                    status,
                ))

    if rows:
        ui.print_table(rows, headers)
        print()
        ui.info(f"Monitored {len(rows)} thermal sensor zones.")
    else:
        # Fallback to dumpsys thermalservice
        ok_ts, ts_out = adb.run(["shell", "dumpsys", "thermalservice"])
        if ok_ts and ts_out:
            ui.header("Thermal Service Output:")
            for line in ts_out.splitlines()[:30]:
                print(f"    {line}")
        else:
            ui.warning("Thermal sensor metrics unavailable on this device architecture.")


# ─── 10. Full Build Properties Dump ──────────────────────────────────────────

def show_full_build_props():
    """Inspect, search, or export all device system build properties."""
    if not ensure_device():
        return

    ui.print_sub_banner("System Build Properties Dump", "📜")

    props = adb.get_all_props()
    if not props:
        ui.error("No system properties could be retrieved.")
        return

    ui.info(f"Total available system properties: {len(props)}")
    print()
    print("  [1] Search properties by keyword / prefix")
    print("  [2] View core Android properties (ro.build.*, ro.product.*)")
    print("  [3] View telephony & network properties (gsm.*, net.*)")
    print("  [4] Export ALL properties to a local text file")
    print("  [5] Display all properties in terminal")
    print("  [0] Return to Device Info Menu")
    print()

    sub_choice = ui.get_choice("Select property view mode")

    if sub_choice == "1":
        query = ui.get_choice("Enter keyword to search (e.g. 'display', 'camera', 'dalvik')")
        if not query:
            return
        matches = {k: v for k, v in props.items() if query.lower() in k.lower() or query.lower() in v.lower()}
        ui.header(f"Search Results for '{query}' ({len(matches)} matches):")
        print()
        ui.print_kv(matches)

    elif sub_choice == "2":
        core_props = {k: v for k, v in props.items() if k.startswith("ro.build.") or k.startswith("ro.product.")}
        ui.header(f"Core Product & Build Properties ({len(core_props)} entries):")
        print()
        ui.print_kv(core_props)

    elif sub_choice == "3":
        net_props = {k: v for k, v in props.items() if k.startswith("gsm.") or k.startswith("net.") or k.startswith("telephony.")}
        ui.header(f"Telephony & Network Properties ({len(net_props)} entries):")
        print()
        ui.print_kv(net_props)

    elif sub_choice == "4":
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dev_model = props.get("ro.product.model", "android").replace(" ", "_")
        filename = f"properties_{dev_model}_{timestamp}.txt"

        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"=== DroidCommander System Properties Dump ===\n")
                f.write(f"Device: {props.get('ro.product.model', 'Unknown')} ({props.get('ro.product.manufacturer', '')})\n")
                f.write(f"Serial: {adb.serial}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"Total Properties: {len(props)}\n\n")
                for k in sorted(props.keys()):
                    f.write(f"[{k}]: [{props[k]}]\n")
            ui.success(f"Properties successfully exported to: {os.path.abspath(filename)}")
        except Exception as e:
            ui.error(f"Failed to export properties file: {e}")

    elif sub_choice == "5":
        ui.header(f"Displaying first 60 of {len(props)} properties:")
        sorted_keys = sorted(props.keys())
        for k in sorted_keys[:60]:
            print(f"    {ui.Colors.CYAN}{k}{ui.Colors.RESET} = {props[k]}")
        if len(props) > 60:
            ui.info(f"Output truncated. {len(props) - 60} more properties available. Use Option [4] to export full list.")


# ─── 11. Storage Overview ────────────────────────────────────────────────────

def show_storage_overview():
    """Display internal storage, system partitions, and SD card space metrics."""
    if not ensure_device():
        return

    ui.print_sub_banner("Storage Partitions & Disk Space Overview", "💾")

    ok, df_out = adb.run(["shell", "df", "-h"])
    if not ok:
        ui.error(f"Failed to execute df: {df_out}")
        return

    headers = ("Filesystem", "Size", "Used", "Avail", "Use%", "Mounted On")
    rows: List[Tuple[str, ...]] = []

    internal_used_mb = 0
    internal_total_mb = 0

    for line in df_out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 6:
            fs, size, used, avail, use_pct, mount = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
            # Prioritize standard android mounts
            if mount in ("/data", "/system", "/vendor", "/product", "/storage/emulated", "/sdcard") or "/mnt/" in mount or "/storage/" in mount:
                rows.append((fs, size, used, avail, use_pct, mount))

    ui.print_table(rows, headers)
    print()

    # Query detailed internal storage stats via dumpsys diskstats
    ok_disk, disk_out = adb.run(["shell", "dumpsys", "diskstats"])
    if ok_disk:
        ui.header("Data & Cache Summary:")
        for line in disk_out.splitlines():
            line_str = line.strip()
            if "Data-Free:" in line_str or "Cache-Free:" in line_str or "System-Free:" in line_str:
                print(f"    {ui.Colors.CYAN}•{ui.Colors.RESET} {line_str}")


# ─── 12. Feature List ────────────────────────────────────────────────────────

def show_feature_list():
    """Inspect and categorize device hardware & software feature support."""
    if not ensure_device():
        return

    ui.print_sub_banner("Hardware & System Feature Manifest", "✨")

    ok, feat_out = adb.run(["shell", "pm", "list", "features"])
    if not ok:
        ui.error(f"Failed to list features: {feat_out}")
        return

    supported_features = set()
    for line in feat_out.splitlines():
        line = line.strip()
        if line.startswith("feature:"):
            feat_name = line.replace("feature:", "").split("=")[0].strip()
            supported_features.add(feat_name)

    # Core checklist items
    feature_checks = [
        ("Camera (Back / Main)", "android.hardware.camera"),
        ("Camera (Front Facing)", "android.hardware.camera.front"),
        ("Camera Autofocus", "android.hardware.camera.autofocus"),
        ("Camera Flash", "android.hardware.camera.flash"),
        ("Camera RAW Capability", "android.hardware.camera.raw"),
        ("NFC (Near Field Comm)", "android.hardware.nfc"),
        ("NFC Host Card Emulation", "android.hardware.nfc.hce"),
        ("Bluetooth", "android.hardware.bluetooth"),
        ("Bluetooth Low Energy (BLE)", "android.hardware.bluetooth_le"),
        ("Wi-Fi Networking", "android.hardware.wifi"),
        ("Wi-Fi Direct (P2P)", "android.hardware.wifi.direct"),
        ("Wi-Fi Aware (NAN)", "android.hardware.wifi.aware"),
        ("GPS / Location Hardware", "android.hardware.location.gps"),
        ("Fingerprint Biometrics", "android.hardware.fingerprint"),
        ("Biometrics Strong", "android.hardware.biometrics.strong"),
        ("Accelerometer Sensor", "android.hardware.sensor.accelerometer"),
        ("Gyroscope Sensor", "android.hardware.sensor.gyroscope"),
        ("Compass / Magnetometer", "android.hardware.sensor.compass"),
        ("Barometer / Pressure", "android.hardware.sensor.barometer"),
        ("Step Detector / Counter", "android.hardware.sensor.stepdetector"),
        ("Vulkan Graphics Hardware", "android.hardware.vulkan.version"),
        ("OpenGLES 3.2 Compute", "android.hardware.opengles.aep"),
        ("USB Host (OTG)", "android.hardware.usb.host"),
        ("USB Accessory", "android.hardware.usb.accessory"),
        ("Telephony / Cellular", "android.hardware.telephony"),
        ("SIP / VOIP Calling", "android.software.sip"),
        ("Picture-in-Picture (PiP)", "android.software.picture_in_picture"),
        ("Freeform Multi-Window", "android.software.freeform_window_management"),
    ]

    headers = ("Feature Capability", "System Feature Identifier", "Status")
    rows: List[Tuple[str, ...]] = []

    for label, feat_id in feature_checks:
        is_supported = feat_id in supported_features
        status_str = f"{ui.Colors.GREEN}✓ Supported{ui.Colors.RESET}" if is_supported else f"{ui.Colors.RED}✗ Unsupported{ui.Colors.RESET}"
        rows.append((label, feat_id, status_str))

    ui.print_table(rows, headers)
    print()
    ui.info(f"Device reports {len(supported_features)} total declared system features.")


# ─── 13. Export Full Device Report ───────────────────────────────────────────

def export_full_device_report():
    """Generate and save a comprehensive multi-section diagnostic report."""
    if not ensure_device():
        return

    ui.print_sub_banner("Generate Diagnostic Report", "📑")
    ui.info("Compiling full diagnostic profile from device...")

    props = adb.get_all_props()
    model = props.get("ro.product.model", "device").replace(" ", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"device_report_{model}_{timestamp}.txt"

    lines: List[str] = [
        "=" * 60,
        "   🤖 DROIDCOMMANDER FULL DEVICE DIAGNOSTIC REPORT",
        "=" * 60,
        f"Generated At : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Device Serial: {adb.serial}",
        f"Device Model : {props.get('ro.product.manufacturer', '')} {props.get('ro.product.model', '')}",
        f"Android Ver  : {props.get('ro.build.version.release', '')} (SDK {props.get('ro.build.version.sdk', '')})",
        "=" * 60,
        "",
        "--- [1. BUILD & IDENTITY] ---",
    ]

    for k in sorted(props.keys()):
        if any(k.startswith(p) for p in ("ro.product.", "ro.build.", "ro.boot.", "ro.hardware")):
            lines.append(f"  {k}: {props[k]}")

    lines.append("\n--- [2. BATTERY STATUS] ---")
    ok_b, batt_out = adb.run(["shell", "dumpsys", "battery"])
    lines.append(batt_out if ok_b else "Battery status unavailable.")

    lines.append("\n--- [3. DISPLAY & SCREEN] ---")
    ok_sz, sz_out = adb.run(["shell", "wm", "size"])
    ok_dn, dn_out = adb.run(["shell", "wm", "density"])
    lines.append(f"Resolution: {sz_out if ok_sz else 'N/A'}")
    lines.append(f"Density   : {dn_out if ok_dn else 'N/A'}")

    lines.append("\n--- [4. STORAGE (DF)] ---")
    ok_df, df_out = adb.run(["shell", "df", "-h"])
    lines.append(df_out if ok_df else "Storage info unavailable.")

    lines.append("\n--- [5. MEMORY (MEMINFO)] ---")
    ok_mem, mem_out = adb.run(["shell", "cat", "/proc/meminfo"])
    if ok_mem:
        lines.extend(mem_out.splitlines()[:20])

    lines.append("\n--- [6. THERMAL STATUS] ---")
    ok_ts, ts_out = adb.run(["shell", "dumpsys", "thermalservice"])
    lines.append(ts_out if ok_ts else "Thermal service info unavailable.")

    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        ui.success(f"Full report successfully exported to: {os.path.abspath(filename)}")
    except Exception as e:
        ui.error(f"Failed to write report file: {e}")


# ─── Main Menu Loop ──────────────────────────────────────────────────────────

def device_info_menu():
    """Device information interactive submenu."""
    options = [
        "List connected devices (detailed overview)",
        "Device model, brand, Android version & build",
        "Hardware info (chipset, CPU cores, GPU, RAM)",
        "Battery status (level, health, voltage, temp)",
        "Screen info (resolution, density, refresh rate)",
        "Network info (IP address, MAC, WiFi SSID)",
        "SIM / telephony info (carrier, SIM state)",
        "Sensor list (accelerometer, gyro, etc.)",
        "Thermal zones / temperature diagnostics",
        "Full build properties dump (search / export)",
        "Storage overview (internal partitions, SD card)",
        "Feature list (camera, NFC, bluetooth, etc.)",
        "Export full device diagnostic report (.txt)",
    ]

    while True:
        ui.clear()
        ui.print_banner()
        ui.print_device_status(adb.serial)
        ui.print_menu("📱 Device Information & Diagnostics", options, columns=2)

        choice = ui.get_choice()

        if choice == "0":
            break
        elif choice == "1":
            list_connected_devices()
        elif choice == "2":
            show_device_model_build_info()
        elif choice == "3":
            show_hardware_info()
        elif choice == "4":
            show_battery_info()
        elif choice == "5":
            show_screen_info()
        elif choice == "6":
            show_network_info()
        elif choice == "7":
            show_telephony_sim_info()
        elif choice == "8":
            show_sensor_list()
        elif choice == "9":
            show_thermal_info()
        elif choice == "10":
            show_full_build_props()
        elif choice == "11":
            show_storage_overview()
        elif choice == "12":
            show_feature_list()
        elif choice == "13":
            export_full_device_report()
        else:
            ui.error("Invalid option. Please choose a number from the menu.")

        ui.pause()
