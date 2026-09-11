#!/usr/bin/env python3
"""Find where a native UE4 multicast delegate is *broadcast*, from its shape.

Why this and not an offset scan
-------------------------------
Checkpoint 17 looked for `lea/add rcx, +0xF0` feeding a call.  `+0xF0` is a common
offset (472 sites image-wide) and the two hits it found call `0x140c53e30`, which
disassembles to a `TArray<TDelegateBase>::Empty` -- delegate *teardown*, not
`Broadcast`.  A bare offset cannot tell those apart.

The invocation list can:

    FMulticastDelegateBase<FWeakObjectPtr>            (0x18 bytes)
      +0x00 TDelegateBase* Data   +0x08 int32 Num   +0x0C int32 Max
      +0x10 int32 ExpirableObjectCount               +0x14 int32 LockCount

`Broadcast` is inlined in shipping builds, so there is no call target to xref, but
whatever inlines it *must* load `Data` and `Num` -- it walks
`for (i = Num-1; i >= 0; --i) InvocationList[i]->ExecuteIfSafe()`.  For a delegate
at `Owner + D` that is a qword read of `[reg + D]` and a dword read of
`[reg + D + 8]` inside one function.  Teardown reads `Data` and `Max`
(`[reg + D + 0xC]`) instead, which is what separates them.

Self-validating.  `--offsets` defaults to the delegate under investigation
(`UWW3InventoryManager + 0xF0`, whose bound callback `0x1411c0f30` never fires --
`_delegate_live.py` proves it is bound) *and* the control
(`UWW3CharacterAttachmentManager + 0x120`: same delegate type, same instance
vtable, bound by the same constructor, and its sync bit IS set).  If the control
yields no site the signature is wrong and the other result means nothing.

Static: reads the on-disk exe only.

Usage:
    python match_server/_delegate_broadcast_scan.py
    python match_server/_delegate_broadcast_scan.py --offsets 0xF0,0x120 --verbose
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _exe_fn import FnIndex  # noqa: E402
from _exe_pe import PE  # noqa: E402

MEM = re.compile(r"(qword|dword|word|byte) ptr \[(r[a-z0-9]+) \+ (0x[0-9a-f]+)\]")


def scan(pe: PE, idx: FnIndex, wanted: set[int]):
    """fn -> {disp -> set(operand sizes)} restricted to the displacements asked for."""
    from capstone import CS_ARCH_X86, CS_MODE_64, Cs
    md = Cs(CS_ARCH_X86, CS_MODE_64)

    roots: dict[int, int] = {}          # chunk.beg -> root fn
    for c in idx.chunks:
        r = idx.primary(c.beg)
        roots[c.beg] = r.beg if r else c.beg

    hits: dict[int, dict[int, set[str]]] = defaultdict(lambda: defaultdict(set))
    calls: dict[int, int] = defaultdict(int)
    for c in idx.chunks:
        off = pe.va_to_off(c.beg)
        if off is None or c.end <= c.beg:
            continue
        root = roots[c.beg]
        for _addr, _size, mnem, ops in md.disasm_lite(
                pe.data[off:off + (c.end - c.beg)], c.beg):
            if mnem == "call" and "ptr [" in ops:
                calls[root] += 1
            if "0x" not in ops:
                continue
            for width, reg, disp in MEM.findall(ops):
                d = int(disp, 16)
                if d in wanted and reg != "rsp":
                    hits[root][d].add(width)
    return hits, calls


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offsets", default="0xF0,0x120")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    pe = PE()
    idx = FnIndex(pe)
    offs = [int(x, 0) for x in args.offsets.split(",")]
    wanted = set()
    for o in offs:
        wanted.update((o, o + 8, o + 0xC))
    print(f"scanning {len(idx.chunks)} .pdata chunk(s) for displacements "
          f"{sorted(hex(w) for w in wanted)} ...")
    hits, calls = scan(pe, idx, wanted)
    print(f"{len(hits)} function(s) touch at least one of them\n")

    for o in offs:
        broadcast, teardown = [], []
        for fn, disps in hits.items():
            has_data = "qword" in disps.get(o, set())
            has_num = "dword" in disps.get(o + 8, set())
            has_max = "dword" in disps.get(o + 0xC, set())
            if has_data and has_num:
                broadcast.append(fn)
            elif has_data and has_max:
                teardown.append(fn)
        print(f"== delegate at owner+{o:#x}")
        print(f"   BROADCAST-shaped (reads Data@+{o:#x} and Num@+{o + 8:#x}): "
              f"{len(broadcast)}")
        for fn in sorted(broadcast):
            print(f"     fn {fn:#x}   indirect calls: {calls.get(fn, 0)}")
        print(f"   teardown-shaped (Data + Max@+{o + 0xC:#x}): {len(teardown)}"
              f"  {[hex(f) for f in sorted(teardown)[:8]]}")
        if args.verbose:
            for fn in sorted(hits):
                if o in hits[fn]:
                    print(f"     touches: fn {fn:#x} -> "
                          f"{ {hex(d): sorted(w) for d, w in sorted(hits[fn].items())} }")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
