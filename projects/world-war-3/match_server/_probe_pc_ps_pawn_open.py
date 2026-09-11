#!/usr/bin/env python3
"""Decode PC / PS / pawn open content-block order."""
import json
from pathlib import Path

from actor_channel import Bits, read_content_blocks, read_new_actor
from netguid import PackageMap

HERE = Path(__file__).resolve().parent
stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))


def decode(idxs, label):
    print("=== %s %s ===" % (label, idxs))
    bits = []
    for i in idxs:
        sp = stream[i]
        print("  src=%d ch=%d bits=%d open=%s partial=%s init=%s final=%s exp=%s" % (
            i, sp["chIndex"], sp["bits"], sp.get("bOpen"), sp.get("bPartial"),
            sp.get("bPartialInitial"), sp.get("bPartialFinal"),
            sp.get("bHasPackageMapExports")))
        bits.extend(int(c) for c in sp["payload"])
    pm = PackageMap()
    has_exp = any(stream[i].get("bHasPackageMapExports") for i in idxs)
    if has_exp:
        res = pm.read_export_bunch(bits)
        r = res["reader"]
        print("  exports=%d pos=%d" % (res["num"], r.pos))
    else:
        r = Bits(bits)
    info = read_new_actor(r, pm)
    arch = str(info.get("archetypePath") or "")[-50:]
    print("  [%s] netguid=%s arch=%s incomplete=%s pos=%d/%d" % (
        label, info.get("netguid"), arch, info.get("incomplete"), r.pos, len(bits)))
    blocks = read_content_blocks(Bits(bits, r.pos))
    for k, b in enumerate(blocks):
        kind = "ACTOR" if b.get("isActor") else "SUB"
        print("    [%d] %s rep=%s bits=%s sub=%s bad=%s" % (
            k, kind, b.get("hasRepLayout"), b.get("payloadBits"),
            b.get("subNetGUID"), b.get("bad")))
    if blocks:
        print("  FIRST isActor=%s hasRep=%s" % (
            blocks[0].get("isActor"), blocks[0].get("hasRepLayout")))


decode([0, 1], "PC")
decode([20, 21], "PS")
decode([10, 11], "PAWN")
