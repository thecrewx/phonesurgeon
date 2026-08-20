"""
modules/network_tools.py — Network inspection, diagnostics, and management.

Provides a comprehensive suite of network utilities for Android devices:
- Wi-Fi and Mobile data state & properties
- IP configuration and interface details
- Routing tables, open ports, and active connections
- DNS lookups, Ping, and HTTP/HTTPS connectivity checks
- Data usage statistics & live throughput monitor
- Wi-Fi saved networks and Wi-Fi power toggling
- All-in-one network diagnostics scorecard
"""

import os
import re
import socket
import struct
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from core.adb import adb
from core import ui
from core.device import ensure_device


# ─── Helper Utilities ────────────────────────────────────────────────────────

def _run_shell(cmd: str, timeout: int = 25) -> Tuple[bool, str]:
    """Execute a shell command with adb.run."""
    return adb.run(["shell"] + cmd.split(), timeout=timeout)


def _run_raw_shell(cmd_str: str, timeout: int = 25) -> Tuple[bool, str]:
    """Execute a shell command string using 'sh -c' to preserve quotes and pipes."""
    return adb.run(["shell", "sh", "-c", cmd_str], timeout=timeout)


def _format_bytes(byte_count: int) -> str:
    """Format bytes into human-readable string (B, KB, MB, GB, TB)."""
    if byte_count < 1024:
        return f"{byte_count} B"
    elif byte_count < 1024 ** 2:
        return f"{byte_count / 1024:.2f} KB"
    elif byte_count < 1024 ** 3:
        return f"{byte_count / (1024 ** 2):.2f} MB"
    elif byte_count < 1024 ** 4:
        return f"{byte_count / (1024 ** 3):.2f} GB"
    else:
        return f"{byte_count / (1024 ** 4):.2f} TB"


def _freq_to_band(freq_mhz: int) -> str:
    """Convert Wi-Fi frequency in MHz to human-readable band and channel."""
    if 2412 <= freq_mhz <= 2484:
        channel = (freq_mhz - 2407) // 5 if freq_mhz != 2484 else 14
        return f"2.4 GHz (Channel {channel})"
    elif 5150 <= freq_mhz <= 5885:
        channel = (freq_mhz - 5000) // 5
        return f"5 GHz (Channel {channel})"
    elif 5925 <= freq_mhz <= 7125:
        channel = (freq_mhz - 5950) // 5 + 1
        return f"6 GHz (Wi-Fi 6E/7, Channel {channel})"
    return f"{freq_mhz} MHz"


def _rssi_to_quality(rssi: int) -> Tuple[str, str]:
    """Convert RSSI dBm into a percentage, label, and signal bar representation."""
    if rssi <= -100:
        quality = 0
    elif rssi >= -50:
        quality = 100
    else:
        quality = 2 * (rssi + 100)

    if quality >= 80:
        bars = "████"
        label = f"{ui.Colors.GREEN}Excellent ({quality}%){ui.Colors.RESET}"
    elif quality >= 60:
        bars = "███░"
        label = f"{ui.Colors.CYAN}Good ({quality}%){ui.Colors.RESET}"
    elif quality >= 40:
        bars = "██░░"
        label = f"{ui.Colors.YELLOW}Fair ({quality}%){ui.Colors.RESET}"
    elif quality >= 20:
        bars = "█░░░"
        label = f"{ui.Colors.RED}Weak ({quality}%){ui.Colors.RESET}"
    else:
        bars = "░░░░"
        label = f"{ui.Colors.RED}Very Poor ({quality}%){ui.Colors.RESET}"

    return f"[{bars}] {rssi} dBm", label


def _decode_hex_ip(hex_str: str) -> str:
    """Decode little-endian hex IP from /proc/net/tcp to dotted quad."""
    try:
        if len(hex_str) == 8:
            # IPv4
            ip_int = int(hex_str, 16)
            return socket.inet_ntoa(struct.pack("<L", ip_int))
        elif len(hex_str) == 32:
            # IPv6 (4 32-bit words, each little endian)
            words = [int(hex_str[i:i+8], 16) for i in range(0, 32, 8)]
            packed = struct.pack("<4I", *words)
            return socket.inet_ntop(socket.AF_INET6, packed)
    except Exception:
        pass
    return hex_str


def _resolve_port_name(port: int, proto: str = "tcp") -> str:
    """Return a descriptive name for well-known ports."""
    well_known = {
        53: "DNS",
        67: "DHCP-Server",
        68: "DHCP-Client",
        80: "HTTP",
        123: "NTP",
        443: "HTTPS",
        853: "DNS-over-TLS",
        5228: "Google Play FCM",
        5229: "Google Play FCM",
        5230: "Google Play FCM",
        5555: "ADB over TCP",
        8080: "HTTP-Proxy/Alt",
        8443: "HTTPS-Alt",
        9000: "ADB/DevServer",
    }
    return well_known.get(port, "")


# ─── 1. Wi-Fi Information ────────────────────────────────────────────────────

def show_wifi_info():
    """Display detailed Wi-Fi connection information."""
    if not ensure_device():
        return

    ui.print_sub_banner("Wi-Fi Connection Information", "📶")
    ui.info("Querying Wi-Fi status and connection parameters...")

    # Check Wi-Fi state
    ok_state, state_out = _run_shell("settings get global wifi_on")
    wifi_enabled = "1" in state_out if ok_state else True

    # Try cmd wifi status (Android 10+) or dumpsys wifi
    ok_wifi, wifi_out = _run_shell("dumpsys wifi")
    if not ok_wifi and not wifi_out:
        ui.error("Unable to query Wi-Fi subsystem.")
        ui.pause()
        return

    info_data: Dict[str, str] = {}
    info_data["Wi-Fi Subsystem"] = f"{ui.Colors.GREEN}Enabled{ui.Colors.RESET}" if wifi_enabled else f"{ui.Colors.RED}Disabled{ui.Colors.RESET}"

    # Extract SSID
    ssid_match = re.search(r'SSID:\s*"?([^",\n\r]+)"?', wifi_out)
    ssid = ssid_match.group(1).strip() if ssid_match else ""
    if not ssid or ssid == "<unknown ssid>" or ssid == "0x":
        # Fallback check
        ssid_alt = re.search(r'mWifiInfo\s+SSID:\s*"([^"]+)"', wifi_out)
        ssid = ssid_alt.group(1) if ssid_alt else "Not Connected / Disconnected"
    info_data["SSID (Network Name)"] = f"{ui.Colors.BOLD}{ssid}{ui.Colors.RESET}"

    # Extract BSSID
    bssid_match = re.search(r'BSSID:\s*([0-9a-fA-F:]{17})', wifi_out)
    info_data["BSSID (Access Point MAC)"] = bssid_match.group(1) if bssid_match else "N/A"

    # Extract RSSI / Signal
    rssi_match = re.search(r'RSSI:\s*(-?\d+)', wifi_out)
    if rssi_match:
        rssi_val = int(rssi_match.group(1))
        bars_str, quality_lbl = _rssi_to_quality(rssi_val)
        info_data["Signal Strength (RSSI)"] = f"{bars_str} ({quality_lbl})"
    else:
        info_data["Signal Strength (RSSI)"] = "N/A (Disconnected)"

    # Extract Frequency
    freq_match = re.search(r'Frequency:\s*(\d+)\s*MHz', wifi_out, re.IGNORECASE)
    if freq_match:
        freq_mhz = int(freq_match.group(1))
        info_data["Frequency & Band"] = _freq_to_band(freq_mhz)
    else:
        info_data["Frequency & Band"] = "N/A"

    # Extract Link Speed
    speed_match = re.search(r'Link speed:\s*(\d+)\s*Mbps', wifi_out, re.IGNORECASE)
    tx_match = re.search(r'Tx Link speed:\s*(\d+)\s*Mbps', wifi_out, re.IGNORECASE)
    rx_match = re.search(r'Rx Link speed:\s*(\d+)\s*Mbps', wifi_out, re.IGNORECASE)

    speed_str = ""
    if speed_match:
        speed_str = f"{speed_match.group(1)} Mbps"
    if tx_match or rx_match:
        tx_val = tx_match.group(1) if tx_match else "—"
        rx_val = rx_match.group(1) if rx_match else "—"
        speed_str += f" (Tx: {tx_val} Mbps, Rx: {rx_val} Mbps)"
    info_data["Link Speed"] = speed_str if speed_str else "N/A"

    # Extract Wi-Fi Standard
    std_match = re.search(r'Wi-Fi standard:\s*(\d+)', wifi_out, re.IGNORECASE)
    if std_match:
        std_map = {"4": "Wi-Fi 4 (802.11n)", "5": "Wi-Fi 5 (802.11ac)", "6": "Wi-Fi 6 (802.11ax)", "7": "Wi-Fi 7 (802.11be)"}
        info_data["Wi-Fi Standard"] = std_map.get(std_match.group(1), f"Standard {std_match.group(1)}")

    # Extract Supplicant / Connection State
    state_match = re.search(r'Supplicant state:\s*([A-Z_]+)', wifi_out)
    if state_match:
        info_data["Supplicant State"] = state_match.group(1)
    else:
        ip_state_match = re.search(r'mWifiInfo\s+State:\s*([A-Z_]+)', wifi_out)
        if ip_state_match:
            info_data["Supplicant State"] = ip_state_match.group(1)

    # Extract Device IP & MAC
    mac_match = re.search(r'MAC:\s*([0-9a-fA-F:]{17})', wifi_out)
    info_data["Device Wi-Fi MAC"] = mac_match.group(1) if mac_match else "N/A"

    # Interface name
    wlan_iface = adb.getprop("wifi.interface") or "wlan0"
    info_data["Wi-Fi Interface"] = wlan_iface

    # IP address on wlan0
    ok_ip, ip_out = _run_shell(f"ip -4 addr show {wlan_iface}")
    if ok_ip:
        inet_match = re.search(r'inet\s+([0-9.]+/\d+)', ip_out)
        info_data["Assigned IPv4"] = inet_match.group(1) if inet_match else "None / Unassigned"

    # Gateway
    ok_gw, gw_out = _run_shell(f"ip route show dev {wlan_iface}")
    if ok_gw:
        gw_match = re.search(r'default via\s+([0-9.]+)', gw_out)
        info_data["Default Gateway"] = gw_match.group(1) if gw_match else "N/A"

    print()
    ui.print_kv(info_data, indent=4)
    print()
    ui.pause()


# ─── 2. Wi-Fi IP Address Details ─────────────────────────────────────────────

def show_wifi_ip():
    """Display comprehensive IP, subnet, gateway, and DHCP lease information."""
    if not ensure_device():
        return

    ui.print_sub_banner("Wi-Fi IP Address & Interface Details", "🌐")

    wlan_iface = adb.getprop("wifi.interface") or "wlan0"
    ui.info(f"Inspecting network interface '{wlan_iface}'...")

    ok_addr, addr_out = _run_shell(f"ip addr show {wlan_iface}")
    if not ok_addr or not addr_out.strip():
        # Fallback to checking all wlan interfaces
        ok_addr, addr_out = _run_raw_shell("ip addr | grep -A 8 -E 'wlan|eth'")
        if not ok_addr or not addr_out.strip():
            ui.error(f"No active wireless interface found ({wlan_iface}). Is Wi-Fi turned on?")
            ui.pause()
            return

    # Parse details
    ip_data: Dict[str, str] = {}
    ip_data["Interface"] = wlan_iface

    # Link status
    if "state UP" in addr_out:
        ip_data["Link Status"] = f"{ui.Colors.GREEN}UP (Connected){ui.Colors.RESET}"
    elif "state DOWN" in addr_out:
        ip_data["Link Status"] = f"{ui.Colors.RED}DOWN (Disconnected){ui.Colors.RESET}"
    else:
        ip_data["Link Status"] = "UNKNOWN"

    # MTU
    mtu_match = re.search(r'mtu\s+(\d+)', addr_out)
    ip_data["MTU"] = mtu_match.group(1) if mtu_match else "1500"

    # MAC Address
    mac_match = re.search(r'link/ether\s+([0-9a-fA-F:]{17})', addr_out)
    ip_data["MAC Address (link/ether)"] = mac_match.group(1) if mac_match else "N/A"

    # IPv4 Address
    ipv4_matches = re.findall(r'inet\s+([0-9.]+/\d+)\s+brd\s+([0-9.]+)', addr_out)
    if ipv4_matches:
        ip_data["IPv4 Address (CIDR)"] = ipv4_matches[0][0]
        ip_data["Broadcast Address"] = ipv4_matches[0][1]
    else:
        inet_single = re.search(r'inet\s+([0-9.]+/\d+)', addr_out)
        ip_data["IPv4 Address (CIDR)"] = inet_single.group(1) if inet_single else "None"
        ip_data["Broadcast Address"] = "N/A"

    # IPv6 Addresses
    ipv6_matches = re.findall(r'inet6\s+([0-9a-fA-F:]+/\d+)\s+scope\s+(\w+)', addr_out)
    if ipv6_matches:
        for idx, (ip6, scope) in enumerate(ipv6_matches, 1):
            ip_data[f"IPv6 #{idx} ({scope})"] = ip6
    else:
        ip_data["IPv6 Address"] = "None configured"

    # Gateway & Routes
    ok_route, route_out = _run_shell(f"ip route show dev {wlan_iface}")
    if ok_route and route_out:
        routes = [line.strip() for line in route_out.splitlines() if line.strip()]
        for r in routes:
            if "default via" in r:
                gw = r.split("default via")[1].split()[0]
                ip_data["Default Gateway"] = f"{ui.Colors.BOLD}{gw}{ui.Colors.RESET}"
            elif "/" in r:
                ip_data["Local Subnet Route"] = r

    # DHCP Properties
    dhcp_dns1 = adb.getprop(f"dhcp.{wlan_iface}.dns1")
    dhcp_dns2 = adb.getprop(f"dhcp.{wlan_iface}.dns2")
    dhcp_server = adb.getprop(f"dhcp.{wlan_iface}.server")
    dhcp_lease = adb.getprop(f"dhcp.{wlan_iface}.leasetime")

    if dhcp_dns1 or dhcp_dns2:
        ip_data["DHCP DNS Servers"] = f"{dhcp_dns1}, {dhcp_dns2}".strip(", ")
    if dhcp_server:
        ip_data["DHCP Server"] = dhcp_server
    if dhcp_lease:
        try:
            lease_sec = int(dhcp_lease)
            ip_data["DHCP Lease Duration"] = f"{lease_sec} seconds ({lease_sec / 3600:.1f} hours)"
        except ValueError:
            ip_data["DHCP Lease Duration"] = f"{dhcp_lease} seconds"

    print()
    ui.print_kv(ip_data, indent=4)
    print()
    ui.pause()


# ─── 3. Mobile Data Information ──────────────────────────────────────────────

def show_mobile_data_info():
    """Display cellular network carrier, SIM state, network generation, and mobile data status."""
    if not ensure_device():
        return

    ui.print_sub_banner("Cellular & Mobile Data Information", "📱")
    ui.info("Gathering Telephony and Cellular subsystem properties...")

    data_info: Dict[str, str] = {}

    # Operator / Carrier Names
    carrier_alpha = adb.getprop("gsm.operator.alpha")
    sim_alpha = adb.getprop("gsm.sim.operator.alpha")
    data_info["Registered Operator"] = carrier_alpha or "Unknown / No Service"
    data_info["SIM Card Provider"] = sim_alpha or "Unknown"

    # Network Type (LTE, NR/5G, HSPA, etc.)
    net_type = adb.getprop("gsm.network.type")
    data_info["Radio Access Technology"] = f"{ui.Colors.BOLD}{net_type.upper()}{ui.Colors.RESET}" if net_type else "Unknown"

    # SIM State
    sim_state = adb.getprop("gsm.sim.state")
    if sim_state.upper() in ("READY", "LOADED"):
        data_info["SIM Card State"] = f"{ui.Colors.GREEN}{sim_state}{ui.Colors.RESET}"
    elif sim_state.upper() == "ABSENT":
        data_info["SIM Card State"] = f"{ui.Colors.RED}No SIM Card Inserted{ui.Colors.RESET}"
    else:
        data_info["SIM Card State"] = sim_state or "Unknown"

    # Operator Numeric (MCC/MNC) and Country
    op_numeric = adb.getprop("gsm.operator.numeric")
    data_info["MCC / MNC Code"] = op_numeric if op_numeric else "N/A"

    iso_country = adb.getprop("gsm.operator.iso-country")
    data_info["Operator Country"] = iso_country.upper() if iso_country else "N/A"

    # Roaming Status
    is_roaming = adb.getprop("gsm.operator.isroaming")
    if is_roaming == "true":
        data_info["Roaming Status"] = f"{ui.Colors.YELLOW}Active (Roaming){ui.Colors.RESET}"
    else:
        data_info["Roaming Status"] = f"{ui.Colors.GREEN}Home Network (Not Roaming){ui.Colors.RESET}"

    # Mobile Data Enabled Setting
    ok_md, md_out = _run_shell("settings get global mobile_data")
    if ok_md and "1" in md_out:
        data_info["Mobile Data Switch"] = f"{ui.Colors.GREEN}ON (Enabled){ui.Colors.RESET}"
    elif ok_md and "0" in md_out:
        data_info["Mobile Data Switch"] = f"{ui.Colors.RED}OFF (Disabled){ui.Colors.RESET}"
    else:
        data_info["Mobile Data Switch"] = "Unknown"

    # Data Connection State from dumpsys telephony.registry
    ok_tele, tele_out = _run_shell("dumpsys telephony.registry")
    if ok_tele and tele_out:
        data_state_match = re.search(r'mDataConnectionState\s*=\s*(\d+)', tele_out)
        if data_state_match:
            state_codes = {"0": "Disconnected", "1": "Connecting", "2": "Connected", "3": "Suspended"}
            st_name = state_codes.get(data_state_match.group(1), data_state_match.group(1))
            color = ui.Colors.GREEN if st_name == "Connected" else ui.Colors.YELLOW
            data_info["Data Connection State"] = f"{color}{st_name}{ui.Colors.RESET}"

        # Signal Strength (dBm / Level)
        signal_match = re.search(r'mSignalStrength\s*=\s*SignalStrength:.*level=(\d+)', tele_out)
        if signal_match:
            level = signal_match.group(1)
            level_bars = {"0": "░░░░ (None)", "1": "█░░░ (Poor)", "2": "██░░ (Moderate)", "3": "███░ (Good)", "4": "████ (Great)"}
            data_info["Cellular Signal Level"] = level_bars.get(level, f"Level {level}/4")

    # APN Information
    ok_apn, apn_out = _run_shell("dumpsys telephony.data_connection")
    if ok_apn and apn_out:
        apn_match = re.search(r'mApnSetting\s*=\s*\[ApnSetting\s+([^,\]]+)', apn_out)
        if apn_match:
            data_info["Active APN Profile"] = apn_match.group(1)

    print()
    ui.print_kv(data_info, indent=4)
    print()
    ui.pause()


# ─── 4. Ping a Host from Device ──────────────────────────────────────────────

def ping_host():
    """Execute ping from the Android device to a target host or IP."""
    if not ensure_device():
        return

    ui.print_sub_banner("Ping Diagnostic Utility", "🏓")

    print(f"  {ui.Colors.BOLD}Select a Target Host or enter custom:{ui.Colors.RESET}\n")
    print(f"  {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Google Public DNS (8.8.8.8)")
    print(f"  {ui.Colors.YELLOW}[2]{ui.Colors.RESET} Cloudflare DNS (1.1.1.1)")
    print(f"  {ui.Colors.YELLOW}[3]{ui.Colors.RESET} Google Search (google.com)")
    print(f"  {ui.Colors.YELLOW}[4]{ui.Colors.RESET} Quad9 DNS (9.9.9.9)")
    print(f"  {ui.Colors.YELLOW}[5]{ui.Colors.RESET} Default Gateway / Local Router")
    print(f"  {ui.Colors.YELLOW}[6]{ui.Colors.RESET} Custom Domain or IP Address")
    print(f"  {ui.Colors.YELLOW}[0]{ui.Colors.RESET} Cancel")
    print()

    choice = ui.get_choice("Select target option")
    target = ""
    if choice == "1":
        target = "8.8.8.8"
    elif choice == "2":
        target = "1.1.1.1"
    elif choice == "3":
        target = "google.com"
    elif choice == "4":
        target = "9.9.9.9"
    elif choice == "5":
        wlan_iface = adb.getprop("wifi.interface") or "wlan0"
        ok_gw, gw_out = _run_shell(f"ip route show dev {wlan_iface}")
        gw_match = re.search(r'default via\s+([0-9.]+)', gw_out) if ok_gw else None
        if gw_match:
            target = gw_match.group(1)
        else:
            ui.error("Could not detect local gateway IP. Please enter it manually.")
            target = ui.get_choice("Enter Gateway IP")
    elif choice == "6":
        target = ui.get_choice("Enter hostname or IP to ping")
    elif choice == "0":
        return
    else:
        ui.error("Invalid choice.")
        ui.pause()
        return

    if not target:
        ui.error("No target specified.")
        ui.pause()
        return

    # Count
    count_str = ui.get_choice("Number of packets to send (1-20, default: 4)")
    count = 4
    if count_str.isdigit():
        c_val = int(count_str)
        if 1 <= c_val <= 20:
            count = c_val

    ui.info(f"Pinging {target} from device ({count} packets)...")
    print()

    start_time = time.time()
    ok_ping, ping_out = _run_shell(f"ping -c {count} -W 3 {target}", timeout=35)
    duration = time.time() - start_time

    if not ok_ping and not ping_out:
        ui.error(f"Ping execution failed: {ping_out}")
        ui.pause()
        return

    # Print raw lines
    for line in ping_out.splitlines():
        if "bytes from" in line:
            print(f"    {ui.Colors.GREEN}●{ui.Colors.RESET} {line}")
        elif "packet loss" in line or "round-trip" in line or "rtt" in line:
            print(f"    {ui.Colors.CYAN}{line}{ui.Colors.RESET}")
        else:
            print(f"    {line}")

    # Parse summary statistics
    loss_match = re.search(r'(\d+)%\s*packet loss', ping_out)
    rtt_match = re.search(r'(?:rtt|round-trip)\s+min/avg/max/(?:mdev|stddev)\s*=\s*([0-9.]+)/([0-9.]+)/([0-9.]+)/([0-9.]+)', ping_out)

    print()
    if loss_match:
        loss_pct = int(loss_match.group(1))
        if loss_pct == 0:
            ui.success(f"Ping successful! 0% packet loss to {target} (Total time: {duration:.2f}s)")
        elif loss_pct < 100:
            ui.warning(f"Partial connectivity: {loss_pct}% packet loss to {target}")
        else:
            ui.error(f"Host unreachable: 100% packet loss to {target}")

    if rtt_match:
        min_rtt, avg_rtt, max_rtt, mdev_rtt = rtt_match.groups()
        headers = ("Min RTT", "Avg RTT", "Max RTT", "StdDev / MDev")
        rows = [(f"{min_rtt} ms", f"{avg_rtt} ms", f"{max_rtt} ms", f"{mdev_rtt} ms")]
        ui.print_table(rows, headers, indent=4)

    print()
    ui.pause()


# ─── 5. DNS Lookup & Resolver Settings ───────────────────────────────────────

def dns_lookup():
    """Inspect configured DNS servers and perform domain name resolution from the device."""
    if not ensure_device():
        return

    ui.print_sub_banner("DNS Lookup & Resolver Information", "🔍")

    # Read DNS Properties
    dns_servers: List[str] = []
    for i in range(1, 9):
        dns_prop = adb.getprop(f"net.dns{i}")
        if dns_prop and dns_prop not in dns_servers:
            dns_servers.append(dns_prop)

    # Read Private DNS Mode
    ok_pdns, pdns_mode = _run_shell("settings get global private_dns_mode")
    ok_spec, pdns_spec = _run_shell("settings get global private_dns_specifier")

    dns_info: Dict[str, str] = {}
    dns_info["Configured DNS Servers"] = ", ".join(dns_servers) if dns_servers else "None (Using network default / system resolver)"

    mode_str = pdns_mode.strip() if ok_pdns and pdns_mode.strip() else "off"
    if mode_str == "hostname":
        spec_str = pdns_spec.strip() if ok_spec else ""
        dns_info["Private DNS (DoT)"] = f"{ui.Colors.GREEN}Strict Provider ({spec_str}){ui.Colors.RESET}"
    elif mode_str == "opportunistic":
        dns_info["Private DNS (DoT)"] = f"{ui.Colors.CYAN}Automatic (Opportunistic){ui.Colors.RESET}"
    else:
        dns_info["Private DNS (DoT)"] = f"{ui.Colors.YELLOW}Off / Standard{ui.Colors.RESET}"

    ui.header("Current Device DNS Configuration:")
    ui.print_kv(dns_info, indent=4)
    print()

    # Perform lookup
    query_domain = ui.get_choice("Enter domain name to resolve (default: google.com)")
    if not query_domain:
        query_domain = "google.com"

    ui.info(f"Resolving '{query_domain}' from device...")

    # Try nslookup or ping -c 1 to resolve
    resolved_ips: List[Tuple[str, str]] = []

    ok_ns, ns_out = _run_shell(f"nslookup {query_domain}")
    if ok_ns and "Address" in ns_out:
        for line in ns_out.splitlines():
            line = line.strip()
            if line.startswith("Address") or line.startswith("Addresses"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    ip_val = parts[1].strip()
                    for ip in ip_val.split():
                        ip_clean = ip.strip()
                        if ip_clean:
                            v_type = "IPv6" if ":" in ip_clean else "IPv4"
                            resolved_ips.append((v_type, ip_clean))
    else:
        # Fallback using ping to extract resolved IP
        ok_p, p_out = _run_shell(f"ping -c 1 -W 2 {query_domain}")
        ip_match = re.search(r'\(([0-9.]+)\)', p_out)
        if ip_match:
            resolved_ips.append(("IPv4", ip_match.group(1)))

    if resolved_ips:
        ui.success(f"Successfully resolved '{query_domain}':")
        headers = ("Type", "Resolved IP Address")
        ui.print_table(resolved_ips, headers, indent=4)
    else:
        ui.warning(f"Could not resolve '{query_domain}' or device utilities (nslookup) are unavailable.")

    print()
    ui.pause()


# ─── 6. View Routing Table ───────────────────────────────────────────────────

def view_routing_table():
    """Display the kernel IPv4 and IPv6 routing tables."""
    if not ensure_device():
        return

    ui.print_sub_banner("Kernel Routing Table", "🗺️")
    ui.info("Querying IPv4 and IPv6 routes...")

    ok_v4, v4_out = _run_shell("ip route show")
    ok_v6, v6_out = _run_shell("ip -6 route show")

    table_rows: List[Tuple[str, str, str, str]] = []

    if ok_v4 and v4_out:
        for line in v4_out.splitlines():
            line = line.strip()
            if not line:
                continue
            dest = "default" if line.startswith("default") else line.split()[0]
            gw = "—"
            dev = "—"
            flags = []

            if "via " in line:
                gw = line.split("via ")[1].split()[0]
            if "dev " in line:
                dev = line.split("dev ")[1].split()[0]
            if "proto " in line:
                flags.append(f"proto {line.split('proto ')[1].split()[0]}")
            if "scope " in line:
                flags.append(f"scope {line.split('scope ')[1].split()[0]}")
            if "metric " in line:
                flags.append(f"metric {line.split('metric ')[1].split()[0]}")

            table_rows.append((dest, gw, dev, " ".join(flags) or "direct"))

    if table_rows:
        ui.header("IPv4 Routes:")
        headers = ("Destination", "Gateway", "Interface", "Attributes")
        ui.print_table(table_rows, headers, indent=4)
    else:
        # Fallback to cat /proc/net/route
        ok_proc, proc_out = _run_shell("cat /proc/net/route")
        if ok_proc and proc_out:
            p_rows = []
            for line in proc_out.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 8:
                    iface = parts[0]
                    dest_ip = _decode_hex_ip(parts[1])
                    gw_ip = _decode_hex_ip(parts[2])
                    mask_ip = _decode_hex_ip(parts[7])
                    p_rows.append((f"{dest_ip}/{mask_ip}", gw_ip, iface, f"Flags: {parts[3]}"))
            if p_rows:
                ui.header("IPv4 Routes (/proc/net/route):")
                ui.print_table(p_rows, ("Destination / Mask", "Gateway", "Interface", "Flags"), indent=4)
        else:
            ui.warning("No IPv4 routes found.")

    # IPv6 Table
    if ok_v6 and v6_out.strip():
        v6_rows: List[Tuple[str, str, str]] = []
        for line in v6_out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            dest = parts[0]
            dev = line.split("dev ")[1].split()[0] if "dev " in line else "—"
            gw = line.split("via ")[1].split()[0] if "via " in line else "—"
            v6_rows.append((dest, gw, dev))
        if v6_rows:
            print()
            ui.header("IPv6 Routes (Top 10):")
            ui.print_table(v6_rows[:10], ("Destination Prefix", "Gateway / Next Hop", "Interface"), indent=4)

    print()
    ui.pause()


# ─── 7. View Open Ports (netstat) ────────────────────────────────────────────

def view_open_ports():
    """Display listening TCP and UDP sockets and open network ports."""
    if not ensure_device():
        return

    ui.print_sub_banner("Open Ports & Listening Sockets", "🚪")
    ui.info("Scanning listening TCP and UDP endpoints...")

    ports_found: List[Tuple[str, str, str, str]] = []

    # Attempt netstat -tuln
    ok_ns, ns_out = _run_shell("netstat -tuln")
    if ok_ns and ns_out and "Proto" in ns_out:
        for line in ns_out.splitlines():
            line = line.strip()
            if line.startswith("tcp") or line.startswith("udp"):
                parts = line.split()
                if len(parts) >= 4:
                    proto = parts[0]
                    local_addr = parts[3]
                    state = parts[5] if len(parts) >= 6 else "LISTEN"
                    port_num = local_addr.split(":")[-1] if ":" in local_addr else ""
                    service = _resolve_port_name(int(port_num)) if port_num.isdigit() else ""
                    ports_found.append((proto, local_addr, state, service or "—"))

    # Fallback to parsing /proc/net/tcp and /proc/net/udp if netstat is blocked
    if not ports_found:
        for proto, proc_file in (("tcp", "/proc/net/tcp"), ("tcp6", "/proc/net/tcp6"), ("udp", "/proc/net/udp")):
            ok_p, p_out = _run_shell(f"cat {proc_file}")
            if ok_p and p_out:
                for line in p_out.splitlines()[1:]:
                    parts = line.split()
                    if len(parts) >= 4:
                        local_hex = parts[1]
                        state_hex = parts[3]
                        # 0A = TCP_LISTEN (10), 07 = UDP
                        if state_hex in ("0A", "07"):
                            if ":" in local_hex:
                                hex_ip, hex_port = local_hex.split(":")
                                dec_ip = _decode_hex_ip(hex_ip)
                                dec_port = int(hex_port, 16)
                                service = _resolve_port_name(dec_port)
                                state_lbl = "LISTEN" if proto.startswith("tcp") else "UNCONN"
                                ports_found.append((proto.upper(), f"{dec_ip}:{dec_port}", state_lbl, service or "—"))

    if ports_found:
        ui.success(f"Discovered {len(ports_found)} open/listening ports:")
        headers = ("Proto", "Local Address:Port", "State", "Known Service")
        ui.print_table(ports_found, headers, indent=4)
    else:
        ui.warning("No listening ports detected or permission was restricted by SELinux.")

    print()
    ui.pause()


# ─── 8. View Network Interfaces ──────────────────────────────────────────────

def view_network_interfaces():
    """List all physical and virtual network interfaces, their status, MTU, and IP bindings."""
    if not ensure_device():
        return

    ui.print_sub_banner("Network Interfaces Overview", "🔌")

    ok_ip, ip_out = _run_shell("ip addr show")
    if not ok_ip or not ip_out:
        ui.error("Unable to execute 'ip addr show'.")
        ui.pause()
        return

    interfaces: List[Dict[str, Any]] = []
    current_iface: Optional[Dict[str, Any]] = None

    for line in ip_out.splitlines():
        # Match header line e.g., "1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 ... state UNKNOWN"
        hdr_match = re.match(r'^\d+:\s+([^:@]+)[:@].*<([^>]+)>\s+mtu\s+(\d+).*state\s+(\w+)', line)
        if hdr_match:
            if current_iface:
                interfaces.append(current_iface)
            name = hdr_match.group(1)
            flags = hdr_match.group(2)
            mtu = hdr_match.group(3)
            state = hdr_match.group(4)
            current_iface = {
                "name": name,
                "flags": flags,
                "mtu": mtu,
                "state": state,
                "mac": "—",
                "ipv4": [],
                "ipv6": [],
            }
            continue

        if current_iface:
            mac_match = re.search(r'link/ether\s+([0-9a-fA-F:]{17})', line)
            if mac_match:
                current_iface["mac"] = mac_match.group(1)

            inet_match = re.search(r'inet\s+([0-9.]+/\d+)', line)
            if inet_match:
                current_iface["ipv4"].append(inet_match.group(1))

            inet6_match = re.search(r'inet6\s+([0-9a-fA-F:]+/\d+)', line)
            if inet6_match:
                current_iface["ipv6"].append(inet6_match.group(1))

    if current_iface:
        interfaces.append(current_iface)

    table_rows: List[Tuple[str, str, str, str, str]] = []
    for iface in interfaces:
        state_color = ui.Colors.GREEN if iface["state"] == "UP" else (ui.Colors.YELLOW if iface["state"] == "UNKNOWN" else ui.Colors.RED)
        state_formatted = f"{state_color}{iface['state']}{ui.Colors.RESET}"
        ipv4_str = ", ".join(iface["ipv4"]) if iface["ipv4"] else "—"
        table_rows.append((
            iface["name"],
            state_formatted,
            iface["mtu"],
            iface["mac"],
            ipv4_str,
        ))

    headers = ("Interface", "Status", "MTU", "MAC Address", "Assigned IPv4")
    ui.print_table(table_rows, headers, indent=4)
    print()
    ui.pause()


# ─── 9. Data Usage Statistics & Live Throughput ──────────────────────────────

def data_usage_stats():
    """Display cumulative RX/TX bytes per interface with optional real-time throughput monitor."""
    if not ensure_device():
        return

    ui.print_sub_banner("Network Data Usage Statistics", "📊")

    def _read_proc_net_dev() -> Dict[str, Dict[str, int]]:
        ok_dev, dev_out = _run_shell("cat /proc/net/dev")
        stats: Dict[str, Dict[str, int]] = {}
        if ok_dev and dev_out:
            for line in dev_out.splitlines()[2:]:
                if ":" in line:
                    iface, counts = line.split(":", 1)
                    iface = iface.strip()
                    vals = counts.split()
                    if len(vals) >= 16:
                        stats[iface] = {
                            "rx_bytes": int(vals[0]),
                            "rx_packets": int(vals[1]),
                            "rx_errs": int(vals[2]),
                            "rx_drop": int(vals[3]),
                            "tx_bytes": int(vals[8]),
                            "tx_packets": int(vals[9]),
                            "tx_errs": int(vals[10]),
                            "tx_drop": int(vals[11]),
                        }
        return stats

    initial_stats = _read_proc_net_dev()
    if not initial_stats:
        ui.error("Unable to read /proc/net/dev network statistics.")
        ui.pause()
        return

    rows: List[Tuple[str, str, str, str, str]] = []
    total_rx = 0
    total_tx = 0

    for iface, data in initial_stats.items():
        if data["rx_bytes"] == 0 and data["tx_bytes"] == 0:
            continue
        total_rx += data["rx_bytes"]
        total_tx += data["tx_bytes"]
        rows.append((
            iface,
            _format_bytes(data["rx_bytes"]),
            f"{data['rx_packets']:,}",
            _format_bytes(data["tx_bytes"]),
            f"{data['tx_packets']:,}",
        ))

    headers = ("Interface", "Received (RX)", "RX Packets", "Transmitted (TX)", "TX Packets")
    ui.print_table(rows, headers, indent=4)
    print()
    ui.print_kv({
        "Total Data Received (RX)": _format_bytes(total_rx),
        "Total Data Transmitted (TX)": _format_bytes(total_tx),
        "Total Network I/O": _format_bytes(total_rx + total_tx),
    }, indent=4)
    print()

    # Prompt for real-time throughput monitor
    if ui.confirm("Would you like to monitor real-time network throughput for 5 seconds?"):
        ui.info("Measuring active bandwidth...")
        time.sleep(3.0)
        final_stats = _read_proc_net_dev()

        speed_rows: List[Tuple[str, str, str]] = []
        for iface in initial_stats:
            if iface in final_stats:
                rx_delta = final_stats[iface]["rx_bytes"] - initial_stats[iface]["rx_bytes"]
                tx_delta = final_stats[iface]["tx_bytes"] - initial_stats[iface]["tx_bytes"]
                if rx_delta > 0 or tx_delta > 0:
                    rx_speed = f"{_format_bytes(int(rx_delta / 3.0))}/s"
                    tx_speed = f"{_format_bytes(int(tx_delta / 3.0))}/s"
                    speed_rows.append((iface, rx_speed, tx_speed))

        if speed_rows:
            print()
            ui.header("Live Throughput (past 3s):")
            ui.print_table(speed_rows, ("Interface", "Download Rate (RX)", "Upload Rate (TX)"), indent=4)
        else:
            ui.info("Network was idle during the sample window.")

    print()
    ui.pause()


# ─── 10. Test HTTP / HTTPS Connectivity ──────────────────────────────────────

def test_http_connectivity():
    """Test HTTP and HTTPS network endpoints using curl / wget from the device."""
    if not ensure_device():
        return

    ui.print_sub_banner("HTTP / HTTPS Connectivity Diagnostics", "🌍")

    print(f"  {ui.Colors.BOLD}Select a Connectivity Test Target:{ui.Colors.RESET}\n")
    print(f"  {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Google Captive Portal Check (generate_204)")
    print(f"  {ui.Colors.YELLOW}[2]{ui.Colors.RESET} Cloudflare Trace API (1.1.1.1/cdn-cgi/trace)")
    print(f"  {ui.Colors.YELLOW}[3]{ui.Colors.RESET} Google HTTPS Homepage (https://www.google.com)")
    print(f"  {ui.Colors.YELLOW}[4]{ui.Colors.RESET} Cloudflare DNS-over-HTTPS (https://cloudflare-dns.com)")
    print(f"  {ui.Colors.YELLOW}[5]{ui.Colors.RESET} Custom URL")
    print(f"  {ui.Colors.YELLOW}[0]{ui.Colors.RESET} Cancel")
    print()

    choice = ui.get_choice("Select test endpoint")
    url = ""
    expected_code = 200

    if choice == "1":
        url = "http://connectivitycheck.gstatic.com/generate_204"
        expected_code = 204
    elif choice == "2":
        url = "https://1.1.1.1/cdn-cgi/trace"
    elif choice == "3":
        url = "https://www.google.com"
    elif choice == "4":
        url = "https://cloudflare-dns.com"
    elif choice == "5":
        url = ui.get_choice("Enter full URL (including http:// or https://)")
    elif choice == "0":
        return
    else:
        ui.error("Invalid choice.")
        ui.pause()
        return

    if not url:
        ui.error("No URL provided.")
        ui.pause()
        return

    ui.info(f"Testing reachability of: {url} ...")

    # Command using curl
    curl_cmd = f"curl -s -o /dev/null -w 'HTTP_CODE:%{{http_code}}\\nTIME_DNS:%{{time_namelookup}}\\nTIME_CONNECT:%{{time_connect}}\\nTIME_TOTAL:%{{time_total}}\\n' --max-time 8 '{url}'"
    ok_curl, curl_out = _run_raw_shell(curl_cmd)

    if ok_curl and "HTTP_CODE:" in curl_out:
        code_match = re.search(r'HTTP_CODE:(\d+)', curl_out)
        dns_match = re.search(r'TIME_DNS:([0-9.]+)', curl_out)
        conn_match = re.search(r'TIME_CONNECT:([0-9.]+)', curl_out)
        total_match = re.search(r'TIME_TOTAL:([0-9.]+)', curl_out)

        http_code = int(code_match.group(1)) if code_match else 0
        dns_time = float(dns_match.group(1)) if dns_match else 0.0
        conn_time = float(conn_match.group(1)) if conn_match else 0.0
        total_time = float(total_match.group(1)) if total_match else 0.0

        if http_code in (200, 204, 301, 302):
            ui.success(f"HTTP Request Succeeded! Response Code: {http_code}")
        elif http_code == 0:
            ui.error("HTTP Request Failed (Timeout, DNS failure, or SSL error).")
        else:
            ui.warning(f"HTTP Server Returned Status Code: {http_code}")

        res_data = {
            "Target Endpoint": url,
            "HTTP Response Code": f"{http_code} ({'OK / No Content' if http_code in (200, 204) else 'Redirect / Error'})",
            "DNS Resolution Latency": f"{dns_time * 1000:.1f} ms",
            "TCP Connect Latency": f"{conn_time * 1000:.1f} ms",
            "Total Round-Trip Latency": f"{total_time * 1000:.1f} ms",
        }
        print()
        ui.print_kv(res_data, indent=4)
    else:
        # Fallback to wget test
        ok_wget, wget_out = _run_shell(f"wget -q -O - -T 5 {url}")
        if ok_wget:
            ui.success(f"HTTP Request via wget succeeded for {url}")
        else:
            ui.error(f"HTTP test failed or curl/wget is not supported on this device ROM.")

    print()
    ui.pause()


# ─── 11. View Saved Wi-Fi Networks ───────────────────────────────────────────

def view_wifi_saved_networks():
    """List configured and saved Wi-Fi networks stored on the device."""
    if not ensure_device():
        return

    ui.print_sub_banner("Saved Wi-Fi Networks", "💾")
    ui.info("Querying configured Wi-Fi network profiles...")

    # Attempt cmd wifi list-networks (Android 10+)
    ok_list, list_out = _run_shell("cmd wifi list-networks")
    networks: List[Tuple[str, str, str, str]] = []

    if ok_list and list_out and "Network ID" in list_out:
        for line in list_out.splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 3:
                net_id = parts[0]
                ssid = parts[1]
                security = parts[2]
                status = parts[3] if len(parts) >= 4 else "SAVED"
                networks.append((net_id, ssid, security, status))

    # Fallback to parsing dumpsys wifi for configured networks
    if not networks:
        ok_dump, dump_out = _run_shell("dumpsys wifi")
        if ok_dump and dump_out:
            blocks = re.findall(r'NetworkId\s*(\d+).*?SSID:\s*"([^"]+)"(?:.*?KeyMgmt:\s*([^\s\n]+))?', dump_out, re.DOTALL)
            for net_id, ssid, key_mgmt in blocks:
                networks.append((net_id, ssid, key_mgmt or "WPA2_PSK", "CONFIGURED"))

    if networks:
        ui.success(f"Found {len(networks)} saved Wi-Fi network(s):")
        headers = ("Network ID", "SSID", "Security Type", "Status")
        ui.print_table(networks, headers, indent=4)
    else:
        ui.warning("No saved Wi-Fi networks found, or access requires elevated/root privileges.")

    print()
    ui.pause()


# ─── 12. Toggle Wi-Fi Power ──────────────────────────────────────────────────

def toggle_wifi():
    """Enable, disable, toggle, or reconnect the device's Wi-Fi radio."""
    if not ensure_device():
        return

    ui.print_sub_banner("Wi-Fi Power & State Control", "⚡")

    ok_st, st_out = _run_shell("settings get global wifi_on")
    is_on = "1" in st_out if ok_st else False

    current_state_str = f"{ui.Colors.GREEN}ENABLED (ON){ui.Colors.RESET}" if is_on else f"{ui.Colors.RED}DISABLED (OFF){ui.Colors.RESET}"
    print(f"  Current Wi-Fi State: {current_state_str}\n")

    print(f"  {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Turn Wi-Fi ON")
    print(f"  {ui.Colors.YELLOW}[2]{ui.Colors.RESET} Turn Wi-Fi OFF")
    print(f"  {ui.Colors.YELLOW}[3]{ui.Colors.RESET} Toggle Wi-Fi (flip state)")
    print(f"  {ui.Colors.YELLOW}[4]{ui.Colors.RESET} Trigger Wi-Fi Reconnect")
    print(f"  {ui.Colors.YELLOW}[5]{ui.Colors.RESET} Trigger Wi-Fi Network Scan")
    print(f"  {ui.Colors.YELLOW}[0]{ui.Colors.RESET} Cancel")
    print()

    choice = ui.get_choice("Select Wi-Fi control action")
    if choice == "1":
        ui.info("Enabling Wi-Fi radio...")
        _run_shell("svc wifi enable")
        _run_shell("cmd wifi set-wifi-enabled enabled")
        time.sleep(1)
        ui.success("Wi-Fi enabled.")
    elif choice == "2":
        ui.info("Disabling Wi-Fi radio...")
        _run_shell("svc wifi disable")
        _run_shell("cmd wifi set-wifi-enabled disabled")
        time.sleep(1)
        ui.success("Wi-Fi disabled.")
    elif choice == "3":
        if is_on:
            ui.info("Disabling Wi-Fi radio...")
            _run_shell("svc wifi disable")
            _run_shell("cmd wifi set-wifi-enabled disabled")
        else:
            ui.info("Enabling Wi-Fi radio...")
            _run_shell("svc wifi enable")
            _run_shell("cmd wifi set-wifi-enabled enabled")
        time.sleep(1)
        ui.success("Wi-Fi state toggled.")
    elif choice == "4":
        ui.info("Reconnecting Wi-Fi...")
        _run_shell("cmd wifi reconnect")
        ui.success("Wi-Fi reconnect initiated.")
    elif choice == "5":
        ui.info("Starting Wi-Fi scan...")
        _run_shell("cmd wifi start-scan")
        ui.success("Wi-Fi scan initiated.")
    elif choice == "0":
        return
    else:
        ui.error("Invalid choice.")

    print()
    ui.pause()


# ─── 13. View Active Connections ─────────────────────────────────────────────

def view_active_connections():
    """Display active established, syn-sent, or close-wait TCP/UDP connections."""
    if not ensure_device():
        return

    ui.print_sub_banner("Active Network Connections", "🔗")
    ui.info("Querying active socket connections...")

    active_conns: List[Tuple[str, str, str, str, str]] = []

    # Run netstat -an
    ok_ns, ns_out = _run_shell("netstat -an")
    if ok_ns and ns_out:
        for line in ns_out.splitlines():
            line = line.strip()
            if line.startswith("tcp") or line.startswith("udp"):
                parts = line.split()
                if len(parts) >= 5:
                    proto = parts[0]
                    local_addr = parts[3]
                    foreign_addr = parts[4]
                    state = parts[5] if len(parts) >= 6 else ("ESTABLISHED" if proto.startswith("tcp") else "ASSOCIATED")

                    # Filter out purely listening sockets to focus on active connections
                    if state in ("LISTEN", "UNCONN") or foreign_addr.startswith("0.0.0.0:") or foreign_addr == "*:*":
                        continue

                    remote_port = foreign_addr.split(":")[-1] if ":" in foreign_addr else ""
                    service = _resolve_port_name(int(remote_port)) if remote_port.isdigit() else ""
                    active_conns.append((proto.upper(), local_addr, foreign_addr, state, service or "—"))

    # Fallback to /proc/net/tcp parsing
    if not active_conns:
        ok_proc, proc_out = _run_shell("cat /proc/net/tcp")
        if ok_proc and proc_out:
            for line in proc_out.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 4:
                    state_hex = parts[3]
                    # 01 = ESTABLISHED, 02 = SYN_SENT, 06 = TIME_WAIT, 08 = CLOSE_WAIT
                    state_map = {"01": "ESTABLISHED", "02": "SYN_SENT", "06": "TIME_WAIT", "08": "CLOSE_WAIT"}
                    if state_hex in state_map:
                        local_ip_p = parts[1]
                        rem_ip_p = parts[2]
                        if ":" in local_ip_p and ":" in rem_ip_p:
                            l_ip, l_port = local_ip_p.split(":")
                            r_ip, r_port = rem_ip_p.split(":")
                            l_str = f"{_decode_hex_ip(l_ip)}:{int(l_port, 16)}"
                            r_str = f"{_decode_hex_ip(r_ip)}:{int(r_port, 16)}"
                            r_port_dec = int(r_port, 16)
                            service = _resolve_port_name(r_port_dec)
                            active_conns.append(("TCP", l_str, r_str, state_map[state_hex], service or "—"))

    if active_conns:
        ui.success(f"Found {len(active_conns)} active socket connection(s):")
        headers = ("Proto", "Local Endpoint", "Remote Endpoint", "State", "Service")
        ui.print_table(active_conns, headers, indent=4)
    else:
        ui.info("No active outgoing or remote socket connections detected.")

    print()
    ui.pause()


# ─── 14. Network Diagnostics Scorecard (All-in-One) ──────────────────────────

def network_diagnostics_summary():
    """Run an automated end-to-end network health check and display a scorecard."""
    if not ensure_device():
        return

    ui.print_sub_banner("Automated Network Diagnostics Scorecard", "🩺")
    ui.info("Executing comprehensive connectivity health checks...")
    print()

    tests: List[Tuple[str, str, str]] = []

    # 1. Wi-Fi Subsystem Check
    ok_wifi_st, wifi_st = _run_shell("settings get global wifi_on")
    wifi_on = "1" in wifi_st if ok_wifi_st else False
    tests.append((
        "Wi-Fi Radio",
        f"{ui.Colors.GREEN}ENABLED{ui.Colors.RESET}" if wifi_on else f"{ui.Colors.YELLOW}DISABLED{ui.Colors.RESET}",
        "Radio is powered on" if wifi_on else "Wi-Fi turned off"
    ))

    # 2. Local IP Allocation
    wlan_iface = adb.getprop("wifi.interface") or "wlan0"
    ok_ip, ip_out = _run_shell(f"ip -4 addr show {wlan_iface}")
    has_ip = "inet " in ip_out if ok_ip else False
    tests.append((
        "Local IP Address",
        f"{ui.Colors.GREEN}PASS{ui.Colors.RESET}" if has_ip else f"{ui.Colors.RED}FAIL{ui.Colors.RESET}",
        "DHCP IP assigned" if has_ip else "No IPv4 address on wlan interface"
    ))

    # 3. Default Gateway Ping
    ok_gw, gw_out = _run_shell(f"ip route show dev {wlan_iface}")
    gw_match = re.search(r'default via\s+([0-9.]+)', gw_out) if ok_gw else None
    if gw_match:
        gw_ip = gw_match.group(1)
        ok_gw_ping, _ = _run_shell(f"ping -c 1 -W 2 {gw_ip}")
        tests.append((
            "Gateway Reachability",
            f"{ui.Colors.GREEN}PASS{ui.Colors.RESET}" if ok_gw_ping else f"{ui.Colors.YELLOW}WARN{ui.Colors.RESET}",
            f"Gateway {gw_ip} responded" if ok_gw_ping else f"Gateway {gw_ip} did not reply to ICMP"
        ))
    else:
        tests.append(("Gateway Reachability", f"{ui.Colors.RED}FAIL{ui.Colors.RESET}", "No default route found"))

    # 4. Public Internet Ping
    ok_pub_ping, _ = _run_shell("ping -c 2 -W 3 8.8.8.8")
    tests.append((
        "Internet ICMP (8.8.8.8)",
        f"{ui.Colors.GREEN}PASS{ui.Colors.RESET}" if ok_pub_ping else f"{ui.Colors.RED}FAIL{ui.Colors.RESET}",
        "Global internet reachable" if ok_pub_ping else "No response from public DNS"
    ))

    # 5. DNS Resolution
    ok_dns, dns_out = _run_shell("ping -c 1 -W 3 google.com")
    dns_pass = ok_dns and "(" in dns_out
    tests.append((
        "DNS Name Resolution",
        f"{ui.Colors.GREEN}PASS{ui.Colors.RESET}" if dns_pass else f"{ui.Colors.RED}FAIL{ui.Colors.RESET}",
        "Resolved google.com" if dns_pass else "Domain name resolution failed"
    ))

    # 6. HTTP Connectivity
    ok_http, http_out = _run_raw_shell("curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://connectivitycheck.gstatic.com/generate_204")
    http_pass = "204" in http_out or "200" in http_out
    tests.append((
        "HTTP Reachability (Captive Check)",
        f"{ui.Colors.GREEN}PASS{ui.Colors.RESET}" if http_pass else f"{ui.Colors.YELLOW}WARN{ui.Colors.RESET}",
        "Internet HTTP 204 verified" if http_pass else "HTTP check failed (Captive portal?)"
    ))

    # Print results
    headers = ("Diagnostic Check", "Result", "Notes")
    ui.print_table(tests, headers, indent=4)
    print()
    ui.pause()


# ─── Public Entry Menu ───────────────────────────────────────────────────────

def network_tools_menu():
    """Main interactive loop for Network Tools module."""
    menu_options = [
        "Wi-Fi Information (SSID, RSSI, Band, Speed)",
        "Wi-Fi IP Address & Interface Details",
        "Cellular & Mobile Data Information",
        "Ping a Host / IP from Device",
        "DNS Lookup & Private DNS Resolver",
        "View Kernel Routing Table",
        "View Open Ports (netstat)",
        "View Network Interfaces Overview",
        "Data Usage Stats & Live Throughput",
        "Test HTTP / HTTPS Connectivity",
        "View Saved Wi-Fi Networks",
        "Toggle Wi-Fi Power (On / Off / Reconnect)",
        "View Active Network Connections",
        "Automated Network Diagnostics Scorecard",
    ]

    while True:
        ui.clear()
        ui.print_banner()
        ui.print_device_status(adb.serial)
        ui.print_menu("Network Tools & Diagnostics", menu_options, columns=2)

        choice = ui.get_choice("Select network option")

        if choice == "0":
            break
        elif choice == "1":
            show_wifi_info()
        elif choice == "2":
            show_wifi_ip()
        elif choice == "3":
            show_mobile_data_info()
        elif choice == "4":
            ping_host()
        elif choice == "5":
            dns_lookup()
        elif choice == "6":
            view_routing_table()
        elif choice == "7":
            view_open_ports()
        elif choice == "8":
            view_network_interfaces()
        elif choice == "9":
            data_usage_stats()
        elif choice == "10":
            test_http_connectivity()
        elif choice == "11":
            view_wifi_saved_networks()
        elif choice == "12":
            toggle_wifi()
        elif choice == "13":
            view_active_connections()
        elif choice == "14":
            network_diagnostics_summary()
        else:
            ui.error("Invalid choice. Please select an option from the menu.")
            ui.pause()
