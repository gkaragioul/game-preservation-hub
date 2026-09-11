#!/usr/bin/env python3
"""Investigation: decode the pawn open bunch (src10/11) + clothing export (src212/213)."""
import json
from netguid import PackageMap, GuidReader
from actor_channel import Bits, read_new_actor, read_content_blocks

stream = json.load(open("real_replay_stream.json"))


def get(i):
    return stream[i]


def decode_open(indices, label):
    print(f"=== {label} (src {indices}) ===")
    bits = []
    for i in indices:
        bits.extend(int(c) for c in get(i)["payload"])
    pm = PackageMap()
    res = pm.read_export_bunch(bits)
    print("exports:", res["num"], "repLayoutExport:", res["repLayoutExport"])
    for e in res["exports"]:
        cs = f" checksum=0x{e['checksum']:08x}" if e["checksum"] is not None else ""
        print(" ", e["netguid"], "outer=", e["outer"], "path=", e["path"], cs)
    r = res["reader"]
    return pm, r, bits


pm, r, bits = decode_open((10, 11), "pawn open")
info = read_new_actor(r, pm)
print("actor info:", {k: v for k, v in info.items() if k != "scale_raw_bits"})
print("pos after new_actor:", r.pos, "of", len(bits))
r = Bits(bits, r.pos)
blocks = read_content_blocks(r)
print("n blocks:", len(blocks))
for b in blocks:
    print(
        " block isActor=", b.get("isActor"),
        "hasRepLayout=", b.get("hasRepLayout"),
        "bits=", b.get("payloadBits"),
        "subNetGUID=", b.get("subNetGUID"),
        "bad=", b.get("bad"),
    )

print()
pm2, r2, bits2 = decode_open((212, 213), "pawn clothing/InventoryManager export")
print("pos after export:", r2.pos, "of", len(bits2), "remaining:", len(bits2) - r2.pos)
r2 = Bits(bits2, r2.pos)
blocks2 = read_content_blocks(r2)
print("n blocks:", len(blocks2))
for b in blocks2:
    print(
        " block isActor=", b.get("isActor"),
        "hasRepLayout=", b.get("hasRepLayout"),
        "bits=", b.get("payloadBits"),
        "subNetGUID=", b.get("subNetGUID"),
        "bad=", b.get("bad"),
    )

print()
print("=== pawn RepLayout nudges (src 181, 192) ===")
for i in (181, 192):
    sp = get(i)
    bits3 = [int(c) for c in sp["payload"]]
    print(f"src={i} chIndex={sp['chIndex']} bits={sp['bits']} bReliable={sp.get('bReliable')} payload_bits_len={len(bits3)}")
    blocks3 = read_content_blocks(Bits(bits3))
    for b in blocks3:
        print(
            "  block isActor=", b.get("isActor"),
            "hasRepLayout=", b.get("hasRepLayout"),
            "bits=", b.get("payloadBits"),
            "subNetGUID=", b.get("subNetGUID"),
            "bad=", b.get("bad"),
            "payload(head20)=", (b.get("payload") or [])[:20],
        )
