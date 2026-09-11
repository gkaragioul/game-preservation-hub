#!/usr/bin/env python3
"""Fast partskins clear: dump Parts/Pad_3F0 BEFORE, patch, AFTER summarize, budgeted markers."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import struct
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

STUCK = [0x28B3F060650, 0x28C70C17B30]
OUT = Path(__file__).resolve().parent / "live_log" / "_partskins_clear_evidence.txt"
MARKER_BUDGET = 512 << 20  # 512 MiB scanned max
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
    if not raw:
        return "RPM_FAIL"
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
    psl_n = struct.unpack_from("<i", raw, 0x440)[0]
    main = struct.unpack_from("<Q", raw, 0x428)[0]
    return (
        f"All={alln} b2A4={b2a4} i2B4={i2b4} p318={p318} "
        f"PartsIdsN={parts_n} PartsTypesN={types_n} "
        f"Pad3F0n=({p3f8_n},{p408_n}) PartSkinsLoadedN={psl_n} MainSkin=0x{main:x}"
    )


def dump_parts_pad3f0(h, w):
    lines = []
    raw = rpm(h, w, 0x4C0)
    if not raw:
        return [f"WAM {hex(w)} RPM_FAIL"]
    lines.append(f"### WAM {hex(w)}")
    # DirectReplicatedSkinsIds @ 0x3C8: MainId u16, pad, Parts.AttachmentsIds TArray @ +0x08 = 0x3D0
    main_id = struct.unpack_from("<H", raw, 0x3C8)[0]
    parts_data = struct.unpack_from("<Q", raw, 0x3D0)[0]
    parts_n = struct.unpack_from("<i", raw, 0x3D8)[0]
    parts_m = struct.unpack_from("<i", raw, 0x3DC)[0]
    types_data = struct.unpack_from("<Q", raw, 0x3E0)[0]
    types_n = struct.unpack_from("<i", raw, 0x3E8)[0]
    types_m = struct.unpack_from("<i", raw, 0x3EC)[0]
    lines.append(f"  DirectReplicatedSkinsIds.MainId={main_id} (0x{main_id:x})")
    lines.append(
        f"  Parts.AttachmentsIds data=0x{parts_data:x} num={parts_n} max={parts_m}"
    )
    if parts_data and 0 < parts_n <= 64:
        blob = rpm(h, parts_data, parts_n * 2)
        if blob:
            ids = struct.unpack("<" + str(parts_n) + "H", blob)
            lines.append(f"  Parts.AttachmentsIds={ids} hex={[hex(x) for x in ids]}")
    lines.append(f"  Parts.ItemTypes data=0x{types_data:x} num={types_n} max={types_m}")
    if types_data and 0 < types_n <= 64:
        blob = rpm(h, types_data, types_n)
        if blob:
            lines.append(f"  Parts.ItemTypes={list(blob)}")
    # Pad_3F0 @ 0x3F0
    lines.append(f"  Pad_3F0 raw={raw[0x3F0:0x428].hex()}")
    lead = struct.unpack_from("<H", raw, 0x3F0)[0]
    lines.append(f"  Pad_3F0 lead_u16=0x{lead:x}")
    a_data = struct.unpack_from("<Q", raw, 0x3F8)[0]
    a_n = struct.unpack_from("<i", raw, 0x400)[0]
    a_m = struct.unpack_from("<i", raw, 0x404)[0]
    b_data = struct.unpack_from("<Q", raw, 0x408)[0]
    b_n = struct.unpack_from("<i", raw, 0x410)[0]
    b_m = struct.unpack_from("<i", raw, 0x414)[0]
    sp0 = struct.unpack_from("<Q", raw, 0x418)[0]
    sp1 = struct.unpack_from("<Q", raw, 0x420)[0]
    lines.append(f"  Pad_3F0 arrA data=0x{a_data:x} num={a_n} max={a_m}")
    if a_data and 0 < a_n <= 64:
        blob = rpm(h, a_data, a_n * 2)
        if blob and len(blob) >= a_n * 2:
            ids = struct.unpack("<" + str(a_n) + "H", blob[: a_n * 2])
            lines.append(f"  Pad_3F0 arrA={ids} hex={[hex(x) for x in ids]}")
    lines.append(f"  Pad_3F0 arrB data=0x{b_data:x} num={b_n} max={b_m}")
    if b_data and 0 < b_n <= 64:
        blob = rpm(h, b_data, min(b_n * 8, 512))
        if blob:
            lines.append(f"  Pad_3F0 arrB raw={blob.hex()}")
    lines.append(f"  Pad_3F0 TSharedPtr=({hex(sp0)}, {hex(sp1)})")
    lines.append(f"  summarize: {summarize(h, w)}")
    return lines


def zero_tarray_num(h, wam, num_off):
    return wpm(h, wam + num_off, struct.pack("<ii", 0, 0))


def markers_budgeted(h, budget=MARKER_BUDGET):
    needles = {
        "mag0": "BP_WP_Magazine_108_01_C_0".encode("utf-16le"),
        "sync7": "OnAttachmentManagerSynchronized() : 7 -".encode("utf-16le"),
        "wam_t": "WeaponsAttachments: true".encode("utf-16le"),
        "wam_f": "WeaponsAttachments: false".encode("utf-16le"),
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
    counts["_scanned_bytes"] = scanned
    counts["_budget"] = budget
    return counts


def main():
    lines = []
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
        raise SystemExit("no WW3-Win64-Shipping process")
    h = k32.OpenProcess(0x0010 | 0x0020 | 0x0008 | 0x0400, False, pid)
    if not h:
        raise SystemExit(f"OpenProcess failed err={ctypes.get_last_error()}")
    lines.append(f"# partskins clear evidence")
    lines.append(f"# pid={pid}")
    lines.append("")
    lines.append("## BEFORE Parts / Pad_3F0 dump")
    for w in STUCK:
        lines.extend(dump_parts_pad3f0(h, w))
        lines.append("")
    print("\n".join(lines[-20:]), flush=True)

    lines.append("## BEFORE summarize")
    for w in STUCK:
        s = summarize(h, w)
        lines.append(f"{hex(w)} {s}")
        print("BEFORE", hex(w), s, flush=True)

    for w in STUCK:
        zero_tarray_num(h, w, 0x3D8)
        zero_tarray_num(h, w, 0x3E8)
        zero_tarray_num(h, w, 0x400)
        zero_tarray_num(h, w, 0x410)
        wpm(h, w + 0x418, b"\x00" * 16)
        wpm(h, w + 0x2A4, bytes([0x01, 0x01, 0x00, 0x00]))
        wpm(h, w + 0x2B4, struct.pack("<i", 2))
        wpm(h, w + 0x320, b"\x00" * 0x30)
        s = summarize(h, w)
        lines.append(f"patched {hex(w)} {s}")
        print("patched", hex(w), s, flush=True)

    time.sleep(5)
    lines.append("")
    lines.append("## AFTER 5s summarize")
    for w in STUCK:
        s = summarize(h, w)
        lines.append(f"{hex(w)} {s}")
        print("AFTER", hex(w), s, flush=True)

    lines.append("")
    lines.append("## AFTER Parts / Pad_3F0 dump")
    for w in STUCK:
        lines.extend(dump_parts_pad3f0(h, w))
        lines.append("")

    print("scanning markers (budgeted)...", flush=True)
    m = markers_budgeted(h)
    lines.append(f"## markers (budgeted) {m}")
    print("markers", m, flush=True)

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", OUT, flush=True)
    k32.CloseHandle(h)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
