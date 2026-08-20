# 🏥 PhoneSurgeon — Complete Feature Guide

> **PhoneSurgeon** is an advanced, production-grade Android Debug Bridge (ADB) & Fastboot automation suite. Designed for security researchers, Android developers, QA engineers, reverse engineers, power users, and technicians, PhoneSurgeon provides deep device diagnostics, application management, live screen capture, system forensics, hardware controls, performance telemetry, UI inspection, security auditing, and automation scripting through an interactive terminal interface.

---

## 📑 Table of Contents

- [🚀 Auto-Setup Wizard & Dependency Engine](#-auto-setup-wizard--dependency-engine)
- [📱 Module 1: Device Information & Diagnostics](#-module-1-device-information--diagnostics)
- [📦 Module 2: Application Management](#-module-2-application-management)
- [📁 Module 3: File Manager & Storage Operations](#-module-3-file-manager--storage-operations)
- [📸 Module 4: Screen Capture & Video Recording](#-module-4-screen-capture--video-recording)
- [📋 Module 5: Logcat Viewer & Real-Time Diagnostics](#-module-5-logcat-viewer--real-time-diagnostics)
- [💾 Module 6: Backup & Restore Manager](#-module-6-backup--restore-manager)
- [🔧 Module 7: Device Controls & Power Management](#-module-7-device-controls--power-management)
- [📊 Module 8: Performance Monitor & Resource Telemetry](#-module-8-performance-monitor--resource-telemetry)
- [🌐 Module 9: Network Tools & Connectivity Diagnostics](#-module-9-network-tools--connectivity-diagnostics)
- [👆 Module 10: Input Simulation & Hardware Key Injection](#-module-10-input-simulation--hardware-key-injection)
- [🔍 Module 11: UI & Hierarchy Inspector](#-module-11-ui--hierarchy-inspector)
- [🛠️ Module 12: Developer Options & Tweaks](#️-module-12-developer-options--tweaks)
- [⚡ Module 13: Fastboot & Bootloader Tools](#-module-13-fastboot--bootloader-tools)
- [🖥️ Module 14: System Internals & Low-Level Diagnostics](#️-module-14-system-internals--low-level-diagnostics)
- [🔒 Module 15: Security Audit & Vulnerability Assessment](#-module-15-security-audit--vulnerability-assessment)
- [🤖 Module 16: Automation & Scripting Studio](#-module-16-automation--scripting-studio)
- [⌨️ Quick Reference Card & Keycode Index](#️-quick-reference-card--keycode-index)

---

## 🚀 Auto-Setup Wizard & Dependency Engine

The **Setup Wizard** (`core/setup_wizard.py`) guarantees zero-friction initial setup. When PhoneSurgeon is launched on a clean machine without Android platform tools or drivers, the wizard automatically detects missing dependencies, fetches official Google Platform-Tools, configures environment paths, verifies USB drivers, starts background daemons, and guides the user through enabling USB debugging.

### Features & Capabilities Table

| Feature / Step | Description | Technical Execution |
| :--- | :--- | :--- |
| **Python Version Verification** | Validates that the host environment runs Python 3.8 or newer. | `sys.version_info >= (3, 8)` |
| **ADB Auto-Detection** | Searches system `PATH` and managed tool cache (`~/.phonesurgeon/platform-tools/`) for `adb`. | `shutil.which("adb")` & Path verification |
| **Automated Platform-Tools Downloader** | Downloads official Google SDK Platform-Tools zip with a live stream progress bar for Windows, macOS, or Linux. | HTTP GET to `https://dl.google.com/android/repository/platform-tools-latest-<os>.zip` |
| **Automated Extraction & Chmod** | Extracts tools to `~/.phonesurgeon/platform-tools/` and grants Unix execution rights (`chmod +x`). | `zipfile.ZipFile`, `stat.S_IEXEC` |
| **Session & Permanent PATH Injection** | Prepends the managed binary directory to current session `PATH` and outputs permanent shell setup commands. | `os.environ["PATH"] = tools_dir + os.pathsep + ...` |
| **Fastboot Availability Probe** | Checks if `fastboot` is accessible for bootloader operations. | `shutil.which("fastboot")` |
| **ADB Server Initializer** | Automatically starts background `adb server` daemon. | `adb start-server` |
| **Device Connectivity Probe** | Polls connected USB/wireless endpoints and filters active devices. | `adb devices` |
| **Interactive USB Debugging Guide** | Displays step-by-step visual ASCII guide to unlock Developer Options and authorize RSA key prompts. | Terminal banner guide (Build number x7 -> Settings -> USB Debugging) |
| **Windows USB Driver Detection** | Probes Windows driver registry and connection state for missing OEM/Google USB drivers. | `adb devices` state checking (`unauthorized` / missing endpoints) |
| **Setup State Persistence** | Stores setup metadata in `~/.phonesurgeon/config.json` for fast instant boot on subsequent launches. | `json.dump(config, ~/.phonesurgeon/config.json)` |

> [!TIP]
> Run `python main.py --setup` at any time to force re-execution of the setup wizard and repair broken binary paths.

---

## 📱 Module 1: Device Information & Diagnostics

**Module:** `modules/device_info.py`  
**Overview:** In-depth hardware, firmware, battery, network, display, telephony, sensor, thermal zone, and system build property diagnostics.

```
📱 Device Information & Diagnostics
├── List connected devices (detailed overview)
├── Device model, brand, Android version & build
├── Hardware info (chipset, CPU cores, GPU, RAM)
├── Battery status (level, health, voltage, temp)
├── Screen info (resolution, density, refresh rate)
├── Network info (IP address, MAC, WiFi SSID)
├── SIM / telephony info (carrier, SIM state)
├── Sensor list (accelerometer, gyro, etc.)
├── Thermal zones / temperature diagnostics
├── Full build properties dump (search / export)
├── Storage overview (internal partitions, SD card)
├── Feature list (camera, NFC, bluetooth, etc.)
└── Export full device diagnostic report (.txt)
```

### Features Table

| # | Feature Name | Description | ADB / System Command Used |
| :-: | :--- | :--- | :--- |
| **1** | **List Connected Devices** | Enumerates all connected physical devices, emulators, and TCP endpoints with serial, connection type, product model, and authorization state. | `adb devices -l` |
| **2** | **Device Model & Build Info** | Displays manufacturer, brand, model, codename, board, Android version, dessert codename, API level, security patch date, build fingerprint, and A/B partition slot. | `adb shell getprop ro.product.*`, `ro.build.*`, `ro.boot.*` |
| **3** | **Hardware & Architecture** | Queries SoC vendor, CPU ABI list, 32/64-bit architecture, CPU core topology, frequency ranges, GPU renderer/driver via SurfaceFlinger, and RAM memory breakdown. | `adb shell cat /proc/cpuinfo`, `/sys/devices/system/cpu/online`, `dumpsys SurfaceFlinger`, `/proc/meminfo` |
| **4** | **Battery Status & Power** | Reads battery charge percentage, charging status (AC/USB/Wireless), health state, voltage in mV, temperature in °C/°F, battery technology, and microamp charge counters. | `adb shell dumpsys battery` |
| **5** | **Screen & Display Info** | Inspects physical resolution, override resolution, DPI density bucket (hdpi, xhdpi, etc.), refresh rate (Hz), display power state (ON/OFF/DOZE), brightness level, and screen timeout. | `adb shell wm size`, `wm density`, `dumpsys display`, `dumpsys input`, `settings get system screen_brightness` |
| **6** | **Network & Connectivity** | Displays IPv4/IPv6 interface bindings (`wlan0`, cellular, loopback), Wi-Fi SSID, BSSID, RSSI signal strength dBm, Wi-Fi MAC address, Bluetooth MAC, and DNS server IPs. | `adb shell ip -4 addr show`, `dumpsys wifi`, `/sys/class/net/wlan0/address`, `settings get secure bluetooth_address` |
| **7** | **SIM & Telephony Info** | Checks SIM card state, carrier/operator alphanumeric name, MCC+MNC numeric codes, cellular data network technology (LTE, NR/5G), voice network type, and secure Android ID. | `adb shell getprop gsm.sim.*`, `gsm.operator.*`, `gsm.network.type`, `settings get secure android_id` |
| **8** | **Hardware & Virtual Sensors** | Enumerate all physical and composite hardware sensors (accelerometers, gyroscopes, magnetometers, barometers, proximity) with vendor name, type handle, and power draw (mA). | `adb shell dumpsys sensorservice` |
| **9** | **Thermal Zones & Temperatures** | Scans all kernel thermal zones (`/sys/class/thermal/thermal_zone*`) to monitor real-time temperatures for CPU cores, GPU, battery, PMIC, and skin with heat status indicators. | `adb shell cat /sys/class/thermal/thermal_zone*/temp`, `dumpsys thermalservice` |
| **10** | **Full Build Properties Dump** | Interactive search, categorized viewing (core product, telephony, dalvik), and disk export for all system properties reported by the Android runtime. | `adb shell getprop` |
| **11** | **Storage Partitions Overview** | Summarizes filesystem space utilization (`/data`, `/system`, `/vendor`, `/sdcard`), mount points, used/available blocks, and cache statistics. | `adb shell df -h`, `adb shell dumpsys diskstats` |
| **12** | **System Feature Manifest** | Evaluates device hardware capabilities against official Android feature flags (Camera RAW, NFC HCE, BLE, Biometrics, GPS, Vulkan, OTG Host, Multi-window, etc.). | `adb shell pm list features` |
| **13** | **Export Diagnostic Report** | Compiles complete multi-section hardware and software profile into a timestamped `.txt` report file on the host machine. | Aggregated diagnostic pipeline |

---

## 📦 Module 2: Application Management

**Module:** `modules/app_manager.py`  
**Overview:** Complete package management suite for installing, analyzing, extracting, debugging, configuring, and uninstalling Android packages.

```
📦 Application Management
├── Install single APK (with replace/downgrade flags)
├── Install multiple APKs from local folder
├── Uninstall app (with optional data preservation)
├── List all installed apps (paginated overview)
├── List third-party (user) apps only
├── List system pre-installed apps only
├── Search installed apps by keyword & quick actions
├── Launch app (by package name)
├── Force stop running app
├── Clear app data & cache storage
├── View app permissions (runtime & install-time)
├── Get APK filesystem path on device
├── Extract / pull APK from device to PC
├── Disable / enable (freeze/unfreeze) app
├── App version & package metadata info
└── Open app details in device Settings UI
```

### Features Table

| # | Feature Name | Description | ADB / System Command Used |
| :-: | :--- | :--- | :--- |
| **1** | **Install Single APK** | Sideload an APK with optional flags: replace existing (`-r`), auto-grant all runtime permissions (`-g`), and allow version downgrade (`-d`). | `adb install [-r] [-g] [-d] <local_apk_path>` |
| **2** | **Batch Install APKs from Folder** | Scans a local folder for `.apk` files and installs all applications in batch with real-time progress indicators and a completion summary table. | `adb install -r [-g] <path_to_apk>` in sequence |
| **3** | **Uninstall Application** | Uninstalls target app by package name with an optional flag to retain data and cache directories (`-k`). | `adb uninstall [-k] <package_name>` |
| **4** | **List All Installed Packages** | Full paginated terminal browser of all packages installed on the device with search, navigation, and export to text file. | `adb shell pm list packages` |
| **5** | **List Third-Party Apps** | Filters package list to display only user-installed and sideloaded 3rd-party apps (`-3`). | `adb shell pm list packages -3` |
| **6** | **List System Applications** | Filters package list to display only pre-installed system vendor applications (`-s`). | `adb shell pm list packages -s` |
| **7** | **Search Installed Apps** | Fuzzy keyword search across installed package names with direct access to a **Quick Actions Submenu** (Launch, Stop, Clear, Permissions, Extract, Freeze, Uninstall). | `adb shell pm list packages` + interactive filter |
| **8** | **Launch Application** | Starts an application using the Monkey tool launcher intent or resolves top activity component. | `adb shell monkey -p <pkg> -c android.intent.category.LAUNCHER 1` / `adb shell am start -n <activity>` |
| **9** | **Force Stop Application** | Immediately terminates all running background processes, services, and tasks associated with the package name. | `adb shell am force-stop <package_name>` |
| **10** | **Clear App Data & Cache** | Wipes all application databases, shared preferences, user login tokens, and cache directories without uninstalling. | `adb shell pm clear <package_name>` |
| **11** | **Inspect App Permissions** | Dumps package manifest permissions and categorizes them into Granted Runtime Permissions, Denied Permissions, and Install-Time Permissions. | `adb shell dumpsys package <package_name>` |
| **12** | **Get APK Device Path** | Locates absolute filesystem path(s) of the application's base and split APKs on device flash storage. | `adb shell pm path <package_name>` |
| **13** | **Extract / Pull APK to PC** | Downloads the base APK and split configuration APKs from device flash to a local `extracted_apks/<pkg>` folder on the PC. | `adb shell pm path <pkg>` -> `adb pull <remote_apk> <local_dest>` |
| **14** | **Enable / Disable (Freeze) App** | Freezes (disables) bloatware or unfreezes apps for user 0 without requiring root privileges. | `adb shell pm disable-user --user 0 <pkg>` / `adb shell pm enable <pkg>` |
| **15** | **App Version & Metadata** | Extracts versionName, versionCode, targetSdk, minSdk, first install date, last update timestamp, installer package store, code path, and userId. | `adb shell dumpsys package <package_name>` |
| **16** | **Open App Settings UI** | Launches device Settings application directly into the target app's "App Info" page on the physical screen. | `adb shell am start -a android.settings.APPLICATION_DETAILS_SETTINGS -d package:<pkg>` |

---

## 📁 Module 3: File Manager & Storage Operations

**Module:** `modules/file_manager.py`  
**Overview:** Full-featured two-way file manager between host PC and Android device with safety guards against deleting system root paths.

```
📁 File Manager & Storage Operations
├── Push file to device
├── Pull file from device
├── Push entire folder (recursive)
├── Pull entire folder (recursive)
├── List directory contents (ls -la)
├── Search files by name (find)
├── Disk & storage usage (df / du)
├── Create directory on device
├── Delete file or folder on device
├── Move / rename file or folder
├── View file contents (cat / head / tail)
├── Check file info & permissions
├── Change file permissions (chmod)
├── Verify file checksum (MD5 / SHA256)
└── Create empty file (touch)
```

### Features Table

| # | Feature Name | Description | ADB / System Command Used |
| :-: | :--- | :--- | :--- |
| **1** | **Push File to Device** | Transfers a single file from host PC to device destination folder (defaults to `/sdcard/Download/`). | `adb push <local_file> <remote_dest>` |
| **2** | **Pull File from Device** | Downloads a remote file from Android storage to local `downloads/` directory on PC. | `adb pull <remote_file> <local_dest>` |
| **3** | **Push Folder (Recursive)** | Recursively uploads an entire local folder hierarchy to the device with file count and size calculations. | `adb push <local_dir> <remote_dir>` |
| **4** | **Pull Folder (Recursive)** | Recursively downloads an entire device directory (e.g. `/sdcard/DCIM/Camera`) to local PC storage. | `adb pull <remote_dir> <local_dest>` |
| **5** | **Directory Browser (`ls -la`)** | Tabular directory inspector displaying file permissions, owner, group, byte size, timestamps, and icons with quick presets (`/sdcard/`, `Download`, `DCIM`, `Documents`, `tmp`). | `adb shell ls -la <remote_path>` |
| **6** | **Search Files by Name (`find`)** | Searches remote directories by name patterns, wildcards, max depth, and file type filters (`-type f`, `-type d`). | `adb shell find <root> [-maxdepth N] [-type f\|d] -iname '<pattern>'` |
| **7** | **Disk & Storage Usage** | Analyzes partition capacity (`df -h`), calculates top-level folder sizes (`du -d 1 -h`), and scans for large files exceeding 50 MB. | `adb shell df -h`, `adb shell du -d 1 -h <path>`, `find /sdcard/ -size +50000k` |
| **8** | **Create Directory (`mkdir -p`)** | Creates new directories and necessary parent paths on device flash storage. | `adb shell mkdir -p <remote_path>` |
| **9** | **Delete File or Folder (`rm -rf`)** | Permanently deletes files or folders with confirmation checks and hardcoded protection against wiping system root directories. | `adb shell rm -f <file>` / `adb shell rm -rf <dir>` |
| **10** | **Move / Rename (`mv`)** | Moves or renames files and directories across remote Android filesystems. | `adb shell mv <src_path> <dst_path>` |
| **11** | **View File Content** | Reads remote text files with display modes: Full File (100 lines), First N Lines (`head -n`), Last N Lines (`tail -n`), or Keyword Search (`grep -in`). | `adb shell cat`, `head -n`, `tail -n`, `grep -in <pattern>` |
| **12** | **Inspect Metadata & SELinux** | Queries precise file attributes, octal modes, modification dates, ownership, and SELinux security contexts (`u:object_r:...`). | `adb shell stat <path>`, `adb shell ls -ldZ <path>` |
| **13** | **Change Permissions (`chmod`)** | Modifies file and directory permissions using presets (`755`, `644`, `777`, `600`, `700`, `+x`) or custom octal masks with recursive support (`-R`). | `adb shell chmod [-R] <mode> <path>` |
| **14** | **Verify File Checksum / Hash** | Calculates MD5, SHA-256, or SHA-1 hashes of remote files and verifies integrity against expected hash strings. | `adb shell md5sum`, `sha256sum`, `sha1sum <path>` |
| **15** | **Create Empty File (`touch`)** | Creates a blank file or updates existing file timestamps on device storage. | `adb shell touch <remote_path>` |

---

## 📸 Module 4: Screen Capture & Video Recording

**Module:** `modules/screen_capture.py`  
**Overview:** High-resolution screenshot capture, multi-shot burst photography, and video recording engine with custom bitrates, downscaling, and touch visualization.

```
📸 Screen Capture & Recording
├── Take single screenshot (timestamped)
├── Take burst screenshots (series with delay)
├── Record screen (default 10s)
├── Record screen (custom duration, max 180s)
├── Record screen with custom bitrate
├── Record screen with custom resolution
├── Take screenshot of specific display
├── Open screenshot / capture folder
├── Advanced recording (touches, bitrate, size)
├── View capture history & media list
└── Clean remote temporary capture files
```

### Features Table

| # | Feature Name | Description | ADB / System Command Used |
| :-: | :--- | :--- | :--- |
| **1** | **Single Screenshot** | Captures a PNG screenshot from device framebuffer, saves it locally in `captures/screenshots/`, and optionally opens it in host viewer. | `adb shell screencap -p <remote>` -> `adb pull` -> `rm -f` |
| **2** | **Burst Screenshot Capture** | Captures a sequence of 2 to 30 screenshots at configurable time intervals (0.2s - 5.0s) for testing fast animations or game frames. | Multi-shot `screencap -p` loop with progress tracking |
| **3** | **Screen Recording (Default 10s)** | Records high-definition MP4 video of the device screen for 10 seconds and automatically transfers it to `captures/recordings/`. | `adb shell screenrecord --time-limit 10 <remote.mp4>` -> `adb pull` |
| **4** | **Custom Duration Recording** | Records screen video for any user-specified duration from 1 second up to the Android limit of 180 seconds (3 minutes). | `adb shell screenrecord --time-limit <sec> <remote.mp4>` |
| **5** | **Custom Bitrate Recording** | Optimizes video quality or file size by setting video bitrate: 2 Mbps (Compact), 4 Mbps (Default), 8 Mbps (HD), 12 Mbps (High), 20 Mbps (Ultra), or custom Mbps. | `adb shell screenrecord --bit-rate <bps> --time-limit <sec>` |
| **6** | **Custom Resolution / Downscale** | Records video at native resolution, 720p HD, 1080p FHD, 50% Half-Scale, 480p SD, or custom `WxH` for lightweight bug reports. | `adb shell screenrecord --size <WxH> --time-limit <sec>` |
| **7** | **Multi-Display Screenshot** | Targets specific display IDs (`-d 0` Main, `-d 1` Foldable / External Display, `-d 2` Cast Display) on multi-screen devices. | `adb shell screencap -d <display_id> -p <remote>` |
| **8** | **Open Captures Directory** | Spawns the host operating system's native file explorer (Explorer on Windows, Finder on macOS, xdg-open on Linux) inside the `captures/` folder. | `os.startfile` / `open` / `xdg-open` |
| **9** | **Advanced Recording Wizard** | Interactive wizard configuring duration, bitrate, resolution downscale, visual touch indicators (`show_touches`), 90° rotation, and debug overlay banner. | `screenrecord [--bit-rate N] [--size WxH] [--rotate] [--bugreport]` |
| **10** | **Capture History & Gallery** | Interactive local media gallery displaying recent screenshots and recordings sorted by date with instant viewer launch. | Local directory scanner & OS viewer integration |
| **11** | **Clean Remote Temp Files** | Scans `/sdcard/` for orphaned screenshot PNGs or screenrecord MP4s left behind by previous sessions and deletes them. | `adb shell rm -f /sdcard/screenshot_*.png /sdcard/recording_*.mp4` |

---

## 📋 Module 5: Logcat Viewer & Real-Time Diagnostics

**Module:** `modules/logcat.py`  
**Overview:** Real-time Android log stream viewer, priority and tag filter engine, crash/ANR tracer, kernel dmesg reader, and buffer size manager.

```
📋 Logcat Viewer & Diagnostics
├── View recent logs (last 100 lines)
├── View logs by priority (V/D/I/W/E/F)
├── Filter logs by tag
├── Filter logs by PID / Package
├── Search logs by keyword / regex
├── View crash logs (ActivityManager / Fatal)
├── View ANR logs (Application Not Responding)
├── Clear logcat buffer
├── Save full logcat to file
├── View & configure buffer sizes
├── View kernel logs (dmesg)
├── View event logs (system events)
└── Live logcat stream (interactive)
```

### Features Table

| # | Feature Name | Description | ADB / System Command Used |
| :-: | :--- | :--- | :--- |
| **1** | **View Recent Logs** | Dumps the most recent N lines of logcat (default 100) in standard threadtime format with ANSI syntax coloring. | `adb logcat -d -t <count> -v threadtime` |
| **2** | **Filter Logs by Priority** | Filters log messages by minimum log level: Verbose (`V`), Debug (`D`), Info (`I`), Warning (`W`), Error (`E`), or Fatal (`F`). | `adb logcat -d *:<prio> -t <count> -v threadtime` |
| **3** | **Filter Logs by Tag** | Isolates log events produced by a specific tag (e.g. `AndroidRuntime`, `ActivityManager`, `AudioFlinger`, `flutter`, `Unity`, `OkHttp`). | `adb logcat -d -s <tag>:<prio> -t <count> -v threadtime` |
| **4** | **Filter Logs by PID / Package** | Automatically resolves package names to running process IDs (PID) via `pidof` / `ps -A` and filters logs exclusively for that process. | `adb logcat -d --pid <pid> -t <count> -v threadtime` |
| **5** | **Search Logs (Keyword / Regex)** | Scans up to 20,000 logcat entries with regular expression matching, case-sensitivity toggles, and visual term highlighting. | `adb logcat -d -t <depth> -v threadtime` + regex engine |
| **6** | **View Crash Logs** | Extracts unhandled fatal exceptions, Java stack traces from `AndroidRuntime:E`, dedicated crash buffer entries (`-b crash`), and tombstone files. | `adb logcat -b crash -d`, `adb logcat -d -s AndroidRuntime:E FATAL:* DEBUG:*`, `ls /data/tombstones/` |
| **7** | **View ANR Logs** | Analyzes Application Not Responding incidents, traces ActivityManager load dumps, and checks for trace dumps in `/data/anr/`. | `adb logcat -d -s ActivityManager:E`, `adb shell dumpsys activity anrs` |
| **8** | **Clear Logcat Buffer** | Flushes ring buffer memory for all buffers or specific individual buffers (`main`, `system`, `events`, `crash`, `radio`). | `adb logcat [-b <buffer>] -c` |
| **9** | **Save Logcat to File** | Dumps logcat buffers (`main`, `crash`, `events`, `radio`, `all`) in selected formats (`threadtime`, `time`, `brief`, `uid`, `process`) to local `.txt` file. | `adb logcat -b <buf> -d -v <format>` |
| **10** | **View & Configure Buffer Sizes** | Queries buffer memory consumption (`logcat -g`) and dynamically resizes ring buffers from 256 KB up to 64 MB (`logcat -G`). | `adb logcat -g`, `adb logcat -G <size>` |
| **11** | **View Kernel Logs (`dmesg`)** | Reads Linux kernel ring buffer messages (`dmesg` / `/proc/kmsg`) with severity highlights and local file export. | `adb shell dmesg`, `adb shell cat /proc/kmsg` |
| **12** | **View Event Logs** | Decodes binary system events buffer (`-b events`) displaying process spawns (`am_proc_start`), kills (`am_kill`), focus shifts, and battery events. | `adb logcat -b events -d -t <count> -v threadtime` |
| **13** | **Live Logcat Stream** | Streams live log events to the terminal in real-time with continuous syntax colorization until interrupted by `Ctrl+C`. | `adb logcat -v threadtime [-s <filter>]` |

---

## 💾 Module 6: Backup & Restore Manager

**Module:** `modules/backup_restore.py`  
**Overview:** Comprehensive data preservation toolkit for full device backups, app data archiving, shared storage extraction, contacts export (vCard/CSV), SMS/Call logs dumps, and `.ab` archive analysis.

```
💾 Backup & Restore Manager
├── Full device backup (apps + data + storage)
├── Backup specific app
├── Backup without APKs (data only)
├── Backup shared storage (media/files)
├── Restore from backup file (.ab)
├── Backup contacts (vCard & CSV export)
├── List available backups in directory
├── Backup encryption note & security guide
├── Backup SMS & Call logs (content dump)
├── Export installed packages manifest
└── Inspect & analyze .ab backup file
```

### Features Table

| # | Feature Name | Description | ADB / System Command Used |
| :-: | :--- | :--- | :--- |
| **1** | **Full Device Backup** | Generates an encrypted or unencrypted `.ab` backup of all installed apps, private application data, OBB expansion files, and shared storage. | `adb backup -apk -obb [-shared] -all [-system] -f <file.ab>` |
| **2** | **Backup Specific App** | Creates a targeted backup archive for a single selected package with optional inclusion of the base APK installer and OBB data. | `adb backup [-apk] [-obb] -f <file.ab> <package_name>` |
| **3** | **Backup Data Only (No APKs)** | Creates lightweight backups containing only app settings, databases, and accounts (`-noapk`) for rapid data migration. | `adb backup -noapk -obb [-all | <pkg>] -f <file.ab>` |
| **4** | **Backup Shared Storage** | Archives user media (Photos, DCIM, Documents, Downloads, Music) via direct multi-folder pull or full storage archive. | `adb pull /sdcard/<folder> ...` / `adb backup -shared` |
| **5** | **Restore from Backup File** | Restores device applications and data states from a local `.ab` archive with on-device password decryption prompts. | `adb restore <file.ab>` |
| **6** | **Backup Contacts (vCard / CSV)** | Dumps contacts database from Android Content Provider and converts records into standard vCard 3.0 (`.vcf`) and tabular `.csv` formats. | `adb shell content query --uri content://contacts/phones/` |
| **7** | **List Available Backups** | Catalogs and inspects all local backup archives (`.ab`, `.vcf`, `.csv`, `.json`, `.tar`) in the workspace directory. | Local workspace catalog engine |
| **8** | **Backup Encryption Guide** | Detailed technical documentation on desktop backup passwords, AES-256-CBC encryption, Android 12 extraction rules, and ABE unpack tools. | Embedded security knowledge engine |
| **9** | **Backup SMS & Call Logs** | Queries SMS and telephony call log content providers to export message history and call records into structured CSV files. | `adb shell content query --uri content://sms`, `content://call_log/calls` |
| **10** | **Export Package Manifest** | Generates complete JSON and plain-text inventory manifests of all installed apps, version numbers, APK paths, and system flags. | `adb shell pm list packages -f -u` |
| **11** | **Inspect & Analyze `.ab` File** | Decodes the 24-byte header of an Android Backup archive: compression method (zlib deflated), encryption algorithm (AES-256), user salt, PBKDF2 rounds, and IV. | Low-level binary header parser |

---

## 🔧 Module 7: Device Controls & Power Management

**Module:** `modules/device_controls.py`  
**Overview:** Power state management, boot modes, wireless ADB configuration, screen power & brightness adjustments, airplane mode toggles, and shell access.

```
🔧 Device Controls & Power Management
├── Reboot device (normal)
├── Reboot to recovery
├── Reboot to bootloader
├── Soft reboot (hot restart)
├── Enable WiFi ADB (tcpip 5555)
├── Connect via WiFi (IP:port)
├── Disconnect WiFi device
├── Open interactive ADB shell
├── Send text input to device
├── Send key event (keycodes list)
├── Toggle screen on/off
├── Set screen brightness
├── Set screen timeout
├── Toggle airplane mode
├── Set screen rotation (auto/portrait/landscape)
└── Keep screen awake toggle
```

### Features Table

| # | Feature Name | Description | ADB / System Command Used |
| :-: | :--- | :--- | :--- |
| **1** | **Normal Reboot** | Restarts the device operating system normally. | `adb reboot` |
| **2** | **Reboot to Recovery** | Reboots device into Recovery mode for sideloading updates, clearing cache partitions, or flashing ZIPs. | `adb reboot recovery` |
| **3** | **Reboot to Bootloader** | Reboots device into Fastboot / Bootloader mode for partition flashing. | `adb reboot bootloader` |
| **4** | **Soft Reboot (Hot Restart)** | Performs userspace framework restart (Zygote & SystemUI) without cycling kernel or hardware power. | `adb shell setprop ctl.restart zygote` / `svc power reboot` |
| **5** | **Enable WiFi ADB (TCP/IP)** | Switches ADB daemon from USB mode to TCP/IP listening mode on port 5555 (or custom port) and auto-detects device Wi-Fi IP. | `adb tcpip <port>`, detects IP via `ip addr show wlan0` |
| **6** | **Connect via WiFi (IP:Port)** | Establishes wireless ADB debug connection to an Android device over local Wi-Fi. | `adb connect <ip>:<port>` |
| **7** | **Disconnect WiFi Device** | Disconnects specific or all active wireless ADB connections. | `adb disconnect [<target>]` |
| **8** | **Interactive Shell** | Launches full interactive ADB shell terminal session directly within PhoneSurgeon. | `adb shell` (PTY interactive bridge) |
| **9** | **Send Text Input** | Types text strings into the focused text input field with automatic character escaping, URL formatting, or clipboard injection. | `adb shell input text <escaped>`, `input keyevent 279` |
| **10** | **Send Key Event** | Dispatches standard Android keycodes from a categorised quick-selection menu with repeat counts. | `adb shell input keyevent <keycode>` |
| **11** | **Toggle Screen State** | Reads power manager wakefulness and toggles power (`26`), forces wake (`224`), forces sleep (`223`), or wakes and swipes to unlock. | `dumpsys power`, `input keyevent 26/224/223`, `input swipe` |
| **12** | **Set Screen Brightness** | Adjusts display brightness (0 - 255 / 0% - 100%) and toggles adaptive / automatic brightness mode. | `adb shell settings put system screen_brightness <val>`, `screen_brightness_mode <0\|1>` |
| **13** | **Set Screen Timeout** | Configures display sleep timeout from 15 seconds up to 24 days (Never / Maximum). | `adb shell settings put system screen_off_timeout <ms>` |
| **14** | **Toggle Airplane Mode** | Enables, disables, or flips global Airplane Mode and broadcasts state change intent. | `settings put global airplane_mode_on <0\|1>`, `am broadcast -a android.intent.action.AIRPLANE_MODE` |
| **15** | **Set Screen Rotation** | Configures auto-rotation accelerometer or locks screen orientation to Portrait (0°), Landscape (90°), Reverse Portrait (180°), or Reverse Landscape (270°). | `settings put system accelerometer_rotation <0\|1>`, `settings put system user_rotation <0-3>` |
| **16** | **Keep Screen Awake (Stay On)** | Configures device to stay awake while plugged into AC charger, USB, or Wireless power. | `settings put global stay_on_while_plugged_in <1-7>`, `svc power stayon true/false/usb/ac` |

---

## 📊 Module 8: Performance Monitor & Resource Telemetry

**Module:** `modules/performance.py`  
**Overview:** Real-time hardware telemetry, CPU load breakdown, RAM/ZRAM memory diagnostics, process rankings, disk I/O, network bandwidth, and UI frame rendering profiling.

```
📊 Performance Monitor
├── CPU info (cores, architecture, frequencies)
├── Memory info (RAM total/free/available)
├── Storage info (df -h)
├── Battery stats detailed (dumpsys battery)
├── GPU info (renderer, version)
├── Running processes (top 25 by memory)
├── App-specific memory usage (dumpsys meminfo)
├── CPU usage by app (top snapshot)
├── Disk I/O stats (/proc/diskstats)
├── Network data usage stats (/proc/net/dev)
├── Frame rendering stats (dumpsys gfxinfo)
└── System uptime (/proc/uptime)
```

### Features Table

| # | Feature Name | Description | ADB / System Command Used |
| :-: | :--- | :--- | :--- |
| **1** | **CPU Architecture & Frequencies** | Queries SoC model, CPU ABIs, online/present core ranges, and reads per-core real-time scaling frequencies (MHz), min/max limits, and governors. | `adb shell cat /proc/cpuinfo`, `/sys/devices/system/cpu/cpu*/cpufreq/*` |
| **2** | **RAM & Memory Breakdown** | Parses `/proc/meminfo` to display total, used, free, cached, buffer, active, dirty, slab, and ZRAM/Swap memory with visual percentage progress bars. | `adb shell cat /proc/meminfo` |
| **3** | **Storage Partitions Overview** | Summarizes filesystem storage allocations (`df -h`) and high-level dumpsys diskstats metrics. | `adb shell df -h`, `adb shell dumpsys diskstats` |
| **4** | **Battery Diagnostics** | Displays voltage (V/mV), temperature (°C/°F), charging power sources, charge counter capacity (mAh), and health state. | `adb shell dumpsys battery` |
| **5** | **GPU & Graphics Subsystem** | Queries GPU renderer, vendor, OpenGL ES version, Vulkan capabilities, driver package name, and real-time Adreno GPU clock frequency (MHz). | `adb shell dumpsys SurfaceFlinger`, `dumpsys gpu`, `/sys/class/kgsl/kgsl-3d0/gpuclk` |
| **6** | **Running Processes (Top 25)** | Displays top 25 active processes sorted by physical memory consumption (RSS) or CPU utilization percentage. | `adb shell ps -A -o PID,USER,%CPU,%MEM,VSZ,RSS,NAME --sort=-rss/-%cpu` |
| **7** | **App Memory Profile (`meminfo`)** | Deep memory inspection of target package via `dumpsys meminfo` (Java Heap, Native Heap, Code, Stack, Graphics, Total PSS, and Active Objects). | `adb shell dumpsys meminfo <package_name>` |
| **8** | **CPU Usage by App (`cpuinfo`)** | Samples system and per-process CPU load breakdown (User %, Kernel %, I/O Wait %). | `adb shell dumpsys cpuinfo` |
| **9** | **Block Device Disk I/O** | Reads `/proc/diskstats` to measure completed read/write operations, sectors transferred, megabytes read/written, and active I/O times per block device. | `adb shell cat /proc/diskstats` |
| **10** | **Network Bandwidth Telemetry** | Inspects `/proc/net/dev` to report bytes received (RX), packets, errors, and bytes transmitted (TX) for Wi-Fi and Cellular interfaces. | `adb shell cat /proc/net/dev` |
| **11** | **UI Frame Rendering (`gfxinfo`)** | Profiles UI frame rendering latencies, calculating janky frames percentage (>16.6ms for 60fps), 50th/90th/95th/99th percentiles, missed VSYNCs, and slow UI threads. | `adb shell dumpsys gfxinfo <package_name>` |
| **12** | **System Uptime & Power State** | Reports total system uptime in days/hours/minutes, CPU idle time across all cores, system boot timestamp, and wakefulness status. | `adb shell cat /proc/uptime`, `dumpsys power` |

---

## 🌐 Module 9: Network Tools & Connectivity Diagnostics

**Module:** `modules/network_tools.py`  
**Overview:** Network diagnostics, Wi-Fi link analysis, IP configuration, open port auditing, routing tables, ICMP pings, DNS resolvers, and live throughput monitoring.

```
🌐 Network Tools & Diagnostics
├── Wi-Fi Information (SSID, RSSI, Band, Speed)
├── Wi-Fi IP Address & Interface Details
├── Cellular & Mobile Data Information
├── Ping a Host / IP from Device
├── DNS Lookup & Private DNS Resolver
├── View Kernel Routing Table
├── View Open Ports (netstat)
├── View Network Interfaces Overview
├── Data Usage Stats & Live Throughput
├── Test HTTP / HTTPS Connectivity
├── View Saved Wi-Fi Networks
├── Toggle Wi-Fi Power (On / Off / Reconnect)
├── View Active Network Connections
└── Automated Network Diagnostics Scorecard
```

### Features Table

| # | Feature Name | Description | ADB / System Command Used |
| :-: | :--- | :--- | :--- |
| **1** | **Wi-Fi Connection Info** | Displays SSID, BSSID access point MAC, signal strength (RSSI dBm with quality bar), frequency band (2.4 GHz / 5 GHz / 6 GHz), link speeds (Tx/Rx), and Wi-Fi 4/5/6/7 standard. | `adb shell dumpsys wifi`, `settings get global wifi_on` |
| **2** | **Wi-Fi IP Address Details** | Detailed inspection of `wlan0` link state, MTU, hardware MAC, IPv4 CIDR, IPv6 scopes, default gateway, DHCP servers, and lease duration. | `adb shell ip addr show wlan0`, `ip route show dev wlan0`, `getprop dhcp.wlan0.*` |
| **3** | **Cellular & Mobile Data Info** | Inspects registered carrier name, SIM provider, radio access technology (LTE, 5G NR), SIM state, MCC/MNC, roaming state, and active APN profile. | `adb shell getprop gsm.*`, `dumpsys telephony.registry` |
| **4** | **Ping Host from Device** | Executes ICMP ping from the device to targets (Google DNS 8.8.8.8, Cloudflare 1.1.1.1, Gateway, or custom IP) with packet loss % and RTT stats table. | `adb shell ping -c <count> -W 3 <target>` |
| **5** | **DNS Lookup & Resolver Info** | Inspects configured DNS servers, Private DNS mode (DNS-over-TLS specifiers), and performs remote domain name resolution. | `adb shell getprop net.dns*`, `settings get global private_dns_*`, `nslookup <domain>` |
| **6** | **Kernel Routing Table** | Dumps active IPv4 and IPv6 kernel routing tables with destination prefixes, next-hop gateways, interfaces, and flags. | `adb shell ip route show`, `ip -6 route show`, `cat /proc/net/route` |
| **7** | **Open Ports & Sockets (`netstat`)** | Scans listening TCP and UDP endpoints and identifies known port services (DNS, HTTP, HTTPS, ADB, FCM). | `adb shell netstat -tuln`, `/proc/net/tcp`, `/proc/net/udp` |
| **8** | **Network Interfaces Overview** | Lists all physical and virtual interfaces (`wlan0`, `rmnet*`, `dummy0`, `lo`, `p2p0`) with MTU, link state, MAC address, and bound IP addresses. | `adb shell ip addr show` |
| **9** | **Data Usage & Live Throughput** | Summarizes cumulative byte counters per interface and offers an optional 5-second real-time download/upload bandwidth monitor (KB/s, MB/s). | `adb shell cat /proc/net/dev` with delta sampling |
| **10** | **HTTP / HTTPS Reachability** | Tests web endpoints via `curl` / `wget` measuring HTTP response status codes, DNS lookup latency, TCP connect latency, and total transfer time. | `adb shell curl -s -o /dev/null -w ...` / `wget` |
| **11** | **View Saved Wi-Fi Networks** | Dumps configured Wi-Fi network profiles with network IDs, SSIDs, and security encryption types (WPA2_PSK, SAE, OPEN). | `adb shell cmd wifi list-networks` / `dumpsys wifi` |
| **12** | **Toggle Wi-Fi Power** | Controls Wi-Fi radio power: Turn ON, Turn OFF, flip state, trigger reconnect, or initiate an active network scan. | `adb shell svc wifi enable/disable`, `cmd wifi set-wifi-enabled`, `cmd wifi reconnect`, `cmd wifi start-scan` |
| **13** | **Active Socket Connections** | Lists active outgoing TCP connections (ESTABLISHED, SYN_SENT, TIME_WAIT, CLOSE_WAIT) and maps remote endpoint ports to services. | `adb shell netstat -an`, `/proc/net/tcp` |
| **14** | **Automated Diagnostics Scorecard** | Automated 6-point network health audit checking Wi-Fi power, IP assignment, gateway response, global ICMP, DNS resolution, and HTTP captive check. | Automated end-to-end test suite |

---

## 👆 Module 10: Input Simulation & Hardware Key Injection

**Module:** `modules/input_simulation.py`  
**Overview:** Touch simulation, coordinate taps, long presses, swipe gesture presets, text typing, clipboard injection, and hardware button control.

```
👆 Input Simulation & Hardware Controls
├── Tap at Coordinates (X, Y)
├── Long Press at Coordinates
├── Custom Swipe (Start X,Y -> End X,Y)
├── Swipe Gestures (Scroll, Fling, Edge Swipes)
├── Type Text on Device (Keyboard / Clipboard)
├── Send Key Event (with Reference Table)
├── Send Key Combination (Ctrl+A/C/V, Alt+Tab)
├── Quick Navigation Buttons (Home, Back, Recents, Power)
├── Open / Collapse Notifications Shade
├── Open / Collapse Quick Settings
├── Capture Screenshot (Hardware Combo / Screencap)
├── Volume Controls (Up, Down, Mute, Set Level)
└── Media Playback Controls (Play, Pause, Next, Prev)
```

### Features Table

| # | Feature Name | Description | ADB / System Command Used |
| :-: | :--- | :--- | :--- |
| **1** | **Tap at Coordinates** | Injects single or repeated screen taps at exact (X, Y) screen coordinates or screen center (`c`). | `adb shell input tap <X> <Y>` |
| **2** | **Long Press Gesture** | Simulates touch-and-hold gestures at coordinates for a configurable duration (default: 1000 ms). | `adb shell input swipe <X> <Y> <X> <Y> <duration_ms>` |
| **3** | **Custom Swipe** | Executes custom directional swipe from (X1, Y1) to (X2, Y2) with user-defined duration. | `adb shell input swipe <X1> <Y1> <X2> <Y2> <duration_ms>` |
| **4** | **Swipe Gesture Presets** | Pre-calculated gestures: Scroll Down/Up, Swipe Left/Right, Fast Fling, Left/Right Edge Back Gestures, Bottom Home Gesture, and Recent Apps Swipe-and-Hold. | `adb shell input swipe <X1> <Y1> <X2> <Y2> <dur>` based on screen WxH |
| **5** | **Type Text on Device** | Injects text into active fields via direct typing (with shell character auto-escaping), fast clipboard paste injection (`cmd clipboard set text` + paste), or type + enter. | `adb shell input text <escaped>`, `cmd clipboard set text` + `input keyevent 279` |
| **6** | **Send Key Event** | Interactive browser for the complete Android keycode catalogue (Navigation, Power, Volume, Media, D-Pad, Editing) with optional long-press flag (`--longpress`). | `adb shell input keyevent [--longpress] <keycode>` |
| **7** | **Send Key Combinations** | Injects simultaneous multi-key modifier combos: Ctrl+A (Select All), Ctrl+C (Copy), Ctrl+V (Paste), Ctrl+X (Cut), Ctrl+Z (Undo), Alt+Tab (Task Switcher), Power+VolDown. | `adb shell input keycombination <key1> <key2>` |
| **8** | **Quick Navigation Buttons** | Dedicated one-touch triggers for Home (3), Back (4), Recent Apps (187), Power (26), Wakeup (224), Sleep (223), Menu (82), Voice Assistant (231), and Camera (27). | `adb shell input keyevent <keycode>` |
| **9** | **Notifications Shade Control** | Expands notification shade downward or collapses status bar. | `adb shell cmd statusbar expand-notifications` / `collapse` |
| **10** | **Quick Settings Shade Control** | Expands full Quick Settings tile shade or collapses back to normal. | `adb shell cmd statusbar expand-settings` / `collapse` |
| **11** | **Screenshot Hardware Combo** | Triggers native hardware screenshot key combo (Power + Volume Down) or direct framebuffer screencap. | `adb shell input keycombination 26 25`, `screencap -p` |
| **12** | **Volume Controls** | Volume Up (`24`), Volume Down (`25`), Mute (`164`), Max Volume, Minimum Silence, or setting exact media volume level (0 - 15). | `adb shell input keyevent 24/25/164`, `cmd media_session volume --stream 3 --set <val>` |
| **13** | **Media Playback Controls** | Controls audio/video media sessions: Play/Pause (`85`), Play (`126`), Pause (`127`), Next (`87`), Previous (`88`), Stop (`86`), Fast Forward (`90`), Rewind (`89`), and dump media session info. | `adb shell input keyevent <keycode>`, `dumpsys media_session` |

---

## 🔍 Module 11: UI & Hierarchy Inspector

**Module:** `modules/ui_inspector.py`  
**Overview:** Real-time UI hierarchy layout dumper, active Activity/Fragment inspector, window policy debugger, content provider auditor, and intent filter analyzer.

```
🔍 UI & Hierarchy Inspector
├── Dump UI Hierarchy (XML) & Element Tree
├── Get Current Activity & Task Info
├── Get Current Fragment(s)
├── List Recent Activities (Task Stack)
├── Get Focused Window Technical Info
├── List All Active Windows & Overlays
├── View Content Providers of Current App
├── View Running Services
├── Dump Accessibility Subsystem Info
├── Get Display & Cutout Info
├── View Intent Filters for Current App
└── WindowManager & System UI Policy
```

### Features Table

| # | Feature Name | Description | ADB / System Command Used |
| :-: | :--- | :--- | :--- |
| **1** | **Dump UI Hierarchy (XML)** | Captures active view tree via `uiautomator dump`, parses XML nodes into interactive elements (bounds, center coordinates, IDs, text), allows searching elements, and supports tapping elements directly by index number. | `adb shell uiautomator dump /data/local/tmp/uidump.xml` -> `cat` -> parse XML |
| **2** | **Get Current Activity & Task** | Identifies foreground package name, activity class, PID, and package details with quick actions (Force stop, Restart, Open settings, Clear data). | `adb shell dumpsys window windows` (mCurrentFocus / mFocusedApp), `dumpsys activity top` |
| **3** | **Inspect Active Fragments** | Dumps FragmentManager hierarchy of the top activity displaying active and added fragments with hash IDs and state. | `adb shell dumpsys activity top` (FragmentManager section) |
| **4** | **List Recent Activities (Stack)** | Inspects task records and recent activity backstacks showing Task IDs, package names, top activities, and task hashes. | `adb shell dumpsys activity recents`, `dumpsys activity activities` |
| **5** | **Focused Window Details** | Detailed technical breakdown of the active window: window type, frame bounds, surface size, `FLAG_SECURE` status (screenshot blocking), alpha opacity, layer Z-order, and display ID. | `adb shell dumpsys window windows` (Window block parsing) |
| **6** | **List All Windows & Overlays** | Enumerate all active system windows, dialogs, status bar layers, navigation bars, and third-party overlays sorted by Z-order. | `adb shell dumpsys window windows` |
| **7** | **View Content Providers** | Lists published content providers, authorities, hosting packages, process names, and active client connection counts. | `adb shell dumpsys activity providers` |
| **8** | **View Running Services** | Audits active background and foreground services, process bindings, PIDs, and foreground service notification flags. | `adb shell dumpsys activity services` |
| **9** | **Accessibility Subsystem Info** | Inspects enabled accessibility services, touch exploration state (TalkBack), screen magnification flags, and high-contrast text settings. | `adb shell settings get secure enabled_accessibility_services`, `dumpsys accessibility` |
| **10** | **Display & Cutout Metrics** | Reports physical/override resolution, density DPI buckets, refresh rates (Hz), display state, rotation, and physical notch/cutout bounds (`DisplayCutout`). | `adb shell wm size`, `wm density`, `dumpsys display`, `dumpsys window displays` |
| **11** | **View App Intent Filters** | Decodes package manifest components and lists public activity intent filters, supported actions, categories, and deep link URL schemes (`http`, `custom://`). | `adb shell dumpsys package <package_name>` |
| **12** | **WindowManager Policy & State** | Inspects Keyguard (lockscreen) visibility state, screen power policy, orientation sensor availability, status/nav bar windows, and current IME input method target. | `adb shell dumpsys window policy` |

---

## 🛠️ Module 12: Developer Options & Tweaks

**Module:** `modules/developer_options.py`  
**Overview:** System UI developer settings, hardware debugging flags, animation speed scalers, GPU rendering overlays, StrictMode toggles, and SystemUI Demo Mode.

```
🛠️ Developer Options & Tweaks
├── Toggle Show Layout Bounds
├── Toggle GPU Overdraw Visualization
├── Set Window Animation Scale
├── Set Transition Animation Scale
├── Set Animator Duration Scale
├── Toggle Show Touches (Visual Taps)
├── Toggle Pointer Location Overlay
├── Toggle StrictMode Visual Flash
├── USB Debugging & Stay Awake Settings
├── Set Background Process Limit
├── Toggle WebView Debugging & Inspect
├── Force GPU Rendering & Profile HWUI
├── Toggle Force 4x MSAA
├── Show Developer Settings Overview
├── Quick Animation & Speed Presets
└── SystemUI Demo Mode (Clean Status Bar)
```

### Features Table

| # | Feature Name | Description | ADB / System Command Used |
| :-: | :--- | :--- | :--- |
| **1** | **Toggle Show Layout Bounds** | Toggles on-screen rendering of view clip bounds, margins, and padding boxes with instant GUI refresh. | `adb shell setprop debug.layout true/false` + `service call activity 1599295570` |
| **2** | **GPU Overdraw Visualization** | Visualizes GPU overdraw on screen (Blue: 1x, Green: 2x, Light Red: 3x, Dark Red: 4x+) or displays overdraw numeric counters. | `adb shell setprop debug.hwui.overdraw false/show/count` |
| **3** | **Window Animation Scale** | Configures window animation duration scale: 0.0x (Instant), 0.5x (Snappy), 1.0x (Default), 1.5x, 2.0x, 5.0x, 10.0x, or custom float. | `adb shell settings put global window_animation_scale <val>` |
| **4** | **Transition Animation Scale** | Configures transition animation duration scale across screen transitions. | `adb shell settings put global transition_animation_scale <val>` |
| **5** | **Animator Duration Scale** | Configures ObjectAnimator and progress bar duration scales. | `adb shell settings put global animator_duration_scale <val>` |
| **6** | **Toggle Show Touches** | Enables or disables circular visual touch feedback indicators that follow finger touches on the screen. | `adb shell settings put system show_touches 1/0` |
| **7** | **Toggle Pointer Location** | Toggles status bar coordinate tracker (X, Y, dX, dY, Pressure, Size) and crosshair touch path overlays. | `adb shell settings put system pointer_location 1/0` |
| **8** | **StrictMode Visual Flash** | Toggles screen border flashing when applications perform long disk I/O or network operations on the main UI thread. | `adb shell setprop persist.sys.strictmode.visual 1/0` + `persist.sys.strictmode.disable 0/1` |
| **9** | **USB Debugging & Stay Awake** | Inspects ADB settings, configures stay awake charging modes (AC + USB + Wireless), or switches to wireless port 5555. | `settings put global stay_on_while_plugged_in <val>`, `adb tcpip 5555` |
| **10** | **Background Process Limits** | Configures background process limit (Standard, 0, 1, 2, 3, 4) and disables Android 12-14 Phantom Process Killer for long-running daemons like Termux. | `dumpsys activity set-bg-limit <val>`, `device_config put activity_manager max_phantom_processes 2147483647` |
| **11** | **WebView Debugging & Inspect** | Enables WebView remote developer inspection and displays Chrome / Edge DevTools pairing URLs (`chrome://inspect/#devices`). | `adb shell setprop debug.web.developer_mode 1/0`, `dumpsys webviewupdate` |
| **12** | **Force GPU Rendering & Profile** | Toggles forced 2D hardware acceleration (`persist.sys.force_hw_ui`) and renders on-screen HWUI frame latency bar graphs. | `adb shell setprop debug.hwui.profile visual_bars/true/false`, `setprop persist.sys.force_hw_ui 1/0` |
| **13** | **Toggle Force 4x MSAA** | Forces 4x Multisample Anti-Aliasing in OpenGL ES 2.0 applications for smooth 3D rendering. | `adb shell setprop debug.egl.force_msaa 1/0` |
| **14** | **Developer Settings Dashboard** | Unified diagnostic overview displaying the status of all developer options, animation scales, and hardware flags. | Aggregated settings and property query engine |
| **15** | **Quick Animation Presets** | One-touch presets: ⚡ Super Speed (0.0x all), 🚀 Snappy (0.5x all), 🔄 Default (1.0x all), or 🐛 UI Debugger (2.0x + Bounds + Touches). | Multi-setting batch configuration |
| **16** | **SystemUI Demo Mode** | Forces status bar into presentation mode: 12:00 clock, 100% battery, full Wi-Fi/LTE signal bars, and hidden notifications for clean screenshots. | `settings put global sysui_demo_allowed 1`, `am broadcast -a com.android.systemui.demo ...` |

---

## ⚡ Module 13: Fastboot & Bootloader Tools

**Module:** `modules/fastboot_tools.py`  
**Overview:** Low-level firmware flashing, bootloader variable inspection, partition erasing, temporary RAM booting, OEM unlocking/locking, and A/B slot switching.

```
⚡ Fastboot & Bootloader Tools
├── Check Fastboot Devices
├── Get All Bootloader Variables (getvar all)
├── Get Specific Bootloader Variable
├── Flash Boot Image (boot.img)
├── Flash Recovery Image (recovery.img)
├── Flash System Image (system.img)
├── Flash Custom Partition (vendor/vbmeta/etc.)
├── Erase / Wipe Partition
├── Reboot Options (System/Recovery/Bootloader)
├── OEM Bootloader Unlock (flashing unlock)
├── OEM Bootloader Lock (flashing lock)
├── Boot Image Without Flashing (fastboot boot)
├── Switch Active Slot (A/B Partitioning)
└── Reboot Device from ADB into Fastboot
```

### Features Table

| # | Feature Name | Description | Fastboot / ADB Command Used |
| :-: | :--- | :--- | :--- |
| **1** | **Check Fastboot Devices** | Scans USB bus for devices in Fastboot or Fastbootd mode. | `fastboot devices` |
| **2** | **Get All Bootloader Variables** | Reads all bootloader parameters (`getvar all`) and categorizes them into Hardware/Firmware, Security/Lock, A/B Slots, and Power Limits with file export. | `fastboot getvar all` |
| **3** | **Get Specific Variable** | Queries a single variable (e.g. `unlocked`, `product`, `current-slot`, `battery-voltage`, `max-download-size`). | `fastboot getvar <var_name>` |
| **4** | **Flash Boot Image** | Flashes a kernel/boot image (`boot.img`, Magisk patched boot) to `boot`, `boot_a`, `boot_b`, or `init_boot`. | `fastboot flash boot[_a|_b|init_boot] <file.img>` |
| **5** | **Flash Recovery Image** | Flashes a custom recovery image (TWRP, OrangeFox, PBRP) to `recovery` or slot partitions. | `fastboot flash recovery[_a|_b] <file.img>` |
| **6** | **Flash System Image** | Flashes a generic system image (GSI) or ROM partition to `system` with large-file timeout buffers. | `fastboot flash system[_a|_b] <file.img>` |
| **7** | **Flash Custom Partition** | Flashes images to arbitrary partitions (`vendor`, `vbmeta`, `dtbo`, `modem`, `userdata`) with optional AVB bypass flags (`--disable-verity --disable-verification`). | `fastboot [--disable-verity --disable-verification] flash <partition> <file.img>` |
| **8** | **Erase / Wipe Partition** | Formats and wipes specified partitions (`userdata`, `cache`, `metadata`, `misc`) with critical brick-prevention safety guards. | `fastboot erase <partition>` |
| **9** | **Fastboot Reboot Menu** | Reboots device to System (`reboot`), Recovery (`reboot recovery`), Bootloader (`reboot bootloader`), Fastbootd (`reboot fastboot`), continues boot (`continue`), or powers off (`oem poweroff`). | `fastboot reboot [recovery|bootloader|fastboot]`, `continue`, `oem poweroff` |
| **10** | **OEM Bootloader Unlock** | Dispatches bootloader unlock command (`flashing unlock`, `oem unlock`, or `flashing unlock_critical`) with safety confirmations and screen prompt instructions. | `fastboot flashing unlock` / `fastboot oem unlock` |
| **11** | **OEM Bootloader Lock** | Relocks the bootloader (`flashing lock` / `oem lock`) with critical stock-firmware verification warnings to prevent bricking. | `fastboot flashing lock` / `fastboot oem lock` |
| **12** | **Boot Image (RAM Boot)** | Boots a kernel/recovery image directly from RAM without modifying or flashing device storage partitions (`fastboot boot`). | `fastboot boot <image.img>` |
| **13** | **Switch Active Slot (A/B)** | Inspects current active slot and switches target partition slot between Slot A, Slot B, or Other on seamless update devices. | `fastboot --set-active=a|b|other` |
| **14** | **Reboot ADB to Fastboot** | Reboots an active ADB device into Bootloader, Fastbootd, or Recovery mode. | `adb reboot bootloader` / `adb reboot fastboot` / `adb reboot recovery` |

---

## 🖥️ Module 14: System Internals & Low-Level Diagnostics

**Module:** `modules/system_info.py`  
**Overview:** Linux kernel forensics, SELinux enforcement inspection, block device partitions, filesystem mount points, init daemons, shared libraries, multi-user profiles, input hardware, and boot milestone latencies.

```
🖥️ System Internals & Diagnostics
├── Kernel Version & Architecture
├── SELinux Enforcement Status
├── Partition Layout (/proc/partitions)
├── Mount Points & Filesystems
├── Running System Services (service list)
├── System Features (pm list features)
├── Init Daemons & Boot Properties
├── System Uptime & Processor Load
├── Available Shared Libraries (pm list libraries)
├── List User Profiles & Accounts
├── List Input Hardware Devices
├── Boot Completed Status & Timing
├── CPU Topology & Memory Architecture
└── Export Full System Diagnostics Report
```

### Features Table

| # | Feature Name | Description | ADB / System Command Used |
| :-: | :--- | :--- | :--- |
| **1** | **Kernel Version & Architecture** | Displays Linux kernel version, GCC/Clang compiler build string, kernel release, CPU ABI, and SoC platform. | `adb shell cat /proc/version`, `uname -a`, `cat /proc/sys/kernel/osrelease` |
| **2** | **SELinux Enforcement Status** | Inspects runtime enforcement mode (`getenforce`), kernel enforcement sysfs node (`/sys/fs/selinux/enforce`), boot parameters, and security implications. | `adb shell getenforce`, `cat /sys/fs/selinux/enforce`, `getprop ro.boot.selinux` |
| **3** | **Partition Layout** | Parses `/proc/partitions` to display block devices, major/minor numbers, block capacities, and filesystem usage (`df -h`). | `adb shell cat /proc/partitions`, `df -h` |
| **4** | **Mount Points & Filesystems** | Inspects active storage and system partition mounts (`ext4`, `f2fs`, `erofs`, `fuse`) and virtual kernel mounts (`sysfs`, `proc`). | `adb shell mount`, `cat /proc/mounts` |
| **5** | **Running System Services** | Enumerates all active Binder system services registered in `ServiceManager` with interface descriptors and keyword filtering. | `adb shell service list` |
| **6** | **System Features Manifest** | Catalogs device hardware, software, and Vulkan/OpenGL capabilities reported by PackageManager. | `adb shell pm list features` |
| **7** | **Init Daemons & Boot Properties** | Audits all `init.svc.*` system daemons (running vs stopped), boot flags (`ro.boot.*`), and encryption flags. | `adb shell getprop init.svc.*`, `ro.boot.*`, `ro.crypto.*` |
| **8** | **System Uptime & Load Averages** | Displays uptime, CPU idle time, and 1-minute, 5-minute, and 15-minute load averages from `/proc/loadavg`. | `adb shell uptime`, `cat /proc/uptime`, `cat /proc/loadavg` |
| **9** | **Available Shared Libraries** | Lists all Java and native runtime shared libraries categorized by provider (Android Core, Google Play / GMS, OEM). | `adb shell pm list libraries` |
| **10** | **User Profiles & Accounts** | Inspects multi-user accounts, work profiles, user IDs, profile flags, and device sync account registrations. | `adb shell pm list users`, `dumpsys user`, `dumpsys account` |
| **11** | **Input Hardware Devices** | Lists touchscreen controllers, physical buttons, keypads, and event handlers (`/dev/input/event*`). | `adb shell cat /proc/bus/input/devices`, `getevent -S` |
| **12** | **Boot Completed Status & Timing** | Verifies `sys.boot_completed` state, first boot timestamp, and breaks down individual subsystem initialization latencies (`ro.boottime.*`). | `adb shell getprop sys.boot_completed`, `dev.bootcomplete`, `ro.runtime.firstboot`, `ro.boottime.*` |
| **13** | **CPU & Memory Architecture** | Summarizes CPU core counts, platform codenames, and primary memory allocations from `/proc/meminfo`. | `adb shell cat /proc/cpuinfo`, `/proc/meminfo` |
| **14** | **Export Full System Report** | Executes all 10 diagnostic audits and compiles a full technical forensics report into a timestamped `.txt` file. | Aggregated diagnostic pipeline |

---

## 🔒 Module 15: Security Audit & Vulnerability Assessment

**Module:** `modules/security_audit.py`  
**Overview:** Automated 100-point security audit and vulnerability assessment engine evaluating encryption, lockscreen credentials, SELinux, root binaries, developer exposure, patch currency, and app permissions.

```
🔒 Security Audit & Vulnerability Assessment
├── Check Storage Encryption Status
├── Check Screen Lock & Credential Type
├── Check USB Debugging Status
├── Check Unknown Sources / Sideloading Policy
├── Check Developer Options Status
├── Check Google Play Protect Verification
├── Check SELinux Mode & Policy
├── Check ADB Over Network (Port 5555)
├── List Apps with Dangerous Permissions
├── List Device Administrators & Owners
├── Check Security Patch Level & Currency
├── Check Root & Superuser Integrity
└── Generate Full Security Audit Report (Scorecard)
```

### Features Table

| # | Feature Name | Description | ADB / System Command Used |
| :-: | :--- | :--- | :--- |
| **1** | **Storage Encryption Audit** | Checks whether storage is encrypted (FBE / FDE) and identifies encryption algorithms (AES-256-XTS). | `adb shell getprop ro.crypto.state`, `ro.crypto.type`, `ro.crypto.fde_algorithm` |
| **2** | **Screen Lock & Credentials** | Audits keyguard security (PIN, Alphanumeric Password, Pattern, Biometrics, or Insecure Swipe/None). | `adb shell settings get secure lockscreen.disabled`, `dumpsys trust`, `dumpsys lock_settings` |
| **3** | **USB Debugging Exposure** | Checks if USB debugging is enabled and checks if the ROM is built as a production user release or debuggable build. | `adb shell settings get global adb_enabled`, `getprop ro.debuggable` |
| **4** | **Sideloading Policy** | Evaluates non-market app installation settings (Global legacy bypass vs Android 8+ granular app permissions). | `adb shell settings get secure/global install_non_market_apps` |
| **5** | **Developer Options State** | Audits whether Development Settings are enabled, exposing mock locations and bug reports. | `adb shell settings get global development_settings_enabled` |
| **6** | **Google Play Protect Status** | Checks if package verification and unknown APK cloud scanning are active. | `adb shell settings get global package_verifier_enable`, `upload_apk_enable` |
| **7** | **SELinux Security Posture** | Verifies Mandatory Access Control enforcement (`Enforcing` vs `Permissive` vs `Disabled`). | `adb shell getenforce`, `getprop ro.boot.selinux` |
| **8** | **Network ADB Exposure** | Scans for open TCP listening ports (Port 5555 / Wireless Debugging) that could allow unauthenticated network control. | `adb shell getprop service.adb.tcp.port`, `settings get global adb_wifi_enabled`, `netstat -tuln` |
| **9** | **Sensitive App Permissions** | Audits 3rd-party apps holding critical permissions: Camera, Microphone, Fine Location, SMS, Call Logs, Contacts, Storage, and System Alert Window. | `adb shell pm list packages -3` -> `dumpsys package <pkg>` |
| **10** | **Device Administrators Audit** | Detects active Device Administrators and Device Policy Owners capable of remote locking or wiping data. | `adb shell dpm list-owners`, `dumpsys device_policy` |
| **11** | **Security Patch Currency** | Compares `ro.build.version.security_patch` date against current calendar date, calculating patch age and CVE vulnerability risk. | `adb shell getprop ro.build.version.security_patch`, `ro.build.version.release` |
| **12** | **Root & Superuser Detection** | Detects `su` binaries, Magisk daemons, KernelSU, test-keys build tags, and insecure kernel flags (`ro.secure=0`). | `which su`, `magisk -v`, file checks on `/system/xbin/su`, `getprop ro.build.tags`, `ro.secure` |
| **13** | **Full Audit Scorecard Engine** | Executes all 12 security audits, computes a normalized 100-point security score, assigns a letter grade (A+ through F), and generates actionable remediation recommendations with file export. | Multi-tier security assessment algorithm |

---

## 🤖 Module 16: Automation & Scripting Studio

**Module:** `modules/automation.py`  
**Overview:** Interactive macro recorder, macro replay engine with loops, batch script runner, persistent execution history, favorite command bookmarks, custom ADB/shell execution, remote script execution, and scheduled repeat command loops.

```
🤖 Automation & Scripting Studio
├── Record New Macro (Interactive Step Wizard)
├── Replay Macro from File
├── Run Batch Commands from Text File (.txt/.adb)
├── View & Rerun Command History
├── Manage Favorite Commands & Presets
├── List & Inspect Saved Macros
├── Run Custom ADB Command
├── Run Custom Shell Command
├── Execute Shell Script File (.sh) on Device
└── Scheduled Repeat Command (N times / Interval)
```

### Features Table

| # | Feature Name | Description | Execution / Technical Implementation |
| :-: | :--- | :--- | :--- |
| **1** | **Interactive Macro Recorder** | Wizard to record shell commands, ADB commands, coordinate taps, swipes, key events, text input, sleep pauses, and screenshots into reusable JSON macros. | Interactive step builder -> `scripts/<name>.json` |
| **2** | **Replay Saved Macro** | Replays macro files with configurable loop iterations (1 to N), speed multiplier (0.5x to 2.0x), stop-on-error safety flag, and live progress bars. | JSON step parser & execution engine |
| **3** | **Run Batch Commands** | Sequentially executes lines of ADB and shell commands from a local text file (`.txt`, `.adb`, `.sh`), ignoring comments (`#`), with timing reports. | Batch file parser & execution pipeline |
| **4** | **Command Execution History** | Persistent JSON log tracking the last 100 executed commands with timestamps, execution durations (ms), success status, and rerun capabilities. | `scripts/command_history.json` manager |
| **5** | **Favorite Commands & Presets** | Save, categorize, view, execute, or delete favorite preset commands (e.g. Screenshot, Clear logcat, Restart UI, Dump battery). | `scripts/favorites.json` bookmark engine |
| **6** | **List & Inspect Saved Macros** | Lists all recorded macro JSON files, displays step breakdowns, and provides macro deletion tools. | File scanner & step table renderer |
| **7** | **Run Custom ADB Command** | Interactive command-line prompt to execute arbitrary ADB commands with duration metrics and one-click bookmarking to Favorites. | `adb <args>` wrapper |
| **8** | **Run Custom Shell Command** | Interactive prompt to execute arbitrary shell commands with an optional `su -c` root escalation flag. | `adb shell <cmd>` / `adb shell su -c '<cmd>'` |
| **9** | **Execute `.sh` Script on Device** | Uploads local `.sh` scripts to device staging area (`/data/local/tmp/`), sets executable permissions (`chmod 755`), executes with standard or root shell, and cleans up. | `adb push` -> `chmod 755` -> `sh` / `su -c` -> `rm` |
| **10** | **Scheduled Repeat Command** | Loops any selected ADB or shell command repeatedly N times (or continuously until `Ctrl+C`) with precision interval delays (seconds) and optional log file recording. | Precision timer loop with keyboard interrupt handler |

---

## ⌨️ Quick Reference Card & Keycode Index

### Android Keycode Reference Table

| Key Name | Key Code | Identifier | Description / Common Usage |
| :--- | :---: | :--- | :--- |
| **Home** | `3` | `KEYCODE_HOME` | Returns to the home launcher screen |
| **Back** | `4` | `KEYCODE_BACK` | Back navigation / dismisses dialogs and keyboard |
| **Recent Apps** | `187` | `KEYCODE_APP_SWITCH` | Opens multitasking overview / recent tasks |
| **Menu** | `82` | `KEYCODE_MENU` | Opens legacy options menu |
| **Search** | `84` | `KEYCODE_SEARCH` | Launches global device search |
| **Power** | `26` | `KEYCODE_POWER` | Toggles screen power on or off |
| **Wakeup** | `224` | `KEYCODE_WAKEUP` | Forces display screen to wake up |
| **Sleep** | `223` | `KEYCODE_SLEEP` | Puts display screen to sleep |
| **Lock Screen** | `276` | `KEYCODE_SETTINGS` | Opens system settings or locks keyguard |
| **Voice Assistant** | `231` | `KEYCODE_VOICE_ASSIST` | Triggers Google Assistant / voice prompt |
| **Camera** | `27` | `KEYCODE_CAMERA` | Launches camera app or triggers shutter |
| **Volume Up** | `24` | `KEYCODE_VOLUME_UP` | Increases audio volume by 1 step |
| **Volume Down** | `25` | `KEYCODE_VOLUME_DOWN` | Decreases audio volume by 1 step |
| **Volume Mute** | `164` | `KEYCODE_VOLUME_MUTE` | Mutes or unmutes device audio streams |
| **Play / Pause** | `85` | `KEYCODE_MEDIA_PLAY_PAUSE` | Toggles media playback state |
| **Media Play** | `126` | `KEYCODE_MEDIA_PLAY` | Starts media playback |
| **Media Pause** | `127` | `KEYCODE_MEDIA_PAUSE` | Pauses active media playback |
| **Next Track** | `87` | `KEYCODE_MEDIA_NEXT` | Skips to next audio / video track |
| **Previous Track** | `88` | `KEYCODE_MEDIA_PREVIOUS` | Skips to previous track |
| **Stop Media** | `86` | `KEYCODE_MEDIA_STOP` | Stops media playback |
| **Fast Forward** | `90` | `KEYCODE_MEDIA_FAST_FORWARD`| Fast forwards active media |
| **Rewind** | `89` | `KEYCODE_MEDIA_REWIND` | Rewinds active media track |
| **D-Pad Up** | `19` | `KEYCODE_DPAD_UP` | Directional navigation Up |
| **D-Pad Down** | `20` | `KEYCODE_DPAD_DOWN` | Directional navigation Down |
| **D-Pad Left** | `21` | `KEYCODE_DPAD_LEFT` | Directional navigation Left |
| **D-Pad Right** | `22` | `KEYCODE_DPAD_RIGHT` | Directional navigation Right |
| **D-Pad Center** | `23` | `KEYCODE_DPAD_CENTER` | Directional Confirm / OK button |
| **Enter** | `66` | `KEYCODE_ENTER` | Enter / Return key on keyboard |
| **Backspace** | `67` | `KEYCODE_DEL` | Deletes character to the left of cursor |
| **Delete (Forward)** | `112` | `KEYCODE_FORWARD_DEL` | Deletes character to the right of cursor |
| **Tab** | `61` | `KEYCODE_TAB` | Tab navigation key |
| **Space** | `62` | `KEYCODE_SPACE` | Space bar character |
| **Escape** | `111` | `KEYCODE_ESCAPE` | Escape key |
| **Cut** | `277` | `KEYCODE_CUT` | Cuts selected text |
| **Copy** | `278` | `KEYCODE_COPY` | Copies selected text to clipboard |
| **Paste** | `279` | `KEYCODE_PASTE` | Pastes text from clipboard |
| **Print Screen** | `120` | `KEYCODE_SYSRQ` | Triggers hardware screenshot |
| **Brightness Down** | `220` | `KEYCODE_BRIGHTNESS_DOWN` | Decreases display brightness |
| **Brightness Up** | `221` | `KEYCODE_BRIGHTNESS_UP` | Increases display brightness |
| **Notification Shade** | `83` | `KEYCODE_NOTIFICATION` | Opens notifications panel |

---

### Common ADB CLI Command Reference

| Action | ADB Command |
| :--- | :--- |
| **List Devices** | `adb devices -l` |
| **Enable Wireless ADB** | `adb tcpip 5555` |
| **Connect Over Wi-Fi** | `adb connect <device_ip>:5555` |
| **Disconnect Wireless** | `adb disconnect [<device_ip>:5555]` |
| **Interactive Shell** | `adb shell` |
| **Install APK (Replace)** | `adb install -r -g <app.apk>` |
| **Uninstall App** | `adb uninstall <package_name>` |
| **Extract APK Path** | `adb shell pm path <package_name>` |
| **Pull File from Device** | `adb pull <remote_path> <local_path>` |
| **Push File to Device** | `adb push <local_path> <remote_path>` |
| **Capture Screenshot** | `adb shell screencap -p /sdcard/screen.png && adb pull /sdcard/screen.png` |
| **Record Screen** | `adb shell screenrecord --time-limit 30 /sdcard/demo.mp4 && adb pull /sdcard/demo.mp4` |
| **Filter Logcat** | `adb logcat -v threadtime *:<V|D|I|W|E|F>` |
| **Clear App Data** | `adb shell pm clear <package_name>` |
| **Force Stop App** | `adb shell am force-stop <package_name>` |
| **Launch App** | `adb shell monkey -p <package_name> -c android.intent.category.LAUNCHER 1` |
| **Simulate Tap** | `adb shell input tap <X> <Y>` |
| **Simulate Swipe** | `adb shell input swipe <X1> <Y1> <X2> <Y2> <duration_ms>` |
| **Type Text** | `adb shell input text <escaped_string>` |
| **Reboot to Bootloader** | `adb reboot bootloader` |
| **Reboot to Recovery** | `adb reboot recovery` |
| **Fastboot Flash Boot** | `fastboot flash boot boot.img` |
| **Fastboot Flash Recovery** | `fastboot flash recovery recovery.img` |
| **Fastboot Boot in RAM** | `fastboot boot recovery.img` |
| **Fastboot Variables** | `fastboot getvar all` |

---

*PhoneSurgeon — Advanced ADB & Fastboot Toolkit for Android.*
