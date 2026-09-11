#!/usr/bin/env python3
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)
h = k32.OpenProcess(0x0410, False, 29480)
read = ctypes.c_size_t()


def rpm(addr, n):
    buf = (ctypes.c_char * n)()
    if not k32.ReadProcessMemory(
        h, ctypes.c_uint64(addr), buf, n, ctypes.byref(read)
    ):
        return None
    return bytes(buf[: read.value])


class MODULEINFO(ctypes.Structure):
    _fields_ = [
        ("lpBaseOfDll", ctypes.c_void_p),
        ("SizeOfImage", wt.DWORD),
        ("EntryPoint", ctypes.c_void_p),
    ]


hMods = (ctypes.c_uint64 * 1024)()
needed = wt.DWORD()
psapi.EnumProcessModulesEx(h, hMods, ctypes.sizeof(hMods), ctypes.byref(needed), 3)
name = ctypes.create_unicode_buffer(260)
base = size = None
for i in range(min(needed.value // 8, 1024)):
    psapi.GetModuleBaseNameW(h, ctypes.c_uint64(hMods[i]), name, 260)
    if "WW3-Win64-Shipping" in name.value:
        mi = MODULEINFO()
        psapi.GetModuleInformation(
            h, ctypes.c_uint64(hMods[i]), ctypes.byref(mi), ctypes.sizeof(mi)
        )
        base, size = hMods[i], mi.SizeOfImage
        break
print("module", hex(base), hex(size))


def looks_uobject(addr):
    r = rpm(addr, 0x28)
    if not r:
        return False
    vt = struct.unpack_from("<Q", r, 0)[0]
    cls = struct.unpack_from("<Q", r, 0x10)[0]
    return base <= vt < base + size and cls > 0x10000


wam = 0x28B3F060650
raw = rpm(wam, 0x4C0)
all_data = struct.unpack_from("<Q", raw, 0x1B8)[0]
all_n = struct.unpack_from("<i", raw, 0x1C0)[0]
att_objs = set(struct.unpack("<" + str(all_n) + "Q", rpm(all_data, all_n * 8)))
ids_data = struct.unpack_from("<Q", raw, 0x1C8)[0]
ids = struct.unpack("<" + str(all_n) + "H", rpm(ids_data, all_n * 2))
att_by_ptr = {p: ids[i] for i, p in enumerate(struct.unpack("<" + str(all_n) + "Q", rpm(all_data, all_n * 8)))}
print("WAM atts", {hex(p): i for p, i in att_by_ptr.items()})

for label, a in [
    ("s0", 0x28C74C91AE0),
    ("s1", 0x28C74C90910),
    ("s2", 0x28C74C920E0),
]:
    raw = rpm(a, 0x80)
    data, num, mx = struct.unpack_from("<Qii", raw, 0)
    print(f"=== {label} @{hex(a)} data={hex(data)} num={num} max={mx}")
    ptrs = struct.unpack("<" + str(num) + "Q", rpm(data, num * 8))
    for i, p in enumerate(ptrs):
        u = looks_uobject(p)
        info = ""
        if u:
            r = rpm(p, 0x28)
            n = struct.unpack_from("<ii", r, 0x18)
            cls = struct.unpack_from("<Q", r, 0x10)[0]
            ci = struct.unpack_from("<i", rpm(cls + 0xC, 4))[0]
            info = f" UObject Name={n} ClassIdx={ci} attId={att_by_ptr.get(p)}"
        else:
            # maybe pair of ints / soft path
            r = rpm(p, 16)
            info = f" raw16={r.hex() if r else None}"
        print(f"  [{i}] {hex(p)} uobj={u}{info}")
