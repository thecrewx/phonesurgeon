"""
modules/automation.py — Automation, Macro Recording, Batch Execution, and Scripting.

Provides end-to-end automation capabilities including interactive macro recording,
macro playback with iteration control, batch file command runner, command history
with rerun capabilities, favorite command presets, custom ADB/shell execution,
remote shell script execution, and scheduled repeat command loops.
"""

import os
import sys
import json
import time
import re
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Any

from core.adb import adb
from core import ui
from core.device import ensure_device


# ─── File & Directory Management ──────────────────────────────────────────────

SCRIPTS_DIR = os.path.join(os.getcwd(), "scripts")
FAVORITES_FILE = os.path.join(SCRIPTS_DIR, "favorites.json")
HISTORY_FILE = os.path.join(SCRIPTS_DIR, "command_history.json")


def _ensure_scripts_dir() -> str:
    """Ensure scripts directory exists and return its absolute path."""
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    return SCRIPTS_DIR


def _sanitize_filename(name: str) -> str:
    """Sanitize a string for safe filesystem naming."""
    clean = re.sub(r'[\\/*?:"<>| ]', "_", name.strip().lower())
    return clean if clean else "unnamed_macro"


# ─── History & Favorites Helpers ──────────────────────────────────────────────

def _record_history(cmd_type: str, command: str, success: bool, duration_ms: float):
    """Append a command run to persistent history JSON file."""
    _ensure_scripts_dir()
    history = _load_history()

    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": cmd_type,
        "command": command,
        "success": success,
        "duration_ms": round(duration_ms, 2),
        "device": adb.serial or "default",
    }
    history.insert(0, entry)
    # Keep last 100 records
    history = history[:100]

    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass


def _load_history() -> List[Dict[str, Any]]:
    """Load history records from history file."""
    if not os.path.isfile(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _load_favorites() -> List[Dict[str, str]]:
    """Load saved favorite commands."""
    if not os.path.isfile(FAVORITES_FILE):
        # Default presets
        defaults = [
            {"name": "Take Screenshot & Pull", "type": "shell", "command": "screencap -p /sdcard/screen.png", "desc": "Capture screenshot to sdcard"},
            {"name": "Clear Logcat Buffer", "type": "adb", "command": "logcat -c", "desc": "Wipe logcat buffer"},
            {"name": "Restart System UI", "type": "shell", "command": "pkill -f com.android.systemui", "desc": "Kill systemui to reload status bar"},
            {"name": "Dump Battery Info", "type": "shell", "command": "dumpsys battery", "desc": "Print detailed battery metrics"},
            {"name": "Force Stop All Background", "type": "shell", "command": "am kill-all", "desc": "Kill all safe background processes"},
        ]
        _save_favorites(defaults)
        return defaults
    try:
        with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_favorites(favorites: List[Dict[str, str]]):
    """Save favorites list to JSON file."""
    _ensure_scripts_dir()
    try:
        with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
            json.dump(favorites, f, indent=2)
    except Exception:
        pass


# ─── 1. Record Macro ──────────────────────────────────────────────────────────

def record_macro():
    """Interactive wizard to record a sequence of commands and save to macro JSON."""
    _ensure_scripts_dir()

    ui.header("Interactive Macro Recorder")
    print(f"  {ui.Colors.CYAN}Record a series of ADB / Shell actions into a reusable JSON macro file.{ui.Colors.RESET}\n")

    macro_name = ui.get_choice("Enter macro name (e.g., 'App Setup & Login')")
    if not macro_name:
        ui.error("Macro name cannot be empty.")
        return

    macro_desc = ui.get_choice("Enter macro description (optional)")

    steps: List[Dict[str, Any]] = []

    while True:
        ui.clear()
        ui.print_banner()
        print(f"\n  {ui.Colors.BOLD}Recording Macro: {ui.Colors.CYAN}{macro_name}{ui.Colors.RESET} ({len(steps)} steps recorded)\n")

        if steps:
            print(f"  {ui.Colors.BOLD}Current Steps:{ui.Colors.RESET}")
            for i, st in enumerate(steps, 1):
                t_str = st.get("type", "shell").upper()
                c_str = st.get("command", "")
                d_str = f" [sleep {st.get('delay_after', 0)}s]" if st.get('delay_after', 0) > 0 else ""
                print(f"    {ui.Colors.YELLOW}{i:>2}.{ui.Colors.RESET} [{ui.Colors.GREEN}{t_str}{ui.Colors.RESET}] {c_str}{ui.Colors.DIM}{d_str}{ui.Colors.RESET}")
            print()

        ui.print_menu("Step Action Menu", [
            "Add Shell Command (e.g. input tap, am start, pm clear)",
            "Add ADB Command (e.g. install, push, reboot, forward)",
            "Add Touch Tap on Screen (X, Y)",
            "Add Touch Swipe / Scroll (X1, Y1 -> X2, Y2)",
            "Add Key Event (Home, Back, Power, Volume, Enter)",
            "Add Text Input (Type text into focused field)",
            "Add Sleep / Delay Pause",
            "Add Screenshot Capture",
            "Test Last Step Live on Device",
            "Remove Last Step",
            "Save and Finish Recording",
        ])

        act = ui.get_choice()

        if act == "0":
            if steps and not ui.confirm("Discard recorded steps and exit?"):
                continue
            ui.warning("Macro recording cancelled.")
            break

        elif act == "1":
            cmd = ui.get_choice("Enter shell command (without 'adb shell')")
            if cmd:
                delay = ui.get_choice("Delay after execution in seconds (default 0.5)")
                delay_sec = float(delay) if delay and delay.replace(".", "", 1).isdigit() else 0.5
                steps.append({"type": "shell", "command": cmd, "delay_after": delay_sec})
                ui.success(f"Added shell step: {cmd}")

        elif act == "2":
            cmd = ui.get_choice("Enter ADB command (without 'adb')")
            if cmd:
                delay = ui.get_choice("Delay after execution in seconds (default 1.0)")
                delay_sec = float(delay) if delay and delay.replace(".", "", 1).isdigit() else 1.0
                steps.append({"type": "adb", "command": cmd, "delay_after": delay_sec})
                ui.success(f"Added ADB step: {cmd}")

        elif act == "3":
            coords = ui.get_choice("Enter X and Y coordinates (e.g., 500 1200)")
            parts = coords.split()
            if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                x, y = parts[0], parts[1]
                delay = ui.get_choice("Delay after tap in seconds (default 0.5)")
                delay_sec = float(delay) if delay and delay.replace(".", "", 1).isdigit() else 0.5
                steps.append({"type": "shell", "command": f"input tap {x} {y}", "delay_after": delay_sec, "desc": f"Tap at ({x}, {y})"})
                ui.success(f"Added Tap step at ({x}, {y})")
            else:
                ui.error("Invalid coordinates.")

        elif act == "4":
            swipe_data = ui.get_choice("Enter X1 Y1 X2 Y2 [duration_ms] (e.g. 500 1500 500 500 300)")
            parts = swipe_data.split()
            if len(parts) >= 4:
                x1, y1, x2, y2 = parts[0], parts[1], parts[2], parts[3]
                dur = parts[4] if len(parts) > 4 else "300"
                steps.append({"type": "shell", "command": f"input swipe {x1} {y1} {x2} {y2} {dur}", "delay_after": 0.5, "desc": f"Swipe ({x1},{y1}) -> ({x2},{y2})"})
                ui.success("Added Swipe step.")
            else:
                ui.error("Invalid swipe arguments.")

        elif act == "5":
            print("\n  Common Keycodes: HOME (3), BACK (4), POWER (26), ENTER (66), VOL_UP (24), VOL_DOWN (25), TAB (61)")
            key = ui.get_choice("Enter Keycode name or number (e.g. KEYCODE_HOME or 3)")
            if key:
                steps.append({"type": "shell", "command": f"input keyevent {key}", "delay_after": 0.5, "desc": f"Keyevent {key}"})
                ui.success(f"Added Key event: {key}")

        elif act == "6":
            txt = ui.get_choice("Enter text to type")
            if txt:
                # Escape spaces for input text
                esc_txt = txt.replace(" ", "%s")
                steps.append({"type": "shell", "command": f"input text {esc_txt}", "delay_after": 0.5, "desc": f"Type text '{txt}'"})
                ui.success(f"Added Type Text step.")

        elif act == "7":
            sleep_t = ui.get_choice("Enter pause duration in seconds (e.g. 2.5)")
            if sleep_t and sleep_t.replace(".", "", 1).isdigit():
                steps.append({"type": "sleep", "command": f"sleep {sleep_t}", "delay_after": float(sleep_t), "desc": f"Pause for {sleep_t}s"})
                ui.success(f"Added Pause: {sleep_t}s")

        elif act == "8":
            ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            cap_cmd = f"screencap -p /sdcard/macro_cap_{ts_str}.png"
            steps.append({"type": "shell", "command": cap_cmd, "delay_after": 0.5, "desc": "Capture screenshot"})
            ui.success("Added Screenshot step.")

        elif act == "9":
            if not steps:
                ui.warning("No steps to test.")
            else:
                last_step = steps[-1]
                ui.header(f"Testing step live: [{last_step['type']}] {last_step['command']}...")
                if ensure_device():
                    if last_step["type"] == "adb":
                        ok, out = adb.run(last_step["command"].split())
                    elif last_step["type"] == "sleep":
                        time.sleep(last_step["delay_after"])
                        ok, out = True, f"Slept {last_step['delay_after']}s"
                    else:
                        ok, out = adb.run_shell(last_step["command"])
                    if ok:
                        ui.success(f"Test succeeded! Output: {out if out else 'OK'}")
                    else:
                        ui.error(f"Test failed: {out}")
            ui.pause()

        elif act == "10":
            if steps:
                popped = steps.pop()
                ui.info(f"Removed step: {popped.get('command')}")
            else:
                ui.warning("Step list is already empty.")

        elif act == "11":
            if not steps:
                ui.error("Cannot save empty macro. Add at least one step.")
                continue

            safe_name = _sanitize_filename(macro_name)
            filename = f"{safe_name}.json"
            filepath = os.path.join(SCRIPTS_DIR, filename)

            macro_data = {
                "name": macro_name,
                "description": macro_desc,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "version": "1.0",
                "device_target": adb.serial or "any",
                "steps": steps,
            }

            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(macro_data, f, indent=2)
                ui.success(f"Macro '{macro_name}' saved successfully!")
                ui.info(f"File location: {os.path.abspath(filepath)}")
                break
            except Exception as e:
                ui.error(f"Failed to save macro file: {e}")


# ─── 2. Replay Macro ──────────────────────────────────────────────────────────

def replay_macro():
    """Select and execute a saved macro file with loop iterations and delay control."""
    _ensure_scripts_dir()

    macros = _get_available_macros()
    if not macros:
        ui.warning("No saved macros found in 'scripts/' directory. Record a macro first!")
        return

    ui.header("Replay Saved Macro")
    rows = []
    for i, m in enumerate(macros, 1):
        rows.append((f"  {i}", m["name"], f"{m['step_count']} steps", m["created_at"], os.path.basename(m["path"])))
    ui.print_table(rows, headers=("  #", "Macro Name", "Steps", "Created", "File"))

    choice = ui.get_choice("Select macro number to replay")
    try:
        idx = int(choice) - 1
        if not (0 <= idx < len(macros)):
            ui.error("Invalid selection.")
            return
    except ValueError:
        ui.error("Invalid input.")
        return

    target_macro = macros[idx]
    with open(target_macro["path"], "r", encoding="utf-8") as f:
        data = json.load(f)

    steps = data.get("steps", [])
    if not steps:
        ui.error("Macro contains no executable steps.")
        return

    # Prompt for replay options
    loops_str = ui.get_choice("Number of iterations / loops (default 1)")
    loops = int(loops_str) if loops_str and loops_str.isdigit() and int(loops_str) > 0 else 1

    speed_str = ui.get_choice("Speed multiplier (e.g. 1.0 = normal, 0.5 = 2x faster, 2.0 = 2x slower, default 1.0)")
    try:
        speed_mult = float(speed_str) if speed_str else 1.0
    except ValueError:
        speed_mult = 1.0

    stop_on_err = ui.confirm("Stop execution if any step fails?")

    if not ensure_device():
        return

    ui.header(f"Replaying Macro: '{data.get('name')}' ({loops} loop{'s' if loops > 1 else ''})...")
    total_start = time.time()
    steps_passed = 0
    steps_failed = 0

    for loop in range(1, loops + 1):
        if loops > 1:
            print(f"\n  {ui.Colors.BOLD}{ui.Colors.CYAN}── Loop {loop}/{loops} ──{ui.Colors.RESET}")

        for s_idx, step in enumerate(steps, 1):
            st_type = step.get("type", "shell")
            cmd = step.get("command", "")
            delay = step.get("delay_after", 0.5) * speed_mult
            desc = step.get("desc", cmd)

            label = f"[{loop}/{loops}] Step {s_idx}/{len(steps)}"
            ui.progress_bar(s_idx, len(steps), label=label)

            step_start = time.time()
            ok = False
            out = ""

            if st_type == "adb":
                ok, out = adb.run(cmd.split())
            elif st_type == "sleep":
                time.sleep(delay)
                ok, out = True, f"Waited {delay:.2f}s"
            else:  # shell
                ok, out = adb.run_shell(cmd)

            step_dur = (time.time() - step_start) * 1000
            _record_history(f"macro:{st_type}", cmd, ok, step_dur)

            if ok:
                steps_passed += 1
            else:
                steps_failed += 1
                ui.error(f"Step {s_idx} failed: {cmd} -> {out}")
                if stop_on_err:
                    ui.warning("Execution aborted due to step failure.")
                    break

            if delay > 0 and st_type != "sleep":
                time.sleep(delay)

        if steps_failed > 0 and stop_on_err:
            break

    total_elapsed = time.time() - total_start
    print()
    if steps_failed == 0:
        ui.success(f"Macro replay completed in {total_elapsed:.2f}s! ({steps_passed} steps executed successfully)")
    else:
        ui.warning(f"Macro finished with issues in {total_elapsed:.2f}s: {steps_passed} passed, {steps_failed} failed.")


def _get_available_macros() -> List[Dict[str, Any]]:
    """Scan scripts directory for valid macro JSON files."""
    _ensure_scripts_dir()
    macros = []
    for f in os.listdir(SCRIPTS_DIR):
        if f.endswith(".json") and f not in ("favorites.json", "command_history.json"):
            fpath = os.path.join(SCRIPTS_DIR, f)
            try:
                with open(fpath, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    if isinstance(data, dict) and "steps" in data:
                        macros.append({
                            "name": data.get("name", f[:-5]),
                            "description": data.get("description", ""),
                            "created_at": data.get("created_at", "—"),
                            "step_count": len(data.get("steps", [])),
                            "path": fpath,
                        })
            except Exception:
                continue
    return macros


# ─── 3. Run Batch Commands from Text File ─────────────────────────────────────

def run_batch_commands():
    """Read and sequentially execute ADB/shell commands from a text file (.txt / .adb)."""
    ui.header("Run Batch Commands from Text File")

    path = ui.get_choice("Enter path to batch command file (.txt / .adb / .sh)")
    clean_p = os.path.expanduser(path.strip().strip("'\""))

    if not os.path.isfile(clean_p):
        ui.error(f"File not found: {clean_p}")
        return

    try:
        with open(clean_p, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()
    except Exception as e:
        ui.error(f"Unable to read file: {e}")
        return

    commands = []
    for line in raw_lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        commands.append(line)

    if not commands:
        ui.warning("No executable commands found in file (all lines were empty or comments).")
        return

    ui.info(f"Loaded {len(commands)} command(s) from {os.path.basename(clean_p)}:")
    for i, c in enumerate(commands[:10], 1):
        print(f"  {i:>2}. {c}")
    if len(commands) > 10:
        print(f"  ... and {len(commands) - 10} more commands.")

    if not ui.confirm(f"Execute {len(commands)} commands on device '{adb.serial}'?"):
        ui.warning("Batch execution cancelled.")
        return

    if not ensure_device():
        return

    ui.header("Executing Batch Commands...")
    results = []
    start_all = time.time()

    for idx, cmd in enumerate(commands, 1):
        ui.progress_bar(idx, len(commands), label="Batch Running")
        cmd_start = time.time()

        # Parse command prefix
        if cmd.startswith("adb "):
            args = cmd[len("adb "):].strip().split()
            ok, out = adb.run(args)
            c_type = "adb"
        elif cmd.startswith("shell "):
            sh_cmd = cmd[len("shell "):].strip()
            ok, out = adb.run_shell(sh_cmd)
            c_type = "shell"
        elif cmd.startswith("sleep "):
            parts = cmd.split()
            sec = float(parts[1]) if len(parts) > 1 and parts[1].replace(".", "", 1).isdigit() else 1.0
            time.sleep(sec)
            ok, out = True, f"Slept {sec}s"
            c_type = "sleep"
        else:
            # Default to shell
            ok, out = adb.run_shell(cmd)
            c_type = "shell"

        dur_ms = (time.time() - cmd_start) * 1000
        _record_history(f"batch:{c_type}", cmd, ok, dur_ms)

        status_tag = "OK" if ok else "FAIL"
        summary = out.replace("\n", " ")[:35] if out else "—"
        results.append((f"  {idx}", cmd[:30], status_tag, f"{dur_ms:.1f}ms", summary))

    total_sec = time.time() - start_all
    print("\n")
    ui.print_table(results, headers=("  #", "Command", "Status", "Duration", "Output Summary"))

    passed = sum(1 for r in results if r[2] == "OK")
    failed = len(results) - passed
    ui.success(f"Batch completed in {total_sec:.2f}s: {passed} passed, {failed} failed.")


# ─── 4. View Command History ──────────────────────────────────────────────────

def view_command_history():
    """Inspect recent command executions, review timing, and re-execute items."""
    history = _load_history()
    if not history:
        ui.info("Command history is empty. Commands executed in this session will appear here.")
        return

    ui.header(f"Command Execution History ({len(history)} recent entries)")

    rows = []
    for i, h in enumerate(history[:30], 1):
        status_color = f"{ui.Colors.GREEN}✓ OK{ui.Colors.RESET}" if h.get("success") else f"{ui.Colors.RED}✗ ERR{ui.Colors.RESET}"
        rows.append((
            f"  {i}",
            h.get("timestamp", "—"),
            h.get("type", "adb"),
            h.get("command", "")[:35],
            status_color,
            f"{h.get('duration_ms', 0):.0f}ms",
        ))

    ui.print_table(rows, headers=("  #", "Timestamp", "Type", "Command", "Status", "Duration"))

    sub = ui.get_choice("Options: [1] Rerun a command  [2] Save command to Favorites  [3] Clear History  [0] Back")
    if sub == "1":
        num = ui.get_choice("Enter # number of command to rerun")
        try:
            n_idx = int(num) - 1
            if 0 <= n_idx < len(history):
                selected = history[n_idx]
                _execute_single_command(selected["type"], selected["command"])
        except ValueError:
            ui.error("Invalid entry.")
    elif sub == "2":
        num = ui.get_choice("Enter # number to add to Favorites")
        try:
            n_idx = int(num) - 1
            if 0 <= n_idx < len(history):
                selected = history[n_idx]
                name = ui.get_choice(f"Enter preset name for '{selected['command']}'")
                favs = _load_favorites()
                favs.append({
                    "name": name if name else selected["command"],
                    "type": selected["type"].replace("macro:", "").replace("batch:", ""),
                    "command": selected["command"],
                    "desc": f"Saved from history on {datetime.now().strftime('%Y-%m-%d')}",
                })
                _save_favorites(favs)
                ui.success("Command added to favorites!")
        except ValueError:
            ui.error("Invalid entry.")
    elif sub == "3":
        if ui.confirm("Clear all command history?"):
            try:
                if os.path.exists(HISTORY_FILE):
                    os.remove(HISTORY_FILE)
                ui.success("History cleared.")
            except Exception as e:
                ui.error(f"Failed to clear history: {e}")


def _execute_single_command(cmd_type: str, cmd_str: str):
    """Execute a single arbitrary command and record history."""
    if not ensure_device():
        return

    clean_type = cmd_type.split(":")[-1]
    ui.header(f"Executing: [{clean_type.upper()}] {cmd_str}")

    t0 = time.time()
    if clean_type == "adb":
        ok, out = adb.run(cmd_str.split())
    else:
        ok, out = adb.run_shell(cmd_str)

    dur = (time.time() - t0) * 1000
    _record_history(clean_type, cmd_str, ok, dur)

    if ok:
        ui.success(f"Command finished in {dur:.1f}ms:")
        if out:
            print(f"\n{out}\n")
    else:
        ui.error(f"Command failed ({dur:.1f}ms): {out}")


# ─── 5. Save Current Command to Favorites ─────────────────────────────────────

def manage_favorites():
    """View, execute, create, or delete favorite preset commands."""
    favs = _load_favorites()

    while True:
        ui.clear()
        ui.print_banner()
        ui.header(f"⭐ Favorite Commands & Quick Presets ({len(favs)} saved)")

        if favs:
            rows = []
            for i, f in enumerate(favs, 1):
                rows.append((f"  {i}", f.get("name", "Unnamed"), f.get("type", "shell").upper(), f.get("command", "")[:40]))
            ui.print_table(rows, headers=("  #", "Preset Name", "Type", "Command"))
        else:
            ui.info("No favorites saved yet.")

        ui.print_menu("Favorites Menu", [
            "Run a Favorite Preset",
            "Add New Favorite Command",
            "Delete a Favorite Preset",
            "Reset to Default Presets",
        ])

        choice = ui.get_choice()

        if choice == "0":
            break
        elif choice == "1":
            if not favs:
                ui.warning("No presets available.")
                ui.pause()
                continue
            sel = ui.get_choice("Enter preset # number to execute")
            try:
                idx = int(sel) - 1
                if 0 <= idx < len(favs):
                    target = favs[idx]
                    _execute_single_command(target.get("type", "shell"), target.get("command", ""))
                else:
                    ui.error("Invalid number.")
            except ValueError:
                ui.error("Invalid entry.")
            ui.pause()
        elif choice == "2":
            name = ui.get_choice("Enter preset name")
            c_type = ui.get_choice("Command type: [1] Shell  [2] ADB")
            type_str = "shell" if c_type != "2" else "adb"
            cmd = ui.get_choice(f"Enter {type_str} command")
            desc = ui.get_choice("Enter description (optional)")

            if name and cmd:
                favs.append({"name": name, "type": type_str, "command": cmd, "desc": desc})
                _save_favorites(favs)
                ui.success(f"Preset '{name}' saved to favorites!")
            else:
                ui.error("Name and command are required.")
            ui.pause()
        elif choice == "3":
            if not favs:
                ui.warning("No favorites to delete.")
                ui.pause()
                continue
            sel = ui.get_choice("Enter preset # number to delete")
            try:
                idx = int(sel) - 1
                if 0 <= idx < len(favs):
                    removed = favs.pop(idx)
                    _save_favorites(favs)
                    ui.success(f"Removed '{removed.get('name')}'.")
                else:
                    ui.error("Invalid number.")
            except ValueError:
                ui.error("Invalid entry.")
            ui.pause()
        elif choice == "4":
            if ui.confirm("Reset favorites to defaults?"):
                if os.path.exists(FAVORITES_FILE):
                    os.remove(FAVORITES_FILE)
                favs = _load_favorites()
                ui.success("Favorites reset to defaults.")
            ui.pause()


# ─── 6. List Saved Macros ─────────────────────────────────────────────────────

def list_saved_macros():
    """Inspect saved macros in scripts directory, view step breakdowns, or delete macros."""
    _ensure_scripts_dir()
    macros = _get_available_macros()

    if not macros:
        ui.info(f"No macros found in '{SCRIPTS_DIR}'. Use Option 1 to record a macro.")
        return

    ui.header(f"Saved Automation Macros ({len(macros)} found in scripts/)")
    rows = []
    for i, m in enumerate(macros, 1):
        rows.append((
            f"  {i}",
            m["name"],
            f"{m['step_count']} steps",
            m["created_at"],
            os.path.basename(m["path"]),
        ))
    ui.print_table(rows, headers=("  #", "Macro Name", "Step Count", "Created Date", "File"))

    sub = ui.get_choice("Select option: [1] View Macro Steps  [2] Delete Macro  [0] Back")
    if sub == "1":
        sel = ui.get_choice("Enter macro # number to inspect")
        try:
            idx = int(sel) - 1
            if 0 <= idx < len(macros):
                with open(macros[idx]["path"], "r", encoding="utf-8") as f:
                    m_data = json.load(f)
                ui.header(f"Macro Details: {m_data.get('name')}")
                print(f"  Description : {m_data.get('description', 'None')}")
                print(f"  Created At  : {m_data.get('created_at', 'Unknown')}\n")

                step_rows = []
                for s_i, st in enumerate(m_data.get("steps", []), 1):
                    step_rows.append((
                        f"  {s_i}",
                        st.get("type", "shell").upper(),
                        st.get("command", ""),
                        f"{st.get('delay_after', 0)}s",
                    ))
                ui.print_table(step_rows, headers=("  Step", "Type", "Command", "Delay After"))
        except (ValueError, Exception) as e:
            ui.error(f"Error reading macro: {e}")
    elif sub == "2":
        sel = ui.get_choice("Enter macro # number to delete")
        try:
            idx = int(sel) - 1
            if 0 <= idx < len(macros):
                target = macros[idx]
                if ui.confirm(f"Are you sure you want to permanently delete '{target['name']}'?"):
                    os.remove(target["path"])
                    ui.success(f"Deleted {target['name']}.")
        except ValueError:
            ui.error("Invalid entry.")


# ─── 7. Run Custom ADB Command ────────────────────────────────────────────────

def run_custom_adb_command():
    """Execute arbitrary ADB CLI command interactively with duration metrics."""
    ui.header("Run Custom ADB Command")
    print(f"  {ui.Colors.DIM}Enter arguments without the leading 'adb' (e.g., 'devices -l', 'install app.apk', 'forward tcp:8080 tcp:8080'){ui.Colors.RESET}\n")

    cmd_str = ui.get_choice("adb")
    if not cmd_str:
        ui.error("Command cannot be empty.")
        return

    args = cmd_str.split()
    ui.header(f"Executing: adb {' '.join(args)}...")

    t0 = time.time()
    ok, out = adb.run(args, timeout=120)
    dur = (time.time() - t0) * 1000

    _record_history("adb", cmd_str, ok, dur)

    if ok:
        ui.success(f"Executed successfully in {dur:.1f}ms:")
        if out:
            print(f"\n{out}\n")
    else:
        ui.error(f"Command failed ({dur:.1f}ms): {out}")

    if ui.confirm("Save this command to Favorites?"):
        name = ui.get_choice("Enter friendly name for favorite")
        favs = _load_favorites()
        favs.append({"name": name if name else cmd_str, "type": "adb", "command": cmd_str, "desc": "Custom ADB Command"})
        _save_favorites(favs)
        ui.success("Saved to favorites!")


# ─── 8. Run Custom Shell Command ──────────────────────────────────────────────

def run_custom_shell_command():
    """Execute arbitrary ADB shell command with optional root attempt."""
    if not ensure_device():
        return

    ui.header("Run Custom ADB Shell Command")
    print(f"  {ui.Colors.DIM}Enter command (e.g., 'getprop', 'ls -la /sdcard/', 'dumpsys window displays', 'cat /proc/cpuinfo'){ui.Colors.RESET}\n")

    cmd = ui.get_choice("shell")
    if not cmd:
        ui.error("Command cannot be empty.")
        return

    as_root = False
    if ui.confirm("Run as root (su -c)?"):
        as_root = True
        actual_cmd = f"su -c \"{cmd}\""
    else:
        actual_cmd = cmd

    ui.header(f"Executing shell command: {actual_cmd}...")

    t0 = time.time()
    ok, out = adb.run_shell(actual_cmd, timeout=120)
    dur = (time.time() - t0) * 1000

    _record_history("shell" if not as_root else "root_shell", cmd, ok, dur)

    if ok:
        ui.success(f"Shell command executed in {dur:.1f}ms:")
        if out:
            print(f"\n{out}\n")
    else:
        ui.error(f"Shell command failed ({dur:.1f}ms): {out}")

    if ui.confirm("Save this command to Favorites?"):
        name = ui.get_choice("Enter friendly name for favorite")
        favs = _load_favorites()
        favs.append({"name": name if name else cmd, "type": "shell", "command": cmd, "desc": "Custom Shell Command"})
        _save_favorites(favs)
        ui.success("Saved to favorites!")


# ─── 9. Execute Script File (.sh on device) ───────────────────────────────────

def execute_device_script():
    """Push local shell script to device /data/local/tmp, make executable, and run."""
    if not ensure_device():
        return

    ui.header("Execute Shell Script (.sh) on Device")

    path = ui.get_choice("Enter path to local .sh script file (or type 'NEW' to create template)")
    clean_p = os.path.expanduser(path.strip().strip("'\""))

    if clean_p.upper() == "NEW":
        # Create sample script
        _ensure_scripts_dir()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        sample_path = os.path.join(SCRIPTS_DIR, f"sample_task_{ts}.sh")
        content = """#!/system/bin/sh
# DroidCommander Sample Device Automation Script
echo "=== Starting Automated Task on $(getprop ro.product.model) ==="
echo "Date: $(date)"
echo "Uptime: $(uptime)"
echo "Free Memory:"
free -m 2>/dev/null || cat /proc/meminfo | head -n 4
echo "=== Task Completed Successfully ==="
"""
        with open(sample_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        ui.success(f"Created sample script at: {sample_path}")
        clean_p = sample_path

    if not os.path.isfile(clean_p):
        ui.error(f"Script file not found: {clean_p}")
        return

    script_name = os.path.basename(clean_p)
    remote_path = f"/data/local/tmp/{script_name}"

    ui.info(f"Pushing '{script_name}' to device: {remote_path}...")
    ok_push, push_out = adb.run(["push", clean_p, remote_path])
    if not ok_push:
        ui.error(f"Failed to push script: {push_out}")
        return

    ui.info("Setting executable permissions (chmod 755)...")
    adb.run_shell(f"chmod 755 {remote_path}")

    as_root = ui.confirm("Execute with root privileges (su)?")
    exec_cmd = f"su -c 'sh {remote_path}'" if as_root else f"sh {remote_path}"

    ui.header(f"Executing '{remote_path}'...")
    start_t = time.time()
    ok_exec, exec_out = adb.run_shell(exec_cmd, timeout=300)
    dur = time.time() - start_t

    if ok_exec:
        ui.success(f"Script completed in {dur:.2f}s:")
        print(f"\n{exec_out}\n")
    else:
        ui.error(f"Script execution failed: {exec_out}")

    # Cleanup prompt
    if ui.confirm(f"Remove temporary script '{remote_path}' from device?"):
        adb.run_shell(f"rm {remote_path}")
        ui.info("Temporary script removed from device.")


# ─── 10. Scheduled Repeat Command ─────────────────────────────────────────────

def scheduled_repeat_command():
    """Run an ADB or shell command repeatedly N times with a custom delay interval."""
    if not ensure_device():
        return

    ui.header("Scheduled Repeat Command Runner")
    print(f"  {ui.Colors.DIM}Executes a selected command repeatedly with precision delay interval.{ui.Colors.RESET}\n")

    c_type = ui.get_choice("Command type: [1] Shell  [2] ADB")
    cmd_type = "shell" if c_type != "2" else "adb"

    cmd = ui.get_choice(f"Enter {cmd_type} command to run repeatedly")
    if not cmd:
        ui.error("Command cannot be empty.")
        return

    count_str = ui.get_choice("Number of repetitions (e.g. 5, or 0 for continuous until Ctrl+C)")
    try:
        repeat_count = int(count_str) if count_str else 5
    except ValueError:
        repeat_count = 5

    delay_str = ui.get_choice("Delay interval between executions in seconds (e.g. 2.0)")
    try:
        delay_sec = float(delay_str) if delay_str else 2.0
    except ValueError:
        delay_sec = 2.0

    save_log = ui.confirm("Save output log to file?")
    log_lines = []

    ui.header(f"Starting Repeat Loop: '{cmd}' ({'Continuous' if repeat_count == 0 else f'{repeat_count} times'}, {delay_sec}s interval)...")
    print(f"  {ui.Colors.YELLOW}Press Ctrl+C at any time to halt repetition.{ui.Colors.RESET}\n")

    iteration = 0
    passed = 0
    failed = 0

    try:
        while True:
            iteration += 1
            if repeat_count > 0 and iteration > repeat_count:
                break

            ts = datetime.now().strftime("%H:%M:%S")
            iter_label = f"#{iteration}/{repeat_count}" if repeat_count > 0 else f"#{iteration}"

            t0 = time.time()
            if cmd_type == "adb":
                ok, out = adb.run(cmd.split())
            else:
                ok, out = adb.run_shell(cmd)
            dur = (time.time() - t0) * 1000

            status_str = f"{ui.Colors.GREEN}OK{ui.Colors.RESET}" if ok else f"{ui.Colors.RED}ERR{ui.Colors.RESET}"
            out_preview = out.replace("\n", " ")[:60] if out else "—"

            print(f"  [{ts}] {iter_label:<8} [{status_str}] ({dur:.0f}ms) {out_preview}")

            if save_log:
                log_lines.append(f"[{ts}] Iteration {iteration} - Status: {'OK' if ok else 'ERR'} ({dur:.1f}ms)\n{out}\n")

            if ok:
                passed += 1
            else:
                failed += 1

            if repeat_count == 0 or iteration < repeat_count:
                time.sleep(delay_sec)

    except KeyboardInterrupt:
        print(f"\n\n  {ui.Colors.YELLOW}Repetition stopped by user.{ui.Colors.RESET}")

    ui.success(f"Finished {iteration - 1 if repeat_count == 0 else iteration} iterations: {passed} passed, {failed} failed.")

    if save_log and log_lines:
        _ensure_scripts_dir()
        ts_f = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_f = os.path.join(SCRIPTS_DIR, f"repeat_log_{ts_f}.txt")
        try:
            with open(log_f, "w", encoding="utf-8") as f:
                f.write(f"=== REPEAT COMMAND LOG: {cmd} ===\n")
                f.write(f"Device: {adb.serial} | Total: {iteration}\n\n")
                f.writelines(log_lines)
            ui.success(f"Execution log saved: {os.path.abspath(log_f)}")
        except Exception as e:
            ui.error(f"Failed to write log: {e}")


# ─── Main Menu Loop ───────────────────────────────────────────────────────────

def automation_menu():
    """Automation and scripting interactive submenu."""
    _ensure_scripts_dir()

    options = [
        "Record New Macro (Interactive Step Wizard)",
        "Replay Macro from File",
        "Run Batch Commands from Text File (.txt/.adb)",
        "View & Rerun Command History",
        "Manage Favorite Commands & Presets",
        "List & Inspect Saved Macros",
        "Run Custom ADB Command",
        "Run Custom Shell Command",
        "Execute Shell Script File (.sh) on Device",
        "Scheduled Repeat Command (N times / Interval)",
    ]

    while True:
        ui.clear()
        ui.print_banner()
        ui.print_menu("🤖 Automation & Scripting Studio", options, columns=2)

        choice = ui.get_choice()

        if choice == "0":
            break
        elif choice == "1":
            record_macro()
        elif choice == "2":
            replay_macro()
        elif choice == "3":
            run_batch_commands()
        elif choice == "4":
            view_command_history()
        elif choice == "5":
            manage_favorites()
        elif choice == "6":
            list_saved_macros()
        elif choice == "7":
            run_custom_adb_command()
        elif choice == "8":
            run_custom_shell_command()
        elif choice == "9":
            execute_device_script()
        elif choice == "10":
            scheduled_repeat_command()
        else:
            ui.error("Invalid option. Please choose a valid number.")

        ui.pause()
