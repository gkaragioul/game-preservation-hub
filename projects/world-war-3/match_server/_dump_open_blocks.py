#!/usr/bin/env python3
r"""Dump the content-block chain of captured opens, and test where each
isActor RepLayout stream actually starts.

`_ps_offset_probe.py` showed the PlayerState handle stream is ascending and
model-correct but begins one bit *into* the block payload our parser hands
back. This tells us whether that leading bit is (a) universal across classes,
(b) a mis-parse of SerializeNewActor, or (c) specific to the open bunch.

  python match_server/_dump_open_blocks.py
  python match_server/_dump_open_blocks.py --arch PlayerPawn
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _ps_blocks import group_opens, load_stream, parse_open  # noqa: E402
from actor_channel import Bits  # noqa: E402


def packed_at(bits, pos):
    r = Bits(bits, pos)
    try:
        return r.packed(), r.pos - pos
    except EOFError:
        return None, 0


def ascending_chain(bits, start, maxh=600):
    """Greedy: read a handle, then look for the *next* plausible handle only by
    scanning forward. Here we just report the first handle at `start`."""
    v, _w = packed_at(bits, start)
    return v


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arch", default=None, help="substring filter on archetype path")
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args()

    stream = load_stream()
    shown = 0
    for _first, idxs in group_opens(stream):
        try:
            g = parse_open(stream, idxs)
        except Exception as e:
            continue
        arch = g["header"].get("archetypePath") or "?"
        if args.arch and args.arch.lower() not in arch.lower():
            continue
        shown += 1
        if shown > args.limit:
            break
        total = sum(len(stream[i]["payload"]) for i in idxs)
        hdr = g["header"]
        print(f"\n=== ch{g['chIndex']} srcs={idxs} guid={hdr.get('netguid')} "
              f"totalBits={total} arch={arch}")
        print(f"    header: loc={hdr.get('location') is not None} "
              f"rot={hdr.get('has_rotation')} scale={hdr.get('has_scale')} "
              f"vel={hdr.get('has_velocity')} incomplete={hdr.get('incomplete')}")
        for bi, b in enumerate(g["blocks"]):
            kind = "ACTOR" if b.get("isActor") else f"SUB({b.get('subNetGUID')})"
            if b.get("bad"):
                print(f"    [{bi}] {kind:<12} hasRep={b.get('hasRepLayout')} BAD "
                      f"start={b.get('start')}")
                continue
            p = b["payload"]
            h0 = ascending_chain(p, 0)
            h1 = ascending_chain(p, 1)
            tail8 = "".join(str(x) for x in p[-8:]) if len(p) >= 8 else ""
            print(f"    [{bi}] {kind:<12} hasRep={b.get('hasRepLayout')} "
                  f"start={b['start']:<6} bits={b['payloadBits']:<6} "
                  f"packed@0={str(h0):<6} packed@1={str(h1):<6} tail8={tail8}")
        end = g["blocks"][-1]["start"] + 0 if g["blocks"] else 0
        last = g["blocks"][-1] if g["blocks"] else None
        if last and not last.get("bad"):
            consumed = last["start"] + 2 + last["payloadBits"]
            print(f"    (chain end approx {consumed} of {total} bits)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
