#!/usr/bin/env python3
"""Dump hat/chest opens + weapon-open exports; map WAM AttachmentIds -> BP_WP_*."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from cam_im_resend import (  # noqa: E402
    CAPTURE_WAM_EARLY_ATTACHMENT_IDS,
    CAPTURE_WAM_PRIMARY_ATTACHMENT_IDS,
    CAPTURE_WAM_SECONDARY_ATTACHMENT_IDS,
    parse_clothing_content_blocks,
)
from netguid import PackageMap  # noqa: E402
import derive_rep_handles as D  # noqa: E402

stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))


def dump_exports(label: str, srcs: tuple[int, ...]) -> PackageMap:
    bits: list[int] = []
    for i in srcs:
        bits.extend(int(c) for c in stream[i]["payload"])
    pm = PackageMap()
    exp = pm.read_export_bunch(bits)
    print(f"\n=== {label} exports n={exp['num']} ===")
    for gid, path in sorted(pm.guid_to_path.items()):
        print(f"  {gid}: {path}")
    return pm, bits


print("=== clothing content (hat/chest pattern) ===")
bits = []
for i in (212, 213):
    bits.extend(int(c) for c in stream[i]["payload"])
pm = PackageMap()
pm.read_export_bunch(bits)
for b in parse_clothing_content_blocks(bits):
    cls = b.get("classNetGUID")
    print(
        f"  sub={b['subNetGUID']} stably={b['stablyNamed']} "
        f"cls={cls}({pm.guid_to_path.get(cls)}) "
        f"hasRep={b['hasRepLayout']} bits={b['payloadBits']}"
    )

dump_exports("clothing 212-213", (212, 213))
for label, srcs in [
    ("ch4 glock", (14, 15)),
    ("ch5 glock", (16, 17)),
    ("ch86 glock", (257, 258)),
    ("ch87 hk417", (259, 260)),
]:
    dump_exports(label, srcs)

# SDK: find BP_WP_* and ItemDatabase id mapping if present
sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
print(f"\n=== SDK @ {sdk} exists={sdk.is_dir()} ===")
gobjects = Path(str(D.DEFAULT_DUMP)) / "GObjects-Dump.txt"
if gobjects.is_file():
    print(f"GObjects: {gobjects}")
    ids = set(
        CAPTURE_WAM_SECONDARY_ATTACHMENT_IDS
        + CAPTURE_WAM_PRIMARY_ATTACHMENT_IDS
        + CAPTURE_WAM_EARLY_ATTACHMENT_IDS
    )
    # Search for BP_WP_ lines and id mentions
    wp_lines = []
    id_hits: dict[int, list[str]] = {i: [] for i in ids}
    with gobjects.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if "BP_WP_" in line:
                wp_lines.append(line.rstrip())
            for i in ids:
                # soft: look for exact id as token near BP_WP
                if f" {i} " in f" {line} " or line.strip().endswith(str(i)):
                    if "WP_" in line or "Attachment" in line or "Item" in line:
                        id_hits[i].append(line.rstrip()[:200])
    print(f"BP_WP_ lines in GObjects: {len(wp_lines)}")
    for ln in wp_lines[:40]:
        print(" ", ln[:180])
    if len(wp_lines) > 40:
        print(f"  ... +{len(wp_lines)-40} more")
    print("\n=== id -> nearby GObjects lines ===")
    for i in sorted(ids):
        print(f"  id={i}: {id_hits[i][:3]}")

# Also search SDK headers for SoftClass / item id tables
if sdk.is_dir():
    hits = list(sdk.rglob("*ItemDatabase*"))
    print(f"\nItemDatabase SDK files: {hits[:10]}")
    # Grep BP_WP_Rail_086
    rail = []
    for p in sdk.rglob("*.hpp"):
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if "BP_WP_Rail_086" in txt or "WP_Rail_086" in txt:
            rail.append(str(p))
    print(f"headers mentioning Rail_086: {rail[:5]}")
