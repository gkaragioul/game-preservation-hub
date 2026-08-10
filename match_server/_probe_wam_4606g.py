#!/usr/bin/env python3
"""Context around 4606 hits; try content walk from many offsets after NA."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from actor_channel import read_new_actor
from cam_im_resend import STREAM, _walk_content_blocks
from netguid import GuidReader, PackageMap
from repblock import read_packed, read_u
from _decode_rep_block import decode, layout
import derive_rep_handles as D


def scan_uint16(bits, value):
    return [
        pos
        for pos in range(0, max(0, len(bits) - 15))
        if sum(bits[pos + i] << i for i in range(16)) == value
    ]


def try_walk(bits, pos):
    try:
        blocks = _walk_content_blocks(bits, pos)
        return blocks, None
    except Exception as e:
        return None, str(e)


def main():
    stream = json.loads(STREAM.read_text(encoding="utf-8"))
    sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)
    bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)

    for label, srcs in [("ch4", (14, 15)), ("ch5", (16, 17)), ("ch86", (257, 258))]:
        bits = []
        for i in srcs:
            bits.extend(int(c) for c in stream[i]["payload"])
        pm = PackageMap()
        pos = pm.read_export_bunch(bits)["reader"].pos
        gr = GuidReader(bits, pos)
        info = read_new_actor(gr, pm)
        na = gr.pos
        print(f"\n=== {label} srcs={srcs} bits={len(bits)} NA@{na} "
              f"arch={info.get('archetype')} bNetStartup={info.get('bNetStartup')} ===")
        print(f"  info keys: {sorted(info.keys())}")
        for k, v in info.items():
            if k not in ("reader",):
                print(f"    {k}={v}")

        # search offsets near NA for exact content walk
        best = []
        for off in range(na, min(na + 200, len(bits))):
            blocks, err = try_walk(bits, off)
            if blocks is not None:
                best.append((off, len(blocks), sum(b["payloadBits"] for b in blocks)))
                if len(best) >= 3:
                    break
        print(f"  exact-walk hits near NA: {best[:5]}")
        if best:
            off, n, _ = best[0]
            blocks, _ = try_walk(bits, off)
            for bl in blocks:
                print(
                    f"    sub={bl['subNetGUID']} stably={bl['stablyNamed']} "
                    f"cls={bl['classNetGUID']} hasRep={bl['hasRepLayout']} "
                    f"bits={bl['payloadBits']}"
                )
                if bl["payloadBits"] >= 400:
                    r = decode(bl["payload"], bh, ty, enums=enums)
                    print(f"      WAM? closed={r.get('closed')} left={r.get('left')} "
                          f"seq={[x[1] for x in r['seq'][:8]]}")

        # Context around 4606
        for h in scan_uint16(bits, 4606)[:3]:
            window = bits[max(0, h - 32) : h + 48]
            # show as hex-ish bytes if aligned
            print(f"  4606@{h} context bits[{h-16}:{h+32}]="
                  f"{''.join(str(b) for b in bits[max(0,h-16):h+32])}")
            # interpret nearby as packed ints
            for p in range(max(0, h - 40), h):
                v, w = read_packed(bits, p)
                if v == 4606:
                    print(f"    packed 4606 at {p} width={w}")


if __name__ == "__main__":
    main()
