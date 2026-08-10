#!/usr/bin/env python3
"""Find stably=0 dynamic subs in weapon opens (candidates for ReplicatedAttachments)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from actor_channel import read_new_actor
from cam_im_resend import STREAM, _walk_content_blocks, _find_wam_block_header
from netguid import GuidReader, PackageMap


def walk_from(bits, pos):
    for off in range(pos, min(pos + 16, len(bits))):
        try:
            return off, _walk_content_blocks(bits, off)
        except Exception:
            continue
    return None, []


def main():
    stream = json.loads(STREAM.read_text(encoding="utf-8"))
    for label, srcs in [
        ("ch4", (14, 15)),
        ("ch5", (16, 17)),
        ("ch86", (257, 258)),
        ("ch87", (259, 260)),
    ]:
        bits = []
        for i in srcs:
            bits.extend(int(c) for c in stream[i]["payload"])
        pm = PackageMap()
        pos = pm.read_export_bunch(bits)["reader"].pos
        gr = GuidReader(bits, pos)
        info = read_new_actor(gr, pm)
        off, blocks = walk_from(bits, gr.pos)
        print(f"\n{label} actor={info.get('netguid')} content@{off}")
        for bl in blocks:
            if bl["stablyNamed"] == 0 or (bl["payloadBits"] and bl["payloadBits"] >= 40):
                print(
                    f"  sub={bl['subNetGUID']} stably={bl['stablyNamed']} "
                    f"cls={bl['classNetGUID']} hasRep={bl['hasRepLayout']} "
                    f"bits={bl['payloadBits']}"
                )


if __name__ == "__main__":
    main()
