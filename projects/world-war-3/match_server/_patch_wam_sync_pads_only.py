#!/usr/bin/env python3
"""Pad-only live patch of stuck WAM sync phase (no remote thread / no PE)."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import struct
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

STUCK = [0x28B3F060650, 0x28C70C17B30]
k32 = ctypes.WinDLL("kernel32", use_last_error=True)


def rpm(h, addr, n):
    buf = (ctypes.c_char * n)()
    read = ctypes.c_size_t()
    if not k32.ReadProcessMemory(
        h, ctypes.c_uint64(addr), buf, n, ctypes.byref(read)
    ):
        return None
    return bytes(buf[: read.value])


def wpm(h, addr, data: bytes) -> bool:
    written = ctypes.c_size_t()
    return bool(
        k32.WriteProcessMemory(
            h, ctypes.c_uint64(addr), data, len(data), ctypes.byref(written)
        )
    )


def pad_sum(h, wam):
    raw = rpm(h, wam, 0x4C0)
    i0, i1, i2, i3 = struct.unpack_from("<iiii", raw, 0x298)
    i2b4 = struct.unpack_from("<i", raw, 0x2B4)[0]
    b2a4 = raw[0x2A4:0x2A8].hex()
    ptrs = sum(
        1 for off in range(0x320, 0x350, 8) if struct.unpack_from("<Q", raw, off)[0]
    )
    alln = struct.unpack_from("<i", raw, 0x1C0)[0]
    return f"All={alln} ({i0},{i1},{i2},{i3}) b2A4={b2a4} i2B4={i2b4} p318={ptrs}"


def count_markers(h):
    needles = {
        "mag0": "BP_WP_Magazine_108_01_C_0".encode("utf-16le"),
        "sync7": "OnAttachmentManagerSynchronized() : 7 -".encode("utf-16le"),
        "wam_t": "WeaponsAttachments: true".encode("utf-16le"),
        "wam_f": "WeaponsAttachments: false".encode("utf-16le"),
        "onsync": ": OnSynchronized: Weapons Attachments".encode("utf-16le"),
    }
    counts = {k: 0 for k in needles}

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

    mbi = MBI()
    addr = 0
    read = ctypes.c_size_t()
    while k32.VirtualQueryEx(
        h, ctypes.c_uint64(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)
    ):
        b, size = mbi.BaseAddress, mbi.RegionSize
        nxt = b + size
        if (
            mbi.State == 0x1000
            and (mbi.Protect & 0xFF) in (2, 4, 8)
            and not (mbi.Protect & 0x100)
            and 0 < size <= 32 << 20
        ):
            left, off = size, 0
            while left > 0:
                n = min(1 << 20, left)
                buf = (ctypes.c_char * n)()
                if (
                    k32.ReadProcessMemory(
                        h, ctypes.c_uint64(b + off), buf, n, ctypes.byref(read)
                    )
                    and read.value
                ):
                    data = bytes(buf[: read.value])
                    for k, nd in needles.items():
                        counts[k] += data.count(nd)
                off += n
                left -= n
        addr = nxt
        if addr <= b:
            break
    return counts


def main():
    pid = int(
        subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-Process WW3-Win64-Shipping|Select -First 1).Id",
            ],
            text=True,
        ).strip()
    )
    h = k32.OpenProcess(0x0010 | 0x0020 | 0x0008 | 0x0400, False, pid)
    if not h:
        raise SystemExit(ctypes.get_last_error())
    print("pid", pid)
    print("BEFORE markers", count_markers(h))
    print("BEFORE pads")
    for w in STUCK:
        print(hex(w), pad_sum(h, w))

    for w in STUCK:
        assert wpm(h, w + 0x2A4, bytes([0x01, 0x01, 0x00, 0x00]))
        assert wpm(h, w + 0x2B4, struct.pack("<i", 2))
        assert wpm(h, w + 0x320, b"\x00" * 0x30)
        print("patched", hex(w), pad_sum(h, w))

    print("sleep 5s...")
    time.sleep(5)
    print("AFTER pads")
    for w in STUCK:
        print(hex(w), pad_sum(h, w))
    print("AFTER markers", count_markers(h))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
