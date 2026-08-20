#!/usr/bin/env python3
"""
PhoneSurgeon — Advanced Android Debug Bridge Toolkit.

A powerful, feature-rich, menu-driven ADB toolkit with 16 modules,
multi-device support, 200+ commands, auto-setup, and automation.

Usage:
    python phonesurgeon.py

Requirements:
    - Python 3.8+ (checked automatically)
    - ADB (auto-downloaded if missing)
    - USB Debugging enabled on the Android device
"""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.setup_wizard import run_setup_wizard, run_quick_check
from core.adb import adb
from core import ui
from core.device import select_device, get_device_label

# ── Module imports ────────────────────────────────────────────────────────────
from modules.device_info import device_info_menu
from modules.app_manager import app_manager_menu
from modules.file_manager import file_manager_menu
from modules.screen_capture import screen_capture_menu
from modules.logcat import logcat_menu
from modules.backup_restore import backup_restore_menu
from modules.device_controls import device_controls_menu
from modules.performance import performance_menu
from modules.network_tools import network_tools_menu
from modules.input_simulation import input_simulation_menu
from modules.ui_inspector import ui_inspector_menu
from modules.developer_options import developer_options_menu
from modules.fastboot_tools import fastboot_tools_menu
from modules.system_info import system_info_menu
from modules.security_audit import security_audit_menu
from modules.automation import automation_menu


# ── Main Menu ─────────────────────────────────────────────────────────────────

MAIN_OPTIONS = [
    "📱  Device Information",
    "📦  App Manager",
    "📁  File Manager",
    "📸  Screen Capture",
    "📋  Logcat Viewer",
    "💾  Backup & Restore",
    "🔧  Device Controls",
    "📊  Performance Monitor",
    "🌐  Network Tools",
    "👆  Input Simulation",
    "🔍  UI Inspector",
    "⚙️   Developer Options",
    "⚡  Fastboot Tools",
    "🖥️   System Info",
    "🔒  Security Audit",
    "🤖  Automation & Scripts",
    "─────────────────────",
    "🔄  Switch Device",
    "🏥  Re-run Setup Wizard",
]

MENU_HANDLERS = {
    "1":  device_info_menu,
    "2":  app_manager_menu,
    "3":  file_manager_menu,
    "4":  screen_capture_menu,
    "5":  logcat_menu,
    "6":  backup_restore_menu,
    "7":  device_controls_menu,
    "8":  performance_menu,
    "9":  network_tools_menu,
    "10": input_simulation_menu,
    "11": ui_inspector_menu,
    "12": developer_options_menu,
    "13": fastboot_tools_menu,
    "14": system_info_menu,
    "15": security_audit_menu,
    "16": automation_menu,
    "18": lambda: select_device(),
    "19": lambda: run_setup_wizard(force=True),
}


def startup():
    """
    Run startup sequence:
    1. Quick check for returning users (instant).
    2. Full setup wizard on first run or if ADB is missing.
    3. Auto-select device if exactly one is connected.
    """
    # Fast path — ADB already available
    if run_quick_check():
        # Try auto-selecting a device
        devices = adb.get_connected_serials()
        if devices:
            if len(devices) == 1:
                adb.serial = devices[0]
            else:
                select_device()
        return True

    # Slow path — first run or ADB disappeared
    if not run_setup_wizard():
        ui.clear()
        ui.print_banner()
        ui.error("Setup could not be completed. Please install the required tools.")
        print(f"""
  {ui.Colors.CYAN}Manual install:{ui.Colors.RESET}
    https://developer.android.com/studio/releases/platform-tools

  {ui.Colors.CYAN}Then re-run:{ui.Colors.RESET}
    python phonesurgeon.py
        """)
        sys.exit(1)

    # After setup, try device selection
    devices = adb.get_connected_serials()
    if devices:
        if len(devices) == 1:
            adb.serial = devices[0]
        else:
            select_device()
    return True


def main():
    """Main application loop."""
    startup()

    while True:
        ui.clear()
        ui.print_banner()
        ui.print_device_status(adb.serial, adb.getprop("ro.product.model") if adb.serial else "")
        ui.print_menu("Main Menu", MAIN_OPTIONS, columns=2)

        choice = ui.get_choice()

        if choice == "0":
            print(f"\n  {ui.Colors.CYAN}Thanks for using PhoneSurgeon! 🏥👋{ui.Colors.RESET}\n")
            break

        handler = MENU_HANDLERS.get(choice)
        if handler:
            handler()
        elif choice == "17":
            continue
        else:
            ui.error("Invalid option. Try again.")
            ui.pause()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n  {ui.Colors.CYAN}Interrupted. Goodbye! 🏥👋{ui.Colors.RESET}\n")
        sys.exit(0)
