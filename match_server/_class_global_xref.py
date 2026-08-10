#!/usr/bin/env python3
"""Find the code that constructs a given UClass, by way of its static global.

Motivation
----------
The live client has an `AWW3TeamManager` whose `Teams` array is empty and zero
live `UWW3TeamObject` / `UWW3SquadObject` / `UWW3SlotObject` (see
`_team_graph_live.py`), so `AWW3PlayerState::CurrentSquad` can never become
valid. The question is what native code was supposed to build that graph.

A shipping UE4 build compiles `NewObject<UWW3TeamObject>()` into a load of the
class's cached `PrivateStaticClass` global followed by a call into
`StaticConstructObject_Internal`. The global's *value* is only knowable at
runtime -- but the live process has it, and `GObjects` names it exactly
(`_uobject_live.py`). So:

    1. resolve the live `UClass*` for the named classes,
    2. scan the loaded module image for those pointer values -> the globals,
    3. translate each global's RVA into the on-disk exe VA,
    4. report every rip-relative `mov`/`lea` that reads it, grouped by the
       enclosing function (`.pdata` chunks stitched by `_exe_fn.py`).

Read-only on the live process; the exe is only read from disk.

Usage:
    python match_server/_class_global_xref.py WW3.WW3TeamObject
    python match_server/_class_global_xref.py WW3.WW3TeamObject WW3.WW3SquadObject \
        WW3.WW3SlotObject --disasm
"""
from __future__ import annotations

import argparse
import struct
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _exe_fn import FnIndex  # noqa: E402
from _exe_pe import PE  # noqa: E402
from _ps_sync_live import Mem, find_pid, main_module  # noqa: E402
from _uobject_live import DUMP_ROOT, Objects, load_dump, resolve  # noqa: E402


def module_hits(mem: Mem, mod_base: int, mod_size: int, values: dict[int, str]):
    """Every 8-aligned address inside the loaded image holding one of `values`."""
    pats = {struct.pack("<Q", v): v for v in values}
    out: list[tuple[int, int]] = []
    step = 0x100000
    for off in range(0, mod_size, step):
        n = min(step + 8, mod_size - off)
        blob = mem.read(mod_base + off, n)
        if blob is None:
            continue
        for pat, val in pats.items():
            start = 0
            while True:
                i = blob.find(pat, start)
                if i < 0:
                    break
                start = i + 1
                a = mod_base + off + i
                if a % 8 == 0:
                    out.append((a, val))
    return sorted(set(out))


def rip_refs(pe: PE, targets: set[int]) -> dict[int, list[tuple[int, str]]]:
    """rip-relative `mov r64,[rip+d]` / `lea r64,[rip+d]` / `cmp`, by target VA."""
    hits: dict[int, list[tuple[int, str]]] = {t: [] for t in targets}
    forms = {0x8B: "mov", 0x8D: "lea", 0x3B: "cmp", 0x89: "mov-store"}
    for s in pe.sections:
        if not s.executable:
            continue
        blob = pe.data[s.raw:s.raw + s.rsize]
        base = s.va
        n = len(blob)
        i = 0
        while i < n - 7:
            b = blob[i]
            if 0x48 <= b <= 0x4F:
                op = blob[i + 1]
                if op in forms and (blob[i + 2] & 0xC7) == 0x05:
                    disp = struct.unpack_from("<i", blob, i + 3)[0]
                    tgt = base + i + 7 + disp
                    if tgt in hits:
                        hits[tgt].append((base + i, forms[op]))
                    i += 7
                    continue
            i += 1
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("classes", nargs="+", help="e.g. WW3.WW3TeamObject")
    ap.add_argument("--dump", default=str(DUMP_ROOT / "GObjects-Dump.txt"))
    ap.add_argument("--disasm", action="store_true",
                    help="disassemble each referencing function")
    ap.add_argument("--max-fn", type=int, default=6)
    args = ap.parse_args()

    pid = find_pid()
    mem = Mem(pid)
    mod_base, mod_size = main_module(pid)
    objs = Objects(mem, mod_base)
    _by_index, by_name = load_dump(Path(args.dump))

    values: dict[int, str] = {}
    for nm in args.classes:
        idx = resolve(objs, by_name, nm)
        ptr = objs.ptr(idx)
        values[ptr] = nm
        print(f"{nm:<28} dump idx={idx:#07x}  live UClass={ptr:#x}")

    print("\nscanning the loaded image for those pointer values ...")
    hits = module_hits(mem, mod_base, mod_size, values)
    pe = PE()
    print(f"{len(hits)} global(s) in the image (exe image_base={pe.image_base:#x})")

    targets: dict[int, tuple[str, int]] = {}
    for addr, val in hits:
        rva = addr - mod_base
        exe_va = pe.image_base + rva
        sec = pe.section_of_va(exe_va)
        print(f"  live={addr:#x}  rva={rva:#x}  exe_va={exe_va:#x}  "
              f"section={sec.name if sec else '?'}  class={values[val]}")
        targets[exe_va] = (values[val], rva)

    print("\ncode references:")
    refs = rip_refs(pe, set(targets))
    fns = FnIndex(pe)
    grouped: dict[int, list[tuple[int, str, str]]] = defaultdict(list)
    for tgt, sites in refs.items():
        cname = targets[tgt][0]
        for va, kind in sites:
            c = fns.chunk_at(va)
            start = c.beg if c else va
            grouped[start].append((va, kind, cname))
    if not grouped:
        print("  (none -- the global is written by the registration code only, "
              "or accessed through a computed address)")
    for start in sorted(grouped):
        rows = grouped[start]
        print(f"\n  function {start:#x}  ({len(rows)} ref(s))")
        for va, kind, cname in rows:
            print(f"    {va:#x}  {kind:<9} -> {cname}")
    print(f"\n{len(grouped)} distinct function(s) touch these globals")

    if args.disasm:
        try:
            import capstone
        except ImportError:
            print("capstone not available")
            return 0
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        md.detail = False
        for start in sorted(grouped)[: args.max_fn]:
            c = fns.chunk_at(start)
            if not c:
                continue
            off = pe.va_to_off(c.beg)
            code = pe.data[off:off + min(c.end - c.beg, 0x600)]
            print(f"\n===== function {c.beg:#x}..{c.end:#x}")
            for ins in md.disasm(code, c.beg):
                print(f"  {ins.address:#x}  {ins.mnemonic:<7} {ins.op_str}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
