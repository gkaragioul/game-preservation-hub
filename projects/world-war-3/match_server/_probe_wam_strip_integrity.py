#!/usr/bin/env python3
"""Verify ch4/ch5 FINAL still exact-walks after in-place WAM strip."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from actor_channel import read_new_actor
from cam_im_resend import (
    STREAM,
    WAM_OPEN_FINAL_SRCS,
    _find_wam_block_header,
    _walk_content_blocks,
    rewrite_weapon_final_strip_wam,
)
from netguid import GuidReader, PackageMap
from repblock import read_packed


def loose_walk(bits, pos):
    blocks = []
    p = pos
    while p + 3 <= len(bits):
        start = p
        has_rep, is_actor = bits[p], bits[p + 1]
        p += 2
        sub = stably = cls = None
        if not is_actor:
            sub, sw = read_packed(bits, p)
            if sub is None:
                return blocks, p, "sub fail"
            p += sw
            if p >= len(bits):
                return blocks, p, "eof stably"
            stably = bits[p]
            p += 1
            if stably == 0:
                cls, cw = read_packed(bits, p)
                if cls is None:
                    return blocks, p, "cls fail"
                p += cw
        nbits, nw = read_packed(bits, p)
        if nbits is None or p + nw + nbits > len(bits):
            return blocks, start, f"nbits OOB nbits={nbits}"
        p += nw + nbits
        blocks.append((sub, stably, cls, has_rep, nbits))
    return blocks, p, ("ok" if p == len(bits) else f"left {len(bits)-p}")


def main():
    stream = json.loads(STREAM.read_text(encoding="utf-8"))
    for src, ng in WAM_OPEN_FINAL_SRCS.items():
        raw = [int(c) for c in stream[src]["payload"]]
        out = rewrite_weapon_final_strip_wam(raw, ng, batch_id=1)
        hdr = _find_wam_block_header(out, ng)
        print(f"\nsrc={src} ng={ng} {len(raw)}->{len(out)} wam_nbits={hdr['nbits']}")
        # Try content walk from NA and NA+3
        gr = GuidReader(out, 0)
        info = read_new_actor(gr, PackageMap())
        for delta in (0, 1, 2, 3, 4, 5):
            blocks, end, why = loose_walk(out, gr.pos + delta)
            wam_ok = any(b[0] == ng for b in blocks)
            dyn = [b for b in blocks if b[1] == 0 and b[0]]
            if why == "ok" or wam_ok:
                print(f"  delta={delta}: blocks={len(blocks)} why={why} "
                      f"wam={wam_ok} dyn={[(b[0], b[2]) for b in dyn]}")
                if why == "ok":
                    break


if __name__ == "__main__":
    main()
