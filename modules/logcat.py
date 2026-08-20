"""
modules/logcat.py — Android Logcat Viewer and Diagnostics Module.

Provides comprehensive log viewing, priority and tag filtering, PID isolation,
regex search, crash/ANR log extraction, buffer management, kernel dmesg,
and event logs analysis for DroidCommander.
"""

from datetime import datetime
import os
import re
import subprocess
import time
from typing import Dict, List, Optional, Tuple

from core.adb import adb
from core import ui
from core.device import ensure_device


# ─── Log Formatting & Color Helpers ──────────────────────────────────────────

def colorize_log_line(line: str) -> str:
    """
    Apply ANSI color codes to a logcat line based on its log level / priority.

    Recognizes standard threadtime format:
        MM-DD HH:MM:SS.ms  PID  TID Priority Tag: Message
    as well as brief, process, and raw log formats.

    Parameters
    ----------
    line : str
        Single logcat output line.

    Returns
    -------
    str
        ANSI-colored line string.
    """
    if not line:
        return line

    # Check for Fatal / Crash markers
    if (
        "FATAL EXCEPTION" in line
        or " F " in line
        or line.startswith("F/")
        or "CRASH:" in line
        or "SIGSEGV" in line
        or "SIGABRT" in line
        or "backtrace:" in line
    ):
        return f"{ui.Colors.BOLD}{ui.Colors.RED}{line}{ui.Colors.RESET}"

    # Check for Error markers
    if (
        " E " in line
        or " E/" in line
        or line.startswith("E/")
        or "System.err:" in line
        or "AndroidRuntime:" in line
        or "Error:" in line
        or "Exception:" in line
    ):
        return f"{ui.Colors.RED}{line}{ui.Colors.RESET}"

    # Check for Warning markers
    if (
        " W " in line
        or " W/" in line
        or line.startswith("W/")
        or "Warning:" in line
        or "WARN:" in line
    ):
        return f"{ui.Colors.YELLOW}{line}{ui.Colors.RESET}"

    # Check for Info markers
    if (
        " I " in line
        or " I/" in line
        or line.startswith("I/")
        or "INFO:" in line
    ):
        return f"{ui.Colors.GREEN}{line}{ui.Colors.RESET}"

    # Check for Debug markers
    if (
        " D " in line
        or " D/" in line
        or line.startswith("D/")
        or "DEBUG:" in line
    ):
        return f"{ui.Colors.CYAN}{line}{ui.Colors.RESET}"

    # Check for Verbose markers
    if (
        " V " in line
        or " V/" in line
        or line.startswith("V/")
    ):
        return f"{ui.Colors.DIM}{line}{ui.Colors.RESET}"

    return line


def display_log_lines(
    lines: List[str],
    title: str,
    highlight_query: str = "",
    max_display: int = 200,
) -> None:
    """
    Display a list of logcat lines with count headers and coloring.

    Parameters
    ----------
    lines : list[str]
        List of log lines.
    title : str
        Header title to describe the displayed logs.
    highlight_query : str
        Optional search term to highlight within each line.
    max_display : int
        Maximum number of lines to display to avoid terminal flooding.
    """
    if not lines:
        ui.info("No matching log entries found.")
        return

    total = len(lines)
    ui.header(f"{title} ({total} entries):")
    print()

    displayed_lines = lines[-max_display:] if total > max_display else lines

    if total > max_display:
        ui.info(f"Showing last {max_display} of {total} entries (newest at bottom).")
        print()

    for line in displayed_lines:
        colored = colorize_log_line(line)
        if highlight_query:
            # Highlight query matches in background blue/white text
            pattern = re.compile(re.escape(highlight_query), re.IGNORECASE)
            colored = pattern.sub(
                f"{ui.Colors.BOLD}{ui.Colors.BG_BLUE}{ui.Colors.WHITE}\\g<0>{ui.Colors.RESET}",
                colored,
            )
        print(f"  {colored}")

    print()
    if total > max_display:
        ui.info(f"Note: {total - max_display} earlier lines omitted from screen display.")


def get_logcat_output(args: List[str], timeout: int = 20) -> Tuple[bool, List[str]]:
    """
    Execute an ADB logcat command and return split lines.

    Parameters
    ----------
    args : list[str]
        Arguments passed to `adb logcat`.
    timeout : int
        Command timeout in seconds.

    Returns
    -------
    tuple[bool, list[str]]
        (Success flag, list of non-empty log lines).
    """
    cmd = ["logcat"] + args
    ok, output = adb.run(cmd, timeout=timeout)
    if not ok:
        return False, [output] if output else ["Failed to retrieve logcat."]
    lines = [ln for ln in output.splitlines() if ln.strip()]
    return True, lines


# ─── Feature 1: View Recent Logs ──────────────────────────────────────────────

def view_recent_logs() -> None:
    """View the last N lines of logcat in threadtime format."""
    if not ensure_device():
        return

    print(f"\n  {ui.Colors.CYAN}Common counts: 50, 100, 200, 500 (Press Enter for 100){ui.Colors.RESET}")
    count_input = ui.get_choice("Enter line count")
    count = 100
    if count_input:
        try:
            count = max(1, min(int(count_input), 5000))
        except ValueError:
            ui.warning("Invalid count entered. Defaulting to 100 lines.")
            count = 100

    ui.info(f"Fetching last {count} logcat lines from device...")
    ok, lines = get_logcat_output(["-d", "-t", str(count), "-v", "threadtime"], timeout=20)

    if ok:
        display_log_lines(lines, f"Recent Logcat (Last {len(lines)} lines)")
    else:
        ui.error(f"Failed to fetch logs: {' '.join(lines)}")


# ─── Feature 2: View Logs by Priority ────────────────────────────────────────

def view_logs_by_priority() -> None:
    """View logs filtered by minimum priority level."""
    if not ensure_device():
        return

    print(f"""
  {ui.Colors.BOLD}Available Priority Levels:{ui.Colors.RESET}
    {ui.Colors.DIM}[V]{ui.Colors.RESET} Verbose  (Lowest priority - show all)
    {ui.Colors.CYAN}[D]{ui.Colors.RESET} Debug    (Debug messages)
    {ui.Colors.GREEN}[I]{ui.Colors.RESET} Info     (Informational messages)
    {ui.Colors.YELLOW}[W]{ui.Colors.RESET} Warning  (Potential issues)
    {ui.Colors.RED}[E]{ui.Colors.RESET} Error    (Errors & exceptions)
    {ui.Colors.BOLD}{ui.Colors.RED}[F]{ui.Colors.RESET} Fatal    (Fatal crashes only)
    """)

    prio = ui.get_choice("Enter priority letter [V/D/I/W/E/F]").upper()
    if not prio or prio not in ("V", "D", "I", "W", "E", "F"):
        ui.error("Invalid priority level selected.")
        return

    count_input = ui.get_choice("Enter line count (default 100)")
    count = 100
    if count_input:
        try:
            count = max(1, min(int(count_input), 5000))
        except ValueError:
            count = 100

    prio_names = {
        "V": "Verbose", "D": "Debug", "I": "Info",
        "W": "Warning", "E": "Error", "F": "Fatal",
    }
    ui.info(f"Filtering logs with priority >= {prio_names[prio]} (last {count} lines)...")

    ok, lines = get_logcat_output(["-d", f"*:{prio}", "-t", str(count), "-v", "threadtime"], timeout=20)
    if ok:
        display_log_lines(lines, f"Logs with Priority >= {prio_names[prio]}")
    else:
        ui.error(f"Failed to filter logs: {' '.join(lines)}")


# ─── Feature 3: Filter Logs by Tag ───────────────────────────────────────────

def filter_logs_by_tag() -> None:
    """Filter logs by a specific component or application tag."""
    if not ensure_device():
        return

    print(f"""
  {ui.Colors.CYAN}Common Tags:{ui.Colors.RESET}
    ActivityManager  |  AndroidRuntime  |  WindowManager  |  PackageManager
    AudioFlinger     |  Bluetooth       |  CameraHandler   |  InputDispatcher
    System.err       |  flutter         |  Unity           |  OkHttp
    """)

    tag = ui.get_choice("Enter log tag to filter")
    if not tag:
        ui.error("Tag name cannot be empty.")
        return

    prio = ui.get_choice("Enter min priority for tag (V/D/I/W/E/F, default V)").upper()
    if not prio or prio not in ("V", "D", "I", "W", "E", "F"):
        prio = "V"

    count_input = ui.get_choice("Enter line count (default 100)")
    count = 100
    if count_input:
        try:
            count = max(1, min(int(count_input), 5000))
        except ValueError:
            count = 100

    ui.info(f"Fetching logs for tag '{tag}' (priority >= {prio})...")
    ok, lines = get_logcat_output(["-d", "-s", f"{tag}:{prio}", "-t", str(count), "-v", "threadtime"], timeout=20)

    if ok:
        display_log_lines(lines, f"Logs for Tag '{tag}' ({prio}+)")
    else:
        ui.error(f"Failed to fetch logs for tag: {' '.join(lines)}")


# ─── Feature 4: Filter Logs by PID ───────────────────────────────────────────

def filter_logs_by_pid() -> None:
    """Filter logs generated by a specific process ID or package name."""
    if not ensure_device():
        return

    print(f"\n  {ui.Colors.CYAN}Enter a numeric Process ID (PID) OR an app package name:{ui.Colors.RESET}")
    user_input = ui.get_choice("Enter PID or package name (e.g. com.android.settings)")
    if not user_input:
        ui.error("Input cannot be empty.")
        return

    pid: Optional[int] = None
    package_name: str = ""

    if user_input.isdigit():
        pid = int(user_input)
    else:
        package_name = user_input
        ui.info(f"Looking up PID for package '{package_name}'...")
        ok, pid_out = adb.run_shell(f"pidof {package_name}")
        if ok and pid_out.strip():
            pids = pid_out.strip().split()
            try:
                pid = int(pids[0])
                ui.success(f"Found active process PID: {pid}")
            except ValueError:
                pid = None
        else:
            # Fallback search via ps -A
            ok_ps, ps_out = adb.run_shell(f"ps -A | grep -i {package_name}")
            if ok_ps and ps_out.strip():
                for line in ps_out.splitlines():
                    parts = line.split()
                    if len(parts) >= 2 and parts[1].isdigit():
                        pid = int(parts[1])
                        ui.success(f"Found PID from process list: {pid} ({parts[-1]})")
                        break

    if pid is None:
        ui.error(f"Could not find a running PID for '{user_input}'. Is the app running?")
        return

    count_input = ui.get_choice("Enter line count (default 150)")
    count = 150
    if count_input:
        try:
            count = max(1, min(int(count_input), 5000))
        except ValueError:
            count = 150

    ui.info(f"Fetching logs for PID {pid} (last {count} lines)...")

    # Try modern --pid flag first
    ok, lines = get_logcat_output(["-d", "--pid", str(pid), "-t", str(count), "-v", "threadtime"], timeout=20)

    if not ok:
        # Fallback for older Android: fetch all and regex match PID column
        ui.info("Older logcat detected without --pid support; filtering locally...")
        ok_all, all_lines = get_logcat_output(["-d", "-t", "2000", "-v", "threadtime"], timeout=25)
        if ok_all:
            pid_str = str(pid)
            pid_regex = re.compile(rf"^\S+\s+\S+\s+{pid_str}\s+")
            lines = [ln for ln in all_lines if pid_regex.search(ln)]
            ok = True
        else:
            lines = all_lines

    if ok:
        label = f"PID {pid}" + (f" ({package_name})" if package_name else "")
        display_log_lines(lines, f"Logs for {label}")
    else:
        ui.error(f"Failed to fetch logs for PID {pid}: {' '.join(lines)}")


# ─── Feature 5: Search Logs by Keyword / Regex ───────────────────────────────

def search_logs_by_keyword() -> None:
    """Search logcat using a substring keyword or regular expression."""
    if not ensure_device():
        return

    pattern_input = ui.get_choice("Enter search keyword or regular expression")
    if not pattern_input:
        ui.error("Search query cannot be empty.")
        return

    is_case_sensitive = ui.confirm("Case-sensitive search?")
    flags = 0 if is_case_sensitive else re.IGNORECASE

    try:
        regex = re.compile(pattern_input, flags)
    except re.error as e:
        ui.error(f"Invalid regular expression: {e}")
        return

    print(f"\n  {ui.Colors.CYAN}Buffer depth to scan: 500, 1000, 3000, 5000 (Press Enter for 2000){ui.Colors.RESET}")
    depth_input = ui.get_choice("Enter buffer depth")
    depth = 2000
    if depth_input:
        try:
            depth = max(100, min(int(depth_input), 20000))
        except ValueError:
            depth = 2000

    ui.info(f"Scanning last {depth} logcat entries for '{pattern_input}'...")
    ok, lines = get_logcat_output(["-d", "-t", str(depth), "-v", "threadtime"], timeout=30)

    if not ok:
        ui.error(f"Failed to retrieve logcat: {' '.join(lines)}")
        return

    matched_lines = [ln for ln in lines if regex.search(ln)]
    display_log_lines(
        matched_lines,
        f"Search Results for '{pattern_input}'",
        highlight_query=pattern_input,
    )


# ─── Feature 6: View Crash Logs ──────────────────────────────────────────────

def view_crash_logs() -> None:
    """View fatal exceptions, process crashes, and Android runtime crash stack traces."""
    if not ensure_device():
        return

    ui.info("Scanning for application crashes and fatal exceptions...")
    all_crash_entries: List[str] = []

    # 1. Query dedicated crash buffer (Android 7.0+)
    ok_crash, crash_lines = get_logcat_output(["-b", "crash", "-d", "-v", "threadtime"], timeout=15)
    if ok_crash and crash_lines:
        all_crash_entries.append(f"{ui.Colors.BOLD}─── Crash Buffer Entries (logcat -b crash) ───{ui.Colors.RESET}")
        all_crash_entries.extend(crash_lines)

    # 2. Query AndroidRuntime fatal exceptions and FATAL tags from main buffer
    ok_main, main_lines = get_logcat_output(
        ["-d", "-s", "AndroidRuntime:E", "FATAL:*", "DEBUG:*", "-t", "500", "-v", "threadtime"],
        timeout=15,
    )
    if ok_main and main_lines:
        if all_crash_entries:
            all_crash_entries.append("")
        all_crash_entries.append(f"{ui.Colors.BOLD}─── AndroidRuntime Fatal Exceptions ───{ui.Colors.RESET}")
        all_crash_entries.extend(main_lines)

    # 3. Check for native crash tombstones in /data/tombstones/
    ok_tomb, tomb_out = adb.run_shell("ls -la /data/tombstones/ 2>/dev/null")
    if ok_tomb and tomb_out.strip() and "No such file" not in tomb_out and "Permission denied" not in tomb_out:
        if all_crash_entries:
            all_crash_entries.append("")
        all_crash_entries.append(f"{ui.Colors.BOLD}─── Native Tombstones in /data/tombstones/ ───{ui.Colors.RESET}")
        for ln in tomb_out.splitlines():
            if ln.strip():
                all_crash_entries.append(f"  {ln}")

    if all_crash_entries:
        ui.header("Application Crash Report:")
        print()
        for line in all_crash_entries:
            print(f"  {colorize_log_line(line)}")
        print()
        ui.success(f"Discovered {len(all_crash_entries)} crash log line(s).")
    else:
        ui.success("No recent crashes or fatal exceptions recorded in the logcat buffers!")


# ─── Feature 7: View ANR Logs ────────────────────────────────────────────────

def view_anr_logs() -> None:
    """View Application Not Responding (ANR) traces and ActivityManager logs."""
    if not ensure_device():
        return

    ui.info("Scanning for Application Not Responding (ANR) incidents...")
    anr_found = False

    # 1. Query ActivityManager for ANR errors
    ok_am, am_lines = get_logcat_output(["-d", "-s", "ActivityManager:E", "-t", "300", "-v", "threadtime"], timeout=15)
    if ok_am and am_lines:
        anr_filtered = [ln for ln in am_lines if "ANR in" in ln or "Reason:" in ln or "Load:" in ln or "CPU usage" in ln]
        if anr_filtered:
            anr_found = True
            display_log_lines(anr_filtered, "ActivityManager ANR Incidents")

    # 2. Query dumpsys activity anrs
    ui.info("Checking system ANR dumpsys...")
    ok_dump, dump_out = adb.run_shell("dumpsys activity anrs", timeout=20)
    if ok_dump and dump_out.strip() and "No ANRs" not in dump_out:
        lines = dump_out.splitlines()
        if len(lines) > 0:
            anr_found = True
            ui.header(f"System ANR Dumpsys (Last {min(len(lines), 100)} lines):")
            print()
            for ln in lines[:100]:
                print(f"  {colorize_log_line(ln)}")
            print()

    # 3. Check for trace files in /data/anr/
    ok_ls, ls_out = adb.run_shell("ls -la /data/anr/ 2>/dev/null")
    if ok_ls and ls_out.strip() and "No such file" not in ls_out and "Permission denied" not in ls_out:
        ui.header("Trace Files in /data/anr/:")
        print()
        for ln in ls_out.splitlines():
            print(f"  {ui.Colors.CYAN}{ln}{ui.Colors.RESET}")
        print()

    if not anr_found:
        ui.success("No recent ANR (Application Not Responding) events detected.")


# ─── Feature 8: Clear Logcat Buffer ──────────────────────────────────────────

def clear_logcat_buffer() -> None:
    """Clear one or all logcat ring buffers."""
    if not ensure_device():
        return

    print(f"""
  {ui.Colors.BOLD}Select Logcat Buffer to Clear:{ui.Colors.RESET}
    {ui.Colors.YELLOW}[1]{ui.Colors.RESET} All buffers (main, system, events, crash, radio)
    {ui.Colors.YELLOW}[2]{ui.Colors.RESET} Main buffer
    {ui.Colors.YELLOW}[3]{ui.Colors.RESET} System buffer
    {ui.Colors.YELLOW}[4]{ui.Colors.RESET} Events buffer
    {ui.Colors.YELLOW}[5]{ui.Colors.RESET} Crash buffer
    {ui.Colors.YELLOW}[6]{ui.Colors.RESET} Radio buffer
    """)

    choice = ui.get_choice("Select buffer option (default 1)")
    buffer_map = {
        "1": None,  # all
        "2": "main",
        "3": "system",
        "4": "events",
        "5": "crash",
        "6": "radio",
    }
    selected_buffer = buffer_map.get(choice if choice else "1", None)

    target_desc = f"buffer '{selected_buffer}'" if selected_buffer else "ALL buffers"
    if not ui.confirm(f"Are you sure you want to clear {target_desc}?"):
        ui.info("Operation cancelled.")
        return

    if selected_buffer:
        ok, out = adb.run(["logcat", "-b", selected_buffer, "-c"])
    else:
        ok, out = adb.run(["logcat", "-c"])

    if ok:
        ui.success(f"Successfully cleared {target_desc}.")
    else:
        ui.error(f"Failed to clear logcat: {out}")


# ─── Feature 9: Save Full Logcat to File ─────────────────────────────────────

def save_logcat_to_file() -> None:
    """Dump logcat buffer to a local text file with timestamp and formatting options."""
    if not ensure_device():
        return

    print(f"""
  {ui.Colors.BOLD}Buffer Selection:{ui.Colors.RESET}
    {ui.Colors.YELLOW}[1]{ui.Colors.RESET} All buffers (main, system, crash, events)
    {ui.Colors.YELLOW}[2]{ui.Colors.RESET} Main buffer only
    {ui.Colors.YELLOW}[3]{ui.Colors.RESET} Crash buffer only
    {ui.Colors.YELLOW}[4]{ui.Colors.RESET} Events buffer only
    {ui.Colors.YELLOW}[5]{ui.Colors.RESET} Radio buffer only
    """)

    b_choice = ui.get_choice("Select buffer [1-5] (default 1)")
    buffer_map = {
        "1": "all",
        "2": "main",
        "3": "crash",
        "4": "events",
        "5": "radio",
    }
    buf = buffer_map.get(b_choice if b_choice else "1", "all")

    print(f"""
  {ui.Colors.BOLD}Output Formats:{ui.Colors.RESET}
    {ui.Colors.CYAN}threadtime{ui.Colors.RESET} : Date, time, PID, TID, priority, tag, message (Standard)
    {ui.Colors.CYAN}time{ui.Colors.RESET}       : Date, invocation time, priority/tag, PID
    {ui.Colors.CYAN}brief{ui.Colors.RESET}      : Priority/tag and PID
    {ui.Colors.CYAN}uid{ui.Colors.RESET}        : UID, PID, TID, priority, tag, message
    {ui.Colors.CYAN}process{ui.Colors.RESET}    : PID and message
    """)
    fmt = ui.get_choice("Enter format (default: threadtime)").strip()
    if not fmt:
        fmt = "threadtime"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    serial_tag = adb.serial.replace(":", "_") if adb.serial else "device"
    default_name = f"logcat_{serial_tag}_{buf}_{timestamp}.txt"

    custom_name = ui.get_choice(f"Enter filename (Press Enter for '{default_name}')")
    filename = custom_name if custom_name else default_name

    ui.info(f"Dumping logcat (buffer: {buf}, format: {fmt}) to file '{filename}'...")
    args = ["logcat", "-b", buf, "-d", "-v", fmt]
    ok, output = adb.run(args, timeout=60)

    if not ok:
        ui.error(f"Failed to dump logcat: {output}")
        return

    try:
        # Ensure logs directory exists if path includes directories
        dirname = os.path.dirname(filename)
        if dirname:
            os.makedirs(dirname, exist_ok=True)

        with open(filename, "w", encoding="utf-8", errors="replace") as f:
            f.write(output)

        file_size = os.path.getsize(filename)
        size_str = (
            f"{file_size / (1024 * 1024):.2f} MB"
            if file_size >= 1024 * 1024
            else f"{file_size / 1024:.1f} KB"
        )
        line_count = len(output.splitlines())

        ui.success(f"Logcat saved successfully!")
        ui.print_kv({
            "File Path": os.path.abspath(filename),
            "Line Count": f"{line_count:,} lines",
            "File Size": size_str,
            "Buffer": buf,
            "Format": fmt,
        })
    except OSError as e:
        ui.error(f"Failed to write log file: {e}")


# ─── Feature 10: View & Configure Logcat Buffer Sizes ─────────────────────────

def view_buffer_sizes() -> None:
    """Inspect and adjust logcat ring buffer allocation and usage statistics."""
    if not ensure_device():
        return

    ui.info("Querying logcat buffer statistics (logcat -g)...")
    ok, output = adb.run(["logcat", "-g"], timeout=10)

    if not ok:
        ui.error(f"Failed to query buffer sizes: {output}")
        return

    ui.header("Logcat Ring Buffer Statistics:")
    print()

    # Parse standard buffer lines: e.g. "main: ring buffer is 256 KiB (240 KiB consumed)..."
    rows = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        print(f"  {ui.Colors.CYAN}{line}{ui.Colors.RESET}")

    print()
    if ui.confirm("Would you like to resize the logcat buffer (logcat -G)?"):
        print(f"""
  {ui.Colors.BOLD}Common Buffer Sizes:{ui.Colors.RESET}
    256K  |  512K  |  1M  |  2M  |  4M  |  8M  |  16M  |  64M
        """)
        new_size = ui.get_choice("Enter new buffer size (e.g. 4M, 16M)").strip().upper()
        if new_size:
            ok_res, res_out = adb.run(["logcat", "-G", new_size])
            if ok_res:
                ui.success(f"Logcat buffer size adjusted to {new_size}.")
                # Show updated status
                _, updated_out = adb.run(["logcat", "-g"])
                print()
                for line in updated_out.splitlines():
                    print(f"  {ui.Colors.GREEN}{line}{ui.Colors.RESET}")
            else:
                ui.error(f"Failed to adjust buffer size: {res_out}")


# ─── Feature 11: View Kernel Logs (dmesg) ────────────────────────────────────

def view_kernel_logs() -> None:
    """View kernel ring buffer messages (dmesg / /proc/kmsg)."""
    if not ensure_device():
        return

    ui.info("Querying kernel ring buffer (dmesg)...")
    ok, output = adb.run_shell("dmesg", timeout=20)

    if not ok or not output.strip() or "Permission denied" in output or "klog_permit" in output:
        # Attempt fallback to cat /proc/kmsg or /dev/kmsg
        ui.warning("Standard dmesg restricted by SELinux. Trying /proc/kmsg / /dev/kmsg...")
        ok_kmsg, kmsg_out = adb.run_shell("cat /proc/kmsg 2>/dev/null", timeout=5)
        if ok_kmsg and kmsg_out.strip():
            output = kmsg_out
            ok = True
        else:
            ui.error("Unable to read kernel logs.")
            print(f"""
  {ui.Colors.YELLOW}ℹ Explanation:{ui.Colors.RESET}
    On Android 8.0+ (Oreo and newer), kernel dmesg access is restricted to
    root / eng / userdebug builds for security reasons (SELinux domain policy).
    If your device is rooted, grant root shell or use `su -c dmesg`.
            """)
            return

    lines = [ln for ln in output.splitlines() if ln.strip()]
    ui.header(f"Kernel Logs / dmesg (Total {len(lines)} lines):")
    print()

    # Show last 100 lines
    last_lines = lines[-100:] if len(lines) > 100 else lines
    if len(lines) > 100:
        ui.info(f"Displaying last 100 lines of {len(lines)}:")
        print()

    for line in last_lines:
        # Highlight kernel log levels or errors
        if "<0>" in line or "<1>" in line or "<2>" in line or "<3>" in line or "ERR" in line or "error" in line.lower():
            print(f"  {ui.Colors.RED}{line}{ui.Colors.RESET}")
        elif "<4>" in line or "warn" in line.lower():
            print(f"  {ui.Colors.YELLOW}{line}{ui.Colors.RESET}")
        elif "<6>" in line or "info" in line.lower():
            print(f"  {ui.Colors.GREEN}{line}{ui.Colors.RESET}")
        else:
            print(f"  {line}")

    print()
    if ui.confirm("Save full kernel dmesg log to a local file?"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        serial_tag = adb.serial.replace(":", "_") if adb.serial else "device"
        filename = f"dmesg_{serial_tag}_{timestamp}.txt"
        try:
            with open(filename, "w", encoding="utf-8", errors="replace") as f:
                f.write(output)
            ui.success(f"Kernel log saved to: {os.path.abspath(filename)} ({len(lines)} lines)")
        except OSError as e:
            ui.error(f"Failed to write file: {e}")


# ─── Feature 12: View Event Logs ─────────────────────────────────────────────

def view_event_logs() -> None:
    """View and parse binary system event logs (am_proc_start, am_kill, battery, etc.)."""
    if not ensure_device():
        return

    count_input = ui.get_choice("Enter line count (default 100)")
    count = 100
    if count_input:
        try:
            count = max(1, min(int(count_input), 5000))
        except ValueError:
            count = 100

    ui.info(f"Fetching last {count} system event logs (logcat -b events)...")
    ok, lines = get_logcat_output(["-b", "events", "-d", "-t", str(count), "-v", "threadtime"], timeout=20)

    if not ok:
        ui.error(f"Failed to fetch event logs: {' '.join(lines)}")
        return

    ui.header(f"System Event Logs (logcat -b events, {len(lines)} lines):")
    print()

    for line in lines:
        # Highlight specific high-value event tags
        if "am_anr" in line or "am_crash" in line:
            print(f"  {ui.Colors.BOLD}{ui.Colors.RED}{line}{ui.Colors.RESET}")
        elif "am_proc_start" in line or "am_proc_bound" in line:
            print(f"  {ui.Colors.GREEN}{line}{ui.Colors.RESET}")
        elif "am_kill" in line or "am_proc_died" in line:
            print(f"  {ui.Colors.YELLOW}{line}{ui.Colors.RESET}")
        elif "am_focused_activity" in line or "wm_task_created" in line:
            print(f"  {ui.Colors.CYAN}{line}{ui.Colors.RESET}")
        elif "battery_level" in line or "power_screen_state" in line:
            print(f"  {ui.Colors.MAGENTA}{line}{ui.Colors.RESET}")
        else:
            print(f"  {line}")

    print()


# ─── Feature 13: Live Logcat Stream ──────────────────────────────────────────

def live_logcat_stream() -> None:
    """Stream logcat live to the terminal with real-time colorization."""
    if not ensure_device():
        return

    print(f"""
  {ui.Colors.BOLD}Live Logcat Stream Configuration:{ui.Colors.RESET}
    Press {ui.Colors.BOLD}{ui.Colors.RED}Ctrl+C{ui.Colors.RESET} at any time to stop streaming and return to menu.
    """)

    tag_filter = ui.get_choice("Filter by Tag (Leave empty for all tags)")
    prio_filter = ui.get_choice("Min Priority [V/D/I/W/E/F] (default V)").upper()
    if not prio_filter or prio_filter not in ("V", "D", "I", "W", "E", "F"):
        prio_filter = "V"

    cmd = ["adb"]
    if adb.serial:
        cmd += ["-s", adb.serial]
    cmd += ["logcat", "-v", "threadtime"]

    if tag_filter:
        cmd += ["-s", f"{tag_filter}:{prio_filter}"]
    elif prio_filter != "V":
        cmd += [f"*:{prio_filter}"]

    ui.info("Starting live logcat stream... (Press Ctrl+C to exit)\n")
    time.sleep(1)

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        if proc.stdout:
            for line in proc.stdout:
                line_str = line.rstrip("\r\n")
                if line_str:
                    print(f"  {colorize_log_line(line_str)}")
    except KeyboardInterrupt:
        print(f"\n\n  {ui.Colors.YELLOW}Live logcat stream stopped.{ui.Colors.RESET}")
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            pass


# ─── Main Menu Loop ──────────────────────────────────────────────────────────

def logcat_menu() -> None:
    """Main Logcat Viewer and Diagnostics submenu."""
    while True:
        ui.clear()
        ui.print_banner()
        ui.print_device_status(adb.serial, adb.getprop("ro.product.model") if adb.serial else "")
        ui.print_menu("📋 Logcat Viewer & Diagnostics", [
            "View recent logs (last 100 lines)",
            "View logs by priority (V/D/I/W/E/F)",
            "Filter logs by tag",
            "Filter logs by PID / Package",
            "Search logs by keyword / regex",
            "View crash logs (ActivityManager / Fatal)",
            "View ANR logs (Application Not Responding)",
            "Clear logcat buffer",
            "Save full logcat to file",
            "View & configure buffer sizes",
            "View kernel logs (dmesg)",
            "View event logs (system events)",
            "Live logcat stream (interactive)",
        ], columns=2)

        choice = ui.get_choice()

        if choice == "0":
            break
        elif choice == "1":
            view_recent_logs()
        elif choice == "2":
            view_logs_by_priority()
        elif choice == "3":
            filter_logs_by_tag()
        elif choice == "4":
            filter_logs_by_pid()
        elif choice == "5":
            search_logs_by_keyword()
        elif choice == "6":
            view_crash_logs()
        elif choice == "7":
            view_anr_logs()
        elif choice == "8":
            clear_logcat_buffer()
        elif choice == "9":
            save_logcat_to_file()
        elif choice == "10":
            view_buffer_sizes()
        elif choice == "11":
            view_kernel_logs()
        elif choice == "12":
            view_event_logs()
        elif choice == "13":
            live_logcat_stream()
        else:
            ui.error("Invalid option. Try again.")

        ui.pause()
