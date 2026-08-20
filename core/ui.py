"""
core/ui.py — Terminal UI helpers: colors, menus, banners, prompts.
"""

import os
import sys


# ─── ANSI Colors ──────────────────────────────────────────────────────────────

class Colors:
    """ANSI escape codes for terminal styling."""
    HEADER  = "\033[95m"
    BLUE    = "\033[94m"
    CYAN    = "\033[96m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    MAGENTA = "\033[35m"
    WHITE   = "\033[97m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    UNDERLINE = "\033[4m"
    RESET   = "\033[0m"
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_RED  = "\033[41m"


# ─── Screen ───────────────────────────────────────────────────────────────────

def clear():
    """Clear the terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


# ─── Banner ───────────────────────────────────────────────────────────────────

BANNER = f"""
{Colors.CYAN}{Colors.BOLD}
    ╔══════════════════════════════════════════════════════╗
    ║                                                      ║
    ║       🏥  P H O N E   S U R G E O N  🏥             ║
    ║       ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━               ║
    ║       Advanced Android Debug Bridge Toolkit           ║
    ║       v2.0  •  16 Modules  •  200+ Commands          ║
    ║                                                      ║
    ╚══════════════════════════════════════════════════════╝
{Colors.RESET}"""


def print_banner():
    """Display the main application banner."""
    print(BANNER)


def print_sub_banner(title: str, icon: str = ""):
    """Display a section sub-banner."""
    title_text = f"{icon}  {title}" if icon else title
    width = max(len(title_text) + 6, 44)
    print(f"\n{Colors.CYAN}{Colors.BOLD}")
    print(f"    ┌{'─' * width}┐")
    print(f"    │  {title_text:^{width - 4}}  │")
    print(f"    └{'─' * width}┘")
    print(Colors.RESET)


# ─── Menu ─────────────────────────────────────────────────────────────────────

def print_menu(title: str, options: list[str], columns: int = 1):
    """
    Display a formatted menu.

    Parameters
    ----------
    title : str
        Menu section title.
    options : list[str]
        List of option labels.
    columns : int
        Number of columns for layout (1 or 2).
    """
    print(f"\n  {Colors.BOLD}{Colors.CYAN}── {title} ──{Colors.RESET}\n")

    if columns == 2 and len(options) > 6:
        # Two-column layout
        mid = (len(options) + 1) // 2
        for i in range(mid):
            left_idx = i + 1
            left = f"  {Colors.YELLOW}[{left_idx:>2}]{Colors.RESET} {options[i]}"
            if i + mid < len(options):
                right_idx = i + mid + 1
                right = f"  {Colors.YELLOW}[{right_idx:>2}]{Colors.RESET} {options[i + mid]}"
            else:
                right = ""
            print(f"{left:<45}{right}")
    else:
        for i, option in enumerate(options, 1):
            print(f"  {Colors.YELLOW}[{i:>2}]{Colors.RESET} {option}")

    print(f"\n  {Colors.YELLOW}[ 0]{Colors.RESET} ← Back / Exit\n")


# ─── Prompts ──────────────────────────────────────────────────────────────────

def get_choice(prompt: str = "Select option") -> str:
    """Prompt user for input and return stripped string."""
    try:
        return input(f"  {Colors.GREEN}➤ {prompt}: {Colors.RESET}").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        return "0"


def confirm(prompt: str = "Are you sure?") -> bool:
    """Ask for yes/no confirmation."""
    answer = get_choice(f"{prompt} (y/n)")
    return answer.lower() in ("y", "yes")


def pause():
    """Wait for the user to press Enter."""
    input(f"\n  {Colors.DIM}Press Enter to continue...{Colors.RESET}")


# ─── Messages ─────────────────────────────────────────────────────────────────

def success(msg: str):
    """Print a green success message."""
    print(f"\n  {Colors.GREEN}✓ {msg}{Colors.RESET}")


def error(msg: str):
    """Print a red error message."""
    print(f"\n  {Colors.RED}✗ {msg}{Colors.RESET}")


def info(msg: str):
    """Print a cyan info message."""
    print(f"\n  {Colors.CYAN}ℹ {msg}{Colors.RESET}")


def warning(msg: str):
    """Print a yellow warning message."""
    print(f"\n  {Colors.YELLOW}⚠ {msg}{Colors.RESET}")


def header(msg: str):
    """Print a bold header line."""
    print(f"\n  {Colors.BOLD}{msg}{Colors.RESET}")


# ─── Tables ───────────────────────────────────────────────────────────────────

def print_table(rows: list[tuple], headers: tuple | None = None, indent: int = 4):
    """
    Print a simple ASCII table.

    Parameters
    ----------
    rows : list[tuple]
        Table data rows.
    headers : tuple | None
        Optional column headers.
    indent : int
        Left indentation spaces.
    """
    if not rows and not headers:
        return

    all_rows = ([headers] if headers else []) + rows
    col_widths = [
        max(len(str(row[i])) for row in all_rows)
        for i in range(len(all_rows[0]))
    ]

    pad = " " * indent
    sep = pad + "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"

    if headers:
        print(sep)
        hdr = pad + "|" + "|".join(
            f" {Colors.BOLD}{str(h).ljust(w)}{Colors.RESET} "
            for h, w in zip(headers, col_widths)
        ) + "|"
        print(hdr)

    print(sep)
    for row in rows:
        line = pad + "|" + "|".join(
            f" {str(c).ljust(w)} " for c, w in zip(row, col_widths)
        ) + "|"
        print(line)
    print(sep)


def print_kv(data: dict, indent: int = 4):
    """Print a key-value list with aligned values."""
    if not data:
        return
    max_key = max(len(str(k)) for k in data)
    pad = " " * indent
    for k, v in data.items():
        print(f"{pad}{Colors.CYAN}{str(k).ljust(max_key)}{Colors.RESET}  {v}")


# ─── Progress ─────────────────────────────────────────────────────────────────

def progress_bar(current: int, total: int, width: int = 30, label: str = ""):
    """Print a simple progress bar."""
    pct = current / total if total > 0 else 0
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    pct_str = f"{pct * 100:5.1f}%"
    text = f"  {label} [{Colors.GREEN}{bar}{Colors.RESET}] {pct_str}"
    print(f"\r{text}", end="", flush=True)
    if current >= total:
        print()


# ─── Device status line ──────────────────────────────────────────────────────

def print_device_status(serial: str | None, model: str = ""):
    """Show the currently active device in the header area."""
    if serial:
        dev = f"{serial}"
        if model:
            dev += f" ({model})"
        print(f"  {Colors.DIM}🔌 Active device: {Colors.GREEN}{dev}{Colors.RESET}")
    else:
        print(f"  {Colors.DIM}🔌 No device selected{Colors.RESET}")
