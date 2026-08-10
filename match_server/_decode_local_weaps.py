#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, "match_server")
from netguid import PackageMap
from actor_channel import read_new_actor
from netguid import GuidReader

stream = json.loads(Path("match_server/real_replay_stream.json").read_text(encoding="utf-8"))
for pair in ((257, 258), (259, 260), (261, 262)):
    bits = []
    for i in pair:
        bits.extend(int(c) for c in stream[i]["payload"])
    pm = PackageMap()
    res = pm.read_export_bunch(bits)
    print(f"\n=== src {pair} ch={stream[pair[0]]['chIndex']} ===")
    for e in res["exports"]:
        print(f"  {e['netguid']} outer={e['outer']} path={e.get('path')}")
    gr = GuidReader(bits, res["reader"].pos)
    info = read_new_actor(gr, pm)
    print(f"  actor={info.get('netguid')} arch={info.get('archetypePath')}")
