#!/usr/bin/env python3
r"""Probe the start offset of the PlayerState RepLayout handle stream.

The wire anchors recovered by `_ps_anchor.py` (handle 20 = PlayerNamePrivate,
21 = ClientReplicatedPingPacked, 22 = PlayerCharacter) match
`derive_rep_handles.py` exactly, yet reading a packed handle at payload bit 0
yields 26 -- larger than handles that appear later. So the numbering model is
right and the *start offset* is wrong. This walks candidate start offsets and
reports which one produces a strictly ascending chain that lands on the known
handle-19 position.

  python match_server/_ps_offset_probe.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _find_ps_strings import scan  # noqa: E402
from _ps_blocks import playerstate_samples  # noqa: E402
from actor_channel import Bits  # noqa: E402


def packed_at(bits, pos):
    r = Bits(bits, pos)
    try:
        return r.packed(), r.pos - pos
    except EOFError:
        return None, 0


def main() -> int:
    samples = playerstate_samples()
    print("=== read packed at each candidate handle site (derived from anchors) ===")
    for s in samples:
        p = s["payload"]
        found = [f for f in scan(p) if len(f[1]) >= 3]
        if len(found) < 2:
            continue
        upos = found[0][0]
        h19_pos = upos - 16          # 8-bit handle + 8-bit FUniqueNetIdRepl prefix
        h19, _ = packed_at(p, h19_pos)
        # if handle 17 (PlayerId, int32) immediately precedes handle 19:
        h17_pos = h19_pos - 40
        h17, _ = packed_at(p, h17_pos)
        pre = "".join(str(b) for b in p[max(0, h17_pos - 32):h17_pos])
        print(f"ch{s['chIndex']:<4} uidPos={upos:<4} h19@{h19_pos:<4}->{str(h19):<5} "
              f"h17@{h17_pos:<4}->{str(h17):<5} pre32={pre}")

    print("\n=== packed reads at bit 0..3 of each payload ===")
    for s in samples:
        p = s["payload"]
        vals = []
        for off in range(4):
            v, w = packed_at(p, off)
            vals.append(f"{off}:{v}")
        print(f"ch{s['chIndex']:<4} " + "  ".join(vals) +
              f"   head16={''.join(str(b) for b in p[:16])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
