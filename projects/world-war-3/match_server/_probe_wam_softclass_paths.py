#!/usr/bin/env python3
"""Resolve WAM AttachmentIds -> SoftClass BP_WP_* paths via ItemDatabase dump/SDK."""
from __future__ import annotations

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
)

DUMP = Path(str(D.DEFAULT_DUMP))
IDS = sorted(
    set(
        CAPTURE_WAM_SECONDARY_ATTACHMENT_IDS
        + CAPTURE_WAM_PRIMARY_ATTACHMENT_IDS
        + CAPTURE_WAM_EARLY_ATTACHMENT_IDS
    )
)

# 1) Search ObjectsDump / GObjects / Strings for SoftClass paths near AttachmentData
search_roots = [
    DUMP / "GObjects-Dump.txt",
    DUMP / "ObjectsDump.txt",
    DUMP / "ObjectDump.txt",
]
for p in DUMP.iterdir() if DUMP.is_dir() else []:
    if p.suffix.lower() in {".txt", ".json", ".csv"} and p.is_file():
        if p not in search_roots:
            search_roots.append(p)

print("=== dump files ===")
for p in search_roots:
    print(f"  {p.name}: exists={p.is_file()} size={p.stat().st_size if p.is_file() else 0}")

# SoftObject paths often live in .uasset dumps or SDK FSoftObjectPath comments —
# also check for XXHash / NameDump
name_files = list(DUMP.glob("*Name*")) + list(DUMP.glob("*String*"))
print("name/string files:", [str(p) for p in name_files[:20]])

# Parse SDK WW3AttachmentData / SoftClass fields
sdk = DUMP / "CppSDK" / "SDK"
att_hpp = list(sdk.glob("*Attachment*Data*")) + list(sdk.glob("*WW3Attachment*"))
print("\n=== attachment SDK headers ===")
for p in att_hpp[:30]:
    print(" ", p.name)

# Read WW3AttachmentData struct
for name in (
    "WW3_structs.hpp",
    "WW3AttachmentData_structs.hpp",
    "Basic.hpp",
):
    p = sdk / name
    if p.is_file():
        txt = p.read_text(encoding="utf-8", errors="replace")
        if "WW3AttachmentData" in txt or "AttachmentClass" in txt or "SoftClass" in txt:
            print(f"\n--- hits in {name} ---")
            for m in re.finditer(r".{0,80}(WW3AttachmentData|AttachmentClass|SoftClass|ItemClass).{0,120}", txt):
                print(" ", m.group(0).replace("\n", " ")[:200])

# Search all hpp for AttachmentClass / LoadedClass Soft
print("\n=== SoftClass field names near Attachment ===")
for p in sdk.glob("*.hpp"):
    txt = p.read_text(encoding="utf-8", errors="replace")
    if "TSoftClassPtr" in txt and ("Attachment" in txt or "WeaponPart" in txt or "WP_" in txt):
        print(f"\n{p.name}:")
        for i, line in enumerate(txt.splitlines()):
            if "TSoftClassPtr" in line or "AttachmentClass" in line or "PartClass" in line:
                print(f"  {i}: {line.strip()[:160]}")

# Crash log: OnAttachmentManagerSynchronized lines
crash_root = HERE.parent / "analysis" / "crashes"
print("\n=== crash OnAttachmentManagerSynchronized samples ===")
pat = re.compile(r"OnAttachmentManagerSynchronized.{0,200}")
n = 0
if crash_root.is_dir():
    for log in crash_root.rglob("WW3.log"):
        try:
            text = log.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for m in pat.finditer(text):
            print(f"  {log.parent.name}: {m.group(0)[:180]}")
            n += 1
            if n >= 30:
                break
        if n >= 30:
            break
print(f"total printed={n}")

# Also search live client logs
live = HERE / "live_log"
print("\n=== live_log OnAttachment / BP_WP samples ===")
for p in sorted(live.glob("*.txt"))[-5:]:
    pass
# search client log if any
for p in list(live.rglob("*"))[:0]:
    pass
client_logs = list(Path(r"C:\Users\georg").glob("**/WW3.log")) if False else []
# Prefer repo captures of heap strings
for p in (HERE / "_probe_softclass_pending.py",):
    print(p.read_text(encoding="utf-8")[:500])
