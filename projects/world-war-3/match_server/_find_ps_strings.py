#!/usr/bin/env python3
r"""Find the FString(s) inside the captured PlayerState property blocks.

An FString on the UE wire is `int32 SaveNum` followed by SaveNum ANSI chars
including the trailing NUL (negative SaveNum = UCS2). Player names are the one
piece of a PlayerState block whose *content* we can recognise without knowing
the RepLayout numbering at all -- so finding them anchors the handle stream:
whatever handle immediately precedes the string is PlayerNamePrivate, and that
single fact fixes the flattening model.

  python match_server/_find_ps_strings.py
"""
from __future__ import annotations

import os
import string
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _ps_blocks import playerstate_samples  # noqa: E402
from actor_channel import Bits  # noqa: E402

PRINTABLE = set(string.printable) - set("\t\r\x0b\x0c")


def read_u32(bits: list[int], pos: int) -> int | None:
    if pos + 32 > len(bits):
        return None
    return sum(bits[pos + i] << i for i in range(32))


def read_u8(bits: list[int], pos: int) -> int | None:
    if pos + 8 > len(bits):
        return None
    return sum(bits[pos + i] << i for i in range(8))


def try_fstring(bits: list[int], pos: int, maxlen: int = 80):
    """Try to read an FString at `pos`. -> (text, total_bits) or None."""
    n = read_u32(bits, pos)
    if n is None or n <= 1 or n > maxlen:
        return None
    need = 32 + n * 8
    if pos + need > len(bits):
        return None
    chars = []
    for i in range(n):
        c = read_u8(bits, pos + 32 + i * 8)
        chars.append(c)
    if chars[-1] != 0:
        return None
    if any(c == 0 for c in chars[:-1]):
        return None
    text = "".join(chr(c) for c in chars[:-1])
    if not all(ch in PRINTABLE for ch in text):
        return None
    return text, need


def scan(bits: list[int]):
    out = []
    for pos in range(0, len(bits) - 40):
        got = try_fstring(bits, pos)
        if got:
            out.append((pos, got[0], got[1]))
    return out


def main() -> int:
    samples = playerstate_samples()
    print("=== FString candidates per PlayerState block ===")
    hits = {}
    for s in samples:
        p = s["payload"]
        found = scan(p)
        # keep the longest plausible name per start region
        found = [f for f in found if len(f[1]) >= 3]
        print(f"\nch{s['chIndex']} guid={s['netguid']} bits={len(p)}")
        for pos, text, nbits in found:
            print(f"   pos={pos:>4} len={len(text):>3} bits={nbits:>4}  {text!r}")
        if found:
            hits[s["chIndex"]] = found
    if not hits:
        print("\n(no FString found -- names may be UCS2 or the block is not what we think)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
