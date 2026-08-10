#!/usr/bin/env python3
"""Enumerate the live WW3 client's UObjects by class, read-only.

Why
---
Half the questions in this effort ("does the client actually have an
`AWW3TeamManager`?", "did the `AWW3ActionReplicator` we opened on ch80 really
spawn?", "which of the six heap hits is the *real* local `AWW3PlayerState`?")
are answerable directly from `GObjects` instead of by guessing from wire logs or
by pattern-matching stale heap.

How the pieces fit
------------------
`Dumper-7` recorded, for this exact build:

    Offsets::GObjects = 0x05F2C148        (RVA from the image base)
    TUObjectArray { FUObjectItem** Objects; pad8; int32 MaxElements@0x10,
                    NumElements@0x14, MaxChunks@0x18, NumChunks@0x1C }
    ElementsPerChunk = 0x10000,  sizeof(FUObjectItem) = 0x18
    UObject { void* VTable@0x00; EObjectFlags Flags@0x08; int32 Index@0x0C;
              UClass* Class@0x10; FName Name@0x18; UObject* Outer@0x20 }
    UField  { UField* Next@0x28 }
    UStruct { UStruct* SuperStruct@0x30; UField* Children@0x38; int32 Size@0x40 }

`GObjects-Dump.txt` gives `index -> "Type Package.Path.Name"` for all 230 140
objects that existed at dump time. Native `UClass` objects are registered during
startup in a deterministic order, so their *indices* are stable across runs even
though their addresses are not. That turns the dump into an index -> name table
for exactly the objects we need to name (classes), and the live array turns it
back into pointers.

Nothing is trusted blindly. `--verify` checks, against the live process:
  * `GObjects[i]->Index == i` for a wide sample (proves the array walk),
  * every named class object's `Class` is the live `CoreUObject.Class` UClass
    (proves the index -> name mapping still lines up),
  * `WW3TeamManager`'s `SuperStruct` chain really is Actor -> Object.

Read-only: PROCESS_QUERY_INFORMATION | PROCESS_VM_READ. No writes, no injection.

Usage:
    python match_server/_uobject_live.py --verify
    python match_server/_uobject_live.py --instances WW3.WW3TeamManager
    python match_server/_uobject_live.py --instances WW3.WW3PlayerState --subclasses
    python match_server/_uobject_live.py --netfields WW3.WW3ActionReplicator
"""
from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _ps_sync_live import Mem, find_pid, main_module  # noqa: E402

DUMP_ROOT = Path(r"C:\Dumper-7\4.21.2-0+++UE4+Release-4.21-WW3")
GOBJECTS_RVA = 0x05F2C148
ELEMENTS_PER_CHUNK = 0x10000
FUOBJECTITEM_SIZE = 0x18

OBJ_FLAGS = 0x08
OBJ_INDEX = 0x0C
OBJ_CLASS = 0x10
OBJ_NAME = 0x18
OBJ_OUTER = 0x20
FIELD_NEXT = 0x28
STRUCT_SUPER = 0x30
STRUCT_CHILDREN = 0x38
STRUCT_SIZE = 0x40
FUNC_FLAGS = 0x88
PROP_FLAGS = 0x38
PROP_OFFSET = 0x44

CPF_NET = 0x0000000000000020
FUNC_NET = 0x00000040

DUMP_LINE = re.compile(r"^\[([0-9A-Fa-f]{8})\]\s+\{0x[0-9A-Fa-f]+\}\s+(\S+)\s+(\S+)")


def load_dump(path: Path) -> tuple[dict[int, tuple[str, str]], dict[str, int]]:
    """index -> (type, fullname), and fullname -> index."""
    by_index: dict[int, tuple[str, str]] = {}
    by_name: dict[str, int] = {}
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = DUMP_LINE.match(line)
            if not m:
                continue
            idx = int(m.group(1), 16)
            typ, name = m.group(2), m.group(3)
            by_index[idx] = (typ, name)
            by_name.setdefault(f"{typ} {name}", idx)
            by_name.setdefault(name, idx)
    return by_index, by_name


class Objects:
    def __init__(self, mem: Mem, mod_base: int):
        self.mem = mem
        hdr = mem.read(mod_base + GOBJECTS_RVA, 0x20)
        if hdr is None:
            raise SystemExit("cannot read GObjects")
        (self.chunks_ptr,) = struct.unpack_from("<Q", hdr, 0)
        self.max_elements, self.num_elements, self.max_chunks, self.num_chunks = \
            struct.unpack_from("<iiii", hdr, 0x10)
        if not (0 < self.num_elements <= self.max_elements <= 8_000_000):
            raise SystemExit(f"GObjects looks wrong: {self.num_elements}/{self.max_elements}")
        raw = mem.read(self.chunks_ptr, 8 * max(self.num_chunks, 1))
        self.chunks = list(struct.unpack(f"<{max(self.num_chunks,1)}Q", raw)) if raw else []
        self._items: dict[int, bytes] = {}

    def chunk_blob(self, ci: int) -> bytes | None:
        if ci in self._items:
            return self._items[ci]
        if ci >= len(self.chunks) or not self.chunks[ci]:
            return None
        n = ELEMENTS_PER_CHUNK
        if ci == self.num_chunks - 1:
            n = self.num_elements - ci * ELEMENTS_PER_CHUNK
        blob = self.mem.read(self.chunks[ci], FUOBJECTITEM_SIZE * n)
        self._items[ci] = blob
        return blob

    def ptr(self, index: int) -> int:
        if index < 0 or index >= self.num_elements:
            return 0
        ci, ii = divmod(index, ELEMENTS_PER_CHUNK)
        blob = self.chunk_blob(ci)
        if not blob or (ii + 1) * FUOBJECTITEM_SIZE > len(blob):
            return 0
        return struct.unpack_from("<Q", blob, ii * FUOBJECTITEM_SIZE)[0]

    def all_ptrs(self):
        for ci in range(self.num_chunks):
            blob = self.chunk_blob(ci)
            if not blob:
                continue
            n = len(blob) // FUOBJECTITEM_SIZE
            for ii in range(n):
                p = struct.unpack_from("<Q", blob, ii * FUOBJECTITEM_SIZE)[0]
                if p:
                    yield ci * ELEMENTS_PER_CHUNK + ii, p


def header(mem: Mem, obj: int) -> dict | None:
    b = mem.read(obj, 0x28)
    if b is None:
        return None
    return {
        "vtable": struct.unpack_from("<Q", b, 0)[0],
        "flags": struct.unpack_from("<I", b, OBJ_FLAGS)[0],
        "index": struct.unpack_from("<i", b, OBJ_INDEX)[0],
        "class": struct.unpack_from("<Q", b, OBJ_CLASS)[0],
        "name_cmp": struct.unpack_from("<i", b, OBJ_NAME)[0],
        "name_num": struct.unpack_from("<i", b, OBJ_NAME + 4)[0],
        "outer": struct.unpack_from("<Q", b, OBJ_OUTER)[0],
    }


def super_chain(mem: Mem, cls: int, limit: int = 24) -> list[int]:
    out = []
    cur = cls
    while cur and len(out) < limit:
        out.append(cur)
        nxt = mem.u64(cur + STRUCT_SUPER)
        if not nxt or nxt == cur:
            break
        cur = nxt
    return out


def resolve(objs: Objects, by_name: dict[str, int], name: str) -> int:
    idx = by_name.get(name)
    if idx is None:
        for key, i in by_name.items():
            if key.endswith("." + name) or key == name:
                idx = i
                break
    if idx is None:
        raise SystemExit(f"'{name}' not in GObjects-Dump.txt")
    return idx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--instances", default=None, help="e.g. WW3.WW3TeamManager")
    ap.add_argument("--subclasses", action="store_true",
                    help="also match objects whose super chain contains the class")
    ap.add_argument("--netfields", default=None,
                    help="list the class's own CPF_Net properties / FUNC_Net functions")
    ap.add_argument("--dump", default=str(DUMP_ROOT / "GObjects-Dump.txt"))
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--whatis", default=None,
                    help="address of an object: is it in GObjects, and what class?")
    ap.add_argument("--no-cdo", action="store_true",
                    help="skip RF_ClassDefaultObject/RF_ArchetypeObject hits")
    args = ap.parse_args()

    pid = find_pid()
    mem = Mem(pid)
    mod_base, mod_size = main_module(pid)
    objs = Objects(mem, mod_base)
    by_index, by_name = load_dump(Path(args.dump))
    print(f"pid={pid} image={mod_base:#x}  GObjects={mod_base+GOBJECTS_RVA:#x} -> "
          f"{objs.num_elements} objects in {objs.num_chunks} chunk(s); "
          f"dump has {len(by_index)}")

    if args.verify:
        ok = bad = 0
        for i in range(0, objs.num_elements, max(1, objs.num_elements // 4000)):
            p = objs.ptr(i)
            if not p:
                continue
            h = header(mem, p)
            if h is None:
                continue
            if h["index"] == i:
                ok += 1
            else:
                bad += 1
        print(f"[verify] UObject::Index == array index: {ok} ok / {bad} mismatched")
        cls_idx = resolve(objs, by_name, "Class CoreUObject.Class")
        uclass = objs.ptr(cls_idx)
        print(f"[verify] CoreUObject.Class UClass = {uclass:#x} (dump index {cls_idx:#x})")
        for nm in ("Class WW3.WW3TeamManager", "Class WW3.WW3ActionReplicator",
                   "Class WW3.WW3SquadObject", "Class WW3.WW3PlayerState",
                   "Class Engine.Actor"):
            idx = by_name.get(nm)
            if idx is None:
                print(f"[verify] {nm}: not in dump")
                continue
            p = objs.ptr(idx)
            h = header(mem, p) if p else None
            match = "OK" if h and h["class"] == uclass else "MISMATCH"
            print(f"[verify] {nm:<38} idx={idx:#07x} ptr={p:#x} class={match}")
        tm = objs.ptr(by_name["Class WW3.WW3TeamManager"])
        chain = super_chain(mem, tm)
        rev = {objs.ptr(i): by_index[i][1] for i in
               (by_name.get(n) for n in ("Class Engine.Actor", "Class CoreUObject.Object"))
               if i is not None}
        print("[verify] WW3TeamManager super chain: " +
              " -> ".join(rev.get(c, hex(c)) for c in chain))
        return 0

    if args.whatis:
        addr = int(args.whatis, 0)
        h = header(mem, addr)
        if h is None:
            print(f"{addr:#x}: unreadable")
            return 1
        live = objs.ptr(h["index"]) == addr
        print(f"\n{addr:#x}: Index={h['index']:#x} flags={h['flags']:#x} "
              f"class={h['class']:#x} outer={h['outer']:#x}")
        print(f"  GObjects[{h['index']:#x}] == this object? {live}"
              "   <- if False the object is dead/unregistered heap")
        chain = super_chain(mem, h["class"])
        names = []
        for c in chain:
            ch = header(mem, c)
            nm = by_index.get(ch["index"], (None, None))[1] if ch else None
            ok = ch and objs.ptr(ch["index"]) == c
            names.append(nm if (nm and ok) else hex(c))
        print("  class chain: " + " -> ".join(names))
        return 0

    if args.netfields:
        idx = resolve(objs, by_name, args.netfields)
        cls = objs.ptr(idx)
        print(f"\nclass {args.netfields} idx={idx:#x} ptr={cls:#x} "
              f"size={mem.u32(cls + STRUCT_SIZE)}")
        # Own children only, exactly like TFieldIterator(..., ExcludeSuper)
        child = mem.u64(cls + STRUCT_CHILDREN)
        seen = 0
        rows = []
        while child and seen < 4096:
            seen += 1
            h = header(mem, child)
            if h is None:
                break
            cname = by_index.get(h["index"], ("?", "?"))[1]
            ctype = by_index.get(h["index"], ("?", "?"))[0]
            fflags = mem.u32(child + FUNC_FLAGS) or 0
            pflags = struct.unpack("<Q", mem.read(child + PROP_FLAGS, 8) or b"\0" * 8)[0]
            rows.append((child, h["index"], ctype, cname, fflags, pflags))
            child = mem.u64(child + FIELD_NEXT)
        print(f"  {len(rows)} own field(s)")
        for addr, i, ctype, cname, fflags, pflags in rows:
            is_net_fn = ctype == "Function" and (fflags & FUNC_NET)
            is_net_prop = ctype.endswith("Property") and (pflags & CPF_NET)
            tag = "NET-FUNC" if is_net_fn else ("NET-PROP" if is_net_prop else "        ")
            print(f"    {tag} idx={i:#07x} {ctype:<16} {cname}")
        return 0

    if args.instances:
        targets = {}
        for nm in args.instances.split(","):
            nm = nm.strip()
            if not nm:
                continue
            idx = resolve(objs, by_name, nm)
            targets[objs.ptr(idx)] = nm
            print(f"\nlooking for instances of {nm} "
                  f"(dump idx={idx:#x}, live UClass={objs.ptr(idx):#x})"
                  f"{' incl. subclasses' if args.subclasses else ''}")
        hits: dict[str, list] = {nm: [] for nm in targets.values()}
        cls_cache: dict[int, str | None] = {}
        scanned = 0
        for i, p in objs.all_ptrs():
            scanned += 1
            b = mem.read(p, 0x28)
            if b is None:
                continue
            cls = struct.unpack_from("<Q", b, OBJ_CLASS)[0]
            if not cls:
                continue
            if cls in targets:
                hits[targets[cls]].append((i, p, cls))
                continue
            if not args.subclasses:
                continue
            if cls not in cls_cache:
                found = None
                for anc in super_chain(mem, cls, limit=14):
                    if anc in targets:
                        found = targets[anc]
                        break
                cls_cache[cls] = found
            if cls_cache[cls]:
                hits[cls_cache[cls]].append((i, p, cls))
        print(f"\nscanned {scanned} live objects")
        for nm, rows in hits.items():
            print(f"\n== {nm}: {len(rows)} instance(s)")
            for i, p, cls in rows[: args.limit]:
                h = header(mem, p)
                outer = h["outer"] if h else 0
                oh = header(mem, outer) if outer else None
                oname = by_index.get(oh["index"], ("", "?"))[1] if oh else ""
                ch = header(mem, cls)
                cname = by_index.get(ch["index"], ("", "?"))[1] if ch else ""
                print(f"  [{i:#08x}] {p:#x} class={cname or hex(cls)} "
                      f"flags={h['flags']:#x} outer={oname or hex(outer)}")
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
