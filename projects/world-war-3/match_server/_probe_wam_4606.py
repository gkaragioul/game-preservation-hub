#!/usr/bin/env python3
"""Probe where SoftClass 4606 / WAM catalog can still arm after open strip."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cam_im_resend import (
    WAM_PRIMARY,
    WAM_SECONDARY,
    extract_wam_payloads,
    parse_weapon_open_content_blocks,
    rewrite_weapon_final_strip_wam,
    STREAM,
)

TARGET = 4606


def bits_to_bytes(bits):
    out = bytearray((len(bits) + 7) // 8)
    for i, b in enumerate(bits):
        if b:
            out[i >> 3] |= 1 << (i & 7)
    return bytes(out)


def scan_uint16_in_bits(bits, value):
    """Naive: find 16-bit LE uint16 appearances aligned to bit positions."""
    hits = []
    if len(bits) < 16:
        return hits
    for pos in range(0, len(bits) - 15):
        v = 0
        for i in range(16):
            v |= bits[pos + i] << i
        if v == value:
            hits.append(pos)
    return hits


def main():
    stream = json.loads(STREAM.read_text(encoding="utf-8"))
    print("=== weapon open content blocks ===")
    for label, srcs in [("sec 257-258", (257, 258)), ("pri 259-260", (259, 260))]:
        blocks = parse_weapon_open_content_blocks(srcs)
        print(f"{label}:")
        for b in blocks:
            print(
                f"  sub={b['subNetGUID']} stably={b['stablyNamed']} "
                f"cls={b['classNetGUID']} hasRep={b['hasRepLayout']} "
                f"bits={b['payloadBits']}"
            )

    print("\n=== 4606 in capture src payloads (uint16 bit-scan) ===")
    for i, bunch in enumerate(stream):
        bits = [int(c) for c in bunch["payload"]]
        hits = scan_uint16_in_bits(bits, TARGET)
        if hits:
            ch = bunch.get("ch")
            tag = bunch.get("tag", "")
            print(f"  src={i} ch={ch} hits={len(hits)} first_pos={hits[0]} tag={tag[:80]!r}")

    print("\n=== after open strip, 4606 still in FINAL? ===")
    for src, ng in [(258, WAM_SECONDARY), (260, WAM_PRIMARY)]:
        raw = [int(c) for c in stream[src]["payload"]]
        stripped = rewrite_weapon_final_strip_wam(raw, ng, batch_id=1)
        hits_before = scan_uint16_in_bits(raw, TARGET)
        hits_after = scan_uint16_in_bits(stripped, TARGET)
        print(
            f"  src={src} ng={ng}: before={len(hits_before)} after={len(hits_after)} "
            f"bits {len(raw)}->{len(stripped)}"
        )

    # Also check if INIT-only or other ch86/87 bunches contain 4606
    print("\n=== ch86/87 bunches with 4606 (excl already listed) ===")
    for i, bunch in enumerate(stream):
        if bunch.get("ch") not in (86, 87):
            continue
        bits = [int(c) for c in bunch["payload"]]
        hits = scan_uint16_in_bits(bits, TARGET)
        if hits:
            print(
                f"  src={i} ch={bunch.get('ch')} nbits={len(bits)} "
                f"hits={len(hits)} open={bunch.get('bOpen')} "
                f"reliable={bunch.get('bReliable')}"
            )


if __name__ == "__main__":
    main()
