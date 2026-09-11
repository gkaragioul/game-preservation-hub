#!/usr/bin/env python3
"""Look for mid-flight OnAttachmentManagerSynchronized pending strings (UTF-16)."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import re
import subprocess

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
RW_PROTECTS = (0x04, 0x08, 0x40, 0x80)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class MBI(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_uint64),
        ("AllocationBase", ctypes.c_uint64),
        ("AllocationProtect", wt.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wt.DWORD),
        ("Protect", wt.DWORD),
        ("Type", wt.DWORD),
    ]


def main():
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process WW3-Win64-Shipping -EA SilentlyContinue | Select -First 1).Id"],
        capture_output=True, text=True, check=False,
    )
    pid = int(r.stdout.strip())
    print(f"pid={pid}")
    h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    needles = [
        "OnAttachmentManagerSynchronized()".encode("utf-16le"),
        "OnAttachmentManagerSynchronized".encode("utf-16le"),
        "BP_WP_Rail_086_01_C_0".encode("utf-16le"),
        "BP_WP_Magazine_108_01_C_0".encode("utf-16le"),
        "OnSynchronized: Weapons".encode("utf-16le"),
        "OnSynchronized: Inventory".encode("utf-16le"),
    ]
    found = []
    mbi = MBI()
    addr = 0
    read = ctypes.c_size_t()
    while kernel32.VirtualQueryEx(h, ctypes.c_uint64(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        base, size = mbi.BaseAddress, mbi.RegionSize
        nxt = base + size
        if (mbi.State == MEM_COMMIT and mbi.Protect in RW_PROTECTS
                and not (mbi.Protect & PAGE_GUARD) and 0 < size <= 64 * 1024 * 1024):
            buf = (ctypes.c_char * size)()
            if kernel32.ReadProcessMemory(h, ctypes.c_uint64(base), buf, size, ctypes.byref(read)) and read.value:
                data = bytes(buf[: read.value])
                for n in needles:
                    i = 0
                    while True:
                        j = data.find(n, i)
                        if j < 0:
                            break
                        # decode nearby utf16
                        start = j
                        while start >= 2 and (data[start - 2] | data[start - 1] << 8) != 0:
                            start -= 2
                            if j - start > 200:
                                break
                        end = j
                        while end + 1 < len(data) and (data[end] | data[end + 1] << 8) != 0:
                            end += 2
                            if end - j > 300:
                                break
                        s = data[start:end].decode("utf-16le", "replace")
                        found.append(s)
                        i = j + len(n)
                        if len(found) >= 30:
                            break
                if len(found) >= 30:
                    break
        addr = nxt
        if addr <= base:
            break
    kernel32.CloseHandle(h)
    print(f"hits={len(found)}")
    for s in found:
        print("---")
        print(s)


if __name__ == "__main__":
    main()
