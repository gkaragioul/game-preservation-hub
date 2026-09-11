#!/usr/bin/env python3
"""Tests for WW3_INV_ATTACH clothing CAM/IM extract + content-block stably=0 parse."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from actor_channel import Bits, read_content_blocks  # noqa: E402
from cam_im_resend import (  # noqa: E402
    CAM_NETGUID,
    CAPTURE_CAM_ATTACHMENT_IDS,
    CAPTURE_WAM_EARLY_ATTACHMENT_IDS,
    CAPTURE_WAM_PRIMARY_ATTACHMENT_IDS,
    CAPTURE_WAM_SECONDARY_ATTACHMENT_IDS,
    CAPTURE_WAM_SECONDARY_MAIN_ID,
    CHEST_NETGUID,
    HAT_NETGUID,
    IM_NETGUID,
    WAM_EARLY_CH4,
    WAM_EARLY_CH5,
    WAM_PRIMARY,
    WAM_SECONDARY,
    WAM_STRIP_NETGUIDS,
    build_cam_im_resend_bits,
    build_cam_strip_resend_bits,
    build_cam_stripped_catalog_payload,
    build_wam_resend_bits,
    build_wam_strip_resend_bits,
    build_wam_stripped_catalog_payload,
    cam_im_after_ack_enabled,
    cam_strip_catalog_enabled,
    clothing_resend_enabled,
    clothing_resend_specs,
    extract_cam_im_payloads,
    extract_wam_payloads,
    parse_clothing_content_blocks,
    parse_weapon_open_content_blocks,
    rewrite_weapon_final_strip_wam,
    _find_wam_block_header,
    wam_strip_catalog_enabled,
    WAM_OPEN_FINAL_SRCS,
)
from netguid import PackageMap  # noqa: E402
from build_ownership_bootstrap import _with_inv_attach, RANGES_OWNERSHIP  # noqa: E402


def test_clothing_exact_consume_with_class_guid():
    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
    bits: list[int] = []
    for i in (212, 213):
        bits.extend(int(c) for c in stream[i]["payload"])
    pm = PackageMap()
    pos = pm.read_export_bunch(bits)["reader"].pos
    r = Bits(bits, pos)
    blocks = read_content_blocks(r, total_bits=len(bits))
    assert r.pos == len(bits), f"left={len(bits) - r.pos}"
    subs = [b.get("subNetGUID") for b in blocks if not b.get("isActor")]
    assert CAM_NETGUID in subs
    assert IM_NETGUID in subs
    # Dynamic hat/chest carry class GUIDs
    dyn = [b for b in blocks if b.get("stablyNamed") == 0]
    assert len(dyn) == 2
    assert all(b.get("classNetGUID") for b in dyn)
    print("[ok] clothing bunch exact-consumes with stably=0 class GUID")


def test_extract_cam_im_payloads():
    payloads = extract_cam_im_payloads()
    assert len(payloads[CAM_NETGUID]) == 705
    assert len(payloads[IM_NETGUID]) == 1978
    blocks = parse_clothing_content_blocks()
    assert blocks[-2]["subNetGUID"] == CAM_NETGUID
    assert blocks[-1]["subNetGUID"] == IM_NETGUID
    print("[ok] CAM 705 + IM 1978 extracted from clothing")


def test_resend_roundtrip():
    bits = build_cam_im_resend_bits()
    blocks = read_content_blocks(Bits(bits))
    assert len(blocks) == 2
    assert blocks[0]["subNetGUID"] == CAM_NETGUID
    assert blocks[0]["stablyNamed"] == 1
    assert blocks[0]["payloadBits"] == 705
    assert blocks[1]["subNetGUID"] == IM_NETGUID
    assert blocks[1]["payloadBits"] == 1978
    assert blocks[0]["payload"] == extract_cam_im_payloads()[CAM_NETGUID]
    print(f"[ok] CAM/IM resend frames {len(bits)} bits, round-trips")


def test_inv_attach_ranges_splice():
    os.environ["WW3_INV_ATTACH"] = "1"
    try:
        ranges = _with_inv_attach(list(RANGES_OWNERSHIP))
    finally:
        os.environ.pop("WW3_INV_ATTACH", None)
    assert (205, 206) in ranges
    assert (257, 262) in ranges
    # MSP before clothing, weapons after clothing
    i_msp = ranges.index((205, 206))
    i_cloth = ranges.index((212, 213))
    i_weap = ranges.index((257, 262))
    assert i_msp < i_cloth < i_weap
    print("[ok] INV_ATTACH splices MSP before clothing, weapons after")


def test_wam_in_weapon_opens():
    """Capture fact: WAM RepLayout lives IN the ch86/87 opens, not later follow-ups."""
    payloads = extract_wam_payloads()
    assert len(payloads[WAM_SECONDARY]) == 505
    assert len(payloads[WAM_PRIMARY]) == 457
    sec = parse_weapon_open_content_blocks((257, 258))
    assert any(b["subNetGUID"] == WAM_SECONDARY and b["payloadBits"] == 505 for b in sec)
    bits = build_wam_resend_bits(WAM_SECONDARY)
    blocks = read_content_blocks(Bits(bits))
    assert len(blocks) == 1
    assert blocks[0]["subNetGUID"] == WAM_SECONDARY
    assert blocks[0]["payloadBits"] == 505
    print("[ok] WAM 9418/9426 extracted from weapon opens (505/457)")


def test_after_ack_flag_default_off():
    os.environ.pop("WW3_CAM_IM_AFTER_ACK", None)
    assert cam_im_after_ack_enabled() is False
    os.environ["WW3_CAM_IM_AFTER_ACK"] = "1"
    try:
        assert cam_im_after_ack_enabled() is True
    finally:
        os.environ.pop("WW3_CAM_IM_AFTER_ACK", None)
    print("[ok] WW3_CAM_IM_AFTER_ACK defaults off")


def test_inv_attach_gate_acks_and_timeout():
    import server

    srv = server.MatchServer()
    conn = server.Conn()
    # Immediate mode
    os.environ.pop("WW3_CAM_IM_AFTER_ACK", None)
    ready, why = srv._inv_attach_gate_ready(conn)
    assert ready and why == "immediate"

    os.environ["WW3_CAM_IM_AFTER_ACK"] = "1"
    os.environ["WW3_CAM_IM_ACK_TIMEOUT_S"] = "0.05"
    try:
        conn._ownership_done = True
        conn._ownership_done_t = time.time()
        ready, why = srv._inv_attach_gate_ready(conn)
        assert not ready and "waiting" in why
        conn._clothing_acked = True
        conn._ch85_acked = True
        conn._ch86_acked = True
        conn._ch87_acked = True
        ready, why = srv._inv_attach_gate_ready(conn)
        assert ready and why == "acks"
        # Timeout path
        conn2 = server.Conn()
        conn2._ownership_done = True
        conn2._ownership_done_t = time.time() - 1.0
        ready, why = srv._inv_attach_gate_ready(conn2)
        assert ready and "timeout" in why
    finally:
        os.environ.pop("WW3_CAM_IM_AFTER_ACK", None)
        os.environ.pop("WW3_CAM_IM_ACK_TIMEOUT_S", None)
    print("[ok] AFTER_ACK gate opens on acks or timeout")


def test_ack_audit_tags_inv_channels():
    import server

    was = server.ACK_AUDIT
    try:
        server.ACK_AUDIT = True
        tag = server.MatchServer._audit_tag_for([
            {"chIndex": 86, "bOpen": 1, "bPartial": 1, "bPartialInitial": 1, "_src_idx": 257},
        ])
        assert tag and "ch86" in tag and "src=257" in tag, tag
        srv = server.MatchServer()
        conn = server.Conn()
        conn.pkt_audit = {9: {"t": time.time(), "tag": tag, "acked": None}}
        srv.audit_note_acks(conn, [9])
        assert getattr(conn, "_ch86_acked", False)
    finally:
        server.ACK_AUDIT = was
    print("[ok] ack-audit tags ch86 and sets _ch86_acked")


def test_clothing_resend_specs():
    os.environ.pop("WW3_CLOTHING_RESEND", None)
    assert clothing_resend_enabled() is False
    os.environ["WW3_CLOTHING_RESEND"] = "1"
    try:
        assert clothing_resend_enabled() is True
        specs = clothing_resend_specs()
        assert len(specs) == 2
        assert specs[0]["_src_idx"] == 212
        assert specs[1]["_src_idx"] == 213
        assert specs[0].get("bHasPackageMapExports") == 1
        assert specs[0].get("bPartialInitial") == 1
        assert specs[1].get("bPartialFinal") == 1
        # Concatenate payloads and confirm hat/chest + CAM + IM still walk
        bits: list[int] = []
        for sp in specs:
            bits.extend(int(c) for c in sp["payload"])
        blocks = parse_clothing_content_blocks(bits)
        subs = [b["subNetGUID"] for b in blocks if not b["isActor"]]
        assert HAT_NETGUID in subs and CHEST_NETGUID in subs
        assert CAM_NETGUID in subs and IM_NETGUID in subs
    finally:
        os.environ.pop("WW3_CLOTHING_RESEND", None)
    print("[ok] CLOTHING_RESEND specs = capture 212–213 with hat/chest+CAM+IM")


def test_im_softclassptr_exact_consume():
    """SoftClassPtr = FString; clothing IM 1978-bit payload must exact-consume."""
    from _decode_rep_block import decode, layout
    import derive_rep_handles as D

    sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)
    bh, ty = layout("UWW3InventoryManager", classes, structs)
    pl = extract_cam_im_payloads()[IM_NETGUID]
    r = decode(pl, bh, ty, enums=enums)
    assert r["closed"] and r["left"] == 0, r
    soft = [x for x in r["seq"] if "GadgetClass" in x[1]]
    assert len(soft) == 2
    assert all("soft" in x[4] and "BP_" in x[4] for x in soft), soft
    print("[ok] IM SoftClassPtr FString decode exact-consumes (2 gadget paths)")


def test_cam_replicated_attachments_are_hat_chest():
    from _decode_rep_block import decode, layout
    import derive_rep_handles as D
    from repblock import read_packed, read_u, value_widths

    sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)
    bh, ty = layout("UWW3CharacterAttachmentManager", classes, structs)
    pl = extract_cam_im_payloads()[CAM_NETGUID]
    r = decode(pl, bh, ty, enums=enums)
    assert r["closed"]
    # Walk ReplicatedAttachments[] for object NetGUIDs
    att = next(x for x in r["seq"] if x[1] == "ReplicatedBatch.ReplicatedAttachments[]")
    pos = att[5]
    num = read_u(pl, pos, 16)
    pos += 16
    guids = []
    while True:
        idx, iw = read_packed(pl, pos)
        pos += iw
        if idx == 0:
            break
        cands = value_widths("elem", "UWW3Attachment", pl, pos, enums=enums)
        note = cands[0][1]
        guids.append(note)
        pos += cands[0][0]
    assert num == 2
    assert any("9404" in g for g in guids)
    assert any("9406" in g for g in guids)
    # Catalog SoftClass wait surface: 11 IDs, only 2 channel objects
    ids_prop = next(x for x in r["seq"] if x[1] == "ReplicatedBatch.AttachmentIds[]")
    pos = ids_prop[5]
    n = read_u(pl, pos, 16)
    pos += 16
    ids = []
    while True:
        idx, iw = read_packed(pl, pos)
        pos += iw
        if idx == 0:
            break
        ids.append(read_u(pl, pos, 16))
        pos += 16
    assert n == 11 and ids == list(CAPTURE_CAM_ATTACHMENT_IDS)
    print("[ok] CAM ReplicatedAttachments = NetGUID 9404 + 9406")


def test_cam_strip_catalog_exact_consume():
    """Stripped CAM: empty AttachmentIds/skins, keep 9404+9406, BatchID=2."""
    from _decode_rep_block import decode, layout
    import derive_rep_handles as D
    from repblock import read_packed, read_u, value_widths

    os.environ.pop("WW3_CAM_STRIP_CATALOG", None)
    assert cam_strip_catalog_enabled() is False
    os.environ["WW3_CAM_STRIP_CATALOG"] = "1"
    try:
        assert cam_strip_catalog_enabled() is True
        pl = build_cam_stripped_catalog_payload(batch_id=2)
        sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
        classes, structs = D.parse_sdk(sdk)
        enums = D.parse_enums(sdk)
        bh, ty = layout("UWW3CharacterAttachmentManager", classes, structs)
        r = decode(pl, bh, ty, enums=enums)
        assert r["closed"] and r["left"] == 0, r
        by_name = {x[1]: x for x in r["seq"]}
        pos = by_name["ReplicatedBatch.BatchID"][5]
        assert read_u(pl, pos, 32) == 2
        pos = by_name["ReplicatedBatch.AttachmentIds[]"][5]
        assert read_u(pl, pos, 16) == 0
        pos = by_name["ReplicatedBatch.ReplicatedAttachments[]"][5]
        num = read_u(pl, pos, 16)
        pos += 16
        guids = []
        while True:
            idx, iw = read_packed(pl, pos)
            pos += iw
            if idx == 0:
                break
            cands = value_widths("elem", "UWW3Attachment", pl, pos, enums=enums)
            guids.append(cands[0][1])
            pos += cands[0][0]
        assert num == 2
        assert any("9404" in g for g in guids) and any("9406" in g for g in guids)
        pos = by_name["DirectReplicatedSkinsIds.Parts.AttachmentsIds[]"][5]
        assert read_u(pl, pos, 16) == 0
        pos = by_name["DirectReplicatedSkinsIds.Parts.ItemTypes[]"][5]
        assert read_u(pl, pos, 16) == 0
        bits = build_cam_strip_resend_bits()
        blocks = read_content_blocks(Bits(bits))
        assert len(blocks) == 1 and blocks[0]["subNetGUID"] == CAM_NETGUID
        assert blocks[0]["payload"] == pl
    finally:
        os.environ.pop("WW3_CAM_STRIP_CATALOG", None)
    print("[ok] CAM_STRIP_CATALOG payload exact-consumes (empty ids/skins, keep 9404+9406)")


def test_wam_catalog_softclass_surface():
    """Capture WAM: 9/8 AttachmentIds, MainId on secondary, no ReplicatedAttachments."""
    from _decode_rep_block import decode, layout
    import derive_rep_handles as D
    from repblock import read_u

    sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)
    bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)
    payloads = extract_wam_payloads()

    r = decode(payloads[WAM_SECONDARY], bh, ty, enums=enums)
    assert r["closed"] and r["left"] == 0, r
    by_name = {x[1]: x for x in r["seq"]}
    assert "ReplicatedBatch.ReplicatedAttachments[]" not in by_name
    pos = by_name["ReplicatedBatch.AttachmentIds[]"][5]
    assert read_u(payloads[WAM_SECONDARY], pos, 16) == 9
    pos = by_name["DirectReplicatedSkinsIds.MainId"][5]
    assert read_u(payloads[WAM_SECONDARY], pos, 16) == CAPTURE_WAM_SECONDARY_MAIN_ID

    r = decode(payloads[WAM_PRIMARY], bh, ty, enums=enums)
    assert r["closed"] and r["left"] == 0, r
    by_name = {x[1]: x for x in r["seq"]}
    assert "ReplicatedBatch.ReplicatedAttachments[]" not in by_name
    pos = by_name["ReplicatedBatch.AttachmentIds[]"][5]
    assert read_u(payloads[WAM_PRIMARY], pos, 16) == 8
    assert len(CAPTURE_WAM_SECONDARY_ATTACHMENT_IDS) == 9
    assert len(CAPTURE_WAM_PRIMARY_ATTACHMENT_IDS) == 8
    print("[ok] WAM catalog SoftClass surface (9/8 ids, no ReplicatedAttachments)")


def test_wam_strip_catalog_exact_consume():
    """Stripped WAM: empty AttachmentIds/skins; omit MainId; optional keep dyn."""
    from _decode_rep_block import decode, layout
    import derive_rep_handles as D
    from cam_im_resend import WAM_KEEP_REPLICATED, wam_keep_dynamic_enabled
    from repblock import read_u, read_packed

    os.environ.pop("WW3_WAM_STRIP_CATALOG", None)
    os.environ.pop("WW3_WAM_KEEP_DYNAMIC", None)
    assert wam_strip_catalog_enabled() is False
    assert wam_keep_dynamic_enabled() is False
    os.environ["WW3_WAM_STRIP_CATALOG"] = "1"
    try:
        assert wam_strip_catalog_enabled() is True
        from cam_im_resend import (
            WAM_EARLY_CH4,
            WAM_PRIMARY,
            WAM_SECONDARY,
            wam_open_strip_srcs,
            wam_strip_target_netguids,
        )
        os.environ["WW3_WAM_STRIP_CHANNELS"] = "inv"
        assert wam_strip_target_netguids() == (WAM_SECONDARY, WAM_PRIMARY)
        assert set(wam_open_strip_srcs()) == {258, 260}
        os.environ["WW3_WAM_STRIP_CHANNELS"] = "all"
        assert WAM_EARLY_CH4 in wam_strip_target_netguids()
        # Open-style empty (no keep, no MainId) — SoftClass never arms.
        pl = build_wam_stripped_catalog_payload(batch_id=2)
        sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
        classes, structs = D.parse_sdk(sdk)
        enums = D.parse_enums(sdk)
        bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)
        r = decode(pl, bh, ty, enums=enums)
        assert r["closed"] and r["left"] == 0, r
        by_name = {x[1]: x for x in r["seq"]}
        assert "DirectReplicatedSkinsIds.MainId" not in by_name
        assert "ReplicatedBatch.NumReplicatedAttachments" not in by_name
        assert "ReplicatedBatch.ReplicatedAttachments[]" not in by_name
        pos = by_name["ReplicatedBatch.BatchID"][5]
        assert read_u(pl, pos, 32) == 2
        pos = by_name["ReplicatedBatch.AttachmentIds[]"][5]
        assert read_u(pl, pos, 16) == 0
        # Default post-ACK resend: same empty catalog (no keep).
        for netguid in WAM_STRIP_NETGUIDS:
            bits = build_wam_strip_resend_bits(netguid)
            blocks = read_content_blocks(Bits(bits))
            assert len(blocks) == 1 and blocks[0]["subNetGUID"] == netguid
            assert blocks[0]["payload"] == pl
        # Optional keep-dynamic: Num=1 + ReplicatedAttachments, still no MainId.
        os.environ["WW3_WAM_KEEP_DYNAMIC"] = "1"
        assert wam_keep_dynamic_enabled() is True
        for netguid in WAM_STRIP_NETGUIDS:
            bits = build_wam_strip_resend_bits(netguid)
            blocks = read_content_blocks(Bits(bits))
            keep = WAM_KEEP_REPLICATED[netguid]
            expect = build_wam_stripped_catalog_payload(
                batch_id=2, replicated_attachments=(keep,))
            assert blocks[0]["payload"] == expect
            rr = decode(expect, bh, ty, enums=enums)
            assert rr["closed"] and rr["left"] == 0, (netguid, rr)
            by2 = {x[1]: x for x in rr["seq"]}
            assert "DirectReplicatedSkinsIds.MainId" not in by2
            assert read_u(expect, by2["ReplicatedBatch.NumReplicatedAttachments"][5], 8) == 1
            p = by2["ReplicatedBatch.ReplicatedAttachments[]"][5]
            assert read_u(expect, p, 16) == 1
            p2 = p + 16
            _idx, iw = read_packed(expect, p2)
            p2 += iw
            gid, _gw = read_packed(expect, p2)
            assert gid == keep, (netguid, gid, keep)
    finally:
        os.environ.pop("WW3_WAM_STRIP_CATALOG", None)
        os.environ.pop("WW3_WAM_KEEP_DYNAMIC", None)
        os.environ.pop("WW3_WAM_STRIP_CHANNELS", None)
    print("[ok] WAM_STRIP_CATALOG omit MainId + optional keep dynamic exact-consume")


def test_wam_early_ch4_ch5_softclass_4606_surface():
    """Ownership early Glocks (src 15/17) carry SoftClass catalog id 4606."""
    from _decode_rep_block import decode, layout
    import derive_rep_handles as D
    from repblock import read_u, read_packed

    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
    sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)
    bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)
    assert set(WAM_STRIP_NETGUIDS) == {
        WAM_EARLY_CH4, WAM_EARLY_CH5, WAM_SECONDARY, WAM_PRIMARY,
    }
    for src, ng in ((15, WAM_EARLY_CH4), (17, WAM_EARLY_CH5)):
        raw = [int(c) for c in stream[src]["payload"]]
        hdr = _find_wam_block_header(raw, ng)
        assert hdr is not None, src
        payload = raw[hdr["payload_start"] : hdr["payload_end"]]
        assert len(payload) == 457
        r = decode(payload, bh, ty, enums=enums)
        assert r["closed"] and r["left"] == 0, (src, r)
        by_name = {x[1]: x for x in r["seq"]}
        pos = by_name["ReplicatedBatch.AttachmentIds[]"][5]
        n = read_u(payload, pos, 16)
        assert n == 8
        p2 = pos + 16
        ids = []
        for _ in range(n):
            _idx, iw = read_packed(payload, p2)
            p2 += iw
            ids.append(read_u(payload, p2, 16))
            p2 += 16
        assert tuple(ids) == CAPTURE_WAM_EARLY_ATTACHMENT_IDS
        assert 4606 in ids
    print("[ok] early ch4/ch5 WAM SoftClass surface (8314/7956, id 4606)")


def test_wam_strip_inside_weapon_open_finals():
    """Open FINALs rewrite WAM to empty catalog (BatchID=1), including ch4/ch5."""
    from _decode_rep_block import decode, layout
    import derive_rep_handles as D
    from cam_im_resend import maybe_strip_wam_in_weapon_open_bits
    from repblock import read_u

    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
    for k in (
        "WW3_WAM_STRIP_CATALOG", "WW3_WAM_SOFTCLASS_CATALOG", "WW3_WAM_SOFTCLASS_MODE",
    ):
        os.environ.pop(k, None)
    assert maybe_strip_wam_in_weapon_open_bits(
        [int(c) for c in stream[258]["payload"]], 258) is None

    os.environ["WW3_WAM_STRIP_CATALOG"] = "1"
    try:
        sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
        classes, structs = D.parse_sdk(sdk)
        enums = D.parse_enums(sdk)
        bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)
        for src, ng in WAM_OPEN_FINAL_SRCS.items():
            raw = [int(c) for c in stream[src]["payload"]]
            out = rewrite_weapon_final_strip_wam(raw, ng, batch_id=1)
            assert out is not None and len(out) < len(raw), src
            hdr = _find_wam_block_header(out, ng)
            assert hdr is not None, src
            payload = out[hdr["payload_start"] : hdr["payload_end"]]
            r = decode(payload, bh, ty, enums=enums)
            assert r["closed"] and r["left"] == 0, (src, r)
            by_name = {x[1]: x for x in r["seq"]}
            assert read_u(payload, by_name["ReplicatedBatch.BatchID"][5], 32) == 1
            assert read_u(payload, by_name["ReplicatedBatch.AttachmentIds[]"][5], 16) == 0
            # Bits before the WAM NumBits field unchanged (NewActor + prior blocks).
            raw_hdr = _find_wam_block_header(raw, ng)
            assert raw[: raw_hdr["nbits_pos"]] == out[: hdr["nbits_pos"]]
            via_maybe = maybe_strip_wam_in_weapon_open_bits(raw, src)
            assert via_maybe == out
    finally:
        for k in (
            "WW3_WAM_STRIP_CATALOG", "WW3_WAM_SOFTCLASS_CATALOG", "WW3_WAM_SOFTCLASS_MODE",
        ):
            os.environ.pop(k, None)
    print("[ok] WAM strip inside weapon open FINALs (15/17/258/260, BatchID=1 empty)")


def test_wam_open_softclass_mag_ids():
    """SOFTCLASS_CATALOG=mag: Mag ids spliced into capture open (skins/MainId kept)."""
    from _decode_rep_block import decode, layout
    import derive_rep_handles as D
    from cam_im_resend import (
        CAPTURE_WAM_SECONDARY_MAIN_ID,
        WAM_SOFTCLASS_MAG_IDS,
        splice_wam_payload_attachment_ids,
    )
    from repblock import read_u, read_packed

    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
    for k in (
        "WW3_WAM_STRIP_CATALOG", "WW3_WAM_SOFTCLASS_CATALOG", "WW3_WAM_SOFTCLASS_MODE",
    ):
        os.environ.pop(k, None)
    os.environ["WW3_WAM_STRIP_CATALOG"] = "1"
    os.environ["WW3_WAM_SOFTCLASS_CATALOG"] = "1"
    os.environ["WW3_WAM_SOFTCLASS_MODE"] = "mag"
    try:
        sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
        classes, structs = D.parse_sdk(sdk)
        enums = D.parse_enums(sdk)
        bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)
        for src, ng in WAM_OPEN_FINAL_SRCS.items():
            raw = [int(c) for c in stream[src]["payload"]]
            cap_hdr = _find_wam_block_header(raw, ng)
            cap_pl = raw[cap_hdr["payload_start"] : cap_hdr["payload_end"]]
            cap_r = decode(cap_pl, bh, ty, enums=enums)
            assert cap_r["closed"], (src, cap_r)
            cap_names = {x[1] for x in cap_r["seq"]}

            out = rewrite_weapon_final_strip_wam(raw, ng, batch_id=1)
            hdr = _find_wam_block_header(out, ng)
            payload = out[hdr["payload_start"] : hdr["payload_end"]]
            # Mag splice shrinks AttachmentIds but keeps capture skins/MainId shape.
            assert len(payload) < len(cap_pl), (src, len(payload), len(cap_pl))
            # Full strip Mag rebuild is much smaller (~204b); splice keeps skins (~289+).
            assert len(payload) > 250, (src, len(payload))
            r = decode(payload, bh, ty, enums=enums)
            assert r["closed"] and r["left"] == 0, (src, r)
            by = {x[1]: x for x in r["seq"]}
            expect = WAM_SOFTCLASS_MAG_IDS[ng]
            pos = by["ReplicatedBatch.AttachmentIds[]"][5]
            n = read_u(payload, pos, 16)
            assert n == len(expect) == 1
            p2 = pos + 16
            _idx, iw = read_packed(payload, p2)
            p2 += iw
            assert read_u(payload, p2, 16) == expect[0]
            # Capture SoftClass shape preserved (not stripped empty skins / omit MainId).
            assert "DirectReplicatedSkinsIds.Parts.AttachmentsIds[]" in by
            assert "DirectReplicatedSkinsIds.Parts.ItemTypes[]" in by
            skins_n = read_u(
                payload, by["DirectReplicatedSkinsIds.Parts.AttachmentsIds[]"][5], 16)
            assert skins_n == 3, (src, skins_n)
            if "DirectReplicatedSkinsIds.MainId" in cap_names:
                assert "DirectReplicatedSkinsIds.MainId" in by
                assert read_u(
                    payload, by["DirectReplicatedSkinsIds.MainId"][5], 16
                ) == CAPTURE_WAM_SECONDARY_MAIN_ID
            else:
                assert "DirectReplicatedSkinsIds.MainId" not in by
            # Direct helper matches FINAL rewrite payload.
            direct = splice_wam_payload_attachment_ids(cap_pl, expect)
            assert direct == payload
    finally:
        for k in (
            "WW3_WAM_STRIP_CATALOG", "WW3_WAM_SOFTCLASS_CATALOG", "WW3_WAM_SOFTCLASS_MODE",
        ):
            os.environ.pop(k, None)
    print("[ok] WAM open SoftClass mag splice (capture skins/MainId kept)")


def test_wam_open_softclass_mag_muzzle_ids():
    """SOFTCLASS_CATALOG=mag_muzzle: Mag+Muzzle spliced into capture open."""
    from _decode_rep_block import decode, layout
    import derive_rep_handles as D
    from cam_im_resend import WAM_SOFTCLASS_MAG_MUZZLE_IDS
    from repblock import read_u, read_packed

    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
    for k in (
        "WW3_WAM_STRIP_CATALOG", "WW3_WAM_SOFTCLASS_CATALOG", "WW3_WAM_SOFTCLASS_MODE",
    ):
        os.environ.pop(k, None)
    os.environ["WW3_WAM_STRIP_CATALOG"] = "1"
    os.environ["WW3_WAM_SOFTCLASS_CATALOG"] = "1"
    os.environ["WW3_WAM_SOFTCLASS_MODE"] = "mag_muzzle"
    try:
        sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
        classes, structs = D.parse_sdk(sdk)
        enums = D.parse_enums(sdk)
        bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)
        for src, ng in WAM_OPEN_FINAL_SRCS.items():
            raw = [int(c) for c in stream[src]["payload"]]
            out = rewrite_weapon_final_strip_wam(raw, ng, batch_id=1)
            hdr = _find_wam_block_header(out, ng)
            payload = out[hdr["payload_start"] : hdr["payload_end"]]
            r = decode(payload, bh, ty, enums=enums)
            assert r["closed"] and r["left"] == 0, (src, r)
            by = {x[1]: x for x in r["seq"]}
            expect = WAM_SOFTCLASS_MAG_MUZZLE_IDS[ng]
            pos = by["ReplicatedBatch.AttachmentIds[]"][5]
            n = read_u(payload, pos, 16)
            assert n == len(expect) == 2, (src, n, expect)
            p2 = pos + 16
            ids = []
            for _ in range(n):
                _idx, iw = read_packed(payload, p2)
                p2 += iw
                ids.append(read_u(payload, p2, 16))
                p2 += 16
            assert tuple(ids) == expect
            assert 4606 not in ids
            assert "DirectReplicatedSkinsIds.Parts.AttachmentsIds[]" in by
    finally:
        for k in (
            "WW3_WAM_STRIP_CATALOG", "WW3_WAM_SOFTCLASS_CATALOG", "WW3_WAM_SOFTCLASS_MODE",
        ):
            os.environ.pop(k, None)
    print("[ok] WAM open SoftClass mag_muzzle splice (151+101 / 143+108, no 4606)")


def test_wam_open_softclass_mag_muzzle_barrel_ids():
    """SOFTCLASS_CATALOG=mag_muzzle_barrel: Mag+Muzzle+Barrel spliced into capture open."""
    from _decode_rep_block import decode, layout
    import derive_rep_handles as D
    from cam_im_resend import (
        WAM_SOFTCLASS_MAG_MUZZLE_BARREL_IDS,
        collect_wam_softclass_export_specs,
    )
    from repblock import read_u, read_packed

    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
    for k in (
        "WW3_WAM_STRIP_CATALOG", "WW3_WAM_SOFTCLASS_CATALOG", "WW3_WAM_SOFTCLASS_MODE",
        "WW3_WAM_SOFTCLASS_EXPORT",
    ):
        os.environ.pop(k, None)
    os.environ["WW3_WAM_STRIP_CATALOG"] = "1"
    os.environ["WW3_WAM_SOFTCLASS_CATALOG"] = "1"
    os.environ["WW3_WAM_SOFTCLASS_MODE"] = "mag_muzzle_barrel"
    os.environ["WW3_WAM_SOFTCLASS_EXPORT"] = "1"
    try:
        sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
        classes, structs = D.parse_sdk(sdk)
        enums = D.parse_enums(sdk)
        bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)
        for src, ng in WAM_OPEN_FINAL_SRCS.items():
            raw = [int(c) for c in stream[src]["payload"]]
            out = rewrite_weapon_final_strip_wam(raw, ng, batch_id=1)
            hdr = _find_wam_block_header(out, ng)
            payload = out[hdr["payload_start"] : hdr["payload_end"]]
            r = decode(payload, bh, ty, enums=enums)
            assert r["closed"] and r["left"] == 0, (src, r)
            by = {x[1]: x for x in r["seq"]}
            expect = WAM_SOFTCLASS_MAG_MUZZLE_BARREL_IDS[ng]
            pos = by["ReplicatedBatch.AttachmentIds[]"][5]
            n = read_u(payload, pos, 16)
            assert n == len(expect) == 3, (src, n, expect)
            p2 = pos + 16
            ids = []
            for _ in range(n):
                _idx, iw = read_packed(payload, p2)
                p2 += iw
                ids.append(read_u(payload, p2, 16))
                p2 += 16
            assert tuple(ids) == expect
            assert 4606 not in ids
            assert "DirectReplicatedSkinsIds.Parts.AttachmentsIds[]" in by
        exp = collect_wam_softclass_export_specs()
        assert {s.item_id for s in exp} == {101, 108, 143, 151, 295, 304}
        assert all(s.class_name.startswith("BP_WP_") for s in exp)
    finally:
        for k in (
            "WW3_WAM_STRIP_CATALOG", "WW3_WAM_SOFTCLASS_CATALOG", "WW3_WAM_SOFTCLASS_MODE",
            "WW3_WAM_SOFTCLASS_EXPORT",
        ):
            os.environ.pop(k, None)
    print("[ok] WAM open SoftClass mag_muzzle_barrel splice (151+101+304 / 143+108+295, no 4606)")


def test_wam_open_softclass_mag_muzzle_4606_ids():
    """SOFTCLASS_CATALOG=mag_muzzle_4606: Mag+Muzzle+Rail 4606 on Glock opens."""
    from _decode_rep_block import decode, layout
    import derive_rep_handles as D
    from cam_im_resend import (
        WAM_SOFTCLASS_MAG_MUZZLE_4606_IDS,
    )
    from repblock import read_u, read_packed

    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
    for k in (
        "WW3_WAM_STRIP_CATALOG", "WW3_WAM_SOFTCLASS_CATALOG", "WW3_WAM_SOFTCLASS_MODE",
        "WW3_WAM_SOFTCLASS_EXPORT",
    ):
        os.environ.pop(k, None)
    os.environ["WW3_WAM_STRIP_CATALOG"] = "1"
    os.environ["WW3_WAM_SOFTCLASS_CATALOG"] = "1"
    os.environ["WW3_WAM_SOFTCLASS_MODE"] = "mag_muzzle_4606"
    os.environ["WW3_WAM_SOFTCLASS_EXPORT"] = "0"
    try:
        sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
        classes, structs = D.parse_sdk(sdk)
        enums = D.parse_enums(sdk)
        bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)
        for src, ng in WAM_OPEN_FINAL_SRCS.items():
            raw = [int(c) for c in stream[src]["payload"]]
            out = rewrite_weapon_final_strip_wam(raw, ng, batch_id=1)
            hdr = _find_wam_block_header(out, ng)
            payload = out[hdr["payload_start"] : hdr["payload_end"]]
            r = decode(payload, bh, ty, enums=enums)
            assert r["closed"] and r["left"] == 0, (src, r)
            by = {x[1]: x for x in r["seq"]}
            expect = WAM_SOFTCLASS_MAG_MUZZLE_4606_IDS[ng]
            pos = by["ReplicatedBatch.AttachmentIds[]"][5]
            n = read_u(payload, pos, 16)
            assert n == len(expect), (src, n, expect)
            p2 = pos + 16
            ids = []
            for _ in range(n):
                _idx, iw = read_packed(payload, p2)
                p2 += iw
                ids.append(read_u(payload, p2, 16))
                p2 += 16
            assert tuple(ids) == expect
            if ng != WAM_PRIMARY:
                assert 4606 in ids and 151 in ids and 101 in ids
    finally:
        for k in (
            "WW3_WAM_STRIP_CATALOG", "WW3_WAM_SOFTCLASS_CATALOG", "WW3_WAM_SOFTCLASS_MODE",
            "WW3_WAM_SOFTCLASS_EXPORT",
        ):
            os.environ.pop(k, None)
    print("[ok] WAM open SoftClass mag_muzzle_4606 splice (151+101+4606 / 143+108)")


def test_wam_open_softclass_stub4606_and_open_only():
    """stub4606: capture order/count with 4606→151; OPEN_ONLY empties post-ACK SoftClass."""
    from _decode_rep_block import decode, layout
    import derive_rep_handles as D
    from cam_im_resend import (
        WAM_SOFTCLASS_STUB4606_IDS,
        build_wam_strip_resend_bits,
        rewrite_weapon_final_strip_wam,
        wam_softclass_open_only,
    )
    from repblock import read_u, read_packed

    for k in (
        "WW3_WAM_STRIP_CATALOG", "WW3_WAM_SOFTCLASS_CATALOG", "WW3_WAM_SOFTCLASS_MODE",
        "WW3_WAM_SOFTCLASS_EXPORT", "WW3_WAM_SOFTCLASS_OPEN_ONLY",
    ):
        os.environ.pop(k, None)
    os.environ["WW3_WAM_STRIP_CATALOG"] = "1"
    os.environ["WW3_WAM_SOFTCLASS_CATALOG"] = "1"
    os.environ["WW3_WAM_SOFTCLASS_MODE"] = "stub4606"
    os.environ["WW3_WAM_SOFTCLASS_EXPORT"] = "0"
    os.environ["WW3_WAM_SOFTCLASS_OPEN_ONLY"] = "1"
    try:
        assert wam_softclass_open_only() is True
        stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
        sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
        classes, structs = D.parse_sdk(sdk)
        enums = D.parse_enums(sdk)
        bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)
        for src, ng in WAM_OPEN_FINAL_SRCS.items():
            raw = [int(c) for c in stream[src]["payload"]]
            cap_hdr = _find_wam_block_header(raw, ng)
            cap_pl = raw[cap_hdr["payload_start"] : cap_hdr["payload_end"]]
            out = rewrite_weapon_final_strip_wam(raw, ng, batch_id=1)
            hdr = _find_wam_block_header(out, ng)
            payload = out[hdr["payload_start"] : hdr["payload_end"]]
            # Same bit length as capture (value swap only).
            assert len(payload) == len(cap_pl), (src, len(payload), len(cap_pl))
            r = decode(payload, bh, ty, enums=enums)
            assert r["closed"] and r["left"] == 0, (src, r)
            by = {x[1]: x for x in r["seq"]}
            expect = WAM_SOFTCLASS_STUB4606_IDS[ng]
            pos = by["ReplicatedBatch.AttachmentIds[]"][5]
            n = read_u(payload, pos, 16)
            assert n == len(expect)
            p2 = pos + 16
            ids = []
            for _ in range(n):
                _idx, iw = read_packed(payload, p2)
                p2 += iw
                ids.append(read_u(payload, p2, 16))
                p2 += 16
            assert tuple(ids) == expect
            assert 4606 not in ids
            # skins / MainId preserved from capture
            assert "DirectReplicatedSkinsIds.Parts.AttachmentsIds[]" in by
            if ng == WAM_SECONDARY:
                assert "DirectReplicatedSkinsIds.MainId" in by
            # post-ACK OPEN_ONLY → empty SoftClass
            resend = build_wam_strip_resend_bits(ng, batch_id=2)
            blocks = read_content_blocks(Bits(resend))
            assert len(blocks) == 1
            r2 = decode(blocks[0]["payload"], bh, ty, enums=enums)
            by2 = {x[1]: x for x in r2["seq"]}
            pos2 = by2["ReplicatedBatch.AttachmentIds[]"][5]
            assert read_u(blocks[0]["payload"], pos2, 16) == 0
    finally:
        for k in (
            "WW3_WAM_STRIP_CATALOG", "WW3_WAM_SOFTCLASS_CATALOG", "WW3_WAM_SOFTCLASS_MODE",
            "WW3_WAM_SOFTCLASS_EXPORT", "WW3_WAM_SOFTCLASS_OPEN_ONLY",
        ):
            os.environ.pop(k, None)
    print("[ok] WAM open SoftClass stub4606 + OPEN_ONLY (post-ACK empty)")


def test_hist_softclass_stub_4606_on_early_native_opens():
    """STUB_4606 under STRIP_CHANNELS=inv: early SoftClass 4606→151; inv emptied."""
    from _decode_rep_block import decode, layout
    import derive_rep_handles as D
    from cam_im_resend import (
        WAM_EARLY_CH4,
        WAM_EARLY_CH5,
        WAM_OPEN_FINAL_SRCS,
        WAM_PRIMARY,
        WAM_SECONDARY,
        WAM_SOFTCLASS_STUB4606_IDS,
        maybe_strip_wam_in_weapon_open_bits,
        maybe_stub_softclass_4606_in_weapon_open_bits,
        wam_open_strip_srcs,
        wam_softclass_stub_4606_enabled,
    )
    from repblock import read_u, read_packed

    for k in (
        "WW3_WAM_STRIP_CATALOG", "WW3_WAM_STRIP_CHANNELS",
        "WW3_WAM_SOFTCLASS_CATALOG", "WW3_WAM_SOFTCLASS_STUB_4606",
    ):
        os.environ.pop(k, None)
    os.environ["WW3_WAM_STRIP_CATALOG"] = "1"
    os.environ["WW3_WAM_STRIP_CHANNELS"] = "inv"
    os.environ["WW3_WAM_SOFTCLASS_CATALOG"] = "0"
    os.environ["WW3_WAM_SOFTCLASS_STUB_4606"] = "1"
    try:
        assert wam_softclass_stub_4606_enabled() is True
        assert set(wam_open_strip_srcs().values()) == {WAM_SECONDARY, WAM_PRIMARY}
        stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
        sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
        classes, structs = D.parse_sdk(sdk)
        enums = D.parse_enums(sdk)
        bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)
        for src, ng in WAM_OPEN_FINAL_SRCS.items():
            raw = [int(c) for c in stream[src]["payload"]]
            if ng in (WAM_SECONDARY, WAM_PRIMARY):
                stripped = maybe_strip_wam_in_weapon_open_bits(raw, src)
                assert stripped is not None
                assert maybe_stub_softclass_4606_in_weapon_open_bits(raw, src) is None
                continue
            assert ng in (WAM_EARLY_CH4, WAM_EARLY_CH5)
            assert maybe_strip_wam_in_weapon_open_bits(raw, src) is None
            stubbed = maybe_stub_softclass_4606_in_weapon_open_bits(raw, src)
            assert stubbed is not None
            hdr = _find_wam_block_header(stubbed, ng)
            pl = stubbed[hdr["payload_start"] : hdr["payload_end"]]
            r = decode(pl, bh, ty, enums=enums)
            assert r["closed"], (ng, r)
            by = {x[1]: x for x in r["seq"]}
            expect = WAM_SOFTCLASS_STUB4606_IDS[ng]
            pos = by["ReplicatedBatch.AttachmentIds[]"][5]
            n = read_u(pl, pos, 16)
            assert n == len(expect)
            p2 = pos + 16
            ids = []
            for _ in range(n):
                _idx, iw = read_packed(pl, p2)
                p2 += iw
                ids.append(read_u(pl, p2, 16))
                p2 += 16
            assert tuple(ids) == expect
            assert 4606 not in ids
            assert 151 in ids
    finally:
        for k in (
            "WW3_WAM_STRIP_CATALOG", "WW3_WAM_STRIP_CHANNELS",
            "WW3_WAM_SOFTCLASS_CATALOG", "WW3_WAM_SOFTCLASS_STUB_4606",
        ):
            os.environ.pop(k, None)
    print("[ok] hist SoftClass STUB_4606 on early native opens (inv strip)")


def test_hist_softclass_post_stub_4606_resend():
    """POST_STUB: early SoftClass keep-skins 4606→151 BatchID=2 (not open stub)."""
    from _decode_rep_block import decode, layout
    import derive_rep_handles as D
    from cam_im_resend import (
        WAM_EARLY_CH4,
        WAM_EARLY_CH5,
        WAM_SOFTCLASS_STUB4606_IDS,
        build_wam_post_stub_4606_resend_bits,
        wam_post_stub_4606_target_netguids,
        wam_softclass_post_stub_4606_enabled,
        wam_softclass_post_stub_mode,
    )
    from repblock import read_u, read_packed

    for k in (
        "WW3_WAM_STRIP_CATALOG", "WW3_WAM_STRIP_CHANNELS",
        "WW3_WAM_SOFTCLASS_POST_STUB_4606", "WW3_WAM_SOFTCLASS_POST_STUB_MODE",
        "WW3_WAM_SOFTCLASS_STUB_4606",
    ):
        os.environ.pop(k, None)
    os.environ["WW3_WAM_STRIP_CATALOG"] = "1"
    os.environ["WW3_WAM_STRIP_CHANNELS"] = "inv"
    os.environ["WW3_WAM_SOFTCLASS_POST_STUB_4606"] = "1"
    os.environ["WW3_WAM_SOFTCLASS_POST_STUB_MODE"] = "stub"
    os.environ["WW3_WAM_SOFTCLASS_STUB_4606"] = "0"
    try:
        assert wam_softclass_post_stub_4606_enabled() is True
        assert wam_softclass_post_stub_mode() == "stub"
        targets = wam_post_stub_4606_target_netguids()
        assert set(targets) == {WAM_EARLY_CH4, WAM_EARLY_CH5}
        sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
        classes, structs = D.parse_sdk(sdk)
        enums = D.parse_enums(sdk)
        bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)
        for ng in targets:
            bits = build_wam_post_stub_4606_resend_bits(ng, batch_id=2, mode="stub")
            # stably-named content: hasRepLayout | bIsActor=0 | packed NetGUID | …
            # Decode payload via write path: find AttachmentIds after content hdr.
            from cam_im_resend import build_wam_post_stub_4606_payload
            pl = build_wam_post_stub_4606_payload(ng, batch_id=2, mode="stub")
            r = decode(pl, bh, ty, enums=enums)
            assert r["closed"], (ng, r)
            by = {x[1]: x for x in r["seq"]}
            assert read_u(pl, by["ReplicatedBatch.BatchID"][5], 32) == 2
            expect = WAM_SOFTCLASS_STUB4606_IDS[ng]
            pos = by["ReplicatedBatch.AttachmentIds[]"][5]
            n = read_u(pl, pos, 16)
            assert n == len(expect)
            p2 = pos + 16
            ids = []
            for _ in range(n):
                _idx, iw = read_packed(pl, p2)
                p2 += iw
                ids.append(read_u(pl, p2, 16))
                p2 += 16
            assert tuple(ids) == expect
            assert 4606 not in ids
            # empty mode cancels SoftClass
            empty_pl = build_wam_post_stub_4606_payload(ng, batch_id=2, mode="empty")
            er = decode(empty_pl, bh, ty, enums=enums)
            assert er["closed"], (ng, er)
            eby = {x[1]: x for x in er["seq"]}
            epos = eby["ReplicatedBatch.AttachmentIds[]"][5]
            assert read_u(empty_pl, epos, 16) == 0
    finally:
        for k in (
            "WW3_WAM_STRIP_CATALOG", "WW3_WAM_STRIP_CHANNELS",
            "WW3_WAM_SOFTCLASS_POST_STUB_4606", "WW3_WAM_SOFTCLASS_POST_STUB_MODE",
            "WW3_WAM_SOFTCLASS_STUB_4606",
        ):
            os.environ.pop(k, None)
    print("[ok] hist SoftClass POST_STUB 4606 resend (stub+empty)")


def test_early_empty_parts_reinforce():
    """Early SoftClass BatchID=2 keep SoftClass ids, empty Parts (no PE)."""
    from _decode_rep_block import decode, layout
    import derive_rep_handles as D
    from cam_im_resend import (
        CAPTURE_WAM_EARLY_ATTACHMENT_IDS,
        WAM_EARLY_CH4,
        WAM_EARLY_CH5,
        build_wam_early_empty_parts_resend_bits,
        wam_early_empty_parts_reinforce_enabled,
    )
    from repblock import read_u

    os.environ.pop("WW3_WAM_EARLY_EMPTY_PARTS_REINFORCE", None)
    assert wam_early_empty_parts_reinforce_enabled() is False
    os.environ["WW3_WAM_EARLY_EMPTY_PARTS_REINFORCE"] = "1"
    try:
        assert wam_early_empty_parts_reinforce_enabled() is True
        sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
        classes, structs = D.parse_sdk(sdk)
        enums = D.parse_enums(sdk)
        bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)
        from cam_im_resend import build_wam_stripped_catalog_payload
        for ng in (WAM_EARLY_CH4, WAM_EARLY_CH5):
            bits = build_wam_early_empty_parts_resend_bits(ng, batch_id=2)
            assert len(bits) > 64
            pl = build_wam_stripped_catalog_payload(
                batch_id=2,
                attachment_ids=CAPTURE_WAM_EARLY_ATTACHMENT_IDS,
            )
            r = decode(pl, bh, ty, enums=enums)
            assert r["closed"], (ng, r)
            by = {x[1]: x for x in r["seq"]}
            assert read_u(pl, by["ReplicatedBatch.BatchID"][5], 32) == 2
            ids = []
            pos = by["ReplicatedBatch.AttachmentIds[]"][5]
            # uint16 array: packed count then values — use decode seq payload
            att = [x for x in r["seq"] if x[1] == "ReplicatedBatch.AttachmentIds[]"]
            assert att, r["seq"]
            skins = [
                x for x in r["seq"]
                if "DirectReplicatedSkinsIds.Parts.AttachmentsIds" in x[1]
            ]
            # empty Parts array present
            assert skins, r["seq"]
    finally:
        os.environ.pop("WW3_WAM_EARLY_EMPTY_PARTS_REINFORCE", None)
    print("[ok] early SoftClass empty-Parts reinforce payload")


def test_wam_softclass_keep_skins_post_ack():
    """KEEP_SKINS: post-ACK BatchID=2 SoftClass keeps capture skins/MainId."""
    from _decode_rep_block import decode, layout
    import derive_rep_handles as D
    from cam_im_resend import (
        CAPTURE_WAM_SECONDARY_MAIN_ID,
        WAM_SOFTCLASS_FULL_IDS,
        build_wam_strip_resend_bits,
        extract_all_wam_open_payloads,
        wam_softclass_keep_skins,
    )
    from repblock import read_u, read_packed

    for k in (
        "WW3_WAM_STRIP_CATALOG", "WW3_WAM_SOFTCLASS_CATALOG", "WW3_WAM_SOFTCLASS_MODE",
        "WW3_WAM_SOFTCLASS_EXPORT", "WW3_WAM_SOFTCLASS_OPEN_ONLY",
        "WW3_WAM_SOFTCLASS_KEEP_SKINS",
    ):
        os.environ.pop(k, None)
    os.environ["WW3_WAM_STRIP_CATALOG"] = "1"
    os.environ["WW3_WAM_SOFTCLASS_CATALOG"] = "1"
    os.environ["WW3_WAM_SOFTCLASS_MODE"] = "full"
    os.environ["WW3_WAM_SOFTCLASS_EXPORT"] = "0"
    os.environ["WW3_WAM_SOFTCLASS_OPEN_ONLY"] = "0"
    os.environ["WW3_WAM_SOFTCLASS_KEEP_SKINS"] = "1"
    try:
        assert wam_softclass_keep_skins() is True
        caps = extract_all_wam_open_payloads()
        sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
        classes, structs = D.parse_sdk(sdk)
        enums = D.parse_enums(sdk)
        bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)
        for ng in WAM_STRIP_NETGUIDS:
            cap = caps[ng]
            cap_r = decode(cap, bh, ty, enums=enums)
            assert cap_r["closed"], (ng, cap_r)
            cap_by = {x[1]: x for x in cap_r["seq"]}
            assert read_u(cap, cap_by["ReplicatedBatch.BatchID"][5], 32) == 1

            resend = build_wam_strip_resend_bits(ng, batch_id=2)
            blocks = read_content_blocks(Bits(resend))
            assert len(blocks) == 1 and blocks[0]["subNetGUID"] == ng
            pl = blocks[0]["payload"]
            # MODE=full: AttachmentIds unchanged → only BatchID bits differ.
            assert len(pl) == len(cap), (ng, len(pl), len(cap))
            r = decode(pl, bh, ty, enums=enums)
            assert r["closed"] and r["left"] == 0, (ng, r)
            by = {x[1]: x for x in r["seq"]}
            assert read_u(pl, by["ReplicatedBatch.BatchID"][5], 32) == 2
            expect = WAM_SOFTCLASS_FULL_IDS[ng]
            pos = by["ReplicatedBatch.AttachmentIds[]"][5]
            n = read_u(pl, pos, 16)
            assert n == len(expect)
            p2 = pos + 16
            ids = []
            for _ in range(n):
                _idx, iw = read_packed(pl, p2)
                p2 += iw
                ids.append(read_u(pl, p2, 16))
                p2 += 16
            assert tuple(ids) == expect
            assert "DirectReplicatedSkinsIds.Parts.AttachmentsIds[]" in by
            skins_n = read_u(
                pl, by["DirectReplicatedSkinsIds.Parts.AttachmentsIds[]"][5], 16)
            assert skins_n == 3, (ng, skins_n)
            if ng == WAM_SECONDARY:
                assert "DirectReplicatedSkinsIds.MainId" in by
                assert read_u(
                    pl, by["DirectReplicatedSkinsIds.MainId"][5], 16
                ) == CAPTURE_WAM_SECONDARY_MAIN_ID
            else:
                assert "DirectReplicatedSkinsIds.MainId" not in by
    finally:
        for k in (
            "WW3_WAM_STRIP_CATALOG", "WW3_WAM_SOFTCLASS_CATALOG", "WW3_WAM_SOFTCLASS_MODE",
            "WW3_WAM_SOFTCLASS_EXPORT", "WW3_WAM_SOFTCLASS_OPEN_ONLY",
            "WW3_WAM_SOFTCLASS_KEEP_SKINS",
        ):
            os.environ.pop(k, None)
    print("[ok] WAM SoftClass KEEP_SKINS post-ACK (BatchID=2, skins/MainId kept)")


def test_wam_spawn_attach_cam_pattern():
    """WW3_WAM_SPAWN_ATTACH: export+stably0 BP_WP_* + WAM strip refs those GUIDs."""
    from _decode_rep_block import decode, layout
    import derive_rep_handles as D
    from cam_im_resend import (
        WAM_SPAWN_ATTACHMENTS,
        build_wam_attach_spawn_packet_bits,
        wam_spawn_attach_enabled,
        wam_spawn_specs_for,
        wam_spawn_strip_keep_enabled,
        wam_spawn_target_netguids,
    )
    from repblock import read_u, read_packed

    for k in (
        "WW3_WAM_SPAWN_ATTACH", "WW3_WAM_KEEP_DYNAMIC", "WW3_WAM_STRIP_CATALOG",
        "WW3_WAM_SPAWN_CHANNELS", "WW3_WAM_SPAWN_ATT_LIMIT", "WW3_WAM_SPAWN_STRIP_KEEP",
        "WW3_WAM_SPAWN_EXPORT", "WW3_WAM_SPAWN_CONTENT", "WW3_WAM_SPAWN_PAYLOAD",
        "WW3_WAM_SPAWN_CHECKSUM", "WW3_WAM_SPAWN_HOST",
    ):
        os.environ.pop(k, None)
    assert wam_spawn_attach_enabled() is False

    os.environ["WW3_WAM_SPAWN_ATTACH"] = "1"
    os.environ["WW3_WAM_STRIP_CATALOG"] = "1"
    try:
        assert wam_spawn_attach_enabled() is True
        assert wam_spawn_strip_keep_enabled() is True
        assert wam_spawn_target_netguids() == WAM_STRIP_NETGUIDS
        # Glock secondary: Mag_108 + Rail_086
        sec = WAM_SPAWN_ATTACHMENTS[WAM_SECONDARY]
        assert [s.item_id for s in sec] == [151, 4606]
        assert all(s.class_name.startswith("BP_WP_") for s in sec)
        assert all(s.package_path.startswith("/Game/Blueprints/Weapons/Attachments/")
                   for s in sec)
        # HK417 primary: Mag_116 + Barrel_033
        prim = WAM_SPAWN_ATTACHMENTS[WAM_PRIMARY]
        assert [s.item_id for s in prim] == [143, 295]

        exp, spawn, dyns = build_wam_attach_spawn_packet_bits(WAM_SECONDARY)
        assert dyns == (9608, 9610)
        assert len(exp) > 0 and len(spawn) > 0
        # Export block parses
        pm = PackageMap()
        er = pm.read_export_bunch(exp)
        assert er["num"] == 2
        assert "BP_WP_Magazine_108_01_C" in pm.guid_to_path.values()
        assert "BP_WP_Rail_086_01_C" in pm.guid_to_path.values()
        # Spawn content: two stably=0 blocks with class GUIDs
        blocks = read_content_blocks(Bits(spawn))
        assert len(blocks) == 2
        assert blocks[0]["subNetGUID"] == 9608 and blocks[0]["stablyNamed"] == 0
        assert blocks[1]["subNetGUID"] == 9610 and blocks[1]["stablyNamed"] == 0
        assert blocks[0]["classNetGUID"] == sec[0].class_netguid
        assert blocks[1]["classNetGUID"] == sec[1].class_netguid

        # Strip resend refs spawned dyn GUIDs (not FireType keep)
        sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
        classes, structs = D.parse_sdk(sdk)
        enums = D.parse_enums(sdk)
        bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)
        bits = build_wam_strip_resend_bits(WAM_SECONDARY, batch_id=2)
        wam_blocks = read_content_blocks(Bits(bits))
        assert len(wam_blocks) == 1
        pl = wam_blocks[0]["payload"]
        rr = decode(pl, bh, ty, enums=enums)
        assert rr["closed"] and rr["left"] == 0, rr
        by = {x[1]: x for x in rr["seq"]}
        assert read_u(pl, by["ReplicatedBatch.NumReplicatedAttachments"][5], 8) == 2
        p = by["ReplicatedBatch.ReplicatedAttachments[]"][5]
        assert read_u(pl, p, 16) == 2
        p2 = p + 16
        gids = []
        for _ in range(2):
            _idx, iw = read_packed(pl, p2)
            p2 += iw
            gid, gw = read_packed(pl, p2)
            p2 += gw
            gids.append(gid)
        assert gids == [9608, 9610]
        # SPAWN supersedes KEEP_DYNAMIC FireType GUIDs
        os.environ["WW3_WAM_KEEP_DYNAMIC"] = "1"
        bits2 = build_wam_strip_resend_bits(WAM_SECONDARY, batch_id=2)
        pl2 = read_content_blocks(Bits(bits2))[0]["payload"]
        rr2 = decode(pl2, bh, ty, enums=enums)
        by2 = {x[1]: x for x in rr2["seq"]}
        p = by2["ReplicatedBatch.ReplicatedAttachments[]"][5]
        p2 = p + 16
        gids2 = []
        for _ in range(2):
            _idx, iw = read_packed(pl2, p2)
            p2 += iw
            gid, gw = read_packed(pl2, p2)
            p2 += gw
            gids2.append(gid)
        assert gids2 == [9608, 9610]
        assert 9416 not in gids2  # FireType keep not used

        # Bisect: single channel + att limit + strip keep off
        os.environ["WW3_WAM_SPAWN_CHANNELS"] = "87"
        os.environ["WW3_WAM_SPAWN_ATT_LIMIT"] = "1"
        os.environ["WW3_WAM_SPAWN_STRIP_KEEP"] = "0"
        assert wam_spawn_target_netguids() == (WAM_PRIMARY,)
        assert len(wam_spawn_specs_for(WAM_PRIMARY)) == 1
        assert wam_spawn_specs_for(WAM_SECONDARY) == ()
        assert wam_spawn_strip_keep_enabled() is False
        bits3 = build_wam_strip_resend_bits(WAM_PRIMARY, batch_id=2)
        pl3 = read_content_blocks(Bits(bits3))[0]["payload"]
        rr3 = decode(pl3, bh, ty, enums=enums)
        by3 = {x[1]: x for x in rr3["seq"]}
        assert "ReplicatedBatch.ReplicatedAttachments[]" not in by3

        # host=pawn: shared ch3; collect deduped specs for Mag_116 only (ch87×1)
        from cam_im_resend import (
            collect_wam_spawn_specs,
            wam_spawn_host_ch,
            wam_spawn_host_is_shared,
        )
        os.environ["WW3_WAM_SPAWN_HOST"] = "pawn"
        os.environ["WW3_WAM_SPAWN_STRIP_KEEP"] = "1"
        assert wam_spawn_host_is_shared() is True
        assert wam_spawn_host_ch() == 3
        specs = collect_wam_spawn_specs()
        assert len(specs) == 1 and specs[0].dyn_netguid == 9612
        bits4 = build_wam_strip_resend_bits(WAM_PRIMARY, batch_id=2)
        pl4 = read_content_blocks(Bits(bits4))[0]["payload"]
        rr4 = decode(pl4, bh, ty, enums=enums)
        by4 = {x[1]: x for x in rr4["seq"]}
        assert read_u(pl4, by4["ReplicatedBatch.NumReplicatedAttachments"][5], 8) == 1
    finally:
        for k in (
            "WW3_WAM_SPAWN_ATTACH", "WW3_WAM_KEEP_DYNAMIC", "WW3_WAM_STRIP_CATALOG",
            "WW3_WAM_SPAWN_CHANNELS", "WW3_WAM_SPAWN_ATT_LIMIT", "WW3_WAM_SPAWN_STRIP_KEEP",
            "WW3_WAM_SPAWN_EXPORT", "WW3_WAM_SPAWN_CONTENT", "WW3_WAM_SPAWN_PAYLOAD",
            "WW3_WAM_SPAWN_CHECKSUM", "WW3_WAM_SPAWN_HOST",
        ):
            os.environ.pop(k, None)
    print("[ok] WAM_SPAWN_ATTACH export+stably0 + strip ReplicatedAttachments")


def test_wam_keep_clothing_cam_pattern():
    """WW3_WAM_KEEP_CLOTHING: post-ACK strip refs hat/chest 9404/9406."""
    from _decode_rep_block import decode, layout
    import derive_rep_handles as D
    from cam_im_resend import wam_keep_clothing_enabled
    from repblock import read_u, read_packed

    for k in (
        "WW3_WAM_KEEP_CLOTHING", "WW3_WAM_SOFTCLASS_CATALOG", "WW3_WAM_SPAWN_ATTACH",
        "WW3_WAM_KEEP_DYNAMIC", "WW3_WAM_STRIP_CATALOG",
    ):
        os.environ.pop(k, None)
    assert wam_keep_clothing_enabled() is False
    os.environ["WW3_WAM_KEEP_CLOTHING"] = "1"
    os.environ["WW3_WAM_STRIP_CATALOG"] = "1"
    try:
        assert wam_keep_clothing_enabled() is True
        sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
        classes, structs = D.parse_sdk(sdk)
        enums = D.parse_enums(sdk)
        bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)
        bits = build_wam_strip_resend_bits(WAM_SECONDARY, batch_id=2)
        pl = read_content_blocks(Bits(bits))[0]["payload"]
        rr = decode(pl, bh, ty, enums=enums)
        assert rr["closed"] and rr["left"] == 0, rr
        by = {x[1]: x for x in rr["seq"]}
        assert read_u(pl, by["ReplicatedBatch.AttachmentIds[]"][5], 16) == 0
        assert read_u(pl, by["ReplicatedBatch.NumReplicatedAttachments"][5], 8) == 2
        p = by["ReplicatedBatch.ReplicatedAttachments[]"][5]
        assert read_u(pl, p, 16) == 2
        p2 = p + 16
        gids = []
        for _ in range(2):
            _idx, iw = read_packed(pl, p2)
            p2 += iw
            gid, gw = read_packed(pl, p2)
            p2 += gw
            gids.append(gid)
        assert gids == [HAT_NETGUID, CHEST_NETGUID]
    finally:
        for k in (
            "WW3_WAM_KEEP_CLOTHING", "WW3_WAM_SOFTCLASS_CATALOG",
            "WW3_WAM_SPAWN_ATTACH", "WW3_WAM_KEEP_DYNAMIC", "WW3_WAM_STRIP_CATALOG",
        ):
            os.environ.pop(k, None)
    print("[ok] WAM_KEEP_CLOTHING refs 9404+9406")


def test_wam_softclass_mag_catalog():
    """WW3_WAM_SOFTCLASS_MODE=mag (default): Mag-only SoftClass ids, no keep."""
    from _decode_rep_block import decode, layout
    import derive_rep_handles as D
    from cam_im_resend import (
        WAM_SOFTCLASS_MAG_IDS,
        WAM_SOFTCLASS_MIN_IDS,
        collect_wam_softclass_export_specs,
        wam_softclass_catalog_enabled,
        wam_softclass_ids_for,
        wam_softclass_mode,
    )
    from repblock import read_u, read_packed

    for k in (
        "WW3_WAM_SOFTCLASS_CATALOG", "WW3_WAM_SOFTCLASS_EXPORT",
        "WW3_WAM_SOFTCLASS_MODE",
        "WW3_WAM_KEEP_CLOTHING", "WW3_WAM_SPAWN_ATTACH", "WW3_WAM_KEEP_DYNAMIC",
        "WW3_WAM_STRIP_CATALOG",
    ):
        os.environ.pop(k, None)
    os.environ["WW3_WAM_SOFTCLASS_CATALOG"] = "1"
    os.environ["WW3_WAM_STRIP_CATALOG"] = "1"
    try:
        assert wam_softclass_catalog_enabled() is True
        assert wam_softclass_mode() == "mag"
        sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
        classes, structs = D.parse_sdk(sdk)
        enums = D.parse_enums(sdk)
        bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)
        for ng, expect_ids in WAM_SOFTCLASS_MAG_IDS.items():
            assert wam_softclass_ids_for(ng) == expect_ids
            bits = build_wam_strip_resend_bits(ng, batch_id=2)
            pl = read_content_blocks(Bits(bits))[0]["payload"]
            rr = decode(pl, bh, ty, enums=enums)
            assert rr["closed"] and rr["left"] == 0, (ng, rr)
            by = {x[1]: x for x in rr["seq"]}
            assert "ReplicatedBatch.NumReplicatedAttachments" not in by
            pos = by["ReplicatedBatch.AttachmentIds[]"][5]
            n = read_u(pl, pos, 16)
            assert n == len(expect_ids) == 1
            p2 = pos + 16
            _idx, iw = read_packed(pl, p2)
            p2 += iw
            assert read_u(pl, p2, 16) == expect_ids[0]
        # Mag-only export = Mag_108 + Mag_116 (2 classes).
        exp = collect_wam_softclass_export_specs()
        assert {s.item_id for s in exp} == {151, 143}
        assert all(s.class_name.startswith("BP_WP_Magazine_") for s in exp)
        # min mode still Mag+Rail.
        os.environ["WW3_WAM_SOFTCLASS_MODE"] = "min"
        assert wam_softclass_mode() == "min"
        assert wam_softclass_ids_for(9418) == WAM_SOFTCLASS_MIN_IDS[9418]
    finally:
        for k in (
            "WW3_WAM_SOFTCLASS_CATALOG", "WW3_WAM_SOFTCLASS_EXPORT",
            "WW3_WAM_SOFTCLASS_MODE",
            "WW3_WAM_KEEP_CLOTHING", "WW3_WAM_SPAWN_ATTACH", "WW3_WAM_KEEP_DYNAMIC",
            "WW3_WAM_STRIP_CATALOG",
        ):
            os.environ.pop(k, None)
    print("[ok] WAM_SOFTCLASS_MODE=mag Mag-only AttachmentIds exact-consume")


def test_wam_softclass_min_catalog():
    """WW3_WAM_SOFTCLASS_MODE=min: Mag+Rail SoftClass AttachmentIds, no keep."""
    from _decode_rep_block import decode, layout
    import derive_rep_handles as D
    from cam_im_resend import (
        WAM_SOFTCLASS_MIN_IDS,
        wam_softclass_catalog_enabled,
        wam_softclass_export_enabled,
    )
    from repblock import read_u, read_packed

    for k in (
        "WW3_WAM_SOFTCLASS_CATALOG", "WW3_WAM_SOFTCLASS_EXPORT",
        "WW3_WAM_SOFTCLASS_MODE",
        "WW3_WAM_KEEP_CLOTHING", "WW3_WAM_SPAWN_ATTACH", "WW3_WAM_KEEP_DYNAMIC",
        "WW3_WAM_STRIP_CATALOG",
    ):
        os.environ.pop(k, None)
    assert wam_softclass_catalog_enabled() is False
    os.environ["WW3_WAM_SOFTCLASS_CATALOG"] = "1"
    os.environ["WW3_WAM_SOFTCLASS_MODE"] = "min"
    os.environ["WW3_WAM_STRIP_CATALOG"] = "1"
    try:
        assert wam_softclass_catalog_enabled() is True
        assert wam_softclass_export_enabled() is True  # default on when catalog on
        sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
        classes, structs = D.parse_sdk(sdk)
        enums = D.parse_enums(sdk)
        bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)
        for ng, expect_ids in WAM_SOFTCLASS_MIN_IDS.items():
            bits = build_wam_strip_resend_bits(ng, batch_id=2)
            pl = read_content_blocks(Bits(bits))[0]["payload"]
            rr = decode(pl, bh, ty, enums=enums)
            assert rr["closed"] and rr["left"] == 0, (ng, rr)
            by = {x[1]: x for x in rr["seq"]}
            assert "ReplicatedBatch.NumReplicatedAttachments" not in by
            pos = by["ReplicatedBatch.AttachmentIds[]"][5]
            n = read_u(pl, pos, 16)
            assert n == len(expect_ids)
            p2 = pos + 16
            ids = []
            for _ in range(n):
                _idx, iw = read_packed(pl, p2)
                p2 += iw
                ids.append(read_u(pl, p2, 16))
                p2 += 16
            assert tuple(ids) == expect_ids
    finally:
        for k in (
            "WW3_WAM_SOFTCLASS_CATALOG", "WW3_WAM_SOFTCLASS_EXPORT",
            "WW3_WAM_SOFTCLASS_MODE",
            "WW3_WAM_KEEP_CLOTHING", "WW3_WAM_SPAWN_ATTACH", "WW3_WAM_KEEP_DYNAMIC",
            "WW3_WAM_STRIP_CATALOG",
        ):
            os.environ.pop(k, None)
    print("[ok] WAM_SOFTCLASS_CATALOG min AttachmentIds exact-consume")


def test_wam_softclass_warm_export_specs():
    """WARM_EXPORT collects Mag/Rail (+ early SoftClass) package paths; catalog-independent."""
    from cam_im_resend import (
        WAM_SOFTCLASS_WARM_IDS,
        collect_wam_softclass_warm_export_specs,
        wam_softclass_warm_export_enabled,
    )

    os.environ.pop("WW3_WAM_SOFTCLASS_WARM_EXPORT", None)
    os.environ.pop("WW3_WAM_SOFTCLASS_CATALOG", None)
    assert wam_softclass_warm_export_enabled() is False
    os.environ["WW3_WAM_SOFTCLASS_WARM_EXPORT"] = "1"
    os.environ["WW3_WAM_SOFTCLASS_CATALOG"] = "0"
    try:
        assert wam_softclass_warm_export_enabled() is True
        specs = collect_wam_softclass_warm_export_specs()
        ids = [s.item_id for s in specs]
        assert ids[0] == 151 and ids[1] == 4606, ids
        assert 143 in ids and 295 in ids
        assert set(ids) == {151, 4606, 143, 295}
        assert all(s.class_name.startswith("BP_WP_") for s in specs)
        assert any(s.class_name == "BP_WP_Magazine_108_01_C" for s in specs)
        assert any(s.class_name == "BP_WP_Rail_086_01_C" for s in specs)
        # Export bits stay under drip MAX_PAYLOAD_BITS (~6000) — 10-class warm
        # previously sent 10801 bits and CHANNEL CLOSEd ch0.
        from cam_im_resend import build_wam_attach_export_bits
        bits = build_wam_attach_export_bits(specs)
        assert 100 < len(bits) < 6000, len(bits)
    finally:
        os.environ.pop("WW3_WAM_SOFTCLASS_WARM_EXPORT", None)
        os.environ.pop("WW3_WAM_SOFTCLASS_CATALOG", None)
    print("[ok] SoftClass WARM EXPORT Mag/Rail specs (catalog-independent, export-only)")


if __name__ == "__main__":
    test_clothing_exact_consume_with_class_guid()
    test_extract_cam_im_payloads()
    test_resend_roundtrip()
    test_inv_attach_ranges_splice()
    test_wam_in_weapon_opens()
    test_after_ack_flag_default_off()
    test_inv_attach_gate_acks_and_timeout()
    test_ack_audit_tags_inv_channels()
    test_clothing_resend_specs()
    test_im_softclassptr_exact_consume()
    test_cam_replicated_attachments_are_hat_chest()
    test_cam_strip_catalog_exact_consume()
    test_wam_catalog_softclass_surface()
    test_wam_strip_catalog_exact_consume()
    test_wam_early_ch4_ch5_softclass_4606_surface()
    test_wam_strip_inside_weapon_open_finals()
    test_wam_open_softclass_mag_ids()
    test_wam_open_softclass_mag_muzzle_ids()
    test_wam_open_softclass_mag_muzzle_barrel_ids()
    test_wam_open_softclass_mag_muzzle_4606_ids()
    test_wam_spawn_attach_cam_pattern()
    test_wam_keep_clothing_cam_pattern()
    test_wam_softclass_mag_catalog()
    test_wam_softclass_min_catalog()
    test_wam_softclass_warm_export_specs()
    print("all passed")
