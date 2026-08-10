#!/usr/bin/env python3
"""Operator helpers: screenshot / place / click WW3 on a fixed monitor (default 4).

Never steal the operator's mouse for normal automation — use postclick.
All WW3 UI work MUST stay on WW3_UI_MONITOR (default 4).
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time
from pathlib import Path

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

# Per-monitor DPI awareness so ScreenToClient / monitor sizes match the UE window
# (without this, Win32 returns 1536x864 for a 1920x1080 DISPLAY4 and PostMessage
# clicks land in the wrong client coords).
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_AWARE
except Exception:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

SRCCOPY = 0x00CC0020
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_SHOWWINDOW = 0x0040
SWP_FRAMECHANGED = 0x0020
HWND_TOP = 0
# Prefer Windows \\.\DISPLAYn (matches Display Settings "Identify"), not Enum order.
# Operator target: LG 100Hz = DISPLAY4 @ (4480,141). Override with WW3_UI_DISPLAY=4.
DEFAULT_DISPLAY = int(os.environ.get("WW3_UI_DISPLAY", os.environ.get("WW3_UI_MONITOR", "4")))


class RECT(ctypes.Structure):
    _fields_ = [("left", wt.LONG), ("top", wt.LONG), ("right", wt.LONG), ("bottom", wt.LONG)]


class MONITORINFOEX(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wt.DWORD),
        ("szDevice", wt.WCHAR * 32),
    ]


class DISPLAY_DEVICE(ctypes.Structure):
    _fields_ = [
        ("cb", wt.DWORD),
        ("DeviceName", wt.WCHAR * 32),
        ("DeviceString", wt.WCHAR * 128),
        ("StateFlags", wt.DWORD),
        ("DeviceID", wt.WCHAR * 128),
        ("DeviceKey", wt.WCHAR * 128),
    ]


class DEVMODE(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", wt.WCHAR * 32),
        ("dmSpecVersion", wt.WORD),
        ("dmDriverVersion", wt.WORD),
        ("dmSize", wt.WORD),
        ("dmDriverExtra", wt.WORD),
        ("dmFields", wt.DWORD),
        ("dmPositionX", ctypes.c_long),
        ("dmPositionY", ctypes.c_long),
        ("dmDisplayOrientation", wt.DWORD),
        ("dmDisplayFixedOutput", wt.DWORD),
        ("dmColor", wt.SHORT),
        ("dmDuplex", wt.SHORT),
        ("dmYResolution", wt.SHORT),
        ("dmTTOption", wt.SHORT),
        ("dmCollate", wt.SHORT),
        ("dmFormName", wt.WCHAR * 32),
        ("dmLogPixels", wt.WORD),
        ("dmBitsPerPel", wt.DWORD),
        ("dmPelsWidth", wt.DWORD),
        ("dmPelsHeight", wt.DWORD),
        ("dmDisplayFlags", wt.DWORD),
        ("dmDisplayFrequency", wt.DWORD),
    ]


def list_monitors() -> list[dict]:
    """Enumerate attached displays with Windows DISPLAY number + Hz + vendor id."""
    mons: list[dict] = []
    by_device: dict[str, dict] = {}

    @ctypes.WINFUNCTYPE(ctypes.c_int, wt.HMONITOR, wt.HDC, ctypes.POINTER(RECT), wt.LPARAM)
    def _enum(hmon, hdc, lprect, lparam):
        mi = MONITORINFOEX()
        mi.cbSize = ctypes.sizeof(MONITORINFOEX)
        user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
        r = mi.rcMonitor
        by_device[mi.szDevice] = {
            "x": r.left,
            "y": r.top,
            "w": r.right - r.left,
            "h": r.bottom - r.top,
            "primary": bool(mi.dwFlags & 1),
            "device": mi.szDevice,
        }
        return 1

    user32.EnumDisplayMonitors(0, 0, _enum, 0)

    i = 0
    while True:
        dd = DISPLAY_DEVICE()
        dd.cb = ctypes.sizeof(dd)
        if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
            break
        if dd.StateFlags & 1:  # ATTACHED_TO_DESKTOP
            mon = DISPLAY_DEVICE()
            mon.cb = ctypes.sizeof(mon)
            user32.EnumDisplayDevicesW(dd.DeviceName, 0, ctypes.byref(mon), 0)
            dm = DEVMODE()
            dm.dmSize = ctypes.sizeof(dm)
            user32.EnumDisplaySettingsW(dd.DeviceName, -1, ctypes.byref(dm))
            geo = by_device.get(dd.DeviceName, {})
            # \\.\DISPLAY4 -> number 4 (matches Windows Identify)
            try:
                number = int(dd.DeviceName.rsplit("DISPLAY", 1)[-1])
            except ValueError:
                number = i + 1
            vendor = ""
            if "MONITOR\\" in mon.DeviceID:
                vendor = mon.DeviceID.split("MONITOR\\", 1)[1].split("\\", 1)[0]
            mons.append({
                "index": len(mons),
                "number": number,
                "x": geo.get("x", dm.dmPositionX),
                "y": geo.get("y", dm.dmPositionY),
                "w": geo.get("w", int(dm.dmPelsWidth)),
                "h": geo.get("h", int(dm.dmPelsHeight)),
                "primary": bool(dd.StateFlags & 4) or geo.get("primary", False),
                "device": dd.DeviceName,
                "hz": int(dm.dmDisplayFrequency),
                "native_w": int(dm.dmPelsWidth),
                "native_h": int(dm.dmPelsHeight),
                "vendor": vendor,
                "monitor_name": mon.DeviceString,
            })
        i += 1
    return mons


def get_monitor(monitor_number: int | None = None) -> dict:
    """Resolve UI target: DISPLAY number, else LG 100Hz (GSM*), else env fallback."""
    mons = list_monitors()
    if not mons:
        raise SystemExit("no monitors found")

    # Explicit DISPLAY number (Windows Identify / \\.\DISPLAYn)
    if monitor_number is not None or os.environ.get("WW3_UI_DISPLAY") or os.environ.get("WW3_UI_MONITOR"):
        n = DEFAULT_DISPLAY if monitor_number is None else int(monitor_number)
        mon = next((m for m in mons if m["number"] == n), None)
        if mon:
            return mon
        raise SystemExit(f"DISPLAY{n} not found; have {[m['number'] for m in mons]}")

    # Auto: LG (GSM*) at 100Hz — operator's stated target
    lg100 = [m for m in mons if m.get("hz") == 100 and str(m.get("vendor", "")).startswith("GSM")]
    if lg100:
        return lg100[0]
    hz100 = [m for m in mons if m.get("hz") == 100]
    if hz100:
        return hz100[0]
    mon = next((m for m in mons if m["number"] == DEFAULT_DISPLAY), None)
    if mon:
        return mon
    raise SystemExit(f"UI monitor not found; have {mons}")


def assert_on_ui_monitor(x: int, y: int, monitor_number: int | None = None) -> dict:
    mon = get_monitor(monitor_number)
    if not (mon["x"] <= x < mon["x"] + mon["w"] and mon["y"] <= y < mon["y"] + mon["h"]):
        raise SystemExit(
            f"refusing click ({x},{y}): outside monitor {mon['number']} "
            f"bounds ({mon['x']},{mon['y']})+{mon['w']}x{mon['h']}"
        )
    return mon


def screenshot_monitor(monitor_number: int | None, out_path: Path) -> dict:
    mon = get_monitor(monitor_number)
    x, y, w, h = mon["x"], mon["y"], mon["w"], mon["h"]
    hdc = user32.GetDC(0)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mem, bmp)
    gdi32.BitBlt(mem, 0, 0, w, h, hdc, x, y, SRCCOPY)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
            ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
            ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG),
            ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = w
    bmi.bmiHeader.biHeight = -h
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0
    buf_size = w * h * 4
    buf = (ctypes.c_ubyte * buf_size)()
    gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bmi), 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(0, hdc)

    from PIL import Image
    img = Image.frombuffer("RGB", (w, h), bytes(buf), "raw", "BGRX", 0, 1)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return {"path": str(out_path), **mon}


def find_ww3_hwnd() -> int:
    found = []

    # Prefer the actual Shipping process window.  A Discord/community window can
    # contain "World War 3" in its title and otherwise wins the title-only scan.
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process WW3-Win64-Shipping -EA SilentlyContinue | Select -First 1).Id"],
        capture_output=True, text=True,
    )
    pid = int((r.stdout or "0").strip() or 0)
    if pid:
        @ctypes.WINFUNCTYPE(ctypes.c_int, wt.HWND, wt.LPARAM)
        def _enum_process(hwnd, lparam):
            pid_out = wt.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_out))
            if pid_out.value == pid and user32.IsWindowVisible(hwnd):
                found.append(hwnd)
            return 1
        user32.EnumWindows(_enum_process, 0)
        if found:
            return int(found[0])

    @ctypes.WINFUNCTYPE(ctypes.c_int, wt.HWND, wt.LPARAM)
    def _enum(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return 1
        n = user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return 1
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        title = buf.value
        if "WW3" in title or "World War 3" in title or title.strip() == "WW3":
            found.append(hwnd)
        return 1

    user32.EnumWindows(_enum, 0)
    if found:
        return int(found[0])
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process WW3-Win64-Shipping -EA SilentlyContinue | Select -First 1).Id"],
        capture_output=True, text=True,
    )
    pid = int((r.stdout or "0").strip() or 0)
    if not pid:
        return 0

    @ctypes.WINFUNCTYPE(ctypes.c_int, wt.HWND, wt.LPARAM)
    def _enum2(hwnd, lparam):
        pid_out = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_out))
        if pid_out.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return 1

    user32.EnumWindows(_enum2, 0)
    return int(found[0]) if found else 0


def window_rect(hwnd: int) -> tuple[int, int, int, int]:
    r = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def move_ww3_to_monitor(monitor_number: int | None = None, retries: int = 3) -> dict:
    mon = get_monitor(monitor_number)
    hwnd = find_ww3_hwnd()
    if not hwnd:
        raise SystemExit("WW3 window not found")
    for i in range(retries):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        time.sleep(0.15)
        user32.SetWindowPos(
            hwnd, HWND_TOP, mon["x"], mon["y"], mon["w"], mon["h"],
            SWP_NOZORDER | SWP_SHOWWINDOW | SWP_FRAMECHANGED,
        )
        time.sleep(0.25)
        left, top, right, bottom = window_rect(hwnd)
        on = left >= mon["x"] - 20 and left < mon["x"] + mon["w"] // 2
        if on:
            return {
                "hwnd": hwnd, "attempt": i + 1,
                "rect": [left, top, right, bottom], **mon,
            }
    left, top, right, bottom = window_rect(hwnd)
    return {
        "hwnd": hwnd, "attempt": retries, "warn": "may_not_stick",
        "rect": [left, top, right, bottom], **mon,
    }


def click_screen(x: int, y: int, clicks: int = 1, monitor_number: int | None = None) -> None:
    """Moves the real system cursor (steals mouse). Prefer post_click for hands-off."""
    assert_on_ui_monitor(x, y, monitor_number)
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.05)
    for _ in range(clicks):
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        user32.mouse_event(0x0004, 0, 0, 0, 0)
        time.sleep(0.08)


WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001


def _makelparam(x: int, y: int) -> int:
    return (int(y) & 0xFFFF) << 16 | (int(x) & 0xFFFF)


def post_click_screen(x: int, y: int, clicks: int = 1, focus: bool = False,
                      monitor_number: int | None = None) -> dict:
    """Click via PostMessage — does NOT move the system cursor. Clamped to UI monitor."""
    assert_on_ui_monitor(x, y, monitor_number)
    hwnd = find_ww3_hwnd()
    if not hwnd:
        raise SystemExit("WW3 window not found")
    if focus:
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.05)
    pt = wt.POINT(int(x), int(y))
    if not user32.ScreenToClient(hwnd, ctypes.byref(pt)):
        raise SystemExit("ScreenToClient failed")
    lp = _makelparam(pt.x, pt.y)
    for _ in range(clicks):
        user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lp)
        time.sleep(0.05)
        user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lp)
        time.sleep(0.08)
    return {"hwnd": hwnd, "screen": (x, y), "client": (pt.x, pt.y), "focus": focus}


def click_norm(nx: float, ny: float, *, post: bool = True, focus: bool = False,
               monitor_number: int | None = None) -> dict:
    """Click normalized 0..1 coords within the UI monitor."""
    mon = get_monitor(monitor_number)
    x = int(mon["x"] + nx * mon["w"])
    y = int(mon["y"] + ny * mon["h"])
    if post:
        return post_click_screen(x, y, focus=focus, monitor_number=mon["number"])
    click_screen(x, y, monitor_number=mon["number"])
    return {"screen": (x, y), "norm": (nx, ny), **mon}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("monitors")
    p = sub.add_parser("shot")
    p.add_argument("--monitor", type=int, default=DEFAULT_DISPLAY)
    p.add_argument("-o", type=Path, default=Path("match_server/live_log/auto_shot.png"))
    p = sub.add_parser("place")
    p.add_argument("--monitor", type=int, default=DEFAULT_DISPLAY)
    p = sub.add_parser("where")
    p = sub.add_parser("click")
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)
    p = sub.add_parser("postclick", help="Click without moving mouse (PostMessage)")
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)
    p.add_argument("--focus", action="store_true")
    p = sub.add_parser("nclick", help="Normalized 0..1 click on UI monitor (default post)")
    p.add_argument("nx", type=float)
    p.add_argument("ny", type=float)
    p.add_argument("--steal-mouse", action="store_true")
    p.add_argument("--focus", action="store_true")
    p.add_argument("--monitor", type=int, default=DEFAULT_DISPLAY)
    args = ap.parse_args()
    if args.cmd == "monitors":
        for m in list_monitors():
            print(m)
        print(f"DEFAULT_DISPLAY={DEFAULT_DISPLAY}")
    elif args.cmd == "shot":
        print(screenshot_monitor(args.monitor, args.o))
    elif args.cmd == "place":
        print(move_ww3_to_monitor(args.monitor))
    elif args.cmd == "where":
        hwnd = find_ww3_hwnd()
        if not hwnd:
            raise SystemExit("WW3 window not found")
        left, top, right, bottom = window_rect(hwnd)
        mons = list_monitors()
        hit = None
        for m in mons:
            if m["x"] <= left < m["x"] + m["w"] and m["y"] - 40 <= top < m["y"] + m["h"]:
                hit = m["number"]
        print({"hwnd": hwnd, "rect": [left, top, right, bottom], "monitor": hit})
    elif args.cmd == "click":
        click_screen(args.x, args.y)
    elif args.cmd == "postclick":
        print(post_click_screen(args.x, args.y, focus=args.focus))
    elif args.cmd == "nclick":
        print(click_norm(args.nx, args.ny, post=not args.steal_mouse,
                         focus=args.focus, monitor_number=args.monitor))


if __name__ == "__main__":
    main()
