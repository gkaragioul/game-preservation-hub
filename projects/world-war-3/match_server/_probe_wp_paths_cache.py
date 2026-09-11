#!/usr/bin/env python3
"""Find BP_WP SoftClass package paths from cache manifest / process / files."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

NEED = [
    "BP_WP_Rail_086",
    "BP_WP_Muzzle_020",
    "BP_WP_Magazine_108",
    "BP_WP_Barrel_024",
    "BP_WP_Barrel_033",
    "BP_WP_Magazine_116",
    "BP_WP_Handguard_021",
    "BP_WP_Stock_029",
    "BP_WP_PistolGrip_017",
    "BP_WP_Receiver_008",
    "BP_WP_Upper_091",
    "BP_CH_Hat_004",
]

cache = Path(r"E:\SteamLibrary\steamapps\common\World War 3\_cache")
print("=== cache manifest keys mentioning BP_WP / Attachments ===")
for mf in cache.rglob("*.json"):
    try:
        data = json.loads(mf.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        print(mf, e)
        continue
    text = json.dumps(data)
    print(mf, "size", len(text))
    for n in NEED:
        if n in text:
            # extract nearby paths
            for m in re.finditer(r".{0,80}" + re.escape(n) + r".{0,80}", text):
                print(" ", m.group(0)[:160])

# Also flatten all string values containing /Game/
print("\n=== /Game/Blueprints paths in manifest (sample) ===")
for mf in cache.rglob("*.json"):
    data = json.loads(mf.read_text(encoding="utf-8", errors="replace"))

    def walk(obj, out):
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(k, out)
                walk(v, out)
        elif isinstance(obj, list):
            for x in obj:
                walk(x, out)
        elif isinstance(obj, str):
            if "/Game/" in obj or "BP_WP_" in obj or "Attachments" in obj:
                out.append(obj)

    out = []
    walk(data, out)
    for s in out[:40]:
        print(" ", s[:200])
    print(" total interesting strings", len(out))

# tasklist
print("\n=== processes ===")
out = subprocess.check_output(["tasklist"], text=True, errors="replace")
for line in out.splitlines():
    if re.search(r"WW3|WorldWar", line, re.I):
        print(line)
