#!/usr/bin/env python3
"""Find call/jmp sites targeting a given VA, and recover the constant loaded
into a chosen argument register just before the call.

The client's synchronization checklist is a single bitmask byte, written by one
mutator (`MarkSynchronized(uint8 Mask)`).  Which bit a call site sets is the
whole semantic content of that call site, so the scanner reports the immediate
moved into `dl`/`edx` in the instructions preceding each call.
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _exe_pe import PE  # noqa: E402
from _exe_fn import FnIndex  # noqa: E402


def call_sites(pe: PE, target: int) -> list[tuple[int, str]]:
    """Every `call rel32` / `jmp rel32` whose destination is `target`."""
    out = []
    for s in pe.sections:
        if not s.executable:
            continue
        blob = pe.data[s.raw:s.raw + s.rsize]
        base = s.va
        for op, kind in ((0xE8, "call"), (0xE9, "jmp")):
            i = 0
            while True:
                k = blob.find(bytes([op]), i)
                if k < 0 or k + 5 > len(blob):
                    break
                rel = struct.unpack_from("<i", blob, k + 1)[0]
                if base + k + 5 + rel == target:
                    out.append((base + k, kind))
                i = k + 1
    out.sort()
    return out


def preceding(pe: PE, va: int, back: int = 64):
    """Disassemble linearly up to `va`, returning the instructions that land
    exactly on it (greedy longest valid decode from several start offsets)."""
    from capstone import CS_ARCH_X86, CS_MODE_64, Cs
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    off = pe.va_to_off(va)
    for skew in range(back, 3, -1):
        start = va - skew
        code = pe.data[off - skew:off]
        ins = list(md.disasm(code, start))
        if ins and ins[-1].address + ins[-1].size == va:
            return ins
    return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="hex VA of the callee")
    ap.add_argument("--back", type=int, default=48)
    ap.add_argument("--regs", default="dl,edx,dx,rdx")
    args = ap.parse_args()

    pe = PE()
    idx = FnIndex(pe)
    target = int(args.target, 16)
    regs = set(args.regs.split(","))
    sites = call_sites(pe, target)
    print(f"{len(sites)} site(s) targeting {target:#x}")
    for va, kind in sites:
        fn = idx.primary(va)
        fnstr = f"{fn.beg:#x}" if fn else "?"
        arg = None
        ctx = []
        for ins in preceding(pe, va, args.back):
            ctx.append(f"{ins.mnemonic} {ins.op_str}")
            ops = ins.op_str.split(", ")
            if ins.mnemonic in ("mov", "xor") and len(ops) == 2 and ops[0] in regs:
                if ins.mnemonic == "xor" and ops[0] == ops[1]:
                    arg = 0
                elif ops[1].startswith("0x") or ops[1].isdigit():
                    arg = int(ops[1], 0)
                else:
                    arg = f"<{ops[1]}>"
        print(f"\n  {kind} at {va:#x}   in fn {fnstr}   arg={arg}")
        for c in ctx[-8:]:
            print(f"        {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
