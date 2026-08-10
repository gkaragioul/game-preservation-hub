#!/usr/bin/env python3
"""Extract / re-frame CharacterAttachmentManager + InventoryManager from clothing.

Capture src 212–213 (ch3) carries, after hat/chest dynamic spawns:

  * sub 9374 CharacterAttachmentManager — 705-bit ReplicatedBatch (exact-consume)
  * sub 9384 InventoryManager — 1978-bit WeaponsPreloadRequest / inventory refs

Those two blocks sit *after* stably=0 dynamic subobjects (9404/9406). If the client
fails creating a dynamic attachment mid-bunch, UE can abandon the rest of the bunch
and the CAM/IM tails never apply — matching live ACK of clothing with checklist still
false. Re-sending just the stably-named CAM+IM blocks after local weapons map gives
OnRep another shot with PrimaryWeapon=9410 / Secondary=9412 resolvable.

CAM ReplicatedBatch.ReplicatedAttachments[] = [9404, 9406] (hat/chest). Checklist
`CharacterAttachments` flips on `OnSynchronized: Character Attachments` after
`OnRep_ReplicatedBatch` — which needs those GUIDs mapped. SoftClassPtr decode of IM
is exact-consume (gadget FString paths); SoftClassPtr was a tooling stall, not a
wire abort. `WW3_CLOTHING_RESEND=1` re-plays the full clothing partial chain
(exports + hat/chest + CAM + IM) after the ACK gate so 9404/9406 exist for CAM.

Weapon opens already carry WeaponAttachmentManager RepLayout (ch86 sub 9418 = 505 bits,
ch87 sub 9426 = 457 bits) — not missing from the early stream. Optional
`WW3_WPN_ATTACH=1` re-sends those WAM blocks on their own channels after the same
ACK/delay gate as CAM/IM.

Content-block header for stably-named subobjects (no class GUID):
  hasRepLayout | bIsActor=0 | packed NetGUID | bStablyNamed=1 | packed NumBits | payload

For stably=0 the class NetGUID is packed between bStablyNamed and NumBits — see
`actor_channel.read_content_blocks`.

Flags:
  WW3_INV_ATTACH=1           — bootstrap weapon opens + enable CAM/IM resend
  WW3_CAM_IM_AFTER_ACK=1     — hold CAM/IM (and WPN_ATTACH) until clothing+ch86/87 ACKED
  WW3_CAM_IM_ACK_TIMEOUT_S   — fallback wait from ownership_done (default 3.0)
  WW3_WPN_ATTACH=1           — also resend WAM 9418/9426 after the same gate
  WW3_CLOTHING_RESEND=1      — after gate, resend full clothing 212–213 (not CAM/IM-only)
  WW3_CAM_STRIP_CATALOG=1    — after gate, resend CAM with empty AttachmentIds + empty
                               DirectReplicatedSkinsIds.Parts (BatchID bumped). Keeps
                               ReplicatedAttachments=[9404,9406]. Removes SoftClass waits
                               on the 9 non-channel catalog IDs + 5 skin SoftClasses that
                               block OnSynchronized: Character Attachments offline.
  WW3_WAM_STRIP_CATALOG=1    — empty WAM AttachmentIds/skins Parts (BatchID=2 pattern).
                               (1) Rewrite weapon-open FINAL partials so the first OnRep
                               never arms SoftClass — ownership early Glocks ch4/ch5
                               (src 15/17 → WAM 8314/7956, catalog id 4606) AND INV_ATTACH
                               ch86/87 (src 258/260 → 9418/9426). (2) After ACK gate, also
                               send stripped WAM-only blocks on ch4/5/86/87 (BatchID=2).
                               Capture WAMs carry catalog IDs and no ReplicatedAttachments —
                               SoftClass waits block OnAttachmentManagerSynchronized offline.
                               Do NOT write MainId=0: capture omits MainId on 3/4 opens
                               (only secondary 9418 had MainId=9246); forcing MainId=0
                               Dirties OnRep_ReplicatedSkinsIds / MainSkinLoadedClass.
  WW3_WAM_STRIP_CHANNELS     — which WAMs open+post-ACK strip touch: ``all`` (default
                               ch4/5/86/87), ``inv`` / ``074114`` (ch86/87 only —
                               historical Sync-arm surface: SoftClass stays on early
                               Glock opens), or ``early`` (ch4/5 only).
  WW3_WAM_KEEP_DYNAMIC=1     — post-ACK strip also refs stably=0 subs after each
                               WAM (8312/7954/9416/9424). **Off by default — those
                               are FireType spawns (BP_Glock17FireType_01_C), not
                               UWW3Attachment.** Wrong CAM analogy; does not help WA.
  WW3_WAM_KEEP_CLOTHING=1    — post-ACK strip refs already-mapped clothing hat/chest
                               NetGUIDs 9404/9406 in ReplicatedAttachments[] (CAM
                               pattern). Empty SoftClass catalog. No BP_WP_* spawn —
                               those UObjects exist on pawn ch3 after CLOTHING_RESEND.
  WW3_WAM_SOFTCLASS_CATALOG=1 — SoftClass AttachmentIds on open AND post-ACK
                               BatchID=2 (same MODE ids). Opens: in-place splice
                               of AttachmentIds[] inside capture WAM RepLayout
                               (preserve skins / MainId / handle set) — full
                               strip rebuild never arms Synchronized. Post-ACK
                               still uses stripped SoftClass reinforce unless
                               WW3_WAM_SOFTCLASS_OPEN_ONLY=1 (open SoftClass only;
                               post-ACK empty catalog — avoids BatchID=2 skins=[]
                               / MainId-omit overwrite of capture open shape) or
                               WW3_WAM_SOFTCLASS_KEEP_SKINS=1 (post-ACK BatchID=2
                               SoftClass reinforce that **keeps** capture skins
                               Parts / MainId — Sync-arm bisect vs empty strip).
                               Optional WW3_WAM_SOFTCLASS_EXPORT=1 preloads
                               SoftClass packages via package-map (safe; no
                               stably=0 content).
  WW3_WAM_SOFTCLASS_WARM_EXPORT=1 — early package-map SoftClass Mag/Rail (and
                               other known early SoftClass BP_WP_*) on pawn ch3
                               BEFORE ownership early Glock SoftClass OnRep
                               (src 15/17). Independent of SOFTCLASS_CATALOG —
                               keeps native SoftClass open bits (hist074114).
                               Export-only; no BP_WP_* stably=0 content (no CLOSE).
                               Use to warm SoftClassPtr / already-loaded package
                               residency before SoftClass AttachmentIds fire.
  WW3_WAM_SOFTCLASS_STUB_4606=1 — on early SoftClass opens that STRIP_CHANNELS
                               leaves native (hist ``inv``), splice SoftClass
                               Rail **4606→Mag 151** in-place (skins/MainId/
                               order kept). **Open stub kills Mag NewObject** —
                               keep default 0; use POST_STUB after Mag*_C_0.
  WW3_WAM_SOFTCLASS_POST_STUB_4606=1 — mid-flight finish/skip SoftClass 4606
                               AFTER Mag NewObject: post-ACK SoftClass reinforce
                               on early native SoftClass WAMs (not open-stripped)
                               with 4606→151 (skins/MainId/order kept, BatchID=2)
                               or empty SoftClass cancel. Does not CLOSE.
  WW3_WAM_SOFTCLASS_POST_STUB_DELAY_MS — hold POST_STUB after ACK gate (default
                               2500) so Mag*_C_0 can arm before 4606 is skipped.
  WW3_WAM_SOFTCLASS_POST_STUB_WAIT_FILE — optional absolute/relative path; when
                               set, also wait until the file exists (agent touches
                               after heap Mag*_C_0 / Synchronized detect).
  WW3_WAM_SOFTCLASS_POST_STUB_MODE — ``stub`` (default: 4606→151 keep-skins) or
                               ``empty`` (cancel SoftClass catalog).
  WW3_WAM_EARLY_EMPTY_PARTS_REINFORCE=1 — after ACK gate, BatchID=2 SoftClass
                               reinforce on early native SoftClass WAMs (ch4/5;
                               hist STRIP_CHANNELS=inv leaves them alone). Keeps
                               capture SoftClass AttachmentIds, **empties skins
                               Parts** (clears 0xFFFF ghost), omits MainId. Goal:
                               game-thread OnRep/Check re-entry after SoftClass
                               CreateAttachment — no off-thread ProcessEvent.
                               Independent of SOFTCLASS_CATALOG. Default 0.
  WW3_WAM_SOFTCLASS_MODE     — mag (default: Mag only 151/143 — never arms
                               Synchronized via splice) |
                               mag_muzzle (Mag+Muzzle 151+101 / 143+108 — first
                               non-Rail bisect; paths offline) |
                               mag_barrel (Mag+Barrel 151+304 / 143+295) |
                               mag_muzzle_barrel (Mag+Muzzle+Barrel 151+101+304 /
                               143+108+295 — Mag+two non-Rail; no 4606) |
                               mag_muzzle_4606 (Mag+Muzzle+Rail 151+101+4606 /
                               143+108 — 4606 presence probe; EXPORT=0 preferred) |
                               norail (capture catalogs with SoftClass 4606
                               removed — high end of count bisect without Rail hang) |
                               min (Mag+Rail/Barrel — includes Glock Rail 4606) |
                               full (capture catalogs, hangs mid-flight offline) |
                               stub4606 (capture order/count with SoftClass
                               4606→Mag 151 — hang-avoid shape probe).
  WW3_WAM_SPAWN_ATTACH=1     — post-ACK: package-map export + stably=0 spawn of real
                               BP_WP_* UWW3Attachment parts (CAM hat/chest pattern),
                               then WAM strip BatchID=2 with those NetGUIDs in
                               ReplicatedAttachments[]. Supersedes KEEP_DYNAMIC keep
                               list. SoftClass catalog stays empty (open strip).
                               Capture never exports/opens Mag_108/Rail_086 on the
                               wire (SoftClass-only); weapon-ch stably=0 CLOSES —
                               prefer WW3_WAM_SPAWN_HOST=pawn (ch3) like hat/chest.
  WW3_WAM_SPAWN_CHANNELS     — bisect: which WAMs get spawn/keep.
                               all (default) | inv (86,87) | early (4,5) | comma
                               channel list e.g. 87 or 86,87.
  WW3_WAM_SPAWN_HOST         — where export+stably=0 content is sent:
                               weapon (default: each WAM's actor ch — CLOSES) |
                               pawn / 3 (pawn ch3, CAM clothing host) |
                               <int> (explicit actor channel).
  WW3_WAM_SPAWN_ATT_LIMIT    — bisect: max attachments per WAM (default all; 1 = first).
  WW3_WAM_SPAWN_STRIP_KEEP   — 1 (default): strip ReplicatedAttachments=dyn GUIDs;
                               0: spawn (or export) but strip keeps empty catalog.
  WW3_WAM_SPAWN_EXPORT       — 1 (default) send package-map export; 0 = spawn-only
                               (reuse previously mapped class GUIDs — usually fatal).
  WW3_WAM_SPAWN_CONTENT      — 1 (default) send stably=0 content; 0 = export-only.
  WW3_WAM_SPAWN_PAYLOAD      — min (default AttachmentBatchID=1) | empty | hat
                               (copy clothing 9404 113-bit payload) | health
                               (BatchID=1 + HealthReplicated=100).
  WW3_WAM_SPAWN_CHECKSUM     — optional u32 NetworkChecksum on class+package exports
                               (empty/omit = path-only like clothing hat, default).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import NamedTuple

from actor_channel import (
    read_new_actor,
    write_export_block,
    write_rep_properties,
    write_subobject_content_block,
)
from netguid import GuidReader, GuidWriter, PackageMap
from repblock import read_packed

HERE = Path(__file__).resolve().parent
STREAM = HERE / "real_replay_stream.json"

CAM_NETGUID = 9374
IM_NETGUID = 9384
HAT_NETGUID = 9404
CHEST_NETGUID = 9406
CLOTHING_SRCS = (212, 213)

# WeaponAttachmentManager stably-named subs on local secondary/primary opens.
WAM_SECONDARY = 9418   # ch86 / Glock 9412 open
WAM_PRIMARY = 9426     # ch87 / HK417 9410 open
# Early ownership-bootstrap Glocks (src 14–17) — same SoftClass catalog surface as
# INV_ATTACH secondaries; these arm SoftClass *before* ch86/87 opens are stripped.
WAM_EARLY_CH4 = 8314   # ch4 / Glock 8308 open
WAM_EARLY_CH5 = 7956   # ch5 / Glock 7950 open
WAM_SRCS = {
    WAM_SECONDARY: (257, 258),
    WAM_PRIMARY: (259, 260),
}
WAM_CHANNELS = {
    WAM_EARLY_CH4: 4,
    WAM_EARLY_CH5: 5,
    WAM_SECONDARY: 86,
    WAM_PRIMARY: 87,
}
# FINAL partials only. WAM payloads live entirely in these FINALs (not INIT).
# ch4/ch5 NewActor+content has a 3-bit gap vs GuidReader; strip uses in-place
# payload replace so it does not depend on an exact post-NA content walk.
WAM_OPEN_FINAL_SRCS = {
    15: WAM_EARLY_CH4,
    17: WAM_EARLY_CH5,
    258: WAM_SECONDARY,
    260: WAM_PRIMARY,
}
# Post-ACK stripped reinforce targets (all local WAMs that can arm SoftClass).
WAM_STRIP_NETGUIDS = (
    WAM_EARLY_CH4,
    WAM_EARLY_CH5,
    WAM_SECONDARY,
    WAM_PRIMARY,
)
# Optional (WW3_WAM_KEEP_DYNAMIC=1): post-ACK BatchID=2 refs the stably=0 dynamic
# subobject after each WAM. **Do not enable lightly:** those NetGUIDs are FireType
# spawns (cls 243 = BP_Glock17FireType_01_C / cls 1373 on HK417), NOT
# UWW3Attachment actors. Putting them in ReplicatedAttachments[] is the wrong
# type vs CAM's hat/chest keep. Capture WAMs have no ReplicatedAttachments —
# SoftClass AttachmentIds create BP_WP_* offline-unloadable parts instead.
WAM_KEEP_REPLICATED = {
    WAM_EARLY_CH4: 8312,   # after WAM 8314 on ch4 — FireType, not attachment
    WAM_EARLY_CH5: 7954,   # after WAM 7956 on ch5 — FireType, not attachment
    WAM_SECONDARY: 9416,   # after WAM 9418 on ch86 — FireType, not attachment
    WAM_PRIMARY: 9424,     # after WAM 9426 on ch87 — FireType-like, not attachment
}


class WamAttachSpec(NamedTuple):
    """One channel attachment to spawn (CAM hat/chest analogue)."""

    dyn_netguid: int          # even dynamic instance NetGUID
    class_netguid: int        # odd static class NetGUID
    package_netguid: int      # odd static package NetGUID
    class_name: str           # e.g. BP_WP_Rail_086_01_C
    package_path: str         # /Game/.../BP_WP_Rail_086_01
    item_id: int              # capture SoftClass AttachmentId (docs / crash map)


# SoftClass package paths from live WW3 process string scan (2026-08-07).
# Crash FD35FE0D maps Glock catalog ids → BP_WP_* ; primary HK417 ids likewise.
_PKG_RAIL_086 = (
    "/Game/Blueprints/Weapons/Attachments/BodyParts/Rail/Rail_086/BP_WP_Rail_086_01"
)
_PKG_MAG_108 = (
    "/Game/Blueprints/Weapons/Attachments/WeaponAttachments/Magazine/"
    "Magazine_108/BP_WP_Magazine_108_01"
)
_PKG_MAG_116 = (
    "/Game/Blueprints/Weapons/Attachments/WeaponAttachments/Magazine/"
    "Magazine_116/BP_WP_Magazine_116_01"
)
_PKG_BARREL_033 = (
    "/Game/Blueprints/Weapons/Attachments/WeaponAttachments/Barrel/"
    "Barrel_033/BP_WP_Barrel_033_01"
)
_PKG_BARREL_024 = (
    "/Game/Blueprints/Weapons/Attachments/WeaponAttachments/Barrel/"
    "Barrel_024/BP_WP_Barrel_024_01"
)
_PKG_MUZZLE_020 = (
    "/Game/Blueprints/Weapons/Attachments/WeaponAttachments/Muzzle/"
    "Muzzle_020/BP_WP_Muzzle_020_01"
)
_PKG_MUZZLE_013 = (
    "/Game/Blueprints/Weapons/Attachments/WeaponAttachments/Muzzle/"
    "Muzzle_013/BP_WP_Muzzle_013_01"
)

# Shared static class/package GUIDs (odd). Fresh range above capture clothing 1363.
_CLS_RAIL_086, _PKG_GID_RAIL_086 = 1479, 1481
_CLS_MAG_108, _PKG_GID_MAG_108 = 1483, 1485
_CLS_MAG_116, _PKG_GID_MAG_116 = 1487, 1489
_CLS_BARREL_033, _PKG_GID_BARREL_033 = 1491, 1493
_CLS_BARREL_024, _PKG_GID_BARREL_024 = 1495, 1497
_CLS_MUZZLE_020, _PKG_GID_MUZZLE_020 = 1499, 1501
_CLS_MUZZLE_013, _PKG_GID_MUZZLE_013 = 1503, 1505
_CLS_RECEIVER_008, _PKG_GID_RECEIVER_008 = 1507, 1509
_CLS_UPPER_091, _PKG_GID_UPPER_091 = 1511, 1513
_CLS_SIDE_006, _PKG_GID_SIDE_006 = 1515, 1517
_CLS_HANDGUARD_021, _PKG_GID_HANDGUARD_021 = 1519, 1521
_CLS_STOCK_029, _PKG_GID_STOCK_029 = 1523, 1525
_CLS_PISTOLGRIP_017, _PKG_GID_PISTOLGRIP_017 = 1527, 1529
_CLS_UPPERMINOR_SIDEARM, _PKG_GID_UPPERMINOR_SIDEARM = 1531, 1533
_CLS_UPPERMINOR_BR, _PKG_GID_UPPERMINOR_BR = 1535, 1537

_PKG_RECEIVER_008 = (
    "/Game/Blueprints/Weapons/Attachments/BodyParts/Receiver/"
    "Receiver_008_02/BP_WP_Receiver_008_02"
)
_PKG_UPPER_091 = (
    "/Game/Blueprints/Weapons/Attachments/WeaponAttachments/Upper/"
    "Upper_091/BP_WP_Upper_091_01"
)
_PKG_SIDE_006 = (
    "/Game/Blueprints/Weapons/Attachments/WeaponAttachments/Side/"
    "Side_006/BP_WP_Side_006_01"
)
_PKG_HANDGUARD_021 = (
    "/Game/Blueprints/Weapons/Attachments/BodyParts/Handguard/"
    "Handguard_021/BP_WP_Handguard_021_01"
)
_PKG_STOCK_029 = (
    "/Game/Blueprints/Weapons/Attachments/BodyParts/Stock/"
    "Stock_029/BP_WP_Stock_029_01"
)
_PKG_PISTOLGRIP_017 = (
    "/Game/Blueprints/Weapons/Attachments/BodyParts/PistolGrip/"
    "PistolGrip_017/BP_WP_PistolGrip_017_01"
)
_PKG_UPPERMINOR_SIDEARM = (
    "/Game/Blueprints/Weapons/Attachments/WeaponAttachments/UpperMinor/"
    "UpperMinor_026_06_PST_Sidearm/BP_WP_UpperMinor_026_06_PST_Sidearm"
)
_PKG_UPPERMINOR_BR = (
    "/Game/Blueprints/Weapons/Attachments/WeaponAttachments/UpperMinor/"
    "UpperMinor_026_02_PST_BR/BP_WP_UpperMinor_026_02_PST_BR"
)

# Per-WAM dynamic instances (even) — two each, CAM hat+chest style.
# Glock WAMs: Magazine_108 (id 151) + Rail_086 (id 4606).
# HK417 WAM: Magazine_116 (id 143) + Barrel_033 (id 295).
WAM_SPAWN_ATTACHMENTS: dict[int, tuple[WamAttachSpec, ...]] = {
    WAM_EARLY_CH4: (
        WamAttachSpec(9600, _CLS_MAG_108, _PKG_GID_MAG_108,
                      "BP_WP_Magazine_108_01_C", _PKG_MAG_108, 151),
        WamAttachSpec(9602, _CLS_RAIL_086, _PKG_GID_RAIL_086,
                      "BP_WP_Rail_086_01_C", _PKG_RAIL_086, 4606),
    ),
    WAM_EARLY_CH5: (
        WamAttachSpec(9604, _CLS_MAG_108, _PKG_GID_MAG_108,
                      "BP_WP_Magazine_108_01_C", _PKG_MAG_108, 151),
        WamAttachSpec(9606, _CLS_RAIL_086, _PKG_GID_RAIL_086,
                      "BP_WP_Rail_086_01_C", _PKG_RAIL_086, 4606),
    ),
    WAM_SECONDARY: (
        WamAttachSpec(9608, _CLS_MAG_108, _PKG_GID_MAG_108,
                      "BP_WP_Magazine_108_01_C", _PKG_MAG_108, 151),
        WamAttachSpec(9610, _CLS_RAIL_086, _PKG_GID_RAIL_086,
                      "BP_WP_Rail_086_01_C", _PKG_RAIL_086, 4606),
    ),
    WAM_PRIMARY: (
        WamAttachSpec(9612, _CLS_MAG_116, _PKG_GID_MAG_116,
                      "BP_WP_Magazine_116_01_C", _PKG_MAG_116, 143),
        WamAttachSpec(9614, _CLS_BARREL_033, _PKG_GID_BARREL_033,
                      "BP_WP_Barrel_033_01_C", _PKG_BARREL_033, 295),
    ),
}


def _bits_from_writer(w: GuidWriter) -> list[int]:
    raw = w.get_bytes()
    return [((raw[i >> 3] >> (i & 7)) & 1) for i in range(w.num)]


def _walk_content_blocks(bits: list[int], pos: int = 0) -> list[dict]:
    """Shared content-block walk (stably=0 → class NetGUID before NumBits)."""
    blocks: list[dict] = []
    p = pos
    while p + 3 <= len(bits):
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
            break
        p += nw
        payload = bits[p : p + nbits]
        p += nbits
        blocks.append(
            {
                "hasRepLayout": has_rep,
                "isActor": bool(is_actor),
                "subNetGUID": sub,
                "stablyNamed": stably,
                "classNetGUID": cls,
                "payloadBits": nbits,
                "payload": payload,
            }
        )
    if p != len(bits):
        raise ValueError(f"content walk left {len(bits) - p} bits (pos={p}/{len(bits)})")
    return blocks


def parse_clothing_content_blocks(bits: list[int] | None = None) -> list[dict]:
    """Walk clothing bunch with stably=0 → packed class NetGUID before NumBits."""
    if bits is None:
        stream = json.loads(STREAM.read_text(encoding="utf-8"))
        bits = []
        for i in CLOTHING_SRCS:
            bits.extend(int(c) for c in stream[i]["payload"])
    pm = PackageMap()
    pos = pm.read_export_bunch(bits)["reader"].pos
    return _walk_content_blocks(bits, pos)


def extract_cam_im_payloads(bits: list[int] | None = None) -> dict[int, list[int]]:
    """-> {9374: cam_payload_bits, 9384: im_payload_bits}."""
    out: dict[int, list[int]] = {}
    for b in parse_clothing_content_blocks(bits):
        if b["subNetGUID"] in (CAM_NETGUID, IM_NETGUID) and b["payload"]:
            out[b["subNetGUID"]] = list(b["payload"])
    if CAM_NETGUID not in out or IM_NETGUID not in out:
        raise RuntimeError(f"clothing missing CAM/IM blocks: have {sorted(out)}")
    return out


def build_cam_im_resend_bits(payloads: dict[int, list[int]] | None = None) -> list[int]:
    """Framed ch3 content: CAM(9374) + IM(9384) stably-named RepLayout blocks."""
    payloads = payloads or extract_cam_im_payloads()
    w = GuidWriter()
    write_subobject_content_block(
        w, CAM_NETGUID, stably_named=1, has_rep_layout=1,
        payload_bits_list=payloads[CAM_NETGUID])
    write_subobject_content_block(
        w, IM_NETGUID, stably_named=1, has_rep_layout=1,
        payload_bits_list=payloads[IM_NETGUID])
    return _bits_from_writer(w)


def parse_weapon_open_content_blocks(srcs: tuple[int, int]) -> list[dict]:
    """Walk a weapon open (exports + NewActor + content), exact-consume."""
    stream = json.loads(STREAM.read_text(encoding="utf-8"))
    bits: list[int] = []
    for i in srcs:
        bits.extend(int(c) for c in stream[i]["payload"])
    pm = PackageMap()
    pos = pm.read_export_bunch(bits)["reader"].pos
    gr = GuidReader(bits, pos)
    read_new_actor(gr, pm)
    return _walk_content_blocks(bits, gr.pos)


def extract_wam_payloads() -> dict[int, list[int]]:
    """-> {9418: secondary_wam_bits, 9426: primary_wam_bits} from weapon opens."""
    out: dict[int, list[int]] = {}
    for netguid, srcs in WAM_SRCS.items():
        for b in parse_weapon_open_content_blocks(srcs):
            if b["subNetGUID"] == netguid and b["payload"]:
                out[netguid] = list(b["payload"])
    if WAM_SECONDARY not in out or WAM_PRIMARY not in out:
        raise RuntimeError(f"weapon opens missing WAM blocks: have {sorted(out)}")
    return out


def build_wam_resend_bits(netguid: int, payloads: dict[int, list[int]] | None = None) -> list[int]:
    """Framed content for one WeaponAttachmentManager stably-named RepLayout block."""
    payloads = payloads or extract_wam_payloads()
    w = GuidWriter()
    write_subobject_content_block(
        w, netguid, stably_named=1, has_rep_layout=1,
        payload_bits_list=payloads[netguid])
    return _bits_from_writer(w)


def clothing_resend_specs() -> list[dict]:
    """Capture-faithful clothing partial chain (src 212–213) for post-ACK resend.

    Includes package-map exports for hat/chest classes + stably=0 content for
    9404/9406 + CAM(9374) + IM(9384). CAM ReplicatedAttachments refs those hat/chest
    NetGUIDs; CAM/IM-only resend cannot create them.
    """
    stream = json.loads(STREAM.read_text(encoding="utf-8"))
    out: list[dict] = []
    for i in CLOTHING_SRCS:
        bunch = dict(stream[i])
        bunch["_src_idx"] = i
        bunch["_clothing_resend"] = 1
        out.append(bunch)
    return out


def inv_attach_enabled() -> bool:
    return os.environ.get("WW3_INV_ATTACH", "0") == "1"


def cam_im_after_ack_enabled() -> bool:
    return os.environ.get("WW3_CAM_IM_AFTER_ACK", "0") == "1"


def wpn_attach_enabled() -> bool:
    return os.environ.get("WW3_WPN_ATTACH", "0") == "1"


def clothing_resend_enabled() -> bool:
    return os.environ.get("WW3_CLOTHING_RESEND", "0") == "1"


def cam_strip_catalog_enabled() -> bool:
    return os.environ.get("WW3_CAM_STRIP_CATALOG", "0") == "1"


def wam_strip_catalog_enabled() -> bool:
    return os.environ.get("WW3_WAM_STRIP_CATALOG", "0") == "1"


def wam_strip_target_netguids() -> tuple[int, ...]:
    """Which WAMs the open/post-ACK strip path rewrites.

    Historical Sync-arm rematch ``074114`` only emptied INV_ATTACH ch86/87
    (src 258/260); early Glock ch4/ch5 SoftClass catalogs stayed on the open
    and armed mid-flight ``OnAttachmentManagerSynchronized`` (hang on 4606).
    Use ``WW3_WAM_STRIP_CHANNELS=inv`` to restore that surface. Default ``all``
    matches today's four-WAM strip (clears SoftClass pending).
    """
    raw = (os.environ.get("WW3_WAM_STRIP_CHANNELS") or "all").strip().lower()
    if raw in ("", "all", "*"):
        return WAM_STRIP_NETGUIDS
    if raw in ("inv", "inv_attach", "86,87", "hist", "074114"):
        return (WAM_SECONDARY, WAM_PRIMARY)
    if raw in ("early", "glock", "4,5"):
        return (WAM_EARLY_CH4, WAM_EARLY_CH5)
    ch_to_wam = {ch: ng for ng, ch in WAM_CHANNELS.items()}
    out: list[int] = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            v = int(tok)
        except ValueError:
            continue
        if v in WAM_CHANNELS:
            out.append(v)
        elif v in ch_to_wam:
            out.append(ch_to_wam[v])
    seen: set[int] = set()
    ordered: list[int] = []
    for ng in WAM_STRIP_NETGUIDS:
        if ng in out and ng not in seen:
            ordered.append(ng)
            seen.add(ng)
    return tuple(ordered) if ordered else WAM_STRIP_NETGUIDS


def wam_open_strip_srcs() -> dict[int, int]:
    """src_idx → WAM NetGUID for open-FINAL strip (filtered by STRIP_CHANNELS)."""
    allowed = set(wam_strip_target_netguids())
    return {src: ng for src, ng in WAM_OPEN_FINAL_SRCS.items() if ng in allowed}


def wam_keep_dynamic_enabled() -> bool:
    return os.environ.get("WW3_WAM_KEEP_DYNAMIC", "0") == "1"


def wam_keep_clothing_enabled() -> bool:
    """Post-ACK WAM strip keeps clothing hat/chest NetGUIDs (CAM ReplicatedAttachments)."""
    return os.environ.get("WW3_WAM_KEEP_CLOTHING", "0") == "1"


def wam_softclass_catalog_enabled() -> bool:
    """Non-empty SoftClass AttachmentIds on open strip + post-ACK reinforce."""
    return os.environ.get("WW3_WAM_SOFTCLASS_CATALOG", "0") == "1"


def wam_softclass_mode() -> str:
    """SoftClass catalog size: mag | mag_muzzle | mag_barrel | mag_muzzle_barrel |
    mag_muzzle_4606 | norail | min | full | stub4606."""
    raw = (os.environ.get("WW3_WAM_SOFTCLASS_MODE") or "mag").strip().lower()
    if raw in ("mag", "magazine", "1"):
        return "mag"
    if raw in ("mag_muzzle", "muzzle", "mag+muzzle"):
        return "mag_muzzle"
    if raw in ("mag_barrel", "barrel", "mag+barrel"):
        return "mag_barrel"
    if raw in ("mag_muzzle_barrel", "muzzle_barrel", "mag+muzzle+barrel", "mmb"):
        return "mag_muzzle_barrel"
    if raw in ("mag_muzzle_4606", "mag+muzzle+4606", "muzzle4606", "mmr"):
        return "mag_muzzle_4606"
    if raw in ("norail", "no_rail", "no4606", "sans_rail"):
        return "norail"
    if raw in ("min", "minimal", "rail"):
        return "min"
    if raw in ("full", "capture", "all"):
        return "full"
    if raw in ("stub4606", "stub_4606", "full_stub4606", "stubrail"):
        return "stub4606"
    return "mag"


def wam_softclass_stub_4606_enabled() -> bool:
    """Native early SoftClass opens: splice SoftClass Rail 4606→Mag 151."""
    return os.environ.get("WW3_WAM_SOFTCLASS_STUB_4606", "0") == "1"


def wam_softclass_post_stub_4606_enabled() -> bool:
    """Post-ACK SoftClass 4606 finish/skip after Mag NewObject (not open stub)."""
    return os.environ.get("WW3_WAM_SOFTCLASS_POST_STUB_4606", "0") == "1"


def wam_early_empty_parts_reinforce_enabled() -> bool:
    """Post-ACK SoftClass ids + empty Parts on early hist SoftClass WAMs.

    pads_only / PartSkins RAM clears never re-enter CheckAttachmentsSynchronized;
    off-thread ProcessEvent AVs. This wire BatchID=2 reinforce keeps SoftClass
    AttachmentIds (CreateAttachment already ran) but clears DirectReplicatedSkins
    Parts so OnRep can finish Synchronized on the game thread.
    """
    return os.environ.get("WW3_WAM_EARLY_EMPTY_PARTS_REINFORCE", "0") == "1"


def wam_softclass_post_stub_delay_ms() -> float:
    try:
        return max(0.0, float(os.environ.get(
            "WW3_WAM_SOFTCLASS_POST_STUB_DELAY_MS", "2500")))
    except ValueError:
        return 2500.0


def wam_softclass_post_stub_wait_file() -> str:
    """Optional gate file; empty means delay-only after ACK."""
    return (os.environ.get("WW3_WAM_SOFTCLASS_POST_STUB_WAIT_FILE") or "").strip()


def wam_softclass_post_stub_mode() -> str:
    raw = (os.environ.get("WW3_WAM_SOFTCLASS_POST_STUB_MODE") or "stub").strip().lower()
    if raw in ("skins", "skins_only", "skins-only"):
        return "skins_only"
    if raw in ("full_empty", "full-empty", "fullids", "full_ids"):
        return "full_empty"
    if raw in ("empty", "cancel", "strip", "clear"):
        return "empty"
    return "stub"


def wam_post_stub_4606_target_netguids() -> tuple[int, ...]:
    """Early SoftClass WAMs left native by STRIP_CHANNELS that still carry 4606.

    Under hist ``inv`` strip: ch4/ch5 (8314/7956). Secondary also has 4606 in
    capture but is emptied on open under inv — not a post-stub target.
    """
    stripped = set(wam_strip_target_netguids()) if wam_strip_catalog_enabled() else set()
    out: list[int] = []
    for ng, ids in WAM_SOFTCLASS_FULL_IDS.items():
        if ng in stripped:
            continue
        if 4606 not in ids:
            continue
        # The stub replaces Rail/4606 with Magazine/151.  Never send that
        # shape when the current WAM already contains Magazine/151: the client
        # treats the BatchID bump as a real attachment update and attempts to
        # rebuild two items in the same slot, tripping its native
        # ``multiple attachments for the same slot`` ensure.  In that case the
        # only safe post-ACK operation is the empty-catalog cancel mode.
        if 151 in ids and wam_softclass_post_stub_mode() not in ("empty", "full_empty", "skins_only"):
            continue
        out.append(int(ng))
    return tuple(out)


def wam_softclass_open_only() -> bool:
    """SoftClass AttachmentIds on open only; post-ACK reinforce stays empty.

    Capture-faithful open SoftClass keeps skins Parts / MainId / BatchID=1.
    Post-ACK stripped SoftClass reinforce uses BatchID=2 + skins=[] + omit
    MainId — a different shape that can overwrite the open OnRep surface.
    """
    return os.environ.get("WW3_WAM_SOFTCLASS_OPEN_ONLY", "0") == "1"


def wam_softclass_keep_skins() -> bool:
    """Post-ACK SoftClass reinforce keeps capture skins Parts / MainId.

    When SoftClass catalog is on and OPEN_ONLY is off, default post-ACK uses
    stripped BatchID=2 + skins=[] + omit MainId. KEEP_SKINS=1 instead splices
    SoftClass AttachmentIds into the capture open payload and only bumps
    BatchID (skins / MainId / handle set preserved) — isolates whether the
    empty-skins reinforce shape cancels Sync arm.
    """
    return os.environ.get("WW3_WAM_SOFTCLASS_KEEP_SKINS", "0") == "1"


def wam_softclass_ids_for(netguid: int) -> tuple[int, ...]:
    """AttachmentIds for SoftClass catalog mode (empty when catalog off)."""
    if not wam_softclass_catalog_enabled():
        return ()
    mode = wam_softclass_mode()
    table = {
        "mag": WAM_SOFTCLASS_MAG_IDS,
        "mag_muzzle": WAM_SOFTCLASS_MAG_MUZZLE_IDS,
        "mag_barrel": WAM_SOFTCLASS_MAG_BARREL_IDS,
        "mag_muzzle_barrel": WAM_SOFTCLASS_MAG_MUZZLE_BARREL_IDS,
        "mag_muzzle_4606": WAM_SOFTCLASS_MAG_MUZZLE_4606_IDS,
        "norail": WAM_SOFTCLASS_NORAIL_IDS,
        "min": WAM_SOFTCLASS_MIN_IDS,
        "full": WAM_SOFTCLASS_FULL_IDS,
        "stub4606": WAM_SOFTCLASS_STUB4606_IDS,
    }[mode]
    return tuple(table.get(int(netguid), ()))


def wam_softclass_export_enabled() -> bool:
    """Package-map SoftClass BP_WP_* exports before SoftClass catalog OnRep."""
    if not wam_softclass_catalog_enabled():
        return False
    return os.environ.get("WW3_WAM_SOFTCLASS_EXPORT", "1") == "1"


def wam_softclass_warm_export_enabled() -> bool:
    """Early Mag/Rail SoftClass package-map warm — no catalog rewrite, no content.

    Independent of ``WW3_WAM_SOFTCLASS_CATALOG``. Sends known SoftClass BP_WP_*
    package paths on pawn ch3 before early Glock SoftClass OnRep so ItemDatabase
    SoftClassPtr async can resolve against already-imported paths. Safe: export
    only (no stably=0 BP_WP_* — avoids weapon-channel CLOSE).
    """
    return os.environ.get("WW3_WAM_SOFTCLASS_WARM_EXPORT", "0") == "1"


def wam_spawn_attach_enabled() -> bool:
    return os.environ.get("WW3_WAM_SPAWN_ATTACH", "0") == "1"


def wam_spawn_strip_keep_enabled() -> bool:
    """When spawn is on, put dyn NetGUIDs in post-ACK strip (default on)."""
    if not wam_spawn_attach_enabled():
        return False
    return os.environ.get("WW3_WAM_SPAWN_STRIP_KEEP", "1") == "1"


def wam_spawn_export_enabled() -> bool:
    return os.environ.get("WW3_WAM_SPAWN_EXPORT", "1") == "1"


def wam_spawn_content_enabled() -> bool:
    return os.environ.get("WW3_WAM_SPAWN_CONTENT", "1") == "1"


def wam_spawn_host_ch(weapon_ch: int | None = None) -> int:
    """Actor channel that receives BP_WP_* export + stably=0 content.

    Capture: Mag/Rail never appear as exports or channel opens — SoftClass only.
    Post-ACK stably=0 on weapon channels CHANNEL CLOSEs (bisect 091152/091417).
    CAM hat/chest live as stably=0 subobjects on pawn ch3; host=pawn mirrors that.
    UWW3Attachment is UObject (not AActor) — cannot open dedicated actor channels.
    """
    raw = (os.environ.get("WW3_WAM_SPAWN_HOST") or "weapon").strip().lower()
    if raw in ("weapon", "wam", "self", ""):
        if weapon_ch is None:
            raise ValueError("wam_spawn_host_ch(weapon) needs weapon_ch")
        return int(weapon_ch)
    if raw in ("pawn", "clothing", "ch3", "3"):
        return 3
    try:
        return int(raw)
    except ValueError:
        if weapon_ch is None:
            raise ValueError(f"bad WW3_WAM_SPAWN_HOST={raw!r}") from None
        return int(weapon_ch)


def wam_spawn_host_is_shared() -> bool:
    """True when all BP_WP_* content goes to one host ch (not per-weapon)."""
    raw = (os.environ.get("WW3_WAM_SPAWN_HOST") or "weapon").strip().lower()
    return raw not in ("weapon", "wam", "self", "")


def wam_spawn_att_limit() -> int | None:
    raw = (os.environ.get("WW3_WAM_SPAWN_ATT_LIMIT") or "").strip()
    if not raw:
        return None
    try:
        n = int(raw)
    except ValueError:
        return None
    return n if n > 0 else None


def wam_spawn_checksum() -> int | None:
    raw = (os.environ.get("WW3_WAM_SPAWN_CHECKSUM") or "").strip()
    if not raw:
        return None
    try:
        return int(raw, 0)
    except ValueError:
        return None


def wam_spawn_payload_mode() -> str:
    mode = (os.environ.get("WW3_WAM_SPAWN_PAYLOAD") or "min").strip().lower()
    if mode in ("min", "empty", "hat", "health"):
        return mode
    return "min"


def wam_spawn_target_netguids() -> tuple[int, ...]:
    """Which WAM NetGUIDs receive spawn/export under WW3_WAM_SPAWN_CHANNELS."""
    raw = (os.environ.get("WW3_WAM_SPAWN_CHANNELS") or "all").strip().lower()
    if raw in ("", "all", "*"):
        return WAM_STRIP_NETGUIDS
    if raw in ("inv", "inv_attach", "86,87"):
        return (WAM_SECONDARY, WAM_PRIMARY)
    if raw in ("early", "glock", "4,5"):
        return (WAM_EARLY_CH4, WAM_EARLY_CH5)
    # Comma list of channel indices OR WAM NetGUIDs.
    ch_to_wam = {ch: ng for ng, ch in WAM_CHANNELS.items()}
    out: list[int] = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            v = int(tok)
        except ValueError:
            continue
        if v in WAM_CHANNELS:
            out.append(v)
        elif v in ch_to_wam:
            out.append(ch_to_wam[v])
    # Preserve canonical order, drop dups.
    seen: set[int] = set()
    ordered: list[int] = []
    for ng in WAM_STRIP_NETGUIDS:
        if ng in out and ng not in seen:
            ordered.append(ng)
            seen.add(ng)
    return tuple(ordered)


def wam_spawn_specs_for(netguid: int) -> tuple[WamAttachSpec, ...]:
    """Filtered attachment specs for one WAM (channel + att-limit bisect)."""
    if int(netguid) not in wam_spawn_target_netguids():
        return ()
    if os.environ.get("WW3_WAM_SPAWN_USE_HAT_CLASS", "0") == "1":
        # Control: reuse clothing hat class GUIDs already exported by CLOTHING_RESEND.
        # Isolates BP_WP_* SoftClass path vs 'any stably=0 on weapon channel'.
        lim = wam_spawn_att_limit() or 1
        hat = WamAttachSpec(
            9612, 1357, 1359,
            "BP_CH_Hat_004_01_C",
            "/Game/Blueprints/Player/Attachments/Heads/Headwears/Hat/Hat_004/BP_CH_Hat_004_01",
            0,
        )
        return (hat,)[:lim]
    specs = WAM_SPAWN_ATTACHMENTS.get(int(netguid), ())
    lim = wam_spawn_att_limit()
    if lim is not None:
        specs = specs[:lim]
    return tuple(specs)


def cam_im_ack_timeout_s() -> float:
    try:
        return float(os.environ.get("WW3_CAM_IM_ACK_TIMEOUT_S", "3.0"))
    except ValueError:
        return 3.0


# Capture CAM catalog SoftClass wait surface (clothing src 212–213, closed decode).
CAPTURE_CAM_ATTACHMENT_IDS = (
    1242, 1251, 1260, 1261, 1337, 1386, 2114, 2382, 4425, 6875, 9072,
)
CAPTURE_CAM_SKIN_ATTACHMENT_IDS = (1893, 9961, 10071, 3246, 1857)
CAPTURE_CAM_SKIN_ITEM_TYPES = (2, 3, 12, 5, 9)

# Capture WAM catalog SoftClass wait surface (closed decode).
# No ReplicatedAttachments[] on the wire — sync is SoftClass-only from AttachmentIds.
CAPTURE_WAM_SECONDARY_ATTACHMENT_IDS = (
    101, 151, 304, 4585, 4600, 4606, 4638, 7851, 565,
)
CAPTURE_WAM_PRIMARY_ATTACHMENT_IDS = (
    295, 143, 526, 346, 432, 108, 39, 7847,
)
# Early ch4/ch5 Glock WAMs (8314/7956): 8-id catalog that includes SoftClass id 4606
# (BP_WP_Rail_086). This is what arms the heap wait when only ch86/87 are stripped.
CAPTURE_WAM_EARLY_ATTACHMENT_IDS = (
    151, 4638, 304, 101, 4606, 4608, 88, 7851,
)
CAPTURE_WAM_SECONDARY_MAIN_ID = 9246

# SoftClass AttachmentIds that map to known-on-disk BP_WP_* (crash + process path
# scan). Full capture catalogs hang mid-flight offline on Rail 4606 *after* Mag
# NewObject succeeds (heap: Synchronized … Mag_108 … 151 then stuck on 4606).
# Mag-only / Mag+1 / Mag+2 splices never arm Synchronized — norail (full minus
# 4606) also never arms — Mag+4606 / Mag+Muzzle+4606 EXPORT=0 also never arms.
# Full catalogs hang mid-flight offline on Rail 4606
# *after* Mag NewObject (heap: Synchronized … Mag_108 … 151 then stuck on 4606).
# Crash FD35FE0D maps (Glock early/secondary + HK primary):
#   151 Mag_108, 101 Muzzle_020, 304 Barrel_024, 4638 Receiver_008, 4606 Rail_086,
#   143 Mag_116, 108 Muzzle_013, 295 Barrel_033, 526 Handguard_021, …
WAM_SOFTCLASS_MAG_IDS: dict[int, tuple[int, ...]] = {
    WAM_EARLY_CH4: (151,),
    WAM_EARLY_CH5: (151,),
    WAM_SECONDARY: (151,),
    WAM_PRIMARY: (143,),
}
# Mag + one non-Rail SoftClass id (capture-open splice bisect). Avoids 4606.
WAM_SOFTCLASS_MAG_MUZZLE_IDS: dict[int, tuple[int, ...]] = {
    WAM_EARLY_CH4: (151, 101),
    WAM_EARLY_CH5: (151, 101),
    WAM_SECONDARY: (151, 101),
    WAM_PRIMARY: (143, 108),
}
WAM_SOFTCLASS_MAG_BARREL_IDS: dict[int, tuple[int, ...]] = {
    WAM_EARLY_CH4: (151, 304),
    WAM_EARLY_CH5: (151, 304),
    WAM_SECONDARY: (151, 304),
    WAM_PRIMARY: (143, 295),
}
# Mag + two non-Rail SoftClass ids (count bisect toward full catalog). No 4606.
WAM_SOFTCLASS_MAG_MUZZLE_BARREL_IDS: dict[int, tuple[int, ...]] = {
    WAM_EARLY_CH4: (151, 101, 304),
    WAM_EARLY_CH5: (151, 101, 304),
    WAM_SECONDARY: (151, 101, 304),
    WAM_PRIMARY: (143, 108, 295),
}
# Mag+Muzzle+Rail 4606 — 4606 presence with Mag+1 non-Rail (EXPORT=0 probe).
# HK primary has no 4606; keep Mag+Muzzle there.
WAM_SOFTCLASS_MAG_MUZZLE_4606_IDS: dict[int, tuple[int, ...]] = {
    WAM_EARLY_CH4: (151, 101, 4606),
    WAM_EARLY_CH5: (151, 101, 4606),
    WAM_SECONDARY: (151, 101, 4606),
    WAM_PRIMARY: (143, 108),
}
# Capture SoftClass catalogs with Rail 4606 removed — high end of count bisect.
WAM_SOFTCLASS_NORAIL_IDS: dict[int, tuple[int, ...]] = {
    WAM_EARLY_CH4: tuple(i for i in CAPTURE_WAM_EARLY_ATTACHMENT_IDS if i != 4606),
    WAM_EARLY_CH5: tuple(i for i in CAPTURE_WAM_EARLY_ATTACHMENT_IDS if i != 4606),
    WAM_SECONDARY: tuple(i for i in CAPTURE_WAM_SECONDARY_ATTACHMENT_IDS if i != 4606),
    WAM_PRIMARY: CAPTURE_WAM_PRIMARY_ATTACHMENT_IDS,  # HK primary has no 4606
}
# Mag+Rail/Barrel — Glock includes Rail 4606 (hang surface); prefer mag_barrel.
WAM_SOFTCLASS_MIN_IDS: dict[int, tuple[int, ...]] = {
    WAM_EARLY_CH4: (151, 4606),
    WAM_EARLY_CH5: (151, 4606),
    WAM_SECONDARY: (151, 4606),
    WAM_PRIMARY: (143, 295),
}
# Capture SoftClass catalogs — hang mid-flight offline (do not rematch lightly).
WAM_SOFTCLASS_FULL_IDS: dict[int, tuple[int, ...]] = {
    WAM_EARLY_CH4: CAPTURE_WAM_EARLY_ATTACHMENT_IDS,
    WAM_EARLY_CH5: CAPTURE_WAM_EARLY_ATTACHMENT_IDS,
    WAM_SECONDARY: CAPTURE_WAM_SECONDARY_ATTACHMENT_IDS,
    WAM_PRIMARY: CAPTURE_WAM_PRIMARY_ATTACHMENT_IDS,
}
# Capture order/count with SoftClass Rail 4606 replaced by Mag 151 (offline-
# NewObject proven). Same length/slots/skins/MainId/BatchID as capture open;
# only the 4606 value bits differ. Primary HK has no 4606 — identical to full.
WAM_SOFTCLASS_STUB4606_IDS: dict[int, tuple[int, ...]] = {
    ng: tuple(151 if i == 4606 else i for i in ids)
    for ng, ids in WAM_SOFTCLASS_FULL_IDS.items()
}


def _bits_u(value: int, width: int) -> list[int]:
    return [((value >> i) & 1) for i in range(width)]


def _bits_packed(value: int) -> list[int]:
    w = GuidWriter()
    w.write_packed(int(value))
    return _bits_from_writer(w)


def _bits_uint16_array(values: list[int] | tuple[int, ...]) -> list[int]:
    """REPCMD_DynamicArray<uint16>: ArrayNum + nested idx/value stream + packed 0."""
    out = _bits_u(len(values), 16)
    for i, v in enumerate(values, start=1):
        out.extend(_bits_packed(i))
        out.extend(_bits_u(int(v), 16))
    out.extend(_bits_packed(0))
    return out


def _bits_uint8_array(values: list[int] | tuple[int, ...]) -> list[int]:
    out = _bits_u(len(values), 16)
    for i, v in enumerate(values, start=1):
        out.extend(_bits_packed(i))
        out.extend(_bits_u(int(v), 8))
    out.extend(_bits_packed(0))
    return out


def _bits_object_array(netguids: list[int] | tuple[int, ...]) -> list[int]:
    """DynamicArray of object refs (packed NetGUID per element)."""
    out = _bits_u(len(netguids), 16)
    for i, gid in enumerate(netguids, start=1):
        out.extend(_bits_packed(i))
        out.extend(_bits_packed(int(gid)))
    out.extend(_bits_packed(0))
    return out


def build_cam_stripped_catalog_payload(batch_id: int = 2) -> list[int]:
    """CAM RepLayout: keep hat/chest refs, clear catalog AttachmentIds + skins.

    Capture CAM carries 11 AttachmentIds (only 2 have channel objects 9404/9406)
    and 5 DirectReplicatedSkinsIds.Parts SoftClass loads. OnRep waits on ItemDatabase
    SoftClass completion for the rest — offline that never finishes, so
    `OnSynchronized: Character Attachments` never fires. Empty catalog + bumped
    BatchID re-enters OnRep with only the already-mapped ReplicatedAttachments.
    """
    return write_rep_properties([
        (3, _bits_u(int(batch_id), 32)),                          # BatchID
        (4, _bits_u(2, 8)),                                       # NumReplicatedAttachments
        (5, _bits_uint16_array(())),                              # AttachmentIds[] empty
        (6, _bits_object_array((HAT_NETGUID, CHEST_NETGUID))),    # 9404, 9406
        (8, _bits_uint16_array(())),                              # skins AttachmentsIds[] empty
        (9, _bits_uint8_array(())),                               # skins ItemTypes[] empty
    ])


def build_cam_strip_resend_bits(batch_id: int = 2) -> list[int]:
    """Stably-named ch3 content block: stripped CAM only."""
    w = GuidWriter()
    write_subobject_content_block(
        w, CAM_NETGUID, stably_named=1, has_rep_layout=1,
        payload_bits_list=build_cam_stripped_catalog_payload(batch_id=batch_id))
    return _bits_from_writer(w)


def build_wam_stripped_catalog_payload(
    batch_id: int = 2,
    replicated_attachments: list[int] | tuple[int, ...] = (),
    attachment_ids: list[int] | tuple[int, ...] = (),
) -> list[int]:
    """WAM RepLayout: SoftClass and/or keep-dyn catalog; omit MainId.

    Capture WAMs carry SoftClass-only AttachmentIds and (usually) no
    ReplicatedAttachments[] / MainId. Early ch4/ch5 + primary open handles:
      BatchID, AttachmentIds[], skins Parts.*
    Only secondary 9418 also sent MainId=9246. Writing MainId=0 dirties
    OnRep_ReplicatedSkinsIds and can arm MainSkinLoadedClass SoftClass — omit it.

    Empty AttachmentIds never starts OnAttachmentManagerSynchronized. Options:
      - keep ReplicatedAttachments (clothing 9404/9406 or spawn dyn) — CAM path
      - non-empty SoftClass AttachmentIds — ItemDatabase SoftClass path
    When both empty, match capture open-strip handle set (no Num / keep / MainId).
    """
    att = tuple(int(g) for g in replicated_attachments)
    ids = tuple(int(v) for v in attachment_ids)
    props: list[tuple[int, list[int]]] = [
        (3, _bits_u(int(batch_id), 32)),           # BatchID
    ]
    if att:
        props.append((4, _bits_u(len(att), 8)))    # NumReplicatedAttachments
    props.append((5, _bits_uint16_array(ids)))     # AttachmentIds[]
    if att:
        props.append((6, _bits_object_array(att)))  # ReplicatedAttachments[]
    # Intentionally omit handle 7 MainId (see docstring).
    props.extend([
        (8, _bits_uint16_array(())),               # skins AttachmentsIds[] empty
        (9, _bits_uint8_array(())),                # skins ItemTypes[] empty
    ])
    return write_rep_properties(props)


def extract_all_wam_open_payloads() -> dict[int, list[int]]:
    """Capture WAM RepLayout payloads from open FINALs (all strip targets)."""
    stream = json.loads(STREAM.read_text(encoding="utf-8"))
    out: dict[int, list[int]] = {}
    for src, ng in WAM_OPEN_FINAL_SRCS.items():
        bits = [int(c) for c in stream[int(src)]["payload"]]
        hdr = _find_wam_block_header(bits, int(ng))
        if hdr is None:
            raise RuntimeError(f"WAM {ng} missing from open FINAL src={src}")
        out[int(ng)] = list(bits[hdr["payload_start"] : hdr["payload_end"]])
    return out


def splice_wam_payload_batch_id(
    payload: list[int],
    batch_id: int,
) -> list[int]:
    """Replace ReplicatedBatch.BatchID uint32; keep all other payload bits."""
    from repblock import REP_BLOCK_PREFIX_BITS

    pos = REP_BLOCK_PREFIX_BITS
    h, hw = read_packed(payload, pos)
    if h is None or hw is None:
        raise RuntimeError("WAM payload: eof before BatchID")
    pos += hw
    if h != 3:
        raise RuntimeError(f"WAM payload: expected BatchID handle 3, got {h}")
    new_bits = _bits_u(int(batch_id), 32)
    return list(payload[:pos]) + new_bits + list(payload[pos + 32 :])


def build_wam_softclass_keep_skins_payload(
    netguid: int,
    batch_id: int = 2,
    capture_payloads: dict[int, list[int]] | None = None,
) -> list[int]:
    """Capture-open SoftClass shape with SoftClass ids + bumped BatchID.

    Preserves skins Parts / MainId / handle set from the capture open FINAL.
    """
    payloads = capture_payloads or extract_all_wam_open_payloads()
    capture = payloads[int(netguid)]
    soft_ids = wam_softclass_ids_for(int(netguid))
    spliced = splice_wam_payload_attachment_ids(capture, soft_ids)
    return splice_wam_payload_batch_id(spliced, batch_id)


def build_wam_post_stub_4606_payload(
    netguid: int,
    batch_id: int = 2,
    mode: str | None = None,
    capture_payloads: dict[int, list[int]] | None = None,
) -> list[int]:
    """Mid-flight SoftClass 4606 finish: stub 4606→151 or empty catalog.

    ``stub`` keeps capture skins/MainId/order and only swaps SoftClass 4606→151
    (same as open STUB but post-ACK BatchID bump). ``empty`` cancels SoftClass
    waits with stripped catalog (BatchID=2, skins=[], no MainId).
    """
    mode = mode or wam_softclass_post_stub_mode()
    if mode == "empty":
        return build_wam_stripped_catalog_payload(
            batch_id=batch_id, attachment_ids=())
    if mode == "skins_only":
        # Re-enter the native DirectReplicatedSkinsIds OnRep path without
        # changing the already-created attachment slots.  AttachmentIds are
        # cleared, while the capture's skin/MainId fields are preserved.
        payloads = capture_payloads or extract_all_wam_open_payloads()
        capture = payloads[int(netguid)]
        spliced = splice_wam_payload_attachment_ids(capture, ())
        return splice_wam_payload_batch_id(spliced, batch_id)
    if mode == "full_empty":
        # Preserve every SoftClass attachment ID while clearing only the
        # DirectReplicatedSkinsIds parts.  This is the safe BatchID bump:
        # existing slots remain unique, but the client re-runs its OnRep path.
        ids = WAM_SOFTCLASS_FULL_IDS.get(int(netguid), ())
        return build_wam_stripped_catalog_payload(
            batch_id=batch_id, attachment_ids=ids)
    payloads = capture_payloads or extract_all_wam_open_payloads()
    capture = payloads[int(netguid)]
    stub_ids = WAM_SOFTCLASS_STUB4606_IDS.get(int(netguid))
    if not stub_ids:
        raise RuntimeError(f"no SoftClass stub4606 ids for WAM {netguid}")
    spliced = splice_wam_payload_attachment_ids(capture, stub_ids)
    return splice_wam_payload_batch_id(spliced, batch_id)


def build_wam_post_stub_4606_resend_bits(
    netguid: int,
    batch_id: int = 2,
    mode: str | None = None,
) -> list[int]:
    """Stably-named WAM content: post-ACK SoftClass 4606 finish/skip."""
    w = GuidWriter()
    write_subobject_content_block(
        w, netguid, stably_named=1, has_rep_layout=1,
        payload_bits_list=build_wam_post_stub_4606_payload(
            int(netguid), batch_id=batch_id, mode=mode),
    )
    return _bits_from_writer(w)


def build_wam_early_empty_parts_resend_bits(
    netguid: int,
    batch_id: int = 2,
) -> list[int]:
    """Early SoftClass WAM: keep SoftClass AttachmentIds, empty skins Parts.

    Targets ch4/ch5 hist SoftClass opens (8314/7956). SoftClass catalog from
    capture early8; Parts/ItemTypes empty; MainId omitted.
    """
    soft_ids = WAM_SOFTCLASS_FULL_IDS.get(int(netguid))
    if not soft_ids:
        raise RuntimeError(f"no early SoftClass ids for WAM {netguid}")
    w = GuidWriter()
    write_subobject_content_block(
        w, netguid, stably_named=1, has_rep_layout=1,
        payload_bits_list=build_wam_stripped_catalog_payload(
            batch_id=batch_id,
            replicated_attachments=(),
            attachment_ids=soft_ids,
        ),
    )
    return _bits_from_writer(w)


def build_wam_strip_resend_bits(netguid: int, batch_id: int = 2) -> list[int]:
    """Stably-named weapon-channel content: stripped / SoftClass / keep WAM."""
    keep: tuple[int, ...] = ()
    soft_ids: tuple[int, ...] = ()
    if wam_spawn_attach_enabled():
        # SPAWN_ATTACH owns the keep list when on — STRIP_KEEP=0 means empty
        # ReplicatedAttachments (do not fall through to FireType KEEP_DYNAMIC).
        if wam_spawn_strip_keep_enabled():
            specs = wam_spawn_specs_for(netguid)
            keep = tuple(s.dyn_netguid for s in specs)
    elif wam_keep_clothing_enabled():
        # CAM analogue: already-mapped UWW3Attachment* on pawn ch3 (hat/chest).
        keep = (HAT_NETGUID, CHEST_NETGUID)
    elif wam_keep_dynamic_enabled():
        raw = WAM_KEEP_REPLICATED.get(int(netguid), ())
        keep = (raw,) if isinstance(raw, int) else tuple(raw)
    # SoftClass keep-skins: capture open payload + SoftClass ids + BatchID bump.
    # OPEN_ONLY wins (empty post-ACK). Keep-dyn/clothing/spawn supersede SoftClass.
    if (wam_softclass_catalog_enabled() and not keep
            and wam_softclass_keep_skins()
            and not wam_softclass_open_only()):
        w = GuidWriter()
        write_subobject_content_block(
            w, netguid, stably_named=1, has_rep_layout=1,
            payload_bits_list=build_wam_softclass_keep_skins_payload(
                int(netguid), batch_id=batch_id),
        )
        return _bits_from_writer(w)
    if (wam_softclass_catalog_enabled() and not keep
            and not wam_softclass_open_only()):
        # SoftClass path only when not using keep-dyn (keep supersedes SoftClass wait).
        # OPEN_ONLY: post-ACK stays empty catalog so BatchID=2 skins=[] does not
        # overwrite capture-open SoftClass shape (skins/MainId kept on open).
        soft_ids = wam_softclass_ids_for(int(netguid))
    w = GuidWriter()
    write_subobject_content_block(
        w, netguid, stably_named=1, has_rep_layout=1,
        payload_bits_list=build_wam_stripped_catalog_payload(
            batch_id=batch_id,
            replicated_attachments=keep,
            attachment_ids=soft_ids,
        ))
    return _bits_from_writer(w)


# SoftClass package-map export registry (item_id → class/package). Includes
# Muzzle/Barrel_024 that spawn-attach tables omit (SPAWN still Mag+Rail only).
# dyn_netguid unused for export-only; odd static GUIDs above spawn range.
WAM_SOFTCLASS_EXPORT_BY_ID: dict[int, WamAttachSpec] = {
    151: WamAttachSpec(0, _CLS_MAG_108, _PKG_GID_MAG_108,
                       "BP_WP_Magazine_108_01_C", _PKG_MAG_108, 151),
    143: WamAttachSpec(0, _CLS_MAG_116, _PKG_GID_MAG_116,
                       "BP_WP_Magazine_116_01_C", _PKG_MAG_116, 143),
    101: WamAttachSpec(0, _CLS_MUZZLE_020, _PKG_GID_MUZZLE_020,
                       "BP_WP_Muzzle_020_01_C", _PKG_MUZZLE_020, 101),
    108: WamAttachSpec(0, _CLS_MUZZLE_013, _PKG_GID_MUZZLE_013,
                       "BP_WP_Muzzle_013_01_C", _PKG_MUZZLE_013, 108),
    304: WamAttachSpec(0, _CLS_BARREL_024, _PKG_GID_BARREL_024,
                       "BP_WP_Barrel_024_01_C", _PKG_BARREL_024, 304),
    295: WamAttachSpec(0, _CLS_BARREL_033, _PKG_GID_BARREL_033,
                       "BP_WP_Barrel_033_01_C", _PKG_BARREL_033, 295),
    4606: WamAttachSpec(0, _CLS_RAIL_086, _PKG_GID_RAIL_086,
                        "BP_WP_Rail_086_01_C", _PKG_RAIL_086, 4606),
    4638: WamAttachSpec(0, _CLS_RECEIVER_008, _PKG_GID_RECEIVER_008,
                        "BP_WP_Receiver_008_02_C", _PKG_RECEIVER_008, 4638),
    4608: WamAttachSpec(0, _CLS_UPPER_091, _PKG_GID_UPPER_091,
                        "BP_WP_Upper_091_01_C", _PKG_UPPER_091, 4608),
    88: WamAttachSpec(0, _CLS_SIDE_006, _PKG_GID_SIDE_006,
                      "BP_WP_Side_006_01_C", _PKG_SIDE_006, 88),
    526: WamAttachSpec(0, _CLS_HANDGUARD_021, _PKG_GID_HANDGUARD_021,
                       "BP_WP_Handguard_021_01_C", _PKG_HANDGUARD_021, 526),
    346: WamAttachSpec(0, _CLS_STOCK_029, _PKG_GID_STOCK_029,
                       "BP_WP_Stock_029_01_C", _PKG_STOCK_029, 346),
    432: WamAttachSpec(0, _CLS_PISTOLGRIP_017, _PKG_GID_PISTOLGRIP_017,
                       "BP_WP_PistolGrip_017_01_C", _PKG_PISTOLGRIP_017, 432),
    7851: WamAttachSpec(0, _CLS_UPPERMINOR_SIDEARM, _PKG_GID_UPPERMINOR_SIDEARM,
                        "BP_WP_UpperMinor_026_06_PST_Sidearm_C",
                        _PKG_UPPERMINOR_SIDEARM, 7851),
    7847: WamAttachSpec(0, _CLS_UPPERMINOR_BR, _PKG_GID_UPPERMINOR_BR,
                        "BP_WP_UpperMinor_026_02_PST_BR_C",
                        _PKG_UPPERMINOR_BR, 7847),
}

# SoftClass ids to package-map-warm before early Glock SoftClass OnRep (hist074114).
# Mag + Rail only by default (Sync-arm hang surface) — keep export bunch small
# (~4 classes). Full early SoftClass set blew a 10801-bit single bunch and the
# client CHANNEL CLOSEd ch0 mid-ownership (rematch 130535).
WAM_SOFTCLASS_WARM_IDS: tuple[int, ...] = (151, 4606, 143, 295)


def _specs_for_softclass_ids(wanted: set[int]) -> tuple[WamAttachSpec, ...]:
    """Resolve AttachmentIds → SoftClass export specs (registry, then spawn)."""
    if not wanted:
        return ()
    by_id: dict[int, WamAttachSpec] = {}
    for iid in wanted:
        if iid in WAM_SOFTCLASS_EXPORT_BY_ID:
            by_id[iid] = WAM_SOFTCLASS_EXPORT_BY_ID[iid]
    for ng in WAM_STRIP_NETGUIDS:
        for s in WAM_SPAWN_ATTACHMENTS.get(ng, ()):
            if s.item_id in wanted and s.item_id not in by_id:
                by_id[s.item_id] = s
    # Preserve warm / mode order when provided; else sorted.
    return tuple(by_id[i] for i in sorted(by_id))


def collect_wam_softclass_export_specs() -> tuple[WamAttachSpec, ...]:
    """BP_WP_* class specs to package-map export for the active SoftClass ids."""
    wanted: set[int] = set()
    for ng in WAM_STRIP_NETGUIDS:
        wanted.update(wam_softclass_ids_for(ng))
    return _specs_for_softclass_ids(wanted)


def collect_wam_softclass_warm_export_specs() -> tuple[WamAttachSpec, ...]:
    """Mag/Rail (+ known early SoftClass) package-map specs for pre-open warm."""
    wanted = set(WAM_SOFTCLASS_WARM_IDS)
    by_id: dict[int, WamAttachSpec] = {}
    for iid in WAM_SOFTCLASS_WARM_IDS:
        if iid in WAM_SOFTCLASS_EXPORT_BY_ID:
            by_id[iid] = WAM_SOFTCLASS_EXPORT_BY_ID[iid]
    for ng in WAM_STRIP_NETGUIDS:
        for s in WAM_SPAWN_ATTACHMENTS.get(ng, ()):
            if s.item_id in wanted and s.item_id not in by_id:
                by_id[s.item_id] = s
    # Keep Mag/Rail-first order from WAM_SOFTCLASS_WARM_IDS.
    return tuple(by_id[i] for i in WAM_SOFTCLASS_WARM_IDS if i in by_id)


def _attach_export_spec(spec: WamAttachSpec) -> dict:
    """Package-map export mirroring clothing hat/chest (path; optional checksum)."""
    cs = wam_spawn_checksum()
    return {
        "gid": int(spec.class_netguid),
        "path": spec.class_name,
        "checksum": cs,
        "outer": {
            "gid": int(spec.package_netguid),
            "path": spec.package_path,
            "checksum": cs,
            "outer": None,
        },
    }


def build_wam_attach_export_bits(specs: tuple[WamAttachSpec, ...] | list[WamAttachSpec]) -> list[int]:
    """NetGUID export block for the BP_WP_* classes in `specs` (dedupe by class)."""
    seen: set[int] = set()
    export_specs: list[dict] = []
    for s in specs:
        if s.class_netguid in seen:
            continue
        seen.add(s.class_netguid)
        export_specs.append(_attach_export_spec(s))
    w = GuidWriter()
    write_export_block(w, export_specs)
    return _bits_from_writer(w)


def build_attachment_minimal_payload() -> list[int]:
    """UWW3Attachment RepLayout: AttachmentBatchID=1 only (CAM-style minimal)."""
    return write_rep_properties([
        (1, _bits_u(1, 32)),  # AttachmentBatchID
    ])


def build_attachment_health_payload() -> list[int]:
    """UWW3AttachmentDamageable: BatchID=1 + HealthReplicated=100."""
    return write_rep_properties([
        (1, _bits_u(1, 32)),
        (2, _bits_u(100, 32)),
    ])


def build_attachment_hat_copy_payload() -> list[int]:
    """Bit-copy clothing hat 9404 payload (113 bits) — BP_WP may share base handles."""
    for b in parse_clothing_content_blocks():
        if b["subNetGUID"] == HAT_NETGUID and b.get("payload"):
            return list(b["payload"])
    return build_attachment_minimal_payload()


def build_attachment_spawn_payload() -> list[int]:
    mode = wam_spawn_payload_mode()
    if mode == "empty":
        return []
    if mode == "hat":
        return build_attachment_hat_copy_payload()
    if mode == "health":
        return build_attachment_health_payload()
    return build_attachment_minimal_payload()


def build_wam_attach_spawn_bits(specs: tuple[WamAttachSpec, ...] | list[WamAttachSpec]) -> list[int]:
    """stably=0 hasRep content blocks creating dynamic BP_WP_* attachment instances."""
    payload = build_attachment_spawn_payload()
    has_rep = 1 if payload else 0
    w = GuidWriter()
    for s in specs:
        write_subobject_content_block(
            w,
            s.dyn_netguid,
            stably_named=0,
            has_rep_layout=has_rep,
            class_netguid=s.class_netguid,
            payload_bits_list=payload,
        )
    return _bits_from_writer(w)


def build_wam_attach_spawn_packet_bits(
    wam_netguid: int,
) -> tuple[list[int], list[int], tuple[int, ...]]:
    """-> (export_bits, spawn_content_bits, dyn_netguids) for one WAM.

    CAM clothing: exports + stably=0 hat/chest on pawn ch3, then CAM refs GUIDs.
    Default host=weapon puts export+spawn on the WAM actor ch (CLOSES live).
    host=pawn puts them on ch3; WAM strip on weapon ch only refs the dyn GUIDs.
    """
    specs = wam_spawn_specs_for(wam_netguid)
    if not specs:
        return [], [], ()
    exp = build_wam_attach_export_bits(specs) if wam_spawn_export_enabled() else []
    spawn = build_wam_attach_spawn_bits(specs) if wam_spawn_content_enabled() else []
    return (
        exp,
        spawn,
        tuple(s.dyn_netguid for s in specs),
    )


def collect_wam_spawn_specs() -> tuple[WamAttachSpec, ...]:
    """All spawn specs for current CHANNELS/ATT_LIMIT (dedupe by dyn NetGUID)."""
    seen: set[int] = set()
    out: list[WamAttachSpec] = []
    for netguid in wam_spawn_target_netguids():
        for s in wam_spawn_specs_for(netguid):
            if s.dyn_netguid in seen:
                continue
            seen.add(s.dyn_netguid)
            out.append(s)
    return tuple(out)


def _find_wam_block_header(bits: list[int], wam_netguid: int) -> dict | None:
    """Locate stably-named hasRep WAM content-block header for `wam_netguid`."""
    n = len(bits)
    for hdr in range(0, max(0, n - 24)):
        p = hdr
        has_rep = bits[p]
        is_actor = bits[p + 1]
        p += 2
        if not has_rep or is_actor:
            continue
        sub, sw = read_packed(bits, p)
        if sub != wam_netguid or sw is None:
            continue
        p += sw
        if p >= n:
            continue
        stably = bits[p]
        p += 1
        if stably != 1:
            # Early/INV_ATTACH WAMs are stably-named; skip dynamic headers.
            continue
        nbits, nw = read_packed(bits, p)
        # Empty-catalog strip is ~145 bits (omit MainId/Num); keep-dyn ~217.
        # Capture opens are 457–505. Mag splice into capture keeps skins → ~289+.
        # Reject tiny noise / truncated headers.
        if nbits is None or nw is None or nbits < 100:
            continue
        p += nw
        if p + nbits > n:
            continue
        return {
            "hdr": hdr,
            "nbits_pos": p - nw,
            "nbits_width": nw,
            "nbits": nbits,
            "payload_start": p,
            "payload_end": p + nbits,
        }
    return None


def _consume_uint16_array(bits: list[int], pos: int) -> int:
    """Advance past one REPCMD_DynamicArray<uint16>; return end bit index."""
    from repblock import read_u

    num = read_u(bits, pos, 16)
    if num is None:
        raise RuntimeError("uint16 array: missing ArrayNum")
    pos += 16
    seen = 0
    while True:
        idx, iw = read_packed(bits, pos)
        if idx is None or iw is None:
            raise RuntimeError("uint16 array: truncated idx")
        pos += iw
        if idx == 0:
            return pos
        pos += 16
        seen += 1
        if seen > max(num, 1) + 1 or seen > 4096:
            raise RuntimeError("uint16 array: overrun")


def find_wam_attachment_ids_span(payload: list[int]) -> tuple[int, int]:
    """(value_start, value_end) of ReplicatedBatch.AttachmentIds[] in a WAM payload.

    Walks packed handles; skips BatchID / NumReplicatedAttachments that can
    precede handle 5 on capture or keep-dyn layouts.
    """
    from repblock import REP_BLOCK_PREFIX_BITS

    pos = REP_BLOCK_PREFIX_BITS
    while True:
        h, hw = read_packed(payload, pos)
        if h is None or hw is None:
            raise RuntimeError("WAM payload: eof before AttachmentIds")
        pos += hw
        if h == 0:
            raise RuntimeError("WAM payload: terminator before AttachmentIds")
        if h == 5:
            start = pos
            end = _consume_uint16_array(payload, pos)
            return start, end
        if h == 3:
            pos += 32  # BatchID uint32
        elif h == 4:
            pos += 8   # NumReplicatedAttachments uint8
        else:
            raise RuntimeError(
                f"WAM payload: unexpected handle {h} before AttachmentIds")


def splice_wam_payload_attachment_ids(
    payload: list[int],
    attachment_ids: list[int] | tuple[int, ...],
) -> list[int]:
    """Replace only AttachmentIds[] value bits; keep skins / MainId / handles."""
    start, end = find_wam_attachment_ids_span(payload)
    new_ids = _bits_uint16_array(tuple(int(v) for v in attachment_ids))
    return list(payload[:start]) + new_ids + list(payload[end:])


def rewrite_weapon_final_strip_wam(
    bits: list[int],
    wam_netguid: int,
    batch_id: int = 1,
) -> list[int]:
    """Rewrite WAM RepLayout in a weapon-open FINAL partial.

    Uses in-place NumBits+payload splice (keeps all other bits). Required for
    ownership early Glock FINALs (src 15/17): NewActor reader is 3 bits short of
    the real content start, so a full content-block rewrite from gr.pos fails, but
    the WAM payload still sits entirely in the FINAL and can be spliced.

    Default (SoftClass off): empty catalog + BatchID=1 — never starts ItemDatabase
    SoftClass waits.

    SoftClass on: Mag/min/full AttachmentIds spliced **into the capture open
    payload** (skins / MainId / handle set preserved). Full strip rebuild of
    SoftClass shape never arms OnAttachmentManagerSynchronized; only the capture
    open RepLayout mid-flight path NewObjects Mag offline. Mag-only avoids Rail
    4606 hang. `batch_id` is ignored on SoftClass splice (capture BatchID kept).
    """
    hdr = _find_wam_block_header(bits, wam_netguid)
    if hdr is None:
        raise RuntimeError(f"WAM {wam_netguid} missing from weapon final")
    capture_payload = bits[hdr["payload_start"] : hdr["payload_end"]]
    if wam_softclass_catalog_enabled():
        soft_ids = wam_softclass_ids_for(int(wam_netguid))
        new_payload = splice_wam_payload_attachment_ids(capture_payload, soft_ids)
    else:
        new_payload = build_wam_stripped_catalog_payload(
            batch_id=batch_id,
            attachment_ids=(),
        )
    w = GuidWriter()
    for b in bits[: hdr["nbits_pos"]]:
        w.write_bit(b)
    w.write_packed(len(new_payload))
    for b in new_payload:
        w.write_bit(b)
    for b in bits[hdr["payload_end"] :]:
        w.write_bit(b)
    return _bits_from_writer(w)


def maybe_strip_wam_in_weapon_open_bits(bits: list[int], src_idx: int) -> list[int] | None:
    """If src is a WAM open FINAL and strip is on, return rewritten bits; else None."""
    if not wam_strip_catalog_enabled():
        return None
    wam = wam_open_strip_srcs().get(int(src_idx))
    if wam is None:
        return None
    return rewrite_weapon_final_strip_wam(bits, wam, batch_id=1)


def maybe_stub_softclass_4606_in_weapon_open_bits(
    bits: list[int], src_idx: int,
) -> list[int] | None:
    """Hist SoftClass native opens: splice SoftClass 4606→151 without empty strip.

    Under ``WW3_WAM_STRIP_CHANNELS=inv`` early Glock FINALs (src 15/17) keep
    capture SoftClass catalogs — Mag NewObject can arm. When Mag*_C_0 is seen
    but Rail 4606 never finishes, this flag finishes/skips 4606 by replacing
    that SoftClass id with Mag 151 (capture order/count/skins/MainId kept).
    Skips WAMs already rewritten by the open-strip path.
    """
    if not wam_softclass_stub_4606_enabled():
        return None
    src = int(src_idx)
    wam = WAM_OPEN_FINAL_SRCS.get(src)
    if wam is None:
        return None
    # Already empty-stripped or SoftClass-catalog rewritten by strip path.
    if wam_strip_catalog_enabled() and src in wam_open_strip_srcs():
        return None
    full = WAM_SOFTCLASS_FULL_IDS.get(int(wam))
    stub = WAM_SOFTCLASS_STUB4606_IDS.get(int(wam))
    if not full or not stub or full == stub:
        return None
    hdr = _find_wam_block_header(bits, int(wam))
    if hdr is None:
        raise RuntimeError(f"WAM {wam} missing from weapon final (stub 4606)")
    capture_payload = bits[hdr["payload_start"] : hdr["payload_end"]]
    new_payload = splice_wam_payload_attachment_ids(capture_payload, stub)
    if new_payload == list(capture_payload):
        return None
    w = GuidWriter()
    for b in bits[: hdr["nbits_pos"]]:
        w.write_bit(b)
    w.write_packed(len(new_payload))
    for b in new_payload:
        w.write_bit(b)
    for b in bits[hdr["payload_end"] :]:
        w.write_bit(b)
    return _bits_from_writer(w)
