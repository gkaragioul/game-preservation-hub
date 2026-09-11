#!/usr/bin/env python3
"""Locate the client-side synchronization reporters and disassemble them.

Checkpoint 7 established that the checklist's `PlayerState` item is *not* a
pointer test - the pointer is valid while the item reads false.  So the item is
a predicate on the PlayerState object itself, and the exe carries three unused
reporter strings next to the checklist printer:

    OnSynchronized: Value: %d
    OnSynchronized: IsAutonomousSynchronized
    OnSynchronized: IsSynchronized

This tool finds those strings, finds the code that loads them, snaps each hit to
its enclosing function via `.pdata`, and disassembles it so the predicate's
fields can be read off directly.

Usage:
    python match_server/_ps_sync_predicate.py            # locate + summarise
    python match_server/_ps_sync_predicate.py --disasm   # full disassembly
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _exe_pe import PE  # noqa: E402

NEEDLES = [
    "Client Synchronization [%s][%s]",
    "OnSynchronized: Value: %d",
    "OnSynchronized: IsAutonomousSynchronized",
    "OnSynchronized: IsSynchronized",
    "OnSynchronized: Player State",
    "OnSynchronized: Controller",
    "OnSynchronized: Inventory Manager",
    "OnSynchronized: Weapons Attachments",
    "OnSynchronized: Character Attachments",
    "OnSynchronized: Local Client Configs",
    "OnSynchronized: Game State",
    "OnSynchronized: Map Levels",
]


def encodings(s: str) -> list[tuple[str, bytes]]:
    return [("utf8", s.encode("utf-8") + b"\0"),
            ("utf16", s.encode("utf-16-le") + b"\0\0")]


def runtime_functions(pe: PE) -> list[tuple[int, int, int]]:
    """Parse .pdata into (start_va, end_va, unwind_va) sorted by start."""
    sec = next(s for s in pe.sections if s.name == ".pdata")
    blob = pe.data[sec.raw:sec.raw + sec.rsize]
    out = []
    for i in range(0, len(blob) - 11, 12):
        beg, end, unw = struct.unpack_from("<III", blob, i)
        if beg == 0 and end == 0:
            continue
        out.append((pe.image_base + beg, pe.image_base + end, pe.image_base + unw))
    out.sort()
    return out


def enclosing(funcs: list[tuple[int, int, int]], va: int) -> tuple[int, int] | None:
    lo, hi = 0, len(funcs) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        beg, end, _ = funcs[mid]
        if va < beg:
            hi = mid - 1
        elif va >= end:
            lo = mid + 1
        else:
            return beg, end
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--disasm", action="store_true")
    ap.add_argument("--only", default="", help="substring filter on the string")
    args = ap.parse_args()

    pe = PE()
    funcs = runtime_functions(pe)
    print(f"pdata: {len(funcs)} runtime functions")

    located: dict[int, str] = {}
    for s in NEEDLES:
        if args.only and args.only.lower() not in s.lower():
            continue
        for enc, needle in encodings(s):
            start = 0
            while True:
                k = pe.data.find(needle, start)
                if k < 0:
                    break
                va = pe.off_to_va(k)
                if va is not None:
                    located[va] = f"{s!r} [{enc}]"
                start = k + 1

    if not located:
        print("no strings located")
        return 1

    print(f"\n=== {len(located)} string instances ===")
    for va, label in sorted(located.items()):
        print(f"  va={va:#014x} off={pe.va_to_off(va):#x}  {label}")

    xrefs = pe.lea_xrefs(set(located))
    print("\n=== lea xrefs ===")
    interesting: dict[tuple[int, int], list[str]] = {}
    for va, label in sorted(located.items()):
        hits = xrefs.get(va, [])
        print(f"  {label}")
        if not hits:
            print("      (no rip-relative lea)")
        for h in hits:
            fn = enclosing(funcs, h)
            fnstr = f"fn {fn[0]:#x}..{fn[1]:#x}" if fn else "fn ?"
            print(f"      lea at {h:#014x}   {fnstr}")
            if fn:
                interesting.setdefault(fn, []).append(f"{label} @ {h:#x}")

    print(f"\n=== {len(interesting)} distinct functions ===")
    for (beg, end), labels in sorted(interesting.items()):
        print(f"  fn {beg:#x}..{end:#x}  ({end - beg} bytes)")
        for l in labels:
            print(f"      {l}")

    if args.disasm:
        from capstone import CS_ARCH_X86, CS_MODE_64, Cs
        md = Cs(CS_ARCH_X86, CS_MODE_64)
        md.detail = False
        for (beg, end), labels in sorted(interesting.items()):
            print(f"\n{'=' * 78}\nfn {beg:#x}..{end:#x}")
            for l in labels:
                print(f"  ; {l}")
            print("=" * 78)
            off = pe.va_to_off(beg)
            code = pe.data[off:off + (end - beg)]
            for ins in md.disasm(code, beg):
                note = ""
                if ins.mnemonic == "lea" and "rip" in ins.op_str:
                    try:
                        tgt = int(ins.op_str.split("rip + ")[1].split("]")[0], 16) + ins.address + ins.size
                        if tgt in located:
                            note = f"   ; {located[tgt]}"
                        else:
                            t = pe.cstring_at_va(tgt, 200) or pe.wstring_at_va(tgt, 400)
                            if t and len(t) > 2 and t.isprintable():
                                note = f"   ; {t!r}"
                    except Exception:
                        pass
                print(f"  {ins.address:#014x}  {ins.mnemonic:<8} {ins.op_str}{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
