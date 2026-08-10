#!/usr/bin/env python3
r"""Drive a freshly launched client from the splash into a match on our server.

Why this exists
---------------
Every live A/B needs the same three steps and they are easy to get wrong:

  1. the client boots to **PRESS ANY KEY TO CONTINUE** and sits there forever,
  2. the main menu needs **QUICK PLAY**,
  3. only then does the mock hub run `findLobbyForParty` -> `lobby READY ->
     127.0.0.1:7871` and hand the client to the match server.

The important operational fact, learned the hard way: on the main menu
`PostMessage(WM_LBUTTONDOWN)` is **ignored** -- Slate never sees it, with or
without `SetForegroundWindow` and with or without a preceding `WM_MOUSEMOVE`.
Only a real cursor click (`SetCursorPos` + `mouse_event`, i.e.
`auto_ui.click_norm(post=False)`) registers. `_rematch_drive.py`'s PostMessage
clicks work on the post-match screen but not here.

Progress is confirmed from the mock hub's own log rather than from screenshots,
so this is safe to run unattended.

Usage:
    python match_server/_menu_to_match.py
    python match_server/_menu_to_match.py --timeout 420
"""
from __future__ import annotations

import argparse
import ctypes
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import auto_ui  # noqa: E402

HUB_LOG = HERE.parent / "windows" / "mock_logs" / "hub_version4.err.log"

# Normalised to the monitor the WW3 window is actually on.
SPLASH_ANY_KEY = (0.5000, 0.4917)     # anywhere in the client area dismisses it
QUICK_PLAY = (0.2133, 0.3465)         # "QUICK PLAY -- Join a random match" tile

READY = re.compile(r"lobby (\d+) READY -> ([\d.]+:\d+)")


def hub_ready_count() -> int:
    if not HUB_LOG.exists():
        return 0
    return len(READY.findall(HUB_LOG.read_text(encoding="utf-8", errors="replace")))


def raise_ww3() -> bool:
    """Bring WW3 to the front.

    A real cursor click goes to whatever window is on top at those coordinates,
    so an unrelated console sitting over the game silently eats every click --
    which is exactly how run 2's first drive attempt failed.
    """
    user32 = ctypes.WinDLL("user32")
    hwnd = auto_ui.find_ww3_hwnd()
    if not hwnd:
        return False
    user32.ShowWindow(hwnd, 9)               # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)
    time.sleep(0.35)
    return True


def window_monitor() -> int | None:
    hwnd = auto_ui.find_ww3_hwnd()
    if not hwnd:
        return None
    left, top, _r, _b = auto_ui.window_rect(hwnd)
    for m in auto_ui.list_monitors():
        if (m["x"] <= left < m["x"] + m["w"]
                and m["y"] - 60 <= top < m["y"] + m["h"]):
            return m["number"]
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=float, default=420.0)
    args = ap.parse_args()

    before = hub_ready_count()
    deadline = time.time() + args.timeout

    mon = None
    while time.time() < deadline:
        mon = window_monitor()
        if mon is not None:
            break
        time.sleep(2.0)
    if mon is None:
        print("WW3 window never appeared")
        return 1
    print(f"WW3 window is on monitor {mon}")

    # The splash and the menu are driven by the same real click; alternate
    # between the two targets until the hub reports a lobby handoff.
    for attempt in range(1, 400):
        if hub_ready_count() > before:
            print(f"hub handed the client off after {attempt} click rounds")
            return 0
        if time.time() > deadline:
            break
        target = SPLASH_ANY_KEY if attempt % 2 == 1 else QUICK_PLAY
        name = "splash" if attempt % 2 == 1 else "QUICK PLAY"
        if not raise_ww3():
            print(f"  [{attempt}] WW3 window vanished")
            return 1
        try:
            auto_ui.click_norm(*target, post=False, monitor_number=mon)
            print(f"  [{attempt}] real click on {name}", flush=True)
        except SystemExit as exc:
            print(f"  [{attempt}] click refused: {exc}", flush=True)
        time.sleep(3.0)

    print("timed out waiting for the hub lobby handoff")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
