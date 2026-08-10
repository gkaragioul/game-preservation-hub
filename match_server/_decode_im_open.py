#!/usr/bin/env python3
"""Decode InventoryManager open payload with bitfield-aware widths."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import derive_rep_handles as D  # noqa: E402
from actor_channel import Bits, read_content_blocks, read_new_actor  # noqa: E402
from netguid import PackageMap  # noqa: E402
from repblock import REP_BLOCK_PREFIX_BITS, read_packed, value_widths  # noqa: E402

sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
classes, structs = D.parse_sdk(sdk)
enums = D.parse_enums(sdk)
typed = D.build_typed("UWW3InventoryManager", classes, structs)
# typed: list of (handle, cmd, name, type)
by_h = {h: (n, t) for h, _c, n, t in typed}
print("handles:", len(by_h))

stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
bits: list[int] = []
for i in (10, 11):
    bits.extend(int(c) for c in stream[i]["payload"])
pm = PackageMap()
r = pm.read_export_bunch(bits)["reader"]
read_new_actor(r, pm)
pl = None
for b in read_content_blocks(Bits(bits, r.pos)):
    if b.get("subNetGUID") == 9384:
        pl = b["payload"]
assert pl and len(pl) == 98
print("payload:", "".join(str(x) for x in pl))

# Bitfield props on UActorComponent
BITFIELDS = {"bReplicates", "bIsActive"}

pos = REP_BLOCK_PREFIX_BITS
print(f"checksum={pl[0]}")
seq = []
while pos < len(pl):
    h, hw = read_packed(pl, pos)
    if h is None:
        print(f"eof handle at {pos}")
        break
    pos += hw
    if h == 0:
        print(f"TERMINATOR at {pos}, left={len(pl)-pos}")
        break
    if h not in by_h:
        print(f"unknown h{h} at {pos-hw}")
        break
    name, typ = by_h[h]
    if name in BITFIELDS or typ == "bool":
        cands = [(1, "bitfield/bool")]
    else:
        cands = value_widths(name, typ, pl, pos, enums=enums) or []
    if not cands:
        # object: try packed netguid
        v, vw = read_packed(pl, pos)
        if v is not None:
            cands = [(vw, f"packed_obj={v}")]
        else:
            print(f"no width for h{h} {name} {typ}")
            break
    w, note = cands[0]
    if pos + w > len(pl):
        print(f"overflow h{h} {name} need {w} have {len(pl)-pos}")
        break
    val = pl[pos : pos + w]
    pos += w
    seq.append((h, name, typ, w, note, val))
    print(f"  h{h:<3} {name:<45} w={w:<3} {note} bits={''.join(str(x) for x in val)}")

print(f"done pos={pos}/{len(pl)} left={len(pl)-pos} nprops={len(seq)}")

# Also: decode weapon open subobjects - does IM get weapon refs via outer?
print("\n=== weapon ch4 open content ===")
bits4: list[int] = []
for i in (14, 15):
    bits4.extend(int(c) for c in stream[i]["payload"])
pm4 = PackageMap()
res4 = pm4.read_export_bunch(bits4)
print("exports:")
for e in res4["exports"][:20]:
    print(f"  {e['netguid']} outer={e['outer']} path={e.get('path')}")
r4 = res4["reader"]
info4 = read_new_actor(r4, pm4)
print("actor", info4.get("netguid"), info4.get("archetypePath"), "loc", info4.get("location"))
blocks4 = read_content_blocks(Bits(bits4, r4.pos))
for b in blocks4:
    print(
        f"  isActor={b.get('isActor')} hasRep={b.get('hasRepLayout')} "
        f"sub={b.get('subNetGUID')} bits={b.get('payloadBits')} stably={b.get('stablyNamed')}"
    )

# Search ALL ch3 non-open bunches for any subobject with hasRep after src 213
print("\n=== ch3 subobject content after clothing (src>213, first 30) ===")
from collections import defaultdict

pending: dict[int, list] = defaultdict(list)
n = 0
for i, sp in enumerate(stream):
    if sp["chIndex"] != 3:
        continue
    if not sp.get("bPartial"):
        idxs = [i]
    else:
        if sp.get("bPartialInitial"):
            pending[3] = [i]
            continue
        elif pending.get(3):
            pending[3].append(i)
        else:
            continue
        if not sp.get("bPartialFinal"):
            continue
        idxs = pending.pop(3)
    if idxs[0] <= 213:
        continue
    if stream[idxs[0]].get("bOpen"):
        continue
    bits3: list[int] = []
    for j in idxs:
        bits3.extend(int(c) for c in stream[j]["payload"])
    pos = 0
    pm3 = PackageMap()
    try:
        if stream[idxs[0]].get("bHasPackageMapExports"):
            pos = pm3.read_export_bunch(bits3)["reader"].pos
        bl = read_content_blocks(Bits(bits3, pos), total_bits=len(bits3))
    except Exception:
        continue
    for b in bl:
        if not b.get("isActor") and b.get("payloadBits"):
            print(
                f"  src={idxs[0]} sub={b.get('subNetGUID')} hasRep={b.get('hasRepLayout')} "
                f"bits={b.get('payloadBits')} stably={b.get('stablyNamed')} bad={b.get('bad')}"
            )
            n += 1
            if n >= 30:
                break
    if n >= 30:
        break
print(f"listed {n}")
