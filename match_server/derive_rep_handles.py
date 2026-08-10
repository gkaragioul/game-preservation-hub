#!/usr/bin/env python3
r"""Derive RepLayout property handles (the numbers on the wire inside an actor's
property block) from the Dumper-7 SDK, the same way UE 4.21 builds them.

UE 4.21, `UClass::SetUpRuntimeReplicationData()`:
    ClassReps(C) = ClassReps(Super) ++ (own CPF_Net properties sorted by memory offset,
                                        ties broken by name)
`FRepLayout::InitFromObjectClass()` then walks ClassReps in order and flattens each
property into one or more *commands*; the wire handle is the 1-based command index.
Flattening rules (`InitFromProperty_r`):
    * a struct with a native NetSerializer  -> 1 command
    * any other struct                      -> recurse into its members, in offset order
    * everything else                       -> 1 command

Handles are written with SerializeIntPacked, and a property block is terminated by a
handle of 0. The block itself opens with a single `bDoChecksum` bit -- see
`repblock.py`; decoding from bit 0 instead of bit 1 doubles the first handle and was
what made every earlier derivation look wrong.

This is the RepLayout counterpart of `derive_net_handles.py` (which does the
ClassNetCache/RPC numbering). It is validated against handles actually seen on the wire
via --check.

Usage:
    python match_server/derive_rep_handles.py --leaf ACharacter
    python match_server/derive_rep_handles.py --leaf APlayerController --check 17=Pawn
    python match_server/derive_rep_handles.py --leaf ACharacter --json out.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_DUMP = Path(r"C:\Dumper-7\4.21.2-0+++UE4+Release-4.21-WW3")

ALIGNAS = r"(?:alignas\(0x[0-9A-Fa-f]+\)\s+)?"
FINAL = r"(?:\s+final)?"
CLASS_DECL = re.compile(rf"^class\s+{ALIGNAS}(\w+){FINAL}\s*:\s*public\s+(\w+)")
STRUCT_DECL = re.compile(rf"^struct\s+{ALIGNAS}(\w+){FINAL}(?:\s*:\s*public\s+(\w+))?")
# `    class AActor*  Owner;  // 0x0108(0x0008)(Net, ZeroConstructor, ...)`
# `    uint8  bTearOff : 1;   // 0x0081(0x0001)(BitIndex: 0x07, PropSize: 0x0001 (Net, ...))`
PROP_LINE = re.compile(
    r"^\s+(.*?)\s+(\w+)\s*(?::\s*\d+\s*)?;\s*//\s*0x([0-9A-Fa-f]+)\(0x([0-9A-Fa-f]+)\)\((.*)\)\s*$"
)

# Structs whose TStructOpsTypeTraits declare WithNetSerializer in UE 4.21 -- RepLayout
# emits a single command for these instead of recursing. (Core math types + the engine
# net helper structs; anything else gets flattened member by member.)
NET_SERIALIZE_STRUCTS = {
    "FVector", "FVector2D", "FVector4", "FRotator", "FQuat", "FIntPoint", "FIntVector",
    "FVector_NetQuantize", "FVector_NetQuantize10", "FVector_NetQuantize100",
    "FVector_NetQuantizeNormal",
    "FRepMovement", "FUniqueNetIdRepl", "FGameplayTag", "FGameplayTagContainer",
    # FRootMotionSourceGroup declares WithNetSerializer (RootMotionSource.h) -- confirmed
    # on the wire: making it atomic is what lets ACharacter-derived blocks close.
    "FRootMotionSourceGroup",
    "FRepAttachment_DUMMY_NEVER",  # placeholder: FRepAttachment does NOT net-serialize
}
# Structs that use NetDeltaSerialize (fast arrays) -- also a single command.
NET_DELTA_STRUCTS_SUFFIX = ("FastArraySerializer",)


def _flags(blob: str) -> set[str]:
    return {t.strip() for t in re.split(r"[,()]", blob) if t.strip()}


def _base_type(decl: str) -> str:
    """`struct FRepMovement` / `class AActor*` / `TArray<struct FFoo>` -> core type name."""
    d = decl.strip()
    d = re.sub(r"^(?:const\s+)?", "", d)
    m = re.match(r"^TArray<\s*(?:struct|class)?\s*([\w:]+)", d)
    if m:
        return "TArray<" + m.group(1) + ">"
    d = re.sub(r"^(?:struct|class|enum)\s+", "", d)
    d = d.replace("*", "").strip()
    return d


def parse_sdk(sdk_dir: Path):
    """-> (classes, structs). Each maps name -> {super, props:[(offset, name, type, flags)]}."""
    classes: dict[str, dict] = {}
    structs: dict[str, dict] = {}
    for path in sorted(list(sdk_dir.glob("*_classes.hpp")) + list(sdk_dir.glob("*_structs.hpp"))):
        cur = None
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = CLASS_DECL.match(line)
            if m:
                cur = classes.setdefault(m.group(1),
                                         {"super": m.group(2), "props": [], "kind": "class"})
                continue
            m = STRUCT_DECL.match(line)
            if m:
                cur = structs.setdefault(m.group(1),
                                         {"super": m.group(2), "props": [], "kind": "struct"})
                continue
            if cur is None:
                continue
            if line.startswith("};"):
                cur = None
                continue
            m = PROP_LINE.match(line)
            if not m:
                continue
            decl, name, off_hex, _size, flags = m.groups()
            if name.startswith("Pad_") or name.startswith("BitPad_"):
                continue
            cur["props"].append((int(off_hex, 16), name, _base_type(decl), _flags(flags)))
    return classes, structs


ENUM_DECL = re.compile(r"^enum\s+class\s+(\w+)\s*:\s*(\w+)")
ENUM_ENTRY = re.compile(r"^\s+(\w+)\s*=\s*(-?\d+)\s*,?\s*$")


def parse_enums(sdk_dir: Path) -> dict[str, int]:
    """-> enum name -> UEnum::GetMaxEnumValue().

    Needed because UE nets an enum in `FMath::CeilLogTwo(GetMaxEnumValue())` bits
    (`UByteProperty::NetSerializeItem` / `UEnumProperty::NetSerializeItem`), not 8.
    Dumper-7 emits the auto-generated `_MAX` entry, which is the max value.
    """
    out: dict[str, int] = {}
    for path in sorted(sdk_dir.glob("*_structs.hpp")):
        cur = None
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = ENUM_DECL.match(line)
            if m:
                cur = m.group(1)
                out.setdefault(cur, 0)
                continue
            if cur is None:
                continue
            if line.startswith("};"):
                cur = None
                continue
            m = ENUM_ENTRY.match(line)
            if m:
                out[cur] = max(out[cur], int(m.group(2)))
    return out


def ceil_log_two(v: int) -> int:
    """FMath::CeilLogTwo — 0 for v<=1, else the bit count needed for [0, v)."""
    if v <= 1:
        return 0
    return (v - 1).bit_length()


def chain_of(leaf: str, classes: dict[str, dict]) -> list[str]:
    out, cur, seen = [], leaf, set()
    while cur and cur in classes and cur not in seen:
        seen.add(cur)
        out.append(cur)
        cur = classes[cur]["super"]
    return list(reversed(out))


def is_net_serialize(type_name: str, structs: dict[str, dict]) -> bool:
    if type_name in NET_SERIALIZE_STRUCTS:
        return True
    return any(type_name.endswith(s) for s in NET_DELTA_STRUCTS_SUFFIX)


def flatten(prop_name: str, type_name: str, structs: dict[str, dict],
            depth: int = 0) -> list[str]:
    """-> list of leaf command names contributed by one property."""
    if type_name.startswith("TArray<"):
        # A dynamic array is one command for the array itself; its elements get handles
        # underneath it at runtime, so a static derivation stops here.
        return [prop_name + "[]"]
    if type_name in structs and not is_net_serialize(type_name, structs) and depth < 6:
        out: list[str] = []
        for _off, n, t, _f in sorted(structs[type_name]["props"], key=lambda p: (p[0], p[1])):
            out += [prop_name + "." + s for s in flatten(n, t, structs, depth + 1)]
        return out or [prop_name]
    return [prop_name]


def flatten_typed(prop_name: str, type_name: str, structs: dict[str, dict],
                  depth: int = 0) -> list[tuple[str, str]]:
    """Like `flatten`, but pairs each leaf command with its declared type.

    Needed to net-decode a block: a flattened struct member such as
    `AttachmentReplication.RotationOffset` has no entry in the owning class's
    property list, so its width can only come from the struct's member type.
    """
    if type_name.startswith("TArray<"):
        return [(prop_name + "[]", type_name)]
    if type_name in structs and not is_net_serialize(type_name, structs) and depth < 6:
        out: list[tuple[str, str]] = []
        for _off, n, t, _f in sorted(structs[type_name]["props"], key=lambda p: (p[0], p[1])):
            out += [(prop_name + "." + s, ty)
                    for s, ty in flatten_typed(n, t, structs, depth + 1)]
        return out or [(prop_name, type_name)]
    return [(prop_name, type_name)]


def build_typed(leaf: str, classes: dict[str, dict], structs: dict[str, dict]):
    """-> list[(handle, owner_class, cmd_name, declared_type)]."""
    out: list[tuple[int, str, str, str]] = []
    h = 0
    for cls in chain_of(leaf, classes):
        nets = [(off, n, t) for off, n, t, f in classes[cls]["props"] if "Net" in f]
        for _off, name, tname in sorted(nets, key=lambda p: (p[0], p[1])):
            for cmd, ty in flatten_typed(name, tname, structs):
                h += 1
                out.append((h, cls, cmd, ty))
    return out


def build(leaf: str, classes: dict[str, dict], structs: dict[str, dict]):
    """-> (handles: list[(handle, owner_class, cmd_name)], per-class base map)."""
    handles: list[tuple[int, str, str]] = []
    bases: dict[str, int] = {}
    h = 0
    for cls in chain_of(leaf, classes):
        bases[cls] = h + 1
        nets = [(off, n, t) for off, n, t, f in classes[cls]["props"] if "Net" in f]
        for _off, name, tname in sorted(nets, key=lambda p: (p[0], p[1])):
            for cmd in flatten(name, tname, structs):
                h += 1
                handles.append((h, cls, cmd))
    return handles, bases


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=os.environ.get("WW3_DUMPER7_DIR", str(DEFAULT_DUMP)))
    ap.add_argument("--leaf", required=True, help="comma-separated Dumper-7 class names")
    ap.add_argument("--check", action="append", default=[],
                    help="handle=Name assertion, e.g. 17=Pawn")
    ap.add_argument("--json")
    args = ap.parse_args()

    sdk = Path(args.dump)
    if sdk.name != "SDK":
        sdk = sdk / "CppSDK" / "SDK"
    if not sdk.is_dir():
        print(f"SDK dir not found: {sdk}", file=sys.stderr)
        return 2

    classes, structs = parse_sdk(sdk)
    print(f"dump    : {sdk}")
    print(f"classes : {len(classes)}   structs: {len(structs)}\n")

    doc = {}
    for leaf in args.leaf.split(","):
        leaf = leaf.strip()
        if leaf not in classes:
            print(f"!! {leaf} not in dump")
            continue
        handles, bases = build(leaf, classes, structs)
        print(f"=== {leaf}  ({len(handles)} handles) ===")
        print("  chain: " + " -> ".join(f"{c}@{bases[c]}" for c in chain_of(leaf, classes)
                                        if any(x[1] == c for x in handles)))
        for h, cls, name in handles:
            print(f"  {h:>4}  {cls:<28} {name}")
        doc[leaf] = {str(h): {"class": c, "cmd": n} for h, c, n in handles}
        for chk in args.check:
            want_h, want_n = chk.split("=", 1)
            got = [n for h, _c, n in handles if h == int(want_h)]
            ok = got and want_n.lower() in got[0].lower()
            print(f"  [{'OK ' if ok else 'MISS'}] handle {want_h} -> {got[0] if got else '?'} "
                  f"(expected {want_n})")
        print()

    if args.json:
        Path(args.json).write_text(json.dumps(doc, indent=2), encoding="utf-8")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
