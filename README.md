<p align="center">
  <img src="banner.jpg" alt="PhoneSurgeon Banner" width="100%">
</p>

# 🏥 PhoneSurgeon — Advanced ADB Toolkit

A powerful, feature-rich, menu-driven ADB (Android Debug Bridge) toolkit for Android developers, testers, and power users. Manage devices, apps, files, networking, performance, automation, and more — all from a single interactive CLI.

**Auto-installs everything it needs.** Just run it.

---

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/PhoneSurgeon.git
cd PhoneSurgeon

# Run it — that's it!
python phonesurgeon.py
```

On first run, PhoneSurgeon will:
1. ✅ Check your Python version (needs 3.8+)
2. ✅ Check if ADB is installed — **auto-downloads it if missing**
3. ✅ Check Fastboot availability
4. ✅ Start the ADB server
5. ✅ Detect connected devices
6. ✅ Guide you through USB debugging setup if needed

**Zero manual setup required. Zero dependencies. Pure Python.**

---

## ⚡ Features (16 Modules • 200+ Commands)

| # | Module | Capabilities |
|---|--------|-------------|
| 1 | 📱 **Device Info** | Model, hardware, sensors, thermal, battery, build props, Android version, full device report export |
| 2 | 📦 **App Manager** | Install/uninstall, batch install, list/search, launch, force-stop, clear data, permissions viewer, APK extraction, disable/enable, version info |
| 3 | 📁 **File Manager** | Push/pull files & folders, browse, search, disk usage, create dirs, chmod, checksum verification, view contents |
| 4 | 📸 **Screen Capture** | Screenshots, burst capture, screen recording (custom duration/bitrate/resolution), multi-display, capture history |
| 5 | 📋 **Logcat** | Filter by tag/priority/PID/regex, crash & ANR logs, live stream, kernel logs, event logs, buffer management |
| 6 | 💾 **Backup & Restore** | Full/app backup, data-only, shared storage, contacts (vCard/CSV), SMS & call logs, backup analysis |
| 7 | 🔧 **Device Controls** | Reboot (all modes), WiFi ADB, shell, brightness, rotation, airplane mode, screen timeout, stay awake |
| 8 | 📊 **Performance** | CPU, memory, storage, battery stats, GPU, process monitor, app memory profiling, frame stats, disk I/O |
| 9 | 🌐 **Network Tools** | WiFi info, ping, DNS, open ports, data usage, HTTP test, saved networks, diagnostics scorecard |
| 10 | 👆 **Input Simulation** | Tap, swipe, long press, gestures, text input, key combos, volume, media controls, notifications |
| 11 | 🔍 **UI Inspector** | UI hierarchy dump, current activity, fragments, windows, content providers, services, accessibility |
| 12 | ⚙️ **Developer Options** | Layout bounds, GPU overdraw, animation scales, show touches, pointer location, strict mode, demo mode |
| 13 | ⚡ **Fastboot Tools** | Flash images, OEM unlock/lock, variables, partition management, A/B slot switching, boot without flash |
| 14 | 🖥️ **System Info** | Kernel, SELinux, partitions, services, features, mount points, uptime, input devices, boot diagnostics |
| 15 | 🔒 **Security Audit** | Encryption, screen lock, USB debug, unknown sources, SELinux, dangerous permissions, root detection, security scorecard |
| 16 | 🤖 **Automation** | Record & replay macros, batch commands, command history, favorites, custom scripts, scheduled repeat |

---

## 🏥 Auto-Setup System

PhoneSurgeon includes a smart setup wizard that handles everything automatically:

```
  [1/5] Checking Python version...
    ✓ Python 3.11 detected (minimum 3.8)

  [2/5] Checking ADB (Android Debug Bridge)...
    ✗ ADB not found on system PATH.
    ➤ Download & install ADB automatically? (y/n): y

    Downloading Android SDK Platform Tools...
    ℹ URL: https://dl.google.com/android/repository/platform-tools-latest-windows.zip
    [██████████████████████████████] 100.0%
    ✓ Downloaded (13.2 MB)
    ✓ Extracted successfully!
    ✓ ADB installed!

  [3/5] Checking Fastboot (optional)...
    ✓ Fastboot found

  [4/5] Starting ADB server...
    ✓ ADB server is running

  [5/5] Checking device connectivity...
    ✓ Connected devices: 1
      🔌 R5CT12345
```

### What it auto-detects & installs:
- **Python version** — checks 3.8+ requirement
- **ADB** — downloads Google Platform Tools if missing (Windows/Mac/Linux)
- **Fastboot** — checks availability for bootloader operations
- **ADB Server** — starts automatically
- **USB Drivers** — checks on Windows, guides installation
- **Device Connection** — detects devices, shows USB debugging guide if needed

### Config is saved to `~/.phonesurgeon/` so setup only runs once.

---

## 📂 Project Structure

```
PhoneSurgeon/
├── phonesurgeon.py            # Main entry point — run this!
├── core/
│   ├── __init__.py
│   ├── adb.py                 # ADB/Fastboot command wrapper
│   ├── ui.py                  # Terminal UI, colors, tables, menus
│   ├── device.py              # Multi-device selection & management
│   └── setup_wizard.py        # Auto-setup & prerequisite installer
├── modules/
│   ├── __init__.py
│   ├── device_info.py         # Device information (940 lines)
│   ├── app_manager.py         # Application management (737 lines)
│   ├── file_manager.py        # File transfer & browsing (801 lines)
│   ├── screen_capture.py      # Screenshots & recording (552 lines)
│   ├── logcat.py              # Log viewer & filtering (738 lines)
│   ├── backup_restore.py      # Backup & restore (734 lines)
│   ├── device_controls.py     # Device control & settings (784 lines)
│   ├── performance.py         # Performance monitoring (735 lines)
│   ├── network_tools.py       # Network diagnostics (1100 lines)
│   ├── input_simulation.py    # Touch & input simulation (787 lines)
│   ├── ui_inspector.py        # UI hierarchy inspection (1019 lines)
│   ├── developer_options.py   # Developer settings toggle (562 lines)
│   ├── fastboot_tools.py      # Fastboot operations (672 lines)
│   ├── system_info.py         # System internals (635 lines)
│   ├── security_audit.py      # Security checks (605 lines)
│   └── automation.py          # Macros, scripts, batch ops (842 lines)
├── scripts/                   # Saved automation macros (JSON)
├── README.md
├── LICENSE
└── .gitignore
```

## 🔧 Prerequisites

Everything is auto-detected and installed, but for reference:

| Requirement | Status | Notes |
|---|---|---|
| Python 3.8+ | **Required** | Auto-checked on startup |
| ADB | **Required** | Auto-downloaded if missing |
| Fastboot | Optional | Needed for bootloader module only |
| USB Debugging | **Required** | Setup wizard guides you |
| USB Drivers | Windows only | Auto-detected, guide provided |

## ⚠️ Disclaimer

This tool is a convenience wrapper around Google's official ADB/Fastboot commands intended for **developers and testers only**. Use it only on devices you own or have explicit authorization to manage. The authors are not responsible for misuse.

## 📄 License

MIT License
