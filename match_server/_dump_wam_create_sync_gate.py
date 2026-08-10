#!/usr/bin/env python3
"""Dump WAM CreateAttachment / Synchronized gate state (read-only, no rematch).

Corrects Mag*_C_0 UTF-16 false negative: SoftClass NewObject stores FName
(ComparisonIndex, Number=1) which ToString's as Class_0 only when logged.
Live Mag SoftClass UObjects can exist with Mag*_C_0 string hits=0.

Usage:
  python match_server/_dump_wam_create_sync_gate.py
  python match_server/_dump_wam_create_sync_gate.py --pid 29480

Writes: match_server/live_log/_wam_create_sync_gate_dump.txt
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
OUT = HERE / "live_log" / "_wam_create_sync_gate_dump.txt"

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
DATA_PROTECTS = (0x02, 0x04, 0x08)

# Capture early Glock SoftClass catalog (hist opens).
EARLY8 = (151, 4638, 304, 101, 4606, 4608, 88, 7851)
EARLY8_BYTES = b"".join(struct.pack("<H", x) for x in EARLY8)

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
CHUNK = 1 << 20


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
    out(f"# WAM CreateAttachment / Synchronized gate dump")
    out(f"# time={dt.datetime.now().isoformat(timespec='seconds')} pid={pid}")
    out(f"# PS_REBIND=0 locked; dump-only (no rematch)")
    out(f"# early8 catalog={EARLY8}")
    out("")

    # Pass 1: find packed early8 AttachmentIds arrays
    early_data: list[int] = []
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
                        early_data.append(base + off + j)
                        i = j + 2
                        if len(early_data) >= 24:
                            break
                off += n
                left -= n
        addr = nxt
        if addr <= base or len(early_data) >= 24:
            break

    out(f"## early8 AttachmentIds packed arrays: {len(early_data)}")
    for a in early_data[:12]:
        out(f"  @0x{a:x}")

    # Pass 2: TArray headers pointing at those arrays (Num==8)
    want = {t: struct.pack("<Q", t) for t in early_data}
    headers: dict[int, list[int]] = {t: [] for t in early_data}
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
                                    headers[t].append(abs_base + j)
                            i = j + 8
                            if len(headers[t]) >= 4:
                                break
                off += n
                left -= n
        addr = nxt
        if addr <= base:
            break

    out("")
    out("## WAM ReplicatedBatch / ClientApplied / AllAttachmentObjects")
    valid = 0
    for t, hdrs in headers.items():
        for hdr in hdrs[:2]:
            batch = hdr - 0x08
            raw = rpm(h, batch, 0x80)
            if not raw or len(raw) < 0x48:
                continue
            batch_id = struct.unpack_from("<I", raw, 0)[0]
            num_rep = raw[4]
            ids_num = struct.unpack_from("<i", raw, 0x10)[0]
            rep_num = struct.unpack_from("<i", raw, 0x20)[0]
            cab_id = struct.unpack_from("<I", raw, 0x28)[0]
            cab_ids_num = struct.unpack_from("<i", raw, 0x38)[0]
            # Heuristic: live WAM ReplicatedBatch at component+0x2B8
            if batch_id not in (1, 2, 3) or ids_num != 8:
                continue
            comp = batch - 0x2B8
            raw2 = rpm(h, comp, 0x4C0)
            if not raw2 or len(raw2) < 0x4B0:
                continue
            all_obj_data, all_obj_num, _ = struct.unpack_from("<Qii", raw2, 0x1B8)
            all_ids_data, all_ids_num, _ = struct.unpack_from("<Qii", raw2, 0x1C8)
            base_mesh = struct.unpack_from("<Q", raw2, 0x1B0)[0]
            owner = struct.unpack_from("<Q", raw2, 0x4A8)[0]
            main_skin = struct.unpack_from("<Q", raw2, 0x428)[0]
            part_skin_data = struct.unpack_from("<Q", raw2, 0x438)[0]
            part_skin_num = struct.unpack_from("<i", raw2, 0x440)[0]
            part_skin_max = struct.unpack_from("<i", raw2, 0x444)[0]
            tmp_n = struct.unpack_from("<i", raw2, 0x310)[0]
            mesh_n = struct.unpack_from("<i", raw2, 0x380)[0]
            parent_n = struct.unpack_from("<i", raw2, 0x370)[0]
            # OwnerWeapon should be a heap pointer; reject garbage
            if owner < 0x10000 or base_mesh < 0x10000:
                continue
            if not (0 <= all_obj_num <= 32 and 0 <= all_ids_num <= 32):
                continue
            valid += 1
            out(f"### WAM @0x{comp:x} (batch@0x{batch:x})")
            out(
                f"  ReplicatedBatch BatchID={batch_id} NumRepAtt={num_rep} "
                f"AttIdsNum={ids_num} RepAttNum={rep_num}"
            )
            out(
                f"  ClientApplied   BatchID={cab_id} AttIdsNum={cab_ids_num}"
            )
            out(
                f"  OwnerWeapon=0x{owner:x} BaseMesh=0x{base_mesh:x} "
                f"MainSkinLoaded=0x{main_skin:x}"
            )
            out(
                f"  PartSkinsLoadedClasses=0x{part_skin_data:x} "
                f"num={part_skin_num} max={part_skin_max}"
            )
            out(
                f"  Pad298={raw2[0x298:0x2b8].hex()} "
                f"Pad318={raw2[0x318:0x350].hex()} "
                f"Pad3F0={raw2[0x3f0:0x428].hex()}"
            )
            out(
                f"  AllAttachmentObjects={all_obj_num} AllAttachmentsIds={all_ids_num} "
                f"Temporary={tmp_n} MeshDelegates={mesh_n} ParentMeshDelegates={parent_n}"
            )
            if all_ids_num > 0 and all_ids_data:
                ids_raw = rpm(h, all_ids_data, all_ids_num * 2)
                if ids_raw:
                    ids = struct.unpack("<" + str(all_ids_num) + "H", ids_raw)
                    out(f"  AllAttachmentsIds={ids}")
            if all_obj_num > 0 and all_obj_data:
                objs_raw = rpm(h, all_obj_data, all_obj_num * 8)
                if objs_raw:
                    objs = struct.unpack("<" + str(all_obj_num) + "Q", objs_raw)
                    ids = ()
                    if all_ids_num == all_obj_num and all_ids_data:
                        ir = rpm(h, all_ids_data, all_ids_num * 2)
                        if ir:
                            ids = struct.unpack("<" + str(all_ids_num) + "H", ir)
                    for i, op in enumerate(objs):
                        oid = ids[i] if i < len(ids) else -1
                        if not op:
                            out(f"  [{i}] id={oid} NULL")
                            continue
                        o = rpm(h, op, 0x1E8)
                        if not o:
                            out(f"  [{i}] id={oid} ptr=0x{op:x} unreadable")
                            continue
                        flags = struct.unpack_from("<I", o, 0x8)[0]
                        cls = struct.unpack_from("<Q", o, 0x10)[0]
                        nidx, nnum = struct.unpack_from("<ii", o, 0x18)
                        outer = struct.unpack_from("<Q", o, 0x20)[0]
                        my_am = struct.unpack_from("<Q", o, 0x1D0)[0]
                        bmc = struct.unpack_from("<Q", o, 0x1E0)[0]
                        out(
                            f"  [{i}] id={oid} obj=0x{op:x} Class=0x{cls:x} "
                            f"FName=({nidx},{nnum}) Outer=0x{outer:x} "
                            f"Flags=0x{flags:x} BaseMeshComp=0x{bmc:x} MyAM=0x{my_am:x}"
                        )
                        if oid == 151:
                            out(
                                f"       Mag FName Number={nnum} => ToString "
                                f"'Class_0' only when Synchronized logs; "
                                f"UTF-16 Mag*_C_0 may be absent"
                            )

    out("")
    out(f"## valid WAM dumps: {valid}")

    # String markers
    needles = {
        "mag0": "BP_WP_Magazine_108_01_C_0",
        "mag_c": "BP_WP_Magazine_108_01_C",
        "sync_fmt": "OnAttachmentManagerSynchronized() : %i",
        "sync_live": "OnAttachmentManagerSynchronized() : 7 -",
        "wam_false": "WeaponsAttachments: false",
        "wam_true": "WeaponsAttachments: true",
        "im_false": "InventoryManager: false",
        "im_true": "InventoryManager: true",
    }
    counts = {k: 0 for k in needles}
    samples: dict[str, list[str]] = {k: [] for k in needles}
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
                    for k, s in needles.items():
                        nd = s.encode("utf-16le")
                        i = 0
                        while True:
                            j = data.find(nd, i)
                            if j < 0:
                                break
                            counts[k] += 1
                            if len(samples[k]) < 2:
                                a = j
                                while a >= 2 and not (
                                    data[a - 2] == 0 and data[a - 1] == 0
                                ):
                                    a -= 2
                                    if j - a > 200:
                                        break
                                b = j
                                while b + 1 < len(data) and not (
                                    data[b] == 0 and data[b + 1] == 0
                                ):
                                    b += 2
                                    if b - j > 240:
                                        break
                                samples[k].append(
                                    data[a:b].decode("utf-16le", "replace")[:220]
                                )
                            i = j + len(nd)
                off += n
                left -= n
        addr = nxt
        if addr <= base:
            break

    out("")
    out("## string markers")
    for k in needles:
        out(f"  {k}: {counts[k]}")
        for s in samples[k]:
            out(f"    {s}")

    out("")
    out("## Interpretation")
    out(
        "  If AllAttachmentObjects includes id=151 with FName Number=1 and "
        "Outer=OwnerWeapon: CreateAttachment/NewObject ALREADY ran."
    )
    out(
        "  Mag*_C_0 UTF-16==0 with Mag UObject present => Synchronized never "
        "ToString'd FName (notify/CheckAttachmentsSynchronized gap), NOT "
        "SoftClass create skip."
    )
    out(
        "  Next: CheckAttachmentsSynchronized / OnAttachmentMeshesLoaded / "
        "GameSingleton bBlock* / Pad_298|318 pending — why notify never fires "
        "with objects+BaseMeshComp ready."
    )
    out("  REMATCH: no — no SoftClass wire fix; Mag NewObject already done.")

    kernel32.CloseHandle(h)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
