#!/usr/bin/env python3
r"""Extract every PlayerState `isActor` RepLayout block from the captured stream.

The ch7 open is not the only sample: the capture opens a PlayerState channel per
player (ch7..ch11+), each a partial-initial/partial-final pair carrying the same
class's property block with different data. A RepLayout numbering model has to
exact-consume *all* of them, which is a far stronger filter than the single
483-bit ch7 block the original decode attempt worked on.

  python match_server/_ps_blocks.py
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from actor_channel import Bits, read_content_blocks, read_new_actor  # noqa: E402
from netguid import GuidReader, PackageMap  # noqa: E402

STREAM = os.path.join(HERE, "real_replay_stream.json")


def load_stream() -> list[dict]:
    return json.load(open(STREAM))


def group_opens(stream: list[dict]) -> list[tuple[int, list[int]]]:
    """-> [(first_src_index, [src indices of the reassembled open])] for every bOpen."""
    groups = []
    for i, sp in enumerate(stream):
        if not sp.get("bOpen"):
            continue
        idxs = [i]
        if sp.get("bPartial") and not sp.get("bPartialFinal"):
            ch = sp["chIndex"]
            j = i + 1
            while j < len(stream):
                nxt = stream[j]
                if nxt["chIndex"] == ch:
                    idxs.append(j)
                    if nxt.get("bPartialFinal"):
                        break
                j += 1
        groups.append((i, idxs))
    return groups


def parse_open(stream: list[dict], idxs: list[int]) -> dict:
    specs = [stream[i] for i in idxs]
    bits: list[int] = []
    for sp in specs:
        bits.extend(int(c) for c in sp["payload"])
    pm = PackageMap()
    pos = 0
    if specs[0].get("bHasPackageMapExports"):
        pos = pm.read_export_bunch(bits)["reader"].pos
    gr = GuidReader(bits, pos)
    header = read_new_actor(gr, pm)
    blocks = read_content_blocks(Bits(bits, gr.pos), total_bits=len(bits))
    return {"header": header, "blocks": blocks, "pm": pm, "srcs": idxs,
            "chIndex": specs[0]["chIndex"]}


def playerstate_samples(stream: list[dict] | None = None) -> list[dict]:
    """-> [{chIndex, srcs, netguid, archetype, payload}] for every PlayerState open
    that carries an isActor RepLayout block."""
    stream = stream if stream is not None else load_stream()
    out = []
    for _first, idxs in group_opens(stream):
        try:
            g = parse_open(stream, idxs)
        except Exception:
            continue
        arch = g["header"].get("archetypePath") or ""
        if "PlayerState" not in arch:
            continue
        actor = next((b for b in g["blocks"]
                      if b.get("isActor") and b.get("hasRepLayout") and not b.get("bad")), None)
        if actor is None:
            continue
        out.append({
            "chIndex": g["chIndex"], "srcs": idxs,
            "netguid": g["header"].get("netguid"), "archetype": arch,
            "payload": actor["payload"],
            "nsub": sum(1 for b in g["blocks"] if not b.get("isActor")),
        })
    return out


def first_handles(payload: list[int], n: int = 4) -> list[int]:
    r = Bits(payload)
    out = []
    try:
        for _ in range(n):
            out.append(r.packed())
            break
    except EOFError:
        pass
    return out


def main() -> int:
    stream = load_stream()
    arch_count: dict[str, int] = {}
    for _first, idxs in group_opens(stream):
        try:
            g = parse_open(stream, idxs)
        except Exception:
            continue
        a = g["header"].get("archetypePath") or "?"
        arch_count[a] = arch_count.get(a, 0) + 1
    print("=== opens by archetype ===")
    for a, c in sorted(arch_count.items(), key=lambda kv: -kv[1]):
        print(f"  {c:>4}  {a}")

    samples = playerstate_samples(stream)
    print(f"\n=== PlayerState isActor blocks: {len(samples)} ===")
    for s in samples:
        p = s["payload"]
        r = Bits(p)
        try:
            h0 = r.packed()
        except EOFError:
            h0 = None
        print(f"  ch{s['chIndex']:<3} srcs={s['srcs']} guid={s['netguid']:<6} "
              f"bits={len(p):<5} firstHandle={h0} sub={s['nsub']}  {s['archetype']}")
        print("      " + "".join(str(b) for b in p[:96]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
