#!/usr/bin/env python3
"""Condense a UE `FArchive` (de)serialiser into its wire operations.

The action serialisers in `WW3` are `Ar << field` chains compiled with the
`FMemoryReader` fast path inlined, so each logical read expands into ~8
instructions plus, in this checked build, large `check()` blocks that dwarf the
actual format. This walks the stitched function and reports only:

  * archive reads/writes -- the inlined form
        mov rdx,[rcx]; lea rax,[rdx+N]; cmp rax,[rcx+8]; ja slow
        <fast copy of N bytes into DEST>
    and the slow form `call [rax+0x48]` with `r8d = N`,
  * byte-swap fixups (`call 0x1419af170`),
  * loop back-edges, so nested `TArray` structure is visible,
  * calls that are not assertion helpers.

Usage:
    python match_server/_archive_ops.py 0x140990c90
    python match_server/_archive_ops.py 0x140990c90 --raw
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _exe_fn import FnIndex  # noqa: E402
from _exe_pe import PE  # noqa: E402

ASSERT_HELPERS = {0x141941320, 0x141937210}
BYTESWAP = 0x1419AF170
CALL_RE = re.compile(r"^0x([0-9a-f]+)$")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("va", type=lambda s: int(s, 0))
    ap.add_argument("--limit", type=int, default=400)
    args = ap.parse_args()

    from capstone import CS_ARCH_X86, CS_MODE_64, Cs

    pe = PE()
    fns = FnIndex(pe)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    root = fns.primary(args.va)
    if root is None:
        print(f"no .pdata entry covering {args.va:#x}")
        return 1
    chunks = fns.all_chunks_of(root.beg)
    ins_list = []
    for c in chunks:
        off = pe.va_to_off(c.beg)
        code = pe.data[off:off + (c.end - c.beg)]
        ins_list.extend(list(md.disasm(code, c.beg)))

    # branch targets that jump backwards = loop heads
    back_edges: dict[int, int] = {}
    for ins in ins_list:
        if ins.mnemonic.startswith("j"):
            m = CALL_RE.match(ins.op_str.strip())
            if m:
                t = int(m.group(1), 16)
                if t < ins.address:
                    back_edges[t] = ins.address

    print(f"; fn {root.beg:#x}  ({len(chunks)} chunk(s), {len(ins_list)} instructions)")
    print("; ops: R<n> = archive read/write of n bytes, DEST shown\n")
    n_ops = 0
    i = 0
    while i < len(ins_list) and n_ops < args.limit:
        ins = ins_list[i]
        if ins.address in back_edges:
            print(f"  {ins.address:#x}  <-- loop head (back edge from "
                  f"{back_edges[ins.address]:#x})")
        # fast path: lea rax,[rXX + N] ; cmp rax,[rYY+8] ; ja slow
        if ins.mnemonic == "lea" and "+" in ins.op_str and i + 3 < len(ins_list):
            m = re.match(r"(\w+), \[(\w+) \+ (0x[0-9a-f]+|\d+)\]", ins.op_str)
            nxt = ins_list[i + 1]
            if m and nxt.mnemonic == "cmp" and "+ 8]" in nxt.op_str:
                size = int(m.group(3), 0)
                dest = "?"
                for k in range(i + 2, min(i + 10, len(ins_list))):
                    q = ins_list[k]
                    if q.mnemonic in ("mov", "movzx") and q.op_str.startswith(
                            ("byte ptr", "dword ptr", "qword ptr", "word ptr")):
                        dest = q.op_str.split(",")[0].strip()
                        break
                    if q.mnemonic == "lea" and "rdx," in q.op_str:
                        dest = q.op_str.split(",", 1)[1].strip()
                        break
                print(f"  {ins.address:#x}  R{size:<3} -> {dest}")
                n_ops += 1
                i += 2
                continue
        if ins.mnemonic == "call":
            m = CALL_RE.match(ins.op_str.strip())
            if m:
                t = int(m.group(1), 16)
                if t in ASSERT_HELPERS:
                    i += 1
                    continue
                if t == BYTESWAP:
                    print(f"  {ins.address:#x}  (byteswap fixup)")
                    i += 1
                    continue
                print(f"  {ins.address:#x}  call {t:#x}")
                n_ops += 1
        i += 1
    if n_ops >= args.limit:
        print(f"  ... truncated at {args.limit} ops")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
