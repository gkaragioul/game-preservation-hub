#!/usr/bin/env python3
"""Dump the exact archetype/level/subobject export paths+checksums referenced by the
pawn open bunch (src=10), so we can sanity-check them against the client's actual
loaded content (asset renamed/moved/BP-recompiled would silently break GUID resolution
even though wire bytes are bit-identical)."""
import json
import sys

sys.path.insert(0, "match_server")
from netguid import PackageMap

stream = json.load(open("match_server/real_replay_stream.json"))
bits = [int(c) for c in stream[10]["payload"]]

pm = PackageMap()
res = pm.read_export_bunch(bits)
print(f"num exports: {res['num']}  repLayoutExport: {res['repLayoutExport']}")
for e in res["exports"]:
    cs = f"0x{e['checksum']:08x}" if e.get("checksum") is not None else "None"
    print(f"  guid={e['netguid']:6d}  outer={e['outer']}  checksum={cs}  path={e['path']!r}")
