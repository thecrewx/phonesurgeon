"""
modules/ui_inspector.py — UI & Hierarchy Inspector Module for DroidCommander.

Provides deep introspection into the Android UI hierarchy, window manager,
active activities, fragments, services, content providers, accessibility
services, display cutouts, and intent filters.
"""

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Any

from core.adb import adb
from core import ui
from core.device import ensure_device


# ─── Helper Functions ─────────────────────────────────────────────────────────

def _get_current_focus_raw() -> Tuple[Optional[str], Optional[str]]:
    """
    Extract the currently focused package and activity/window name.

    Returns
    -------
    Tuple[Optional[str], Optional[str]]
        (package_name, activity_name) or (None, None) if not found.
    """
    # Method 1: dumpsys window (mCurrentFocus / mFocusedApp)
    ok, out = adb.run(["shell", "dumpsys", "window", "windows"], timeout=10)
    if ok and out:
        # Check mCurrentFocus: Window{... u0 com.example.app/com.example.app.MainActivity}
        m = re.search(r"mCurrentFocus=Window\{[^\}]*\s+u0\s+([^/\s]+)/([^/\s\}]+)", out)
        if m:
            pkg, act = m.group(1), m.group(2)
            if act.startswith("."):
                act = pkg + act
            return pkg, act

        # Check mFocusedApp: AppWindowToken{... token=... name=com.example.app/.MainActivity}
        m = re.search(r"mFocusedApp=AppWindowToken\{[^\}]*name=([^/\s]+)/([^/\s\}]+)", out)
        if m:
            pkg, act = m.group(1), m.group(2)
            if act.startswith("."):
                act = pkg + act
            return pkg, act

        # Newer Android format: ActivityRecord{... u0 com.example.app/.MainActivity ...}
        m = re.search(r"mFocusedApp=.*ActivityRecord\{[^\}]*u0\s+([^/\s]+)/([^/\s\}]+)", out)
        if m:
            pkg, act = m.group(1), m.group(2)
            if act.startswith("."):
                act = pkg + act
            return pkg, act

    # Method 2: dumpsys activity top
    ok, out = adb.run(["shell", "dumpsys", "activity", "top"], timeout=10)
    if ok and out:
        m = re.search(r"ACTIVITY\s+([^/\s]+)/([^/\s]+)\s+([a-f0-9]+)\s+pid=(\d+)", out)
        if m:
            pkg, act = m.group(1), m.group(2)
            if act.startswith("."):
                act = pkg + act
            return pkg, act

        m = re.search(r"topResumedActivity=ActivityRecord\{[^\}]*u0\s+([^/\s]+)/([^/\s\}]+)", out)
        if m:
            pkg, act = m.group(1), m.group(2)
            if act.startswith("."):
                act = pkg + act
            return pkg, act

    # Method 3: dumpsys activity activities
    ok, out = adb.run(["shell", "dumpsys", "activity", "activities"], timeout=10)
    if ok and out:
        m = re.search(r"mResumedActivity:\s+ActivityRecord\{[^\}]*u0\s+([^/\s]+)/([^/\s\}]+)", out)
        if m:
            pkg, act = m.group(1), m.group(2)
            if act.startswith("."):
                act = pkg + act
            return pkg, act

    return None, None


def _get_package_details(package_name: str) -> Dict[str, str]:
    """Retrieve detailed package information (version, targetSdk, APK path)."""
    details: Dict[str, str] = {
        "Package": package_name,
        "Version Name": "Unknown",
        "Version Code": "Unknown",
        "Target SDK": "Unknown",
        "Min SDK": "Unknown",
        "APK Path": "Unknown",
        "Installer": "Unknown",
    }

    ok, out = adb.run(["shell", "dumpsys", "package", package_name], timeout=10)
    if not ok or not out:
        return details

    v_name = re.search(r"versionName=([^\s]+)", out)
    if v_name:
        details["Version Name"] = v_name.group(1)

    v_code = re.search(r"versionCode=(\d+)", out)
    if v_code:
        details["Version Code"] = v_code.group(1)

    t_sdk = re.search(r"targetSdk=(\d+)", out)
    if t_sdk:
        details["Target SDK"] = t_sdk.group(1)

    m_sdk = re.search(r"minSdk=(\d+)", out)
    if m_sdk:
        details["Min SDK"] = m_sdk.group(1)

    code_path = re.search(r"codePath=([^\s]+)", out)
    if code_path:
        details["APK Path"] = code_path.group(1)

    installer = re.search(r"installerPackageName=([^\s]+)", out)
    if installer:
        details["Installer"] = installer.group(1)

    return details


def _dump_ui_xml_from_device() -> Tuple[bool, str]:
    """
    Dump the current UI hierarchy XML using uiautomator.

    Returns
    -------
    Tuple[bool, str]
        (success, xml_content_or_error_message)
    """
    temp_remote = "/data/local/tmp/uidump.xml"
    # Remove old dump if exists
    adb.run(["shell", "rm", "-f", temp_remote], timeout=5)

    ui.info("Capturing UI hierarchy via uiautomator...")
    ok, out = adb.run(["shell", "uiautomator", "dump", temp_remote], timeout=15)
    if not ok and "UI hierchary dumped to" not in out and "dumped to:" not in out:
        # Fallback without args
        ok, out = adb.run(["shell", "uiautomator", "dump"], timeout=15)

    # Read back XML
    ok_read, xml_content = adb.run(["shell", "cat", temp_remote], timeout=15)
    if not ok_read or not xml_content.strip() or "<hierarchy" not in xml_content:
        # Try default path /sdcard/window_dump.xml
        ok_read, xml_content = adb.run(["shell", "cat", "/sdcard/window_dump.xml"], timeout=15)

    # Clean up device temp file
    adb.run(["shell", "rm", "-f", temp_remote], timeout=5)

    if ok_read and "<hierarchy" in xml_content:
        # Clean any garbage prefix before <?xml
        start_idx = xml_content.find("<?xml")
        if start_idx == -1:
            start_idx = xml_content.find("<hierarchy")
        if start_idx != -1:
            xml_content = xml_content[start_idx:]
        return True, xml_content.strip()

    return False, f"Failed to dump UI hierarchy: {out}"


def _parse_ui_node_dict(elem: ET.Element, depth: int = 0) -> List[Dict[str, Any]]:
    """Recursively parse XML elements into flat node dicts."""
    nodes = []
    attribs = elem.attrib

    bounds_str = attribs.get("bounds", "")
    coords = (0, 0, 0, 0)
    center = (0, 0)
    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds_str)
    if m:
        x1, y1, x2, y2 = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        coords = (x1, y1, x2, y2)
        center = ((x1 + x2) // 2, (y1 + y2) // 2)

    node_data = {
        "depth": depth,
        "class": attribs.get("class", ""),
        "package": attribs.get("package", ""),
        "text": attribs.get("text", ""),
        "resource_id": attribs.get("resource-id", ""),
        "content_desc": attribs.get("content-desc", ""),
        "checkable": attribs.get("checkable", "false") == "true",
        "checked": attribs.get("checked", "false") == "true",
        "clickable": attribs.get("clickable", "false") == "true",
        "enabled": attribs.get("enabled", "false") == "true",
        "focusable": attribs.get("focusable", "false") == "true",
        "focused": attribs.get("focused", "false") == "true",
        "scrollable": attribs.get("scrollable", "false") == "true",
        "long_clickable": attribs.get("long-clickable", "false") == "true",
        "password": attribs.get("password", "false") == "true",
        "selected": attribs.get("selected", "false") == "true",
        "bounds_str": bounds_str,
        "bounds": coords,
        "center": center,
    }

    if elem.tag == "node":
        nodes.append(node_data)

    for child in elem:
        nodes.extend(_parse_ui_node_dict(child, depth + 1))

    return nodes


# ─── Module Features ──────────────────────────────────────────────────────────

def dump_ui_hierarchy():
    """Dump UI hierarchy XML, parse tree nodes, summarize, and optionally save to file."""
    if not ensure_device():
        return

    ok, xml_content = _dump_ui_xml_from_device()
    if not ok:
        ui.error(xml_content)
        return

    try:
        root = ET.fromstring(xml_content)
        nodes = _parse_ui_node_dict(root)
    except ET.ParseError as e:
        ui.error(f"Error parsing XML hierarchy: {e}")
        return

    ui.success(f"UI hierarchy successfully captured! ({len(nodes)} total nodes)")

    clickable_nodes = [n for n in nodes if n["clickable"]]
    text_nodes = [n for n in nodes if n["text"]]
    input_nodes = [n for n in nodes if "EditText" in n["class"] or "AutoComplete" in n["class"]]
    scrollable_nodes = [n for n in nodes if n["scrollable"]]

    print()
    ui.header("UI Component Summary:")
    summary_data = {
        "Total UI Nodes": str(len(nodes)),
        "Clickable Elements": str(len(clickable_nodes)),
        "Text Elements": str(len(text_nodes)),
        "Input / Edit Fields": str(len(input_nodes)),
        "Scrollable Views": str(len(scrollable_nodes)),
    }
    ui.print_kv(summary_data)

    print()
    ui.header("Interactive & Clickable Elements:")
    if clickable_nodes:
        headers = ("#", "Class", "Resource ID", "Text / Desc", "Bounds [L,T][R,B]", "Center (X,Y)")
        rows = []
        for i, n in enumerate(clickable_nodes[:25], 1):
            cls_name = n["class"].split(".")[-1]
            res_id = n["resource_id"].split("/")[-1] if "/" in n["resource_id"] else n["resource_id"]
            txt = n["text"] or n["content_desc"]
            if len(txt) > 20:
                txt = txt[:17] + "..."
            if len(res_id) > 22:
                res_id = res_id[:19] + "..."
            rows.append((
                str(i),
                cls_name,
                res_id if res_id else "—",
                txt if txt else "—",
                n["bounds_str"],
                f"({n['center'][0]}, {n['center'][1]})",
            ))
        ui.print_table(rows, headers)
        if len(clickable_nodes) > 25:
            ui.info(f"Showing top 25 of {len(clickable_nodes)} clickable items.")
    else:
        ui.warning("No clickable elements detected in current layout.")

    # Sub-actions
    print()
    print(f"  {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Save full XML to local file")
    print(f"  {ui.Colors.YELLOW}[2]{ui.Colors.RESET} Search element by text or resource ID")
    print(f"  {ui.Colors.YELLOW}[3]{ui.Colors.RESET} Simulate tap on a numbered element")
    print(f"  {ui.Colors.YELLOW}[0]{ui.Colors.RESET} Return to UI Inspector menu")
    print()

    sub_choice = ui.get_choice("Action")
    if sub_choice == "1":
        dumps_dir = os.path.join(os.getcwd(), "dumps")
        os.makedirs(dumps_dir, exist_ok=True)
        filename = f"ui_dump_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
        file_path = os.path.join(dumps_dir, filename)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(xml_content)
            ui.success(f"Hierarchy XML saved to: {file_path}")
        except Exception as ex:
            ui.error(f"Failed to save file: {ex}")
    elif sub_choice == "2":
        query = ui.get_choice("Enter search string (text, ID, or class)")
        if query:
            q_lower = query.lower()
            matches = [
                n for n in nodes
                if q_lower in n["text"].lower()
                or q_lower in n["resource_id"].lower()
                or q_lower in n["content_desc"].lower()
                or q_lower in n["class"].lower()
            ]
            if matches:
                ui.header(f"Found {len(matches)} matching element(s):")
                m_headers = ("#", "Class", "Resource ID", "Text", "Bounds", "Center Tap")
                m_rows = []
                for i, m_node in enumerate(matches, 1):
                    cls_name = m_node["class"].split(".")[-1]
                    res_id = m_node["resource_id"].split("/")[-1] if "/" in m_node["resource_id"] else m_node["resource_id"]
                    txt = m_node["text"] or m_node["content_desc"]
                    m_rows.append((
                        str(i),
                        cls_name,
                        res_id or "—",
                        txt or "—",
                        m_node["bounds_str"],
                        f"{m_node['center'][0]} {m_node['center'][1]}",
                    ))
                ui.print_table(m_rows, m_headers)
            else:
                ui.warning(f"No elements matching '{query}' found.")
    elif sub_choice == "3" and clickable_nodes:
        idx_str = ui.get_choice("Enter element # to tap")
        try:
            elem_idx = int(idx_str) - 1
            if 0 <= elem_idx < min(len(clickable_nodes), 25):
                target = clickable_nodes[elem_idx]
                cx, cy = target["center"]
                ui.info(f"Tapping element at ({cx}, {cy})...")
                adb.run(["shell", "input", "tap", str(cx), str(cy)])
                ui.success("Tap sent!")
            else:
                ui.error("Invalid element index.")
        except ValueError:
            ui.error("Invalid number.")


def get_current_activity_name():
    """Retrieve and display currently focused package, activity, and process info."""
    if not ensure_device():
        return

    ui.header("Active Foreground Activity Inspector")
    pkg, act = _get_current_focus_raw()

    if not pkg:
        ui.error("Could not determine current active activity. Is the screen unlocked?")
        return

    # Extract PID if running
    pid = "Unknown"
    ok, pid_out = adb.run(["shell", "pidof", pkg], timeout=5)
    if ok and pid_out.strip():
        pid = pid_out.strip()

    # Package metadata
    details = _get_package_details(pkg)

    data = {
        "Package Name": f"{ui.Colors.GREEN}{pkg}{ui.Colors.RESET}",
        "Activity Class": f"{ui.Colors.CYAN}{act}{ui.Colors.RESET}",
        "Process ID (PID)": pid,
        "Version Name": details.get("Version Name", "—"),
        "Version Code": details.get("Version Code", "—"),
        "Target SDK": details.get("Target SDK", "—"),
        "Min SDK": details.get("Min SDK", "—"),
        "APK Path": details.get("APK Path", "—"),
        "Installer": details.get("Installer", "—"),
    }
    print()
    ui.print_kv(data)

    # Sub-actions
    print()
    print(f"  {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Force Stop this App (`am force-stop`)")
    print(f"  {ui.Colors.YELLOW}[2]{ui.Colors.RESET} Restart this Activity (`am start -S`)")
    print(f"  {ui.Colors.YELLOW}[3]{ui.Colors.RESET} Open App Details in Settings")
    print(f"  {ui.Colors.YELLOW}[4]{ui.Colors.RESET} Clear App Cache & Data (`pm clear`)")
    print(f"  {ui.Colors.YELLOW}[0]{ui.Colors.RESET} Return to menu")
    print()

    action = ui.get_choice("Action")
    if action == "1":
        ui.info(f"Stopping package {pkg}...")
        ok, _ = adb.run(["shell", "am", "force-stop", pkg])
        if ok:
            ui.success(f"App {pkg} stopped.")
        else:
            ui.error("Failed to stop app.")
    elif action == "2":
        ui.info(f"Restarting activity {pkg}/{act}...")
        ok, out = adb.run(["shell", "am", "start", "-S", "-n", f"{pkg}/{act}"])
        if ok:
            ui.success(f"Activity started: {out}")
        else:
            ui.error(f"Failed to start activity: {out}")
    elif action == "3":
        ui.info("Opening app details in device settings...")
        adb.run(["shell", "am", "start", "-a", "android.settings.APPLICATION_DETAILS_SETTINGS", "-d", f"package:{pkg}"])
        ui.success("Settings page opened.")
    elif action == "4":
        if ui.confirm(f"Are you sure you want to CLEAR all data for {pkg}?"):
            ok, out = adb.run(["shell", "pm", "clear", pkg])
            if ok:
                ui.success(f"Cleared data for {pkg}.")
            else:
                ui.error(f"Failed to clear data: {out}")


def get_current_fragments():
    """Inspect and display active and added Android fragments for the top activity."""
    if not ensure_device():
        return

    pkg, act = _get_current_focus_raw()
    if not pkg:
        ui.error("Could not determine current foreground package.")
        return

    ui.header(f"Fragment Inspector for: {pkg}")
    ui.info(f"Querying FragmentManager hierarchy from dumpsys for {pkg}...")

    ok, out = adb.run(["shell", "dumpsys", "activity", "top"], timeout=10)
    if not ok or not out:
        ok, out = adb.run(["shell", "dumpsys", "activity", pkg], timeout=10)

    if not ok or not out:
        ui.error("Failed to retrieve activity top hierarchy.")
        return

    # Extract FragmentManager sections
    fragment_lines: List[str] = []
    in_fragment_section = False
    for line in out.splitlines():
        if "FragmentManager" in line or "Active Fragments in" in line or "Added Fragments:" in line:
            in_fragment_section = True
        elif in_fragment_section and line.strip().startswith("View Hierarchy:"):
            in_fragment_section = False
        elif in_fragment_section and line.strip().startswith("Resumed:"):
            in_fragment_section = False

        if in_fragment_section:
            fragment_lines.append(line)

    if not fragment_lines:
        # Search for any Fragment occurrences
        matches = [line for line in out.splitlines() if "Fragment" in line and ("{" in line or "#" in line)]
        if matches:
            ui.header("Detected Fragment References:")
            for m in matches[:20]:
                print(f"    {ui.Colors.CYAN}•{ui.Colors.RESET} {m.strip()}")
        else:
            ui.warning("No active FragmentManager or Fragment hierarchy detected in the current activity.")
            ui.info("The application might be using pure Views, Jetpack Compose, Flutter, or React Native.")
        return

    ui.success("Fragments found in active Activity:")
    print()
    for fline in fragment_lines:
        stripped = fline.rstrip()
        if "Active Fragments" in stripped or "Added Fragments:" in stripped or "FragmentManager" in stripped:
            print(f"  {ui.Colors.BOLD}{ui.Colors.GREEN}{stripped}{ui.Colors.RESET}")
        elif "#" in stripped:
            print(f"    {ui.Colors.CYAN}{stripped.strip()}{ui.Colors.RESET}")
        else:
            print(f"      {ui.Colors.DIM}{stripped.strip()}{ui.Colors.RESET}")


def list_recent_activities():
    """List recent activity task stacks and background task records."""
    if not ensure_device():
        return

    ui.header("Recent Activities & Task Stack")
    ok, out = adb.run(["shell", "dumpsys", "activity", "recents"], timeout=12)
    if not ok or not out:
        ok, out = adb.run(["shell", "dumpsys", "activity", "activities"], timeout=12)

    if not ok or not out:
        ui.error("Failed to query activity stack.")
        return

    # Parse Tasks: TaskRecord / Task #id
    tasks: List[Dict[str, str]] = []
    task_pattern = re.compile(r"\* (?:TaskRecord|Task)\{(\w+)\s+#(\d+)\s+(?:type=[^\s]+\s+)?(?:I=)?([^/\s]+)/([^/\s\}]+)", re.IGNORECASE)
    activity_pattern = re.compile(r"Hist\s+#\d+:\s+ActivityRecord\{[^\}]*\s+u0\s+([^/\s]+)/([^/\s\}]+)", re.IGNORECASE)

    current_task: Optional[Dict[str, str]] = None
    for line in out.splitlines():
        t_match = task_pattern.search(line)
        if t_match:
            current_task = {
                "hash": t_match.group(1),
                "task_id": t_match.group(2),
                "pkg": t_match.group(3),
                "activity": t_match.group(4),
                "activities_count": "1",
            }
            tasks.append(current_task)
            continue

        # Check alternative format: Task id #...
        alt_match = re.search(r"Task\s+id\s+#(\d+):\s+([^\s]+)", line)
        if alt_match:
            current_task = {
                "hash": "—",
                "task_id": alt_match.group(1),
                "pkg": alt_match.group(2).split("/")[0] if "/" in alt_match.group(2) else alt_match.group(2),
                "activity": alt_match.group(2).split("/")[1] if "/" in alt_match.group(2) else "—",
                "activities_count": "1",
            }
            tasks.append(current_task)

    if not tasks:
        # Fallback simpler line search
        rows = []
        for line in out.splitlines()[:40]:
            if "ActivityRecord{" in line or "TaskRecord{" in line:
                rows.append((line.strip(),))
        if rows:
            ui.print_table(rows, ("Activity & Task Records",))
        else:
            ui.info("No recent task records returned by dumpsys.")
        return

    headers = ("Task ID", "Package Name", "Base / Top Activity", "Task Hash")
    rows = []
    for t in tasks[:20]:
        act = t["activity"]
        if act.startswith("."):
            act = t["pkg"] + act
        if len(act) > 30:
            act = "..." + act[-27:]
        rows.append((
            f"#{t['task_id']}",
            t["pkg"],
            act,
            t["hash"],
        ))

    ui.print_table(rows, headers)
    ui.info(f"Total tasks detected: {len(tasks)}")


def get_focused_window_info():
    """Extract and display deep technical details of the currently focused window."""
    if not ensure_device():
        return

    ui.header("Focused Window Technical Details")
    ok, out = adb.run(["shell", "dumpsys", "window", "windows"], timeout=12)
    if not ok or not out:
        ui.error("Failed to query window manager.")
        return

    # Extract mCurrentFocus
    focus_match = re.search(r"mCurrentFocus=Window\{([a-f0-9]+)\s+u0\s+([^\}]+)\}", out)
    if not focus_match:
        # Try finding Window matching mCurrentFocus
        focus_match = re.search(r"mCurrentFocus=([^\r\n]+)", out)
        if not focus_match:
            ui.error("Could not find mCurrentFocus in dumpsys window.")
            return
        focus_title = focus_match.group(1).strip()
        ui.print_kv({"Current Focus": focus_title})
        return

    win_hash = focus_match.group(1)
    win_title = focus_match.group(2).strip()

    # Locate the full Window block for this window
    window_block = ""
    start_token = f"Window{{{win_hash}"
    in_block = False
    for line in out.splitlines():
        if start_token in line:
            in_block = True
        elif in_block and line.strip().startswith("Window{") and start_token not in line:
            break
        if in_block:
            window_block += line + "\n"

    parsed_info: Dict[str, str] = {
        "Window Hash": win_hash,
        "Window Title": win_title,
    }

    # Extract Window Type
    type_match = re.search(r"(?:type|mType)=(\w+|\d+)", window_block)
    if type_match:
        parsed_info["Window Type"] = type_match.group(1)

    # Extract Frame / Bounds
    frame_match = re.search(r"mFrame=\[([0-9\s,-]+)\]\[([0-9\s,-]+)\]", window_block)
    if frame_match:
        parsed_info["Frame Bounds"] = f"[{frame_match.group(1)}][{frame_match.group(2)}]"

    # Extract Surface size
    surf_match = re.search(r"mSurface=Surface\(name=([^)]+)\)\s*.*w=(\d+)\s+h=(\d+)", window_block)
    if surf_match:
        parsed_info["Surface Size"] = f"{surf_match.group(2)} x {surf_match.group(3)}"

    # Extract Flags
    flags_match = re.search(r"(?:mAttrs=WM.LayoutParams\{|flags=)([^\}\n]+)", window_block)
    if flags_match:
        raw_flags = flags_match.group(1)
        if "FLAG_SECURE" in raw_flags or "0x2000" in raw_flags:
            parsed_info["Secure Flag (FLAG_SECURE)"] = f"{ui.Colors.RED}ENABLED (Screenshots blocked){ui.Colors.RESET}"
        else:
            parsed_info["Secure Flag"] = "Disabled"
        if "FLAG_FULLSCREEN" in raw_flags:
            parsed_info["Fullscreen"] = "Yes"

    # Extract Alpha / Visibility
    alpha_match = re.search(r"mAlpha=([\d.]+)", window_block)
    if alpha_match:
        parsed_info["Alpha (Opacity)"] = alpha_match.group(1)

    shown_match = re.search(r"mShown=(\w+)", window_block)
    if shown_match:
        parsed_info["Shown On Screen"] = shown_match.group(1)

    # Extract Layer / Z-Order
    layer_match = re.search(r"mLayer=(\d+)", window_block)
    if layer_match:
        parsed_info["Layer / Z-Order"] = layer_match.group(1)

    # Extract Display ID
    disp_match = re.search(r"mDisplayId=(\d+)", window_block)
    if disp_match:
        parsed_info["Display ID"] = disp_match.group(1)

    print()
    ui.print_kv(parsed_info)


def list_all_windows():
    """List all active windows on the device and classify them."""
    if not ensure_device():
        return

    ui.header("Active Window Hierarchy (Z-Order Top to Bottom)")
    ok, out = adb.run(["shell", "dumpsys", "window", "windows"], timeout=12)
    if not ok or not out:
        ui.error("Failed to query window manager.")
        return

    windows: List[Tuple[str, str, str, str]] = []
    # Pattern: Window #<num> Window{<hash> u0 <title>}:
    win_pattern = re.compile(r"Window\s+#(\d+)\s+Window\{([a-f0-9]+)\s+u0\s+([^\}]+)\}:", re.IGNORECASE)

    current_idx = ""
    current_hash = ""
    current_title = ""
    current_shown = "—"
    current_layer = "—"

    for line in out.splitlines():
        m = win_pattern.search(line)
        if m:
            if current_title:
                windows.append((current_idx, current_title, current_layer, current_shown))
            current_idx = f"#{m.group(1)}"
            current_hash = m.group(2)
            current_title = m.group(3).strip()
            current_shown = "—"
            current_layer = "—"
            continue

        if "mShown=true" in line or "mHasSurface=true" in line:
            current_shown = f"{ui.Colors.GREEN}Visible{ui.Colors.RESET}"
        elif "mShown=false" in line:
            current_shown = f"{ui.Colors.DIM}Hidden{ui.Colors.RESET}"

        l_m = re.search(r"mLayer=(\d+)", line)
        if l_m:
            current_layer = l_m.group(1)

    if current_title:
        windows.append((current_idx, current_title, current_layer, current_shown))

    if not windows:
        # Fallback line filter
        for line in out.splitlines():
            if "Window #" in line:
                windows.append(("", line.strip()[:65], "—", "—"))

    if not windows:
        ui.warning("No windows returned by dumpsys window.")
        return

    headers = ("#", "Window Identifier / Name", "Z-Layer", "State")
    ui.print_table(windows[:30], headers)
    if len(windows) > 30:
        ui.info(f"Showing 30 of {len(windows)} active windows.")


def view_current_content_providers():
    """Display published content providers and active client connections."""
    if not ensure_device():
        return

    pkg, _ = _get_current_focus_raw()
    target_pkg = pkg if pkg else ""

    ui.header("Content Provider Inspector")
    print(f"  {ui.Colors.YELLOW}[1]{ui.Colors.RESET} Inspect foreground app providers ({target_pkg or 'None'})")
    print(f"  {ui.Colors.YELLOW}[2]{ui.Colors.RESET} Inspect specific package")
    print(f"  {ui.Colors.YELLOW}[3]{ui.Colors.RESET} List all published system & 3rd party providers")
    print(f"  {ui.Colors.YELLOW}[0]{ui.Colors.RESET} Back")
    print()

    choice = ui.get_choice("Select option")
    cmd_args = ["shell", "dumpsys", "activity", "providers"]
    filter_pkg = None

    if choice == "1":
        if not target_pkg:
            ui.error("No active foreground package detected.")
            return
        filter_pkg = target_pkg
    elif choice == "2":
        filter_pkg = ui.get_choice("Enter package name")
        if not filter_pkg:
            return
    elif choice == "3":
        filter_pkg = None
    else:
        return

    ui.info("Querying content providers...")
    ok, out = adb.run(cmd_args, timeout=12)
    if not ok or not out:
        ui.error("Failed to query activity providers.")
        return

    # Parse published providers
    # Pattern: * ContentProviderRecord{... u0 <authority> ...}
    # package=<pkg> process=<proc>
    providers: List[Dict[str, str]] = []
    curr_prov: Optional[Dict[str, str]] = None

    for line in out.splitlines():
        line_s = line.strip()
        if "ContentProviderRecord{" in line_s or "Published content providers" in line_s:
            auth_match = re.search(r"ContentProviderRecord\{[^\}]*\s+u0\s+([^\s\}]+)", line_s)
            if auth_match:
                curr_prov = {
                    "authority": auth_match.group(1),
                    "package": "—",
                    "process": "—",
                    "clients": "0",
                }
                providers.append(curr_prov)
            continue

        if curr_prov:
            pkg_m = re.search(r"package=([^\s]+)", line_s)
            if pkg_m:
                curr_prov["package"] = pkg_m.group(1)

            proc_m = re.search(r"process=([^\s]+)", line_s)
            if proc_m:
                curr_prov["process"] = proc_m.group(1)

            client_m = re.search(r"Client\s+connections:\s*(\d+)", line_s)
            if client_m:
                curr_prov["clients"] = client_m.group(1)

    if filter_pkg:
        providers = [p for p in providers if filter_pkg.lower() in p["package"].lower() or filter_pkg.lower() in p["authority"].lower()]

    if not providers:
        ui.warning(f"No matching content providers found{' for ' + filter_pkg if filter_pkg else ''}.")
        return

    headers = ("Authority", "Package Name", "Process Name", "Clients")
    rows = []
    for p in providers[:30]:
        rows.append((
            p["authority"],
            p["package"],
            p["process"],
            p["clients"],
        ))

    ui.print_table(rows, headers)
    ui.info(f"Total providers found: {len(providers)}")


def view_running_services():
    """List running services, foreground service types, and active clients."""
    if not ensure_device():
        return

    pkg, _ = _get_current_focus_raw()
    target_pkg = pkg or ""

    ui.header("Running Services Inspector")
    print(f"  {ui.Colors.YELLOW}[1]{ui.Colors.RESET} View foreground app services ({target_pkg or 'None'})")
    print(f"  {ui.Colors.YELLOW}[2]{ui.Colors.RESET} View services for specific package")
    print(f"  {ui.Colors.YELLOW}[3]{ui.Colors.RESET} View all 3rd party & system services")
    print(f"  {ui.Colors.YELLOW}[0]{ui.Colors.RESET} Back")
    print()

    choice = ui.get_choice("Select option")
    filter_pkg = None
    if choice == "1":
        if not target_pkg:
            ui.error("No active foreground package detected.")
            return
        filter_pkg = target_pkg
    elif choice == "2":
        filter_pkg = ui.get_choice("Enter package name")
        if not filter_pkg:
            return
    elif choice == "3":
        filter_pkg = None
    else:
        return

    ui.info("Querying running services...")
    ok, out = adb.run(["shell", "dumpsys", "activity", "services"], timeout=15)
    if not ok or not out:
        ui.error("Failed to query activity services.")
        return

    # Parse ServiceRecord
    # Pattern: * ServiceRecord{<hash> u0 <pkg>/<service> <flags>}
    service_pattern = re.compile(r"\*\s+ServiceRecord\{[a-f0-9]+\s+u0\s+([^/\s]+)/([^/\s]+)", re.IGNORECASE)
    services: List[Dict[str, str]] = []
    curr_srv: Optional[Dict[str, str]] = None

    for line in out.splitlines():
        line_s = line.strip()
        m = service_pattern.search(line_s)
        if m:
            p_name = m.group(1)
            s_name = m.group(2)
            if s_name.startswith("."):
                s_name = p_name + s_name
            curr_srv = {
                "package": p_name,
                "service": s_name,
                "process": "—",
                "pid": "—",
                "is_foreground": "No",
            }
            services.append(curr_srv)
            continue

        if curr_srv:
            proc_m = re.search(r"app=ProcessRecord\{[a-f0-9]+\s+(\d+):([^/\s]+)", line_s)
            if proc_m:
                curr_srv["pid"] = proc_m.group(1)
                curr_srv["process"] = proc_m.group(2)

            if "isForeground=true" in line_s or "foregroundId=" in line_s:
                curr_srv["is_foreground"] = f"{ui.Colors.GREEN}YES (Foreground){ui.Colors.RESET}"

    if filter_pkg:
        services = [s for s in services if filter_pkg.lower() in s["package"].lower() or filter_pkg.lower() in s["service"].lower()]

    if not services:
        ui.warning(f"No running services found{' for ' + filter_pkg if filter_pkg else ''}.")
        return

    headers = ("Service Component", "Package", "PID", "Foreground?")
    rows = []
    for s in services[:35]:
        s_comp = s["service"].split(".")[-1]
        if len(s_comp) > 28:
            s_comp = s_comp[:25] + "..."
        rows.append((
            s_comp,
            s["package"],
            s["pid"],
            s["is_foreground"],
        ))

    ui.print_table(rows, headers)
    ui.info(f"Total running services detected: {len(services)}")


def dump_accessibility_info():
    """Inspect accessibility framework, enabled accessibility services, and features."""
    if not ensure_device():
        return

    ui.header("Accessibility Subsystem Inspector")
    ok_svc, svc_out = adb.run(["shell", "settings", "get", "secure", "enabled_accessibility_services"], timeout=5)
    ok_dump, dump_out = adb.run(["shell", "dumpsys", "accessibility"], timeout=12)

    enabled_services = svc_out.strip() if ok_svc and svc_out.strip() and svc_out.strip() != "null" else "None"

    # Extract accessibility flags
    ok_touch, touch_out = adb.run(["shell", "settings", "get", "secure", "touch_exploration_enabled"], timeout=5)
    ok_mag, mag_out = adb.run(["shell", "settings", "get", "secure", "accessibility_display_magnification_enabled"], timeout=5)
    ok_contrast, contrast_out = adb.run(["shell", "settings", "get", "secure", "high_text_contrast_enabled"], timeout=5)

    touch_exp = "Enabled" if ok_touch and touch_out.strip() == "1" else "Disabled"
    mag_enabled = "Enabled" if ok_mag and mag_out.strip() == "1" else "Disabled"
    high_contrast = "Enabled" if ok_contrast and contrast_out.strip() == "1" else "Disabled"

    print()
    ui.header("Accessibility Settings & Services:")
    acc_data = {
        "Enabled Services": f"{ui.Colors.YELLOW}{enabled_services}{ui.Colors.RESET}",
        "Touch Exploration (TalkBack)": touch_exp,
        "Screen Magnification": mag_enabled,
        "High Text Contrast": high_contrast,
    }
    ui.print_kv(acc_data)

    if ok_dump and dump_out:
        print()
        ui.header("Active Accessibility Connections & Focus:")
        conn_lines = []
        for line in dump_out.splitlines():
            line_s = line.strip()
            if any(k in line_s for k in ["AccessibilityServiceConnection", "mTouchExplorationEnabled", "mIsDefault", "mFocus"]):
                conn_lines.append(line_s)

        if conn_lines:
            for cl in conn_lines[:15]:
                print(f"    {ui.Colors.CYAN}•{ui.Colors.RESET} {cl}")
        else:
            ui.info("No active third-party accessibility bindings.")


def get_current_display_info():
    """Retrieve screen resolution, density, refresh rate, rotation, and display cutouts."""
    if not ensure_device():
        return

    ui.header("Display, Screen & Cutout Information")

    # Resolution & Density
    ok_size, size_out = adb.run(["shell", "wm", "size"], timeout=5)
    ok_density, density_out = adb.run(["shell", "wm", "density"], timeout=5)

    # Display dumpsys
    ok_disp, disp_out = adb.run(["shell", "dumpsys", "display"], timeout=10)

    # Window dumpsys for rotation & cutouts
    ok_win, win_out = adb.run(["shell", "dumpsys", "window", "displays"], timeout=10)

    display_info: Dict[str, str] = {
        "Physical Resolution": "Unknown",
        "Override Resolution": "None",
        "Physical Density (DPI)": "Unknown",
        "Override Density": "None",
        "Refresh Rate": "Unknown",
        "Display State": "Unknown",
        "Current Rotation": "Unknown",
        "Display Cutout (Notch)": "None / Normal",
        "HDR Capabilities": "Unknown",
    }

    if ok_size and size_out:
        m_phys = re.search(r"Physical size:\s*([0-9x]+)", size_out)
        if m_phys:
            display_info["Physical Resolution"] = m_phys.group(1)
        m_over = re.search(r"Override size:\s*([0-9x]+)", size_out)
        if m_over:
            display_info["Override Resolution"] = m_over.group(1)

    if ok_density and density_out:
        m_pd = re.search(r"Physical density:\s*(\d+)", density_out)
        if m_pd:
            dpi_val = int(m_pd.group(1))
            bucket = "mdpi" if dpi_val <= 160 else "hdpi" if dpi_val <= 240 else "xhdpi" if dpi_val <= 320 else "xxhdpi" if dpi_val <= 480 else "xxxhdpi"
            display_info["Physical Density (DPI)"] = f"{dpi_val} ({bucket})"
        m_od = re.search(r"Override density:\s*(\d+)", density_out)
        if m_od:
            display_info["Override Density"] = m_od.group(1)

    if ok_disp and disp_out:
        m_fps = re.search(r"fps=([\d.]+)|refreshRate=([\d.]+)", disp_out)
        if m_fps:
            fps_val = m_fps.group(1) or m_fps.group(2)
            display_info["Refresh Rate"] = f"{fps_val} Hz"

        m_state = re.search(r"mState=(\w+)|state=(\w+)", disp_out)
        if m_state:
            display_info["Display State"] = m_state.group(1) or m_state.group(2)

        m_hdr = re.search(r"HdrCapabilities\{([^\}]+)\}", disp_out)
        if m_hdr:
            display_info["HDR Capabilities"] = m_hdr.group(1)

    if ok_win and win_out:
        m_rot = re.search(r"mCurrentRotation=(\w+|\d+)|init=(\d+)\s+([0-9x]+)\s+(\d+)dpi", win_out)
        if m_rot and m_rot.group(1):
            rot_map = {"0": "ROTATION_0 (Portrait)", "1": "ROTATION_90 (Landscape)", "2": "ROTATION_180 (Reverse Portrait)", "3": "ROTATION_270 (Reverse Landscape)"}
            display_info["Current Rotation"] = rot_map.get(m_rot.group(1), m_rot.group(1))

        # Check cutout
        m_cutout = re.search(r"DisplayCutout\{([^\}]+)\}", win_out)
        if m_cutout:
            display_info["Display Cutout (Notch)"] = m_cutout.group(1)

    print()
    ui.print_kv(display_info)


def view_intent_filters_for_current_app():
    """Extract and display exported activities, services, receivers and their intent filters."""
    if not ensure_device():
        return

    pkg, _ = _get_current_focus_raw()
    if not pkg:
        pkg = ui.get_choice("Enter package name to inspect")
        if not pkg:
            return

    ui.header(f"Intent Filters & Manifest Components: {pkg}")
    ui.info(f"Dumping package components for {pkg}...")

    ok, out = adb.run(["shell", "dumpsys", "package", pkg], timeout=15)
    if not ok or not out:
        ui.error("Failed to query package manager.")
        return

    # Extract Activity Intent Filters
    activities_filters: List[Dict[str, Any]] = []
    in_activities_section = False
    curr_activity = ""
    curr_filter: Dict[str, Any] = {"actions": [], "categories": [], "schemes": []}

    for line in out.splitlines():
        line_s = line.strip()
        if "Activity Resolver Table:" in line_s:
            in_activities_section = True
            continue
        elif in_activities_section and ("Receiver Resolver Table:" in line_s or "Service Resolver Table:" in line_s or "Provider Resolver Table:" in line_s):
            in_activities_section = False
            continue

        if in_activities_section:
            # Activity Component
            act_match = re.search(r"([a-f0-9]+)\s+([^/\s]+)/([^/\s]+)\s+filter\s+([a-f0-9]+)", line_s)
            if act_match:
                comp_act = act_match.group(3)
                curr_activity = comp_act
                curr_filter = {"activity": comp_act, "actions": [], "categories": [], "schemes": []}
                activities_filters.append(curr_filter)
                continue

            if "Action:" in line_s:
                act_name = line_s.replace("Action:", "").strip().replace('"', '')
                if curr_filter and act_name not in curr_filter["actions"]:
                    curr_filter["actions"].append(act_name)

            if "Category:" in line_s:
                cat_name = line_s.replace("Category:", "").strip().replace('"', '')
                if curr_filter and cat_name not in curr_filter["categories"]:
                    curr_filter["categories"].append(cat_name)

            if "Scheme:" in line_s:
                scheme_name = line_s.replace("Scheme:", "").strip().replace('"', '')
                if curr_filter and scheme_name not in curr_filter["schemes"]:
                    curr_filter["schemes"].append(scheme_name)

    if not activities_filters:
        ui.warning(f"No public intent filter entries resolved for {pkg}.")
        return

    ui.success(f"Found {len(activities_filters)} activity intent-filter mappings:")
    print()

    for idx, item in enumerate(activities_filters[:20], 1):
        act_short = item["activity"].split(".")[-1]
        print(f"  {ui.Colors.BOLD}{ui.Colors.CYAN}[{idx}] {act_short}{ui.Colors.RESET} ({item['activity']})")
        if item["actions"]:
            print(f"      {ui.Colors.GREEN}Actions:{ui.Colors.RESET} {', '.join(item['actions'][:4])}")
        if item["categories"]:
            print(f"      {ui.Colors.YELLOW}Categories:{ui.Colors.RESET} {', '.join(item['categories'][:4])}")
        if item["schemes"]:
            print(f"      {ui.Colors.MAGENTA}Schemes (Deep Links):{ui.Colors.RESET} {', '.join(item['schemes'])}")
        print()


def window_manager_info():
    """Retrieve full WindowManager policy, keyguard state, and system bar policy."""
    if not ensure_device():
        return

    ui.header("WindowManager & System UI Policy")
    ok, out = adb.run(["shell", "dumpsys", "window", "policy"], timeout=10)
    if not ok or not out:
        ok, out = adb.run(["shell", "dumpsys", "window"], timeout=10)

    if not ok or not out:
        ui.error("Failed to query window manager policy.")
        return

    # Extract Keyguard state
    m_keyguard = re.search(r"mKeyguardShowing=(\w+)|keyguardShowing=(\w+)", out)
    keyguard_state = (m_keyguard.group(1) or m_keyguard.group(2)) if m_keyguard else "Unknown"

    # Screen state
    m_screen_on = re.search(r"mScreenOnFully=(\w+)|screenOnEarly=(\w+)", out)
    screen_on = (m_screen_on.group(1) or m_screen_on.group(2)) if m_screen_on else "Unknown"

    # Orientation listener
    m_orient = re.search(r"mOrientationListenerAvailable=(\w+)", out)
    orient_listener = m_orient.group(1) if m_orient else "Unknown"

    # Status Bar / Nav Bar visibility
    m_sb = re.search(r"mStatusBar=Window\{[^\}]*\s+u0\s+([^\}]+)\}", out)
    status_bar_win = m_sb.group(1) if m_sb else "System Default"

    m_nb = re.search(r"mNavigationBar=Window\{[^\}]*\s+u0\s+([^\}]+)\}", out)
    nav_bar_win = m_nb.group(1) if m_nb else "Gesture / Default"

    # Current IME target
    m_ime = re.search(r"mInputMethodTarget=Window\{[^\}]*\s+u0\s+([^\}]+)\}", out)
    ime_target = m_ime.group(1) if m_ime else "None"

    policy_info = {
        "Keyguard (Lockscreen) Showing": keyguard_state,
        "Screen Fully On": screen_on,
        "Orientation Sensor Available": orient_listener,
        "Status Bar Window": status_bar_win,
        "Navigation Bar Window": nav_bar_win,
        "Input Method (IME) Target": ime_target,
    }

    print()
    ui.print_kv(policy_info)


# ─── Public Entry Menu ────────────────────────────────────────────────────────

def ui_inspector_menu():
    """Main menu loop for the UI & Hierarchy Inspector module."""
    while True:
        ui.clear()
        ui.print_banner()
        ui.print_sub_banner("UI & Hierarchy Inspector", "🔍")
        ui.print_device_status(adb.serial)

        options = [
            "Dump UI Hierarchy (XML) & Element Tree",
            "Get Current Activity & Task Info",
            "Get Current Fragment(s)",
            "List Recent Activities (Task Stack)",
            "Get Focused Window Technical Info",
            "List All Active Windows & Overlays",
            "View Content Providers of Current App",
            "View Running Services",
            "Dump Accessibility Subsystem Info",
            "Get Display & Cutout Info",
            "View Intent Filters for Current App",
            "WindowManager & System UI Policy",
        ]

        ui.print_menu("UI Inspector Menu", options, columns=2)
        choice = ui.get_choice("Select option")

        if choice == "0":
            break
        elif choice == "1":
            dump_ui_hierarchy()
            ui.pause()
        elif choice == "2":
            get_current_activity_name()
            ui.pause()
        elif choice == "3":
            get_current_fragments()
            ui.pause()
        elif choice == "4":
            list_recent_activities()
            ui.pause()
        elif choice == "5":
            get_focused_window_info()
            ui.pause()
        elif choice == "6":
            list_all_windows()
            ui.pause()
        elif choice == "7":
            view_current_content_providers()
            ui.pause()
        elif choice == "8":
            view_running_services()
            ui.pause()
        elif choice == "9":
            dump_accessibility_info()
            ui.pause()
        elif choice == "10":
            get_current_display_info()
            ui.pause()
        elif choice == "11":
            view_intent_filters_for_current_app()
            ui.pause()
        elif choice == "12":
            window_manager_info()
            ui.pause()
        else:
            ui.error("Invalid option. Please choose a valid number.")
            ui.pause()
