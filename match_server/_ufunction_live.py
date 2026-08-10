#!/usr/bin/env python3
"""Resolve a UFunction's native code address from the live client, then
disassemble it out of the on-disk exe.

`AWW3ActionReplicator`'s checks are compiled out, so `_exe_srcmap.py` cannot
find its functions and there is no symbol to search for. But every `UFunction`
carries its `exec` thunk pointer at +0xB0, and the live `GObjects` array names
every UFunction exactly (`_uobject_live.py`). So:

    GObjects[idx] -> UFunction -> +0xB0 ExecFunction (live VA)
                  -> RVA = live - module base
                  -> exe VA = PE image base + RVA
                  -> `.pdata`-stitched disassembly (`_exe_fn.py`)

The exec thunk is the generated `execClient_ReceivePacket`; it unpacks the stack
parameters and tail-calls `..._Implementation`, which is what we actually want to
read.

Read-only on the live process.

Usage:
    python match_server/_ufunction_live.py WW3.WW3ActionReplicator.Client_ReceivePacket
    python match_server/_ufunction_live.py WW3.WW3ActionReplicator.Client_ReceivePacket --disasm
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
from _uobject_live import DUMP_ROOT, Objects, header, load_dump  # noqa: E402

FUNC_EXEC = 0xB0
FUNC_FLAGS = 0x88
STRUCT_SIZE = 0x40


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="+", help="full dump names of UFunctions")
    ap.add_argument("--dump", default=str(DUMP_ROOT / "GObjects-Dump.txt"))
    ap.add_argument("--disasm", action="store_true")
    ap.add_argument("--follow", action="store_true",
                    help="also disassemble the first call target (the _Implementation)")
    args = ap.parse_args()

    pid = find_pid()
    mem = Mem(pid)
    mod_base, mod_size = main_module(pid)
    objs = Objects(mem, mod_base)
    by_index, by_name = load_dump(Path(args.dump))
    pe = PE()
    fns = FnIndex(pe)
    print(f"pid={pid} live module={mod_base:#x}  exe image_base={pe.image_base:#x}")

    for name in args.names:
        idx = by_name.get(name) or by_name.get("Function " + name)
        if idx is None:
            print(f"\n{name}: not in dump")
            continue
        obj = objs.ptr(idx)
        h = header(mem, obj) if obj else None
        if not h or h["index"] != idx:
            print(f"\n{name}: GObjects[{idx:#x}] does not round-trip -- stale index")
            continue
        flags = mem.u32(obj + FUNC_FLAGS)
        params = mem.u32(obj + STRUCT_SIZE)
        execfn = mem.u64(obj + FUNC_EXEC)
        print(f"\n=== {name}")
        print(f"  UFunction   = {obj:#x} (idx {idx:#x})")
        print(f"  FunctionFlags= {flags:#x}  ParmsSize={params}")
        if not execfn or not (mod_base <= execfn < mod_base + mod_size):
            print(f"  ExecFunction= {execfn:#x} (outside the image)")
            continue
        rva = execfn - mod_base
        exe_va = pe.image_base + rva
        print(f"  ExecFunction= live {execfn:#x}  rva {rva:#x}  exe {exe_va:#x}")
        if args.disasm or args.follow:
            disasm_fn(pe, fns, exe_va)
        if args.follow:
            # first `call rel32` inside the thunk is the _Implementation
            c = fns.primary(exe_va)
            if not c:
                continue
            off = pe.va_to_off(c.beg)
            blob = pe.data[off:off + (c.end - c.beg)]
            i = 0
            targets = []
            while i < len(blob) - 5:
                if blob[i] in (0xE8, 0xE9):
                    rel = struct.unpack_from("<i", blob, i + 1)[0]
                    targets.append(c.beg + i + 5 + rel)
                i += 1
            print(f"\n  call/jmp targets from the thunk: "
                  f"{[hex(t) for t in targets[:8]]}")
            for t in targets[:2]:
                print(f"\n  ----- following {t:#x}")
                disasm_fn(pe, fns, t)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
