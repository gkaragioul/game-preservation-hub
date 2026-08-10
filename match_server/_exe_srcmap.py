#!/usr/bin/env python3
"""Recover the game's own source-file map from the shipping client.

This build keeps its `check()`/`ensure()` metadata: every assertion materialises
an ANSI source path (`D:\\W3\\c\\WW3\\Source\\ShooterGame\\Private\\...cpp`), the
condition text, and the line number (`mov r8d, <line>`). That turns a stripped
binary into something with a table of contents -- for each source file we can
list the functions that contain code from it, ordered by line number.

Used to locate `AWW3TeamManager`'s graph-construction code, since the live client
has a TeamManager whose `Teams` array is empty (`_team_graph_live.py`).

Usage:
    python match_server/_exe_srcmap.py --list
    python match_server/_exe_srcmap.py --file WW3TeamManager.cpp
    python match_server/_exe_srcmap.py --file WW3TeamManager.cpp --conditions
"""
from __future__ import annotations

import argparse
import re
import struct
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _exe_fn import FnIndex  # noqa: E402
from _exe_pe import PE  # noqa: E402

PRINTABLE = re.compile(rb"[ -~]{6,240}")


def source_paths(pe: PE) -> dict[str, int]:
    """Every embedded WW3 source path -> its VA."""
    out: dict[str, int] = {}
    needle = b"Source" + bytes([0x5C])  # "Source\"
    start = 0
    d = pe.data
    while True:
        k = d.find(needle, start)
        if k < 0:
            break
        start = k + 1
        s = k
        while s > 0 and 32 <= d[s - 1] < 127:
            s -= 1
        e = k
        while e < len(d) and 32 <= d[e] < 127:
            e += 1
        txt = d[s:e].decode("ascii", "replace")
        if not txt.lower().endswith((".cpp", ".h", ".inl")):
            continue
        va = pe.off_to_va(s)
        if va is not None:
            out.setdefault(txt, va)
    return out


def line_before(pe: PE, va: int, back: int = 40) -> int | None:
    """The `mov r8d, imm32` line number emitted just before the path `lea`."""
    off = pe.va_to_off(va)
    if off is None:
        return None
    blob = pe.data[max(0, off - back):off]
    best = None
    for i in range(len(blob) - 4):
        if blob[i] == 0x41 and blob[i + 1] == 0xB8:  # mov r8d, imm32
            best = struct.unpack_from("<I", blob, i + 2)[0]
        elif blob[i] == 0xB8:  # mov eax, imm32 (rare form)
            pass
    return best


def condition_near(pe: PE, va: int, back: int = 64) -> str | None:
    """The condition string `lea rcx,[rip+..]` immediately preceding."""
    off = pe.va_to_off(va)
    if off is None:
        return None
    blob = pe.data[max(0, off - back):off + 8]
    base = va - min(off, back)
    best = None
    i = 0
    while i < len(blob) - 7:
        b = blob[i]
        if 0x48 <= b <= 0x4F and blob[i + 1] == 0x8D and (blob[i + 2] & 0xC7) == 0x05:
            disp = struct.unpack_from("<i", blob, i + 3)[0]
            tgt = base + i + 7 + disp
            s = pe.cstring_at_va(tgt, 160)
            if s and 2 < len(s) < 160 and s.isprintable() and "\\" not in s:
                best = s
            i += 7
            continue
        i += 1
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--grep", default="")
    ap.add_argument("--file", default=None, help="substring of a source path")
    ap.add_argument("--conditions", action="store_true")
    args = ap.parse_args()

    pe = PE()
    paths = source_paths(pe)

    if args.list or not args.file:
        rows = [(t, va) for t, va in paths.items()
                if not args.grep or args.grep.lower() in t.lower()]
        print(f"{len(paths)} source paths in the exe; {len(rows)} shown")
        for t, va in sorted(rows):
            print(f"  {va:#x}  {t}")
        return 0

    targets = {va: t for t, va in paths.items() if args.file.lower() in t.lower()}
    if not targets:
        print(f"no source path matching {args.file!r}")
        return 1
    for va, t in targets.items():
        print(f"{t}\n  string VA {va:#x}")

    hits = pe.lea_xrefs(set(targets))
    fns = FnIndex(pe)
    by_fn: dict[int, list[tuple[int, int | None, str | None]]] = defaultdict(list)
    total = 0
    for tgt, sites in hits.items():
        for site in sites:
            total += 1
            c = fns.primary(site) or fns.chunk_at(site)
            start = c.beg if c else site
            by_fn[start].append((site, line_before(pe, site),
                                 condition_near(pe, site) if args.conditions else None))
    print(f"\n{total} assertion site(s) in {len(by_fn)} function(s)\n")
    rows = []
    for start, sites in by_fn.items():
        lines = sorted({ln for _s, ln, _c in sites if ln})
        rows.append((min(lines) if lines else 1 << 30, start, lines, sites))
    for first, start, lines, sites in sorted(rows):
        span = f"L{min(lines)}-L{max(lines)}" if lines else "L?"
        print(f"  fn {start:#x}  {span:<16} {len(sites)} check(s)")
        if args.conditions:
            seen = set()
            for _s, ln, cond in sorted(sites, key=lambda r: (r[1] or 0)):
                if cond and (ln, cond) not in seen:
                    seen.add((ln, cond))
                    print(f"        L{ln}: {cond}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
