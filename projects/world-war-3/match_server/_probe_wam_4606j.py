#!/usr/bin/env python3
"""Find ch4 WAM via offset search; verify FINAL-only strip feasibility for ch4/ch5."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from actor_channel import read_new_actor, write_subobject_content_block
from cam_im_resend import (
    STREAM,
    _walk_content_blocks,
    _bits_from_writer,
    build_wam_stripped_catalog_payload,
)
from netguid import GuidReader, GuidWriter, PackageMap
from _decode_rep_block import decode, layout
import derive_rep_handles as D
from repblock import read_u, read_packed


def find_exact_content_start(bits, na_pos, max_delta=64):
    for off in range(max(0, na_pos - 8), min(len(bits), na_pos + max_delta)):
        try:
            blocks = _walk_content_blocks(bits, off)
            return off, blocks
        except Exception:
            continue
    return None, None


def decode_ids(payload, bh, ty, enums):
    r = decode(payload, bh, ty, enums=enums)
    if not (r.get("closed") and r.get("left") == 0):
        return None
    by = {x[1]: x for x in r["seq"]}
    if "ReplicatedBatch.AttachmentIds[]" not in by:
        return None
    p = by["ReplicatedBatch.AttachmentIds[]"][5]
    n = read_u(payload, p, 16)
    p2 = p + 16
    ids = []
    for _ in range(n):
        _idx, iw = read_packed(payload, p2)
        p2 += iw
        ids.append(read_u(payload, p2, 16))
        p2 += 16
    main = None
    if "DirectReplicatedSkinsIds.MainId" in by:
        main = read_u(payload, by["DirectReplicatedSkinsIds.MainId"][5], 16)
    return {"ids": ids, "main": main, "seq": [x[1] for x in r["seq"]]}


def rewrite_from(bits, content_start, wam_netguid, batch_id=1):
    blocks = _walk_content_blocks(bits, content_start)
    stripped = build_wam_stripped_catalog_payload(batch_id=batch_id)
    w = GuidWriter()
    for b in bits[:content_start]:
        w.write_bit(b)
    found = False
    for bl in blocks:
        payload = list(bl["payload"])
        if bl["subNetGUID"] == wam_netguid and bl["hasRepLayout"]:
            payload = stripped
            found = True
        write_subobject_content_block(
            w,
            int(bl["subNetGUID"]) if bl["subNetGUID"] is not None else 0,
            stably_named=1 if bl["stablyNamed"] else 0,
            has_rep_layout=int(bl["hasRepLayout"]),
            payload_bits_list=payload,
            class_netguid=bl["classNetGUID"],
        )
    if not found:
        raise RuntimeError("not found")
    out = _bits_from_writer(w)
    # verify
    blocks2 = _walk_content_blocks(out, content_start)
    return out, blocks2


def main():
    stream = json.loads(STREAM.read_text(encoding="utf-8"))
    sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)
    bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)

    for label, srcs, expect_ch in [("ch4", (14, 15), 4), ("ch5", (16, 17), 5)]:
        print(f"\n===== {label} =====")
        # combined
        bits = []
        for i in srcs:
            bits.extend(int(c) for c in stream[i]["payload"])
        pm = PackageMap()
        pos = pm.read_export_bunch(bits)["reader"].pos
        gr = GuidReader(bits, pos)
        info = read_new_actor(gr, pm)
        off, blocks = find_exact_content_start(bits, gr.pos)
        print(f"combined NA@{gr.pos} content@{off} actor={info.get('netguid')}")
        if blocks:
            for bl in blocks:
                if bl["payloadBits"] >= 200 and bl["hasRepLayout"]:
                    d = decode_ids(bl["payload"], bh, ty, enums)
                    if d:
                        print(
                            f"  WAM sub={bl['subNetGUID']} bits={bl['payloadBits']} "
                            f"main={d['main']} ids={d['ids']} has4606={4606 in d['ids']}"
                        )

        # FINAL-only (what server rewrites)
        final = [int(c) for c in stream[srcs[1]]["payload"]]
        gr2 = GuidReader(final, 0)
        info2 = read_new_actor(gr2, PackageMap())
        off2, blocks2 = find_exact_content_start(final, gr2.pos)
        print(f"FINAL src={srcs[1]} NA@{gr2.pos} content@{off2} delta={None if off2 is None else off2-gr2.pos}")
        wam_sub = None
        if blocks2:
            for bl in blocks2:
                if bl["payloadBits"] >= 200 and bl["hasRepLayout"]:
                    d = decode_ids(bl["payload"], bh, ty, enums)
                    if d:
                        wam_sub = bl["subNetGUID"]
                        print(
                            f"  FINAL WAM sub={wam_sub} bits={bl['payloadBits']} "
                            f"ids={d['ids']} has4606={4606 in d['ids']}"
                        )
        if wam_sub is not None and off2 is not None:
            out, blocks3 = rewrite_from(final, off2, wam_sub, batch_id=1)
            print(f"  strip rewrite {len(final)}->{len(out)} bits")
            for bl in blocks3:
                if bl["subNetGUID"] == wam_sub:
                    d = decode_ids(bl["payload"], bh, ty, enums)
                    print(f"  after strip WAM bits={bl['payloadBits']} ids={d}")


if __name__ == "__main__":
    main()
