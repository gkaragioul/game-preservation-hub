#!/usr/bin/env python3
"""Execute a bounded `input_plan` against the live WW3 window via `SendInput`.

Why `SendInput` and not `PostMessage` (what `auto_ui.py` uses): UE4 reads the
keyboard and mouse through **raw input** (`WM_INPUT`), which only ever reports
real, driver-level events.  A `PostMessage(WM_KEYDOWN)` is visible to Slate/UMG
but not to the raw-input path, which is why "TAB/M/SPACE produce zero client
RPCs" was recorded in Checkpoint 3 and never re-examined.  `SendInput` with
`KEYEVENTF_SCANCODE` is injected at the driver level and is what raw input sees.

Safety, in order of importance:

  1. **Focus gate** -- input is only ever emitted while the WW3 window is the
     foreground window.  If focus is not held, nothing is sent (fail closed).
  2. **Balance gate** -- the plan must satisfy `plan_is_balanced` before a single
     event goes out, so no keydown can ship without its keyup.
  3. **Release net** -- a `finally` block re-releases everything the plan touched
     even if the process is interrupted mid-plan.

Usage:
    python match_server/_send_input.py --key m --hold 0.06
    python match_server/_send_input.py --key w --hold 0.8
    python match_server/_send_input.py --click-norm 0.90,0.86
    python match_server/_send_input.py --key w --hold 0.5 --dry-run
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _live_frame import find_pid, find_window, focus_window, window_rect  # noqa: E402
from input_plan import (  # noqa: E402
    click_events,
    describe,
    key_events,
    plan_is_balanced,
    unbalanced_keys,
)

user32 = ctypes.WinDLL("user32", use_last_error=True)

INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
KEYEVENTF_KEYUP, KEYEVENTF_SCANCODE = 0x0002, 0x0008
MOUSEEVENTF_MOVE, MOUSEEVENTF_ABSOLUTE, MOUSEEVENTF_VIRTUALDESK = 0x0001, 0x8000, 0x4000
MOUSE_FLAGS = {
    ("left", True): 0x0002, ("left", False): 0x0004,
    ("right", True): 0x0008, ("right", False): 0x0010,
}
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("pad", ctypes.c_ubyte * 32)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _INPUTUNION)]


def _send(*inputs: INPUT) -> int:
    n = len(inputs)
    arr = (INPUT * n)(*inputs)
    sent = user32.SendInput(n, ctypes.byref(arr), ctypes.sizeof(INPUT))
    if sent != n:
        raise SystemExit(f"SendInput sent {sent}/{n} err={ctypes.get_last_error()}")
    return sent


def key_input(scan: int, down: bool) -> INPUT:
    flags = KEYEVENTF_SCANCODE | (0 if down else KEYEVENTF_KEYUP)
    return INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(0, scan, flags, 0, 0))


def mouse_button_input(button: str, down: bool) -> INPUT:
    return INPUT(type=INPUT_MOUSE,
                 mi=MOUSEINPUT(0, 0, 0, MOUSE_FLAGS[(button, down)], 0, 0))


def mouse_move_input(x: int, y: int) -> INPUT:
    vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    nx = int(round((x - vx) * 65535 / max(vw - 1, 1)))
    ny = int(round((y - vy) * 65535 / max(vh - 1, 1)))
    flags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
    return INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(nx, ny, 0, flags, 0, 0))


def release_all(plan) -> None:
    """Belt-and-braces: send an 'up' for everything the plan ever pressed."""
    for e in plan:
        try:
            if e["type"] == "key" and e["down"]:
                _send(key_input(e["scan"], False))
            elif e["type"] == "mouse" and e["down"]:
                _send(mouse_button_input(e["button"], False))
        except Exception:
            pass


def execute(plan, hwnd: int, *, require_focus: bool = True) -> dict:
    if not plan_is_balanced(plan):
        raise SystemExit(f"REFUSING unbalanced plan; still held: {unbalanced_keys(plan)}")
    fg = user32.GetForegroundWindow()
    if require_focus and fg != hwnd:
        raise SystemExit(f"REFUSING to send input: foreground {fg:#x} != WW3 {hwnd:#x}")
    t0 = time.time()
    try:
        for e in plan:
            if e["type"] == "sleep":
                time.sleep(e["s"])
            elif e["type"] == "key":
                _send(key_input(e["scan"], e["down"]))
            elif e["type"] == "mouse":
                _send(mouse_button_input(e["button"], e["down"]))
            elif e["type"] == "mousemove":
                _send(mouse_move_input(e["x"], e["y"]))
                time.sleep(0.03)
    finally:
        release_all(plan)
    return {"elapsed": time.time() - t0,
            "foreground_ok": user32.GetForegroundWindow() == hwnd}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, default=None)
    ap.add_argument("--hwnd", type=lambda s: int(s, 0), default=None)
    ap.add_argument("--key", action="append", default=[])
    ap.add_argument("--hold", type=float, default=0.06)
    ap.add_argument("--click", default=None, help="absolute screen X,Y")
    ap.add_argument("--click-win", default=None, help="window-relative X,Y")
    ap.add_argument("--click-norm", default=None, help="window-normalised nx,ny in 0..1")
    ap.add_argument("--button", default="left")
    ap.add_argument("--no-focus", dest="focus", action="store_false", default=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pid = args.pid or find_pid()
    hwnd = args.hwnd or find_window(pid)
    l, t, r, b = window_rect(hwnd)
    w, h = r - l, b - t

    plan: list[dict] = []
    if args.click:
        x, y = (int(v) for v in args.click.split(","))
        plan += click_events(x, y, args.button)
    if args.click_win:
        x, y = (int(v) for v in args.click_win.split(","))
        plan += click_events(l + x, t + y, args.button)
    if args.click_norm:
        nx, ny = (float(v) for v in args.click_norm.split(","))
        plan += click_events(int(l + nx * w), int(t + ny * h), args.button)
    for k in args.key:
        plan += key_events(k, args.hold)

    if not plan:
        raise SystemExit("nothing to do: pass --key / --click / --click-win / --click-norm")

    print(f"pid={pid} hwnd={hwnd:#x} rect=({l},{t})-({r},{b}) {w}x{h}")
    print(f"plan: {describe(plan)}")
    print(f"balanced={plan_is_balanced(plan)}")
    if args.dry_run:
        print("dry run -- nothing sent")
        return 0

    if args.focus:
        ok = focus_window(hwnd)
        print(f"focus ok={ok} foreground={user32.GetForegroundWindow():#x}")

    res = execute(plan, hwnd)
    print(f"sent in {res['elapsed']:.3f}s; still foreground={res['foreground_ok']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
