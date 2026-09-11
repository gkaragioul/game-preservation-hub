#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, "match_server")
from netguid import PackageMap, GuidReader
from actor_channel import read_new_actor

stream = json.loads(Path("match_server/real_replay_stream.json").read_text(encoding="utf-8"))

# Find any open that creates 9402
for i, sp in enumerate(stream):
    if not sp.get("bOpen"):
        continue
    bits = [int(c) for c in sp["payload"]]
    # may be partial - only look at init
    if sp.get("bPartial") and not sp.get("bPartialInitial"):
        continue
    # gather partial group
    idxs = [i]
    if sp.get("bPartialInitial"):
        j = i + 1
        while j < len(stream) and stream[j]["chIndex"] == sp["chIndex"]:
            idxs.append(j)
            if stream[j].get("bPartialFinal"):
                break
            j += 1
        bits = []
        for k in idxs:
            bits.extend(int(c) for c in stream[k]["payload"])
    pm = PackageMap()
    pos = 0
    try:
        if sp.get("bHasPackageMapExports"):
            res = pm.read_export_bunch(bits)
            pos = res["reader"].pos
            for e in res["exports"]:
                if e.get("netguid") == 9402 or e.get("outer") == 9402:
                    print(f"export src={i} ch={sp['chIndex']} {e}")
        gr = GuidReader(bits, pos)
        info = read_new_actor(gr, pm)
        if info.get("netguid") == 9402:
            print(f"actor open src={idxs[0]}-{idxs[-1]} ch={sp['chIndex']} arch={info.get('archetypePath')}")
    except Exception:
        continue

# Also list archetype for ch86 - maybe class exported earlier
bits = []
for i in (257, 258):
    bits.extend(int(c) for c in stream[i]["payload"])
pm = PackageMap()
res = pm.read_export_bunch(bits)
print("ch86 exports detailed:")
for e in res["exports"]:
    print(" ", e)
