"""
core/device.py — Multi-device selection and management.

When multiple devices are connected, this module presents a picker
and ensures all subsequent commands target the chosen device.
"""

from core.adb import adb
from core import ui


def select_device() -> bool:
    """
    Prompt the user to select a device if multiple are connected.

    Returns *True* if a device is selected and ready, *False* otherwise.
    """
    devices = adb.list_devices()
    online = [d for d in devices if d["state"] == "device"]

    if not online:
        ui.error("No devices connected. Connect a device with USB Debugging enabled.")
        return False

    if len(online) == 1:
        adb.serial = online[0]["serial"]
        model = online[0].get("model", "")
        ui.info(f"Auto-selected device: {adb.serial} {f'({model})' if model else ''}")
        return True

    # Multiple devices — let the user pick
    ui.header("Multiple devices detected:")
    print()
    headers = ("  #", "Serial", "State", "Model", "Device")
    rows = []
    for i, d in enumerate(online, 1):
        rows.append((
            f"  {i}",
            d["serial"],
            d["state"],
            d.get("model", "—"),
            d.get("device", "—"),
        ))
    ui.print_table(rows, headers)
    print()

    choice = ui.get_choice("Select device number")
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(online):
            adb.serial = online[idx]["serial"]
            model = online[idx].get("model", "")
            ui.success(f"Selected: {adb.serial} {f'({model})' if model else ''}")
            return True
    except ValueError:
        pass

    ui.error("Invalid selection.")
    return False


def ensure_device() -> bool:
    """
    Make sure a device is connected and selected.

    If no device has been selected yet, tries :func:`select_device`.
    """
    if adb.serial and adb.serial in adb.get_connected_serials():
        return True
    return select_device()


def get_device_label() -> str:
    """Return a human-friendly label for the active device."""
    if not adb.serial:
        return "No device"
    model = adb.getprop("ro.product.model")
    return f"{adb.serial} ({model})" if model else adb.serial
