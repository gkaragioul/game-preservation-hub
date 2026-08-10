#!/usr/bin/env python3
r"""Model-free structure recovery for the PlayerState property block.

13 captured PlayerState opens carry the same class's RepLayout block with
different data. Handle bytes are *identical* across samples (same properties
changed vs the archetype); value bits differ. Aligning the samples from the
front therefore exposes the handle positions directly, with no SDK model
assumed -- and once the handle positions are known, the widths fall out, and
the widths are what identify the correct flattening model.

  python match_server/_align_ps_blocks.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _ps_blocks import playerstate_samples  # noqa: E402
from actor_channel import Bits  # noqa: E402


def agree_map(payloads: list[list[int]]) -> list[str]:
    """-> per-bit '0'/'1' where every sample agrees, '.' where they differ."""
    n = min(len(p) for p in payloads)
    out = []
    for i in range(n):
        v = payloads[0][i]
        out.append(str(v) if all(p[i] == v for p in payloads) else ".")
    return out


def try_packed(bits: list[int], pos: int) -> tuple[int, int] | None:
    """Read SerializeIntPacked at pos -> (value, nbits) or None."""
    r = Bits(bits, pos)
    try:
        v = r.packed()
    except EOFError:
        return None
    return v, r.pos - pos


def main() -> int:
    samples = playerstate_samples()
    pays = [s["payload"] for s in samples]
    labels = [f"ch{s['chIndex']}" for s in samples]

    print(f"samples={len(pays)}  lens={[len(p) for p in pays]}")

    ag = agree_map(pays)
    print(f"\ncommon prefix length considered: {len(ag)} bits")
    print("agreement map (. = differs between samples):")
    for off in range(0, len(ag), 96):
        print(f"  {off:>4}: " + "".join(ag[off:off + 96]))

    # Longest run of agreement from the start
    run = 0
    while run < len(ag) and ag[run] != ".":
        run += 1
    print(f"\nagreeing prefix = {run} bits")

    # Candidate handle positions: any byte-window where all 13 agree and the
    # packed read yields a small ascending handle.
    print("\n=== candidate handle reads at all-agree windows ===")
    last = 0
    pos = 0
    while pos < len(ag) - 8:
        if all(c != "." for c in ag[pos:pos + 8]):
            got = try_packed(pays[0], pos)
            if got and 0 < got[0] < 400:
                v, nb = got
                mark = "  ASC" if v > last else ""
                print(f"  pos={pos:>4} packed={v:>4} ({nb} bits){mark}")
        pos += 1

    # Reverse alignment: trailing structure
    print("\n=== last 64 bits of each sample ===")
    for lab, p in zip(labels, pays):
        print(f"  {lab:<6} {''.join(str(b) for b in p[-64:])}")

    # Suffix agreement
    n = min(len(p) for p in pays)
    suf = []
    for i in range(1, n + 1):
        v = pays[0][-i]
        suf.append(str(v) if all(p[-i] == v for p in pays) else ".")
    srun = 0
    while srun < len(suf) and suf[srun] != ".":
        srun += 1
    print(f"\nagreeing suffix = {srun} bits: "
          f"{''.join(reversed(suf[:min(srun + 24, len(suf))]))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
