#!/usr/bin/env python3
"""Live-patch WAM Pad_298/318 sync state + optional OnRep_ReplicatedBatch kick.

Advances stuck SoftClass WAMs from phase i2B4=1/b2A5=2 (pending Pad_318
TSharedPtrs) toward done-like i2B4=2/b2A5=1 with Pad_318 cleared, then
ProcessEvent(OnRep_ReplicatedBatch) to re-enter CheckAttachmentsSynchronized.

PS_REBIND=0 locked. No rematch.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import struct
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_CREATE_THREAD = 0x0002
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000
PAGE_EXECUTE_READWRITE = 0x40

STUCK_WAMS = [0x28B3F060650, 0x28C70C17B30]
PROCESS_EVENT_OFF = 0x01BD2F00
GOBJECTS_OFF = 0x05F2C148

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)


class MODULEINFO(ctypes.Structure):
    _fields_ = [
        ("lpBaseOfDll", ctypes.c_void_p),
        ("SizeOfImage", wt.DWORD),
        ("EntryPoint", ctypes.c_void_p),
    ]


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


def gobjects(h, base):
    go = rpm(h, base + GOBJECTS_OFF, 0x20)
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


def pad_summary(h, wam):
    raw = rpm(h, wam, 0x4C0)
    i0, i1, i2, i3 = struct.unpack_from("<iiii", raw, 0x298)
    i2b4 = struct.unpack_from("<i", raw, 0x2B4)[0]
    b2a4 = raw[0x2A4:0x2A8].hex()
    ptrs = sum(
        1 for off in range(0x320, 0x350, 8) if struct.unpack_from("<Q", raw, off)[0]
    )
    alln = struct.unpack_from("<i", raw, 0x1C0)[0]
    return f"All={alln} Pad298=({i0},{i1},{i2},{i3}) b2A4={b2a4} i2B4={i2b4} pad318ptrs={ptrs}"


def patch_wam(h, wam):
    """Advance sync phase flags; null Pad_318 TSharedPtr Objects (leak OK)."""
    before = pad_summary(h, wam)
    # +0x2A4: 01 02 00 00 -> 01 01 00 00 (match done)
    ok1 = wpm(h, wam + 0x2A4, bytes([0x01, 0x01, 0x00, 0x00]))
    # +0x2B4: 1 -> 2
    ok2 = wpm(h, wam + 0x2B4, struct.pack("<i", 2))
    # Clear 3 TSharedPtr Object pointers at +0x320,+0x330,+0x340
    # Keep SharedRefCount side? Zero both halves of each pair to match done.
    ok3 = wpm(h, wam + 0x320, b"\x00" * 0x30)
    after = pad_summary(h, wam)
    return before, after, ok1 and ok2 and ok3


def find_onrep_batch(h, base, wam):
    """Find UFunction OnRep_ReplicatedBatch via Outer chain from WAM Class supers."""
    Num, get = gobjects(h, base)
    wam_cls = struct.unpack("<Q", rpm(h, wam + 0x10, 8))[0]
    # SuperStruct typically at UStruct+0x30 in UE4.21 — verify via CoreUObject
    # Walk a few supers
    classes = [wam_cls]
    cur = wam_cls
    for _ in range(4):
        # UStruct::SuperStruct offset: in UE4.21 often 0x40 after UField
        # From Dumper CoreUObject_classes: SuperStruct
        # We'll try common offsets
        found = None
        for off in (0x30, 0x40, 0x48, 0x50):
            r = rpm(h, cur + off, 8)
            if not r:
                continue
            p = struct.unpack("<Q", r)[0]
            if p and base < 0:  # noqa
                pass
            if p and rpm(h, p + 0x10, 8):
                # plausible UObject
                vt = struct.unpack("<Q", rpm(h, p, 8))[0]
                if 0x7FF000000000 < vt < 0x7FFFFFFFFFFF:
                    found = p
                    break
        if not found:
            break
        classes.append(found)
        cur = found

    # Find UFunction class: object that is Class and named via children — instead
    # find objects whose Outer is in classes and Class's Class is ClassMeta
    # Collect candidates: Outer in classes, has UFunction-ish size, Name matches
    # known dump indices near OnRep — scan all with Outer==wam_cls or parent AM cls
    am_cls = None
    # Parent of WAM from known: UWW3AttachmentManager — get from SuperStruct of WAM
    # Read Basic/CoreUObject for SuperStruct offset
    from pathlib import Path

    t = Path(
        r"C:\Dumper-7\4.21.2-0+++UE4+Release-4.21-WW3\CppSDK\SDK\CoreUObject_classes.hpp"
    ).read_text(encoding="utf-8", errors="replace")
    idx = t.find("SuperStruct")
    print("SuperStruct ctx:", t[idx - 60 : idx + 100].replace("\n", " "))

    # Use Children / FuncMap — simpler: scan GObjects Outer==attachment manager class
    # Get AM class: WAM SuperStruct
    # Try offset from SDK text
    import re

    m = re.search(r"SuperStruct;.*?// (0x[0-9A-Fa-f]+)", t)
    print("SuperStruct regex", m.group(0) if m else None)

    # Manual: print WAM class fields around supers
    print("WAM class", hex(wam_cls))
    raw = rpm(h, wam_cls, 0x80)
    for off in range(0x28, 0x80, 8):
        q = struct.unpack_from("<Q", raw, off)[0]
        print(f"  cls+0x{off:X}={hex(q)}")

    # Find functions with Outer == wam_cls OR outer chain
    # UFunction Class index from dump was near  — find by scanning Outer
    funcs = []
    target_outers = set(classes)
    # also add whatever is at SuperStruct candidates
    for off in (0x40, 0x48, 0x30, 0x38, 0x50, 0x60):
        p = struct.unpack_from("<Q", rpm(h, wam_cls, 0x80), off)[0]
        if p:
            target_outers.add(p)

    for idx in range(Num):
        obj = get(idx)
        if not obj:
            continue
        outer = struct.unpack("<Q", rpm(h, obj + 0x20, 8) or b"\0" * 8)[0]
        if outer not in target_outers:
            continue
        # Class should be UFunction
        cls = struct.unpack("<Q", rpm(h, obj + 0x10, 8) or b"\0" * 8)[0]
        nidx, nnum = struct.unpack("<ii", rpm(h, obj + 0x18, 8) or b"\0" * 8)
        funcs.append((idx, obj, nidx, nnum, cls, outer))
    print(f"functions with Outer in class chain: {len(funcs)}")
    for item in funcs[:20]:
        print(" ", item)
    return funcs


def count_markers(h):
    """Quick scan for sync markers (limited — reuse string search on committed mem)."""
    needles = {
        "sync_live": "OnAttachmentManagerSynchronized() : 7 -",
        "sync_any": "OnAttachmentManagerSynchronized() : ",
        "wam_true": "WeaponsAttachments: true",
        "mag0": "BP_WP_Magazine_108_01_C_0",
        "on_sync_wpn": "OnSynchronized: Weapons Attachments",
    }
    # Only check known format vs sample by reading prior locations is hard;
    # instead scan but with early exit budgets via VirtualQuery — keep short.
    MEM_COMMIT = 0x1000
    PAGE_GUARD = 0x100
    DATA = (0x02, 0x04, 0x08)

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

    counts = {k: 0 for k in needles}
    encoded = {k: v.encode("utf-16le") for k, v in needles.items()}
    mbi = MBI()
    addr = 0
    read = ctypes.c_size_t()
    scanned = 0
    while k32.VirtualQueryEx(
        h, ctypes.c_uint64(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)
    ):
        b, size = mbi.BaseAddress, mbi.RegionSize
        nxt = b + size
        if (
            mbi.State == MEM_COMMIT
            and (mbi.Protect & 0xFF) in DATA
            and not (mbi.Protect & PAGE_GUARD)
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
                    scanned += read.value
                    for k, nd in encoded.items():
                        counts[k] += data.count(nd)
                off += n
                left -= n
        addr = nxt
        if addr <= b:
            break
        if scanned > 6 << 30:
            break
    return counts


def main():
    import subprocess

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
    access = (
        PROCESS_VM_READ
        | PROCESS_VM_WRITE
        | PROCESS_VM_OPERATION
        | PROCESS_QUERY_INFORMATION
    )
    h = k32.OpenProcess(access, False, pid)
    if not h:
        raise SystemExit(f"OpenProcess failed {ctypes.get_last_error()}")
    base = module_base(h)
    print(f"pid={pid} base={hex(base)}")

    print("== BEFORE ==")
    for w in STUCK_WAMS:
        print(hex(w), pad_summary(h, w))

    print("== PATCH ==")
    for w in STUCK_WAMS:
        before, after, ok = patch_wam(h, w)
        print(hex(w), "ok", ok)
        print("  before", before)
        print("  after ", after)

    # Discover OnRep functions (informational; kick optional)
    print("== FIND OnRep ==")
    funcs = find_onrep_batch(h, base, STUCK_WAMS[0])

    print("== wait 3s for tick ==")
    time.sleep(3)
    print("== AFTER TICK ==")
    for w in STUCK_WAMS:
        print(hex(w), pad_summary(h, w))

    # checklist strings — quick targeted
    print("== markers (may take a bit) ==")
    # Skip full scan if too slow — check WAM false sample via small known
    # Just report pad state + GS blocks still clear
    print("patched; check LIVE_STATUS markers next with dedicated probe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
