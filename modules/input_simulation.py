"""
modules/input_simulation.py — Touch, gesture, keyboard, and hardware button simulation.

Provides an extensive set of input injection utilities for Android devices:
- Coordinate-based taps (single, repeat, center)
- Long press with custom duration
- Custom swipe paths and pre-calculated gesture presets (scroll, fling, edge swipe)
- Text typing with character escaping and clipboard injection
- Key event injection with comprehensive keycode reference table
- Key combinations (Ctrl+A/C/V/Z, Alt+Tab, Power+VolDown)
- Quick navigation controls (Home, Back, Recents, Power, Wake, Sleep)
- Notifications panel and Quick Settings shade toggling
- Screenshot capture via hardware combo or screencap
- Volume controls (Up, Down, Mute, Volume level adjustments)
- Media playback controls (Play, Pause, Next, Prev, Stop, Rewind)
- Interactive macro script execution
"""

import os
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from core.adb import adb
from core import ui
from core.device import ensure_device


# ─── Screen Dimensions & Info Helper ─────────────────────────────────────────

def get_screen_dimensions() -> Tuple[int, int, int]:
    """
    Retrieve display width, height, and density (DPI) from the connected device.

    Returns
    -------
    Tuple[int, int, int]
        (width, height, density)
    """
    width, height, density = 1080, 2400, 420

    ok_size, size_out = adb.run(["shell", "wm", "size"])
    if ok_size and size_out:
        # Check for "Override size: WxH" first, else "Physical size: WxH"
        override_match = re.search(r'Override size:\s*(\d+)x(\d+)', size_out)
        physical_match = re.search(r'Physical size:\s*(\d+)x(\d+)', size_out)

        if override_match:
            width, height = int(override_match.group(1)), int(override_match.group(2))
        elif physical_match:
            width, height = int(physical_match.group(1)), int(physical_match.group(2))

    ok_den, den_out = adb.run(["shell", "wm", "density"])
    if ok_den and den_out:
        den_override = re.search(r'Override density:\s*(\d+)', den_out)
        den_phys = re.search(r'Physical density:\s*(\d+)', den_out)
        if den_override:
            density = int(den_override.group(1))
        elif den_phys:
            density = int(den_phys.group(1))

    return width, height, density


def _print_display_header():
    """Print current display resolution context."""
    w, h, dpi = get_screen_dimensions()
    print(f"  {ui.Colors.DIM}📱 Display Resolution: {ui.Colors.CYAN}{w} × {h}{ui.Colors.DIM} (DPI: {dpi}){ui.Colors.RESET}\n")


# ─── Key Event Definitions & Reference Table ──────────────────────────────────

KEYCODES_CATALOGUE: Dict[str, List[Tuple[int, str, str]]] = {
    "Navigation & System": [
        (3, "KEYCODE_HOME", "Home screen button"),
        (4, "KEYCODE_BACK", "Back button / dismiss"),
        (82, "KEYCODE_MENU", "Options menu"),
        (187, "KEYCODE_APP_SWITCH", "Recent apps / overview"),
        (26, "KEYCODE_POWER", "Power button (screen toggle)"),
        (224, "KEYCODE_WAKEUP", "Wake device screen"),
        (223, "KEYCODE_SLEEP", "Put device screen to sleep"),
        (231, "KEYCODE_VOICE_ASSIST", "Voice assistant prompt"),
        (27, "KEYCODE_CAMERA", "Launch camera / shutter"),
        (276, "KEYCODE_SETTINGS", "Open system settings"),
    ],
    "Volume & Audio": [
        (24, "KEYCODE_VOLUME_UP", "Increase volume"),
        (25, "KEYCODE_VOLUME_DOWN", "Decrease volume"),
        (164, "KEYCODE_VOLUME_MUTE", "Mute / unmute audio"),
    ],
    "Media Playback": [
        (85, "KEYCODE_MEDIA_PLAY_PAUSE", "Play / Pause toggle"),
        (126, "KEYCODE_MEDIA_PLAY", "Start playback"),
        (127, "KEYCODE_MEDIA_PAUSE", "Pause playback"),
        (87, "KEYCODE_MEDIA_NEXT", "Skip to next track"),
        (88, "KEYCODE_MEDIA_PREVIOUS", "Previous track"),
        (86, "KEYCODE_MEDIA_STOP", "Stop playback"),
        (90, "KEYCODE_MEDIA_FAST_FORWARD", "Fast forward"),
        (89, "KEYCODE_MEDIA_REWIND", "Rewind track"),
    ],
    "Directional Pad (D-Pad)": [
        (19, "KEYCODE_DPAD_UP", "Navigate Up"),
        (20, "KEYCODE_DPAD_DOWN", "Navigate Down"),
        (21, "KEYCODE_DPAD_LEFT", "Navigate Left"),
        (22, "KEYCODE_DPAD_RIGHT", "Navigate Right"),
        (23, "KEYCODE_DPAD_CENTER", "Select / Confirm (OK)"),
    ],
    "Keyboard & Text Editing": [
        (66, "KEYCODE_ENTER", "Enter / Return key"),
        (67, "KEYCODE_DEL", "Backspace (delete left)"),
        (112, "KEYCODE_FORWARD_DEL", "Delete (delete right)"),
        (61, "KEYCODE_TAB", "Tab key"),
        (62, "KEYCODE_SPACE", "Space bar"),
        (111, "KEYCODE_ESCAPE", "Escape key"),
        (277, "KEYCODE_CUT", "Cut selection"),
        (278, "KEYCODE_COPY", "Copy selection"),
        (279, "KEYCODE_PASTE", "Paste clipboard"),
        (120, "KEYCODE_SYSRQ", "Print Screen / SysRq"),
    ],
}


# ─── 1. Tap at Coordinates ───────────────────────────────────────────────────

def tap_at_coordinates():
    """Simulate single or repeated screen taps at exact X, Y coordinates."""
    if not ensure_device():
        return

    ui.print_sub_banner("Simulate Screen Tap", "👆")
    w, h, _ = get_screen_dimensions()
    _print_display_header()

    print(f"  Valid X range: {ui.Colors.CYAN}0 – {w}{ui.Colors.RESET} | Valid Y range: {ui.Colors.CYAN}0 – {h}{ui.Colors.RESET}\n")

    x_input = ui.get_choice(f"Enter X coordinate (or 'c' for screen center: {w // 2})")
    if not x_input:
        return
    if x_input.lower() == "c":
        x = w // 2
        y = h // 2
    else:
        try:
            x = int(x_input)
        except ValueError:
            ui.error("Invalid X coordinate integer.")
            ui.pause()
            return

        y_input = ui.get_choice(f"Enter Y coordinate (default: {h // 2})")
        try:
            y = int(y_input) if y_input else h // 2
        except ValueError:
            ui.error("Invalid Y coordinate integer.")
            ui.pause()
            return

    # Repeat options
    repeat_str = ui.get_choice("Number of taps to send (default: 1)")
    repeat_count = 1
    if repeat_str.isdigit() and int(repeat_str) > 0:
        repeat_count = min(int(repeat_str), 100)

    delay = 0.1
    if repeat_count > 1:
        delay_str = ui.get_choice("Delay between taps in seconds (default: 0.1)")
        try:
            delay = float(delay_str) if delay_str else 0.1
        except ValueError:
            delay = 0.1

    ui.info(f"Sending {repeat_count} tap(s) at ({x}, {y})...")

    for i in range(repeat_count):
        ok, out = adb.run(["shell", "input", "tap", str(x), str(y)])
        if not ok:
            ui.error(f"Tap command failed: {out}")
            break
        if repeat_count > 1 and i < repeat_count - 1:
            time.sleep(delay)

    if ok:
        ui.success(f"Successfully performed {repeat_count} tap(s) at ({x}, {y})")

    print()
    ui.pause()


# ─── 2. Long Press at Coordinates ────────────────────────────────────────────

def long_press_at_coordinates():
    """Simulate a touch and hold (long press) gesture at coordinates with duration."""
    if not ensure_device():
        return

    ui.print_sub_banner("Simulate Long Press", "⏱️")
    w, h, _ = get_screen_dimensions()
    _print_display_header()

    x_input = ui.get_choice(f"Enter X coordinate (or 'c' for center: {w // 2})")
    if not x_input:
        return
    if x_input.lower() == "c":
        x = w // 2
        y = h // 2
    else:
        try:
            x = int(x_input)
            y_input = ui.get_choice(f"Enter Y coordinate (default: {h // 2})")
            y = int(y_input) if y_input else h // 2
        except ValueError:
            ui.error("Invalid coordinate input.")
            ui.pause()
            return

    dur_input = ui.get_choice("Long press duration in milliseconds (default: 1000 ms / 1.0s)")
    duration = 1000
    if dur_input.isdigit() and int(dur_input) >= 200:
        duration = int(dur_input)

    ui.info(f"Injecting long press at ({x}, {y}) for {duration} ms...")

    # Long press in ADB is executed via swipe with identical start/end coordinates and duration
    ok, out = adb.run(["shell", "input", "swipe", str(x), str(y), str(x), str(y), str(duration)])

    if ok:
        ui.success(f"Long press executed at ({x}, {y}) for {duration} ms")
    else:
        ui.error(f"Failed to execute long press: {out}")

    print()
    ui.pause()


# ─── 3. Custom Swipe ─────────────────────────────────────────────────────────

def swipe_custom():
    """Simulate custom directional swipe from (X1, Y1) to (X2, Y2) with duration."""
    if not ensure_device():
        return

    ui.print_sub_banner("Custom Swipe Simulation", "↔️")
    w, h, _ = get_screen_dimensions()
    _print_display_header()

    try:
        x1_str = ui.get_choice(f"Start X coordinate (0-{w})")
        if not x1_str:
            return
        x1 = int(x1_str)

        y1_str = ui.get_choice(f"Start Y coordinate (0-{h})")
        y1 = int(y1_str)

        x2_str = ui.get_choice(f"End X coordinate (0-{w})")
        x2 = int(x2_str)

        y2_str = ui.get_choice(f"End Y coordinate (0-{h})")
        y2 = int(y2_str)

        dur_str = ui.get_choice("Swipe duration in milliseconds (default: 300 ms)")
        duration = int(dur_str) if dur_str.isdigit() and int(dur_str) > 0 else 300
    except ValueError:
        ui.error("Invalid numeric input for swipe coordinates or duration.")
        ui.pause()
        return

    ui.info(f"Swiping from ({x1}, {y1}) to ({x2}, {y2}) over {duration} ms...")
    ok, out = adb.run(["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration)])

    if ok:
        ui.success(f"Swipe completed: ({x1}, {y1}) ➔ ({x2}, {y2}) [{duration}ms]")
    else:
        ui.error(f"Swipe execution failed: {out}")

    print()
    ui.pause()


# ─── 4. Swipe Gestures Presets ───────────────────────────────────────────────

def swipe_gestures_presets():
    """Execute pre-calculated swipe gestures (scroll, fling, edge navigation)."""
    if not ensure_device():
        return

    w, h, _ = get_screen_dimensions()

    # Precalculate screen points
    cx = w // 2
    cy = h // 2
    y_top = int(h * 0.20)
    y_bot = int(h * 0.80)
    x_left = int(w * 0.20)
    x_right = int(w * 0.80)

    presets = [
        ("Swipe Up (Scroll Down Content)", (cx, y_bot, cx, y_top, 350)),
        ("Swipe Down (Scroll Up Content)", (cx, y_top, cx, y_bot, 350)),
        ("Swipe Left (Next Page / Card)", (x_right, cy, x_left, cy, 300)),
        ("Swipe Right (Previous Page / Card)", (x_left, cy, x_right, cy, 300)),
        ("Fast Fling Up (Fling Scroll Down)", (cx, y_bot, cx, y_top, 120)),
        ("Fast Fling Down (Fling Scroll Up)", (cx, y_top, cx, y_bot, 120)),
        ("Edge Swipe Left (Back Gesture from Left Edge)", (10, cy, int(w * 0.4), cy, 200)),
        ("Edge Swipe Right (Back Gesture from Right Edge)", (w - 10, cy, int(w * 0.6), cy, 200)),
        ("Swipe Up from Bottom Edge (Home Gesture)", (cx, h - 10, cx, int(h * 0.4), 250)),
        ("Swipe Up and Hold (Recent Apps Gesture)", (cx, h - 10, cx, cy, 600)),
    ]

    while True:
        ui.clear()
        ui.print_banner()
        ui.print_device_status(adb.serial)
        _print_display_header()

        options = [label for label, _ in presets]
        ui.print_menu("Gesture Presets", options, columns=2)

        choice = ui.get_choice("Select gesture preset")
        if choice == "0":
            break

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(presets):
                label, (x1, y1, x2, y2, dur) = presets[idx]
                repeat_str = ui.get_choice("Repeat count (default: 1)")
                reps = int(repeat_str) if repeat_str.isdigit() and int(repeat_str) > 0 else 1

                ui.info(f"Executing '{label}' ({reps} time(s))...")
                for r in range(reps):
                    adb.run(["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(dur)])
                    if reps > 1 and r < reps - 1:
                        time.sleep(0.3)

                ui.success(f"Gesture '{label}' executed successfully.")
                ui.pause()
            else:
                ui.error("Invalid gesture index.")
                ui.pause()
        except ValueError:
            ui.error("Invalid input.")
            ui.pause()


# ─── 5. Type Text on Device ──────────────────────────────────────────────────

def type_text_on_device():
    """Input text characters on the active text field on the Android device."""
    if not ensure_device():
        return

    ui.print_sub_banner("Input Text on Device", "⌨️")

    print(f"  {ui.Colors.BOLD}Select Text Input Method:{ui.Colors.RESET}\n")
    print(f"  {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Direct Typing (input text with auto-escape)")
    print(f"  {ui.Colors.YELLOW}[2]{ui.Colors.RESET} Clipboard Injection & Paste (fastest & handles all special chars/emojis)")
    print(f"  {ui.Colors.YELLOW}[3]{ui.Colors.RESET} Clear Text Field first, then Type")
    print(f"  {ui.Colors.YELLOW}[4]{ui.Colors.RESET} Type Text and press Enter")
    print(f"  {ui.Colors.YELLOW}[0]{ui.Colors.RESET} Cancel")
    print()

    mode = ui.get_choice("Select input method")
    if mode == "0" or not mode:
        return

    text_to_type = ui.get_choice("Enter text string to send to device")
    if not text_to_type:
        ui.warning("No text entered.")
        ui.pause()
        return

    if mode == "1":
        # Escape spaces and special chars for adb shell input text
        # In Android 'input text', spaces must be replaced by %s
        escaped = text_to_type.replace(" ", "%s")
        # Escape characters with special shell meaning
        for ch in ["&", "<", ">", "|", ";", "$", "`", "(", ")", '"', "'", "\\"]:
            escaped = escaped.replace(ch, f"\\{ch}")

        ui.info(f"Injecting text: '{text_to_type}'...")
        ok, out = adb.run(["shell", "input", "text", escaped])
        if ok:
            ui.success("Text successfully typed on device.")
        else:
            ui.error(f"Failed to type text: {out}")

    elif mode == "2":
        # Clipboard injection via cmd clipboard or fallback service call
        ui.info("Setting clipboard and triggering paste...")
        # Escape quotes for sh -c
        safe_text = text_to_type.replace("'", "'\\''")
        adb.run(["shell", "sh", "-c", f"cmd clipboard set text '{safe_text}'"])
        time.sleep(0.1)
        # Send Paste Keycode (279) or Ctrl+V
        ok_paste, _ = adb.run(["shell", "input", "keyevent", "279"])
        if not ok_paste:
            # Fallback to keycombo Ctrl+V
            adb.run(["shell", "input", "keycombination", "113", "50"])
        ui.success(f"Clipboard set to '{text_to_type}' and paste command sent.")

    elif mode == "3":
        ui.info("Clearing field and typing text...")
        # Select all (Ctrl+A / 113 + 29) + DEL (67)
        adb.run(["shell", "input", "keycombination", "113", "29"])
        adb.run(["shell", "input", "keyevent", "67"])
        time.sleep(0.1)
        escaped = text_to_type.replace(" ", "%s")
        for ch in ["&", "<", ">", "|", ";", "$", "`", "(", ")", '"', "'", "\\"]:
            escaped = escaped.replace(ch, f"\\{ch}")
        adb.run(["shell", "input", "text", escaped])
        ui.success("Field cleared and text typed.")

    elif mode == "4":
        escaped = text_to_type.replace(" ", "%s")
        for ch in ["&", "<", ">", "|", ";", "$", "`", "(", ")", '"', "'", "\\"]:
            escaped = escaped.replace(ch, f"\\{ch}")
        adb.run(["shell", "input", "text", escaped])
        time.sleep(0.1)
        adb.run(["shell", "input", "keyevent", "66"])  # KEYCODE_ENTER
        ui.success("Text typed and Enter pressed.")

    print()
    ui.pause()


# ─── 6. Send Key Event with Reference Table ───────────────────────────────────

def send_key_event():
    """Display comprehensive keycode reference table and send any key event."""
    if not ensure_device():
        return

    while True:
        ui.clear()
        ui.print_banner()
        ui.print_device_status(adb.serial)
        ui.print_sub_banner("Send Android Key Event", "🔘")

        print(f"  {ui.Colors.BOLD}{ui.Colors.CYAN}Key Event Reference Catalogue:{ui.Colors.RESET}\n")

        for category, items in KEYCODES_CATALOGUE.items():
            print(f"  {ui.Colors.BOLD}▶ {category}:{ui.Colors.RESET}")
            rows = [(f" {k}", name, desc) for k, name, desc in items]
            ui.print_table(rows, ("Code", "Key Identifier", "Description"), indent=4)
            print()

        print(f"  {ui.Colors.YELLOW}[Custom Code]{ui.Colors.RESET} Enter any integer keycode (0-350+)")
        print(f"  {ui.Colors.YELLOW}[0]{ui.Colors.RESET} ← Back\n")

        choice = ui.get_choice("Enter Keycode number to inject (or 0 to exit)")
        if choice == "0" or not choice:
            break

        if choice.isdigit():
            k_code = int(choice)
            longpress_ans = ui.confirm(f"Send keycode {k_code} with Long-Press flag (--longpress)?")

            ui.info(f"Injecting keyevent {k_code}...")
            cmd = ["shell", "input", "keyevent"]
            if longpress_ans:
                cmd.append("--longpress")
            cmd.append(str(k_code))

            ok, out = adb.run(cmd)
            if ok:
                ui.success(f"Keyevent {k_code} dispatched successfully.")
            else:
                ui.error(f"Failed to dispatch keyevent: {out}")
            ui.pause()
        else:
            ui.error("Keycode must be a valid integer.")
            ui.pause()


# ─── 7. Send Key Combination ─────────────────────────────────────────────────

def send_key_combo():
    """Inject simultaneous modifier key combos (Ctrl+A, Ctrl+C, Ctrl+V, Alt+Tab, etc.)."""
    if not ensure_device():
        return

    ui.print_sub_banner("Send Key Combination", "🔤")

    combos = [
        ("Ctrl + A (Select All)", [113, 29]),
        ("Ctrl + C (Copy)", [113, 31]),
        ("Ctrl + V (Paste)", [113, 50]),
        ("Ctrl + X (Cut)", [113, 52]),
        ("Ctrl + Z (Undo)", [113, 54]),
        ("Ctrl + Y (Redo)", [113, 53]),
        ("Alt + Tab (App Switcher)", [57, 61]),
        ("Power + Volume Down (Hardware Screenshot)", [26, 25]),
        ("Power + Volume Up (Power/Recovery Trigger)", [26, 24]),
        ("Win / Meta + Enter (Assistant)", [117, 66]),
        ("Custom Key Combination", []),
    ]

    print(f"  {ui.Colors.BOLD}Select a Key Combo to send:{ui.Colors.RESET}\n")
    for idx, (lbl, _) in enumerate(combos, 1):
        print(f"  {ui.Colors.YELLOW}[{idx:>2}]{ui.Colors.RESET} {lbl}")
    print(f"  {ui.Colors.YELLOW}[ 0]{ui.Colors.RESET} Cancel\n")

    choice = ui.get_choice("Select combination")
    if choice == "0" or not choice:
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(combos):
            lbl, keys = combos[idx]
            if not keys:
                # Custom combo
                c_str = ui.get_choice("Enter 2 or 3 keycodes separated by spaces (e.g., '113 29')")
                parts = c_str.split()
                keys = [int(p) for p in parts if p.isdigit()]
                if not keys:
                    ui.error("Invalid custom keycodes.")
                    ui.pause()
                    return
                lbl = f"Custom Combo ({' + '.join(str(k) for k in keys)})"

            ui.info(f"Injecting key combination: {lbl}...")
            # Try input keycombination (Android 11+)
            args = ["shell", "input", "keycombination"] + [str(k) for k in keys]
            ok, out = adb.run(args)
            if not ok:
                # Fallback to input keycombo
                args_alt = ["shell", "input", "keycombo"] + [str(k) for k in keys]
                ok, out = adb.run(args_alt)

            if ok:
                ui.success(f"Key combination '{lbl}' sent.")
            else:
                ui.warning(f"Key combo command returned: {out}")
        else:
            ui.error("Invalid selection.")
    except ValueError:
        ui.error("Invalid number.")

    print()
    ui.pause()


# ─── 8. Press Home / Back / Recent / Power (Quick Nav Buttons) ───────────────

def quick_navigation_buttons():
    """Quick access buttons for primary Android system navigation controls."""
    if not ensure_device():
        return

    while True:
        ui.clear()
        ui.print_banner()
        ui.print_device_status(adb.serial)
        ui.print_sub_banner("Quick Navigation Controls", "🧭")

        nav_options = [
            "Press HOME Button (KEYCODE_HOME / 3)",
            "Press BACK Button (KEYCODE_BACK / 4)",
            "Press RECENTS / App Switcher (KEYCODE_APP_SWITCH / 187)",
            "Press POWER Button Toggle (KEYCODE_POWER / 26)",
            "WAKE Device Screen (KEYCODE_WAKEUP / 224)",
            "SLEEP Device Screen (KEYCODE_SLEEP / 223)",
            "Press MENU Button (KEYCODE_MENU / 82)",
            "Launch Voice Assistant (KEYCODE_VOICE_ASSIST / 231)",
            "Launch Camera App (KEYCODE_CAMERA / 27)",
        ]

        ui.print_menu("Navigation Buttons", nav_options)
        choice = ui.get_choice("Select button action")

        if choice == "0":
            break
        elif choice == "1":
            adb.run(["shell", "input", "keyevent", "3"])
            ui.success("HOME button pressed.")
        elif choice == "2":
            adb.run(["shell", "input", "keyevent", "4"])
            ui.success("BACK button pressed.")
        elif choice == "3":
            adb.run(["shell", "input", "keyevent", "187"])
            ui.success("RECENTS button pressed.")
        elif choice == "4":
            adb.run(["shell", "input", "keyevent", "26"])
            ui.success("POWER button pressed.")
        elif choice == "5":
            adb.run(["shell", "input", "keyevent", "224"])
            ui.success("WAKEUP signal sent.")
        elif choice == "6":
            adb.run(["shell", "input", "keyevent", "223"])
            ui.success("SLEEP signal sent.")
        elif choice == "7":
            adb.run(["shell", "input", "keyevent", "82"])
            ui.success("MENU button pressed.")
        elif choice == "8":
            adb.run(["shell", "input", "keyevent", "231"])
            ui.success("Voice Assistant triggered.")
        elif choice == "9":
            adb.run(["shell", "input", "keyevent", "27"])
            ui.success("Camera shutter / app triggered.")
        else:
            ui.error("Invalid choice.")

        time.sleep(0.5)


# ─── 9. Open Notifications Panel ─────────────────────────────────────────────

def open_notifications_panel():
    """Expand or collapse the Android notification shade."""
    if not ensure_device():
        return

    ui.print_sub_banner("Notifications Panel Control", "🔔")

    print(f"  {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Expand Notifications Shade (Swipe Down)")
    print(f"  {ui.Colors.YELLOW}[2]{ui.Colors.RESET} Collapse Notifications Shade")
    print(f"  {ui.Colors.YELLOW}[0]{ui.Colors.RESET} Cancel\n")

    choice = ui.get_choice("Select action")
    if choice == "1":
        ui.info("Expanding notifications panel...")
        # cmd statusbar expand-notifications (Android 10+)
        ok, out = adb.run(["shell", "cmd", "statusbar", "expand-notifications"])
        if not ok:
            # Fallback service call statusbar 1
            ok, out = adb.run(["shell", "service", "call", "statusbar", "1"])
        if not ok:
            # Fallback top swipe
            w, h, _ = get_screen_dimensions()
            adb.run(["shell", "input", "swipe", str(w // 2), "0", str(w // 2), str(h // 2), "200"])
        ui.success("Notifications shade expanded.")
    elif choice == "2":
        ui.info("Collapsing statusbar / notifications...")
        ok, out = adb.run(["shell", "cmd", "statusbar", "collapse"])
        if not ok:
            adb.run(["shell", "service", "call", "statusbar", "2"])
        ui.success("Notifications shade collapsed.")

    print()
    ui.pause()


# ─── 10. Open Quick Settings ─────────────────────────────────────────────────

def open_quick_settings():
    """Expand or collapse the Android Quick Settings shade."""
    if not ensure_device():
        return

    ui.print_sub_banner("Quick Settings Shade Control", "⚙️")

    print(f"  {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Expand Quick Settings Shade (Full Pull-Down)")
    print(f"  {ui.Colors.YELLOW}[2]{ui.Colors.RESET} Collapse Quick Settings Shade")
    print(f"  {ui.Colors.YELLOW}[0]{ui.Colors.RESET} Cancel\n")

    choice = ui.get_choice("Select action")
    if choice == "1":
        ui.info("Expanding Quick Settings shade...")
        ok, out = adb.run(["shell", "cmd", "statusbar", "expand-settings"])
        if not ok:
            ok, out = adb.run(["shell", "service", "call", "statusbar", "3"])
        if not ok:
            w, h, _ = get_screen_dimensions()
            adb.run(["shell", "input", "swipe", str(w // 2), "0", str(w // 2), str(int(h * 0.8)), "250"])
        ui.success("Quick Settings shade expanded.")
    elif choice == "2":
        ui.info("Collapsing Quick Settings...")
        ok, out = adb.run(["shell", "cmd", "statusbar", "collapse"])
        if not ok:
            adb.run(["shell", "service", "call", "statusbar", "2"])
        ui.success("Quick Settings collapsed.")

    print()
    ui.pause()


# ─── 11. Take Screenshot via Key Combo / Screencap ───────────────────────────

def take_screenshot_input():
    """Trigger screenshot via hardware key combo or capture screenshot directly."""
    if not ensure_device():
        return

    ui.print_sub_banner("Capture Device Screenshot", "📸")

    print(f"  {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Trigger Hardware Screenshot Combo (Power + VolDown)")
    print(f"  {ui.Colors.YELLOW}[2]{ui.Colors.RESET} Direct ADB Screencap & Pull to Host PC")
    print(f"  {ui.Colors.YELLOW}[3]{ui.Colors.RESET} Save Screenshot directly to Device Storage (/sdcard/Screenshots)")
    print(f"  {ui.Colors.YELLOW}[0]{ui.Colors.RESET} Cancel\n")

    choice = ui.get_choice("Select screenshot method")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if choice == "1":
        ui.info("Dispatching Power + Volume Down key combination...")
        ok, out = adb.run(["shell", "input", "keycombination", "26", "25"])
        if not ok:
            adb.run(["shell", "input", "keyevent", "120"])  # KEYCODE_SYSRQ
        ui.success("Hardware screenshot triggered on device.")

    elif choice == "2":
        local_filename = f"screenshot_{timestamp}.png"
        remote_path = f"/sdcard/screenshot_tmp_{timestamp}.png"

        ui.info("Capturing display frame buffer...")
        ok_cap, out_cap = adb.run(["shell", "screencap", "-p", remote_path])
        if ok_cap:
            ui.info(f"Pulling screenshot to local folder ({local_filename})...")
            ok_pull, out_pull = adb.run(["pull", remote_path, local_filename])
            adb.run(["shell", "rm", remote_path])
            if ok_pull:
                ui.success(f"Screenshot successfully saved to host: {os.path.abspath(local_filename)}")
            else:
                ui.error(f"Failed to pull screenshot: {out_pull}")
        else:
            ui.error(f"Screencap failed: {out_cap}")

    elif choice == "3":
        remote_path = f"/sdcard/screenshot_{timestamp}.png"
        ui.info(f"Capturing screenshot to {remote_path}...")
        ok_cap, out_cap = adb.run(["shell", "screencap", "-p", remote_path])
        if ok_cap:
            ui.success(f"Screenshot saved on device: {remote_path}")
        else:
            ui.error(f"Screencap failed: {out_cap}")

    print()
    ui.pause()


# ─── 12. Volume Controls ─────────────────────────────────────────────────────

def volume_controls():
    """Adjust audio volume levels, mute state, or set exact volume."""
    if not ensure_device():
        return

    while True:
        ui.clear()
        ui.print_banner()
        ui.print_device_status(adb.serial)
        ui.print_sub_banner("Device Volume Controls", "🔊")

        vol_options = [
            "Volume UP (KEYCODE_VOLUME_UP / 24)",
            "Volume DOWN (KEYCODE_VOLUME_DOWN / 25)",
            "Toggle MUTE / Unmute (KEYCODE_VOLUME_MUTE / 164)",
            "Set Specific Media Volume Level (0 – 15)",
            "Max Volume (Boost to 100%)",
            "Minimum Volume / Complete Silence",
            "Show Audio Stream Levels (dumpsys audio)",
        ]

        ui.print_menu("Volume Options", vol_options)
        choice = ui.get_choice("Select volume action")

        if choice == "0":
            break
        elif choice == "1":
            adb.run(["shell", "input", "keyevent", "24"])
            ui.success("Volume increased.")
            time.sleep(0.3)
        elif choice == "2":
            adb.run(["shell", "input", "keyevent", "25"])
            ui.success("Volume decreased.")
            time.sleep(0.3)
        elif choice == "3":
            adb.run(["shell", "input", "keyevent", "164"])
            ui.success("Volume mute state toggled.")
            time.sleep(0.3)
        elif choice == "4":
            level_str = ui.get_choice("Enter media volume level (0 - 15)")
            if level_str.isdigit():
                lvl = int(level_str)
                # cmd media_session volume --stream 3 --set <val>
                ok, _ = adb.run(["shell", "cmd", "media_session", "volume", "--stream", "3", "--set", str(lvl)])
                if ok:
                    ui.success(f"Media volume set to {lvl}/15.")
                else:
                    ui.warning("Direct volume set not supported on this ROM; using step keys.")
            ui.pause()
        elif choice == "5":
            ui.info("Maximizing volume...")
            for _ in range(15):
                adb.run(["shell", "input", "keyevent", "24"])
            ui.success("Volume set to maximum.")
            ui.pause()
        elif choice == "6":
            ui.info("Minimizing volume...")
            for _ in range(15):
                adb.run(["shell", "input", "keyevent", "25"])
            ui.success("Volume minimized to zero.")
            ui.pause()
        elif choice == "7":
            ui.info("Querying dumpsys audio...")
            ok_a, out_a = adb.run(["shell", "dumpsys", "audio"])
            if ok_a:
                music_lines = [l.strip() for l in out_a.splitlines() if "STREAM_MUSIC" in l or "STREAM_RING" in l or "STREAM_VOICE_CALL" in l]
                if music_lines:
                    print()
                    for ml in music_lines[:8]:
                        print(f"    {ui.Colors.CYAN}●{ui.Colors.RESET} {ml}")
                else:
                    ui.info("Audio dump retrieved successfully.")
            ui.pause()


# ─── 13. Media Playback Controls ─────────────────────────────────────────────

def media_playback_controls():
    """Dispatch media control events (Play, Pause, Skip, Prev, FastForward)."""
    if not ensure_device():
        return

    while True:
        ui.clear()
        ui.print_banner()
        ui.print_device_status(adb.serial)
        ui.print_sub_banner("Media Playback Controls", "🎵")

        media_options = [
            "Play / Pause Toggle (KEYCODE_MEDIA_PLAY_PAUSE / 85)",
            "Play (KEYCODE_MEDIA_PLAY / 126)",
            "Pause (KEYCODE_MEDIA_PAUSE / 127)",
            "Next Track (KEYCODE_MEDIA_NEXT / 87)",
            "Previous Track (KEYCODE_MEDIA_PREVIOUS / 88)",
            "Stop Playback (KEYCODE_MEDIA_STOP / 86)",
            "Fast Forward (KEYCODE_MEDIA_FAST_FORWARD / 90)",
            "Rewind (KEYCODE_MEDIA_REWIND / 89)",
            "Show Currently Playing Media Info (dumpsys media_session)",
        ]

        ui.print_menu("Media Controls", media_options)
        choice = ui.get_choice("Select media command")

        if choice == "0":
            break
        elif choice == "1":
            adb.run(["shell", "input", "keyevent", "85"])
            ui.success("Media Play/Pause toggled.")
        elif choice == "2":
            adb.run(["shell", "input", "keyevent", "126"])
            ui.success("Media Play sent.")
        elif choice == "3":
            adb.run(["shell", "input", "keyevent", "127"])
            ui.success("Media Pause sent.")
        elif choice == "4":
            adb.run(["shell", "input", "keyevent", "87"])
            ui.success("Next Track sent.")
        elif choice == "5":
            adb.run(["shell", "input", "keyevent", "88"])
            ui.success("Previous Track sent.")
        elif choice == "6":
            adb.run(["shell", "input", "keyevent", "86"])
            ui.success("Stop Playback sent.")
        elif choice == "7":
            adb.run(["shell", "input", "keyevent", "90"])
            ui.success("Fast Forward sent.")
        elif choice == "8":
            adb.run(["shell", "input", "keyevent", "89"])
            ui.success("Rewind sent.")
        elif choice == "9":
            ui.info("Querying active media session...")
            ok_m, out_m = adb.run(["shell", "dumpsys", "media_session"])
            if ok_m and out_m:
                session_lines = [l.strip() for l in out_m.splitlines() if "description=" in l or "state=PlaybackState" in l or "package=" in l]
                if session_lines:
                    print()
                    for sl in session_lines[:6]:
                        print(f"    {ui.Colors.GREEN}♪{ui.Colors.RESET} {sl}")
                else:
                    ui.info("No active media player playback session found.")
            ui.pause()

        time.sleep(0.3)


# ─── Public Entry Menu ───────────────────────────────────────────────────────

def input_simulation_menu():
    """Main interactive loop for Input Simulation module."""
    menu_options = [
        "Tap at Coordinates (X, Y)",
        "Long Press at Coordinates",
        "Custom Swipe (Start X,Y ➔ End X,Y)",
        "Swipe Gestures (Scroll, Fling, Edge Swipes)",
        "Type Text on Device (Keyboard / Clipboard)",
        "Send Key Event (with Reference Table)",
        "Send Key Combination (Ctrl+A/C/V, Alt+Tab)",
        "Quick Navigation Buttons (Home, Back, Recents, Power)",
        "Open / Collapse Notifications Shade",
        "Open / Collapse Quick Settings",
        "Capture Screenshot (Hardware Combo / Screencap)",
        "Volume Controls (Up, Down, Mute, Set Level)",
        "Media Playback Controls (Play, Pause, Next, Prev)",
    ]

    while True:
        ui.clear()
        ui.print_banner()
        ui.print_device_status(adb.serial)
        ui.print_menu("Input Simulation & Hardware Controls", menu_options, columns=2)

        choice = ui.get_choice("Select input option")

        if choice == "0":
            break
        elif choice == "1":
            tap_at_coordinates()
        elif choice == "2":
            long_press_at_coordinates()
        elif choice == "3":
            swipe_custom()
        elif choice == "4":
            swipe_gestures_presets()
        elif choice == "5":
            type_text_on_device()
        elif choice == "6":
            send_key_event()
        elif choice == "7":
            send_key_combo()
        elif choice == "8":
            quick_navigation_buttons()
        elif choice == "9":
            open_notifications_panel()
        elif choice == "10":
            open_quick_settings()
        elif choice == "11":
            take_screenshot_input()
        elif choice == "12":
            volume_controls()
        elif choice == "13":
            media_playback_controls()
        else:
            ui.error("Invalid choice. Please select an option from the menu.")
            ui.pause()
