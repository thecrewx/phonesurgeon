"""
modules/device_controls.py — Device controls and hardware configuration for DroidCommander.

Provides quick access to power states, reboot modes, wireless ADB configuration,
screen and brightness management, airplane mode, input simulation, and shell access.
"""

from typing import Optional
import re
import time
from datetime import datetime

from core.adb import adb
from core import ui
from core.device import ensure_device


# ─── Helper: Query Display Status ─────────────────────────────────────────────

def _get_screen_state() -> str:
    """Return 'ON', 'OFF', or 'UNKNOWN' based on power manager dumpsys."""
    ok, out = adb.run(["shell", "dumpsys", "power"])
    if not ok or not out:
        return "UNKNOWN"

    for line in out.splitlines():
        line_clean = line.strip()
        if "mWakefulness=" in line_clean:
            # e.g., mWakefulness=Awake, mWakefulness=Asleep, mWakefulness=Dozing
            val = line_clean.split("mWakefulness=")[-1].split()[0]
            return "ON" if "Awake" in val else "OFF"
        if "Display Power: state=" in line_clean:
            val = line_clean.split("Display Power: state=")[-1].split()[0]
            return val.upper()
        if "mHoldingDisplaySuspendBlocker=" in line_clean:
            if "true" in line_clean.lower():
                return "ON"
            elif "false" in line_clean.lower():
                return "OFF"
    return "UNKNOWN"


def _get_wlan_ip() -> Optional[str]:
    """Detect and return the Wi-Fi IP address (wlan0) of the device."""
    # Method 1: ip -f inet addr show wlan0
    ok, out = adb.run(["shell", "ip", "-f", "inet", "addr", "show", "wlan0"])
    if ok and out:
        match = re.search(r"inet\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", out)
        if match:
            return match.group(1)

    # Method 2: getprop dhcp.wlan0.ipaddress
    ip_prop = adb.getprop("dhcp.wlan0.ipaddress").strip()
    if ip_prop and re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip_prop):
        return ip_prop

    # Method 3: ip route show
    ok, out = adb.run(["shell", "ip", "route", "show"])
    if ok and out:
        for line in out.splitlines():
            if "wlan0" in line and "src" in line:
                parts = line.split()
                if "src" in parts:
                    idx = parts.index("src")
                    if idx + 1 < len(parts):
                        return parts[idx + 1]

    # Method 4: ifconfig wlan0
    ok, out = adb.run(["shell", "ifconfig", "wlan0"])
    if ok and out:
        match = re.search(r"inet\s+addr:(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", out)
        if match:
            return match.group(1)

    return None


# ─── 1. Reboot Options ────────────────────────────────────────────────────────

def reboot_normal():
    """Reboot the device normally."""
    if not ensure_device():
        return

    ui.header("Reboot Device (Normal)")
    print()
    ui.warning(f"This will reboot device '{adb.serial}'.")
    if not ui.confirm("Are you sure you want to reboot now?"):
        ui.info("Reboot cancelled.")
        return

    ui.info("Sending reboot command...")
    ok, out = adb.run(["reboot"])
    if ok:
        ui.success("Reboot command accepted. The device is restarting.")
        ui.info("ADB connection will temporarily disconnect.")
    else:
        ui.error(f"Reboot failed: {out}")


def reboot_recovery():
    """Reboot the device into Recovery mode."""
    if not ensure_device():
        return

    ui.header("Reboot to Recovery Mode")
    print()
    ui.warning("Recovery mode is used for flashing ZIP packages, ADB sideload, wiping cache/data.")
    if not ui.confirm(f"Reboot '{adb.serial}' to Recovery?"):
        ui.info("Operation cancelled.")
        return

    ui.info("Sending reboot recovery command...")
    ok, out = adb.run(["reboot", "recovery"])
    if ok:
        ui.success("Rebooting to Recovery mode...")
    else:
        ui.error(f"Failed to reboot to recovery: {out}")


def reboot_bootloader():
    """Reboot the device into Bootloader (Fastboot) mode."""
    if not ensure_device():
        return

    ui.header("Reboot to Bootloader / Fastboot")
    print()
    ui.warning("Bootloader mode allows flashing partitions using fastboot commands.")
    if not ui.confirm(f"Reboot '{adb.serial}' to Bootloader?"):
        ui.info("Operation cancelled.")
        return

    ui.info("Sending reboot bootloader command...")
    ok, out = adb.run(["reboot", "bootloader"])
    if ok:
        ui.success("Rebooting to Bootloader (Fastboot mode)...")
        ui.info("Once in bootloader, use Fastboot Tools to interact with the device.")
    else:
        ui.error(f"Failed to reboot to bootloader: {out}")


def soft_reboot():
    """Perform a soft reboot (userspace hot restart by restarting Zygote)."""
    if not ensure_device():
        return

    ui.header("Soft Reboot (Hot Restart)")
    print()
    ui.info("A soft reboot restarts the Android framework (Zygote & SystemUI)")
    ui.info("without cycling the Linux kernel or hardware power.")
    print()
    if not ui.confirm("Perform soft reboot now?"):
        ui.info("Operation cancelled.")
        return

    ui.info("Attempting framework restart (ctl.restart zygote)...")
    ok, out = adb.run(["shell", "setprop", "ctl.restart", "zygote"])

    # Fallback to svc power reboot if setprop didn't work or had permission issue
    if not ok or "permission denied" in out.lower():
        ui.warning("setprop restricted; attempting fallback via svc power reboot...")
        ok2, out2 = adb.run(["shell", "svc", "power", "reboot"])
        if ok2:
            ui.success("Soft reboot initiated via power service.")
            return

    if ok:
        ui.success("Soft reboot initiated. SystemUI will reload shortly.")
    else:
        ui.error(f"Soft reboot failed: {out}")
        ui.info("Note: Soft reboot typically requires root or privileged shell access.")


# ─── 2. WiFi ADB Management ───────────────────────────────────────────────────

def enable_wifi_adb():
    """Enable ADB over TCP/IP on a specified port and show connection details."""
    if not ensure_device():
        return

    ui.header("Enable WiFi ADB (TCP/IP)")
    print()
    default_port = "5555"
    port_input = ui.get_choice(f"Enter TCP/IP port [{default_port}]")
    port = port_input if port_input else default_port

    if not port.isdigit() or not (1 <= int(port) <= 65535):
        ui.error("Invalid port number. Must be between 1 and 65535.")
        return

    ui.info(f"Enabling ADB over TCP/IP on port {port}...")
    ok, out = adb.run(["tcpip", port])
    if not ok:
        ui.error(f"Failed to enable TCP/IP mode: {out}")
        return

    ui.success(f"WiFi ADB successfully enabled on port {port}!")
    print()

    # Query device IP
    wlan_ip = _get_wlan_ip()
    if wlan_ip:
        ui.header("Connection Details:")
        ui.print_kv({
            "Device Wi-Fi IP": wlan_ip,
            "Target Port": port,
            "Connect Command": f"adb connect {wlan_ip}:{port}",
            "Status": "Ready for wireless connection"
        })
        print()
        ui.info("You can now unplug the USB cable if desired.")
        if ui.confirm(f"Connect to {wlan_ip}:{port} wirelessly now?"):
            ok_conn, conn_out = adb.run(["connect", f"{wlan_ip}:{port}"])
            if ok_conn and "connected" in conn_out.lower():
                ui.success(f"Connected: {conn_out}")
                if ui.confirm(f"Switch active target to {wlan_ip}:{port}?"):
                    adb.serial = f"{wlan_ip}:{port}"
                    ui.success(f"Active device set to {adb.serial}")
            else:
                ui.warning(f"Connection response: {conn_out}")
    else:
        ui.warning("Could not auto-detect Wi-Fi IP. Ensure device is connected to Wi-Fi.")
        ui.info(f"Once you find the device IP in Settings > About > Status, run: adb connect <IP>:{port}")


def connect_wifi_device():
    """Connect to an Android device over WiFi via IP and port."""
    ui.header("Connect via WiFi (IP:Port)")
    print()
    ip = ui.get_choice("Enter device IP address (e.g., 192.168.1.100)")
    if not ip:
        ui.info("Operation cancelled.")
        return

    port_input = ui.get_choice("Enter port [5555]")
    port = port_input if port_input else "5555"

    endpoint = f"{ip}:{port}"
    ui.info(f"Connecting to {endpoint}...")
    ok, out = adb.run(["connect", endpoint], timeout=15)

    if ok and ("connected" in out.lower() or "already connected" in out.lower()):
        ui.success(f"Connection established: {out}")
        if ui.confirm(f"Set '{endpoint}' as the active device?"):
            adb.serial = endpoint
            ui.success(f"Active target set to {adb.serial}")
    else:
        ui.error(f"Failed to connect to {endpoint}: {out}")
        ui.info("Ensure the device has WiFi ADB enabled ('adb tcpip 5555') and is on the same network.")


def disconnect_wifi_device():
    """Disconnect one or all WiFi ADB devices."""
    ui.header("Disconnect WiFi Device")
    print()

    # List devices to see which ones are WiFi endpoints
    devices = adb.list_devices()
    wifi_devs = [d for d in devices if ":" in d["serial"]]

    print("  Options:")
    print(f"    {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Disconnect ALL WiFi endpoints")
    if wifi_devs:
        for idx, dev in enumerate(wifi_devs, 2):
            print(f"    {ui.Colors.YELLOW}[{idx}]{ui.Colors.RESET} Disconnect {dev['serial']} ({dev.get('model', 'device')})")
    print(f"    {ui.Colors.YELLOW}[9]{ui.Colors.RESET} Disconnect custom IP:Port")
    print()

    choice = ui.get_choice("Select option")
    if choice == "1":
        ui.info("Disconnecting all devices...")
        ok, out = adb.run(["disconnect"])
        if ok:
            ui.success(f"Disconnected: {out or 'All wireless devices disconnected.'}")
            if adb.serial and ":" in adb.serial:
                adb.serial = None
        else:
            ui.error(f"Error: {out}")

    elif choice.isdigit() and 2 <= int(choice) < 2 + len(wifi_devs):
        target = wifi_devs[int(choice) - 2]["serial"]
        ui.info(f"Disconnecting {target}...")
        ok, out = adb.run(["disconnect", target])
        if ok:
            ui.success(f"Disconnected {target}")
            if adb.serial == target:
                adb.serial = None
        else:
            ui.error(f"Failed: {out}")

    elif choice == "9":
        endpoint = ui.get_choice("Enter IP:Port to disconnect")
        if endpoint:
            ok, out = adb.run(["disconnect", endpoint])
            if ok:
                ui.success(f"Disconnected {endpoint}: {out}")
                if adb.serial == endpoint:
                    adb.serial = None
            else:
                ui.error(f"Error: {out}")
    else:
        ui.info("Cancelled.")


# ─── 3. Shell & Input ─────────────────────────────────────────────────────────

def open_interactive_shell():
    """Open an interactive ADB shell session."""
    if not ensure_device():
        return

    ui.header("Interactive ADB Shell")
    ui.info("Opening shell session for device: " + str(adb.serial))
    ui.info("Type 'exit' or press Ctrl+D to return to DroidCommander.")
    print(f"  {ui.Colors.DIM}{'─' * 50}{ui.Colors.RESET}\n")

    adb.run_interactive_shell()

    print(f"\n  {ui.Colors.DIM}{'─' * 50}{ui.Colors.RESET}")
    ui.success("Interactive shell session closed.")


def send_text_input():
    """Send text input to the active input field on the device."""
    if not ensure_device():
        return

    ui.header("Send Text Input to Device")
    print()
    ui.info("Make sure an input field (text box, search bar, etc.) is focused on the device.")
    print()
    print("  Modes:")
    print(f"    {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Type standard text (spaces auto-escaped)")
    print(f"    {ui.Colors.YELLOW}[2]{ui.Colors.RESET} Send URL / web link")
    print(f"    {ui.Colors.YELLOW}[3]{ui.Colors.RESET} Send clipboard paste event (KEYCODE_PASTE)")
    print(f"    {ui.Colors.YELLOW}[4]{ui.Colors.RESET} Send multiple backspaces / clear text")
    print()

    mode = ui.get_choice("Select mode [1]")
    if mode in ("", "1"):
        text = ui.get_choice("Enter text to type")
        if not text:
            ui.info("No text entered.")
            return

        # ADB input text replaces spaces with %s
        escaped = text.replace(" ", "%s").replace("&", "\\&").replace("<", "\\<").replace(">", "\\>")
        ok, out = adb.run(["shell", "input", "text", escaped])
        if ok:
            ui.success(f"Text sent successfully: \"{text}\"")
        else:
            ui.error(f"Failed to send text: {out}")

    elif mode == "2":
        url = ui.get_choice("Enter URL (e.g. https://example.com)")
        if not url:
            ui.info("No URL entered.")
            return
        escaped = url.replace(" ", "%s").replace("&", "\\&")
        ok, out = adb.run(["shell", "input", "text", escaped])
        if ok:
            ui.success(f"URL sent: {url}")
        else:
            ui.error(f"Failed: {out}")

    elif mode == "3":
        ui.info("Sending KEYCODE_PASTE (279)...")
        ok, out = adb.run(["shell", "input", "keyevent", "279"])
        if ok:
            ui.success("Paste event sent.")
        else:
            ui.error(f"Failed: {out}")

    elif mode == "4":
        count_str = ui.get_choice("How many backspaces to send? [10]")
        count = int(count_str) if count_str.isdigit() else 10
        ui.info(f"Sending {count} backspaces...")
        for _ in range(count):
            adb.run(["shell", "input", "keyevent", "67"])
        ui.success(f"Sent {count} backspace events.")


def send_key_event():
    """Send Android keyevents with a comprehensive quick-selection menu."""
    if not ensure_device():
        return

    ui.header("Send Key Event")
    print()

    key_groups = [
        ("Navigation", [
            ("Home", "3"),
            ("Back", "4"),
            ("Recent Apps", "187"),
            ("Menu", "82"),
            ("Search", "84"),
        ]),
        ("Power & System", [
            ("Power", "26"),
            ("Sleep", "223"),
            ("Wakeup", "224"),
            ("Lock Screen", "276"),
            ("Camera", "27"),
        ]),
        ("Volume & Media", [
            ("Volume Up", "24"),
            ("Volume Down", "25"),
            ("Volume Mute", "164"),
            ("Play / Pause", "85"),
            ("Next Track", "87"),
            ("Prev Track", "88"),
        ]),
        ("D-Pad & Editing", [
            ("D-Pad Up", "19"),
            ("D-Pad Down", "20"),
            ("D-Pad Left", "21"),
            ("D-Pad Right", "22"),
            ("D-Pad Center", "23"),
            ("Enter", "66"),
            ("Delete / Backspace", "67"),
            ("Tab", "61"),
            ("Space", "62"),
        ]),
        ("UI Actions", [
            ("Open Notifications", "83"),
            ("Quick Settings", "280"),
            ("Voice Assistant", "231"),
            ("Screenshot", "120"),
            ("Brightness Down", "220"),
            ("Brightness Up", "221"),
        ]),
    ]

    # Display tables of common key events
    table_rows = []
    for group_name, keys in key_groups:
        for name, code in keys:
            table_rows.append((group_name, name, code))

    headers = ("Category", "Key Name", "Key Code")
    ui.print_table(table_rows, headers)
    print()

    code_input = ui.get_choice("Enter Key Code number or custom integer")
    if not code_input:
        ui.info("Cancelled.")
        return

    if not code_input.isdigit():
        ui.error("Key code must be a numeric integer.")
        return

    repeat_str = ui.get_choice("Repeat count [1]")
    repeat = int(repeat_str) if repeat_str.isdigit() and int(repeat_str) > 0 else 1

    ui.info(f"Sending keyevent {code_input} (x{repeat})...")
    success_count = 0
    for _ in range(repeat):
        ok, _ = adb.run(["shell", "input", "keyevent", code_input])
        if ok:
            success_count += 1
        time.sleep(0.05)

    if success_count == repeat:
        ui.success(f"Key event {code_input} sent {repeat} time(s) successfully.")
    else:
        ui.warning(f"Sent {success_count}/{repeat} key events.")


# ─── 4. Display & Power Controls ──────────────────────────────────────────────

def toggle_screen_power():
    """Check current screen state and toggle or force screen on/off."""
    if not ensure_device():
        return

    ui.header("Toggle Screen Power / State")
    current_state = _get_screen_state()
    print()
    ui.print_kv({
        "Current Screen State": f"{ui.Colors.GREEN if current_state == 'ON' else ui.Colors.YELLOW}{current_state}{ui.Colors.RESET}"
    })
    print()

    print("  Actions:")
    print(f"    {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Toggle Power button (KEYCODE_POWER = 26)")
    print(f"    {ui.Colors.YELLOW}[2]{ui.Colors.RESET} Force Screen ON (KEYCODE_WAKEUP = 224)")
    print(f"    {ui.Colors.YELLOW}[3]{ui.Colors.RESET} Force Screen OFF (KEYCODE_SLEEP = 223)")
    print(f"    {ui.Colors.YELLOW}[4]{ui.Colors.RESET} Wake screen and unlock (Swipe up)")
    print()

    choice = ui.get_choice("Select action [1]")
    if choice in ("", "1"):
        ok, out = adb.run(["shell", "input", "keyevent", "26"])
        if ok:
            time.sleep(0.3)
            new_state = _get_screen_state()
            ui.success(f"Power toggled. Screen is now: {new_state}")
        else:
            ui.error(f"Failed to toggle power: {out}")

    elif choice == "2":
        ok, out = adb.run(["shell", "input", "keyevent", "224"])
        if ok:
            ui.success("Sent KEYCODE_WAKEUP. Screen turned ON.")
        else:
            ui.error(f"Failed: {out}")

    elif choice == "3":
        ok, out = adb.run(["shell", "input", "keyevent", "223"])
        if ok:
            ui.success("Sent KEYCODE_SLEEP. Screen turned OFF.")
        else:
            ui.error(f"Failed: {out}")

    elif choice == "4":
        # Wakeup then swipe up to unlock
        adb.run(["shell", "input", "keyevent", "224"])
        time.sleep(0.3)
        ok, out = adb.run(["shell", "input", "swipe", "500", "1500", "500", "300", "300"])
        if ok:
            ui.success("Woke screen and swiped to unlock.")
        else:
            ui.error(f"Failed to swipe: {out}")


def set_screen_brightness():
    """Get and set screen brightness and toggle adaptive brightness."""
    if not ensure_device():
        return

    ui.header("Screen Brightness Control")
    print()

    # Query current brightness and mode
    ok_b, val_b = adb.run(["shell", "settings", "get", "system", "screen_brightness"])
    ok_m, val_m = adb.run(["shell", "settings", "get", "system", "screen_brightness_mode"])

    current_b = val_b.strip() if ok_b and val_b.strip().isdigit() else "Unknown"
    is_auto = val_m.strip() == "1" if ok_m else False

    pct_str = f"({round(int(current_b) / 255 * 100)}%)" if current_b.isdigit() else ""
    ui.print_kv({
        "Current Brightness": f"{current_b} / 255 {pct_str}",
        "Adaptive / Auto Mode": "ENABLED" if is_auto else "DISABLED (Manual)"
    })
    print()

    print("  Presets & Settings:")
    print(f"    {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Set by percentage (0% - 100%)")
    print(f"    {ui.Colors.YELLOW}[2]{ui.Colors.RESET} Set exact value (0 - 255)")
    print(f"    {ui.Colors.YELLOW}[3]{ui.Colors.RESET} Preset: Minimum (10 / 255)")
    print(f"    {ui.Colors.YELLOW}[4]{ui.Colors.RESET} Preset: 25% (64 / 255)")
    print(f"    {ui.Colors.YELLOW}[5]{ui.Colors.RESET} Preset: 50% (128 / 255)")
    print(f"    {ui.Colors.YELLOW}[6]{ui.Colors.RESET} Preset: 75% (192 / 255)")
    print(f"    {ui.Colors.YELLOW}[7]{ui.Colors.RESET} Preset: Maximum (255 / 255)")
    print(f"    {ui.Colors.YELLOW}[8]{ui.Colors.RESET} Toggle Auto/Adaptive Brightness Mode")
    print()

    choice = ui.get_choice("Select option")
    target_val: Optional[int] = None

    if choice == "1":
        pct = ui.get_choice("Enter brightness percentage (0-100)")
        if pct.isdigit() and 0 <= int(pct) <= 100:
            target_val = int(int(pct) * 255 / 100)
        else:
            ui.error("Invalid percentage.")
            return

    elif choice == "2":
        raw = ui.get_choice("Enter exact value (0-255)")
        if raw.isdigit() and 0 <= int(raw) <= 255:
            target_val = int(raw)
        else:
            ui.error("Invalid value.")
            return

    elif choice == "3":
        target_val = 10
    elif choice == "4":
        target_val = 64
    elif choice == "5":
        target_val = 128
    elif choice == "6":
        target_val = 192
    elif choice == "7":
        target_val = 255
    elif choice == "8":
        new_mode = "0" if is_auto else "1"
        ok, out = adb.run(["shell", "settings", "put", "system", "screen_brightness_mode", new_mode])
        if ok:
            ui.success(f"Adaptive brightness set to {'ENABLED' if new_mode == '1' else 'DISABLED'}.")
        else:
            ui.error(f"Failed to change mode: {out}")
        return
    else:
        ui.info("Cancelled.")
        return

    if target_val is not None:
        # Disable auto brightness if setting a manual value
        if is_auto:
            adb.run(["shell", "settings", "put", "system", "screen_brightness_mode", "0"])

        ok, out = adb.run(["shell", "settings", "put", "system", "screen_brightness", str(target_val)])
        if ok:
            pct = round(target_val / 255 * 100)
            ui.success(f"Screen brightness updated to {target_val}/255 ({pct}%).")
        else:
            ui.error(f"Failed to update brightness: {out}")


def set_screen_timeout():
    """Get and set screen off timeout in milliseconds."""
    if not ensure_device():
        return

    ui.header("Screen Timeout Configuration")
    print()

    ok, out = adb.run(["shell", "settings", "get", "system", "screen_off_timeout"])
    current_ms = out.strip() if ok and out.strip().isdigit() else "Unknown"

    human_curr = "Unknown"
    if current_ms.isdigit():
        sec = int(current_ms) // 1000
        if sec >= 86400:
            human_curr = "Never / Maximum"
        elif sec >= 60:
            human_curr = f"{sec // 60}m {sec % 60}s ({current_ms} ms)"
        else:
            human_curr = f"{sec} seconds ({current_ms} ms)"

    ui.print_kv({
        "Current Timeout": human_curr
    })
    print()

    presets = [
        ("15 seconds", 15000),
        ("30 seconds", 30000),
        ("1 minute", 60000),
        ("2 minutes", 120000),
        ("5 minutes", 300000),
        ("10 minutes", 600000),
        ("30 minutes", 1800000),
        ("Never / Max (24 days)", 2147483647),
        ("Custom duration", -1),
    ]

    for idx, (label, _) in enumerate(presets, 1):
        print(f"    {ui.Colors.YELLOW}[{idx}]{ui.Colors.RESET} {label}")
    print()

    choice = ui.get_choice("Select timeout option")
    if not choice.isdigit() or not (1 <= int(choice) <= len(presets)):
        ui.info("Cancelled.")
        return

    selected_label, selected_ms = presets[int(choice) - 1]
    if selected_ms == -1:
        custom_sec = ui.get_choice("Enter custom timeout in seconds")
        if not custom_sec.isdigit() or int(custom_sec) <= 0:
            ui.error("Invalid duration.")
            return
        selected_ms = int(custom_sec) * 1000
        selected_label = f"{custom_sec} seconds"

    ui.info(f"Setting screen timeout to {selected_label} ({selected_ms} ms)...")
    ok, out = adb.run(["shell", "settings", "put", "system", "screen_off_timeout", str(selected_ms)])
    if ok:
        ui.success(f"Screen timeout set to {selected_label} successfully.")
    else:
        ui.error(f"Failed to set timeout: {out}")


# ─── 5. Wireless & System Settings ────────────────────────────────────────────

def toggle_airplane_mode():
    """Check current state and toggle or set airplane mode."""
    if not ensure_device():
        return

    ui.header("Airplane Mode Control")
    print()

    ok, out = adb.run(["shell", "settings", "get", "global", "airplane_mode_on"])
    is_on = out.strip() == "1" if ok else False

    ui.print_kv({
        "Current Status": f"{ui.Colors.YELLOW}ENABLED (ON){ui.Colors.RESET}" if is_on else f"{ui.Colors.GREEN}DISABLED (OFF){ui.Colors.RESET}"
    })
    print()

    print("  Actions:")
    print(f"    {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Toggle Airplane Mode ({'Turn OFF' if is_on else 'Turn ON'})")
    print(f"    {ui.Colors.YELLOW}[2]{ui.Colors.RESET} Force Enable Airplane Mode")
    print(f"    {ui.Colors.YELLOW}[3]{ui.Colors.RESET} Force Disable Airplane Mode")
    print()

    choice = ui.get_choice("Select action [1]")
    if choice in ("", "1"):
        new_state = "0" if is_on else "1"
    elif choice == "2":
        new_state = "1"
    elif choice == "3":
        new_state = "0"
    else:
        ui.info("Cancelled.")
        return

    state_bool = "true" if new_state == "1" else "false"
    ui.info(f"Updating Airplane Mode to {'ON' if new_state == '1' else 'OFF'}...")

    # Write global setting and broadcast the change
    adb.run(["shell", "settings", "put", "global", "airplane_mode_on", new_state])
    ok, out = adb.run(["shell", "am", "broadcast", "-a", "android.intent.action.AIRPLANE_MODE", "--ez", "state", state_bool])

    # Also attempt cmd connectivity for newer Android versions
    adb.run(["shell", "cmd", "connectivity", "airplane-mode", "enable" if new_state == "1" else "disable"])

    if ok:
        ui.success(f"Airplane mode is now {'ENABLED (ON)' if new_state == '1' else 'DISABLED (OFF)'}.")
    else:
        ui.warning(f"Setting updated, broadcast response: {out}")


def set_screen_rotation():
    """Configure auto-rotation and lock orientation (portrait / landscape)."""
    if not ensure_device():
        return

    ui.header("Screen Rotation & Orientation")
    print()

    # Query accelerometer_rotation (1 = auto, 0 = locked)
    ok_a, out_a = adb.run(["shell", "settings", "get", "system", "accelerometer_rotation"])
    # Query user_rotation (0 = portrait, 1 = landscape 90, 2 = reverse portrait 180, 3 = reverse landscape 270)
    ok_u, out_u = adb.run(["shell", "settings", "get", "system", "user_rotation"])

    is_auto = out_a.strip() == "1" if ok_a else False
    user_rot = out_u.strip() if ok_u and out_u.strip().isdigit() else "0"

    rot_names = {
        "0": "Portrait (0°)",
        "1": "Landscape (90°)",
        "2": "Reverse Portrait (180°)",
        "3": "Reverse Landscape (270°)",
    }

    ui.print_kv({
        "Auto-Rotate": "ENABLED" if is_auto else "LOCKED (Disabled)",
        "Current Locked Rotation": rot_names.get(user_rot, f"Unknown ({user_rot})")
    })
    print()

    print("  Orientation Options:")
    print(f"    {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Enable Auto-Rotation (Accelerometer On)")
    print(f"    {ui.Colors.YELLOW}[2]{ui.Colors.RESET} Lock to Portrait (0°)")
    print(f"    {ui.Colors.YELLOW}[3]{ui.Colors.RESET} Lock to Landscape (90°)")
    print(f"    {ui.Colors.YELLOW}[4]{ui.Colors.RESET} Lock to Reverse Portrait (180°)")
    print(f"    {ui.Colors.YELLOW}[5]{ui.Colors.RESET} Lock to Reverse Landscape (270°)")
    print()

    choice = ui.get_choice("Select option")
    if choice == "1":
        ok, out = adb.run(["shell", "settings", "put", "system", "accelerometer_rotation", "1"])
        if ok:
            ui.success("Auto-rotation enabled.")
        else:
            ui.error(f"Failed: {out}")

    elif choice in ("2", "3", "4", "5"):
        rot_val = str(int(choice) - 2)
        # Disable auto-rotate first, then set user rotation
        adb.run(["shell", "settings", "put", "system", "accelerometer_rotation", "0"])
        ok, out = adb.run(["shell", "settings", "put", "system", "user_rotation", rot_val])
        if ok:
            ui.success(f"Screen locked to {rot_names.get(rot_val, 'specified orientation')}.")
        else:
            ui.error(f"Failed: {out}")
    else:
        ui.info("Cancelled.")


def keep_screen_awake_toggle():
    """Toggle Stay Awake mode while plugged into power (USB, AC, Wireless)."""
    if not ensure_device():
        return

    ui.header("Stay Awake While Plugged In")
    print()

    # Query stay_on_while_plugged_in (Bitmask: 1=AC, 2=USB, 4=Wireless, 7=All, 0=Never)
    ok, out = adb.run(["shell", "settings", "get", "global", "stay_on_while_plugged_in"])
    val_str = out.strip() if ok and out.strip().isdigit() else "0"
    val = int(val_str)

    mode_desc = []
    if val & 1:
        mode_desc.append("AC")
    if val & 2:
        mode_desc.append("USB")
    if val & 4:
        mode_desc.append("Wireless")

    current_summary = ", ".join(mode_desc) if mode_desc else "OFF (Normal screen timeout applies)"

    ui.print_kv({
        "Current Stay Awake Mode": f"{ui.Colors.GREEN if val > 0 else ui.Colors.YELLOW}{current_summary}{ui.Colors.RESET}"
    })
    print()

    print("  Stay Awake Options:")
    print(f"    {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Always Stay Awake (AC + USB + Wireless)")
    print(f"    {ui.Colors.YELLOW}[2]{ui.Colors.RESET} Stay Awake on USB Only (Developer Mode)")
    print(f"    {ui.Colors.YELLOW}[3]{ui.Colors.RESET} Stay Awake on AC Charger Only")
    print(f"    {ui.Colors.YELLOW}[4]{ui.Colors.RESET} Disable Stay Awake (Standard Timeout)")
    print(f"    {ui.Colors.YELLOW}[5]{ui.Colors.RESET} Force Stay Awake via Power Service (svc power stayon true)")
    print()

    choice = ui.get_choice("Select option")
    if choice == "1":
        adb.run(["shell", "svc", "power", "stayon", "true"])
        ok, out = adb.run(["shell", "settings", "put", "global", "stay_on_while_plugged_in", "7"])
        if ok:
            ui.success("Stay Awake enabled for all power sources (AC + USB + Wireless).")
        else:
            ui.error(f"Failed: {out}")

    elif choice == "2":
        adb.run(["shell", "svc", "power", "stayon", "usb"])
        ok, out = adb.run(["shell", "settings", "put", "global", "stay_on_while_plugged_in", "2"])
        if ok:
            ui.success("Stay Awake enabled for USB connections.")
        else:
            ui.error(f"Failed: {out}")

    elif choice == "3":
        adb.run(["shell", "svc", "power", "stayon", "ac"])
        ok, out = adb.run(["shell", "settings", "put", "global", "stay_on_while_plugged_in", "1"])
        if ok:
            ui.success("Stay Awake enabled for AC charger.")
        else:
            ui.error(f"Failed: {out}")

    elif choice == "4":
        adb.run(["shell", "svc", "power", "stayon", "false"])
        ok, out = adb.run(["shell", "settings", "put", "global", "stay_on_while_plugged_in", "0"])
        if ok:
            ui.success("Stay Awake disabled. Normal display sleep timeout restored.")
        else:
            ui.error(f"Failed: {out}")

    elif choice == "5":
        ok, out = adb.run(["shell", "svc", "power", "stayon", "true"])
        if ok:
            ui.success("Sent 'svc power stayon true'.")
        else:
            ui.error(f"Failed: {out}")
    else:
        ui.info("Cancelled.")


# ─── Main Menu Loop ───────────────────────────────────────────────────────────

def device_controls_menu():
    """Main menu dispatch for Device Controls module."""
    while True:
        ui.clear()
        ui.print_banner()
        ui.print_device_status(adb.serial, adb.getprop("ro.product.model") if adb.serial else "")
        ui.print_sub_banner("Device Controls", "🔧")

        options = [
            "Reboot device (normal)",
            "Reboot to recovery",
            "Reboot to bootloader",
            "Soft reboot (hot restart)",
            "Enable WiFi ADB (tcpip 5555)",
            "Connect via WiFi (IP:port)",
            "Disconnect WiFi device",
            "Open interactive ADB shell",
            "Send text input to device",
            "Send key event (keycodes list)",
            "Toggle screen on/off",
            "Set screen brightness",
            "Set screen timeout",
            "Toggle airplane mode",
            "Set screen rotation (auto/portrait/landscape)",
            "Keep screen awake toggle",
        ]

        ui.print_menu("Device Controls", options, columns=2)
        choice = ui.get_choice()

        if choice == "0":
            break
        elif choice == "1":
            reboot_normal()
        elif choice == "2":
            reboot_recovery()
        elif choice == "3":
            reboot_bootloader()
        elif choice == "4":
            soft_reboot()
        elif choice == "5":
            enable_wifi_adb()
        elif choice == "6":
            connect_wifi_device()
        elif choice == "7":
            disconnect_wifi_device()
        elif choice == "8":
            open_interactive_shell()
        elif choice == "9":
            send_text_input()
        elif choice == "10":
            send_key_event()
        elif choice == "11":
            toggle_screen_power()
        elif choice == "12":
            set_screen_brightness()
        elif choice == "13":
            set_screen_timeout()
        elif choice == "14":
            toggle_airplane_mode()
        elif choice == "15":
            set_screen_rotation()
        elif choice == "16":
            keep_screen_awake_toggle()
        else:
            ui.error("Invalid option. Please try again.")

        ui.pause()
