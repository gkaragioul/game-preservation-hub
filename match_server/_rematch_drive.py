#!/usr/bin/env python3
"""Drive the client from the post-match screen back into a match on our server.

Sequence observed on this build: LEVEL PROGRESS -> "GO TO LOBBY" -> lobby
"SKIP WAITING" -> hub hands off to match_server on :7871.

Usage:
    python match_server/_rematch_drive.py --log live_log/match_console_X.out.txt
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
GO_TO_LOBBY = (0.500, 0.916)
SKIP_WAITING = (0.514, 0.851)
VK_ESCAPE = 0x1B


def press(vk: int) -> None:
    scan = user32.MapVirtualKeyW(vk, 0)
    user32.keybd_event(vk, scan, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(vk, scan, 2, 0)


def handshakes(log: Path) -> int:
    if not log.exists():
        return 0
    return log.read_text(encoding="utf-8", errors="replace").count("HANDSHAKE COMPLETE")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--leave", action="store_true",
                    help="Esc out of a live match first")
    args = ap.parse_args()

    log = Path(args.log)
    before = handshakes(log)
    hwnd = auto_ui.find_ww3_hwnd()
    if not hwnd:
        print("WW3 window not found")
        return 1

    if args.leave:
        for _ in range(8):
            press(VK_ESCAPE)
            time.sleep(0.35)
        time.sleep(1.5)

    deadline = time.time() + args.timeout
    while time.time() < deadline:
        for nx, ny in (GO_TO_LOBBY, SKIP_WAITING):
            auto_ui.click_norm(nx, ny, post=True, monitor_number=4)
            time.sleep(0.4)
        for _ in range(12):
            time.sleep(1.0)
            if handshakes(log) > before:
                print(f"handshake seen after {args.timeout - (deadline - time.time()):.0f}s")
                return 0
        print("...still waiting for handoff")
    print("timed out waiting for handshake")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
