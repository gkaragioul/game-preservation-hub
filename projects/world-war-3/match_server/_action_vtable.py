#!/usr/bin/env python3
"""Diff `UWW3ReplicatedAction` subclass vtables to find each action's overrides,
and disassemble them out of the exe.

`Client_ReceivePacket_Implementation` calls the action's `vtable[0x240]` to
deserialise its body and `vtable[0x250]` to decide whether it executes
immediately. Those are the two functions that define the wire format of a
`TM_*` action, and neither has a symbol or a retained `check()` string.

Every action class has a CDO (`UClass::ClassDefaultObject` at +0x100) whose first
qword is the class vtable, so the live process hands us the vtables directly.
Comparing a subclass's slots against `UWW3ReplicatedAction`'s shows exactly which
methods it overrides.

Read-only on the live process.

Usage:
    python match_server/_action_vtable.py
    python match_server/_action_vtable.py --disasm 0x240 \
        --classes WW3.WW3ReplicatedAction_TM_RandomPlayerRegisteredToNewSquad
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _exe_fn import FnIndex, disasm_fn  # noqa: E402
from _exe_pe import PE  # noqa: E402
from _ps_sync_live import Mem, find_pid, main_module  # noqa: E402
from _uobject_live import DUMP_ROOT, Objects, load_dump, resolve  # noqa: E402

CDO_OFF = 0x100
DEFAULT_CLASSES = [
    "WW3.WW3ReplicatedAction",
    "WW3.WW3ReplicatedAction_TM_base",
    "WW3.WW3ReplicatedAction_TM_Synchronize",
    "WW3.WW3ReplicatedAction_TM_RandomPlayerRegisteredToNewSquad",
    "WW3.WW3ReplicatedAction_TM_PlayerStateBindedToSlot",
    "WW3.WW3ReplicatedAction_TM_WarmupFinished",
]


def vtable_of(mem: Mem, objs: Objects, by_name, name: str) -> tuple[int, int]:
    idx = resolve(objs, by_name, name)
    cls = objs.ptr(idx)
    cdo = mem.u64(cls + CDO_OFF)
    vt = mem.u64(cdo) if cdo else 0
    return cls, vt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--classes", nargs="*", default=DEFAULT_CLASSES)
    ap.add_argument("--lo", type=lambda s: int(s, 0), default=0x1F0)
    ap.add_argument("--hi", type=lambda s: int(s, 0), default=0x2B0)
    ap.add_argument("--dump", default=str(DUMP_ROOT / "GObjects-Dump.txt"))
    ap.add_argument("--disasm", default=None, help="slot offset, e.g. 0x240")
    args = ap.parse_args()

    pid = find_pid()
    mem = Mem(pid)
    mod_base, mod_size = main_module(pid)
    objs = Objects(mem, mod_base)
    _by_index, by_name = load_dump(Path(args.dump))
    pe = PE()
    fns = FnIndex(pe)

    def to_exe(live: int) -> int | None:
        if not live or not (mod_base <= live < mod_base + mod_size):
            return None
        return pe.image_base + (live - mod_base)

    tables: dict[str, dict[int, int]] = {}
    for name in args.classes:
        cls, vt = vtable_of(mem, objs, by_name, name)
        short = name.split(".")[-1].replace("WW3ReplicatedAction", "Action")
        print(f"{short:<46} UClass={cls:#x} CDO vtable={vt:#x}")
        slots = {}
        for off in range(args.lo, args.hi, 8):
            p = mem.u64(vt + off)
            e = to_exe(p)
            if e:
                slots[off] = e
        tables[short] = slots

    base = tables.get("Action", {})
    print(f"\nslots {args.lo:#x}..{args.hi:#x}; '=' means same as UWW3ReplicatedAction\n")
    hdr = "slot   " + "".join(f"{n[:22]:<24}" for n in tables)
    print(hdr)
    for off in range(args.lo, args.hi, 8):
        cells = []
        for name, slots in tables.items():
            v = slots.get(off)
            if v is None:
                cells.append(f"{'-':<24}")
            elif name != "Action" and base.get(off) == v:
                cells.append(f"{'=':<24}")
            else:
                cells.append(f"{v:#x}".ljust(24))
        print(f"{off:#05x}  " + "".join(cells))

    if args.disasm:
        slot = int(args.disasm, 0)
        for name, slots in tables.items():
            v = slots.get(slot)
            if v is None or (name != "Action" and base.get(slot) == v):
                continue
            print(f"\n{'='*70}\n=== {name} vtable[{slot:#x}] = {v:#x}\n{'='*70}")
            disasm_fn(pe, fns, v)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
