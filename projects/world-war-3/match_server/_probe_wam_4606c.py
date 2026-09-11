#!/usr/bin/env python3
"""Decode bootstrap bunches that still carry catalog id 4606 (src 15/17)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from actor_channel import read_new_actor
from cam_im_resend import STREAM, _walk_content_blocks, CAPTURE_WAM_SECONDARY_ATTACHMENT_IDS
from netguid import GuidReader, PackageMap
from _decode_rep_block import decode, layout
import derive_rep_handles as D
from repblock import read_u

TARGET = 4606


def scan_uint16_in_bits(bits, value):
    hits = []
    for pos in range(0, max(0, len(bits) - 15)):
        v = 0
        for i in range(16):
            v |= bits[pos + i] << i
        if v == value:
            hits.append(pos)
    return hits


def try_decode_wam(payload):
    sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)
    bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)
    r = decode(payload, bh, ty, enums=enums)
    return r


_SDK = None


def get_wam_layout():
    global _SDK
    if _SDK is None:
        sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
        classes, structs = D.parse_sdk(sdk)
        enums = D.parse_enums(sdk)
        bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)
        _SDK = (bh, ty, enums)
    return _SDK


def analyze_src(stream, src_idx):
    bits = [int(c) for c in stream[src_idx]["payload"]]
    b = stream[src_idx]
    print(f"\n=== src={src_idx} ch={b.get('chIndex')} bits={len(bits)} "
          f"open={b.get('bOpen')} partial={b.get('bPartial')} "
          f"exp={b.get('bHasPackageMapExports')} ===")

    for mode in ("export+na", "na-only", "content-only"):
        try:
            pm = PackageMap()
            pos = 0
            if mode == "export+na":
                pos = pm.read_export_bunch(bits)["reader"].pos
                gr = GuidReader(bits, pos)
                info = read_new_actor(gr, pm)
                pos = gr.pos
                print(f"  [{mode}] NewActor incomplete={info.get('incomplete')} "
                      f"arch={info.get('archetype')} pos={pos}")
            elif mode == "na-only":
                gr = GuidReader(bits, 0)
                info = read_new_actor(gr, pm)
                pos = gr.pos
                print(f"  [{mode}] NewActor incomplete={info.get('incomplete')} "
                      f"arch={info.get('archetype')} pos={pos}")
            blocks = _walk_content_blocks(bits, pos)
            print(f"  [{mode}] content blocks={len(blocks)} exact")
            bh, ty, enums = get_wam_layout()
            for bl in blocks:
                mark = ""
                hits = scan_uint16_in_bits(bl["payload"], TARGET)
                if hits:
                    mark = f" *** HAS 4606 @ {hits[0]} ***"
                    try:
                        r = decode(bl["payload"], bh, ty, enums=enums)
                        by_name = {x[1]: x for x in r["seq"]}
                        if "ReplicatedBatch.AttachmentIds[]" in by_name:
                            p = by_name["ReplicatedBatch.AttachmentIds[]"][5]
                            n = read_u(bl["payload"], p, 16)
                            mark += (
                                f" WAM closed={r.get('closed')} left={r.get('left')} "
                                f"AttachmentIds.ArrayNum={n}"
                            )
                        else:
                            mark += f" decode ok but no AttachmentIds closed={r.get('closed')}"
                    except Exception as e:
                        mark += f" decode_err={e}"
                print(
                    f"    sub={bl['subNetGUID']} stably={bl['stablyNamed']} "
                    f"cls={bl['classNetGUID']} hasRep={bl['hasRepLayout']} "
                    f"bits={bl['payloadBits']}{mark}"
                )
            return
        except Exception as e:
            print(f"  [{mode}] FAIL: {type(e).__name__}: {e}")


def main():
    stream = json.loads(STREAM.read_text(encoding="utf-8"))
    for src in (14, 15, 16, 17, 258):
        analyze_src(stream, src)
    print("\nCAPTURE secondary AttachmentIds:", CAPTURE_WAM_SECONDARY_ATTACHMENT_IDS)


if __name__ == "__main__":
    main()
