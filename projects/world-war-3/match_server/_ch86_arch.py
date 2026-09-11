#!/usr/bin/env python3
"""Find archetype GUID for ch86 weapon 9412."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "match_server")
from netguid import PackageMap, GuidReader
from actor_channel import Bits, read_new_actor

stream = json.loads(Path("match_server/real_replay_stream.json").read_text(encoding="utf-8"))
bits = []
for i in (257, 258):
    bits.extend(int(c) for c in stream[i]["payload"])
pm = PackageMap()
res = pm.read_export_bunch(bits)
gr = GuidReader(bits, res["reader"].pos)
# Manual: packed actor, packed arch, packed level
info = read_new_actor(gr, pm)
print("info", {k: v for k, v in info.items() if k != "scale_raw_bits"})
print("archetype guid raw - re-read")
pm2 = PackageMap()
res2 = pm2.read_export_bunch(bits)
r = Bits(bits, res2["reader"].pos)
actor = r.packed()
arch = r.packed()
lvl = r.packed()
print(f"actor={actor} arch={arch} lvl={lvl}")
print(f"arch path in pm after exports: {pm2.guid_to_path.get(arch)}")

# Find where arch guid is exported in stream
arch_g = arch
for i, sp in enumerate(stream):
    if i >= 257:
        break
    if not sp.get("bHasPackageMapExports"):
        continue
    try:
        rr = PackageMap().read_export_bunch([int(c) for c in sp["payload"]])
    except Exception:
        continue
    for e in rr["exports"]:
        if e.get("netguid") == arch_g or (e.get("path") and "Glock" in str(e.get("path"))):
            if e.get("netguid") == arch_g or i > 240:
                print(f"  src={i} ch={sp['chIndex']} {e.get('netguid')} {e.get('path')}")
