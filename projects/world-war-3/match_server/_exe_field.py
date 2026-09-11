#!/usr/bin/env python3
"""Find every instruction that touches `[reg + <offset>]` in the shipping client.

Reverse engineering the checklist reduced the PlayerState item to a single
predicate - `IsValid(r15->[0x710])` - so the question "why is the bit never set"
becomes "who writes 0x710, and under what conditions".  Linear disassembly of a
60 MB .text is too slow, so this scans for the encodings directly and only
disassembles around the hits.

Usage:
    python match_server/_exe_field.py 0x710
    python match_server/_exe_field.py 0x710 --stores-only
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _exe_pe import PE  # noqa: E402
from _exe_fn import FnIndex  # noqa: E402

REG64 = ["rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi",
         "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"]


def scan(pe: PE, disp: int, stores_only: bool):
    """Yield (va, text) for `mov [base+disp], src` and `mov dst, [base+disp]`."""
    key = struct.pack("<i", disp)
    for s in pe.sections:
        if not s.executable:
            continue
        blob = pe.data[s.raw:s.raw + s.rsize]
        i = 0
        while True:
            k = blob.find(key, i)
            if k < 0:
                break
            i = k + 1
            # Walk back over: [REX] opcode modrm [SIB]
            for sib in (0, 1):
                pos = k - 1 - sib
                if pos < 2:
                    continue
                modrm = blob[pos]
                if modrm & 0xC0 != 0x80:
                    continue
                if (modrm & 0x07 == 4) != bool(sib):
                    continue
                op = blob[pos - 1]
                rex = blob[pos - 2]
                if rex & 0xF0 != 0x40 or not (rex & 0x08):
                    continue
                if op == 0x89:
                    kind = "store"
                elif op == 0x8B:
                    kind = "load"
                elif op == 0x8D:
                    kind = "lea"
                else:
                    continue
                if stores_only and kind != "store":
                    continue
                reg = ((rex & 0x04) << 1) | ((modrm >> 3) & 7)
                rm = ((rex & 0x01) << 3) | (modrm & 7)
                base = REG64[rm] if not sib else f"sib({blob[k-1]:#04x})"
                if kind == "store":
                    txt = f"mov qword ptr [{base} + {disp:#x}], {REG64[reg]}"
                elif kind == "load":
                    txt = f"mov {REG64[reg]}, qword ptr [{base} + {disp:#x}]"
                else:
                    txt = f"lea {REG64[reg]}, [{base} + {disp:#x}]"
                yield s.va + pos - 2, kind, txt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("offset")
    ap.add_argument("--stores-only", action="store_true")
    args = ap.parse_args()

    pe = PE()
    idx = FnIndex(pe)
    disp = int(args.offset, 0)
    rows = list(scan(pe, disp, args.stores_only))
    by_fn: dict[int, list] = {}
    for va, kind, txt in rows:
        fn = idx.primary(va)
        by_fn.setdefault(fn.beg if fn else 0, []).append((va, kind, txt))
    print(f"{len(rows)} hit(s) for +{disp:#x} across {len(by_fn)} function(s)\n")
    for fnbeg, hits in sorted(by_fn.items()):
        kinds = {k for _, k, _ in hits}
        print(f"fn {fnbeg:#x}   ({len(hits)} hit(s), {'/'.join(sorted(kinds))})")
        for va, kind, txt in hits:
            print(f"    {va:#014x}  {kind:<5} {txt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
