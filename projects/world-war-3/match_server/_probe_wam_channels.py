#!/usr/bin/env python3
"""Probe ch85-88 + later weapon channels for WeaponAttachmentManager content."""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
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


print("=== bunches on ch85-88 ===")
for i, sp in enumerate(stream):
    if sp["chIndex"] in (85, 86, 87, 88):
        print(
            f"  src={i} ch={sp['chIndex']} open={sp.get('bOpen')} "
            f"exp={sp.get('bHasPackageMapExports')} bits={sp['bits']} "
            f"partial={sp.get('bPartial')} i={sp.get('bPartialInitial')} "
            f"f={sp.get('bPartialFinal')}"
        )

print("\n=== content blocks on ch85-88 ===")
for ch, idxs in groups({85, 86, 87, 88}):
    bits: list[int] = []
    for i in idxs:
        bits.extend(int(c) for c in stream[i]["payload"])
    pos = 0
    pm = PackageMap()
    try:
        if stream[idxs[0]].get("bHasPackageMapExports"):
            pos = pm.read_export_bunch(bits)["reader"].pos
            exports = []
            for g, e in sorted(pm.export_map.items()):
                exports.append(f"{g}:{getattr(e, 'path', e)}")
            print(f"  ch{ch} src={idxs[0]} exports({len(pm.export_map)}): {exports[:12]}")
        if stream[idxs[0]].get("bOpen"):
            gr = GuidReader(bits, pos)
            try:
                na = read_new_actor(gr, pm)
                pos = gr.pos
                print(f"  ch{ch} src={idxs[0]} NewActor arch={na.get('archetype')} "
                      f"netguid={na.get('netGUID')} leftover_open={len(bits)-pos}")
            except Exception as ex:
                print(f"  ch{ch} src={idxs[0]} NewActor FAIL {ex}")
        r = Bits(bits, pos)
        bl = read_content_blocks(r, total_bits=len(bits))
        rem = len(bits) - r.pos
        for b in bl:
            print(
                f"  ch{ch} src={idxs[0]} isActor={b.get('isActor')} hasRep={b.get('hasRepLayout')} "
                f"sub={b.get('subNetGUID')} stably={b.get('stablyNamed')} "
                f"cls={b.get('classNetGUID')} bits={b.get('payloadBits')} bad={b.get('bad')}"
            )
        if rem > 8:
            print(f"  ch{ch} src={idxs[0]} LEFTOVER={rem}")
    except Exception as ex:
        print(f"  ch{ch} src={idxs[0]} PARSE FAIL {ex}")

# Search entire stream for stably-named subs with BIG payloads that look like ReplicatedBatch (~700 bits)
print("\n=== BIG stably-named RepLayout blocks anywhere (possible CAM/WAM) ===")
for ch, idxs in groups(set(range(0, 200))):
    bits = []
    for i in idxs:
        bits.extend(int(c) for c in stream[i]["payload"])
    pos = 0
    pm = PackageMap()
    try:
        if stream[idxs[0]].get("bHasPackageMapExports"):
            pos = pm.read_export_bunch(bits)["reader"].pos
        if stream[idxs[0]].get("bOpen"):
            gr = GuidReader(bits, pos)
            try:
                read_new_actor(gr, pm)
                pos = gr.pos
            except Exception:
                pass
        r = Bits(bits, pos)
        bl = read_content_blocks(r, total_bits=len(bits))
    except Exception:
        continue
    for b in bl:
        n = b.get("payloadBits") or 0
        if n >= 200 and b.get("stablyNamed") == 1 and b.get("hasRepLayout"):
            print(
                f"  ch{ch} src={idxs[0]} sub={b.get('subNetGUID')} bits={n} "
                f"isActor={b.get('isActor')}"
            )
