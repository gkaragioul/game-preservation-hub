#!/usr/bin/env python3
r"""Scan the capture for actor RepLayout blocks and report the first handle each one
carries, so we can find which bunch delivers a given replicated property.

RepLayout handles inside a property block are strictly ascending, so a block whose first
handle is 34 cannot possibly contain handle 16. That makes "first handle" enough to locate
the bunch that delivers a low-numbered property such as `AController::PlayerState` (16) or
`AController::Pawn` (17) -- see `derive_rep_handles.py` for the numbering.

  python match_server/_first_handle_scan.py --ch 2 --max-handle 20
  python match_server/_first_handle_scan.py --ch 2 3 7 --limit 400
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from actor_channel import Bits, read_content_blocks, read_new_actor  # noqa: E402
from netguid import GuidReader, PackageMap  # noqa: E402

STREAM = os.path.join(HERE, "real_replay_stream.json")


def groups_for_channel(stream: list, ch: int):
    """Yield (src_indices, [bunch specs]) with partial chains reassembled."""
    group: list[dict] = []
    gidx: list[int] = []
    for i, sp in enumerate(stream):
        if sp["chIndex"] != ch:
            continue
        if sp.get("bPartial"):
            if sp.get("bPartialInitial"):
                group, gidx = [sp], [i]
            else:
                group.append(sp)
                gidx.append(i)
            if sp.get("bPartialFinal") and group:
                yield gidx, group
                group, gidx = [], []
        else:
            yield [i], [sp]


def blocks_of(specs: list[dict]):
    bits: list[int] = []
    for sp in specs:
        bits.extend(int(c) for c in sp["payload"])
    pm = PackageMap()
    pos = 0
    if specs[0].get("bHasPackageMapExports"):
        pos = pm.read_export_bunch(bits)["reader"].pos
    if specs[0].get("bOpen"):
        gr = GuidReader(bits, pos)
        read_new_actor(gr, pm)
        pos = gr.pos
    return read_content_blocks(Bits(bits, pos), total_bits=len(bits))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ch", nargs="*", type=int, default=[2])
    ap.add_argument("--limit", type=int, default=10 ** 9, help="stop after this src index")
    ap.add_argument("--max-handle", type=int, default=10 ** 9,
                    help="only report blocks whose first handle is <= this")
    args = ap.parse_args()

    stream = json.load(open(STREAM))
    for ch in args.ch:
        print(f"\n===== channel {ch} =====")
        hits = 0
        for gidx, specs in groups_for_channel(stream, ch):
            if gidx[0] > args.limit:
                break
            try:
                blocks = blocks_of(specs)
            except Exception as exc:
                print(f"  src={gidx} DECODE FAIL {type(exc).__name__}: {exc}")
                continue
            for bi, b in enumerate(blocks):
                if not (b.get("isActor") and b.get("hasRepLayout") and b.get("payload")):
                    continue
                try:
                    h = Bits(b["payload"]).packed()
                except EOFError:
                    continue
                if h > args.max_handle:
                    continue
                hits += 1
                print(f"  src={gidx} block[{bi}] first_handle={h:<5} "
                      f"payloadBits={b['payloadBits']} open={bool(specs[0].get('bOpen'))}")
        print(f"  -> {hits} block(s) with first handle <= {args.max_handle}")


if __name__ == "__main__":
    main()
