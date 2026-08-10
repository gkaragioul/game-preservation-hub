#!/usr/bin/env python3
"""CUSTOMIZE / EQUIPMENT SoftClassPtr warm via brief mouse clicks (Slate).

PostMessage alone does NOT switch WW3 top-nav tabs — use steal-mouse clicks,
then restore the cursor. Monitor 4 only.

Usage (from match_server/):
  python _customize_warm.py          # CUSTOMIZE → EQUIPMENT → browse
  python _customize_warm.py dismiss  # OK on WEIGHT LIMIT at (0.50, 0.463)
  python _customize_warm.py play     # PLAY list item + Space findLobby trail
"""
from __future__ import annotations

import ctypes
import sys
import time

import auto_ui

user32 = ctypes.WinDLL("user32")
VK_RETURN = 0x0D
VK_SPACE = 0x20
VK_ESCAPE = 0x1B
VK_X = 0x58
KEYUP = 0x0002


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def _save_cursor() -> tuple[int, int]:
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def _restore(saved: tuple[int, int]) -> None:
    user32.SetCursorPos(saved[0], saved[1])


def _key(vk: int, n: int = 1, gap: float = 0.25) -> None:
    for _ in range(n):
        user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(vk, 0, KEYUP, 0)
        time.sleep(gap)


def _steal(nx: float, ny: float) -> None:
    auto_ui.click_norm(nx, ny, post=False, monitor_number=4)


def dismiss_weight() -> None:
    """WEIGHT LIMIT OK button — calibrated ~image (959, 500) on 1920x1080."""
    for ny in (0.463, 0.46, 0.47):
        _steal(0.50, ny)
        time.sleep(0.2)
    _key(VK_SPACE, 1)


def warm_equipment() -> None:
    hwnd = auto_ui.find_ww3_hwnd()
    if not hwnd:
        raise SystemExit("no WW3")
    saved = _save_cursor()
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.15)
    # CUSTOMIZE top-nav (left of CAREER; gold tab band ~ y 0.16)
    for nx, ny in [(0.10, 0.16), (0.11, 0.157), (0.12, 0.16), (0.195, 0.16)]:
        _steal(nx, ny)
        time.sleep(0.25)
    # EQUIPMENT category
    for nx, ny in [(0.13, 0.35), (0.14, 0.37), (0.15, 0.38), (0.12, 0.40)]:
        _steal(nx, ny)
        time.sleep(0.3)
    dismiss_weight()
    time.sleep(0.5)
    # Browse weapons + toggle parts
    for ny in [i / 100 for i in range(25, 75, 5)]:
        _steal(0.12, ny)
        time.sleep(0.12)
    _key(VK_X, 2, gap=0.6)
    for nx, ny in [(0.32, 0.40), (0.32, 0.48), (0.35, 0.45), (0.40, 0.50)]:
        _steal(nx, ny)
        time.sleep(0.25)
    time.sleep(1.5)
    _restore(saved)
    print("customize_warm: equipment browse done (cursor restored)")


def play_findlobby() -> None:
    hwnd = auto_ui.find_ww3_hwnd()
    if not hwnd:
        raise SystemExit("no WW3")
    saved = _save_cursor()
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.15)
    # PLAY top-nav
    for nx, ny in [(0.05, 0.155), (0.06, 0.16), (0.07, 0.157)]:
        _steal(nx, ny)
        time.sleep(0.25)
    # PLAY list item (Quick Play) then Space/Enter
    for nx, ny in [(0.15, 0.28), (0.18, 0.30), (0.16, 0.32)]:
        _steal(nx, ny)
        time.sleep(0.2)
    _key(VK_SPACE, 4, gap=0.3)
    _key(VK_RETURN, 3, gap=0.3)
    _restore(saved)
    print("customize_warm: play findLobby trail done")


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "warm"
    if cmd == "warm":
        warm_equipment()
    elif cmd == "dismiss":
        saved = _save_cursor()
        user32.SetForegroundWindow(auto_ui.find_ww3_hwnd())
        dismiss_weight()
        _restore(saved)
    elif cmd == "play":
        play_findlobby()
    else:
        raise SystemExit("usage: _customize_warm.py [warm|dismiss|play]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
