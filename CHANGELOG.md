# Changelog

All notable changes to the **PhoneSurgeon** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] - 2026-08-20

### 💥 Major Architectural Rewrite
- Complete architectural redesign and rebrand from **PhoneSurgeon — Advanced ADB Toolkit**.
- Migrated from a monolithic single-file script to a modular, extensible architecture with a clean `core/` runtime and 16 standalone domain modules in `modules/`.
- Codebase expanded from ~1,200 lines to **16,100+ lines of pure Python** with **200+ ADB and Fastboot commands**.
- Zero external third-party dependencies (`requirements.txt` is empty; 100% Python standard library).

### 🚀 Added

#### 🧙 Auto-Setup Wizard & Dependency Management (`core/setup_wizard.py`)
- **Automated ADB Download**: Automatically detects missing platform tools and downloads official Google Android SDK Platform Tools for Windows, macOS, and Linux.
- **Self-Extracting & Path Management**: Unpacks binaries into `~/.phonesurgeon/platform-tools/` and injects them dynamically into the runtime `PATH`.
- **Fastboot Verification**: Detects and verifies Fastboot availability for bootloader operations.
- **Python Version Gate**: Ensures minimum Python 3.8+ runtime environment.
- **Driver Diagnostics**: Probes Windows USB driver status and provides direct vendor download guidance.
- **Fast-Path Startup**: Caches configuration in `~/.phonesurgeon/config.json` for near-instant returning user launches.

#### 🔌 Multi-Device Management (`core/device.py` & `core/adb.py`)
- **Device Enumeration**: Real-time detection and listing of all connected USB and wireless ADB devices.
- **Active Device Targeting**: Transparent injection of `-s <serial>` across all 200+ commands.
- **Interactive Device Switcher**: Dual-column device picker table with auto-selection when only one device is connected.
- **TCP/IP Wireless ADB**: 1-click Wi-Fi debugging daemon activation (`adb tcpip 5555`) with connection manager.

#### 🎨 Modern Terminal UI Engine (`core/ui.py`)
- Standardized ANSI color palettes, box-drawing characters, and formatted banners.
- Two-column responsive menu layouts for large option lists.
- Dynamic ASCII data tables, aligned key-value property formatters, and real-time progress bars.

#### 📦 16 Specialized Subsystem Modules (`modules/`)

| # | Module | File | Lines | Feature Count | Capabilities & Description |
|---|---|---|---|:---:|---|
| 1 | **📱 Device Info** | [`modules/device_info.py`](file:///c:/Users/SRI/Documents/antigravity/zealous-hopper/modules/device_info.py) | 1,122 | 13 Features | Deep hardware profiling, SoC/CPU architecture, battery health, display DPI/refresh rates, telephony/SIM, sensors, thermal zones, storage layout, build properties, and full diagnostic report export. |
| 2 | **📦 App Manager** | [`modules/app_manager.py`](file:///c:/Users/SRI/Documents/antigravity/zealous-hopper/modules/app_manager.py) | 916 | 16 Features | Single & batch APK sideloading (`-r`, `-d`, `-g`), uninstaller with data retention (`-k`), third-party/system app filtering, instant keyword search, force-stop, app data wipe (`pm clear`), runtime permission viewer, APK extraction to PC, and app freeze/unfreeze (`pm disable-user`). |
| 3 | **📁 File Manager** | [`modules/file_manager.py`](file:///c:/Users/SRI/Documents/antigravity/zealous-hopper/modules/file_manager.py) | 978 | 15 Features | Bidirectional file and recursive folder push/pull, remote directory browser (`ls -la`), pattern search (`find`), disk usage (`df`/`du`), remote file viewer (`cat`/`head`/`tail`), POSIX permission editor (`chmod`), and MD5/SHA256 checksum verification. |
| 4 | **📸 Screen Capture** | [`modules/screen_capture.py`](file:///c:/Users/SRI/Documents/antigravity/zealous-hopper/modules/screen_capture.py) | 685 | 11 Features | Instant timestamped PNG screenshots, burst series capture, screen video recording (up to 180s), custom video bitrates (2–20 Mbps), custom video resolutions, multi-display ID support, touch visualization overlay (`--show-touches`), and auto-pull to local PC. |
| 5 | **📋 Logcat Viewer** | [`modules/logcat.py`](file:///c:/Users/SRI/Documents/antigravity/zealous-hopper/modules/logcat.py) | 891 | 13 Features | Real-time colorized log stream, priority filtering (`V`/`D`/`I`/`W`/`E`/`F`), tag filtering, PID/Package targeting, regex search, automated crash extractor (`FATAL EXCEPTION`), ANR trace viewer (`/data/anr/`), buffer size manager, kernel logs (`dmesg`), and event buffer logs. |
| 6 | **💾 Backup & Restore** | [`modules/backup_restore.py`](file:///c:/Users/SRI/Documents/antigravity/zealous-hopper/modules/backup_restore.py) | 889 | 11 Features | Full system `.ab` backup, single app backup with/without APK binaries, shared storage dump, `.ab` archive restoration, contacts vCard (`.vcf`) & CSV export via content providers, SMS and call log extraction, and package manifest exporter. |
| 7 | **🔧 Device Controls** | [`modules/device_controls.py`](file:///c:/Users/SRI/Documents/antigravity/zealous-hopper/modules/device_controls.py) | 936 | 16 Features | System reboot (Normal, Recovery, Bootloader, Soft Restart), interactive ADB shell, remote text typing, keycode injection, screen wake/sleep, brightness slider, screen timeout settings, airplane mode toggle, rotation controls, and stay awake toggle. |
| 8 | **📊 Performance Monitor** | [`modules/performance.py`](file:///c:/Users/SRI/Documents/antigravity/zealous-hopper/modules/performance.py) | 899 | 12 Features | Live CPU core frequency tracking, RAM & zRAM memory breakdown (`/proc/meminfo`), detailed battery subsystem discharge, GPU OpenGL/Vulkan capabilities, top 25 process monitor, app PSS/Private-Dirty memory profiler (`dumpsys meminfo`), disk I/O, and frame rendering stats (`dumpsys gfxinfo`). |
| 9 | **🌐 Network Tools** | [`modules/network_tools.py`](file:///c:/Users/SRI/Documents/antigravity/zealous-hopper/modules/network_tools.py) | 1,312 | 14 Features | Wi-Fi signal & BSSID metrics, IP/subnet configuration, mobile data RAT state, remote ICMP ping, DNS & Private DNS inspector, kernel routing table, open port scanner (`netstat`), real-time bandwidth throughput meter, HTTP/HTTPS connectivity validator, and automated network health scorecard. |
| 10 | **👆 Input Simulation** | [`modules/input_simulation.py`](file:///c:/Users/SRI/Documents/antigravity/zealous-hopper/modules/input_simulation.py) | 939 | 13 Features | Screen pixel tap `(X, Y)`, long press with duration, custom vector swipe, swipe gesture presets (scroll, fling, edge swipe), direct text typing, hardware key event injection, keyboard shortcuts (`Ctrl+C`, `Alt+Tab`), status bar & quick settings toggles, volume step control, and media playback control. |
| 11 | **🔍 UI Inspector** | [`modules/ui_inspector.py`](file:///c:/Users/SRI/Documents/antigravity/zealous-hopper/modules/ui_inspector.py) | 1,211 | 12 Features | Full UI XML hierarchy dump (`uiautomator dump`), top-most foreground Activity detector, Fragment backstack inspector, recent task stack history, focused window metrics, active system overlays & dialogs, ContentProvider enumerator, background service viewer, and display cutout/notch analyzer. |
| 12 | **⚙️ Developer Options** | [`modules/developer_options.py`](file:///c:/Users/SRI/Documents/antigravity/zealous-hopper/modules/developer_options.py) | 675 | 16 Features | Toggle layout bounds, GPU overdraw color overlay, window/transition/animator scale adjustments, show touches overlay, pointer location tracker, StrictMode UI flash, background process limit, Chromium WebView debugging, HWUI profiling, 4x MSAA, animation speed presets, and SystemUI Demo Mode for pristine store screenshots. |
| 13 | **⚡ Fastboot Tools** | [`modules/fastboot_tools.py`](file:///c:/Users/SRI/Documents/antigravity/zealous-hopper/modules/fastboot_tools.py) | 820 | 14 Features | Fastboot device detection, bootloader variable dump (`getvar all`), boot image flashing (`boot.img`), recovery flashing (`recovery.img`), system flashing (`system.img`), custom partition flashing, partition erase/wipe, OEM unlock/lock triggers, direct boot without flashing (`fastboot boot`), A/B slot switcher, and ADB-to-Bootloader rebooter. |
| 14 | **🖥️ System Info** | [`modules/system_info.py`](file:///c:/Users/SRI/Documents/antigravity/zealous-hopper/modules/system_info.py) | 790 | 14 Features | Kernel version & architecture details, SELinux enforcement mode, partition block layout (`/proc/partitions`), filesystem mount table, IBinder system services (`service list`), PackageManager feature flags, init daemons, system load averages, shared library list, user accounts, and input hardware devices. |
| 15 | **🔒 Security Audit** | [`modules/security_audit.py`](file:///c:/Users/SRI/Documents/antigravity/zealous-hopper/modules/security_audit.py) | 753 | 13 Features | Storage encryption verification (FBE/FDE), lockscreen credential strength, USB debugging audit, unknown sources sideloading policy, Google Play Protect verification, SELinux security mode, wireless ADB port exposure, dangerous permissions auditor, device admin scanner, security patch currency, root/superuser probe (`su`, Magisk, KernelSU), and automated security scorecard grade (A+ to F). |
| 16 | **🤖 Automation** | [`modules/automation.py`](file:///c:/Users/SRI/Documents/antigravity/zealous-hopper/modules/automation.py) | 1,025 | 10 Features | Interactive step-by-step macro recorder, JSON macro playback engine with loop repetitions, batch command runner (`.txt`/`.adb`), interactive command history, favorite command bookmarks, custom ADB/Shell command runners, on-device `.sh` script execution, and scheduled repeat runners. |

---

## [1.0.0] - 2026-08-19

### 🚀 Initial Release (as DroidCommander)
- Initial public release as **DroidCommander**, a single-file interactive ADB utility.
- Included 8 foundational ADB modules:
  - 📱 Basic Device Information (`getprop` dump)
  - 📦 Simple Package Manager (install, uninstall, list packages)
  - 📁 Basic File Push/Pull
  - 📸 Simple Screenshot Capture
  - 📋 Raw Logcat Stream
  - 💾 Standard `adb backup` Command Trigger
  - 🔧 Basic Reboot Controls (Reboot, Recovery, Bootloader)
  - 👆 Basic Keycode Injection
- Monolithic architecture contained within a single Python script (~1,200 lines).
- Required manual installation and PATH configuration of Android SDK Platform Tools.
- Single-device support only.
