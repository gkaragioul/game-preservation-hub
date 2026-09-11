#!/usr/bin/env python3
"""Clear ghost DirectReplicatedSkinsIds.Parts (0xFFFF x3) + Pad_3F0 pending on stuck WAMs."""
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


def summarize(h, w):
    raw = rpm(h, w, 0x4C0)
    i2b4 = struct.unpack_from("<i", raw, 0x2B4)[0]
    b2a4 = raw[0x2A4:0x2A8].hex()
    parts_n = struct.unpack_from("<i", raw, 0x3D8)[0]
    types_n = struct.unpack_from("<i", raw, 0x3E8)[0]
    p3f8_n = struct.unpack_from("<i", raw, 0x400)[0]
    p408_n = struct.unpack_from("<i", raw, 0x410)[0]
    p318 = sum(
        1 for off in range(0x320, 0x350, 8) if struct.unpack_from("<Q", raw, off)[0]
    )
    alln = struct.unpack_from("<i", raw, 0x1C0)[0]
    return (
        f"All={alln} b2A4={b2a4} i2B4={i2b4} p318={p318} "
        f"PartsIdsN={parts_n} PartsTypesN={types_n} "
        f"Pad3F0n=({p3f8_n},{p408_n})"
    )


def zero_tarray_num(h, wam, num_off):
    """Set TArray Num (and Max) to 0 at wam+num_off-8 for Data... wait Num at +8."""
    # TArray: Data@0 Num@8 Max@12 relative to start
    # num_off is absolute offset of Num field within WAM
    return wpm(h, wam + num_off, struct.pack("<ii", 0, 0))


MARKER_BUDGET = 512 << 20  # 512 MiB — avoid multi-minute full-heap hangs


def dump_parts_pad3f0(h, w):
    """Print DirectReplicatedSkinsIds.Parts + Pad_3F0 contents."""
    raw = rpm(h, w, 0x4C0)
    if not raw:
        print(hex(w), "RPM_FAIL")
        return
    main_id = struct.unpack_from("<H", raw, 0x3C8)[0]
    parts_data = struct.unpack_from("<Q", raw, 0x3D0)[0]
    parts_n = struct.unpack_from("<i", raw, 0x3D8)[0]
    types_data = struct.unpack_from("<Q", raw, 0x3E0)[0]
    types_n = struct.unpack_from("<i", raw, 0x3E8)[0]
    print(
        f"  {hex(w)} MainId={main_id:#x} PartsN={parts_n} TypesN={types_n}"
    )
    if parts_data and 0 < parts_n <= 64:
        blob = rpm(h, parts_data, parts_n * 2)
        if blob:
            ids = struct.unpack("<" + str(parts_n) + "H", blob)
            print(f"  Parts.AttachmentsIds={ids} {[hex(x) for x in ids]}")
    if types_data and 0 < types_n <= 64:
        blob = rpm(h, types_data, types_n)
        if blob:
            print(f"  Parts.ItemTypes={list(blob)}")
    lead = struct.unpack_from("<H", raw, 0x3F0)[0]
    a_data = struct.unpack_from("<Q", raw, 0x3F8)[0]
    a_n = struct.unpack_from("<i", raw, 0x400)[0]
    b_data = struct.unpack_from("<Q", raw, 0x408)[0]
    b_n = struct.unpack_from("<i", raw, 0x410)[0]
    sp0 = struct.unpack_from("<Q", raw, 0x418)[0]
    sp1 = struct.unpack_from("<Q", raw, 0x420)[0]
    print(
        f"  Pad_3F0 lead={lead:#x} arrA(n={a_n})@{hex(a_data)} "
        f"arrB(n={b_n})@{hex(b_data)} tsp=({hex(sp0)},{hex(sp1)})"
    )
    if a_data and 0 < a_n <= 64:
        blob = rpm(h, a_data, a_n * 2)
        if blob and len(blob) >= a_n * 2:
            ids = struct.unpack("<" + str(a_n) + "H", blob[: a_n * 2])
            print(f"  Pad_3F0 arrA={ids} {[hex(x) for x in ids]}")


def markers(h, budget=MARKER_BUDGET):
    needles = {
        "mag0": "BP_WP_Magazine_108_01_C_0".encode("utf-16le"),
        "sync7": "OnAttachmentManagerSynchronized() : 7 -".encode("utf-16le"),
        "wam_t": "WeaponsAttachments: true".encode("utf-16le"),
        "onsync": ": OnSynchronized: Weapons Attachments".encode("utf-16le"),
    }
    counts = {k: 0 for k in needles}
    scanned = 0

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
            while left > 0 and scanned < budget:
                n = min(1 << 20, left, budget - scanned)
                buf = (ctypes.c_char * n)()
                if (
                    k32.ReadProcessMemory(
                        h, ctypes.c_uint64(b + off), buf, n, ctypes.byref(read)
                    )
                    and read.value
                ):
                    data = bytes(buf[: read.value])
                    scanned += len(data)
                    for k, nd in needles.items():
                        counts[k] += data.count(nd)
                off += n
                left -= n
            if scanned >= budget:
                break
        addr = nxt
        if addr <= b:
            break
    counts["_scanned"] = scanned
    return counts


def main():
    pid = int(
        subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-Process WW3-Win64-Shipping -EA SilentlyContinue|Select -First 1).Id",
            ],
            text=True,
        ).strip()
        or "0"
    )
    if not pid:
        raise SystemExit("no WW3-Win64-Shipping")
    h = k32.OpenProcess(0x0010 | 0x0020 | 0x0008 | 0x0400, False, pid)
    if not h:
        raise SystemExit(ctypes.get_last_error())
    print("pid", pid, flush=True)
    print("BEFORE Parts/Pad_3F0", flush=True)
    for w in STUCK:
        dump_parts_pad3f0(h, w)
    print("BEFORE summarize", flush=True)
    for w in STUCK:
        print(hex(w), summarize(h, w), flush=True)

    for w in STUCK:
        # Zero Parts.AttachmentsIds Num/Max @ 0x3D8
        zero_tarray_num(h, w, 0x3D8)
        # Zero Parts.ItemTypes Num/Max @ 0x3E8
        zero_tarray_num(h, w, 0x3E8)
        # Zero Pad_3F0 mirror arrays @ 0x400 and 0x410
        zero_tarray_num(h, w, 0x400)
        zero_tarray_num(h, w, 0x410)
        # Clear Pad_3F0 trailing TSharedPtr pair
        wpm(h, w + 0x418, b"\x00" * 16)
        # Re-apply done-like sync phase
        wpm(h, w + 0x2A4, bytes([0x01, 0x01, 0x00, 0x00]))
        wpm(h, w + 0x2B4, struct.pack("<i", 2))
        wpm(h, w + 0x320, b"\x00" * 0x30)
        print("patched", hex(w), summarize(h, w), flush=True)

    time.sleep(5)
    print("AFTER 5s", flush=True)
    for w in STUCK:
        print(hex(w), summarize(h, w), flush=True)
        dump_parts_pad3f0(h, w)
    print("markers (budgeted)...", flush=True)
    print("markers", markers(h), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
