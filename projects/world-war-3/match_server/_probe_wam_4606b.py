#!/usr/bin/env python3
"""Which ownership/bootstrap bunches still carry catalog id 4606?"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cam_im_resend import STREAM

TARGET = 4606


def scan_uint16_in_bits(bits, value):
    hits = []
    for pos in range(0, max(0, len(bits) - 15)):
        v = 0
        for i in range(16):
            v |= bits[pos + i] << i
        if v == value:
            hits.append(pos)
    return hits


def main():
    stream = json.loads(STREAM.read_text(encoding="utf-8"))
    # Ownership bootstrap src indices
    from build_ownership_bootstrap import write_bootstrap

    os.environ.setdefault("WW3_BOOTSTRAP", "ownership")
    os.environ.setdefault("WW3_INV_ATTACH", "1")
    # write_bootstrap returns path; load ownership_bootstrap.json instead
    boot_path = Path(__file__).resolve().parent / "ownership_bootstrap.json"
    if not boot_path.exists():
        write_bootstrap("ownership")
    specs = json.loads(boot_path.read_text(encoding="utf-8"))
    srcs = []
    for s in specs:
        si = s.get("_src_idx")
        if si is not None:
            srcs.append(int(si))
    print(f"ownership bootstrap bunches: {len(specs)}, with _src_idx: {len(srcs)}")
    print(f"src range: {min(srcs) if srcs else None}..{max(srcs) if srcs else None}")
    boot_set = set(srcs)

    hits_in_boot = []
    for si in sorted(boot_set):
        bits = [int(c) for c in stream[si]["payload"]]
        hits = scan_uint16_in_bits(bits, TARGET)
        if hits:
            hits_in_boot.append((si, len(hits), hits[0], len(bits)))
    print(f"\n=== 4606 inside ownership bootstrap srcs ({len(hits_in_boot)}) ===")
    for si, n, pos, nbits in hits_in_boot:
        b = stream[si]
        print(
            f"  src={si} hits={n} first_pos={pos} nbits={nbits} "
            f"chIndex={b.get('chIndex')} bOpen={b.get('bOpen')} "
            f"partial={b.get('bPartial')} tag={str(b.get('tag',''))[:60]!r}"
        )

    print("\n=== early stream srcs <300 with 4606 ===")
    for i in range(min(300, len(stream))):
        bits = [int(c) for c in stream[i]["payload"]]
        hits = scan_uint16_in_bits(bits, TARGET)
        if hits:
            in_boot = "BOOT" if i in boot_set else "not-boot"
            b = stream[i]
            print(
                f"  src={i} [{in_boot}] hits={len(hits)} nbits={len(bits)} "
                f"ch={b.get('chIndex')} open={b.get('bOpen')} "
                f"tag={str(b.get('tag',''))[:70]!r}"
            )


if __name__ == "__main__":
    main()
