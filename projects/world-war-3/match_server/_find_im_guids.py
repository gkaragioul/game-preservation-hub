#!/usr/bin/env python3
"""Locate NetGUIDs referenced by clothing IM payload (9402/9408/9410/9412)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from netguid import PackageMap  # noqa: E402

WANT = {9402, 9404, 9406, 9408, 9410, 9412}
stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
found = {g: [] for g in WANT}
for i, sp in enumerate(stream):
    if not sp.get("bHasPackageMapExports"):
        continue
    bits = [int(c) for c in sp["payload"]]
    try:
        res = PackageMap().read_export_bunch(bits)
    except Exception:
        continue
    for e in res["exports"]:
        g = e.get("netguid")
        if g in WANT or e.get("outer") in WANT:
            found.setdefault(g, []).append(
                (i, sp["chIndex"], e.get("outer"), e.get("path"), e.get("checksum"))
            )
            print(
                f"src={i} ch={sp['chIndex']} guid={g} outer={e.get('outer')} "
                f"path={e.get('path')} cs={e.get('checksum')}"
            )

print("\nsummary:")
for g in sorted(WANT):
    print(f"  {g}: {len(found.get(g, []))} export hits")

# How big is the stream? Any bunches after 275?
print(f"\nstream len={len(stream)} last src ch={stream[-1]['chIndex']} bits={stream[-1]['bits']}")
print("ch3 bunches:", sum(1 for s in stream if s["chIndex"] == 3))
print("ch4 bunches:", sum(1 for s in stream if s["chIndex"] == 4))
print("ch5 bunches:", sum(1 for s in stream if s["chIndex"] == 5))
