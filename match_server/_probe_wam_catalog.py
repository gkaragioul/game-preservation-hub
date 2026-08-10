#!/usr/bin/env python3
"""Catalog WAM AttachmentIds / skins SoftClass wait surface from weapon opens."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import derive_rep_handles as D  # noqa: E402
from cam_im_resend import (  # noqa: E402
    WAM_PRIMARY,
    WAM_SECONDARY,
    WAM_SRCS,
    extract_wam_payloads,
    parse_weapon_open_content_blocks,
)
from _decode_rep_block import decode, layout  # noqa: E402
from repblock import read_packed, read_u  # noqa: E402


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


def dump_object_array(payload, p0, enums):
    num = read_u(payload, p0, 16)
    pos = p0 + 16
    guids = []
    from repblock import value_widths
    while True:
        idx, iw = read_packed(payload, pos)
        pos += iw
        if idx == 0:
            break
        cands = value_widths("elem", "UWW3Attachment", payload, pos, enums=enums)
        guids.append(cands[0][1])
        pos += cands[0][0]
    return num, guids


def main() -> int:
    sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)
    cands = sorted(c for c in classes if "AttachmentManager" in c or "WeaponAttachment" in c)
    print("class candidates:", cands)

    payloads = extract_wam_payloads()
    leaves = [
        "UWW3WeaponAttachmentManager",
        "UWW3AttachmentManager",
        "UWW3CharacterAttachmentManager",
    ]
    for netguid in (WAM_SECONDARY, WAM_PRIMARY):
        pl = payloads[netguid]
        print("\n=== WAM %d nbits=%d ===" % (netguid, len(pl)))
        for leaf in leaves:
            if leaf not in classes:
                print("  %s: missing from SDK" % leaf)
                continue
            bh, ty = layout(leaf, classes, structs)
            r = decode(pl, bh, ty, enums=enums)
            print(
                "  %s: closed=%s props=%d left=%s reason=%s"
                % (leaf, r["closed"], len(r["seq"]), r.get("left"), r.get("reason"))
            )
            if not r["seq"]:
                continue
            for h, name, typ, w, note, p0 in r["seq"]:
                print("    h%d %s %s" % (h, name, note))
                if "AttachmentIds[]" in name and "Skins" not in name and "AttachmentsIds" not in name:
                    print("      ids=%s" % (dump_uint16_array(pl, p0)[1],))
                if "AttachmentsIds[]" in name:
                    print("      skin_ids=%s" % (dump_uint16_array(pl, p0)[1],))
                if "ReplicatedAttachments[]" in name:
                    try:
                        n, guids = dump_object_array(pl, p0, enums)
                        print("      num=%d guids=%s" % (n, guids))
                    except Exception as e:
                        print("      object walk err: %s" % e)

        # Also list all content blocks on the open (what attachment objects exist)
        blocks = parse_weapon_open_content_blocks(WAM_SRCS[netguid])
        print("  content blocks:")
        for b in blocks:
            print(
                "    sub=%s stably=%s cls=%s bits=%s"
                % (b["subNetGUID"], b["stablyNamed"], b["classNetGUID"], b["payloadBits"])
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
