#!/usr/bin/env python3
r"""Decode every isActor RepLayout block in the captured stream.

The definitive score for the RepLayout numbering model: replay the whole
capture, remember which archetype opened each channel, and run every actor
property block on that channel through the decoder. A wrong flattening model,
a wrong width rule or a wrong block prefix shows up immediately as blocks that
do not exact-consume.

  python match_server/_decode_all_blocks.py
  python match_server/_decode_all_blocks.py --ch 3 --verbose
  python match_server/_decode_all_blocks.py --fails 20
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import derive_rep_handles as D  # noqa: E402
from _decode_rep_block import decode, layout  # noqa: E402
from actor_channel import Bits, read_content_blocks, read_new_actor  # noqa: E402
from netguid import GuidReader, PackageMap  # noqa: E402

STREAM = os.path.join(HERE, "real_replay_stream.json")


def archetype_to_class(arch: str, classes: dict) -> str | None:
    """`Default__BP_PlayerPawn_01_C` -> `ABP_PlayerPawn_01_C`."""
    if not arch:
        return None
    name = arch.split("/")[-1]
    if name.startswith("Default__"):
        name = name[len("Default__"):]
    for pre in ("A", "U", ""):
        if pre + name in classes:
            return pre + name
    return None


def groups(stream):
    """Yield (chIndex, [src indices]) for each reassembled bunch, in order."""
    pending: dict[int, list[int]] = defaultdict(list)
    for i, sp in enumerate(stream):
        ch = sp["chIndex"]
        if not sp.get("bPartial"):
            yield ch, [i]
            continue
        if sp.get("bPartialInitial"):
            pending[ch] = [i]
        elif pending.get(ch):
            pending[ch].append(i)
        else:
            continue
        if sp.get("bPartialFinal") and pending.get(ch):
            yield ch, pending.pop(ch)


def main() -> int:
    import json

    ap = argparse.ArgumentParser()
    ap.add_argument("--ch", type=int, default=None)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--fails", type=int, default=12)
    ap.add_argument("--dump", default=os.environ.get("WW3_DUMPER7_DIR", str(D.DEFAULT_DUMP)))
    args = ap.parse_args()

    sdk = Path(args.dump)
    if sdk.name != "SDK":
        sdk = sdk / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)

    stream = json.load(open(STREAM))
    ch_class: dict[int, str] = {}
    ch_arch: dict[int, str] = {}
    cache: dict[str, tuple] = {}

    stats = defaultdict(lambda: [0, 0])       # class -> [closed, total]
    fails = []
    unknown_class = defaultdict(int)

    for ch, idxs in groups(stream):
        if args.ch is not None and ch != args.ch:
            continue
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
                arch = hdr.get("archetypePath") or ""
                ch_arch[ch] = arch
                cls = archetype_to_class(arch, classes)
                if cls:
                    ch_class[ch] = cls
                elif arch:
                    unknown_class[arch] += 1
                if hdr.get("incomplete"):
                    continue
            blocks = read_content_blocks(Bits(bits, pos), total_bits=len(bits))
        except Exception:
            continue

        leaf = ch_class.get(ch)
        if not leaf:
            continue
        if leaf not in cache:
            cache[leaf] = layout(leaf, classes, structs)
        by_h, types = cache[leaf]

        for b in blocks:
            if not (b.get("isActor") and b.get("hasRepLayout")) or b.get("bad"):
                continue
            r = decode(b["payload"], by_h, types, enums=enums)
            st = stats[leaf]
            st[1] += 1
            if r["closed"]:
                st[0] += 1
            else:
                fails.append((ch, idxs, leaf, len(b["payload"]), r))
            if args.verbose:
                print(f"\nch{ch} srcs={idxs} {leaf} bits={len(b['payload'])} "
                      f"{'CLOSED' if r['closed'] else 'FAIL ' + r['reason']} left={r['left']}")
                for h, name, typ, w, note, p in r["seq"]:
                    print(f"   @{p:<5} h{h:<4} {name:<44} {str(typ):<22} w={w:<5} {note}")

    tot_ok = sum(v[0] for v in stats.values())
    tot = sum(v[1] for v in stats.values())
    kinds = defaultdict(int)
    for _ch, _idxs, _leaf, _n, r in fails:
        kinds["clean terminator + custom-delta tail" if r["reason"] == "terminator"
              else r["reason"].split("_")[0]] += 1
    print(f"\n=== actor property blocks decoded: {tot_ok}/{tot} exact-consume ===")
    if kinds:
        print("failure reasons:")
        for k, c in sorted(kinds.items(), key=lambda kv: -kv[1]):
            print(f"  {c:>6}  {k}")
    for cls, (ok, n) in sorted(stats.items(), key=lambda kv: -kv[1][1]):
        flag = "" if ok == n else "   <-- MISMATCH"
        print(f"  {ok:>6}/{n:<6}  {cls}{flag}")
    if unknown_class:
        print("\narchetypes with no class in the dump:")
        for a, c in sorted(unknown_class.items(), key=lambda kv: -kv[1])[:10]:
            print(f"  {c:>4}  {a}")
    if fails:
        print(f"\nfirst {min(args.fails, len(fails))} failures:")
        for ch, idxs, leaf, nbits, r in fails[:args.fails]:
            print(f"  ch{ch} srcs={idxs[:2]} {leaf} bits={nbits} "
                  f"{r['reason']} left={r['left']} props={len(r['seq'])}")
    return 0 if tot and tot_ok == tot else 1


if __name__ == "__main__":
    raise SystemExit(main())
