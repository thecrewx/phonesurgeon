"""
modules/developer_options.py — Developer Options & Tweaks Module for DroidCommander.

Enables toggling and configuring Android Developer Options, animation scales,
GPU overdraw visualization, layout bounds, touch tracking, StrictMode,
background process limits, WebView debugging, and UI rendering performance.
"""

import os
import re
import time
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

from core.adb import adb
from core import ui
from core.device import ensure_device


# ─── Low-Level Setting & Property Helpers ─────────────────────────────────────

def _poke_gui():
    """
    Trigger GUI refresh on device to apply developer property changes immediately.

    Uses the internal ActivityManager service code (1599295570) to invoke
    updateConfiguration() across the system.
    """
    adb.run(["shell", "service", "call", "activity", "1599295570"], timeout=5)


def _get_setting(table: str, key: str) -> str:
    """Read a setting from global, system, or secure table."""
    ok, out = adb.run(["shell", "settings", "get", table, key], timeout=5)
    return out.strip() if ok and out.strip() != "null" else ""


def _put_setting(table: str, key: str, value: str) -> bool:
    """Write a setting to global, system, or secure table."""
    ok, _ = adb.run(["shell", "settings", "put", table, key, value], timeout=5)
    return ok


def _get_prop(prop: str) -> str:
    """Read a system property via getprop."""
    return adb.getprop(prop)


def _set_prop(prop: str, val: str) -> bool:
    """Set a system property via setprop."""
    ok, _ = adb.run(["shell", "setprop", prop, val], timeout=5)
    return ok


# ─── Module Features ──────────────────────────────────────────────────────────

def toggle_layout_bounds():
    """Toggle showing layout bounds (clip bounds, margins, padding)."""
    if not ensure_device():
        return

    ui.header("Show Layout Bounds (debug.layout)")
    current = _get_prop("debug.layout").lower() == "true"
    new_state = not current
    new_val = "true" if new_state else "false"

    ui.info(f"Current state: {'ENABLED' if current else 'DISABLED'}")
    ui.info(f"Setting debug.layout to '{new_val}'...")

    if _set_prop("debug.layout", new_val):
        _poke_gui()
        if new_state:
            ui.success("Layout bounds ENABLED! You should see bounding boxes and margins on screen.")
        else:
            ui.success("Layout bounds DISABLED.")
        ui.info("Note: Some UI views refresh upon screen rotation or switching apps.")
    else:
        ui.error("Failed to set property debug.layout.")


def toggle_gpu_overdraw():
    """Configure GPU Overdraw visualization (Off / Show Areas / Show Count)."""
    if not ensure_device():
        return

    ui.header("GPU Overdraw Visualization (debug.hwui.overdraw)")
    current = _get_prop("debug.hwui.overdraw") or "false"
    ui.info(f"Current setting: {current}")

    print()
    print(f"  {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Off (Default)")
    print(f"  {ui.Colors.YELLOW}[2]{ui.Colors.RESET} Show overdraw areas (Blue: 1x, Green: 2x, Light Red: 3x, Dark Red: 4x+)")
    print(f"  {ui.Colors.YELLOW}[3]{ui.Colors.RESET} Show overdraw count (Numeric counter)")
    print(f"  {ui.Colors.YELLOW}[0]{ui.Colors.RESET} Cancel")
    print()

    choice = ui.get_choice("Select mode")
    val_map = {"1": "false", "2": "show", "3": "count"}
    if choice in val_map:
        val = val_map[choice]
        if _set_prop("debug.hwui.overdraw", val):
            _poke_gui()
            ui.success(f"GPU Overdraw set to: {val}")
        else:
            ui.error("Failed to set GPU overdraw property.")


def set_window_animation_scale():
    """Configure Window Animation Scale."""
    if not ensure_device():
        return

    ui.header("Window Animation Scale")
    current = _get_setting("global", "window_animation_scale") or "1.0"
    ui.info(f"Current Window Animation Scale: {current}x")

    print()
    print(f"  {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Animation off (0.0x) — Instant UI")
    print(f"  {ui.Colors.YELLOW}[2]{ui.Colors.RESET} 0.5x — Snappy UI")
    print(f"  {ui.Colors.YELLOW}[3]{ui.Colors.RESET} 1.0x — Default Android")
    print(f"  {ui.Colors.YELLOW}[4]{ui.Colors.RESET} 1.5x")
    print(f"  {ui.Colors.YELLOW}[5]{ui.Colors.RESET} 2.0x — Slower (UI testing)")
    print(f"  {ui.Colors.YELLOW}[6]{ui.Colors.RESET} 5.0x — Debug animations")
    print(f"  {ui.Colors.YELLOW}[7]{ui.Colors.RESET} 10.0x — Slow-motion")
    print(f"  {ui.Colors.YELLOW}[8]{ui.Colors.RESET} Custom value...")
    print(f"  {ui.Colors.YELLOW}[0]{ui.Colors.RESET} Cancel")
    print()

    scale_map = {"1": "0.0", "2": "0.5", "3": "1.0", "4": "1.5", "5": "2.0", "6": "5.0", "7": "10.0"}
    choice = ui.get_choice("Select scale")
    val = None
    if choice in scale_map:
        val = scale_map[choice]
    elif choice == "8":
        val = ui.get_choice("Enter float value (e.g., 0.25, 0.75, 1.5)")

    if val:
        try:
            float(val)
            if _put_setting("global", "window_animation_scale", val):
                ui.success(f"Window animation scale set to {val}x.")
            else:
                ui.error("Failed to update window animation scale.")
        except ValueError:
            ui.error("Invalid numeric scale value.")


def set_transition_animation_scale():
    """Configure Transition Animation Scale."""
    if not ensure_device():
        return

    ui.header("Transition Animation Scale")
    current = _get_setting("global", "transition_animation_scale") or "1.0"
    ui.info(f"Current Transition Animation Scale: {current}x")

    print()
    print(f"  {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Animation off (0.0x) — Instant screen changes")
    print(f"  {ui.Colors.YELLOW}[2]{ui.Colors.RESET} 0.5x — Snappy")
    print(f"  {ui.Colors.YELLOW}[3]{ui.Colors.RESET} 1.0x — Default Android")
    print(f"  {ui.Colors.YELLOW}[4]{ui.Colors.RESET} 1.5x")
    print(f"  {ui.Colors.YELLOW}[5]{ui.Colors.RESET} 2.0x")
    print(f"  {ui.Colors.YELLOW}[6]{ui.Colors.RESET} 5.0x")
    print(f"  {ui.Colors.YELLOW}[7]{ui.Colors.RESET} 10.0x")
    print(f"  {ui.Colors.YELLOW}[8]{ui.Colors.RESET} Custom value...")
    print(f"  {ui.Colors.YELLOW}[0]{ui.Colors.RESET} Cancel")
    print()

    scale_map = {"1": "0.0", "2": "0.5", "3": "1.0", "4": "1.5", "5": "2.0", "6": "5.0", "7": "10.0"}
    choice = ui.get_choice("Select scale")
    val = None
    if choice in scale_map:
        val = scale_map[choice]
    elif choice == "8":
        val = ui.get_choice("Enter float value (e.g., 0.25, 0.75, 1.5)")

    if val:
        try:
            float(val)
            if _put_setting("global", "transition_animation_scale", val):
                ui.success(f"Transition animation scale set to {val}x.")
            else:
                ui.error("Failed to update transition animation scale.")
        except ValueError:
            ui.error("Invalid numeric scale value.")


def set_animator_duration_scale():
    """Configure Animator Duration Scale."""
    if not ensure_device():
        return

    ui.header("Animator Duration Scale")
    current = _get_setting("global", "animator_duration_scale") or "1.0"
    ui.info(f"Current Animator Duration Scale: {current}x")

    print()
    print(f"  {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Animation off (0.0x) — Disable ObjectAnimators")
    print(f"  {ui.Colors.YELLOW}[2]{ui.Colors.RESET} 0.5x — Snappy UI")
    print(f"  {ui.Colors.YELLOW}[3]{ui.Colors.RESET} 1.0x — Default Android")
    print(f"  {ui.Colors.YELLOW}[4]{ui.Colors.RESET} 1.5x")
    print(f"  {ui.Colors.YELLOW}[5]{ui.Colors.RESET} 2.0x")
    print(f"  {ui.Colors.YELLOW}[6]{ui.Colors.RESET} 5.0x")
    print(f"  {ui.Colors.YELLOW}[7]{ui.Colors.RESET} 10.0x")
    print(f"  {ui.Colors.YELLOW}[8]{ui.Colors.RESET} Custom value...")
    print(f"  {ui.Colors.YELLOW}[0]{ui.Colors.RESET} Cancel")
    print()

    scale_map = {"1": "0.0", "2": "0.5", "3": "1.0", "4": "1.5", "5": "2.0", "6": "5.0", "7": "10.0"}
    choice = ui.get_choice("Select scale")
    val = None
    if choice in scale_map:
        val = scale_map[choice]
    elif choice == "8":
        val = ui.get_choice("Enter float value (e.g., 0.25, 0.75, 1.5)")

    if val:
        try:
            float(val)
            if _put_setting("global", "animator_duration_scale", val):
                ui.success(f"Animator duration scale set to {val}x.")
            else:
                ui.error("Failed to update animator duration scale.")
        except ValueError:
            ui.error("Invalid numeric scale value.")


def toggle_show_touches():
    """Toggle visual circle feedback on screen for taps."""
    if not ensure_device():
        return

    ui.header("Show Visual Taps / Touches")
    current = _get_setting("system", "show_touches")
    new_val = "0" if current == "1" else "1"

    if _put_setting("system", "show_touches", new_val):
        if new_val == "1":
            ui.success("Show Touches ENABLED. A circular touch indicator will follow touches.")
        else:
            ui.success("Show Touches DISABLED.")
    else:
        ui.error("Failed to toggle show_touches setting.")


def toggle_pointer_location():
    """Toggle pointer coordinates, touch crosshairs, pressure, and velocity overlay."""
    if not ensure_device():
        return

    ui.header("Pointer Location Overlay")
    current = _get_setting("system", "pointer_location")
    new_val = "0" if current == "1" else "1"

    if _put_setting("system", "pointer_location", new_val):
        if new_val == "1":
            ui.success("Pointer Location ENABLED. Coordinate bar and crosshairs active.")
        else:
            ui.success("Pointer Location DISABLED.")
    else:
        ui.error("Failed to toggle pointer_location setting.")


def toggle_strict_mode_visual():
    """Toggle StrictMode visual flash (flashes screen borders when apps do long I/O on main thread)."""
    if not ensure_device():
        return

    ui.header("StrictMode Visual Flash")
    current = _get_prop("persist.sys.strictmode.visual")
    new_val = "0" if current == "1" else "1"

    _set_prop("persist.sys.strictmode.visual", new_val)
    _set_prop("persist.sys.strictmode.disable", "0" if new_val == "1" else "1")
    _poke_gui()

    if new_val == "1":
        ui.success("StrictMode Visual Flash ENABLED.")
        ui.info("Screen will flash red on long operations on the UI main thread.")
    else:
        ui.success("StrictMode Visual Flash DISABLED.")


def usb_debugging_info():
    """Display detailed USB & Wireless Debugging status, stay awake, and auth info."""
    if not ensure_device():
        return

    ui.header("USB Debugging & Device State Details")

    adb_enabled = _get_setting("global", "adb_enabled")
    stay_awake = _get_setting("global", "stay_on_while_plugged_in")
    adb_wifi_port = _get_prop("service.adb.tcp.port")

    stay_awake_desc = "Never (0)"
    if stay_awake == "3":
        stay_awake_desc = "AC + USB (3)"
    elif stay_awake == "7":
        stay_awake_desc = "AC + USB + Wireless (7)"
    elif stay_awake == "1":
        stay_awake_desc = "AC Only (1)"
    elif stay_awake == "2":
        stay_awake_desc = "USB Only (2)"

    info_data = {
        "USB Debugging (ADB)": f"{ui.Colors.GREEN}ENABLED{ui.Colors.RESET}" if adb_enabled == "1" else "Disabled",
        "Wireless ADB TCP Port": adb_wifi_port if adb_wifi_port and adb_wifi_port != "0" else "Inactive (USB mode)",
        "Stay Awake While Charging": stay_awake_desc,
        "Connected Serial": adb.serial or "None",
        "Device Product Model": _get_prop("ro.product.model"),
        "Android OS Version": f"{_get_prop('ro.build.version.release')} (API {_get_prop('ro.build.version.sdk')})",
        "Security Patch Level": _get_prop("ro.build.version.security_patch"),
    }
    print()
    ui.print_kv(info_data)

    print()
    print(f"  {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Set Stay Awake to Always On (AC + USB + Wireless)")
    print(f"  {ui.Colors.YELLOW}[2]{ui.Colors.RESET} Disable Stay Awake (Normal screen timeout)")
    print(f"  {ui.Colors.YELLOW}[3]{ui.Colors.RESET} Enable Wireless ADB on Port 5555 (`adb tcpip 5555`)")
    print(f"  {ui.Colors.YELLOW}[0]{ui.Colors.RESET} Back")
    print()

    choice = ui.get_choice("Action")
    if choice == "1":
        if _put_setting("global", "stay_on_while_plugged_in", "7"):
            ui.success("Stay Awake set to Always On while plugged in.")
    elif choice == "2":
        if _put_setting("global", "stay_on_while_plugged_in", "0"):
            ui.success("Stay Awake disabled.")
    elif choice == "3":
        ui.info("Restarting ADB daemon in TCP mode on port 5555...")
        ok, out = adb.run(["tcpip", "5555"])
        if ok:
            ui.success("ADB daemon listening on port 5555.")
            ui.info("You can now disconnect USB and run: adb connect <device-ip>:5555")
        else:
            ui.error(f"Failed to enable TCP mode: {out}")


def set_background_process_limit():
    """Set the system background process limit or configure phantom process killer."""
    if not ensure_device():
        return

    ui.header("Background Process Limit Configuration")

    print(f"  {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Standard limit (Android system default)")
    print(f"  {ui.Colors.YELLOW}[2]{ui.Colors.RESET} No background processes (0)")
    print(f"  {ui.Colors.YELLOW}[3]{ui.Colors.RESET} At most 1 process")
    print(f"  {ui.Colors.YELLOW}[4]{ui.Colors.RESET} At most 2 processes")
    print(f"  {ui.Colors.YELLOW}[5]{ui.Colors.RESET} At most 3 processes")
    print(f"  {ui.Colors.YELLOW}[6]{ui.Colors.RESET} At most 4 processes")
    print(f"  {ui.Colors.YELLOW}[7]{ui.Colors.RESET} Disable Phantom Process Killer (Android 12+ / 13+ / 14+)")
    print(f"  {ui.Colors.YELLOW}[0]{ui.Colors.RESET} Cancel")
    print()

    choice = ui.get_choice("Select limit")
    limit_map = {"1": "-1", "2": "0", "3": "1", "4": "2", "5": "3", "6": "4"}

    if choice in limit_map:
        val = limit_map[choice]
        ui.info(f"Setting background process limit to {val}...")
        ok, _ = adb.run(["shell", "dumpsys", "activity", "set-bg-limit", val])
        if not ok:
            # Fallback service call
            ok, _ = adb.run(["shell", "service", "call", "activity", "52", "i32", val])
        ui.success("Background process limit applied.")
    elif choice == "7":
        ui.info("Disabling Android Phantom Process Killer...")
        adb.run(["shell", "/system/bin/device_config", "put", "activity_manager", "max_phantom_processes", "2147483647"])
        adb.run(["shell", "/system/bin/device_config", "set_sync_disabled_for_tests", "persistent"])
        _put_setting("global", "settings_enable_monitor_phantom_procs", "false")
        ui.success("Phantom process limits disabled. Termux and background daemons will run smoothly.")


def toggle_webview_debugging():
    """Toggle WebView debugging and display Chrome DevTools inspection instructions."""
    if not ensure_device():
        return

    ui.header("WebView Debugging & Remote Inspection")

    curr_debug = _get_prop("debug.web.developer_mode")
    new_val = "0" if curr_debug == "1" else "1"

    _set_prop("debug.web.developer_mode", new_val)
    _set_prop("debug.webkit.developer_mode", new_val)

    if new_val == "1":
        ui.success("WebView developer debugging flag ENABLED.")
    else:
        ui.success("WebView developer debugging flag DISABLED.")

    # Inspect WebView package
    ok, out = adb.run(["shell", "dumpsys", "webviewupdate"], timeout=8)
    cur_wv = "Default System WebView"
    if ok and out:
        m = re.search(r"Current WebView package \(name, version\):\s*\(([^,]+),\s*([^)]+)\)", out)
        if m:
            cur_wv = f"{m.group(1)} (v{m.group(2)})"

    print()
    ui.header("Chrome DevTools Remote Inspection:")
    ui.print_kv({
        "Current WebView Provider": cur_wv,
        "PC Inspection URL": "chrome://inspect/#devices",
        "Edge Inspection URL": "edge://inspect/#devices",
    })
    ui.info("Open Chrome on your computer to live-inspect any active WebView, Cordova, or Capacitor app.")


def force_gpu_rendering_and_profile():
    """Configure GPU rendering and on-screen GPU profiling bars."""
    if not ensure_device():
        return

    ui.header("Force GPU Rendering & Profile HWUI")

    curr_profile = _get_prop("debug.hwui.profile") or "false"
    curr_force_hw = _get_prop("persist.sys.force_hw_ui") or "0"

    ui.info(f"Profile HWUI: {curr_profile} | Force HW 2D: {curr_force_hw}")
    print()
    print(f"  {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Profile HWUI: On screen as visual bars (Frame render graph)")
    print(f"  {ui.Colors.YELLOW}[2]{ui.Colors.RESET} Profile HWUI: In dumpsys (`dumpsys gfxinfo`)")
    print(f"  {ui.Colors.YELLOW}[3]{ui.Colors.RESET} Profile HWUI: Disabled")
    print(f"  {ui.Colors.YELLOW}[4]{ui.Colors.RESET} Toggle Force GPU 2D Hardware Acceleration (`persist.sys.force_hw_ui`)")
    print(f"  {ui.Colors.YELLOW}[0]{ui.Colors.RESET} Back")
    print()

    choice = ui.get_choice("Select option")
    if choice == "1":
        _set_prop("debug.hwui.profile", "visual_bars")
        _poke_gui()
        ui.success("HWUI Profile set to Visual Bars (Green/Orange/Red frame graph on screen).")
    elif choice == "2":
        _set_prop("debug.hwui.profile", "true")
        _poke_gui()
        ui.success("HWUI Profile set to dumpsys.")
    elif choice == "3":
        _set_prop("debug.hwui.profile", "false")
        _poke_gui()
        ui.success("HWUI Profiling disabled.")
    elif choice == "4":
        new_f = "0" if curr_force_hw == "1" else "1"
        _set_prop("persist.sys.force_hw_ui", new_f)
        _poke_gui()
        ui.success(f"Force GPU 2D Rendering set to: {'ENABLED' if new_f == '1' else 'DISABLED'}")


def toggle_4x_msaa():
    """Toggle 4x Multisample Anti-Aliasing (MSAA) for OpenGL ES 2.0 apps."""
    if not ensure_device():
        return

    ui.header("Force 4x MSAA (Multisample Anti-Aliasing)")
    curr = _get_prop("debug.egl.force_msaa")
    new_val = "0" if curr == "1" else "1"

    if _set_prop("debug.egl.force_msaa", new_val):
        _poke_gui()
        if new_val == "1":
            ui.success("Force 4x MSAA ENABLED. Improves OpenGL graphics smoothness at slight GPU cost.")
        else:
            ui.success("Force 4x MSAA DISABLED.")
    else:
        ui.error("Failed to update debug.egl.force_msaa property.")


def show_developer_settings_status():
    """Compile and display an all-in-one developer settings status dashboard."""
    if not ensure_device():
        return

    ui.header("Developer Options Comprehensive Status Report")

    # Animation Scales
    win_anim = _get_setting("global", "window_animation_scale") or "1.0"
    trans_anim = _get_setting("global", "transition_animation_scale") or "1.0"
    dur_anim = _get_setting("global", "animator_duration_scale") or "1.0"

    # Touches & Pointer
    touches = _get_setting("system", "show_touches") == "1"
    pointer = _get_setting("system", "pointer_location") == "1"

    # Properties
    layout = _get_prop("debug.layout").lower() == "true"
    overdraw = _get_prop("debug.hwui.overdraw") or "false"
    strictmode = _get_prop("persist.sys.strictmode.visual") == "1"
    msaa = _get_prop("debug.egl.force_msaa") == "1"
    hwui_prof = _get_prop("debug.hwui.profile") or "false"
    force_hw = _get_prop("persist.sys.force_hw_ui") == "1"
    webview_dev = _get_prop("debug.web.developer_mode") == "1"

    # System global settings
    adb_enabled = _get_setting("global", "adb_enabled") == "1"
    stay_awake = _get_setting("global", "stay_on_while_plugged_in")
    demo_allowed = _get_setting("global", "sysui_demo_allowed") == "1"

    status_data = {
        "USB Debugging (ADB)": f"{ui.Colors.GREEN}ENABLED{ui.Colors.RESET}" if adb_enabled else f"{ui.Colors.RED}DISABLED{ui.Colors.RESET}",
        "Show Layout Bounds": f"{ui.Colors.GREEN}ON{ui.Colors.RESET}" if layout else f"{ui.Colors.DIM}OFF{ui.Colors.RESET}",
        "GPU Overdraw Visualization": f"{ui.Colors.YELLOW}{overdraw}{ui.Colors.RESET}" if overdraw != "false" else f"{ui.Colors.DIM}OFF{ui.Colors.RESET}",
        "Window Animation Scale": f"{win_anim}x",
        "Transition Animation Scale": f"{trans_anim}x",
        "Animator Duration Scale": f"{dur_anim}x",
        "Show Touches (Visual taps)": f"{ui.Colors.GREEN}ON{ui.Colors.RESET}" if touches else f"{ui.Colors.DIM}OFF{ui.Colors.RESET}",
        "Pointer Location Overlay": f"{ui.Colors.GREEN}ON{ui.Colors.RESET}" if pointer else f"{ui.Colors.DIM}OFF{ui.Colors.RESET}",
        "StrictMode Visual Flash": f"{ui.Colors.GREEN}ON{ui.Colors.RESET}" if strictmode else f"{ui.Colors.DIM}OFF{ui.Colors.RESET}",
        "Force 4x MSAA": f"{ui.Colors.GREEN}ON{ui.Colors.RESET}" if msaa else f"{ui.Colors.DIM}OFF{ui.Colors.RESET}",
        "Profile HWUI Rendering": f"{ui.Colors.YELLOW}{hwui_prof}{ui.Colors.RESET}" if hwui_prof != "false" else f"{ui.Colors.DIM}OFF{ui.Colors.RESET}",
        "Force GPU 2D Rendering": f"{ui.Colors.GREEN}ON{ui.Colors.RESET}" if force_hw else f"{ui.Colors.DIM}OFF{ui.Colors.RESET}",
        "WebView Developer Mode": f"{ui.Colors.GREEN}ON{ui.Colors.RESET}" if webview_dev else f"{ui.Colors.DIM}OFF{ui.Colors.RESET}",
        "Stay Awake (Plugged in)": f"{stay_awake or '0'}",
        "SystemUI Demo Mode Allowed": f"{ui.Colors.GREEN}YES{ui.Colors.RESET}" if demo_allowed else f"{ui.Colors.DIM}NO{ui.Colors.RESET}",
    }

    print()
    ui.print_kv(status_data)


def quick_animation_presets():
    """Apply speed or debugging presets across all animation scales simultaneously."""
    if not ensure_device():
        return

    ui.header("Quick Animation & Performance Presets")
    print(f"  {ui.Colors.YELLOW}[1]{ui.Colors.RESET} ⚡ Super Speed — All animations off (0.0x) for instant snappy UI")
    print(f"  {ui.Colors.YELLOW}[2]{ui.Colors.RESET} 🚀 Snappy — All animations set to 0.5x (Fast & smooth)")
    print(f"  {ui.Colors.YELLOW}[3]{ui.Colors.RESET} 🔄 Standard Android Default — All animations set to 1.0x")
    print(f"  {ui.Colors.YELLOW}[4]{ui.Colors.RESET} 🐛 Deep UI Debugging Preset — Layout bounds ON, Touches ON, 2.0x Animations")
    print(f"  {ui.Colors.YELLOW}[0]{ui.Colors.RESET} Cancel")
    print()

    choice = ui.get_choice("Select preset")
    if choice == "1":
        _put_setting("global", "window_animation_scale", "0.0")
        _put_setting("global", "transition_animation_scale", "0.0")
        _put_setting("global", "animator_duration_scale", "0.0")
        ui.success("Super Speed preset applied! (0.0x animations)")
    elif choice == "2":
        _put_setting("global", "window_animation_scale", "0.5")
        _put_setting("global", "transition_animation_scale", "0.5")
        _put_setting("global", "animator_duration_scale", "0.5")
        ui.success("Snappy preset applied! (0.5x animations)")
    elif choice == "3":
        _put_setting("global", "window_animation_scale", "1.0")
        _put_setting("global", "transition_animation_scale", "1.0")
        _put_setting("global", "animator_duration_scale", "1.0")
        ui.success("Default preset applied! (1.0x animations)")
    elif choice == "4":
        _put_setting("global", "window_animation_scale", "2.0")
        _put_setting("global", "transition_animation_scale", "2.0")
        _put_setting("global", "animator_duration_scale", "2.0")
        _set_prop("debug.layout", "true")
        _put_setting("system", "show_touches", "1")
        _poke_gui()
        ui.success("UI Debug preset applied! (Layout bounds ON, Touches ON, 2.0x animations)")


def toggle_systemui_demo_mode():
    """Toggle SystemUI Demo Mode (clean status bar for screenshots/presentations)."""
    if not ensure_device():
        return

    ui.header("SystemUI Demo Mode (Clean Status Bar)")
    allowed = _get_setting("global", "sysui_demo_allowed") == "1"

    print(f"  {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Enter Demo Mode (12:00 clock, 100% battery, full WiFi/LTE, clean icons)")
    print(f"  {ui.Colors.YELLOW}[2]{ui.Colors.RESET} Exit Demo Mode (Restore normal status bar)")
    print(f"  {ui.Colors.YELLOW}[0]{ui.Colors.RESET} Back")
    print()

    choice = ui.get_choice("Select option")
    if choice == "1":
        ui.info("Enabling SystemUI Demo Mode...")
        _put_setting("global", "sysui_demo_allowed", "1")
        adb.run(["shell", "am", "broadcast", "-a", "com.android.systemui.demo", "-e", "command", "enter"])
        adb.run(["shell", "am", "broadcast", "-a", "com.android.systemui.demo", "-e", "command", "clock", "-e", "hhmm", "1200"])
        adb.run(["shell", "am", "broadcast", "-a", "com.android.systemui.demo", "-e", "command", "battery", "-e", "level", "100", "-e", "plugged", "false"])
        adb.run(["shell", "am", "broadcast", "-a", "com.android.systemui.demo", "-e", "command", "network", "-e", "wifi", "show", "-e", "level", "4", "-e", "mobile", "show", "-e", "datatype", "lte", "-e", "level", "4"])
        adb.run(["shell", "am", "broadcast", "-a", "com.android.systemui.demo", "-e", "command", "notifications", "-e", "visible", "false"])
        ui.success("Demo Mode active! Status bar icons are clean and presentation-ready.")
    elif choice == "2":
        ui.info("Exiting Demo Mode...")
        adb.run(["shell", "am", "broadcast", "-a", "com.android.systemui.demo", "-e", "command", "exit"])
        ui.success("Demo Mode disabled.")


# ─── Public Entry Menu ────────────────────────────────────────────────────────

def developer_options_menu():
    """Main menu loop for the Developer Options module."""
    while True:
        ui.clear()
        ui.print_banner()
        ui.print_sub_banner("Developer Options & Tweaks", "🛠️")
        ui.print_device_status(adb.serial)

        options = [
            "Toggle Show Layout Bounds",
            "Toggle GPU Overdraw Visualization",
            "Set Window Animation Scale",
            "Set Transition Animation Scale",
            "Set Animator Duration Scale",
            "Toggle Show Touches (Visual Taps)",
            "Toggle Pointer Location Overlay",
            "Toggle StrictMode Visual Flash",
            "USB Debugging & Stay Awake Settings",
            "Set Background Process Limit",
            "Toggle WebView Debugging & Inspect",
            "Force GPU Rendering & Profile HWUI",
            "Toggle Force 4x MSAA",
            "Show Developer Settings Overview",
            "Quick Animation & Speed Presets",
            "SystemUI Demo Mode (Clean Status Bar)",
        ]

        ui.print_menu("Developer Options Menu", options, columns=2)
        choice = ui.get_choice("Select option")

        if choice == "0":
            break
        elif choice == "1":
            toggle_layout_bounds()
            ui.pause()
        elif choice == "2":
            toggle_gpu_overdraw()
            ui.pause()
        elif choice == "3":
            set_window_animation_scale()
            ui.pause()
        elif choice == "4":
            set_transition_animation_scale()
            ui.pause()
        elif choice == "5":
            set_animator_duration_scale()
            ui.pause()
        elif choice == "6":
            toggle_show_touches()
            ui.pause()
        elif choice == "7":
            toggle_pointer_location()
            ui.pause()
        elif choice == "8":
            toggle_strict_mode_visual()
            ui.pause()
        elif choice == "9":
            usb_debugging_info()
            ui.pause()
        elif choice == "10":
            set_background_process_limit()
            ui.pause()
        elif choice == "11":
            toggle_webview_debugging()
            ui.pause()
        elif choice == "12":
            force_gpu_rendering_and_profile()
            ui.pause()
        elif choice == "13":
            toggle_4x_msaa()
            ui.pause()
        elif choice == "14":
            show_developer_settings_status()
            ui.pause()
        elif choice == "15":
            quick_animation_presets()
            ui.pause()
        elif choice == "16":
            toggle_systemui_demo_mode()
            ui.pause()
        else:
            ui.error("Invalid option. Please choose a valid number.")
            ui.pause()
