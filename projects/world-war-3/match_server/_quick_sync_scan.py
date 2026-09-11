#!/usr/bin/env python3
"""Faster heap scan: stop after finding Client Synchronization checklist blocks."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import re
import subprocess
import sys

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
        capture_output=True, text=True, check=False,
    )
    pid = (r.stdout or "").strip()
    if not pid:
        raise SystemExit("WW3 not running")
    return int(pid)


def main() -> int:
    pid = find_pid()
    print(f"pid={pid}")
    h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        raise SystemExit(f"OpenProcess failed err={ctypes.get_last_error()}")
    needle = b"Client Synchronization"
    wide = "Client Synchronization".encode("utf-16le")
    on_sync = b"OnSynchronized: Character Attachments"
    on_sync_w = "OnSynchronized: Character Attachments".encode("utf-16le")
    found: list[str] = []
    mbi = MEMORY_BASIC_INFORMATION()
    addr = 0
    scanned = 0
    while kernel32.VirtualQueryEx(h, ctypes.c_uint64(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        base, size = mbi.BaseAddress, mbi.RegionSize
        nxt = base + size
        if (
            mbi.State == MEM_COMMIT
            and not (mbi.Protect & PAGE_NOACCESS)
            and not (mbi.Protect & PAGE_GUARD)
            and 0 < size <= 32 * 1024 * 1024
        ):
            buf = (ctypes.c_char * size)()
            nread = ctypes.c_size_t()
            if kernel32.ReadProcessMemory(
                h, ctypes.c_uint64(base), buf, size, ctypes.byref(nread)
            ) and nread.value:
                data = bytes(buf[: nread.value])
                scanned += nread.value
                for n in (needle, wide, on_sync, on_sync_w):
                    i = 0
                    while True:
                        j = data.find(n, i)
                        if j < 0:
                            break
                        chunk = data[j : j + 400]
                        ascii = re.sub(rb"[^ -~\n\t]", b".", chunk).decode("ascii", "replace")
                        found.append(ascii)
                        i = j + len(n)
                        if len(found) >= 12:
                            break
                if len(found) >= 12:
                    break
        addr = nxt
        if addr <= base:
            break
    kernel32.CloseHandle(h)
    print(f"scanned_bytes={scanned} samples={len(found)}")
    for s in found:
        print("---")
        print(s)
    # summarize latest-looking flags
    text = "\n".join(found)
    for name in (
        "Controller", "PlayerState", "InventoryManager", "CharacterAttachments",
        "WeaponsAttachments", "GameState", "LocalClientConfigs", "MapLevels",
    ):
        t = f"{name}: true" in text
        f = f"{name}: false" in text
        print(f"  {name}: true_seen={t} false_seen={f}")
    print(f"  OnSynchronized Character Attachments seen={'OnSynchronized: Character Attachments' in text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
