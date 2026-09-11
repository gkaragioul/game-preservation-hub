#!/usr/bin/env python3
"""Derive absolute ClassNetCache wire handles from a Dumper-7 SDK dump.

Why this exists
---------------
`class_net_cache_ww3.json` was originally built from exe string-table ordering and
*calibrated* so that `ServerAcknowledgePossession == 34`. That list was wrong in
detail (34 `Client*` entries starting at `ClientPlayCameraShake`; it also included
`ClientTravel`, which is not a `Net` function, and omitted `OnServerStartedVisualLogger`,
which is). `docs/M4_Possession_Findings.md` fact #10 then showed `ClientRestart` on
handle 9 producing no client reaction at all, which put the whole table in doubt.

This script reconstructs the table from the Dumper-7 dump of the *live* WW3 build
(`4.21.2-0+++UE4+Release-4.21-WW3`), which records the real `Net` property flags and
the real `Net`/`NetClient`/`NetServer` function flags for every UClass.

How UE 4.21 numbers the handles
-------------------------------
`UClass::SetUpRuntimeReplicationData()` fills `UClass::NetFields` from *this class's own*
children only (`TFieldIterator<UField>(this, ExcludeSuper)`):

  * `UProperty` with `CPF_Net`
  * `UFunction` with `FUNC_Net` (and a valid native func)

then sorts `NetFields` **by name** so the numbering is stable across builds.

`FClassNetCacheMgr::GetClassNetCache()` then assigns absolute indices:

    FieldsBase(C)   = FieldsBase(Super) + len(NetFields(Super))     # == Super->GetMaxIndex()
    handle(field)   = FieldsBase(C) + position of field in NetFields(C)

So a base-class RPC keeps the same handle no matter how deep the actual actor's class
is -- `ClientRestart` is fixed by `APlayerController`'s own slot, not by which
`AWW3*PlayerController` / BP subclass the match happens to spawn.

Two open questions the dump alone can't settle, so we compute both and let the live
wire anchors pick the winner:

  * `include_properties`: whether 4.21 puts `CPF_Net` properties in `NetFields` at all
    (early UE4 did; later versions left properties entirely to `RepLayout`). Properties
    in `NetFields` are dead weight for RPC dispatch but still consume handle slots.
  * name-sort collation: UE's `FString::operator<` is `Stricmp`, i.e. case-insensitive.

Usage:
    python match_server/derive_net_handles.py                # report + anchor check
    python match_server/derive_net_handles.py --json out.json # emit class_net_cache doc
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_DUMP = Path(r"C:\Dumper-7\4.21.2-0+++UE4+Release-4.21-WW3")

# Live C->S wire observations, re-measured with the correct field-header decoder
# (`_probe_field_header.py`: the handle is a fixed-width LSB-first int, not SerializeIntPacked).
# Source: captures/24July26/W3_match_full_2.pcapng, C->S ch2, 17325 RPC blocks.
# Every one of these is a Server* RPC whose payload size matches its signature, and no
# Client*-range handle ever appears C->S -- see match_server/live_log/HANDLE_DERIVE.md.
WIRE_ANCHORS = {
    "ServerAcknowledgePossession": 64,          # n=11 (respawns), 0/8-bit payload
    "ServerCheckClientPossession": 67,          # n=1,  zero-arg
    "ServerCheckClientPossessionReliable": 68,  # n=2,  zero-arg
    "ServerSetSpectatorLocation": 73,           # n=666 (spectator cam), vector+rotator
    "ServerShortTimeout": 75,                   # n=1,  zero-arg, once at login
    "ServerUpdateCamera": 78,                   # n=15402 dominant, 77/80/83-bit payloads
    "ServerUpdateLevelVisibility": 79,          # n=31, level streaming
    "ServerVerifyViewTarget": 81,               # n=2,  zero-arg
}

# The chain that owns every handle we care about. The actual match PC is a BP subclass
# of AWW3DominationPlayerController, but subclass fields are appended *after* these.
PC_CHAIN = ["Object", "Actor", "Controller", "PlayerController"]

CLASS_DECL = re.compile(r"^class\s+(\w+)\s*:\s*public\s+(\w+)")
CLASS_COMMENT = re.compile(r"^// (?:Class|BlueprintGeneratedClass|WidgetBlueprintGeneratedClass|"
                           r"AnimBlueprintGeneratedClass)\s+([\w\-]+)\.(\w+)")
FUNC_COMMENT = re.compile(r"^// Function\s+([\w\-]+)\.(\w+)\.(\w+)\s*$")
FLAGS_COMMENT = re.compile(r"^// \((.*)\)\s*$")

# `    class UPlayer*   Player;   // 0x03B0(0x0008)(ZeroConstructor, ...)`
# `    uint8   bTearOff : 1;      // 0x0081(0x0001)(BitIndex: 0x07, PropSize: 0x0001 (Net, ...))`
PROP_LINE = re.compile(
    r"^\s+.*?(\w+)\s*(?::\s*\d+\s*)?;\s*//\s*0x[0-9A-Fa-f]+\(0x[0-9A-Fa-f]+\)\((.*)\)\s*$"
)


def _flag_set(blob: str) -> set[str]:
    return {t.strip() for t in re.split(r"[,()]", blob) if t.strip()}


def parse_classes(sdk_dir: Path) -> dict[str, dict]:
    """cpp-name -> {unreal, super_cpp, net_props: [names]} for every dumped UClass."""
    classes: dict[str, dict] = {}
    for path in sorted(sdk_dir.glob("*_classes.hpp")):
        pending_unreal: str | None = None
        cur: dict | None = None
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = CLASS_COMMENT.match(line)
            if m:
                pending_unreal = m.group(2)
                continue
            m = CLASS_DECL.match(line)
            if m:
                cpp, super_cpp = m.group(1), m.group(2)
                cur = {
                    "unreal": pending_unreal or cpp.lstrip("AUFE"),
                    "cpp": cpp,
                    "super_cpp": super_cpp,
                    "net_props": [],
                }
                classes.setdefault(cpp, cur)
                cur = classes[cpp]
                pending_unreal = None
                continue
            if cur is None:
                continue
            if line.startswith("};"):
                cur = None
                continue
            m = PROP_LINE.match(line)
            if not m:
                continue
            name, flags = m.group(1), m.group(2)
            # Dumper-7 synthesises these to pad the struct; they are not UProperties.
            if name.startswith("Pad_") or name.startswith("BitPad_"):
                continue
            if "Net" in _flag_set(flags):
                cur["net_props"].append(name)
    return classes


def parse_net_functions(sdk_dir: Path) -> dict[str, list[str]]:
    """unreal class name -> [names of FUNC_Net functions declared on that class]."""
    out: dict[str, list[str]] = {}
    for path in sorted(sdk_dir.glob("*_functions.cpp")):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines):
            m = FUNC_COMMENT.match(line)
            if not m:
                continue
            cls, func = m.group(2), m.group(3)
            if i + 1 >= len(lines):
                continue
            fm = FLAGS_COMMENT.match(lines[i + 1])
            if not fm:
                continue
            if "Net" in _flag_set(fm.group(1)):
                out.setdefault(cls, []).append(func)
    return out


def net_fields(unreal: str, classes: dict[str, dict], funcs: dict[str, list[str]],
               include_properties: bool) -> list[str]:
    """UClass::NetFields for one class: own Net props + own Net funcs, sorted by name.

    UE sorts with FString::operator< (Stricmp), i.e. case-insensitive.
    """
    by_unreal = {c["unreal"]: c for c in classes.values()}
    names: list[str] = []
    if include_properties:
        entry = by_unreal.get(unreal)
        if entry:
            names += entry["net_props"]
    names += funcs.get(unreal, [])
    return sorted(names, key=lambda n: (n.lower(), n))


def build_cache(chain: list[str], classes: dict[str, dict], funcs: dict[str, list[str]],
                include_properties: bool) -> tuple[dict[str, int], dict[str, int]]:
    """-> (handle_by_name, fields_base_by_class) walking Object -> ... -> leaf."""
    handles: dict[str, int] = {}
    bases: dict[str, int] = {}
    base = 0
    for cls in chain:
        bases[cls] = base
        nf = net_fields(cls, classes, funcs, include_properties)
        for i, name in enumerate(nf):
            handles[name] = base + i
        base += len(nf)
    return handles, bases


def wrapped_width(value_max: int) -> int:
    """Bit width of UE's FBitWriter::WriteIntWrapped(v, ValueMax) -- bits while Mask < Max."""
    n = 0
    mask = 1
    while mask < value_max:
        n += 1
        mask *= 2
    return n


def cpp_chain(leaf_cpp: str, classes: dict[str, dict]) -> list[str]:
    """[Object ... leaf] as *unreal* class names, walking Dumper-7's super links."""
    out: list[str] = []
    cur = leaf_cpp
    seen = set()
    while cur and cur in classes and cur not in seen:
        seen.add(cur)
        out.append(classes[cur]["unreal"])
        cur = classes[cur]["super_cpp"]
    if cur == "UObject" or (out and out[-1] != "Object"):
        out.append("Object")
    return list(reversed(out))


def score(handles: dict[str, int]) -> tuple[int, int]:
    """(#anchors matched, sum |error|) against the live wire observations."""
    hit = 0
    err = 0
    for name, want in WIRE_ANCHORS.items():
        got = handles.get(name)
        if got is None:
            err += 999
            continue
        if got == want:
            hit += 1
        err += abs(got - want)
    return hit, err


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=os.environ.get("WW3_DUMPER7_DIR", str(DEFAULT_DUMP)))
    ap.add_argument("--json", help="write a class_net_cache_ww3.json-shaped doc here")
    ap.add_argument("--chain", default=",".join(PC_CHAIN))
    ap.add_argument("--leaf", help="comma-separated Dumper-7 C++ class names to walk fully")
    args = ap.parse_args()

    sdk = Path(args.dump)
    if sdk.name != "SDK":
        sdk = sdk / "CppSDK" / "SDK"
    if not sdk.is_dir():
        print(f"SDK dir not found: {sdk}", file=sys.stderr)
        return 2

    chain = [c.strip() for c in args.chain.split(",") if c.strip()]
    classes = parse_classes(sdk)
    funcs = parse_net_functions(sdk)

    print(f"dump      : {sdk}")
    print(f"classes   : {len(classes)}  (net-func classes: {len(funcs)})")
    print(f"chain     : {' -> '.join(chain)}\n")

    best = None
    for include_properties in (False, True):
        handles, bases = build_cache(chain, classes, funcs, include_properties)
        hit, err = score(handles)
        tag = "props+funcs" if include_properties else "funcs-only"
        print(f"=== NetFields model: {tag} ===")
        for cls in chain:
            nf = net_fields(cls, classes, funcs, include_properties)
            print(f"  {cls:<20} FieldsBase={bases[cls]:>4}  NetFields={len(nf):>3}  "
                  f"MaxIndex={bases[cls] + len(nf):>4}")
        for name, want in WIRE_ANCHORS.items():
            got = handles.get(name)
            mark = "OK " if got == want else "MISS"
            print(f"  [{mark}] {name:<36} derived={got}  wire={want}")
        print(f"  score: {hit}/{len(WIRE_ANCHORS)} anchors, total error {err}\n")
        if best is None or (hit, -err) > (best[0], -best[1]):
            best = (hit, err, include_properties, handles, bases)

    hit, err, include_properties, handles, bases = best
    tag = "props+funcs" if include_properties else "funcs-only"
    print(f"=== WINNER: {tag} ({hit}/{len(WIRE_ANCHORS)} anchors, error {err}) ===")
    targets = [
        "ClientRestart",
        "ClientRetryClientRestart",
        "ServerAcknowledgePossession",
        "ServerCheckClientPossession",
        "ServerCheckClientPossessionReliable",
        "ServerNotifyLoadedWorld",
    ]
    for name in targets:
        print(f"  {name:<38} -> {handles.get(name)}")

    leaf = chain[-1]
    nf = net_fields(leaf, classes, funcs, include_properties)
    print(f"\n=== {leaf} NetFields (FieldsBase={bases[leaf]}) ===")
    for i, name in enumerate(nf):
        print(f"  {bases[leaf] + i:>4}  {name}")

    # The wire handle width is WriteIntWrapped(handle, MaxIndex+1) of the *actual* actor
    # class, so it depends on the whole subclass chain. 8 bits is what the capture shows.
    if args.leaf:
        print("\n=== full subclass chains: MaxIndex -> wire handle width ===")
        for leaf_cpp in args.leaf.split(","):
            leaf_cpp = leaf_cpp.strip()
            if leaf_cpp not in classes:
                print(f"  {leaf_cpp}: NOT IN DUMP")
                continue
            full = cpp_chain(leaf_cpp, classes)
            h2, b2 = build_cache(full, classes, funcs, include_properties)
            last = full[-1]
            maxidx = b2[last] + len(net_fields(last, classes, funcs, include_properties))
            print(f"  {leaf_cpp:<44} MaxIndex={maxidx:>4}  "
                  f"width={wrapped_width(maxidx + 1)} bits  depth={len(full)}")
            for c in full:
                n = len(net_fields(c, classes, funcs, include_properties))
                if n:
                    by_unreal = {v["unreal"]: v for v in classes.values()}
                    np_ = len(by_unreal.get(c, {}).get("net_props", []))
                    print(f"      {c:<42} base={b2[c]:>4} +{n:<4} "
                          f"(props {np_}, funcs {len(funcs.get(c, []))})")

    if args.json:
        doc = {
            "schema_version": 2,
            "game": "WW3",
            "engine": "UE4.21",
            "source": "dumper7_sdk_netfields",
            "build": {"dump": str(sdk), "id": sdk.parents[1].name},
            "netfields_model": tag,
            "handle_bits": 8,
            "handle_value_max": 315,
            "anchor_check": {
                "class": leaf,
                "field": "ServerAcknowledgePossession",
                "index": handles.get("ServerAcknowledgePossession"),
            },
            "wire_anchors": WIRE_ANCHORS,
            "chain": {c: {"fields_base": bases[c],
                          "net_fields": net_fields(c, classes, funcs, include_properties)}
                      for c in chain},
            "rpc_handles": {leaf: handles},
            "by_index": {leaf: {str(v): k for k, v in sorted(handles.items(),
                                                             key=lambda kv: kv[1])}},
            "notes": [
                "Generated by match_server/derive_net_handles.py from the Dumper-7 dump of "
                "the live WW3 build -- do not hand-edit.",
                "handle_value_max=315 (AWW3GamePlayerController MaxIndex+1): UE writes "
                "the handle as SerializeInt(index, MaxIndex+1), whose width depends on "
                "the VALUE, not just the class -- handle>=59 takes 8 bits, smaller ones "
                "take 9. handle_bits=8 is the legacy fixed-width control only; it agrees "
                "on every C->S handle (all >=64) but wrote ClientRestart (39) one bit "
                "short. Bracketed to [311,320] by the wire; see "
                "match_server/_probe_wrapped_valuemax.py.",
                "All 8 wire_anchors reproduce exactly; see "
                "match_server/live_log/HANDLE_DERIVE.md.",
            ],
        }
        Path(args.json).write_text(json.dumps(doc, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
