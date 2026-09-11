#!/usr/bin/env python3
"""Map capture WAM AttachmentIds -> BP_WP_* package paths; decode hat payload."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import derive_rep_handles as D  # noqa: E402
from cam_im_resend import (  # noqa: E402
    CAPTURE_WAM_EARLY_ATTACHMENT_IDS,
    CAPTURE_WAM_PRIMARY_ATTACHMENT_IDS,
    CAPTURE_WAM_SECONDARY_ATTACHMENT_IDS,
    parse_clothing_content_blocks,
)
from _decode_rep_block import decode, layout  # noqa: E402

DUMP = Path(str(D.DEFAULT_DUMP))
GOBJ = DUMP / "GObjects-Dump.txt"

# From crash FD35FE0D Glock OnAttachmentManagerSynchronized (id -> class)
CRASH_ID_TO_CLS = {
    101: "BP_WP_Muzzle_020_01_C",
    304: "BP_WP_Barrel_024_01_C",
    4608: "BP_WP_Upper_091_01_C",
    7851: "BP_WP_UpperMinor_026_06_PST_Sidearm_C",
    4606: "BP_WP_Rail_086_01_C",
    4638: "BP_WP_Receiver_008_02_C",
    151: "BP_WP_Magazine_108_01_C",
}

# Parse more id->class from all crash logs
pat = re.compile(
    r"OnAttachmentManagerSynchronized\(\)\s*:\s*\d+\s*-\s*(BP_WP_[A-Za-z0-9_]+),\s*\d+,\s*(\d+),"
)
id_to_cls: dict[int, str] = dict(CRASH_ID_TO_CLS)
crash_root = HERE.parent / "analysis" / "crashes"
for log in crash_root.rglob("WW3.log"):
    text = log.read_text(encoding="utf-8", errors="replace")
    for m in pat.finditer(text):
        cls, iid = m.group(1), int(m.group(2))
        id_to_cls.setdefault(iid, cls)

ids = sorted(
    set(
        CAPTURE_WAM_SECONDARY_ATTACHMENT_IDS
        + CAPTURE_WAM_PRIMARY_ATTACHMENT_IDS
        + CAPTURE_WAM_EARLY_ATTACHMENT_IDS
    )
)
print("=== capture id -> crash class ===")
for i in ids:
    print(f"  {i}: {id_to_cls.get(i, '?')}")

# Resolve package paths from GObjects
need_cls = {id_to_cls[i] for i in ids if i in id_to_cls}
# strip trailing _C for package search
need_pkg = {c[:-2] if c.endswith("_C") else c for c in need_cls}
print("\n=== GObjects package paths ===")
paths: dict[str, str] = {}
with GOBJ.open(encoding="utf-8", errors="replace") as f:
    for line in f:
        for pkg in list(need_pkg):
            if pkg in line and ("Package " in line or "BlueprintGeneratedClass" in line):
                # Prefer Package line with full path if present
                if f"Package {pkg}" in line or f".{pkg}" in line:
                    paths.setdefault(pkg, line.rstrip()[:220])
for pkg, ln in sorted(paths.items()):
    print(f"  {pkg}: {ln}")

# Also search for /Game/ paths containing BP_WP_
print("\n=== /Game/ path samples for mapped classes ===")
game_paths: dict[str, str] = {}
with GOBJ.open(encoding="utf-8", errors="replace") as f:
    for line in f:
        if "/Game/" not in line:
            continue
        for pkg in need_pkg:
            if pkg in line:
                m = re.search(r"(/Game/[A-Za-z0-9_./]+" + re.escape(pkg) + r")", line)
                if m:
                    game_paths.setdefault(pkg, m.group(1))
for pkg, p in sorted(game_paths.items()):
    print(f"  {pkg}: {p}")

# SDK class files for those BPs (non-Preview)
sdk = DUMP / "CppSDK" / "SDK"
print("\n=== SDK class files ===")
for pkg in sorted(need_pkg):
    hits = list(sdk.glob(f"{pkg}_classes.hpp"))
    print(f"  {pkg}: {[h.name for h in hits]}")
    if hits:
        txt = hits[0].read_text(encoding="utf-8", errors="replace")
        # parent class
        m = re.search(r"public\s+(U\w+)", txt)
        print(f"    parent={m.group(1) if m else '?'}")

# Hat payload decode (113 bits) — template for minimal attachment
print("\n=== hat/chest RepLayout decode ===")
sdk_classes, structs = D.parse_sdk(sdk)
enums = D.parse_enums(sdk)
blocks = parse_clothing_content_blocks()
for sub in (9404, 9406):
    b = next(x for x in blocks if x["subNetGUID"] == sub)
    print(f"\nsub={sub} nbits={b['payloadBits']} cls={b['classNetGUID']}")
    for leaf in (
        "UWW3Attachment",
        "UWW3CharacterAttachment",
        "UWW3AttachmentDamageable",
        "UObject",
    ):
        if leaf not in sdk_classes:
            # try find
            cands = [c for c in sdk_classes if leaf in c]
            print(f"  {leaf} missing; cands={cands[:5]}")
            continue
        try:
            bh, ty = layout(leaf, sdk_classes, structs)
        except Exception as e:
            print(f"  {leaf}: {e}")
            continue
        r = decode(b["payload"], bh, ty, enums=enums)
        print(
            f"  {leaf}: closed={r['closed']} props={len(r['seq'])} "
            f"reason={r.get('reason')} left={r.get('left')}"
        )
        for h, name, typ, w, note, p0 in r["seq"][:15]:
            print(f"    h{h} {name} {note}")

# Primary (HK417) id mapping — search crash for those ids
print("\n=== primary catalog id crash hits ===")
for i in CAPTURE_WAM_PRIMARY_ATTACHMENT_IDS:
    print(f"  {i}: {id_to_cls.get(i, '?')}")
