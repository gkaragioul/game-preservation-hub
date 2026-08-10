#!/usr/bin/env python3
"""Decode a native UE4 multicast delegate out of the live client.

Why
---
`0x1411c0f30` is the only producer of the `InventoryManager` sync bit and it has
**no call sites** -- `_exe_xref.py` finds none, and its address appears nowhere as
a qword, so it is not a vtable slot.  `AWW3Character`'s constructor
(`0x141186910`) binds it to the multicast delegate at
`Character->InventoryManager + 0xF0`.

"Bound to +0xF0" was, until now, read off the *constructor*.  This reads it off
the *live object*, which is a different and much stronger claim: it walks the
delegate's invocation list, pulls the C++ member-function pointer out of each
`TBaseUObjectMethodDelegateInstance`, and converts it back to an exe VA.  If
`0x1411c0f30` shows up there, the binding demonstrably ran and the callback is
demonstrably still subscribed -- so a silent bit can only mean the delegate was
never broadcast.

Layout (UE 4.21, `NUM_DELEGATE_INLINE_BYTES == 0` so the delegate allocator is
`FHeapAllocator`):

    FMulticastDelegateBase<FWeakObjectPtr>
      +0x00  TDelegateBase* InvocationList.Data
      +0x08  int32          InvocationList.Num
      +0x0C  int32          InvocationList.Max
      +0x10  int32          CompactionThreshold
      +0x14  int32          InvocationListLockCount

    TDelegateBase<FWeakObjectPtr>            (stride 0x10)
      +0x00  void*          Allocation       -> IDelegateInstance
      +0x08  int32          DelegateSize

Nothing about the *instance* layout is assumed: the allocation is scanned for
qwords that land in the main module's executable range, and each is reported
with its exe VA, so the method pointer is found rather than computed from a
guessed offset.  `FWeakObjectPtr` candidates (int32 ObjectIndex + int32
ObjectSerialNumber) are resolved through `GObjects` the same way.

Read-only: PROCESS_QUERY_INFORMATION | PROCESS_VM_READ.

Usage:
    python match_server/_delegate_live.py --character
    python match_server/_delegate_live.py --addr 0x1b86aa58a50
    python match_server/_delegate_live.py --character --expect 0x1411c0f30
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _exe_pe import PE  # noqa: E402
from _ps_sync_live import Mem, find_pid, main_module  # noqa: E402
from _team_graph_live import live_instances  # noqa: E402
from _uobject_live import DUMP_ROOT, OBJ_CLASS, Objects, load_dump  # noqa: E402

CH_INVENTORY_MANAGER = 0x7B0   # AWW3Character::InventoryManager
CH_ATTACHMENT_MANAGER = 0x7A0  # the object whose +0x120 delegate DOES fire
INV_DELEGATE = 0xF0            # bound to 0x1411c0f30 (InventoryManager|WeaponsAttachments)
ATT_DELEGATE = 0x120           # bound to 0x1411ba920 (CharacterAttachments) -- the control

ENTRY_STRIDE = 0x10


def u32(mem, a):
    b = mem.read(a, 4)
    return None if b is None else struct.unpack("<i", b)[0]


def u64(mem, a):
    b = mem.read(a, 8)
    return None if b is None else struct.unpack("<Q", b)[0]


class Resolver:
    """live VA <-> exe VA, and GObjects index -> name."""

    def __init__(self, mem: Mem, mod_base: int, mod_size: int, objs: Objects,
                 by_index: dict[int, tuple[str, str]]):
        self.mem = mem
        self.mod_base = mod_base
        self.mod_size = mod_size
        self.objs = objs
        self.by_index = by_index
        self.pe = PE()

    def in_module(self, va: int) -> bool:
        return self.mod_base <= va < self.mod_base + self.mod_size

    def exe_va(self, live_va: int) -> int:
        return self.pe.image_base + (live_va - self.mod_base)

    def live_va(self, exe_va: int) -> int:
        return self.mod_base + (exe_va - self.pe.image_base)

    def is_code(self, exe_va: int) -> bool:
        s = self.pe.section_of_va(exe_va)
        return bool(s and s.executable)

    def object_name(self, ptr: int) -> str | None:
        cls = u64(self.mem, ptr + OBJ_CLASS)
        if not cls:
            return None
        idx = u32(self.mem, cls + 0x0C)
        if idx is None:
            return None
        row = self.by_index.get(idx)
        return row[1] if row else None


def dump_delegate(res: Resolver, addr: int, label: str, expect: int | None) -> bool:
    """Print one multicast delegate; return True if `expect` (an exe VA) is bound."""
    mem = res.mem
    head = mem.read(addr, 0x18)
    print(f"\n=== {label}  @ {addr:#x}")
    if head is None:
        print("  unreadable")
        return False
    data, num, mx, compaction, lock = struct.unpack("<QiiiI", head)
    print(f"  InvocationList  Data={data:#x} Num={num} Max={mx}")
    print(f"  CompactionThreshold={compaction}  LockCount={lock}")
    if num < 0 or num > mx or mx < 0 or mx > 4096:
        print("  -> not a well-formed TArray; wrong offset or not a delegate")
        return False
    if num == 0:
        print("  -> EMPTY: nothing is subscribed to this delegate")
        return False

    found = False
    for i in range(num):
        ent = mem.read(data + i * ENTRY_STRIDE, ENTRY_STRIDE)
        if ent is None:
            print(f"  [{i}] unreadable entry")
            continue
        alloc, size = struct.unpack_from("<Qi", ent, 0)
        print(f"  [{i}] Allocation={alloc:#x}  DelegateSize={size}")
        if not alloc:
            print("       (empty slot)")
            continue
        blob = mem.read(alloc, max(size, 0x40) if 0 < size <= 0x200 else 0x40)
        if blob is None:
            print("       unreadable allocation")
            continue
        vt = struct.unpack_from("<Q", blob, 0)[0]
        if res.in_module(vt):
            print(f"       vtable = {vt:#x}  exe {res.exe_va(vt):#x}")
        for off in range(8, len(blob) - 7, 8):
            q = struct.unpack_from("<Q", blob, off)[0]
            if q and res.in_module(q):
                eva = res.exe_va(q)
                kind = "CODE" if res.is_code(eva) else "data"
                mark = ""
                if expect is not None and eva == expect:
                    mark = "   <<< the callback we are looking for"
                    found = True
                print(f"       +{off:#04x} {q:#x} -> exe {eva:#x} [{kind}]{mark}")
        # FWeakObjectPtr candidates: (int32 ObjectIndex, int32 ObjectSerialNumber)
        for off in range(8, len(blob) - 7, 4):
            oi, ser = struct.unpack_from("<ii", blob, off)
            if not (0 < oi < res.objs.num_elements) or not (0 < ser < 1 << 24):
                continue
            p = res.objs.ptr(oi)
            if not p:
                continue
            nm = res.object_name(p)
            if nm:
                print(f"       +{off:#04x} FWeakObjectPtr idx={oi} serial={ser}"
                      f" -> {p:#x} {nm}")
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--addr", action="append", default=[],
                    help="explicit delegate address (repeatable)")
    ap.add_argument("--character", action="store_true",
                    help="locate the live AWW3Character and dump both known delegates")
    ap.add_argument("--expect", default=None,
                    help="exe VA of a callback that should be bound (e.g. 0x1411c0f30)")
    ap.add_argument("--dump", default=str(DUMP_ROOT / "GObjects-Dump.txt"))
    args = ap.parse_args()

    pid = find_pid()
    mem = Mem(pid)
    mod_base, mod_size = main_module(pid)
    objs = Objects(mem, mod_base)
    by_index, by_name = load_dump(Path(args.dump))
    res = Resolver(mem, mod_base, mod_size, objs, by_index)
    expect = int(args.expect, 0) if args.expect else None
    print(f"pid={pid}  module={mod_base:#x}+{mod_size:#x}  "
          f"exe image_base={res.pe.image_base:#x}")
    if expect:
        print(f"expecting exe {expect:#x} (live {res.live_va(expect):#x}) to be bound")

    hits = 0
    if args.character:
        chars = live_instances(mem, objs, by_name,
                               ["WW3.WW3Character"]).get("WW3.WW3Character", [])
        for _i, ch, _c, _f in chars:
            inv = u64(mem, ch + CH_INVENTORY_MANAGER) or 0
            att = u64(mem, ch + CH_ATTACHMENT_MANAGER) or 0
            print(f"\n########## AWW3Character {ch:#x}")
            print(f"  InventoryManager(+0x7B0) = {inv:#x}"
                  f"   class={res.object_name(inv) if inv else None}")
            print(f"  [+0x7A0]                 = {att:#x}"
                  f"   class={res.object_name(att) if att else None}")
            if inv and dump_delegate(res, inv + INV_DELEGATE,
                                     "InventoryManager +0xF0 (never fires)", expect):
                hits += 1
            if att:
                dump_delegate(res, att + ATT_DELEGATE,
                              "[+0x7A0] +0x120 (CharacterAttachments -- this one DOES fire)",
                              None)
    for a in args.addr:
        if dump_delegate(res, int(a, 0), f"explicit {a}", expect):
            hits += 1

    if expect is not None:
        print(f"\nRESULT: callback {expect:#x} bound in {hits} delegate(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
