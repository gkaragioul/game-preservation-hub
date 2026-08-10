#!/usr/bin/env python3
"""Resolve virtual-table slots of a live UObject to exe addresses.

The two sites that broadcast `UWW3InventoryManagerBase + 0xF0` (found by
`_delegate_broadcast_scan.py` and confirmed against the real
`TBaseMulticastDelegate<void>::Broadcast` at `0x140425920`) are both gated on
`this->vtable[0x3D0]()`.  A shipping build has no symbols, and the callee is
class-dependent, so the only way to know *which* function that is -- rather than
guessing from the offset -- is to read the slot off the live object of the exact
class involved and translate the live VA back to an exe VA.

Read-only: PROCESS_QUERY_INFORMATION | PROCESS_VM_READ.

Usage:
    python match_server/_vtable_live.py --character-inventory --slots 0x3d0,0x3d8,0x3f8,0x418
    python match_server/_vtable_live.py --obj 0x1b86aa58960 --slots 0x3d0
    python match_server/_vtable_live.py --obj 0x1b86aa58960 --range 0x3c0 0x430
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

CH_INVENTORY_MANAGER = 0x7B0


def u64(mem, a):
    b = mem.read(a, 8)
    return None if b is None else struct.unpack("<Q", b)[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--obj", default=None, help="live object address")
    ap.add_argument("--character-inventory", action="store_true",
                    help="use the live AWW3Character's InventoryManager")
    ap.add_argument("--slots", default="",
                    help="comma-separated byte offsets into the vtable")
    ap.add_argument("--range", nargs=2, type=lambda s: int(s, 0), default=None,
                    metavar=("LO", "HI"))
    ap.add_argument("--dump", default=str(DUMP_ROOT / "GObjects-Dump.txt"))
    args = ap.parse_args()

    pid = find_pid()
    mem = Mem(pid)
    mod_base, mod_size = main_module(pid)
    objs = Objects(mem, mod_base)
    by_index, by_name = load_dump(Path(args.dump))
    pe = PE()

    targets = []
    if args.obj:
        targets.append(int(args.obj, 0))
    if args.character_inventory:
        for _i, ch, _c, _f in live_instances(
                mem, objs, by_name, ["WW3.WW3Character"]).get("WW3.WW3Character", []):
            inv = u64(mem, ch + CH_INVENTORY_MANAGER)
            if inv:
                targets.append(inv)
    if not targets:
        ap.error("give --obj or --character-inventory")

    slots = [int(s, 0) for s in args.slots.split(",") if s.strip()]
    if args.range:
        slots += list(range(args.range[0], args.range[1], 8))

    for obj in targets:
        cls = u64(mem, obj + OBJ_CLASS) or 0
        cidx = struct.unpack("<i", mem.read(cls + 0x0C, 4))[0] if cls else None
        vt = u64(mem, obj) or 0
        print(f"\nobject {obj:#x}  class={by_index.get(cidx, '?')}")
        print(f"  vtable live {vt:#x}  exe {pe.image_base + (vt - mod_base):#x}")
        for s in sorted(set(slots)):
            fn = u64(mem, vt + s)
            if not fn or not (mod_base <= fn < mod_base + mod_size):
                print(f"    [{s:#05x}] {fn if fn is None else hex(fn)}  (outside image)")
                continue
            print(f"    [{s:#05x}] live {fn:#x}  ->  exe {pe.image_base + (fn - mod_base):#x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
