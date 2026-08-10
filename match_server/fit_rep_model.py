#!/usr/bin/env python3
r"""Score RepLayout flattening models against captured wire data.

Replaces the old `_fit_rep_model.py`, which scored a single hand-read anchor
(`APlayerController::Pawn == 34`) that turned out to be a decode artefact of
reading the property block from bit 0 instead of bit 1 (see `repblock.py`).

The scoring criterion is now the one NEXT_EXPERIMENT.md asked for, applied to
every captured block of the class: a model is accepted only if each block ends
on handle 0 with **exactly** 0 bits left.

  python match_server/fit_rep_model.py --leaf ABP_WW3DominationPlayerState_C
  python match_server/fit_rep_model.py --leaf ABP_BotPawn_01_C --sample 40
  python match_server/fit_rep_model.py --leaf ABP_BotPawn_01_C --candidates
"""
from __future__ import annotations

import argparse
import itertools
import os
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import derive_rep_handles as D  # noqa: E402
from _decode_all_blocks import archetype_to_class, groups  # noqa: E402
from _decode_rep_block import decode, layout  # noqa: E402
from actor_channel import Bits, read_content_blocks, read_new_actor  # noqa: E402
from netguid import GuidReader, PackageMap  # noqa: E402

#: structs whose atomicity is not in question (native NetSerializer, proven by
#: the PlayerState/PlayerController blocks closing 626/626 and by AActor's
#: Owner/Role/Instigator landing on 13/14/15)
BASE_ATOMIC = {"FUniqueNetIdRepl", "FGameplayTag", "FGameplayTagContainer",
               "FRepMovement", "FRotator", "FVector", "FVector2D", "FVector4",
               "FQuat", "FIntPoint", "FIntVector",
               "FVector_NetQuantize", "FVector_NetQuantize10",
               "FVector_NetQuantize100", "FVector_NetQuantizeNormal"}


def candidate_structs(leaf, classes, structs):
    """Structs the leaf's net properties actually recurse through."""
    seen: list[str] = []

    def walk(tname, depth=0):
        if depth > 6 or tname in BASE_ATOMIC:
            return
        if tname in structs:
            if tname not in seen:
                seen.append(tname)
            for _o, _n, t, _f in structs[tname]["props"]:
                walk(t, depth + 1)

    for cls in D.chain_of(leaf, classes):
        for _off, _n, t, f in classes[cls]["props"]:
            if "Net" in f:
                walk(t)
    return seen


def collect_blocks(target_cls, classes, limit=None):
    """-> [payload] for every isActor RepLayout block on channels of `target_cls`."""
    import json

    stream = json.load(open(os.path.join(HERE, "real_replay_stream.json")))
    ch_class: dict[int, str] = {}
    out = []
    for ch, idxs in groups(stream):
        specs = [stream[i] for i in idxs]
        bits: list[int] = []
        for sp in specs:
            bits.extend(int(c) for c in sp["payload"])
        pm = PackageMap()
        pos = 0
        try:
            if specs[0].get("bHasPackageMapExports"):
                pos = pm.read_export_bunch(bits)["reader"].pos
            if specs[0].get("bOpen"):
                gr = GuidReader(bits, pos)
                hdr = read_new_actor(gr, pm)
                pos = gr.pos
                cls = archetype_to_class(hdr.get("archetypePath") or "", classes)
                if cls:
                    ch_class[ch] = cls
                if hdr.get("incomplete"):
                    continue
            if ch_class.get(ch) != target_cls:
                continue
            blocks = read_content_blocks(Bits(bits, pos), total_bits=len(bits))
        except Exception:
            continue
        for b in blocks:
            if b.get("isActor") and b.get("hasRepLayout") and not b.get("bad"):
                out.append(b["payload"])
                if limit and len(out) >= limit:
                    return out
    return out


def score(leaf, atomic, classes, structs, enums, payloads):
    D.NET_SERIALIZE_STRUCTS.clear()
    D.NET_SERIALIZE_STRUCTS.update(BASE_ATOMIC)
    D.NET_SERIALIZE_STRUCTS.update(atomic)
    by_h, types = layout(leaf, classes, structs)
    return sum(1 for p in payloads if decode(p, by_h, types, enums=enums)["closed"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--leaf", required=True)
    ap.add_argument("--sample", type=int, default=60,
                    help="blocks used during the search (all are used to verify)")
    ap.add_argument("--candidates", action="store_true", help="just list ambiguous structs")
    ap.add_argument("--max-atomic", type=int, default=3,
                    help="max structs forced atomic per model")
    ap.add_argument("--dump", default=os.environ.get("WW3_DUMPER7_DIR", str(D.DEFAULT_DUMP)))
    args = ap.parse_args()

    sdk = Path(args.dump)
    if sdk.name != "SDK":
        sdk = sdk / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)

    cands = candidate_structs(args.leaf, classes, structs)
    print(f"leaf={args.leaf}  ambiguous structs reachable: {len(cands)}")
    for c in cands:
        print(f"    {c}")
    if args.candidates:
        return 0

    allp = collect_blocks(args.leaf, classes)
    print(f"\ncaptured blocks for this class: {len(allp)}")
    if not allp:
        return 2
    probe = allp[:args.sample]

    base = score(args.leaf, (), classes, structs, enums, probe)
    print(f"baseline (nothing extra atomic): {base}/{len(probe)}")

    results = []
    for r in range(args.max_atomic + 1):
        for atomic in itertools.combinations(cands, r):
            ok = score(args.leaf, atomic, classes, structs, enums, probe)
            results.append((ok, atomic))
    results.sort(key=lambda x: -x[0])
    print(f"\ntop models on the {len(probe)}-block probe:")
    for ok, atomic in results[:15]:
        print(f"  {ok:>4}/{len(probe)}  {{{','.join(atomic) or 'none'}}}")

    best_ok, best = results[0]
    if best_ok == len(probe):
        full = score(args.leaf, best, classes, structs, enums, allp)
        print(f"\nverify best model on all {len(allp)} blocks: {full}/{len(allp)}")
        if full == len(allp):
            D.NET_SERIALIZE_STRUCTS.clear()
            D.NET_SERIALIZE_STRUCTS.update(BASE_ATOMIC)
            D.NET_SERIALIZE_STRUCTS.update(best)
            for h, cls, name, typ in D.build_typed(args.leaf, classes, structs):
                print(f"  {h:>4}  {cls:<24} {name:<58} {typ}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
