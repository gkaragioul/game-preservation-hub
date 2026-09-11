#!/usr/bin/env python3
"""Recover a UE `FArchive` (de)serialiser's exact wire field list.

`_archive_ops.py` condenses a serialiser but its destination heuristic reads the
first store *after* the bounds check, which is wrong for `FArchive::operator<<
(bool&)`: that helper serialises an `int32` through a scratch slot and only then
stores a byte into the object.  On `TM_Synchronize` it therefore reported the
final per-slot bool as landing at `+0x60` when the real store is `+0x61`, and it
attributed the trailing `FString` to `[rcx]`.

This walks the stitched function and reports one line per archive operation with
both facts kept separate:

  * `size`  -- bytes on the wire, from UE 4.21's `FArchive::FastPathLoad<N>()`
               inline (`mov rdx,[rcx]; lea rax,[rdx+N]; cmp rax,[rcx+8]; ja`)
               or from `mov r8d, N` before `call qword ptr [rax+0x48]`
               (`FArchive::Serialize(void*, int64)`),
  * `wire`  -- the buffer/scratch address the archive was handed,
  * `store` -- where the value is actually written afterwards, which for a bool
               is a `setne`/`sete` byte store at a different offset.

Usage:
    python match_server/_archive_fields.py 0x140990c90
    python match_server/_archive_fields.py 0x140990c90 --range 0x140991b40 0x1409927ee
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _exe_fn import FnIndex  # noqa: E402
from _exe_pe import PE  # noqa: E402

SERIALIZE_SLOT = "qword ptr [rax + 0x48]"   # FArchive::Serialize(void*, int64)
BYTESWAP = 0x1419AF170
FSTRING = 0x141884C80
MEM_RE = re.compile(r"^(byte|word|dword|qword) ptr \[(\w+)(?: ([+-]) (0x[0-9a-f]+|\d+))?\]$")
LEA_RE = re.compile(r"^(\w+), \[(\w+)(?: ([+-]) (0x[0-9a-f]+|\d+))?\]$")


def _mem(text: str) -> str | None:
    m = MEM_RE.match(text.strip())
    if not m:
        return None
    _, reg, sign, off = m.groups()
    if off is None:
        return f"[{reg}]"
    return f"[{reg}{sign}{int(off, 0):#x}]"


def _lea_dest(op_str: str) -> tuple[str, str] | None:
    m = LEA_RE.match(op_str.strip())
    if not m:
        return None
    dst, reg, sign, off = m.groups()
    if off is None:
        return dst, f"[{reg}]"
    return dst, f"[{reg}{sign}{int(off, 0):#x}]"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("va", type=lambda s: int(s, 0))
    ap.add_argument("--range", nargs=2, type=lambda s: int(s, 0), default=None,
                    metavar=("LO", "HI"))
    args = ap.parse_args()

    from capstone import CS_ARCH_X86, CS_MODE_64, Cs

    pe = PE()
    fns = FnIndex(pe)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    root = fns.primary(args.va)
    if root is None:
        print(f"no .pdata entry covering {args.va:#x}")
        return 1
    ins = []
    for c in fns.all_chunks_of(root.beg):
        off = pe.va_to_off(c.beg)
        ins.extend(list(md.disasm(pe.data[off:off + (c.end - c.beg)], c.beg)))

    back_edges: dict[int, int] = {}
    for k in ins:
        if k.mnemonic.startswith("j"):
            t = k.op_str.strip()
            if re.fullmatch(r"0x[0-9a-f]+", t) and int(t, 16) < k.address:
                back_edges.setdefault(int(t, 16), k.address)

    lo, hi = args.range if args.range else (root.beg, 1 << 63)
    print(f"; fn {root.beg:#x}  {len(ins)} instructions")
    print("; size = bytes on the wire | wire = archive buffer arg | "
          "store = where the value lands\n")

    for i, k in enumerate(ins):
        if not (lo <= k.address < hi):
            continue
        if k.address in back_edges:
            print(f"  {k.address:#x}  <== loop head (back edge from "
                  f"{back_edges[k.address]:#x})")

        size = None
        wire = None

        # UE 4.21 FArchive::FastPathLoad<N>: the bounds check itself names N.
        if k.mnemonic == "lea" and i + 2 < len(ins):
            d = _lea_dest(k.op_str)
            nxt, nx2 = ins[i + 1], ins[i + 2]
            if (d and d[0] == "rax" and nxt.mnemonic == "cmp"
                    and nxt.op_str.endswith("+ 8]") and nx2.mnemonic == "ja"):
                m = re.match(r"\[(\w+)\+(0x[0-9a-f]+)\]", d[1])
                if m:
                    size = int(m.group(2), 0)
                    wire = "fastpath"

        # Generic path: mov r8d, N ; lea rdx, DEST ; call [rax+0x48]
        if k.mnemonic == "call" and k.op_str.strip() == SERIALIZE_SLOT:
            for j in range(i - 1, max(i - 14, -1), -1):
                p = ins[j]
                if size is None and p.mnemonic == "mov" and p.op_str.startswith("r8d, "):
                    size = int(p.op_str.split(", ")[1], 0)
                if wire in (None, "fastpath") and p.mnemonic == "lea":
                    d = _lea_dest(p.op_str)
                    if d and d[0] == "rdx":
                        wire = d[1]
                if size is not None and wire not in (None, "fastpath"):
                    break
            if wire == "fastpath":
                wire = "?"

        if size is None:
            if k.mnemonic == "call" and re.fullmatch(r"0x[0-9a-f]+", k.op_str.strip()):
                t = int(k.op_str, 16)
                if t == FSTRING:
                    dest = "?"
                    for j in range(i - 1, max(i - 8, -1), -1):
                        d = _lea_dest(ins[j].op_str) if ins[j].mnemonic == "lea" else None
                        if d and d[0] == "rdx":
                            dest = d[1]
                            break
                    print(f"  {k.address:#x}  FString                 -> {dest}")
                elif t != BYTESWAP:
                    print(f"  {k.address:#x}  call {t:#x}")
            continue

        # Where does it land?  A bool round-trips through setne/sete.
        store = "?"
        kind = f"raw{size}"
        for j in range(i + 1, min(i + 22, len(ins))):
            q = ins[j]
            if q.mnemonic in ("setne", "sete"):
                kind = f"bool(int{size * 8})"
                continue
            if q.mnemonic == "call":
                break
            if q.mnemonic in ("mov", "movzx") and "," in q.op_str:
                dst = q.op_str.split(",")[0].strip()
                mem = _mem(dst)
                if mem and "rbp" not in mem and "rsp" not in mem:
                    store = mem
                    break
                if mem and store == "?":
                    store = mem            # scratch: a count, not a member
        print(f"  {k.address:#x}  {kind:<14} wire={wire:<12} store={store}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
