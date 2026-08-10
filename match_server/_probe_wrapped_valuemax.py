#!/usr/bin/env python3
"""Bracket `ClassCache->GetMaxIndex()+1` (the ValueMax of the RPC field handle).

`_probe_field_header.py` settled that the handle is *not* `SerializeIntPacked`, but it
only ever tested **fixed-width** models. UE 4.21 actually writes it with

    FBitWriter::SerializeInt(FieldNetIndex, ClassCache->GetMaxIndex() + 1)

which is *value-dependent*, not fixed width::

    for (Mask = 1; (Written + Mask) < ValueMax && Mask; Mask *= 2)
        write bit (Value & Mask)

For ValueMax in (256, 512] a handle >= ValueMax-256 stops after 8 bits while a smaller
handle takes 9. Every C->S anchor is >= 64, so on this build's traffic `fixed8` and
`wrapped(ValueMax<=320)` are *identical* -- which is exactly why the fixed-8 model scored
100%, and exactly why the S->C `ClientRestart` handle 39 (small!) was written one bit short.

This probe re-runs the exact-consumption test for the wrapped model over a sweep of
ValueMax and prints the range that survives.
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


def read_wrapped(pb: list[int], pos: int, value_max: int) -> tuple[int, int]:
    """FBitReader::SerializeInt(Value, ValueMax) -- reads a value-dependent bit count."""
    value = 0
    mask = 1
    while (value + mask) < value_max and mask < (1 << 32):
        if pos >= len(pb):
            raise EOFError
        if pb[pos]:
            value |= mask
        pos += 1
        mask <<= 1
    return value, pos


def try_wrapped(pb: list[int], value_max: int) -> list[int] | None:
    pos = 0
    handles: list[int] = []
    while pos < len(pb):
        try:
            h, pos = read_wrapped(pb, pos, value_max)
            n, pos = read_packed(pb, pos)
        except EOFError:
            return None
        if pos + n > len(pb):
            return None
        pos += n
        handles.append(h)
    return handles if pos == len(pb) else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pcap")
    ap.add_argument("--session")
    ap.add_argument("--chan", type=int, default=2)
    ap.add_argument("--sip", default="auto")
    ap.add_argument("--sport", type=int, default=7868)
    ap.add_argument("--lo", type=int, default=200)
    ap.add_argument("--hi", type=int, default=520)
    ap.add_argument("--limit", type=int, default=0,
                    help="only use the first N blocks (speed)")
    args = ap.parse_args()

    if args.session:
        blocks = collect_session(Path(args.session), args.chan)
    else:
        blocks = collect_blocks(Path(args.pcap), args.chan, args.sip, args.sport)
    if args.limit:
        blocks = blocks[: args.limit]
    print(f"collected {len(blocks)} isActor/no-RepLayout content-block payloads "
          f"on ch{args.chan}\n")

    survivors: list[int] = []
    print(f"{'ValueMax':>9} {'exact':>8} {'rate':>7}  handles")
    for vm in range(args.lo, args.hi + 1):
        ok = 0
        hist: collections.Counter = collections.Counter()
        for pb in blocks:
            hs = try_wrapped(pb, vm)
            if hs is None:
                continue
            ok += 1
            for h in hs:
                hist[h] += 1
        rate = ok / len(blocks) if blocks else 0
        if rate >= 0.995:
            survivors.append(vm)
            if vm in (args.lo, args.hi) or len(survivors) <= 3 or vm % 16 == 0:
                top = ", ".join(f"{h}:{c}" for h, c in hist.most_common(10))
                print(f"{vm:>9} {ok:>8} {rate:>6.1%}  {top}")

    if survivors:
        # contiguous runs
        runs = []
        start = prev = survivors[0]
        for v in survivors[1:]:
            if v == prev + 1:
                prev = v
                continue
            runs.append((start, prev))
            start = prev = v
        runs.append((start, prev))
        print("\nValueMax ranges consuming >=99.5% of blocks exactly:")
        for a, b in runs:
            print(f"  [{a} .. {b}]")
        print("\nBits needed for handle 39 in each range:")
        for a, b in runs:
            for vm in (a, b):
                pos = 0
                v, mask = 0, 1
                n = 0
                while (v + mask) < vm and mask < (1 << 32):
                    n += 1
                    mask <<= 1
                print(f"  ValueMax {vm}: handle 39 -> "
                      f"{_wrapped_width(39, vm)} bits (max width {n})")
    else:
        print("\nno ValueMax survives -- the wrapped model is wrong for this corpus")
    return 0


def _wrapped_width(value: int, value_max: int) -> int:
    written = 0
    mask = 1
    n = 0
    while (written + mask) < value_max and mask < (1 << 32):
        if value & mask:
            written |= mask
        n += 1
        mask <<= 1
    return n


if __name__ == "__main__":
    raise SystemExit(main())
