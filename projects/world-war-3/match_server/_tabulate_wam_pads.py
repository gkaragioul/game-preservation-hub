#!/usr/bin/env python3
"""Tabulate Pad_298 state across all live WAMs."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)
import subprocess
pid = int(subprocess.check_output([
    "powershell", "-NoProfile", "-Command",
    "(Get-Process WW3-Win64-Shipping -EA SilentlyContinue | Select -First 1).Id"
], text=True).strip())
h = k32.OpenProcess(0x0410, False, pid)
read = ctypes.c_size_t()


def rpm(addr, n):
    buf = (ctypes.c_char * n)()
    if not k32.ReadProcessMemory(
        h, ctypes.c_uint64(addr), buf, n, ctypes.byref(read)
    ):
        return None
    return bytes(buf[: read.value])


hMods = (ctypes.c_uint64 * 1024)()
needed = wt.DWORD()
psapi.EnumProcessModulesEx(h, hMods, ctypes.sizeof(hMods), ctypes.byref(needed), 3)
name = ctypes.create_unicode_buffer(260)
base = None
for i in range(min(needed.value // 8, 1024)):
    psapi.GetModuleBaseNameW(h, ctypes.c_uint64(hMods[i]), name, 260)
    if "WW3-Win64-Shipping" in name.value:
        base = hMods[i]
        break

go = rpm(base + 0x05F2C148, 0x20)
Objects = struct.unpack_from("<Q", go)[0]
Num = struct.unpack_from("<i", go, 0x14)[0]
NumChunks = struct.unpack_from("<i", go, 0x1C)[0]
chunks = struct.unpack("<" + str(NumChunks) + "Q", rpm(Objects, NumChunks * 8))


def get(idx):
    ci, ii = divmod(idx, 0x10000)
    c = chunks[ci]
    if not c:
        return None
    item = rpm(c + ii * 0x18, 8)
    return struct.unpack("<Q", item)[0] if item else None


known_wam_cls = None
print("comp Batch CA All Mesh Pad298(i0,i1,i2,i3) b2A4 i2B4 ptrs ownerName")
candidate_classes = {}
for idx in range(Num):
    obj = get(idx)
    if not obj:
        continue
    cls_raw = rpm(obj + 0x10, 8)
    if not cls_raw:
        continue
    cls = struct.unpack("<Q", cls_raw)[0]
    # Avoid stale hard-coded WAM addresses: identify live candidates by their
    # AttachmentManager layout, then keep only classes that recur.
    raw = rpm(obj, 0x4C0)
    if not raw:
        continue
    bid = struct.unpack_from("<I", raw, 0x2B8)[0]
    cab = struct.unpack_from("<I", raw, 0x2E0)[0]
    alln = struct.unpack_from("<i", raw, 0x1C0)[0]
    meshdel = struct.unpack_from("<i", raw, 0x380)[0]
    owner = struct.unpack_from("<Q", raw, 0x4A8)[0]
    if bid not in (1, 2, 3) or not (0 < alln <= 32) or owner < 0x10000:
        continue
    candidate_classes[cls] = candidate_classes.get(cls, 0) + 1
    if known_wam_cls is None or candidate_classes[cls] >= 2:
        known_wam_cls = cls
    i0, i1, i2, i3 = struct.unpack_from("<iiii", raw, 0x298)
    b2a4 = raw[0x2A4:0x2A8].hex()
    i2b4 = struct.unpack_from("<i", raw, 0x2B4)[0]
    ptrs = sum(
        1
        for off in range(0x320, 0x350, 8)
        if struct.unpack_from("<Q", raw, off)[0]
    )
    oname = "?"
    if owner:
        on = rpm(owner + 0x18, 8)
        if on:
            oname = str(struct.unpack("<ii", on))
    print(
        f"{hex(obj)} {bid} {cab} {alln} {meshdel} "
        f"({i0},{i1},{i2},{i3}) {b2a4} {i2b4} ptrs={ptrs} {oname}"
    )
