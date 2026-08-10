#!/usr/bin/env python3
"""Function-level view of the shipping client: `.pdata` chunk resolution +
disassembly with string annotation.

MSVC splits hot/cold paths, so a single logical function shows up as several
`RUNTIME_FUNCTION` entries; the cold chunks carry `UNW_FLAG_CHAININFO` and point
back at the primary chunk.  Reading only the chunk that happens to contain a
string reference gives a truncated, jump-into-nowhere listing (that is why the
first pass at the `OnSynchronized` reporters looked headless).  This module
stitches the chunks back together.
"""
from __future__ import annotations

import struct
import sys
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _exe_pe import PE  # noqa: E402

UNW_FLAG_CHAININFO = 0x4


@dataclass(frozen=True)
class Chunk:
    beg: int
    end: int
    unwind: int


class FnIndex:
    def __init__(self, pe: PE):
        self.pe = pe
        sec = next(s for s in pe.sections if s.name == ".pdata")
        blob = pe.data[sec.raw:sec.raw + sec.rsize]
        chunks: list[Chunk] = []
        for i in range(0, len(blob) - 11, 12):
            beg, end, unw = struct.unpack_from("<III", blob, i)
            if beg == 0 and end == 0:
                continue
            chunks.append(Chunk(pe.image_base + beg, pe.image_base + end,
                                pe.image_base + unw))
        chunks.sort(key=lambda c: c.beg)
        self.chunks = chunks
        self.starts = [c.beg for c in chunks]

    def chunk_at(self, va: int) -> Chunk | None:
        i = bisect_right(self.starts, va) - 1
        if i < 0:
            return None
        c = self.chunks[i]
        return c if c.beg <= va < c.end else None

    def _chain_parent(self, c: Chunk) -> Chunk | None:
        """If this chunk chains to another, return the parent chunk."""
        off = self.pe.va_to_off(c.unwind)
        if off is None:
            return None
        ver_flags = self.pe.data[off]
        flags = ver_flags >> 3
        if not (flags & UNW_FLAG_CHAININFO):
            return None
        count = self.pe.data[off + 2]
        # UNWIND_INFO: 4 byte header + 2 bytes per code, padded to 4 bytes,
        # then the chained RUNTIME_FUNCTION.
        tail = off + 4 + 2 * ((count + 1) & ~1)
        beg, end, unw = struct.unpack_from("<III", self.pe.data, tail)
        return Chunk(self.pe.image_base + beg, self.pe.image_base + end,
                     self.pe.image_base + unw)

    def primary(self, va: int) -> Chunk | None:
        c = self.chunk_at(va)
        seen = set()
        while c is not None and c.beg not in seen:
            seen.add(c.beg)
            p = self._chain_parent(c)
            if p is None:
                return c
            c = self.chunk_at(p.beg) or p
        return c

    def all_chunks_of(self, primary_beg: int) -> list[Chunk]:
        """Every chunk whose chain root is `primary_beg`, in address order."""
        out = []
        for c in self.chunks:
            root = self.primary(c.beg)
            if root and root.beg == primary_beg:
                out.append(c)
        return out


def annotate(pe: PE, ins, extra: dict[int, str] | None = None) -> str:
    if "rip" not in ins.op_str:
        return ""
    try:
        s = ins.op_str
        k = s.index("[rip")
        seg = s[k:s.index("]", k)]
        sign = 1 if "+" in seg else -1
        num = seg.split("+")[-1] if sign > 0 else seg.split("-")[-1]
        disp = sign * int(num.strip(), 16)
    except Exception:
        return ""
    tgt = ins.address + ins.size + disp
    if extra and tgt in extra:
        return f"   ; {extra[tgt]}"
    if ins.mnemonic in ("lea",):
        w = pe.wstring_at_va(tgt, 400)
        if w and len(w) > 2:
            return f"   ; L{w!r}"
        c = pe.cstring_at_va(tgt, 200)
        if c and len(c) > 3 and c.isprintable():
            return f"   ; {c!r}"
    return f"   ; [{tgt:#x}]"


def disasm_fn(pe: PE, idx: FnIndex, va: int, extra: dict[int, str] | None = None,
              out=print) -> None:
    from capstone import CS_ARCH_X86, CS_MODE_64, Cs
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    root = idx.primary(va)
    if root is None:
        out(f"; no .pdata entry covering {va:#x}")
        return
    chunks = idx.all_chunks_of(root.beg)
    total = sum(c.end - c.beg for c in chunks)
    out(f"; fn {root.beg:#x}  ({len(chunks)} chunk(s), {total} bytes)")
    for c in chunks:
        out(f"; --- chunk {c.beg:#x}..{c.end:#x} ---")
        off = pe.va_to_off(c.beg)
        code = pe.data[off:off + (c.end - c.beg)]
        for ins in md.disasm(code, c.beg):
            out(f"  {ins.address:#014x}  {ins.mnemonic:<9} {ins.op_str}"
                f"{annotate(pe, ins, extra)}")
