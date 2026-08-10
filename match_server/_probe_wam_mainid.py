#!/usr/bin/env python3
"""Decode capture vs stripped WAM: which handles appear, MainId presence."""
from __future__ import annotations

import json
from pathlib import Path

import derive_rep_handles as D
from _decode_rep_block import decode, layout
from cam_im_resend import (
    WAM_OPEN_FINAL_SRCS,
    _find_wam_block_header,
    build_wam_stripped_catalog_payload,
)
from repblock import read_u

HERE = Path(__file__).resolve().parent
stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
classes, structs = D.parse_sdk(sdk)
enums = D.parse_enums(sdk)
bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)

print("=== capture open WAM handles ===")
for src, ng in WAM_OPEN_FINAL_SRCS.items():
    raw = [int(c) for c in stream[src]["payload"]]
    hdr = _find_wam_block_header(raw, ng)
    pl = raw[hdr["payload_start"] : hdr["payload_end"]]
    r = decode(pl, bh, ty, enums=enums)
    names = [x[1] for x in r["seq"]]
    main = None
    if "DirectReplicatedSkinsIds.MainId" in names:
        pos = {x[1]: x for x in r["seq"]}["DirectReplicatedSkinsIds.MainId"][5]
        main = read_u(pl, pos, 16)
    print(f"src={src} ng={ng} bits={len(pl)} closed={r['closed']} main={main}")
    print(f"  handles: {names}")

print("\n=== stripped BatchID=1 payload handles ===")
pl = build_wam_stripped_catalog_payload(batch_id=1)
r = decode(pl, bh, ty, enums=enums)
names = [x[1] for x in r["seq"]]
pos = {x[1]: x for x in r["seq"]}["DirectReplicatedSkinsIds.MainId"][5]
print(f"bits={len(pl)} closed={r['closed']} MainId={read_u(pl, pos, 16)}")
print(f"  handles: {names}")

# Also check CAM strip vs capture for MainId analogy
print("\n=== CAM capture vs strip (for comparison) ===")
from cam_im_resend import extract_cam_im_payloads, build_cam_stripped_catalog_payload, CAM_NETGUID
bh2, ty2 = layout("UWW3CharacterAttachmentManager", classes, structs)
cam = extract_cam_im_payloads()[CAM_NETGUID]
r = decode(cam, bh2, ty2, enums=enums)
print("capture CAM:", [x[1] for x in r["seq"]])
pl = build_cam_stripped_catalog_payload(batch_id=2)
r = decode(pl, bh2, ty2, enums=enums)
print("strip CAM:", [x[1] for x in r["seq"]], "closed", r["closed"], "bits", len(pl))
