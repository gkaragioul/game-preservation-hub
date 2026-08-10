#!/usr/bin/env python3
"""Dump post-NewActor bit headers in ch4/ch5 FINALs; find WAM-like decode windows."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from actor_channel import read_new_actor
from cam_im_resend import STREAM, extract_wam_payloads, WAM_SECONDARY, CAPTURE_WAM_SECONDARY_ATTACHMENT_IDS
from netguid import GuidReader, PackageMap
from _decode_rep_block import decode, layout
import derive_rep_handles as D
from repblock import read_u, read_packed

TARGET = 4606


def scan_uint16(bits, value):
    return [
        pos
        for pos in range(0, max(0, len(bits) - 15))
        if sum(bits[pos + i] << i for i in range(16)) == value
    ]


def main():
    stream = json.loads(STREAM.read_text(encoding="utf-8"))
    sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)
    bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)

    # Secondary AttachmentIds bit pattern after ArrayNum=9
    # Build expected first few ids as uint16 LE after ArrayNum
    from cam_im_resend import _bits_uint16_array
    ids_bits = _bits_uint16_array(CAPTURE_WAM_SECONDARY_ATTACHMENT_IDS)
    print(f"secondary AttachmentIds wire bits len={len(ids_bits)}")
    # Find this pattern in src 15/17
    for src in (15, 17, 258):
        bits = [int(c) for c in stream[src]["payload"]]
        hits = []
        for i in range(0, len(bits) - len(ids_bits) + 1):
            if bits[i : i + len(ids_bits)] == ids_bits:
                hits.append(i)
        print(f"src={src}: AttachmentIds pattern hits={hits}; 4606@{scan_uint16(bits, TARGET)}")

    for src in (15, 17):
        bits = [int(c) for c in stream[src]["payload"]]
        pm = PackageMap()
        gr = GuidReader(bits, 0)
        info = read_new_actor(gr, pm)
        pos = gr.pos
        print(f"\n=== src={src} NA pos={pos} arch={info.get('archetype')} ===")
        # dump first 64 bits as groups
        head = bits[pos : pos + 80]
        print(f"  head bits: {''.join(str(b) for b in head)}")
        # try interpret as content header
        p = pos
        has_rep, is_actor = bits[p], bits[p + 1]
        p += 2
        print(f"  hasRep={has_rep} isActor={is_actor}")
        if not is_actor:
            sub, sw = read_packed(bits, p)
            p += sw
            stably = bits[p]
            p += 1
            print(f"  sub={sub} stably={stably}")
            if stably == 0:
                cls, cw = read_packed(bits, p)
                p += cw
                print(f"  cls={cls}")
        nbits, nw = read_packed(bits, p)
        print(f"  nbits={nbits} nw={nw} remain={len(bits)-p-nw}")

        # Sliding-window: try decode WAM at every 4606 hit minus 193 (ref offset)
        ref_off = 193
        for h in scan_uint16(bits, TARGET):
            start = h - ref_off
            if start < 0:
                continue
            # try payload lengths around 505
            for plen in (505, 457, 500, 510, 520, 480, 530, 600, 700, 800):
                if start + plen > len(bits):
                    continue
                payload = bits[start : start + plen]
                r = decode(payload, bh, ty, enums=enums)
                if r.get("closed") and r.get("left") == 0:
                    by = {x[1]: x for x in r["seq"]}
                    if "ReplicatedBatch.AttachmentIds[]" in by:
                        p0 = by["ReplicatedBatch.AttachmentIds[]"][5]
                        n = read_u(payload, p0, 16)
                        print(
                            f"  WAM EXACT at bit {start} plen={plen} idsN={n} "
                            f"handles={list(by)[:6]}"
                        )
                        break
            else:
                # best near-close
                best = None
                for plen in range(200, 900):
                    if start + plen > len(bits):
                        break
                    payload = bits[start : start + plen]
                    r = decode(payload, bh, ty, enums=enums)
                    if r.get("closed") and r.get("left", 99) == 0 and any(
                        "AttachmentIds" in x[1] for x in r["seq"]
                    ):
                        best = (plen, r)
                        break
                if best:
                    print(f"  WAM near at {start} plen={best[0]}")
                else:
                    print(f"  no WAM close at 4606@{h} start={start}")


if __name__ == "__main__":
    main()
