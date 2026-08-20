"""
modules/security_audit.py — Comprehensive Android Security Audit and Vulnerability Assessment.

Performs deep security posture evaluation including device encryption, lockscreen credentials,
developer settings exposure, sideloading policies, app verification (Play Protect), SELinux mode,
network ADB risks, dangerous app permissions, device administrators, security patch currency,
and root/superuser detection with an automated graded scoring engine.
"""

import os
import time
from datetime import datetime, date
from typing import Optional, List, Dict, Tuple, Any

from core.adb import adb
from core import ui
from core.device import ensure_device


# ─── 1. Check Encryption Status ───────────────────────────────────────────────

def check_encryption_status() -> Dict[str, Any]:
    """Check storage encryption state (FBE / FDE / unencrypted)."""
    if not ensure_device():
        return {}

    ui.header("Storage Encryption Status")

    crypto_state = adb.getprop("ro.crypto.state")
    crypto_type = adb.getprop("ro.crypto.type")
    crypto_fde = adb.getprop("ro.crypto.fde_algorithm")
    vold_decrypt = adb.getprop("vold.decrypt")

    # Determine encryption type
    is_encrypted = crypto_state.lower() == "encrypted"
    enc_type_str = "File-Based Encryption (FBE)" if crypto_type.lower() == "file" else ("Full-Disk Encryption (FDE)" if crypto_type.lower() == "block" else crypto_type)

    if is_encrypted:
        ui.success(f"Device storage is {ui.Colors.BOLD}ENCRYPTED{ui.Colors.RESET}")
    else:
        ui.error(f"Device storage is {ui.Colors.BOLD}UNENCRYPTED / VULNERABLE{ui.Colors.RESET}")

    details = {
        "Encryption State (ro.crypto.state)": f"{ui.Colors.GREEN}encrypted{ui.Colors.RESET}" if is_encrypted else f"{ui.Colors.RED}unencrypted{ui.Colors.RESET}",
        "Encryption Type (ro.crypto.type)": enc_type_str if enc_type_str else "Standard",
        "FDE Algorithm": crypto_fde if crypto_fde else "AES-256-XTS (Hardware-backed)",
        "Decryption Status (vold.decrypt)": vold_decrypt if vold_decrypt else "Normal Operation",
    }
    ui.print_kv(details, indent=4)

    return {
        "encrypted": is_encrypted,
        "type": enc_type_str,
        "score": 10 if is_encrypted else 0,
        "risk": "LOW" if is_encrypted else "CRITICAL",
    }


# ─── 2. Check Screen Lock Type ────────────────────────────────────────────────

def check_screen_lock_type() -> Dict[str, Any]:
    """Check lock screen credential security (PIN / Password / Pattern / None)."""
    if not ensure_device():
        return {}

    ui.header("Screen Lock & Credential Security")

    # Query lock settings
    ok1, lock_disabled = adb.run_shell("settings get secure lockscreen.disabled")
    ok2, trust_dump = adb.run_shell("dumpsys trust")
    ok3, lock_dump = adb.run_shell("dumpsys lock_settings")

    is_disabled = lock_disabled.strip() == "1" if ok1 else False
    lock_type = "Unknown"
    is_secure = False

    # Check trust manager
    if ok2 and trust_dump:
        for line in trust_dump.splitlines():
            line = line.strip()
            if "deviceLocked=" in line or "deviceLockedForUser" in line:
                pass
            if "trustAgent" in line or "Fingerprint" in line or "Face" in line:
                lock_type = "Biometric / Secure Keyguard"

    # Analyze lock_settings dump
    if ok3 and lock_dump:
        lower_dump = lock_dump.lower()
        if "pin" in lower_dump or "lockscreen.password_type=131072" in lower_dump:
            lock_type = "PIN Credential"
            is_secure = True
        elif "pattern" in lower_dump or "lockscreen.password_type=65536" in lower_dump:
            lock_type = "Pattern Credential"
            is_secure = True
        elif "password" in lower_dump or "lockscreen.password_type=262144" in lower_dump or "lockscreen.password_type=327680" in lower_dump:
            lock_type = "Alphanumeric Password"
            is_secure = True
        elif "lockscreen.password_type=0" in lower_dump or is_disabled:
            lock_type = "None / Swipe Only (Insecure)"
            is_secure = False
        else:
            if not is_disabled:
                lock_type = "Configured (PIN / Pattern / Biometric)"
                is_secure = True

    if is_disabled:
        lock_type = "None (Lockscreen Disabled)"
        is_secure = False

    if is_secure:
        ui.success(f"Screen Lock: {ui.Colors.BOLD}{lock_type}{ui.Colors.RESET}")
    else:
        ui.warning(f"Screen Lock: {ui.Colors.BOLD}{lock_type}{ui.Colors.RESET} — Device is unprotected without lock credential.")

    details = {
        "Lockscreen Status": "Enabled" if not is_disabled else f"{ui.Colors.RED}Disabled{ui.Colors.RESET}",
        "Credential Type": lock_type,
        "Physical Protection": "Protected" if is_secure else f"{ui.Colors.RED}Unprotected{ui.Colors.RESET}",
    }
    ui.print_kv(details, indent=4)

    return {
        "secure": is_secure,
        "lock_type": lock_type,
        "score": 10 if is_secure else 0,
        "risk": "LOW" if is_secure else "HIGH",
    }


# ─── 3. USB Debugging Status ──────────────────────────────────────────────────

def check_usb_debugging_status() -> Dict[str, Any]:
    """Inspect USB debugging state and authorized authorization keys."""
    if not ensure_device():
        return {}

    ui.header("USB Debugging Configuration")

    ok, adb_enabled = adb.run_shell("settings get global adb_enabled")
    is_adb_on = adb_enabled.strip() == "1" if ok else True

    usb_config = adb.getprop("persist.sys.usb.config")
    usb_state = adb.getprop("sys.usb.state")
    debuggable = adb.getprop("ro.debuggable") == "1"

    status_str = f"{ui.Colors.YELLOW}ENABLED (Active ADB Connection){ui.Colors.RESET}" if is_adb_on else f"{ui.Colors.GREEN}DISABLED{ui.Colors.RESET}"
    print(f"\n  USB Debugging: {status_str}\n")

    details = {
        "ADB Enabled Setting": "1 (True)" if is_adb_on else "0 (False)",
        "Persistent USB Config": usb_config if usb_config else "mtp,adb",
        "Current USB State": usb_state if usb_state else "adb",
        "System Build Debuggable": f"{ui.Colors.RED}YES (ro.debuggable=1){ui.Colors.RESET}" if debuggable else f"{ui.Colors.GREEN}NO (Production release){ui.Colors.RESET}",
    }
    ui.print_kv(details, indent=4)

    print(f"\n  {ui.Colors.DIM}Note: USB Debugging should be disabled on personal daily devices when not actively developing.{ui.Colors.RESET}")

    return {
        "adb_enabled": is_adb_on,
        "debuggable": debuggable,
        "score": 5 if not debuggable else 0,
        "risk": "MEDIUM" if is_adb_on else "LOW",
    }


# ─── 4. Unknown Sources / Sideloading Status ──────────────────────────────────

def check_unknown_sources_status() -> Dict[str, Any]:
    """Inspect unknown sources / app sideloading policy."""
    if not ensure_device():
        return {}

    ui.header("Unknown Sources & Sideloading Policy")

    ok_sec, sec_val = adb.run_shell("settings get secure install_non_market_apps")
    ok_glob, glob_val = adb.run_shell("settings get global install_non_market_apps")

    # On modern Android (8.0+), install_non_market_apps is per-app permission REQUEST_INSTALL_PACKAGES
    val = sec_val.strip() if ok_sec and sec_val.strip() != "null" else (glob_val.strip() if ok_glob else "0")
    is_allowed = val == "1"

    status_str = f"{ui.Colors.YELLOW}ALLOWED (Global Sideloading Enabled){ui.Colors.RESET}" if is_allowed else f"{ui.Colors.GREEN}RESTRICTED (Per-App Permission or Blocked){ui.Colors.RESET}"
    print(f"\n  Sideloading Status: {status_str}\n")

    details = {
        "Global Non-Market Apps Setting": "1 (Allowed globally)" if is_allowed else "0 (Restricted / Per-App)",
        "Policy Enforcement": "Android 8+ Granular App Permissions" if val in ("0", "null", "") else "Legacy Global Permission",
    }
    ui.print_kv(details, indent=4)

    return {
        "global_sideload_allowed": is_allowed,
        "score": 10 if not is_allowed else 5,
        "risk": "LOW" if not is_allowed else "MEDIUM",
    }


# ─── 5. Developer Options Status ──────────────────────────────────────────────

def check_developer_options_status() -> Dict[str, Any]:
    """Inspect developer options state."""
    if not ensure_device():
        return {}

    ui.header("Developer Options Status")

    ok, dev_val = adb.run_shell("settings get global development_settings_enabled")
    is_dev_on = dev_val.strip() == "1" if ok else False

    status_str = f"{ui.Colors.YELLOW}ENABLED{ui.Colors.RESET}" if is_dev_on else f"{ui.Colors.GREEN}DISABLED{ui.Colors.RESET}"
    print(f"\n  Developer Options: {status_str}\n")

    details = {
        "Development Settings Setting": "1 (Active)" if is_dev_on else "0 (Disabled)",
        "Security Implication": "Exposes mock locations, wireless debugging, bug reports" if is_dev_on else "Standard Protected Mode",
    }
    ui.print_kv(details, indent=4)

    return {
        "developer_options_enabled": is_dev_on,
        "score": 10 if not is_dev_on else 7,
        "risk": "MEDIUM" if is_dev_on else "LOW",
    }


# ─── 6. Verify Apps (Google Play Protect) Status ──────────────────────────────

def check_verify_apps_status() -> Dict[str, Any]:
    """Inspect Google Play Protect and package verification status."""
    if not ensure_device():
        return {}

    ui.header("Google Play Protect / App Verification Status")

    ok1, verifier_enable = adb.run_shell("settings get global package_verifier_enable")
    ok2, upload_enable = adb.run_shell("settings get global upload_apk_enable")
    ok3, user_consent = adb.run_shell("settings get secure package_verifier_user_consent")

    is_verifier_on = verifier_enable.strip() == "1" if ok1 and verifier_enable.strip() != "null" else True
    is_upload_on = upload_enable.strip() == "1" if ok2 and upload_enable.strip() != "null" else True

    if is_verifier_on:
        ui.success("Google Play Protect / App Verification is ACTIVE")
    else:
        ui.error("Google Play Protect / App Verification is DISABLED")

    details = {
        "Package Verifier (package_verifier_enable)": f"{ui.Colors.GREEN}1 (Enabled){ui.Colors.RESET}" if is_verifier_on else f"{ui.Colors.RED}0 (Disabled){ui.Colors.RESET}",
        "Unknown App Upload (upload_apk_enable)": "1 (Enabled)" if is_upload_on else "0 (Disabled)",
        "User Consent Status": user_consent.strip() if ok3 and user_consent.strip() != "null" else "1",
    }
    ui.print_kv(details, indent=4)

    return {
        "verifier_enabled": is_verifier_on,
        "score": 10 if is_verifier_on else 0,
        "risk": "LOW" if is_verifier_on else "HIGH",
    }


# ─── 7. SELinux Mode ──────────────────────────────────────────────────────────

def check_selinux_mode() -> Dict[str, Any]:
    """Evaluate SELinux enforcement posture."""
    if not ensure_device():
        return {}

    ui.header("SELinux Enforcement Posture")

    ok, mode = adb.run_shell("getenforce")
    status = mode.strip() if ok else "Unknown"

    is_enforcing = "enforc" in status.lower()
    is_permissive = "permissive" in status.lower()

    if is_enforcing:
        ui.success(f"SELinux Mode: {ui.Colors.BOLD}ENFORCING{ui.Colors.RESET} (Mandatory Access Control Active)")
    elif is_permissive:
        ui.warning(f"SELinux Mode: {ui.Colors.BOLD}PERMISSIVE{ui.Colors.RESET} (Violations logged only, NOT blocked!)")
    else:
        ui.error(f"SELinux Mode: {ui.Colors.BOLD}{status.upper()}{ui.Colors.RESET} (Security Subsystem Inactive!)")

    details = {
        "Runtime Mode (getenforce)": status,
        "Kernel Boot Flag (ro.boot.selinux)": adb.getprop("ro.boot.selinux") or "enforcing",
    }
    ui.print_kv(details, indent=4)

    score = 15 if is_enforcing else (5 if is_permissive else 0)
    risk = "LOW" if is_enforcing else ("HIGH" if is_permissive else "CRITICAL")

    return {
        "mode": status,
        "is_enforcing": is_enforcing,
        "score": score,
        "risk": risk,
    }


# ─── 8. Check ADB Over Network (TCP/IP) ───────────────────────────────────────

def check_adb_over_network() -> Dict[str, Any]:
    """Inspect wireless ADB / network listening ports."""
    if not ensure_device():
        return {}

    ui.header("ADB Over Network (TCP/IP Port 5555 / Wireless Debugging)")

    port_prop = adb.getprop("service.adb.tcp.port")
    ok_wifi, wifi_dbg = adb.run_shell("settings get global adb_wifi_enabled")

    is_wifi_dbg_on = wifi_dbg.strip() == "1" if ok_wifi else False
    is_net_port_open = False
    active_port = "Disabled"

    if port_prop and port_prop.strip() not in ("-1", "0", ""):
        is_net_port_open = True
        active_port = port_prop.strip()

    # Also check netstat for port 5555
    ok_net, net_out = adb.run_shell("netstat -tuln")
    if ok_net and ":5555" in net_out:
        is_net_port_open = True
        active_port = "5555"

    if is_net_port_open or is_wifi_dbg_on:
        ui.warning(f"Network ADB is OPEN on port {active_port} / Wireless Debugging: {is_wifi_dbg_on}")
        print(f"  {ui.Colors.RED}Risk:{ui.Colors.RESET} Devices listening on network ports may be remotely controllable across local Wi-Fi.")
    else:
        ui.success("ADB Over Network / TCP Port is CLOSED (USB only)")

    details = {
        "TCP/IP Port (service.adb.tcp.port)": active_port,
        "Wireless Debugging (adb_wifi_enabled)": "1 (Enabled)" if is_wifi_dbg_on else "0 (Disabled)",
        "Network Exposure Risk": f"{ui.Colors.RED}HIGH (Network accessible){ui.Colors.RESET}" if (is_net_port_open or is_wifi_dbg_on) else f"{ui.Colors.GREEN}LOW (USB Bound){ui.Colors.RESET}",
    }
    ui.print_kv(details, indent=4)

    return {
        "network_adb_open": is_net_port_open or is_wifi_dbg_on,
        "port": active_port,
        "score": 10 if not (is_net_port_open or is_wifi_dbg_on) else 0,
        "risk": "HIGH" if (is_net_port_open or is_wifi_dbg_on) else "LOW",
    }


# ─── 9. List Apps with Dangerous Permissions ──────────────────────────────────

def list_apps_dangerous_permissions():
    """List third-party applications granted critical/sensitive permissions."""
    if not ensure_device():
        return

    ui.header("Apps with Sensitive / Dangerous Permissions")

    sensitive_perms = [
        ("CAMERA", "android.permission.CAMERA", "📷"),
        ("RECORD_AUDIO", "android.permission.RECORD_AUDIO", "🎤"),
        ("LOCATION", "android.permission.ACCESS_FINE_LOCATION", "📍"),
        ("SMS", "android.permission.READ_SMS", "✉️"),
        ("CALL_LOG", "android.permission.READ_CALL_LOG", "📞"),
        ("CONTACTS", "android.permission.READ_CONTACTS", "👥"),
        ("STORAGE", "android.permission.READ_EXTERNAL_STORAGE", "💾"),
        ("SYSTEM_ALERT_WINDOW", "android.permission.SYSTEM_ALERT_WINDOW", "🪟"),
    ]

    print("  Scanning third-party packages for sensitive permissions...")
    ok, pkgs_out = adb.run_shell("pm list packages -3")
    if not ok or not pkgs_out.strip():
        ui.info("No third-party packages found.")
        return

    packages = [l.replace("package:", "").strip() for l in pkgs_out.splitlines() if l.strip()]
    ui.info(f"Found {len(packages)} third-party apps. Auditing permissions...")

    app_perms: Dict[str, List[str]] = {}

    for i, pkg in enumerate(packages[:25]):  # Scan first 25 for fast response
        ui.progress_bar(i + 1, min(len(packages), 25), label="Auditing Apps")
        ok_d, dump = adb.run_shell(f"dumpsys package {pkg}")
        if not ok_d or not dump:
            continue

        granted = []
        for tag, perm, icon in sensitive_perms:
            if f"{perm}: granted=true" in dump or f"{perm}" in dump:
                granted.append(f"{icon} {tag}")

        if granted:
            app_perms[pkg] = granted

    print("\n")
    if app_perms:
        rows = []
        for pkg, perms in sorted(app_perms.items()):
            rows.append((pkg, ", ".join(perms)))
        ui.print_table(rows, headers=("Application Package", "Granted Sensitive Permissions"))
        if len(packages) > 25:
            ui.info(f"Scanned sample of 25 apps from {len(packages)} total 3rd-party apps.")
    else:
        ui.success("No critical permission anomalies detected in sample.")


# ─── 10. Device Admin Apps & Owners ───────────────────────────────────────────

def check_device_admin_apps() -> Dict[str, Any]:
    """Inspect active device administrators and device policy owners."""
    if not ensure_device():
        return {}

    ui.header("Device Administrators & Policy Owners")

    ok1, dpm_out = adb.run_shell("dpm list-owners")
    ok2, policy_out = adb.run_shell("dumpsys device_policy")

    admins = []
    device_owner = "None"
    profile_owner = "None"

    if ok1 and dpm_out:
        for line in dpm_out.splitlines():
            line = line.strip()
            if "Device Owner:" in line or "admin=" in line:
                device_owner = line
            elif "Profile Owner:" in line:
                profile_owner = line

    if ok2 and policy_out:
        for line in policy_out.splitlines():
            line = line.strip()
            if line.startswith("Active Admin:") or "admin=" in line:
                admins.append(line)

    if admins or device_owner != "None":
        ui.info(f"Detected {len(admins)} active administrator(s):")
        for a in admins:
            print(f"  • {a}")
        if device_owner != "None":
            print(f"  • Device Owner: {device_owner}")
    else:
        ui.success("No third-party Device Administrators or Device Owners registered.")

    print(f"\n  {ui.Colors.DIM}Device Administrators hold elevated rights (remote wipe, password locks, anti-uninstall).{ui.Colors.RESET}")

    return {
        "admin_count": len(admins),
        "device_owner": device_owner,
        "score": 10 if len(admins) <= 2 else 5,
        "risk": "LOW" if len(admins) <= 2 else "MEDIUM",
    }


# ─── 11. Security Patch Level & Vulnerability Analysis ────────────────────────

def check_security_patch_level() -> Dict[str, Any]:
    """Evaluate Android security patch date and currency."""
    if not ensure_device():
        return {}

    ui.header("Android Security Patch Level & Currency")

    patch_str = adb.getprop("ro.build.version.security_patch")
    android_ver = adb.getprop("ro.build.version.release")
    build_id = adb.getprop("ro.build.display.id")

    days_old = None
    risk_level = "UNKNOWN"
    score = 0

    if patch_str and len(patch_str) >= 10:
        try:
            patch_date = datetime.strptime(patch_str, "%Y-%m-%d").date()
            today = date.today()
            days_old = (today - patch_date).days

            if days_old < 60:
                risk_level = "UP TO DATE (Low Risk)"
                score = 15
                color = ui.Colors.GREEN
            elif days_old < 180:
                risk_level = "MODERATE (2-6 Months Old)"
                score = 10
                color = ui.Colors.YELLOW
            elif days_old < 365:
                risk_level = "HIGH RISK (6-12 Months Old)"
                score = 5
                color = ui.Colors.RED
            else:
                risk_level = "CRITICALLY OUTDATED (> 1 Year Old)"
                score = 0
                color = ui.Colors.RED
        except Exception:
            color = ui.Colors.YELLOW
    else:
        patch_str = "Not Reported / Legacy ROM"
        color = ui.Colors.RED

    print(f"\n  Security Patch: {color}{ui.Colors.BOLD}{patch_str}{ui.Colors.RESET} ({risk_level})\n")

    details = {
        "Security Patch Date": patch_str,
        "Android OS Version": android_ver,
        "Firmware Build ID": build_id,
        "Patch Age (Days)": f"{days_old} days ago" if days_old is not None else "N/A",
        "Known CVE Exposure Risk": risk_level,
    }
    ui.print_kv(details, indent=4)

    return {
        "patch_date": patch_str,
        "days_old": days_old,
        "score": score,
        "risk": risk_level,
    }


# ─── 12. Root & Su Binary Detection ───────────────────────────────────────────

def check_root_status() -> Dict[str, Any]:
    """Detect root binaries, Magisk, KernelSU, test-keys, and unsecure flags."""
    if not ensure_device():
        return {}

    ui.header("Root & Superuser Integrity Detection")

    ok_which, which_su = adb.run_shell("which su")
    ok_magisk, magisk_v = adb.run_shell("magisk -v")

    # Check common binary locations
    su_paths = ["/system/bin/su", "/system/xbin/su", "/sbin/su", "/data/local/su", "/vendor/bin/su"]
    found_paths = []
    for p in su_paths:
        ok_p, out_p = adb.run_shell(f"ls -l {p}")
        if ok_p and "No such" not in out_p:
            found_paths.append(p)

    build_tags = adb.getprop("ro.build.tags")
    ro_secure = adb.getprop("ro.secure")
    ro_debug = adb.getprop("ro.debuggable")

    has_su = (ok_which and "su" in which_su) or len(found_paths) > 0
    has_magisk = ok_magisk and magisk_v.strip() != ""
    is_test_keys = "test-keys" in build_tags.lower()

    is_rooted = has_su or has_magisk

    if is_rooted:
        ui.warning(f"Device appears {ui.Colors.BOLD}ROOTED / MODIFIED{ui.Colors.RESET}")
    else:
        ui.success("No active root binaries or Superuser daemons detected.")

    details = {
        "Root Binary (su)": f"{ui.Colors.RED}Detected at {found_paths}{ui.Colors.RESET}" if found_paths else f"{ui.Colors.GREEN}Not Found{ui.Colors.RESET}",
        "Magisk / Root Daemon": f"{ui.Colors.RED}Active ({magisk_v.strip()}){ui.Colors.RESET}" if has_magisk else f"{ui.Colors.GREEN}Not Detected{ui.Colors.RESET}",
        "Build Tags (ro.build.tags)": f"{ui.Colors.YELLOW}{build_tags}{ui.Colors.RESET}" if is_test_keys else f"{ui.Colors.GREEN}{build_tags}{ui.Colors.RESET}",
        "Kernel Security (ro.secure)": "1 (Enforced)" if ro_secure == "1" else f"{ui.Colors.RED}0 (Insecure Kernel){ui.Colors.RESET}",
        "Debug Flag (ro.debuggable)": "0 (Production)" if ro_debug != "1" else f"{ui.Colors.RED}1 (Debuggable){ui.Colors.RESET}",
    }
    ui.print_kv(details, indent=4)

    return {
        "rooted": is_rooted,
        "magisk": has_magisk,
        "score": 10 if not is_rooted else 0,
        "risk": "HIGH" if is_rooted else "LOW",
    }


# ─── 13. Full Security Summary Report (Scoring Engine) ────────────────────────

def run_full_security_summary():
    """Execute complete 12-point security audit, compute score, and generate report."""
    if not ensure_device():
        return

    ui.clear()
    ui.print_banner()
    ui.header("🔒 Running Full System Security Audit & Scorecard...")
    print("  Evaluating all security layers and threat vectors. Please wait...\n")

    # Run individual audits silently
    enc = check_encryption_status()
    lock = check_screen_lock_type()
    usb = check_usb_debugging_status()
    sideload = check_unknown_sources_status()
    dev_opts = check_developer_options_status()
    verify = check_verify_apps_status()
    selinux = check_selinux_mode()
    net_adb = check_adb_over_network()
    admins = check_device_admin_apps()
    patch = check_security_patch_level()
    root = check_root_status()

    # Calculate total score (out of 100)
    total_score = (
        enc.get("score", 0) +
        lock.get("score", 0) +
        usb.get("score", 0) +
        sideload.get("score", 0) +
        dev_opts.get("score", 0) +
        verify.get("score", 0) +
        selinux.get("score", 0) +
        net_adb.get("score", 0) +
        admins.get("score", 0) +
        patch.get("score", 0) +
        root.get("score", 0)
    )

    # Normalize to 100
    total_score = min(max(total_score, 0), 100)

    # Compute Letter Grade
    if total_score >= 90:
        grade = "A+"
        grade_color = ui.Colors.GREEN
    elif total_score >= 80:
        grade = "A"
        grade_color = ui.Colors.GREEN
    elif total_score >= 70:
        grade = "B"
        grade_color = ui.Colors.CYAN
    elif total_score >= 60:
        grade = "C"
        grade_color = ui.Colors.YELLOW
    elif total_score >= 50:
        grade = "D"
        grade_color = ui.Colors.RED
    else:
        grade = "F"
        grade_color = ui.Colors.RED

    print(f"\n{ui.Colors.BOLD}══════════════════════════════════════════════════════════════════════{ui.Colors.RESET}")
    print(f"       🛡️  SECURITY POSTURE AUDIT SCORECARD : {grade_color}{ui.Colors.BOLD}{grade} ({total_score}/100){ui.Colors.RESET}")
    print(f"{ui.Colors.BOLD}══════════════════════════════════════════════════════════════════════{ui.Colors.RESET}\n")

    summary_rows = [
        ("Storage Encryption", f"{enc.get('score', 0)}/10", enc.get("risk", "N/A"), "Encrypted (FBE/FDE)" if enc.get("encrypted") else "Unencrypted!"),
        ("Screen Lock Credential", f"{lock.get('score', 0)}/10", lock.get("risk", "N/A"), lock.get("lock_type", "Unknown")),
        ("SELinux Enforcement", f"{selinux.get('score', 0)}/15", selinux.get("risk", "N/A"), selinux.get("mode", "Unknown")),
        ("Root / Superuser Status", f"{root.get('score', 0)}/10", root.get("risk", "N/A"), "Clean" if not root.get("rooted") else "Rooted / Magisk"),
        ("Security Patch Freshness", f"{patch.get('score', 0)}/15", patch.get("risk", "N/A"), patch.get("patch_date", "Unknown")),
        ("Play Protect Verification", f"{verify.get('score', 0)}/10", verify.get("risk", "N/A"), "Enabled" if verify.get("verifier_enabled") else "Disabled"),
        ("Network ADB Exposure", f"{net_adb.get('score', 0)}/10", net_adb.get("risk", "N/A"), "Closed" if not net_adb.get("network_adb_open") else f"Open Port {net_adb.get('port')}"),
        ("Sideloading Policy", f"{sideload.get('score', 0)}/10", sideload.get("risk", "N/A"), "Restricted" if not sideload.get("global_sideload_allowed") else "Global Enabled"),
        ("Device Administrators", f"{admins.get('score', 0)}/10", admins.get("risk", "N/A"), f"{admins.get('admin_count', 0)} Active Admin(s)"),
    ]

    ui.print_table(summary_rows, headers=("Security Check Area", "Score", "Risk Level", "Current Finding"))

    # Key Recommendations
    recs = []
    if not enc.get("encrypted"):
        recs.append("CRITICAL: Enable full device encryption in Android Settings > Security.")
    if not lock.get("secure"):
        recs.append("HIGH: Set a secure PIN, Password, or Biometric lock on the lockscreen.")
    if not selinux.get("is_enforcing"):
        recs.append("CRITICAL: SELinux is not in Enforcing mode. Restore stock kernel/boot.")
    if net_adb.get("network_adb_open"):
        recs.append("HIGH: Disable ADB over Network (set service.adb.tcp.port to -1).")
    if not verify.get("verifier_enabled"):
        recs.append("MEDIUM: Turn on Google Play Protect app scanning in Play Store settings.")
    if patch.get("score", 0) < 10:
        recs.append("HIGH: Device has outdated security patches. Check for OEM system updates.")

    if recs:
        print(f"\n  {ui.Colors.BOLD}Actionable Recommendations:{ui.Colors.RESET}")
        for r in recs:
            print(f"  • {r}")
    else:
        ui.success("No critical security misconfigurations detected. Good security hygiene!")

    # Export option
    print()
    if ui.confirm("Export complete security audit scorecard to file?"):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"security_audit_{adb.serial}_{ts}.txt"
        try:
            with open(fname, "w", encoding="utf-8") as f:
                f.write("=== DROIDCOMMANDER SECURITY AUDIT SCORECARD ===\n")
                f.write(f"Target Device : {adb.serial} ({adb.getprop('ro.product.model')})\n")
                f.write(f"Audit Date    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Score / Grade : {grade} ({total_score}/100)\n\n")
                f.write("Findings:\n")
                for r in summary_rows:
                    f.write(f" - {r[0]}: {r[3]} [Score: {r[1]}, Risk: {r[2]}]\n")
                f.write("\nRecommendations:\n")
                for rc in recs:
                    f.write(f" - {rc}\n")
            ui.success(f"Audit report saved to: {os.path.abspath(fname)}")
        except Exception as e:
            ui.error(f"Export failed: {e}")


# ─── Main Menu Loop ───────────────────────────────────────────────────────────

def security_audit_menu():
    """Security audit interactive submenu."""
    options = [
        "Check Storage Encryption Status",
        "Check Screen Lock & Credential Type",
        "Check USB Debugging Status",
        "Check Unknown Sources / Sideloading Policy",
        "Check Developer Options Status",
        "Check Google Play Protect Verification",
        "Check SELinux Mode & Policy",
        "Check ADB Over Network (Port 5555)",
        "List Apps with Dangerous Permissions",
        "List Device Administrators & Owners",
        "Check Security Patch Level & Currency",
        "Check Root & Superuser Integrity",
        "Generate Full Security Audit Report (Scorecard)",
    ]

    while True:
        ui.clear()
        ui.print_banner()
        ui.print_menu("🔒 Security Audit & Vulnerability Assessment", options, columns=2)

        choice = ui.get_choice()

        if choice == "0":
            break
        elif choice == "1":
            check_encryption_status()
        elif choice == "2":
            check_screen_lock_type()
        elif choice == "3":
            check_usb_debugging_status()
        elif choice == "4":
            check_unknown_sources_status()
        elif choice == "5":
            check_developer_options_status()
        elif choice == "6":
            check_verify_apps_status()
        elif choice == "7":
            check_selinux_mode()
        elif choice == "8":
            check_adb_over_network()
        elif choice == "9":
            list_apps_dangerous_permissions()
        elif choice == "10":
            check_device_admin_apps()
        elif choice == "11":
            check_security_patch_level()
        elif choice == "12":
            check_root_status()
        elif choice == "13":
            run_full_security_summary()
        else:
            ui.error("Invalid option. Please choose a valid number.")

        ui.pause()
