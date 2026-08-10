#!/usr/bin/env python3
"""Prove Mag/Rail are SoftClass-only in capture (no channel opens / exports)."""
from __future__ import annotations

import json
from pathlib import Path

from actor_channel import read_new_actor
from cam_im_resend import _walk_content_blocks, parse_clothing_content_blocks
from netguid import GuidReader, PackageMap

HERE = Path(__file__).resolve().parent
stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))

NEEDLES = (
    "Magazine_108", "Rail_086", "Magazine_116", "Barrel_033",
    "BP_WP_", "WeaponAttachments/Magazine", "BodyParts/Rail",
)


def main() -> None:
    bits: list[int] = []
    for i in (212, 213):
        bits.extend(int(c) for c in stream[i]["payload"])
    pm = PackageMap()
    pm.read_export_bunch(bits)
    print("=== clothing 212-213 (CAM hat/chest pattern) ===")
    for gid, path in sorted(pm.guid_to_path.items()):
        print(f"  {gid}: {path}")
    for b in parse_clothing_content_blocks(bits):
        cls = b.get("classNetGUID")
        print(
            f"  sub={b['subNetGUID']} stably={b['stablyNamed']} "
            f"cls={cls}({pm.guid_to_path.get(cls)}) "
            f"hasRep={b['hasRepLayout']} bits={b['payloadBits']}"
        )

    print("\n=== timeline: early Glocks / clothing / INV_ATTACH ===")
    for i in (10, 14, 15, 16, 17, 212, 213, 257, 258, 259, 260):
        r = stream[i]
        print(
            f"  src={i} ch={r.get('ch')} open={r.get('open')} "
            f"partial={r.get('partial')} bits={len(r.get('payload', ''))}"
        )

    print("\n=== ALL export paths matching Mag/Rail/WP_* ===")
    hits = []
    for i, rec in enumerate(stream):
        payload = rec.get("payload", "")
        if not payload:
            continue
        bits = [int(c) for c in payload]
        pm = PackageMap()
        try:
            exp = pm.read_export_bunch(bits)
        except Exception:
            continue
        if exp.get("num", 0) <= 0:
            continue
        for gid, path in pm.guid_to_path.items():
            if any(n in path for n in NEEDLES):
                hits.append((i, rec.get("ch"), gid, path))
    print(f"hits={len(hits)}")
    for h in hits[:40]:
        print(f"  {h}")

    print("\n=== stably=0 FireType/Hat/Chest/WP on weapon opens ===")
    for label, srcs in [
        ("ch4", (14, 15)),
        ("ch5", (16, 17)),
        ("ch86", (257, 258)),
        ("ch87", (259, 260)),
    ]:
        bits = []
        for i in srcs:
            bits.extend(int(c) for c in stream[i]["payload"])
        pm = PackageMap()
        pos = pm.read_export_bunch(bits)["reader"].pos
        gr = GuidReader(bits, pos)
        info = read_new_actor(gr, pm)
        blocks = []
        for off in range(gr.pos, min(gr.pos + 12, len(bits))):
            try:
                blocks = _walk_content_blocks(bits, off)
                if blocks:
                    break
            except Exception:
                continue
        print(f"\n{label} actor={info.get('netguid')} arch={info.get('archetypePath')}")
        for b in blocks:
            if b.get("stablyNamed") != 0 and (b.get("payloadBits") or 0) < 40:
                continue
            cls = b.get("classNetGUID")
            print(
                f"  sub={b['subNetGUID']} stably={b['stablyNamed']} "
                f"cls={cls}({pm.guid_to_path.get(cls)}) "
                f"hasRep={b['hasRepLayout']} bits={b['payloadBits']}"
            )

    print("\n=== actor opens whose archetypePath mentions WP_/Magazine/Rail ===")
    n_open = 0
    for i, rec in enumerate(stream):
        payload = rec.get("payload", "")
        if not payload or len(payload) < 40:
            continue
        bits = [int(c) for c in payload]
        pm = PackageMap()
        try:
            exp = pm.read_export_bunch(bits)
            pos = exp["reader"].pos
        except Exception:
            continue
        try:
            gr = GuidReader(bits, pos)
            info = read_new_actor(gr, pm)
        except Exception:
            continue
        if not info.get("netguid"):
            continue
        n_open += 1
        path = info.get("archetypePath") or ""
        if any(n in path for n in NEEDLES + ("Hat_", "Chest", "BP_CH_")):
            print(
                f"  src={i} ch={rec.get('ch')} netguid={info['netguid']} "
                f"arch={path}"
            )
    print(f"total actor opens parsed: {n_open}")


if __name__ == "__main__":
    main()
