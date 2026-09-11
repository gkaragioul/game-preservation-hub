#!/usr/bin/env python3
"""Recover `EWW3ReplicatedActionType` -> action class, from the client's own
action factory.

`AWW3ActionReplicator::Client_ReceivePacket_Implementation` (exe 0x140873980,
found via the live vtable slot 0x640) parses:

    int32  TotalSize        # whole packet, fragments concatenated
    int32  ActionCount
    repeat ActionCount:
        uint8  ActionType
        <body, UWW3ReplicatedAction::Serialize -- vtable +0x240>

and turns each `ActionType` byte into an object through a factory at
0x140872d30, which is a 32-case jump table on `ActionType - 1`. Every case calls
that action class's `StaticClass()` accessor, and each accessor just returns a
cached `.data` global. The globals are meaningless on disk but the live process
has them filled in, and `GObjects` names them (`_uobject_live.py`).

So the enum's numeric values are recovered from the binary itself rather than
guessed from the order of the `EWW3ReplicatedActionType::...` strings in .rdata.

Read-only on the live process.

Usage:
    python match_server/_action_type_map.py
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _exe_pe import PE  # noqa: E402
from _ps_sync_live import Mem, find_pid, main_module  # noqa: E402
from _uobject_live import DUMP_ROOT, OBJ_INDEX, Objects, load_dump  # noqa: E402

FACTORY = 0x140872D30
JUMP_TABLE = 0x1408731A4
CASES = 0x20


def calls_from(pe: PE, va: int, limit: int = 0x60) -> list[int]:
    off = pe.va_to_off(va)
    if off is None:
        return []
    blob = pe.data[off:off + limit]
    out = []
    i = 0
    while i < len(blob) - 5:
        if blob[i] == 0xE8:
            rel = struct.unpack_from("<i", blob, i + 1)[0]
            out.append(va + i + 5 + rel)
            i += 5
            continue
        i += 1
    return out


def global_read_by(pe: PE, va: int, limit: int = 0x40) -> int | None:
    """The first rip-relative qword load in a `StaticClass()` accessor."""
    off = pe.va_to_off(va)
    if off is None:
        return None
    blob = pe.data[off:off + limit]
    i = 0
    while i < len(blob) - 7:
        b = blob[i]
        if 0x48 <= b <= 0x4F and blob[i + 1] in (0x8B, 0x8D) and (blob[i + 2] & 0xC7) == 0x05:
            disp = struct.unpack_from("<i", blob, i + 3)[0]
            return va + i + 7 + disp
        i += 1
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=str(DUMP_ROOT / "GObjects-Dump.txt"))
    args = ap.parse_args()

    pid = find_pid()
    mem = Mem(pid)
    mod_base, mod_size = main_module(pid)
    objs = Objects(mem, mod_base)
    by_index, _by_name = load_dump(Path(args.dump))
    pe = PE()

    tbl_off = pe.va_to_off(JUMP_TABLE)
    entries = struct.unpack_from(f"<{CASES}I", pe.data, tbl_off)
    print(f"factory {FACTORY:#x}, jump table {JUMP_TABLE:#x}, {CASES} cases\n")
    print(f"{'type':>5}  {'case':<14} {'StaticClass':<14} {'global(exe)':<14} class")
    rows = []
    for i, ent in enumerate(entries):
        case_va = pe.image_base + ent
        cs = calls_from(pe, case_va)
        # case shape: call <log/scope>, call <StaticClass>, ... then shared tail
        sc = cs[1] if len(cs) > 1 else (cs[0] if cs else None)
        name = "?"
        gvar = None
        if sc:
            gvar = global_read_by(pe, sc)
            if gvar:
                live = mod_base + (gvar - pe.image_base)
                cls = mem.u64(live)
                if cls:
                    h = mem.read(cls, 0x28)
                    if h:
                        idx = struct.unpack_from("<i", h, OBJ_INDEX)[0]
                        if objs.ptr(idx) == cls:
                            name = by_index.get(idx, ("?", "?"))[1]
        rows.append((i + 1, case_va, sc, gvar, name))
        print(f"{i+1:>5}  {case_va:#x}  {sc:#x}  "
              f"{gvar:#x}  {name}" if sc and gvar else
              f"{i+1:>5}  {case_va:#x}  {sc}  {gvar}  {name}")

    print("\n=== EWW3ReplicatedActionType (recovered) ===")
    print("    0  Action_None")
    for t, _c, _s, _g, name in rows:
        short = name.split(".")[-1].replace("WW3ReplicatedAction_", "")
        print(f"  {t:>3}  {short}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
