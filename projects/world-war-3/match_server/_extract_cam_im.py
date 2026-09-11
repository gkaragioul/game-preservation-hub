#!/usr/bin/env python3
"""Extract CAM(9374)/IM(9384) payloads from clothing bunch with correct stably=0 header."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from netguid import PackageMap  # noqa: E402
from repblock import read_packed  # noqa: E402
from _decode_rep_block import decode, layout  # noqa: E402
import derive_rep_handles as D  # noqa: E402

stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
bits: list[int] = []
for i in (212, 213):
    bits.extend(int(c) for c in stream[i]["payload"])

pm = PackageMap()
pos = pm.read_export_bunch(bits)["reader"].pos

blocks = []
p = pos
while p + 3 <= len(bits):
    has_rep = bits[p]
    is_actor = bits[p + 1]
    p += 2
    sub = stably = cls = None
    if not is_actor:
        sub, sw = read_packed(bits, p)
        p += sw
        stably = bits[p]
        p += 1
        if stably == 0:
            cls, cw = read_packed(bits, p)
            p += cw
    nbits, nw = read_packed(bits, p)
    p += nw
    payload = bits[p : p + nbits]
    p += nbits
    blocks.append(
        {
            "hasRep": has_rep,
            "isActor": is_actor,
            "sub": sub,
            "stably": stably,
            "cls": cls,
            "nbits": nbits,
            "payload": payload,
        }
    )
assert p == len(bits), (p, len(bits))

sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
classes, structs = D.parse_sdk(sdk)
enums = D.parse_enums(sdk)

for b in blocks:
    print(
        f"isActor={b['isActor']} sub={b['sub']} stably={b['stably']} "
        f"cls={b['cls']} nbits={b['nbits']}"
    )
    if b["sub"] == 9374:
        by_h, types = layout("UWW3CharacterAttachmentManager", classes, structs)
        r = decode(b["payload"], by_h, types, enums=enums)
        print(f"  CAM closed={r['closed']} left={r['left']} props={len(r['seq'])}")
        for h, name, typ, w, note, p0 in r["seq"]:
            print(f"    h{h} {name} w={w} {note}")
    if b["sub"] == 9384:
        by_h, types = layout("UWW3InventoryManager", classes, structs)
        # bitfield-aware manual? try standard first
        r = decode(b["payload"], by_h, types, enums=enums)
        print(
            f"  IM standard closed={r['closed']} reason={r['reason']} "
            f"left={r['left']} props={len(r['seq'])}"
        )
        for h, name, typ, w, note, p0 in r["seq"][:20]:
            print(f"    h{h} {name} w={w} {note}")
        # bitfield override walk
        from repblock import REP_BLOCK_PREFIX_BITS, value_widths

        BITFIELDS = {"bReplicates", "bIsActive"}
        pos2 = REP_BLOCK_PREFIX_BITS
        pl = b["payload"]
        seq = []
        while pos2 < len(pl):
            h, hw = read_packed(pl, pos2)
            pos2 += hw
            if h == 0:
                print(f"  IM bitfield-aware TERMINATOR left={len(pl)-pos2}")
                break
            if h not in by_h:
                print(f"  IM unknown h{h}")
                break
            name, typ = by_h[h] if isinstance(by_h[h], tuple) else (by_h[h], types.get(by_h[h]))
            # layout returns name only in by_h
            name = by_h[h]
            typ = types[name]
            if name in BITFIELDS or typ == "bool":
                w, note = 1, "bit"
            else:
                cands = value_widths(name, typ, pl, pos2, enums=enums)
                if not cands:
                    v, vw = read_packed(pl, pos2)
                    w, note = vw, f"packed={v}"
                else:
                    w, note = cands[0]
            if pos2 + w > len(pl):
                print(f"  overflow h{h} {name}")
                break
            pos2 += w
            seq.append((h, name, w, note))
            print(f"    h{h} {name} w={w} {note}")
        print(f"  seq_len={len(seq)} pos={pos2}/{len(pl)}")
