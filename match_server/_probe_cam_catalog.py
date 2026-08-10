#!/usr/bin/env python3
"""Catalog CAM AttachmentIds / skins SoftClass wait surface from clothing capture."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import derive_rep_handles as D  # noqa: E402
from cam_im_resend import parse_clothing_content_blocks  # noqa: E402
from _decode_rep_block import decode, layout  # noqa: E402
from repblock import read_packed, read_u  # noqa: E402

CAPTURE_IDS = [1242, 1251, 1260, 1261, 1337, 1386, 2114, 2382, 4425, 6875, 9072]
SKIN_IDS = [1893, 9961, 10071, 3246, 1857]


def dump_uint16_array(payload, p0):
    num = read_u(payload, p0, 16)
    pos = p0 + 16
    ids = []
    while True:
        idx, iw = read_packed(payload, pos)
        pos += iw
        if idx == 0:
            break
        ids.append(read_u(payload, pos, 16))
        pos += 16
    return num, ids


def main() -> int:
    sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)
    blocks = parse_clothing_content_blocks()

    cam = next(b for b in blocks if b["subNetGUID"] == 9374)
    bh, ty = layout("UWW3CharacterAttachmentManager", classes, structs)
    r = decode(cam["payload"], bh, ty, enums=enums)
    print("CAM closed=%s props=%d" % (r["closed"], len(r["seq"])))
    for h, name, typ, w, note, p0 in r["seq"]:
        print("  h%d %s %s" % (h, name, note))
        if "AttachmentIds[]" in name and "Skins" not in name:
            print("    ids=%s" % (dump_uint16_array(cam["payload"], p0)[1],))
        if "AttachmentsIds[]" in name:
            print("    skin_ids=%s" % (dump_uint16_array(cam["payload"], p0)[1],))

    # Try decode hat/chest as various classes
    for sub in (9404, 9406):
        b = next(x for x in blocks if x["subNetGUID"] == sub)
        print("\n=== sub %d cls=%s nbits=%d ===" % (sub, b["classNetGUID"], b["payloadBits"]))
        for leaf in (
            "AWW3CharacterAttachment",
            "AWW3Attachment",
            "UWW3Attachment",
            "AWW3InventoryItem",
            "AActor",
        ):
            try:
                lbh, lty = layout(leaf, classes, structs)
            except Exception as e:
                print("  %s: layout err %s" % (leaf, e))
                continue
            rr = decode(b["payload"], lbh, lty, enums=enums)
            print(
                "  %s: closed=%s props=%d reason=%s left=%s"
                % (leaf, rr["closed"], len(rr["seq"]), rr.get("reason"), rr.get("left"))
            )
            for h, name, typ, w, note, p0 in rr["seq"][:12]:
                print("    h%d %s %s" % (h, name, note))

    # Search GObjects for BP paths that mention catalog IDs as Default__ names
    gobj = Path(str(D.DEFAULT_DUMP)) / "GObjects-Dump.txt"
    needles = ["BP_CH_Hat_004", "BP_CH_KSK_NOJACKET", "Hat_004_01"]
    print("\n=== GObjects path hits ===")
    with gobj.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            if any(n in line for n in needles):
                print(line.rstrip())

    # Search RepLayout / Dumpspace for DatabaseItem with those IDs — scan string assets
    print("\nCatalog IDs (capture):", CAPTURE_IDS)
    print("Skin IDs (capture):", SKIN_IDS)
    print("Replicated only: NetGUID 9404+9406 — 9 AttachmentIds + 5 skins need SoftClass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
