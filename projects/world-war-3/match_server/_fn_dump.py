#!/usr/bin/env python3
"""Dump one stitched shipping-client function as annotated disassembly.

`_exe_fn.py` already knows how to stitch MSVC's hot/cold `.pdata` chunks back
into one logical function and annotate rip-relative string references; it just
had no CLI.  This is that CLI, plus a `--range` window so a 1600-instruction
serialiser can be read a screen at a time.

Usage:
    python match_server/_fn_dump.py 0x140873980
    python match_server/_fn_dump.py 0x140873980 --range 0x140873a80 0x140873d60
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _exe_fn import FnIndex, disasm_fn  # noqa: E402
from _exe_pe import PE  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("va", type=lambda s: int(s, 0))
    ap.add_argument("--range", nargs=2, type=lambda s: int(s, 0), default=None,
                    metavar=("LO", "HI"), help="only print instructions in [LO, HI)")
    ap.add_argument("--raw", type=lambda s: int(s, 0), default=0,
                    help="disassemble N bytes linearly instead of using .pdata "
                         "(UFunction exec thunks are leaves and have no unwind entry)")
    args = ap.parse_args()

    # Annotations can quote UTF-16 blobs the console codepage cannot encode; a
    # disassembly listing must never die on one of them.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    pe = PE()
    idx = FnIndex(pe)
    lines: list[str] = []
    if args.raw:
        from capstone import CS_ARCH_X86, CS_MODE_64, Cs

        from _exe_fn import annotate
        md = Cs(CS_ARCH_X86, CS_MODE_64)
        off = pe.va_to_off(args.va)
        if off is None:
            print(f"; {args.va:#x} is not in any section")
            return 1
        print(f"; raw {args.raw} byte(s) at {args.va:#x}")
        for ins in md.disasm(pe.data[off:off + args.raw], args.va):
            print(f"  {ins.address:#014x}  {ins.mnemonic:<9} {ins.op_str}"
                  f"{annotate(pe, ins)}")
        return 0
    disasm_fn(pe, idx, args.va, out=lines.append)
    lo, hi = args.range if args.range else (None, None)
    for line in lines:
        if lo is None or line.startswith(";"):
            print(line)
            continue
        try:
            addr = int(line.split()[0], 16)
        except (ValueError, IndexError):
            print(line)
            continue
        if lo <= addr < hi:
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
