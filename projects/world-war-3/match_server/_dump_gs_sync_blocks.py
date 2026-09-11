#!/usr/bin/env python3
"""Dump GameSingleton bBlock* + WAM Pad_298/318 sync gate (read-only).

Usage:
  python match_server/_dump_gs_sync_blocks.py
  python match_server/_dump_gs_sync_blocks.py --pid 29480

Writes: match_server/live_log/_gs_sync_blocks_dump.txt
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import datetime as dt
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "live_log" / "_gs_sync_blocks_dump.txt"

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
DATA_PROTECTS = (0x02, 0x04, 0x08)
CHUNK = 1 << 20

GOBJECTS_OFF = 0x05F2C148
GWORLD_OFF = 0x06020BC8
ELEMENTS_PER_CHUNK = 0x10000
# Dump-time Class WW3.WW3GameSingleton index (stable across same build boots).
GS_CLASS_INDEX = 0x4A7

EARLY8 = (151, 4638, 304, 101, 4606, 4608, 88, 7851)
EARLY8_BYTES = b"".join(struct.pack("<H", x) for x in EARLY8)

GS_BLOCKS = [
    (0x118, "bForceAttachmentsAttached"),
    (0x119, "bForceAttachmentsDetached"),
    (0x11A, "bPrintAMComplexity"),
    (0x11B, "bPrintAMVisibility"),
    (0x11C, "bBlockOnPreviewAttachmentLoaded"),
    (0x11D, "bBlockOnRealAttachmentLoaded"),
    (0x11E, "bBlockCreateAttachmentStructureAndRebuild"),
    (0x11F, "bBlockRebuildAllAttachments"),
    (0x120, "bBlockOnAttachmentMeshesLoaded"),
    (0x121, "bBlockCreateAttachments"),
    (0x122, "bBlockTryToInitializeAttachments"),
    (0x123, "bBlockInitializeAttachments"),
    (0x124, "bBlockCheckAttachmentsSynchronized"),
    (0x125, "bBlockOnAttachmentsFullySynchronized"),
    (0x126, "bBlockOnCharacterAttachmentsFullySynchronized"),
    (0x127, "bBlockOnWeaponAttachmentsFullySynchronized"),
    (0x128, "bBlockOnVehicleAttachmentsFullySynchronized"),
]

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)


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


def find_pid() -> int:
    r = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "(Get-Process WW3-Win64-Shipping -EA SilentlyContinue | Select -First 1).Id",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    s = (r.stdout or "").strip()
    if not s:
        raise SystemExit("WW3-Win64-Shipping not running")
    return int(s)


def rpm(h, addr: int, n: int) -> bytes | None:
    buf = (ctypes.c_char * n)()
    read = ctypes.c_size_t()
    if not kernel32.ReadProcessMemory(
        h, ctypes.c_uint64(addr), buf, n, ctypes.byref(read)
    ):
        return None
    return bytes(buf[: read.value])


def module_base(h) -> int:
    hMods = (ctypes.c_uint64 * 1024)()
    needed = wt.DWORD()
    psapi.EnumProcessModulesEx(
        h, hMods, ctypes.sizeof(hMods), ctypes.byref(needed), 0x03
    )
    name = ctypes.create_unicode_buffer(260)
    for i in range(min(needed.value // 8, 1024)):
        psapi.GetModuleBaseNameW(h, ctypes.c_uint64(hMods[i]), name, 260)
        if "WW3-Win64-Shipping" in name.value:
            return int(hMods[i])
    raise SystemExit("module base not found")


def gobjects_table(h, base: int):
    go = rpm(h, base + GOBJECTS_OFF, 0x20)
    if not go:
        raise SystemExit("GObjects unreadable")
    Objects, _Max, NumElements, _MaxChunks, NumChunks = struct.unpack_from(
        "<Q8xiiii", go
    )
    chunks = struct.unpack(
        "<" + str(NumChunks) + "Q", rpm(h, Objects, NumChunks * 8) or b""
    )

    def get_by_index(idx: int) -> int | None:
        if idx < 0 or idx >= NumElements:
            return None
        ci = idx // ELEMENTS_PER_CHUNK
        ii = idx % ELEMENTS_PER_CHUNK
        chunk = chunks[ci]
        if not chunk:
            return None
        item = rpm(h, chunk + ii * 0x18, 8)
        if not item:
            return None
        return struct.unpack("<Q", item)[0]

    return NumElements, get_by_index


def scan_wams(h) -> list[int]:
    early: list[int] = []
    mbi = MBI()
    addr = 0
    read = ctypes.c_size_t()
    while kernel32.VirtualQueryEx(
        h, ctypes.c_uint64(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)
    ):
        base, size = mbi.BaseAddress, mbi.RegionSize
        nxt = base + size
        if (
            mbi.State == MEM_COMMIT
            and (mbi.Protect & 0xFF) in DATA_PROTECTS
            and not (mbi.Protect & PAGE_GUARD)
            and 0 < size <= 64 << 20
        ):
            left, off = size, 0
            while left > 0:
                n = min(CHUNK, left)
                buf = (ctypes.c_char * n)()
                if (
                    kernel32.ReadProcessMemory(
                        h, ctypes.c_uint64(base + off), buf, n, ctypes.byref(read)
                    )
                    and read.value
                ):
                    data = bytes(buf[: read.value])
                    i = 0
                    while True:
                        j = data.find(EARLY8_BYTES, i)
                        if j < 0:
                            break
                        early.append(base + off + j)
                        i = j + 2
                        if len(early) >= 16:
                            break
                off += n
                left -= n
        addr = nxt
        if addr <= base or len(early) >= 16:
            break

    want = {t: struct.pack("<Q", t) for t in early}
    headers: list[int] = []
    addr = 0
    while kernel32.VirtualQueryEx(
        h, ctypes.c_uint64(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)
    ):
        base, size = mbi.BaseAddress, mbi.RegionSize
        nxt = base + size
        if (
            mbi.State == MEM_COMMIT
            and (mbi.Protect & 0xFF) in DATA_PROTECTS
            and not (mbi.Protect & PAGE_GUARD)
            and 0 < size <= 64 << 20
        ):
            left, off = size, 0
            while left > 0:
                n = min(CHUNK, left)
                buf = (ctypes.c_char * n)()
                if (
                    kernel32.ReadProcessMemory(
                        h, ctypes.c_uint64(base + off), buf, n, ctypes.byref(read)
                    )
                    and read.value
                ):
                    data = bytes(buf[: read.value])
                    abs_base = base + off
                    for t, pat in want.items():
                        i = 0
                        while True:
                            j = data.find(pat, i)
                            if j < 0:
                                break
                            if j + 16 <= len(data):
                                num, mx = struct.unpack_from("<ii", data, j + 8)
                                if num == 8 and mx >= 8:
                                    headers.append(abs_base + j)
                            i = j + 8
                off += n
                left -= n
        addr = nxt
        if addr <= base:
            break

    wams: list[int] = []
    for hdr in headers:
        batch = hdr - 0x08
        raw = rpm(h, batch, 0x30)
        if not raw:
            continue
        batch_id = struct.unpack_from("<I", raw, 0)[0]
        ids_num = struct.unpack_from("<i", raw, 0x10)[0]
        if batch_id not in (1, 2) or ids_num != 8:
            continue
        comp = batch - 0x2B8
        raw2 = rpm(h, comp, 0x4C0)
        if not raw2:
            continue
        all_obj_num = struct.unpack_from("<i", raw2, 0x1C0)[0]
        owner = struct.unpack_from("<Q", raw2, 0x4A8)[0]
        base_mesh = struct.unpack_from("<Q", raw2, 0x1B0)[0]
        if owner < 0x10000 or base_mesh < 0x10000:
            continue
        if not (0 <= all_obj_num <= 32):
            continue
        if comp not in wams:
            wams.append(comp)
    return wams


def dump_pad_hex(label: str, blob: bytes, base_off: int, lines: list[str]) -> None:
    lines.append(f"  {label} hex={blob.hex()}")
    lines.append(f"  {label} bytes={list(blob[: min(32, len(blob))])}")
    for i in range(0, len(blob), 8):
        chunk = blob[i : i + 8]
        if len(chunk) < 8:
            break
        q = struct.unpack_from("<Q", chunk, 0)[0]
        i0, i1 = struct.unpack_from("<ii", chunk, 0)
        lines.append(
            f"    +0x{base_off + i:X}: u64=0x{q:x} i32=({i0},{i1}) "
            f"bytes={list(chunk)}"
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, default=0)
    args = ap.parse_args()
    pid = args.pid or find_pid()
    h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        raise SystemExit(f"OpenProcess failed pid={pid}")

    lines: list[str] = []
    out = lines.append
    out("# GameSingleton bBlock* + WAM Pad_298/318 sync dump")
    out(f"# time={dt.datetime.now().isoformat(timespec='seconds')} pid={pid}")
    out("# PS_REBIND=0 locked; dump-only (no rematch)")
    out("")

    base = module_base(h)
    gw = rpm(h, base + GWORLD_OFF, 8)
    gworld = struct.unpack("<Q", gw)[0] if gw else 0
    out(f"## module base=0x{base:x} GWorld=0x{gworld:x}")

    NumElements, get_by_index = gobjects_table(h, base)
    cls = get_by_index(GS_CLASS_INDEX)
    out(f"## GObjects Num={NumElements} ClassWW3GameSingleton@idx0x4A7=0x{cls:x}" if cls else "## Class missing")
    out("")

    hits: list[tuple[int, int]] = []
    if cls:
        for idx in range(NumElements):
            obj = get_by_index(idx)
            if not obj:
                continue
            r = rpm(h, obj + 0x10, 8)
            if not r:
                continue
            if struct.unpack("<Q", r)[0] == cls:
                hits.append((idx, obj))

    out(f"## GameSingleton instances: {len(hits)}")
    any_block = False
    for idx, obj in hits:
        oflags = struct.unpack("<I", rpm(h, obj + 0x8, 4) or b"\0\0\0\0")[0]
        iidx = struct.unpack("<i", rpm(h, obj + 0xC, 4) or b"\0\0\0\0")[0]
        nidx, nnum = struct.unpack("<ii", rpm(h, obj + 0x18, 8) or b"\0" * 8)
        outer = struct.unpack("<Q", rpm(h, obj + 0x20, 8) or b"\0" * 8)[0]
        season = (rpm(h, obj + 0x28, 1) or b"\0")[0]
        blocks = rpm(h, obj + 0x118, 0x11) or b"\0" * 0x11
        out(
            f"### GS @0x{obj:x} idx={idx} Internal={iidx} flags=0x{oflags:x} "
            f"Name=({nidx},{nnum}) Outer=0x{outer:x} ActiveSeason={season}"
        )
        for off, nm in GS_BLOCKS:
            v = blocks[off - 0x118]
            mark = " <<<" if v else ""
            if v:
                any_block = True
            out(f"  {nm}@0x{off:X}={v}{mark}")
    out("")
    out(f"## any GameSingleton bBlock* set? {'YES' if any_block else 'NO (all 0)'}")
    out("")

    wams = scan_wams(h)
    out(f"## early8 WAMs: {len(wams)}")
    for comp in wams[:8]:
        raw = rpm(h, comp, 0x4C0)
        if not raw:
            continue
        batch_id = struct.unpack_from("<I", raw, 0x2B8)[0]
        cab_id = struct.unpack_from("<I", raw, 0x2E0)[0]
        all_obj_num = struct.unpack_from("<i", raw, 0x1C0)[0]
        all_ids_num = struct.unpack_from("<i", raw, 0x1D0)[0]
        owner = struct.unpack_from("<Q", raw, 0x4A8)[0]
        base_mesh = struct.unpack_from("<Q", raw, 0x1B0)[0]
        main_skin = struct.unpack_from("<Q", raw, 0x428)[0]
        tmp_n = struct.unpack_from("<i", raw, 0x310)[0]
        mesh_n = struct.unpack_from("<i", raw, 0x380)[0]
        parent_n = struct.unpack_from("<i", raw, 0x370)[0]
        as_data, as_num, as_max = struct.unpack_from("<Qii", raw, 0x288)
        fv_n = struct.unpack_from("<i", raw, 0x358)[0]
        out(f"### WAM @0x{comp:x}")
        out(
            f"  BatchID={batch_id} ClientApplied={cab_id} "
            f"AllObj={all_obj_num} AllIds={all_ids_num} Owner=0x{owner:x} "
            f"BaseMesh=0x{base_mesh:x} MainSkin=0x{main_skin:x}"
        )
        out(
            f"  AttachmentsStructure num={as_num}/{as_max} data=0x{as_data:x} "
            f"Temporary={tmp_n} MeshDelegates={mesh_n} ParentMesh={parent_n} "
            f"ForcedVisibility={fv_n}"
        )
        dump_pad_hex("Pad_298", raw[0x298:0x2B8], 0x298, lines)
        dump_pad_hex("Pad_318", raw[0x318:0x350], 0x318, lines)
        # Pad_388 (between mesh delegates and fire types)
        dump_pad_hex("Pad_388", raw[0x388:0x398], 0x388, lines)
        dump_pad_hex("Pad_3A8", raw[0x3A8:0x3C2], 0x3A8, lines)
        dump_pad_hex("Pad_3F0", raw[0x3F0:0x428], 0x3F0, lines)

    out("")
    out("## Interpretation")
    if not any_block:
        out(
            "  GameSingleton bBlockCheck*/bBlockOnWeapon* are ALL CLEAR — "
            "sync notify gap is NOT a GameSingleton debug block."
        )
        out(
            "  Next focus: Pad_298/318 (unknown pending/sync state between "
            "AttachmentsStructure and ReplicatedBatch / after Temporary)."
        )
    else:
        out("  One or more GameSingleton bBlock* flags are SET — clear via cheat/env or WriteProcessMemory.")
    out("  REMATCH: only if a concrete Pad/flag fix needs a fresh session.")

    kernel32.CloseHandle(h)
    text = "\n".join(lines) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
