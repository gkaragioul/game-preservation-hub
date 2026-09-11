#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from actor_channel import Bits, read_content_blocks, read_new_actor
from netguid import GuidReader, PackageMap
from _decode_rep_block import decode, layout
import derive_rep_handles as D
from repblock import read_u, read_packed

stream = json.loads(Path("real_replay_stream.json").read_text(encoding="utf-8"))
sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
classes, structs = D.parse_sdk(sdk)
enums = D.parse_enums(sdk)
bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)

for label, srcs in [("ch4", (14, 15)), ("ch5", (16, 17))]:
    bits: list[int] = []
    for i in srcs:
        bits.extend(int(c) for c in stream[i]["payload"])
    pm = PackageMap()
    pos = pm.read_export_bunch(bits)["reader"].pos
    gr = GuidReader(bits, pos)
    info = read_new_actor(gr, pm)
    print(label, "actor", info.get("netguid"), "NA", gr.pos, "scale", info.get("has_scale"))
    try:
        bl = read_content_blocks(Bits(bits, gr.pos), total_bits=len(bits))
        print(" blocks", len(bl))
        for b in bl:
            extra = ""
            if b.get("payloadBits", 0) >= 200 and b.get("hasRepLayout"):
                r = decode(b["payload"], bh, ty, enums=enums)
                names = [x[1] for x in r.get("seq", [])]
                if r.get("closed") and any("AttachmentIds" in n for n in names):
                    by = {x[1]: x for x in r["seq"]}
                    p = by["ReplicatedBatch.AttachmentIds[]"][5]
                    n = read_u(b["payload"], p, 16)
                    p2 = p + 16
                    ids = []
                    for _ in range(n):
                        _idx, iw = read_packed(b["payload"], p2)
                        p2 += iw
                        ids.append(read_u(b["payload"], p2, 16))
                        p2 += 16
                    extra = f" WAM ids={ids}"
            print(
                f"  sub={b.get('subNetGUID')} stably={b.get('stablyNamed')} "
                f"cls={b.get('classNetGUID')} hasRep={b.get('hasRepLayout')} "
                f"bits={b.get('payloadBits')} bad={b.get('bad')}{extra}"
            )
    except Exception as e:
        print(" FAIL", type(e).__name__, e)

    # FINAL-only with read_content_blocks
    final = [int(c) for c in stream[srcs[1]]["payload"]]
    gr2 = GuidReader(final, 0)
    info2 = read_new_actor(gr2, PackageMap())
    print(" FINAL NA", gr2.pos, "incomplete", info2.get("incomplete"))
    try:
        bl2 = read_content_blocks(Bits(final, gr2.pos), total_bits=len(final))
        print(" FINAL blocks", len(bl2))
        for b in bl2:
            if b.get("payloadBits", 0) >= 200 and b.get("hasRepLayout"):
                r = decode(b["payload"], bh, ty, enums=enums)
                if r.get("closed"):
                    by = {x[1]: x for x in r["seq"]}
                    if "ReplicatedBatch.AttachmentIds[]" in by:
                        p = by["ReplicatedBatch.AttachmentIds[]"][5]
                        n = read_u(b["payload"], p, 16)
                        print(f"  FINAL WAM sub={b.get('subNetGUID')} idsN={n} bits={b.get('payloadBits')}")
    except Exception as e:
        print(" FINAL FAIL", type(e).__name__, e)
