#!/usr/bin/env python3
"""Confirm ch4/ch5 WAM NetGUIDs + AttachmentIds (4606), and test FINAL rewrite."""
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
from repblock import read_u


def try_walk(bits, pos):
    try:
        return _walk_content_blocks(bits, pos), pos
    except Exception:
        return None, pos


def find_wam_blocks(bits, na_pos, bh, ty, enums):
    """Search a few offsets after NA for a walk that yields a closed WAM payload."""
    for off in range(na_pos, min(na_pos + 32, len(bits))):
        blocks, _ = try_walk(bits, off)
        if not blocks:
            continue
        wams = []
        for bl in blocks:
            if not bl["hasRepLayout"] or bl["payloadBits"] < 200:
                continue
            r = decode(bl["payload"], bh, ty, enums=enums)
            if not (r.get("closed") and r.get("left") == 0):
                continue
            by = {x[1]: x for x in r["seq"]}
            if "ReplicatedBatch.AttachmentIds[]" not in by:
                continue
            p = by["ReplicatedBatch.AttachmentIds[]"][5]
            n = read_u(bl["payload"], p, 16)
            # collect ids
            ids = []
            # use decode seq raw if available - else just N
            main = None
            if "DirectReplicatedSkinsIds.MainId" in by:
                main = read_u(bl["payload"], by["DirectReplicatedSkinsIds.MainId"][5], 16)
            wams.append({
                "off": off,
                "sub": bl["subNetGUID"],
                "bits": bl["payloadBits"],
                "idsN": n,
                "main": main,
                "payload": bl["payload"],
                "blocks": blocks,
                "seq": [x[1] for x in r["seq"]],
            })
        if wams:
            return off, blocks, wams
    return None, None, []


def rewrite_final_strip_at(bits, wam_netguid, content_start, batch_id=1):
    """Rewrite WAM in a FINAL that starts at content_start (after NewActor)."""
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
            int(bl["subNetGUID"]),
            stably_named=1 if bl["stablyNamed"] else 0,
            has_rep_layout=int(bl["hasRepLayout"]),
            payload_bits_list=payload,
            class_netguid=bl["classNetGUID"],
        )
    if not found:
        raise RuntimeError(f"WAM {wam_netguid} not found")
    return _bits_from_writer(w)


def main():
    stream = json.loads(STREAM.read_text(encoding="utf-8"))
    sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)
    bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)

    for label, srcs in [("ch4", (14, 15)), ("ch5", (16, 17))]:
        bits = []
        for i in srcs:
            bits.extend(int(c) for c in stream[i]["payload"])
        pm = PackageMap()
        pos = pm.read_export_bunch(bits)["reader"].pos
        gr = GuidReader(bits, pos)
        info = read_new_actor(gr, pm)
        print(f"\n=== {label} actor={info.get('netguid')} arch={info.get('archetypePath')} ===")
        off, blocks, wams = find_wam_blocks(bits, gr.pos, bh, ty, enums)
        print(f"  content_off={off} nblocks={len(blocks) if blocks else 0} wams={len(wams)}")
        for w in wams:
            # extract ids by scanning uint16s that match known secondary set? decode array
            from cam_im_resend import CAPTURE_WAM_SECONDARY_ATTACHMENT_IDS, CAPTURE_WAM_PRIMARY_ATTACHMENT_IDS
            pl = w["payload"]
            # read array manually from AttachmentIds pos
            r = decode(pl, bh, ty, enums=enums)
            by = {x[1]: x for x in r["seq"]}
            p = by["ReplicatedBatch.AttachmentIds[]"][5]
            n = read_u(pl, p, 16)
            # after ArrayNum, packed idx + uint16 value
            from repblock import read_packed
            p2 = p + 16
            ids = []
            for _ in range(n):
                idx, iw = read_packed(pl, p2)
                p2 += iw
                ids.append(read_u(pl, p2, 16))
                p2 += 16
            print(
                f"  WAM sub={w['sub']} bits={w['bits']} MainId={w['main']} "
                f"ids({n})={ids} has4606={4606 in ids}"
            )
            # Compare to capture catalogs
            if tuple(ids) == CAPTURE_WAM_SECONDARY_ATTACHMENT_IDS:
                print("    == CAPTURE secondary catalog")
            if tuple(ids) == CAPTURE_WAM_PRIMARY_ATTACHMENT_IDS:
                print("    == CAPTURE primary catalog")

        # Can we strip FINAL-only like ch86?
        # For ch86, FINAL alone has NewActor+content. For ch4/ch5, FINAL alone may not.
        final = [int(c) for c in stream[srcs[1]]["payload"]]
        pm2 = PackageMap()
        gr2 = GuidReader(final, 0)
        info2 = read_new_actor(gr2, pm2)
        print(f"  FINAL-only NA incomplete={info2.get('incomplete')} pos={gr2.pos}")
        off2, blocks2, wams2 = find_wam_blocks(final, gr2.pos, bh, ty, enums)
        print(f"  FINAL-only content_off={off2} wams={[(w['sub'], w['bits']) for w in wams2]}")

        # Try strip on combined open using content off
        if wams and off is not None:
            ng = wams[0]["sub"]
            try:
                # rewrite on full bits from content start — but send path only has FINAL
                # Check whether WAM payload sits entirely in FINAL (like ch86)
                init_len = len(stream[srcs[0]]["payload"])
                # find WAM payload start in combined
                pl = wams[0]["payload"]
                # locate in combined
                start = None
                for i in range(len(bits) - len(pl) + 1):
                    if bits[i : i + len(pl)] == pl:
                        start = i
                        break
                print(f"  WAM payload abs_start={start} init_len={init_len} "
                      f"in_FINAL={start is not None and start >= init_len}")
            except Exception as e:
                print(f"  strip probe err: {e}")


if __name__ == "__main__":
    main()
