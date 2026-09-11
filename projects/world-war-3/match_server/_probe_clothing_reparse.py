#!/usr/bin/env python3
"""Re-parse clothing content assuming UE InternalLoadObject on unknown GUID."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from actor_channel import Bits, read_content_blocks  # noqa: E402
from netguid import PackageMap, GuidReader  # noqa: E402
from _decode_rep_block import decode, layout  # noqa: E402
import derive_rep_handles as D  # noqa: E402

stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
bits: list[int] = []
for i in (212, 213):
    bits.extend(int(c) for c in stream[i]["payload"])

pm = PackageMap()
res = pm.read_export_bunch(bits)
pos = res["reader"].pos
print(f"after export pos={pos}/{len(bits)}")
print("mapped guids sample:", sorted(pm.guid_to_path)[:20], "...")

# Standard parse
r = Bits(bits, pos)
blocks = read_content_blocks(r, total_bits=len(bits))
print(f"standard blocks={len(blocks)} end_pos={r.pos} left={len(bits)-r.pos}")
for b in blocks:
    print(
        f"  isActor={b.get('isActor')} hasRep={b.get('hasRepLayout')} "
        f"sub={b.get('subNetGUID')} stably={b.get('stablyNamed')} "
        f"bits={b.get('payloadBits')} bad={b.get('bad')}"
    )

# Hypothesis: after actor block, next is subobject 9374 (CAM) stably=1 with big payload
# Manually walk from pos
pos2 = pos
has_rep = bits[pos2]
is_actor = bits[pos2 + 1]
pos2 += 2
from repblock import read_packed

nbits, nw = read_packed(bits, pos2)
pos2 += nw
print(f"\nblock0: hasRep={has_rep} isActor={is_actor} nbits={nbits} -> end {pos2+nbits}")
pos2 += nbits

# Next header
has_rep = bits[pos2]
is_actor = bits[pos2 + 1]
pos2 += 2
print(f"block1 header hasRep={has_rep} isActor={is_actor} at bit {pos2-2}")

if not is_actor:
    # Try reading as InternalLoadObject-style: PackageMap.load_object
    gr = GuidReader(bits, pos2)
    # Use a PackageMap that already knows 9374 from a fresh open
    pm2 = PackageMap()
    # Seed pawn open exports so 9374 is known
    bits_open: list[int] = []
    for i in (10, 11):
        bits_open.extend(int(c) for c in stream[i]["payload"])
    pm2.read_export_bunch(bits_open)
    print("9374 mapped?", 9374 in pm2.guid_to_path, pm2.guid_to_path.get(9374))
    print("9404 mapped?", 9404 in pm2.guid_to_path)

    # Read NetGUID only (packed) as our simple parser does
    sub, sw = read_packed(bits, pos2)
    print(f"  packed subguid={sub} width={sw}")
    # If we seed 9374 as known stably named, try forcing interpret as 9374 path:
    # After packed guid + stably bit + nbits

    # Search: at this bit position, does packed int equal 9374?
    # 9374 packed width?
    from netguid import GuidWriter

    w = GuidWriter()
    w.write_packed(9374)
    packed_9374 = [(w.get_bytes()[i >> 3] >> (i & 7)) & 1 for i in range(w.num)]
    w2 = GuidWriter()
    w2.write_packed(9404)
    packed_9404 = [(w2.get_bytes()[i >> 3] >> (i & 7)) & 1 for i in range(w2.num)]
    head = bits[pos2 : pos2 + 40]
    print("  head40:", "".join(str(x) for x in head))
    print("  9374 packed:", "".join(str(x) for x in packed_9374))
    print("  9404 packed:", "".join(str(x) for x in packed_9404))
    print("  matches 9374?", head[: len(packed_9374)] == packed_9374)
    print("  matches 9404?", head[: len(packed_9404)] == packed_9404)

# Decode 9404 payload as CharacterAttachmentManager RepLayout
sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
classes, structs = D.parse_sdk(sdk)
enums = D.parse_enums(sdk)
by_h, types = layout("UWW3CharacterAttachmentManager", classes, structs)
print("\nCAM handles:")
for h, name in sorted(by_h.items()):
    print(f"  h{h}: {name}")

pl = None
for b in blocks:
    if b.get("subNetGUID") == 9404:
        pl = b.get("payload")
if pl:
    rdec = decode(pl, by_h, types, enums=enums)
    print(
        f"\nCAM decode of '9404' payload: closed={rdec['closed']} "
        f"reason={rdec['reason']} left={rdec['left']} props={len(rdec['seq'])}"
    )
    for h, name, typ, w, note, p in rdec["seq"][:20]:
        print(f"  @{p} h{h} {name} {typ} w={w} {note}")
    if rdec["reason"] == "terminator" and rdec["left"] > 0:
        rem = pl[-rdec["left"] :]
        print(f"  custom-delta tail bits={len(rem)} head64={''.join(str(x) for x in rem[:64])}")
