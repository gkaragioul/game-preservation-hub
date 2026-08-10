#!/usr/bin/env python3
"""Dump the client's log buffer around the Client Synchronization checklist.

The checklist is formatted into memory even though this build writes no
Saved/Logs file, so the neighbouring formatted log lines are the closest thing to
a client-side log we can get without relaunching the game.

Usage:
    python match_server/_sync_context.py [--before 3000] [--after 3000]
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import re
import subprocess

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_NOACCESS = 0x01
PAGE_GUARD = 0x100

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_uint64),
        ("AllocationBase", ctypes.c_uint64),
        ("AllocationProtect", wt.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wt.DWORD),
        ("Protect", wt.DWORD),
        ("Type", wt.DWORD),
    ]


def find_pid() -> int:
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process WW3-Win64-Shipping -EA SilentlyContinue | Select -First 1).Id"],
        capture_output=True, text=True, check=False)
    pid = (r.stdout or "").strip()
    if not pid:
        raise SystemExit("WW3-Win64-Shipping not running")
    return int(pid)


def readable(text: str) -> str:
    """Keep only printable runs so the dump is a log, not a hex spill."""
    out = []
    for chunk in re.split(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\xff]{4,}", text):
        chunk = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\xff]", " ", chunk).strip()
        if len(chunk) >= 8:
            out.append(chunk)
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", type=int, default=3000)
    ap.add_argument("--after", type=int, default=3000)
    ap.add_argument("--needle", default="InventoryManager: ")
    ap.add_argument("--max", type=int, default=4)
    args = ap.parse_args()

    pid = find_pid()
    print(f"pid={pid} needle={args.needle!r}")
    h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        raise SystemExit(f"OpenProcess failed err={ctypes.get_last_error()}")

    needles = [(args.needle.encode("ascii"), "ascii"),
               (args.needle.encode("utf-16le"), "utf-16le")]
    mbi = MEMORY_BASIC_INFORMATION()
    addr = 0
    shown = 0
    read = ctypes.c_size_t()
    while kernel32.VirtualQueryEx(h, ctypes.c_uint64(addr), ctypes.byref(mbi),
                                  ctypes.sizeof(mbi)) and shown < args.max:
        base, size = mbi.BaseAddress, mbi.RegionSize
        nxt = base + size
        if (mbi.State == MEM_COMMIT and not (mbi.Protect & PAGE_NOACCESS)
                and not (mbi.Protect & PAGE_GUARD) and 0 < size <= 64 * 1024 * 1024):
            buf = (ctypes.c_char * size)()
            if kernel32.ReadProcessMemory(h, ctypes.c_uint64(base), buf, size,
                                          ctypes.byref(read)) and read.value:
                data = bytes(buf[:read.value])
                for needle, enc in needles:
                    i = data.find(needle)
                    if i < 0:
                        continue
                    lo = max(0, i - args.before * (2 if enc == "utf-16le" else 1))
                    hi = min(len(data), i + args.after * (2 if enc == "utf-16le" else 1))
                    chunk = data[lo:hi]
                    text = chunk.decode(enc, "replace") if enc == "utf-16le" \
                        else chunk.decode("latin-1", "replace")
                    print(f"\n===== @0x{base + i:x} ({enc}) =====")
                    print(readable(text))
                    shown += 1
                    break
        addr = nxt
        if addr == 0:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
