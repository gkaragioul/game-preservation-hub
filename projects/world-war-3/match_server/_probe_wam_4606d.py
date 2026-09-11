#!/usr/bin/env python3
"""Decode ch4/ch5 weapon opens (src 14-17) — likely SoftClass 4606 arm source."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from actor_channel import read_new_actor
from cam_im_resend import STREAM, _walk_content_blocks
from netguid import GuidReader, PackageMap
from _decode_rep_block import decode, layout
import derive_rep_handles as D
from repblock import read_u

TARGET = 4606


def scan_uint16(bits, value):
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
    sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)
    bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)

    for label, srcs in [("ch4 14-15", (14, 15)), ("ch5 16-17", (16, 17)),
                        ("ch86 257-258", (257, 258)), ("ch87 259-260", (259, 260))]:
        bits = []
        for i in srcs:
            bits.extend(int(c) for c in stream[i]["payload"])
        print(f"\n=== {label} total_bits={len(bits)} ===")
        pm = PackageMap()
        pos = pm.read_export_bunch(bits)["reader"].pos
        gr = GuidReader(bits, pos)
        info = read_new_actor(gr, pm)
        print(f"  NewActor incomplete={info.get('incomplete')} "
              f"arch={info.get('archetype')} actor={info.get('actor')} "
              f"pos={gr.pos}")
        blocks = _walk_content_blocks(bits, gr.pos)
        for bl in blocks:
            mark = ""
            hits = scan_uint16(bl["payload"], TARGET)
            if hits or (bl["payloadBits"] > 400 and bl["hasRepLayout"]):
                try:
                    r = decode(bl["payload"], bh, ty, enums=enums)
                    by_name = {x[1]: x for x in r["seq"]}
                    if "ReplicatedBatch.AttachmentIds[]" in by_name:
                        p = by_name["ReplicatedBatch.AttachmentIds[]"][5]
                        n = read_u(bl["payload"], p, 16)
                        ids = []
                        # walk array roughly via decode seq values if present
                        mark = (
                            f" WAM closed={r['closed']} left={r['left']} "
                            f"AttachmentIds.N={n} has4606={bool(hits)}"
                        )
                        if "ReplicatedBatch.ReplicatedAttachments[]" in by_name:
                            mark += " +ReplicatedAttachments"
                        if "DirectReplicatedSkinsIds.MainId" in by_name:
                            mp = by_name["DirectReplicatedSkinsIds.MainId"][5]
                            mark += f" MainId={read_u(bl['payload'], mp, 16)}"
                    elif hits:
                        mark = f" has4606 but not WAM? closed={r.get('closed')}"
                except Exception as e:
                    mark = f" decode_err={e}" if hits else ""
            if hits:
                mark += f" ***4606@{hits[0]}***"
            print(
                f"  sub={bl['subNetGUID']} stably={bl['stablyNamed']} "
                f"cls={bl['classNetGUID']} hasRep={bl['hasRepLayout']} "
                f"bits={bl['payloadBits']}{mark}"
            )


if __name__ == "__main__":
    main()
