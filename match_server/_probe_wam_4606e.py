#!/usr/bin/env python3
"""Locate WAM catalog (4606) inside ch4/ch5 FINALs without requiring exact walk."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from actor_channel import read_new_actor, write_rep_properties
from cam_im_resend import (
    STREAM,
    _walk_content_blocks,
    extract_wam_payloads,
    WAM_SECONDARY,
    build_wam_stripped_catalog_payload,
    rewrite_weapon_final_strip_wam,
)
from netguid import GuidReader, PackageMap, GuidWriter
from _decode_rep_block import decode, layout
import derive_rep_handles as D
from repblock import read_u, read_packed

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


def walk_loose(bits, pos=0):
    """Like _walk_content_blocks but stop on failure; return blocks + end pos."""
    blocks = []
    p = pos
    while p + 3 <= len(bits):
        start = p
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
            return blocks, start, "nbits OOB"
        p += nw
        payload = bits[p : p + nbits]
        p += nbits
        blocks.append({
            "hasRepLayout": has_rep,
            "isActor": bool(is_actor),
            "subNetGUID": sub,
            "stablyNamed": stably,
            "classNetGUID": cls,
            "payloadBits": nbits,
            "payload": payload,
            "start": start,
        })
    return blocks, p, "ok" if p == len(bits) else f"left {len(bits)-p}"


def main():
    stream = json.loads(STREAM.read_text(encoding="utf-8"))
    sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)
    bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)

    sec_payload = extract_wam_payloads()[WAM_SECONDARY]
    print(f"reference secondary WAM payload bits={len(sec_payload)}")
    # find 4606 offset in reference
    print(f"  4606 hits in ref: {scan_uint16(sec_payload, TARGET)}")

    for label, srcs in [("ch4 14+15", (14, 15)), ("ch5 16+17", (16, 17))]:
        bits = []
        for i in srcs:
            bits.extend(int(c) for c in stream[i]["payload"])
        print(f"\n=== {label} bits={len(bits)} ===")
        # Find raw 4606
        hits = scan_uint16(bits, TARGET)
        print(f"  raw 4606 hits: {hits}")

        # Find secondary WAM payload as substring
        found = False
        for i in range(0, len(bits) - len(sec_payload) + 1):
            if bits[i : i + len(sec_payload)] == sec_payload:
                print(f"  EXACT secondary WAM payload at bit {i}")
                found = True
                break
        if not found:
            # try FINAL-only
            final = [int(c) for c in stream[srcs[1]]["payload"]]
            for i in range(0, len(final) - len(sec_payload) + 1):
                if final[i : i + len(sec_payload)] == sec_payload:
                    print(f"  EXACT secondary WAM in FINAL-only at bit {i}")
                    found = True
                    break
        if not found:
            print("  no exact secondary WAM payload match")

        pm = PackageMap()
        pos = pm.read_export_bunch(bits)["reader"].pos
        gr = GuidReader(bits, pos)
        info = read_new_actor(gr, pm)
        print(f"  NA incomplete={info.get('incomplete')} arch={info.get('archetype')} "
              f"pos={gr.pos}")
        blocks, end, why = walk_loose(bits, gr.pos)
        print(f"  loose walk: {len(blocks)} blocks end={end} why={why}")
        for bl in blocks:
            hits_p = scan_uint16(bl["payload"], TARGET)
            extra = ""
            if bl["payloadBits"] >= 400 or hits_p:
                try:
                    r = decode(bl["payload"], bh, ty, enums=enums)
                    by = {x[1]: x for x in r["seq"]}
                    if "ReplicatedBatch.AttachmentIds[]" in by:
                        p = by["ReplicatedBatch.AttachmentIds[]"][5]
                        n = read_u(bl["payload"], p, 16)
                        extra = f" WAM idsN={n} closed={r['closed']} left={r['left']}"
                except Exception as e:
                    extra = f" err={e}"
            if hits_p:
                extra += f" ***4606***"
            print(
                f"    @{bl['start']}: sub={bl['subNetGUID']} stably={bl['stablyNamed']} "
                f"cls={bl['classNetGUID']} hasRep={bl['hasRepLayout']} "
                f"bits={bl['payloadBits']}{extra}"
            )

    # FINAL-only loose walk from NewActor
    for src in (15, 17):
        bits = [int(c) for c in stream[src]["payload"]]
        print(f"\n=== FINAL-only src={src} ===")
        hits = scan_uint16(bits, TARGET)
        print(f"  4606 @ {hits}")
        pm = PackageMap()
        gr = GuidReader(bits, 0)
        info = read_new_actor(gr, pm)
        print(f"  NA incomplete={info.get('incomplete')} arch={info.get('archetype')} pos={gr.pos}")
        blocks, end, why = walk_loose(bits, gr.pos)
        print(f"  loose: {len(blocks)} blocks end={end} {why}")
        for bl in blocks:
            hits_p = scan_uint16(bl["payload"], TARGET)
            extra = ""
            if hits_p or bl["payloadBits"] >= 400:
                try:
                    r = decode(bl["payload"], bh, ty, enums=enums)
                    by = {x[1]: x for x in r["seq"]}
                    if "ReplicatedBatch.AttachmentIds[]" in by:
                        p = by["ReplicatedBatch.AttachmentIds[]"][5]
                        extra = f" WAM idsN={read_u(bl['payload'], p, 16)} closed={r['closed']}"
                except Exception as e:
                    extra = f" {e}"
            print(
                f"    sub={bl['subNetGUID']} bits={bl['payloadBits']} "
                f"stably={bl['stablyNamed']}{extra}{' ***4606***' if hits_p else ''}"
            )


if __name__ == "__main__":
    main()
