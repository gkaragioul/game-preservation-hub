#!/usr/bin/env python3
"""Fast Pad_298/318 dump for known early WAMs (no full memscan of GS)."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import struct
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent / "live_log" / "_gs_sync_blocks_dump.txt"
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
DATA = (0x02, 0x04, 0x08)
CHUNK = 1 << 20
EARLY8 = (151, 4638, 304, 101, 4606, 4608, 88, 7851)
EARLY8_BYTES = b"".join(struct.pack("<H", x) for x in EARLY8)

# Known from prior dump (may still be valid)
KNOWN = [0x28B3F060650, 0x28C70C17B30]

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


def rpm(h, addr, n):
    buf = (ctypes.c_char * n)()
    read = ctypes.c_size_t()
    if not kernel32.ReadProcessMemory(
        h, ctypes.c_uint64(addr), buf, n, ctypes.byref(read)
    ):
        return None
    return bytes(buf[: read.value])


def find_pid():
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
    return int((r.stdout or "").strip())


def module_base(h):
    hMods = (ctypes.c_uint64 * 1024)()
    needed = wt.DWORD()
    psapi.EnumProcessModulesEx(h, hMods, ctypes.sizeof(hMods), ctypes.byref(needed), 3)
    name = ctypes.create_unicode_buffer(260)
    for i in range(min(needed.value // 8, 1024)):
        psapi.GetModuleBaseNameW(h, ctypes.c_uint64(hMods[i]), name, 260)
        if "WW3-Win64-Shipping" in name.value:
            return int(hMods[i])
    raise SystemExit("no module")


def gobjects_get(h, base):
    go = rpm(h, base + 0x05F2C148, 0x20)
    Objects, _M, Num, _Mc, NumChunks = struct.unpack_from("<Q8xiiii", go)
    chunks = struct.unpack("<" + str(NumChunks) + "Q", rpm(h, Objects, NumChunks * 8))

    def get(idx):
        if idx < 0 or idx >= Num:
            return None
        ci, ii = divmod(idx, 0x10000)
        c = chunks[ci]
        if not c:
            return None
        item = rpm(h, c + ii * 0x18, 8)
        return struct.unpack("<Q", item)[0] if item else None

    return Num, get


def dump_wam(h, comp, lines):
    raw = rpm(h, comp, 0x4C0)
    if not raw:
        lines.append(f"### WAM @0x{comp:x} UNREADABLE")
        return False
    batch_id = struct.unpack_from("<I", raw, 0x2B8)[0]
    cab = struct.unpack_from("<I", raw, 0x2E0)[0]
    all_n = struct.unpack_from("<i", raw, 0x1C0)[0]
    owner = struct.unpack_from("<Q", raw, 0x4A8)[0]
    if owner < 0x10000 or all_n < 0 or all_n > 32:
        return False
    if batch_id not in (1, 2):
        return False
    base_mesh = struct.unpack_from("<Q", raw, 0x1B0)[0]
    main_skin = struct.unpack_from("<Q", raw, 0x428)[0]
    tmp_n = struct.unpack_from("<i", raw, 0x310)[0]
    mesh_n = struct.unpack_from("<i", raw, 0x380)[0]
    parent_n = struct.unpack_from("<i", raw, 0x370)[0]
    as_n = struct.unpack_from("<i", raw, 0x290)[0]
    lines.append(f"### WAM @0x{comp:x}")
    lines.append(
        f"  Batch={batch_id} ClientApplied={cab} AllObj={all_n} "
        f"Owner=0x{owner:x} BaseMesh=0x{base_mesh:x} MainSkin=0x{main_skin:x}"
    )
    lines.append(
        f"  AttachStructNum={as_n} Temporary={tmp_n} MeshDel={mesh_n} "
        f"ParentDel={parent_n}"
    )
    for label, start, end in (
        ("Pad_298", 0x298, 0x2B8),
        ("Pad_318", 0x318, 0x350),
        ("Pad_360", 0x360, 0x368),
        ("Pad_388", 0x388, 0x398),
        ("Pad_3A8", 0x3A8, 0x3C2),
        ("Pad_3F0", 0x3F0, 0x428),
    ):
        blob = raw[start:end]
        lines.append(f"  {label}: {blob.hex()}")
        lines.append(f"  {label} bytes: {list(blob)}")
        for i in range(0, len(blob) - 7, 8):
            q = struct.unpack_from("<Q", blob, i)[0]
            a, b = struct.unpack_from("<ii", blob, i)
            lines.append(f"    +0x{start+i:X}: u64=0x{q:x} i32=({a},{b})")
    # Attachment objects sync-ish fields
    all_data = struct.unpack_from("<Q", raw, 0x1B8)[0]
    all_ids_data = struct.unpack_from("<Q", raw, 0x1C8)[0]
    if all_n > 0 and all_data:
        objs = struct.unpack(
            "<" + str(all_n) + "Q", rpm(h, all_data, all_n * 8) or b""
        )
        ids = ()
        if all_ids_data:
            ir = rpm(h, all_ids_data, all_n * 2)
            if ir:
                ids = struct.unpack("<" + str(all_n) + "H", ir)
        for i, op in enumerate(objs):
            oid = ids[i] if i < len(ids) else -1
            if not op:
                lines.append(f"  att[{i}] id={oid} NULL")
                continue
            o = rpm(h, op, 0x1F0)
            if not o:
                continue
            bmc = struct.unpack_from("<Q", o, 0x1E0)[0]
            myam = struct.unpack_from("<Q", o, 0x1D0)[0]
            # SoftClass BaseMeshTemplate at ~0x28/0x30 — dump first 0x80 for unknowns
            lines.append(
                f"  att[{i}] id={oid} obj=0x{op:x} BMC=0x{bmc:x} MyAM=0x{myam:x}"
            )
            # dump bytes 0x28..0x80 and 0x180..0x1F0 for sync flags
            lines.append(f"       +0x28: {o[0x28:0x80].hex()}")
            lines.append(f"       +0x180: {o[0x180:0x1F0].hex()}")
    return True


def main():
    pid = find_pid()
    h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    lines = [
        f"# GS+Pad sync dump (fast)",
        f"# pid={pid}",
        "",
    ]
    base = module_base(h)
    Num, get = gobjects_get(h, base)
    cls = get(0x4A7)
    lines.append(f"## GS class=0x{cls:x}")
    # find GS instance — scan but only Class compare; still N=370k reads ~ok
    gs_hits = []
    for idx in range(Num):
        obj = get(idx)
        if not obj:
            continue
        r = rpm(h, obj + 0x10, 8)
        if r and struct.unpack("<Q", r)[0] == cls:
            gs_hits.append((idx, obj))
    lines.append(f"## GS instances={len(gs_hits)}")
    names = [
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
    any_block = False
    for idx, obj in gs_hits:
        blocks = rpm(h, obj + 0x118, 0x11)
        lines.append(f"### GS @0x{obj:x} idx={idx}")
        for off, nm in names:
            v = blocks[off - 0x118]
            if v:
                any_block = True
            lines.append(f"  {nm}={v}")
    lines.append(f"## any bBlock* set? {any_block}")
    lines.append("")

    # Prefer known WAMs; validate; else quick early8 header find limited
    wams = []
    for c in KNOWN:
        raw = rpm(h, c, 0x4C0)
        if raw and struct.unpack_from("<I", raw, 0x2B8)[0] in (1, 2):
            wams.append(c)
    if not wams:
        # limited scan: only search for early8 then headers (same as before but stop early)
        early = []
        mbi = MBI()
        addr = 0
        read = ctypes.c_size_t()
        while kernel32.VirtualQueryEx(
            h, ctypes.c_uint64(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)
        ):
            b, size = mbi.BaseAddress, mbi.RegionSize
            nxt = b + size
            if (
                mbi.State == MEM_COMMIT
                and (mbi.Protect & 0xFF) in DATA
                and not (mbi.Protect & PAGE_GUARD)
                and 0 < size <= 64 << 20
            ):
                left, off = size, 0
                while left > 0:
                    n = min(CHUNK, left)
                    buf = (ctypes.c_char * n)()
                    if (
                        kernel32.ReadProcessMemory(
                            h, ctypes.c_uint64(b + off), buf, n, ctypes.byref(read)
                        )
                        and read.value
                    ):
                        data = bytes(buf[: read.value])
                        i = 0
                        while True:
                            j = data.find(EARLY8_BYTES, i)
                            if j < 0:
                                break
                            early.append(b + off + j)
                            i = j + 2
                            if len(early) >= 8:
                                break
                    off += n
                    left -= n
            addr = nxt
            if addr <= b or len(early) >= 8:
                break
        for t in early:
            # find header pointing here with Num=8 near expected WAM layout
            # search only +/- 0x1000? better: scan for pointer value
            pat = struct.pack("<Q", t)
            # reuse full scan but only for this one pointer - expensive
            # instead try common: AttachmentIds at batch+8 = comp+0x2C0
            # so if we have data ptr, header at data_ptr referenced from somewhere
            pass
        # fallback: treat early array addrs - 0x08 as batch if BatchID ok
        for t in early:
            for delta in (0x08, 0):
                batch = t - delta
                raw = rpm(h, batch, 0x30)
                if not raw:
                    continue
                bid = struct.unpack_from("<I", raw, 0)[0]
                ids_num = struct.unpack_from("<i", raw, 0x10)[0]
                if bid in (1, 2) and ids_num == 8 and struct.unpack_from("<Q", raw, 0x08)[0] == t:
                    comp = batch - 0x2B8
                    if comp not in wams:
                        wams.append(comp)

    lines.append(f"## WAMs={len(wams)}")
    for comp in wams:
        dump_wam(h, comp, lines)

    lines.append("")
    lines.append("## Interpretation")
    if not any_block:
        lines.append(
            "GameSingleton bBlockCheck*/FullySynchronized ALL 0 — not the gate."
        )
    lines.append("Inspect Pad_298/318 for pending counters / sync bools.")
    text = "\n".join(lines) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
