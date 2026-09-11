#!/usr/bin/env python3
"""Locate stably=0 keep attachments relative to early ch4/ch5 WAM headers."""
from __future__ import annotations

import json
from pathlib import Path

from cam_im_resend import _find_wam_block_header
from netguid import PackageMap
from repblock import read_packed

HERE = Path(__file__).resolve().parent
stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))


def scan_blocks_from(bits: list[int], start: int) -> list[dict]:
    """Best-effort content walk that tolerates leftover bits."""
    blocks = []
    p = start
    n = len(bits)
    while p + 3 <= n:
        has_rep = bits[p]
        is_actor = bits[p + 1]
        p0 = p
        p += 2
        sub = stably = cls = None
        if not is_actor:
            sub, sw = read_packed(bits, p)
            if sub is None:
                break
            p += sw
            if p >= n:
                break
            stably = bits[p]
            p += 1
            if stably == 0:
                cls, cw = read_packed(bits, p)
                if cls is None:
                    break
                p += cw
        nbits, nw = read_packed(bits, p)
        if nbits is None or p + nw + nbits > n:
            break
        p += nw
        payload = bits[p : p + nbits]
        p += nbits
        blocks.append({
            "hdr": p0,
            "sub": sub,
            "stably": stably,
            "cls": cls,
            "nbits": nbits,
            "has_rep": has_rep,
            "is_actor": is_actor,
            "end": p,
        })
        if len(blocks) > 20:
            break
    return blocks, p


def main() -> None:
    for label, srcs, wam, claimed_keep in [
        ("ch4", (14, 15), 8314, 8312),
        ("ch5", (16, 17), 7956, 7954),
        ("ch86", (257, 258), 9418, 9416),
        ("ch87", (259, 260), 9426, 9424),
    ]:
        bits = []
        for i in srcs:
            bits.extend(int(c) for c in stream[i]["payload"])
        hdr = _find_wam_block_header(bits, wam)
        print(f"\n=== {label} wam={wam} claimed_keep={claimed_keep} total={len(bits)}")
        print(f"  WAM hdr={hdr}")
        if not hdr:
            continue
        # Walk forward from WAM header through following blocks
        blocks, end = scan_blocks_from(bits, hdr["hdr"])
        print(f"  from WAM hdr: {len(blocks)} blocks, end={end}/{len(bits)}")
        for b in blocks[:8]:
            mark = ""
            if b["sub"] == wam:
                mark = " <<WAM"
            if b["sub"] == claimed_keep:
                mark = " <<CLAIMED_KEEP"
            print(
                f"    sub={b['sub']} stably={b['stably']} cls={b['cls']} "
                f"bits={b['nbits']} hasRep={b['has_rep']}{mark}"
            )
        # Also search FINAL-only
        final = [int(c) for c in stream[srcs[1]]["payload"]]
        fhdr = _find_wam_block_header(final, wam)
        print(f"  FINAL-only WAM hdr={fhdr}")
        if fhdr:
            fblocks, _ = scan_blocks_from(final, fhdr["hdr"])
            for b in fblocks[:6]:
                mark = ""
                if b["sub"] == wam:
                    mark = " <<WAM"
                if b["sub"] == claimed_keep:
                    mark = " <<CLAIMED_KEEP"
                print(
                    f"    F sub={b['sub']} stably={b['stably']} cls={b['cls']} "
                    f"bits={b['nbits']}{mark}"
                )


if __name__ == "__main__":
    main()
