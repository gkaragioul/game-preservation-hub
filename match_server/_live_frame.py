#!/usr/bin/env python3
"""Capture *proven-live* frames of the WW3 client window.

Checkpoint 18: "capture screenshots are stale/byte-identical and cannot establish
UI state".  This tool exists to make a screenshot admissible again, by capturing
several frames and reporting the rule from `frame_liveness` alongside them.  A
single image proves nothing; N images that demonstrably move do.

Two things are done differently from `auto_ui.py shot`:

  * the pixels come from the **desktop DC** (`BitBlt` of the screen region the
    window occupies), never `PrintWindow`.  A D3D swapchain does not render into
    a `PrintWindow` DC, which is the most likely reason the earlier captures were
    byte-identical.
  * the window is optionally raised first, because the desktop DC returns
    whatever is physically on screen -- an occluded window captures the occluder.

Read-only with respect to the game: no memory access, no injection.  `--focus`
does raise the window, which is a UI side effect and is therefore opt-in.

Usage:
    python match_server/_live_frame.py --frames 4 --delay 0.4
    python match_server/_live_frame.py --focus --frames 6 --delay 0.3 --tag deploy
    python match_server/_live_frame.py --focus --crop-center 640x360
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from frame_liveness import DEFAULT_MIN_CHANGED_FRAC, liveness_verdict  # noqa: E402

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_AWARE
except Exception:  # pragma: no cover - depends on OS build
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

SRCCOPY = 0x00CC0020
OUT_DIR = Path(__file__).resolve().parent / "live_log"


class RECT(ctypes.Structure):
    _fields_ = [("left", wt.LONG), ("top", wt.LONG),
                ("right", wt.LONG), ("bottom", wt.LONG)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
                ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


def find_pid() -> int:
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process WW3-Win64-Shipping -EA SilentlyContinue | Select -First 1).Id"],
        capture_output=True, text=True)
    out = (r.stdout or "").strip()
    if not out.isdigit():
        raise SystemExit("WW3-Win64-Shipping is not running")
    return int(out)


def find_window(pid: int) -> int:
    """Largest visible top-level window owned by `pid`."""
    best, best_area = 0, -1

    @ctypes.WINFUNCTYPE(ctypes.c_int, wt.HWND, wt.LPARAM)
    def _enum(hwnd, _l):
        nonlocal best, best_area
        wpid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value != pid or not user32.IsWindowVisible(hwnd):
            return 1
        r = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        area = (r.right - r.left) * (r.bottom - r.top)
        if area > best_area:
            best, best_area = hwnd, area
        return 1

    user32.EnumWindows(_enum, 0)
    if not best:
        raise SystemExit(f"no visible top-level window for pid {pid}")
    return best


def window_rect(hwnd: int) -> tuple[int, int, int, int]:
    r = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def focus_window(hwnd: int) -> bool:
    """Raise + focus, using the AttachThreadInput dance Windows requires."""
    fg = user32.GetForegroundWindow()
    cur_tid = ctypes.windll.kernel32.GetCurrentThreadId()
    fg_tid = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    if fg_tid and fg_tid != cur_tid:
        user32.AttachThreadInput(cur_tid, fg_tid, True)
    user32.ShowWindow(hwnd, 9)          # SW_RESTORE
    user32.BringWindowToTop(hwnd)
    ok = bool(user32.SetForegroundWindow(hwnd))
    user32.SetActiveWindow(hwnd)
    if fg_tid and fg_tid != cur_tid:
        user32.AttachThreadInput(cur_tid, fg_tid, False)
    time.sleep(0.25)
    return bool(ok or user32.GetForegroundWindow() == hwnd)


def grab(left: int, top: int, width: int, height: int) -> np.ndarray:
    """BitBlt the screen region out of the desktop DC -> HxWx3 uint8 (RGB)."""
    hdesk = user32.GetDesktopWindow()
    hdc = user32.GetDC(hdesk)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, width, height)
    old = gdi32.SelectObject(mem, bmp)
    try:
        if not gdi32.BitBlt(mem, 0, 0, width, height, hdc, left, top, SRCCOPY):
            raise SystemExit(f"BitBlt failed err={ctypes.get_last_error()}")
        bi = BITMAPINFO()
        bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bi.bmiHeader.biWidth = width
        bi.bmiHeader.biHeight = -height          # top-down
        bi.bmiHeader.biPlanes = 1
        bi.bmiHeader.biBitCount = 32
        bi.bmiHeader.biCompression = 0           # BI_RGB
        buf = ctypes.create_string_buffer(width * height * 4)
        if not gdi32.GetDIBits(mem, bmp, 0, height, buf, ctypes.byref(bi), 0):
            raise SystemExit("GetDIBits failed")
        arr = np.frombuffer(buf, dtype=np.uint8).reshape(height, width, 4)
        return arr[:, :, [2, 1, 0]].copy()       # BGRA -> RGB
    finally:
        gdi32.SelectObject(mem, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(hdesk, hdc)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, default=None)
    ap.add_argument("--hwnd", type=lambda s: int(s, 0), default=None)
    ap.add_argument("--frames", type=int, default=4)
    ap.add_argument("--delay", type=float, default=0.4)
    ap.add_argument("--focus", action="store_true", help="raise the window first")
    ap.add_argument("--tag", default="frame")
    ap.add_argument("--save", action="store_true", default=True)
    ap.add_argument("--no-save", dest="save", action="store_false")
    ap.add_argument("--crop-center", default=None, help="e.g. 640x360")
    ap.add_argument("--min-changed-frac", type=float, default=DEFAULT_MIN_CHANGED_FRAC)
    ap.add_argument("--allow-occluded", action="store_true",
                    help="capture even if WW3 is not the foreground window")
    args = ap.parse_args()

    pid = args.pid or find_pid()
    hwnd = args.hwnd or find_window(pid)
    l, t, r, b = window_rect(hwnd)
    w, h = r - l, b - t
    print(f"pid={pid} hwnd={hwnd:#x} rect=({l},{t})-({r},{b}) {w}x{h}")

    if args.focus:
        got = focus_window(hwnd)
        fg = user32.GetForegroundWindow()
        print(f"focus requested: ok={got} foreground={fg:#x} "
              f"{'== target' if fg == hwnd else '!= target'}")

    # The pixels come from the desktop DC, so an occluding window is captured
    # instead of the game.  That is both useless as evidence and a privacy
    # hazard -- whatever the operator happens to have open ends up on disk.
    # Refuse unless the caller explicitly opts in.
    fg = user32.GetForegroundWindow()
    if fg != hwnd and not args.allow_occluded:
        print(f"REFUSING to capture: foreground is {fg:#x}, not WW3 {hwnd:#x}.\n"
              f"  Re-run with --focus (raises WW3 first) or --allow-occluded.")
        return 4

    # Per-frame, not once up front: another window can raise itself mid-capture
    # (a chat notification is enough), and a frame taken during that is both
    # useless and a privacy leak.  Drop any frame not bracketed by WW3 focus.
    frames = []
    stamps = []
    dropped = 0
    for i in range(args.frames):
        before = user32.GetForegroundWindow()
        f = grab(l, t, w, h)
        after = user32.GetForegroundWindow()
        if not args.allow_occluded and (before != hwnd or after != hwnd):
            dropped += 1
            print(f"   [drop] frame {i}: foreground {before:#x}/{after:#x} != WW3")
        else:
            frames.append(f)
            stamps.append(time.time())
        if i != args.frames - 1:
            time.sleep(args.delay)
    if dropped:
        print(f"   dropped {dropped} occluded frame(s); kept {len(frames)}")
    if len(frames) < 2:
        print("not enough on-target frames to judge liveness; re-run with --focus")
        return 4

    v = liveness_verdict(frames, min_changed_frac=args.min_changed_frac)
    print(f"\n[liveness] frames={v['frames']} distinct_digests={v['distinct_digests']} "
          f"max_changed_frac={v['max_changed_frac']:.6f} "
          f"threshold={v['min_changed_frac']} -> LIVE={v['live']}")
    for p in v["pairs"]:
        print(f"   pair {p['index']}->{p['index']+1}: changed={p['changed_pixels']}/"
              f"{p['total_pixels']} ({p['changed_frac']:.6f}) max_abs={p['max_abs']} "
              f"mean_abs={p['mean_abs']:.3f} moved={p['moved']}")
    print(f"   digest[0]={v['digests'][0][:16]}  digest[-1]={v['digests'][-1][:16]}")

    if args.crop_center:
        cw, ch = (int(x) for x in args.crop_center.lower().split("x"))
        cx, cy = w // 2, h // 2
        x0, y0 = max(0, cx - cw // 2), max(0, cy - ch // 2)
        crops = [f[y0:y0 + ch, x0:x0 + cw] for f in frames]
        cv = liveness_verdict(crops, min_changed_frac=args.min_changed_frac)
        print(f"[liveness/center {cw}x{ch}] max_changed_frac={cv['max_changed_frac']:.6f} "
              f"-> LIVE={cv['live']}")

    if args.save:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%H%M%S")
        for i, f in enumerate(frames):
            p = OUT_DIR / f"lf_{args.tag}_{ts}_{i}.png"
            Image.fromarray(f).save(p)
            print(f"   saved {p}")

    return 0 if v["live"] else 3


if __name__ == "__main__":
    sys.exit(main())
