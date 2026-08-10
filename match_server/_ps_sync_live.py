#!/usr/bin/env python3
"""Find the live client's synchronization owner object and read the predicate
inputs straight out of its memory.

Static analysis of `WW3-Win64-Shipping.exe` (see `_ps_sync_predicate.py`) showed
the whole "Client Synchronization" checklist is a single bitmask byte:

    owner + 0x848  -> FSync*            (the sync object)
    FSync + 0x48   -> Value    (uint8)  bit0 Controller, bit1 PlayerState,
                                        bit2 InventoryManager, bit3 CharacterAttachments,
                                        bit4 WeaponsAttachments, bit5 GameState,
                                        bit6 LocalClientConfigs, bit7 MapLevels
    FSync + 0x4a   -> Required (uint8)  compared with `Value >= Required`
    owner + 0x156e -> last printed Value (the printer only logs on change)
    owner + 0x118  -> AActor::Role

That gives a uniquely-shaped signature to scan for, and once the owner is found
the pointers the predicate actually reads can be dereferenced instead of guessed.

Read-only: PROCESS_VM_READ only, no writes, no injection.

Usage:
    python match_server/_ps_sync_live.py
    python match_server/_ps_sync_live.py --mask 0xe9
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import struct
import subprocess
import sys

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_NOACCESS = 0x01
PAGE_GUARD = 0x100

SYNC_PTR_OFF = 0x848
VALUE_OFF = 0x48
REQUIRED_OFF = 0x4A
CACHED_OFF = 0x156E
ROLE_OFF = 0x118

BITS = ["Controller", "PlayerState", "InventoryManager", "CharacterAttachments",
        "WeaponsAttachments", "GameState", "LocalClientConfigs", "MapLevels"]
ROLES = ["ROLE_None", "ROLE_SimulatedProxy", "ROLE_AutonomousProxy", "ROLE_Authority"]

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_uint64),
        ("AllocationBase", ctypes.c_uint64),
        ("AllocationProtect", wt.DWORD),
        ("__align", wt.DWORD),
        ("RegionSize", ctypes.c_uint64),
        ("State", wt.DWORD),
        ("Protect", wt.DWORD),
        ("Type", wt.DWORD),
        ("__align2", wt.DWORD),
    ]


def well_formed_array(blob: bytes, off: int) -> bool:
    """TArray<T> = {T* Data; int32 Num; int32 Max} sanity check."""
    data, num, mx = struct.unpack_from("<Qii", blob, off)
    if num < 0 or mx < 0 or num > mx or mx > 4096:
        return False
    if mx == 0:
        return data == 0
    return 0x10000 <= data < 0x7FFFFFFFFFFF and data % 8 == 0


def main_module(pid: int) -> tuple[int, int]:
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"$m=(Get-Process -Id {pid}).MainModule; "
         "\"$([int64]$m.BaseAddress) $($m.ModuleMemorySize)\""],
        capture_output=True, text=True, check=False)
    base, size = (r.stdout or "0 0").split()
    return int(base), int(size)


def find_pid() -> int:
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process WW3-Win64-Shipping -EA SilentlyContinue | Select -First 1).Id"],
        capture_output=True, text=True, check=False)
    pid = (r.stdout or "").strip()
    if not pid:
        raise SystemExit("WW3-Win64-Shipping not running")
    return int(pid)


class Mem:
    def __init__(self, pid: int):
        self.h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
                                      False, pid)
        if not self.h:
            raise SystemExit(f"OpenProcess failed: {ctypes.get_last_error()}")
        self._cache: dict[int, bytes] = {}
        self.regions = list(self._walk())

    def _walk(self):
        addr = 0
        mbi = MEMORY_BASIC_INFORMATION()
        while addr < 0x7FFFFFFFFFFF:
            n = kernel32.VirtualQueryEx(self.h, ctypes.c_void_p(addr),
                                        ctypes.byref(mbi), ctypes.sizeof(mbi))
            if not n:
                break
            size = mbi.RegionSize
            if (mbi.State == MEM_COMMIT and not (mbi.Protect & PAGE_GUARD)
                    and mbi.Protect not in (0, PAGE_NOACCESS)):
                yield (mbi.BaseAddress, size, mbi.Protect, mbi.Type)
            addr = mbi.BaseAddress + size
            if size == 0:
                break

    def read(self, addr: int, size: int) -> bytes | None:
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t(0)
        ok = kernel32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), buf, size,
                                        ctypes.byref(got))
        if not ok or got.value != size:
            return None
        return buf.raw

    def u8(self, a):
        b = self.read(a, 1)
        return b[0] if b else None

    def u64(self, a):
        b = self.read(a, 8)
        return struct.unpack("<Q", b)[0] if b else None

    def u32(self, a):
        b = self.read(a, 4)
        return struct.unpack("<I", b)[0] if b else None


def describe(mask: int) -> str:
    return " ".join(f"{'+' if mask >> i & 1 else '-'}{n}" for i, n in enumerate(BITS))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mask", default=None,
                    help="expected Value byte (default: infer from candidates)")
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args()

    pid = find_pid()
    mem = Mem(pid)
    mod_base, mod_size = main_module(pid)
    print(f"pid={pid}  {len(mem.regions)} committed regions  "
          f"module={mod_base:#x}+{mod_size:#x}")

    want = int(args.mask, 0) if args.mask else None

    # The sync owner Y holds the FSync* at +0x848 and AActor::Role at +0x118.
    # (The checklist printer caches the last-logged byte at +0x156e, but that is a
    # *different* object - it reaches Y through its own +0x360 - so the cache byte
    # is not part of this signature.)
    #
    # Anchor on the bits we know are already true from the live checklist:
    # Controller|GameState|LocalClientConfigs|MapLevels = 0xe1.
    floor = 0xE1 if want is None else want
    cands = []
    scanned = 0
    seen_sync: set[int] = set()
    for base, size, prot, typ in mem.regions:
        if size < SYNC_PTR_OFF + 8:
            continue
        blob = mem.read(base, size)
        if blob is None:
            blob = b"".join(
                (mem.read(base + o, min(0x10000, size - o)) or b"\0" * min(0x10000, size - o))
                for o in range(0, size, 0x10000))
        scanned += size
        n = len(blob)
        for off in range(0, n - (SYNC_PTR_OFF + 8), 8):
            if blob[off + ROLE_OFF] not in (2, 3):
                continue
            # A real UObject starts with a vtable pointer into the main module.
            vt = struct.unpack_from("<Q", blob, off)[0]
            if not (mod_base <= vt < mod_base + mod_size):
                continue
            p = struct.unpack_from("<Q", blob, off + SYNC_PTR_OFF)[0]
            if p < 0x10000 or p > 0x7FFFFFFFFFFF or p & 7:
                continue
            head = mem.read(p, 0x50)
            if head is None:
                continue
            v, req = head[VALUE_OFF], head[REQUIRED_OFF]
            if (v & floor) != floor:
                continue
            if want is not None and v != want:
                continue
            # The three multicast-delegate invocation lists must look like real
            # TArrays; this is what rejects filler pages full of 0xff.
            if not all(well_formed_array(head, o) for o in (0x00, 0x18, 0x30)):
                continue
            key = (p, base + off)
            if key in seen_sync:
                continue
            seen_sync.add(key)
            cands.append((base + off, p, v, req, blob[off + ROLE_OFF]))
            if len(cands) >= args.limit:
                break
        if len(cands) >= args.limit:
            break

    print(f"scanned {scanned/1e9:.2f} GB, {len(cands)} candidate owner(s)\n")
    for owner, sync, val, req, role in cands:
        vt = mem.u64(owner)
        print(f"owner={owner:#x}  vtable={vt:#x}" if vt else f"owner={owner:#x}")
        print(f"  Role({ROLE_OFF:#x})   = {role} {ROLES[role] if role < 4 else '?'}")
        print(f"  Sync({SYNC_PTR_OFF:#x})  = {sync:#x}")
        print(f"    Value(+0x48)    = {val:#04x}   {describe(val)}")
        print(f"    Required(+0x4a) = {req:#04x}   {describe(req)}")
        print(f"    +0x49           = {mem.u8(sync + 0x49)}")
        print(f"    +0x44 (int)     = {mem.u32(sync + 0x44)}")
        missing = req & ~val
        print(f"    MISSING         = {missing:#04x} -> "
              f"{[BITS[i] for i in range(8) if missing >> i & 1]}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
