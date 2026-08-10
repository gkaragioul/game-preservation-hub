#!/usr/bin/env python3
import json
from pathlib import Path

stream = json.loads(Path("match_server/real_replay_stream.json").read_text(encoding="utf-8"))
for i in range(250, 280):
    sp = stream[i]
    print(
        f"src={i} ch={sp['chIndex']} bits={sp['bits']} "
        f"open={int(bool(sp.get('bOpen')))} exp={int(bool(sp.get('bHasPackageMapExports')))} "
        f"partial={int(bool(sp.get('bPartial')))} "
        f"init={int(bool(sp.get('bPartialInitial')))} fin={int(bool(sp.get('bPartialFinal')))}"
    )

# Also find 9402/9408 - gadgets referenced by IM
from netguid import PackageMap

for want in (9402, 9408, 9410, 9412, 9414, 9418):
    for i, sp in enumerate(stream):
        if not sp.get("bHasPackageMapExports"):
            continue
        try:
            res = PackageMap().read_export_bunch([int(c) for c in sp["payload"]])
        except Exception:
            continue
        for e in res["exports"]:
            if e.get("netguid") == want:
                print(
                    f"FOUND {want} at src={i} ch={sp['chIndex']} "
                    f"path={e.get('path')} outer={e.get('outer')}"
                )
