#!/usr/bin/env python3
"""Rematch via PostMessage only — no SetCursorPos / mouse_event."""
from __future__ import annotations

import ctypes
import sys
import time

sys.path.insert(0, ".")
import auto_ui  # noqa: E402

user32 = ctypes.WinDLL("user32")
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
VK_ESCAPE = 0x1B
VK_RETURN = 0x0D
VK_SPACE = 0x20


def post_key(hwnd, vk, n=1, gap=0.08):
    for _ in range(n):
        user32.PostMessageW(hwnd, WM_KEYDOWN, vk, 0)
        time.sleep(0.03)
        user32.PostMessageW(hwnd, WM_KEYUP, vk, 0)
        time.sleep(gap)


def main() -> int:
    hwnd = auto_ui.find_ww3_hwnd()
    print("hwnd", hwnd)
    if not hwnd:
        return 1
    # Escape loading / menus (PostMessage — no cursor)
    print("post Esc x8")
    post_key(hwnd, VK_ESCAPE, n=8, gap=0.35)
    time.sleep(0.5)
    # GO TO LOBBY trail (bottom-center)
    print("lobby postclicks")
    for nx, ny in [
        (0.50, 0.90), (0.50, 0.92), (0.50, 0.88), (0.48, 0.90), (0.52, 0.90),
        (0.50, 0.85), (0.45, 0.90), (0.55, 0.90), (0.50, 0.94), (0.50, 0.80),
    ]:
        auto_ui.click_norm(nx, ny, post=True, monitor_number=4)
        time.sleep(0.12)
    time.sleep(1.0)
    # Quick Play region (typical left/center menu) — dense trail + Enter
    print("quickplay postclicks")
    for nx, ny in [
        (0.18, 0.42), (0.20, 0.45), (0.16, 0.45), (0.22, 0.48), (0.18, 0.50),
        (0.25, 0.45), (0.15, 0.40), (0.30, 0.50), (0.12, 0.55), (0.35, 0.42),
        (0.50, 0.55), (0.45, 0.60), (0.55, 0.58),
    ]:
        auto_ui.click_norm(nx, ny, post=True, monitor_number=4)
        time.sleep(0.10)
    post_key(hwnd, VK_RETURN, n=3, gap=0.25)
    post_key(hwnd, VK_SPACE, n=2, gap=0.25)
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
