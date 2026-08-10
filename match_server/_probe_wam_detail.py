#!/usr/bin/env python3
"""Parse all ch85-88 groups: exports + content blocks (WAM hunt)."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from actor_channel import Bits, read_content_blocks, read_new_actor  # noqa: E402
from netguid import GuidReader, PackageMap  # noqa: E402

stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))


def groups(chs):
    pending: dict[int, list[int]] = defaultdict(list)
    for i, sp in enumerate(stream):
        ch = sp["chIndex"]
        if ch not in chs:
            continue
        if not sp.get("bPartial"):
            yield ch, [i]
            continue
        if sp.get("bPartialInitial"):
            pending[ch] = [i]
        elif pending.get(ch):
            pending[ch].append(i)
        if sp.get("bPartialFinal") and pending.get(ch):
            yield ch, pending.pop(ch)


for ch, idxs in groups({85, 86, 87, 88}):
    bits: list[int] = []
    for i in idxs:
        bits.extend(int(c) for c in stream[i]["payload"])
    pos = 0
    pm = PackageMap()
    try:
        if stream[idxs[0]].get("bHasPackageMapExports"):
            res = pm.read_export_bunch(bits)
            pos = res["reader"].pos
            exports = [(e.get("netguid"), e.get("path")) for e in res.get("exports", [])]
        else:
            exports = []
        if stream[idxs[0]].get("bOpen"):
            gr = GuidReader(bits, pos)
            na = read_new_actor(gr, pm)
            pos = gr.pos
            print(f"=== ch{ch} src={idxs} OPEN actor={na.get('netGUID')} "
                  f"arch={na.get('archetype')} ===")
        else:
            print(f"=== ch{ch} src={idxs} bits={len(bits)} ===")
        for g, p in exports[:25]:
            print(f"  export {g}: {p}")
        r = Bits(bits, pos)
        bl = read_content_blocks(r, total_bits=len(bits))
        rem = len(bits) - r.pos
        for b in bl:
            print(
                f"  block isActor={b.get('isActor')} hasRep={b.get('hasRepLayout')} "
                f"sub={b.get('subNetGUID')} stably={b.get('stablyNamed')} "
                f"cls={b.get('classNetGUID')} bits={b.get('payloadBits')} "
                f"bad={b.get('bad')}"
            )
        print(f"  leftover={rem}")
    except Exception as ex:
        print(f"=== ch{ch} src={idxs} FAIL {type(ex).__name__}: {ex}")
