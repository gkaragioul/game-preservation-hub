#!/usr/bin/env python3
"""Probe capture: isActor RepLayout vs subobject order inside OPEN bunches."""
from __future__ import annotations

import json
from pathlib import Path

from actor_channel import Bits, read_content_blocks, read_new_actor
from netguid import PackageMap, GuidReader

HERE = Path(__file__).resolve().parent
stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))


def collect_open_group(i: int):
    sp = stream[i]
    parts = [sp]
    j = i + 1
    while j < len(stream):
        nxt = stream[j]
        if nxt.get("chIndex") != sp["chIndex"]:
            break
        if nxt.get("bOpen"):
            break
        # Continue while still completing a partial open
        if parts[-1].get("bPartial") and not parts[-1].get("bPartialFinal"):
            parts.append(nxt)
            j += 1
            if nxt.get("bPartialFinal"):
                break
            continue
        break
    return parts, j


def skip_exports(bits, has_exports: bool):
    r = Bits(bits)
    pm = PackageMap()
    if has_exports:
        gr = GuidReader(r, pm)
        gr.read_export_bunch()
    return r.pos, pm


def describe_block(b):
    if b.get("bad"):
        return "BAD"
    if b.get("isActor") and b.get("hasRepLayout"):
        return "ACTOR_REP(%d)" % b.get("payloadBits", 0)
    if b.get("isActor"):
        return "ACTOR_RPC(%d)" % b.get("payloadBits", 0)
    return "SUB(%s,%d,rep=%s)" % (
        b.get("subNetGUID"), b.get("payloadBits", 0), b.get("hasRepLayout"))


print("=== Opens with isActor RepLayout ===")
i = 0
shown = 0
pawn_shown = False
while i < len(stream):
    if not stream[i].get("bOpen"):
        i += 1
        continue
    parts, nxt = collect_open_group(i)
    bits = []
    for p in parts:
        bits.extend(int(c) for c in p["payload"])
    has_exp = bool(parts[0].get("bHasPackageMapExports"))
    try:
        pos, pm = skip_exports(bits, has_exp)
        r = Bits(bits, pos)
        info = read_new_actor(r, pm)
        blocks = read_content_blocks(Bits(bits, r.pos))
    except Exception as e:
        i = nxt if nxt > i else i + 1
        continue

    actor_rep = [b for b in blocks if b.get("isActor") and b.get("hasRepLayout") and not b.get("bad")]
    subs = [b for b in blocks if not b.get("isActor") and not b.get("bad")]
    ch = stream[i]["chIndex"]
    arch = (info.get("archetypePath") or "")[-60:]
    is_pawn = ch == 3 or "Pawn" in (info.get("archetypePath") or "")

    if actor_rep or is_pawn:
        order = [describe_block(b) for b in blocks]
        first_actor = next((k for k, b in enumerate(blocks)
                            if b.get("isActor") and b.get("hasRepLayout") and not b.get("bad")), None)
        first_sub = next((k for k, b in enumerate(blocks) if not b.get("isActor") and not b.get("bad")), None)
        rel = "?"
        if first_actor is not None and first_sub is not None:
            rel = "ACTOR_BEFORE_SUB" if first_actor < first_sub else "SUB_BEFORE_ACTOR"
        elif first_actor is not None:
            rel = "ACTOR_ONLY"
        elif first_sub is not None:
            rel = "SUB_ONLY"
        print("src=%d ch=%d parts=%d nbits=%d arch=...%s" % (i, ch, len(parts), len(bits), arch))
        print("  relation=%s  order=%s" % (rel, " -> ".join(order[:24])))
        print("  n_actor_rep=%d n_sub=%d" % (len(actor_rep), len(subs)))
        shown += 1
        if is_pawn:
            pawn_shown = True
        if shown >= 25 and pawn_shown:
            break
    i = nxt if nxt > i else i + 1

print("\ndone shown=%d" % shown)
