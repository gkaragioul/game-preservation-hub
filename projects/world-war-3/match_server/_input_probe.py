#!/usr/bin/env python3
"""Send real keyboard input to the WW3 client and report what it made it say.

The client is behind a full-screen briefing layer, so the only way to tell which
UI actually owns input is to press a key and diff the match server's C->S RPC log.

Usage:
    python match_server/_input_probe.py --log live_log/match_console_X.out.txt ESC M TAB
"""
from __future__ import annotations

import argparse
import ctypes
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import auto_ui  # noqa: E402

user32 = ctypes.WinDLL("user32")
KEYEVENTF_KEYUP = 0x0002

VK = {
    "ESC": 0x1B, "ENTER": 0x0D, "SPACE": 0x20, "TAB": 0x09,
    "M": 0x4D, "W": 0x57, "A": 0x41, "S": 0x53, "D": 0x44,
    "E": 0x45, "F": 0x46, "B": 0x42, "N": 0x4E,
    "F1": 0x70, "F5": 0x74,
}


def press(vk: int, hold: float = 0.06) -> None:
    scan = user32.MapVirtualKeyW(vk, 0)
    user32.keybd_event(vk, scan, 0, 0)
    time.sleep(hold)
    user32.keybd_event(vk, scan, KEYEVENTF_KEYUP, 0)


def focus_ww3(hwnd: int) -> None:
    """SetForegroundWindow alone is refused across process/thread boundaries.

    Attach to the target's input queue first, which is what lets a background
    process legitimately hand focus over.  A title-bar click is the fallback.
    """
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.4)
    if user32.GetForegroundWindow() == hwnd:
        return
    # Cross-process SetForegroundWindow is refused while another app owns focus.
    # A real click on WW3's own title bar is the one thing Windows always honours,
    # and it cannot reach the game's viewport.
    left, top, right, _bottom = auto_ui.window_rect(hwnd)
    user32.SetCursorPos((left + right) // 2, top + 12)
    time.sleep(0.2)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.06)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(0.8)


def interesting(line: str) -> bool:
    return ("RPC handles" in line and "handles=[73]" not in line
            and "handles=[17]" not in line) or "M4:" in line or "CHANNEL CLOSE" in line


def tail_len(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def new_lines(path: Path, since: int) -> list[str]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return [ln for ln in lines[since:] if interesting(ln)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("keys", nargs="+")
    ap.add_argument("--log", required=True)
    ap.add_argument("--settle", type=float, default=2.5)
    ap.add_argument("--repeat", type=int, default=1)
    args = ap.parse_args()

    log = Path(args.log)
    hwnd = auto_ui.find_ww3_hwnd()
    if not hwnd:
        print("WW3 window not found")
        return 1
    focus_ww3(hwnd)
    fg = user32.GetForegroundWindow()
    print(f"hwnd={hwnd} foreground={fg} focused={fg == hwnd}")
    if fg != hwnd:
        print("! WW3 is not foreground; keystrokes would go elsewhere")
        return 2

    for name in args.keys:
        vk = VK.get(name.upper())
        if vk is None:
            print(f"! unknown key {name}")
            continue
        mark = tail_len(log)
        for _ in range(args.repeat):
            press(vk)
            time.sleep(0.12)
        time.sleep(args.settle)
        added = new_lines(log, mark)
        print(f"\n=== {name} x{args.repeat} -> {len(added)} new events ===")
        for ln in added[:25]:
            print("   ", ln.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
