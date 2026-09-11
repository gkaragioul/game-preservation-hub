#!/usr/bin/env python3
"""Decode hat stably=0 payload bit layout."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from cam_im_resend import parse_clothing_content_blocks  # noqa: E402
from actor_channel import write_rep_properties  # noqa: E402
from cam_im_resend import _bits_u  # noqa: E402

blocks = parse_clothing_content_blocks()
for sub in (9404, 9406):
    b = next(x for x in blocks if x["subNetGUID"] == sub)
    pl = b["payload"]
    by = bytearray((len(pl) + 7) // 8)
    for i, bit in enumerate(pl):
        if bit:
            by[i >> 3] |= 1 << (i & 7)
    print(f"sub={sub} nbits={len(pl)} hex={by.hex()}")

# Candidate minimal payloads
for label, props in [
    ("batch1", [(1, _bits_u(1, 32))]),
    ("batch1_health100", [(1, _bits_u(1, 32)), (2, _bits_u(100, 32))]),
    ("batch2_health100", [(1, _bits_u(2, 32)), (2, _bits_u(100, 32))]),
]:
    bits = write_rep_properties(props)
    by = bytearray((len(bits) + 7) // 8)
    for i, bit in enumerate(bits):
        if bit:
            by[i >> 3] |= 1 << (i & 7)
    print(f"synth {label}: nbits={len(bits)} hex={by.hex()}")
    if bits == blocks[1]["payload"] or bits == blocks[2]["payload"]:
        print("  MATCH hat/chest")
