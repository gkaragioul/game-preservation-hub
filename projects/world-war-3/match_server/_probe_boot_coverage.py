#!/usr/bin/env python3
"""Find 9404 and list bootstrap ch3/4/5 coverage."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from netguid import PackageMap  # noqa: E402

stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
found = 0
for i, sp in enumerate(stream):
    if not sp.get("bHasPackageMapExports"):
        continue
    bits = [int(c) for c in sp["payload"]]
    try:
        res = PackageMap().read_export_bunch(bits)
    except Exception:
        continue
    for e in res["exports"]:
        if e.get("netguid") == 9404 or e.get("outer") == 9404:
            print("HIT", i, sp["chIndex"], e)
            found += 1
print("export hits for 9404:", found)

boot = json.loads((HERE / "ownership_bootstrap.json").read_text(encoding="utf-8"))
print("\nbootstrap ch3/4/5 / key srcs:")
for b in boot:
    src = b.get("_src_idx")
    ch = b.get("chIndex")
    if ch in (3, 4, 5) or src in (10, 11, 14, 16, 119, 120, 121, 181, 192, 212, 213):
        print(
            f"  src={src} ch={ch} bits={b.get('bits')} "
            f"open={int(bool(b.get('bOpen')))} exp={int(bool(b.get('bHasPackageMapExports')))}"
        )

# Is 119-121 weapon related?
print("\nsrc 14-21 and 119-125 summary:")
for i in list(range(14, 22)) + list(range(119, 126)):
    sp = stream[i]
    print(
        f"  src={i} ch={sp['chIndex']} bits={sp['bits']} "
        f"open={int(bool(sp.get('bOpen')))} exp={int(bool(sp.get('bHasPackageMapExports')))} "
        f"partial={int(bool(sp.get('bPartial')))}"
    )
