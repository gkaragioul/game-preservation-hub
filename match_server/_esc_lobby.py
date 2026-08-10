#!/usr/bin/env python3
"""Brief Esc via keybd_event (raw input) then optional lobby PostMessage clicks."""
from __future__ import annotations

import ctypes
import sys
import time

sys.path.insert(0, ".")
import auto_ui  # noqa: E402

user32 = ctypes.WinDLL("user32")
VK_ESCAPE = 0x1B
KEYEVENTF_KEYUP = 0x0002


def esc(n: int = 5) -> None:
    hwnd = auto_ui.find_ww3_hwnd()
    print("hwnd", hwnd)
    if not hwnd:
        raise SystemExit("no ww3")
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.15)
    for _ in range(n):
        user32.keybd_event(VK_ESCAPE, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.4)
    print("keybd_esc_done")


def lobby_clicks() -> None:
    # Dense trail around GO TO LOBBY (bottom-center) — PostMessage, no cursor steal
    pts = [
        (0.50, 0.90), (0.50, 0.92), (0.50, 0.88), (0.48, 0.90), (0.52, 0.90),
        (0.50, 0.85), (0.45, 0.90), (0.55, 0.90), (0.50, 0.94),
    ]
    for nx, ny in pts:
        auto_ui.click_norm(nx, ny, post=True, monitor_number=4)
        time.sleep(0.12)
    print("lobby_clicks_done")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "esc"
    if cmd == "esc":
        esc()
    elif cmd == "lobby":
        lobby_clicks()
    else:
        raise SystemExit("usage: _esc_lobby.py esc|lobby")
