#!/usr/bin/env python3
"""Payload-bit shapes per RPC handle, decoded with the *wrapped* field-handle model.

Answers two questions the old `_c2s_handle_histogram.py` could not:

1. What is `ClassCache->GetMaxIndex()+1` (`--value-max`)? See `_probe_wrapped_valuemax.py`.
2. Does an RPC parameter payload start with `FRepLayout::SendPropertiesForRPC`'s
   per-parameter "Send" bit?

(2) is decidable from a single-`UObject*`-parameter RPC such as
`ServerAcknowledgePossession(APawn*)` (handle 64): a NetGUID is `SerializeIntPacked`,
i.e. always a whole number of bytes, so

    payload_bits % 8 == 0  ->  no Send bit
    payload_bits % 8 == 1  ->  one leading Send bit

`--decode-object H` prints both readings of every payload for handle H.
"""
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "match_analysis"))

from _probe_field_header import (collect_blocks, collect_session,  # noqa: E402
                                 read_packed)
from _probe_wrapped_valuemax import read_wrapped  # noqa: E402


def split_fields(pb: list[int], value_max: int):
    pos = 0
    out = []
    while pos < len(pb):
        try:
            h, pos = read_wrapped(pb, pos, value_max)
            n, pos = read_packed(pb, pos)
        except EOFError:
            return None
        if pos + n > len(pb):
            return None
        out.append((h, pb[pos:pos + n]))
        pos += n
    return out if pos == len(pb) else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pcap")
    ap.add_argument("--session")
    ap.add_argument("--chan", type=int, default=2)
    ap.add_argument("--sip", default="auto")
    ap.add_argument("--sport", type=int, default=7868)
    ap.add_argument("--value-max", type=int, default=315)
    ap.add_argument("--decode-object", type=int, action="append", default=[])
    args = ap.parse_args()

    if args.session:
        blocks = collect_session(Path(args.session), args.chan)
    else:
        blocks = collect_blocks(Path(args.pcap), args.chan, args.sip, args.sport)
    print(f"{len(blocks)} blocks, ValueMax={args.value_max}\n")

    shapes: dict[int, collections.Counter] = {}
    samples: dict[int, list[list[int]]] = {}
    bad = 0
    for pb in blocks:
        fs = split_fields(pb, args.value_max)
        if fs is None:
            bad += 1
            continue
        for h, payload in fs:
            shapes.setdefault(h, collections.Counter())[len(payload)] += 1
            if h in args.decode_object and len(samples.setdefault(h, [])) < 12:
                samples[h].append(payload)

    print(f"{'handle':>7} {'n':>8}  payload-bit sizes (top 6)     mod8")
    for h in sorted(shapes):
        c = shapes[h]
        n = sum(c.values())
        top = ", ".join(f"{k}:{v}" for k, v in c.most_common(6))
        mod = collections.Counter(k % 8 for k in c.elements())
        modtxt = ", ".join(f"{k}:{v}" for k, v in sorted(mod.items()))
        print(f"{h:>7} {n:>8}  {top:<29} {modtxt}")
    print(f"\nblocks not consumed exactly: {bad}/{len(blocks)}")

    for h in args.decode_object:
        print(f"\n--- handle {h}: object-parameter payload readings ---")
        for payload in samples.get(h, []):
            raw = "".join(str(b) for b in payload)
            try:
                v0, _ = read_packed(payload, 0)
            except EOFError:
                v0 = None
            try:
                v1, _ = read_packed(payload, 1)
            except EOFError:
                v1 = None
            print(f"  len={len(payload):>3} bits={raw}")
            print(f"      no-send-bit: packed@0 = {v0}")
            print(f"      send-bit={payload[0] if payload else '-'} packed@1 = {v1}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
