#!/usr/bin/env python3
r"""Inspect what follows the RepLayout terminator inside an actor property block.

Every block that still fails now fails the same way: a clean handle-0 terminator
with a constant number of bits left (454 on ABP_BotPawn_01_C, 568 on the PC open).
UE reads that remainder in `FObjectReplicator::ReceivedBunch` as a chain of
`ReadFieldHeaderAndPayload` records -- the custom-delta / ClassNetCache field
space, i.e. the same framing as an RPC, not RepLayout. This dumps the tails so
the next session can confirm that rather than re-litigating the numbering.

  python match_server/_probe_block_tail.py
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import derive_rep_handles as D  # noqa: E402
from _decode_rep_block import decode, layout  # noqa: E402
from fit_rep_model import collect_blocks  # noqa: E402


def main() -> int:
    sdk = Path(os.environ.get("WW3_DUMPER7_DIR", str(D.DEFAULT_DUMP)))
    if sdk.name != "SDK":
        sdk = sdk / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)

    for leaf in ("ABP_BotPawn_01_C", "ABP_WW3_DominationPlayerController_01_C"):
        by_h, types = layout(leaf, classes, structs)
        payloads = collect_blocks(leaf, classes)
        lefts = Counter()
        tails = []
        for p in payloads:
            r = decode(p, by_h, types, enums=enums)
            if r["closed"] or r["reason"] != "terminator":
                continue
            lefts[r["left"]] += 1
            tails.append(p[len(p) - r["left"]:])
        print(f"\n=== {leaf}: {len(tails)} blocks end on a terminator with bits left ===")
        for n, c in lefts.most_common(6):
            print(f"   left={n:<6} x{c}")
        if not tails:
            continue
        uniq = {tuple(t) for t in tails}
        print(f"   distinct tails: {len(uniq)} of {len(tails)}")
        print(f"   first tail[:96] : {''.join(str(b) for b in tails[0][:96])}")
        if len(tails) > 1:
            print(f"   second tail[:96]: {''.join(str(b) for b in tails[1][:96])}")
            same = sum(1 for a, b in zip(tails[0], tails[1]) if a == b)
            print(f"   tail0 vs tail1 agreement: {same}/{min(len(tails[0]), len(tails[1]))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
