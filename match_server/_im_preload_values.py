#!/usr/bin/env python3
"""Print the *values* of the capture's InventoryManager WeaponsPreloadRequest.

`_decode_im_soft.py` proves the block closes and names every handle; this reads
the value bits so the actual PreloadID / bNeedsPreload / preload-state enums can
be compared against what the client needs in order to answer
`Server_OnClientPreloadWeaponsFinished` (C->S h279).

Usage:
    python match_server/_im_preload_values.py
    python match_server/_im_preload_values.py --srcs 212,213
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import derive_rep_handles as D  # noqa: E402
from _decode_im_soft import decode_soft  # noqa: E402
from _decode_rep_block import layout  # noqa: E402
from cam_im_resend import parse_clothing_content_blocks  # noqa: E402
from repblock import read_u  # noqa: E402

IM_CLASS = "UWW3InventoryManager"


def bits_of(stream, srcs):
    out: list[int] = []
    for i in srcs:
        out.extend(int(c) for c in stream[i]["payload"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--srcs", default="212,213")
    args = ap.parse_args()
    srcs = [int(x) for x in args.srcs.split(",")]

    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
    bits = bits_of(stream, srcs)

    sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)
    by_h, types = layout(IM_CLASS, classes, structs)

    cbs = parse_clothing_content_blocks(bits)
    im = max(cbs, key=lambda b: b["payloadBits"])
    payload = im["payload"]
    print(f"IM subobject netguid={im['subNetGUID']} payloadBits={im['payloadBits']}")

    res = decode_soft(payload, by_h, types, enums=enums)
    print(f"closed={res['closed']} reason={res['reason']} left={res['left']}")
    for h, name, typ, w, note, pos in res["seq"]:
        val = ""
        if note and note.startswith("soft"):
            val = note
        elif w <= 32:
            val = str(read_u(payload, pos, w))
        else:
            val = note or f"<{w} bits>"
        print(f"  h{h:<3} {name:<58} w={w:<5} value={val}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
