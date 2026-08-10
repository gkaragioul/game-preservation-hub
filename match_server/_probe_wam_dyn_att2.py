#!/usr/bin/env python3
"""Find post-WAM dynamic sub NetGUID in each FINAL (in-place header scan)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cam_im_resend import STREAM, _find_wam_block_header, WAM_OPEN_FINAL_SRCS
from repblock import read_packed


def scan_blocks_after(bits, start):
    p = start
    out = []
    while p + 3 <= len(bits):
        hdr = p
        has_rep = bits[p]
        is_actor = bits[p + 1]
        p += 2
        sub = stably = cls = None
        if not is_actor:
            sub, sw = read_packed(bits, p)
            if sub is None:
                break
            p += sw
            if p >= len(bits):
                break
            stably = bits[p]
            p += 1
            if stably == 0:
                cls, cw = read_packed(bits, p)
                if cls is None:
                    break
                p += cw
        nbits, nw = read_packed(bits, p)
        if nbits is None or p + nw + nbits > len(bits):
            break
        p += nw + nbits
        out.append({"hdr": hdr, "sub": sub, "stably": stably, "cls": cls,
                    "hasRep": has_rep, "isActor": is_actor, "nbits": nbits})
    return out


def main():
    stream = json.loads(STREAM.read_text(encoding="utf-8"))
    for src, ng in WAM_OPEN_FINAL_SRCS.items():
        bits = [int(c) for c in stream[src]["payload"]]
        hdr = _find_wam_block_header(bits, ng)
        print(f"\nsrc={src} WAM={ng} hdr={hdr and hdr['hdr']}")
        if not hdr:
            continue
        blocks = scan_blocks_after(bits, hdr["hdr"])
        for b in blocks:
            print(
                f"  @{b['hdr']}: sub={b['sub']} stably={b['stably']} cls={b['cls']} "
                f"hasRep={b['hasRep']} isActor={b['isActor']} nbits={b['nbits']}"
            )


if __name__ == "__main__":
    main()
