#!/usr/bin/env python3
"""Field-for-field: capture WAM open vs SoftClass splices + post-ACK reinforce."""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("WW3_WAM_STRIP_CATALOG", "1")
os.environ.setdefault("WW3_WAM_SOFTCLASS_CATALOG", "1")

import json  # noqa: E402

from cam_im_resend import (  # noqa: E402
    HERE,
    WAM_EARLY_CH4,
    WAM_EARLY_CH5,
    WAM_PRIMARY,
    WAM_SECONDARY,
    WAM_SOFTCLASS_FULL_IDS,
    WAM_SOFTCLASS_MAG_IDS,
    WAM_SOFTCLASS_MAG_MUZZLE_4606_IDS,
    WAM_SOFTCLASS_MAG_MUZZLE_BARREL_IDS,
    WAM_SOFTCLASS_MAG_MUZZLE_IDS,
    WAM_SOFTCLASS_MIN_IDS,
    WAM_SOFTCLASS_NORAIL_IDS,
    _find_wam_block_header,
    build_wam_stripped_catalog_payload,
    extract_wam_payloads,
    splice_wam_payload_attachment_ids,
)
from _decode_rep_block import decode, layout  # noqa: E402
import derive_rep_handles as D  # noqa: E402
from repblock import read_packed, read_u  # noqa: E402


def read_u16_arr(pl: list[int], pos: int) -> tuple[list[int], int]:
    n = read_u(pl, pos, 16)
    pos += 16
    vals: list[int] = []
    while True:
        idx, iw = read_packed(pl, pos)
        pos += iw
        if idx == 0:
            break
        vals.append(read_u(pl, pos, 16))
        pos += 16
    return vals, pos


def read_u8_arr(pl: list[int], pos: int) -> list[int]:
    pos += 16  # ArrayNum
    vals: list[int] = []
    while True:
        idx, iw = read_packed(pl, pos)
        pos += iw
        if idx == 0:
            break
        vals.append(read_u(pl, pos, 8))
        pos += 8
    return vals


def summarize(pl: list[int], bh, ty, enums) -> dict:
    r = decode(pl, bh, ty, enums=enums)
    by = {x[1]: x for x in r["seq"]}
    out: dict = {
        "bits": len(pl),
        "closed": r["closed"],
        "left": r["left"],
        "handles": [x[1] for x in r["seq"]],
    }
    if "ReplicatedBatch.BatchID" in by:
        out["BatchID"] = read_u(pl, by["ReplicatedBatch.BatchID"][5], 32)
    if "ReplicatedBatch.NumReplicatedAttachments" in by:
        out["NumRepAtt"] = read_u(pl, by["ReplicatedBatch.NumReplicatedAttachments"][5], 8)
    else:
        out["NumRepAtt"] = None
    if "ReplicatedBatch.AttachmentIds[]" in by:
        out["AttachmentIds"], _ = read_u16_arr(pl, by["ReplicatedBatch.AttachmentIds[]"][5])
    out["has_RepAtt"] = "ReplicatedBatch.ReplicatedAttachments[]" in by
    if "DirectReplicatedSkinsIds.MainId" in by:
        out["MainId"] = read_u(pl, by["DirectReplicatedSkinsIds.MainId"][5], 16)
    else:
        out["MainId"] = None
    if "DirectReplicatedSkinsIds.Parts.AttachmentsIds[]" in by:
        out["skinsParts"], _ = read_u16_arr(
            pl, by["DirectReplicatedSkinsIds.Parts.AttachmentsIds[]"][5])
    else:
        out["skinsParts"] = None
    if "DirectReplicatedSkinsIds.Parts.ItemTypes[]" in by:
        out["skinsTypes"] = read_u8_arr(
            pl, by["DirectReplicatedSkinsIds.Parts.ItemTypes[]"][5])
    else:
        out["skinsTypes"] = None
    return out


def first_bit_diff(a: list[int], b: list[int]) -> str:
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return f"@{i}"
    if len(a) != len(b):
        return f"len {len(a)} vs {len(b)}"
    return "none"


def main() -> None:
    sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)
    bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)
    payloads = extract_wam_payloads()
    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
    for src, ng in ((15, WAM_EARLY_CH4), (17, WAM_EARLY_CH5)):
        raw = [int(c) for c in stream[src]["payload"]]
        hdr = _find_wam_block_header(raw, ng)
        assert hdr is not None, src
        payloads[ng] = raw[hdr["payload_start"] : hdr["payload_end"]]
    modes = {
        "mag": WAM_SOFTCLASS_MAG_IDS,
        "mag_muzzle": WAM_SOFTCLASS_MAG_MUZZLE_IDS,
        "mag_muzzle_barrel": WAM_SOFTCLASS_MAG_MUZZLE_BARREL_IDS,
        "mag_muzzle_4606": WAM_SOFTCLASS_MAG_MUZZLE_4606_IDS,
        "min": WAM_SOFTCLASS_MIN_IDS,
        "norail": WAM_SOFTCLASS_NORAIL_IDS,
        "full": WAM_SOFTCLASS_FULL_IDS,
    }
    # stub4606: capture order/count with SoftClass 4606 replaced by Mag 151
    stub4606 = {
        ng: tuple(151 if i == 4606 else i for i in ids)
        for ng, ids in WAM_SOFTCLASS_FULL_IDS.items()
    }
    modes["stub4606"] = stub4606
    channels = [
        (WAM_EARLY_CH4, "ch4/8314"),
        (WAM_EARLY_CH5, "ch5/7956"),
        (WAM_SECONDARY, "ch86/9418"),
        (WAM_PRIMARY, "ch87/9426"),
    ]
    for ng, name in channels:
        cap = payloads[ng]
        sc = summarize(cap, bh, ty, enums)
        print("=" * 72)
        print(f"CAPTURE {name} bits={sc['bits']} closed={sc['closed']}")
        for k in (
            "BatchID", "NumRepAtt", "AttachmentIds", "has_RepAtt",
            "MainId", "skinsParts", "skinsTypes", "handles",
        ):
            print(f"  {k}: {sc[k]}")
        for mode, table in modes.items():
            ids = table[ng]
            sp = splice_wam_payload_attachment_ids(cap, ids)
            ss = summarize(sp, bh, ty, enums)
            identical = sp == list(cap)
            print(
                f"  -- splice {mode}: bits {len(cap)}->{len(sp)} "
                f"identical={identical} ids={list(ids)}"
            )
            print(
                f"     BatchID_ok={ss['BatchID'] == sc['BatchID']} "
                f"skins/MainId_ok="
                f"{ss['skinsParts'] == sc['skinsParts'] and ss['skinsTypes'] == sc['skinsTypes'] and ss['MainId'] == sc['MainId']} "
                f"id_order_vs_cap={ss['AttachmentIds'] == sc['AttachmentIds']} "
                f"first_diff={first_bit_diff(cap, sp)}"
            )
        soft = WAM_SOFTCLASS_FULL_IDS[ng]
        post = build_wam_stripped_catalog_payload(batch_id=2, attachment_ids=soft)
        ps = summarize(post, bh, ty, enums)
        print(
            f"  -- postACK reinforce FULL: bits={ps['bits']} "
            f"BatchID={ps['BatchID']} MainId={ps['MainId']} "
            f"skinsParts={ps['skinsParts']} ids={ps['AttachmentIds']}"
        )
        print(
            f"     DIFF vs capture: BatchID {sc['BatchID']}->{ps['BatchID']}, "
            f"MainId {sc['MainId']}->{ps['MainId']}, "
            f"skinsParts {sc['skinsParts']}->{ps['skinsParts']}, "
            f"skinsTypes {sc['skinsTypes']}->{ps['skinsTypes']}, "
            f"NumRepAtt {sc['NumRepAtt']}->{ps['NumRepAtt']}"
        )


if __name__ == "__main__":
    main()
