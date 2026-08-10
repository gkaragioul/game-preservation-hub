#!/usr/bin/env python3
r"""Read-only: decode every bunch the ownership bootstrap sends on the pawn/weapon
channels and print its content blocks and RepLayout handles.

The sync checklist blames the pawn cluster (PlayerState / InventoryManager /
CharacterAttachments / WeaponsAttachments), so the first question is what the pawn
channel actually carries. ch3 has only six bunches in the whole capture and the
bootstrap replays all six, so whatever is missing is missing from the capture slice
itself, not from our selection.

  python match_server/_pawn_rep_dump.py            # ch3 (pawn)
  python match_server/_pawn_rep_dump.py --ch 4 5 7 2
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from actor_channel import Bits, read_content_blocks, read_new_actor  # noqa: E402
from netguid import GuidReader, PackageMap  # noqa: E402

STREAM = os.path.join(HERE, "real_replay_stream.json")


def payload_bits(spec: dict) -> list[int]:
    return [int(c) for c in spec["payload"]]


def read_handles(payload: list[int], limit: int = 40) -> list[tuple[int, int]]:
    """RepLayout stream -> [(handle, bits_until_next_handle_or_end)].

    Widths are unknown per property, so this only reports the first handle reliably;
    subsequent handles are guesses. Reported as (handle, remaining) for the first and
    the raw remaining-bit count so sizes can be compared across bunches.
    """
    r = Bits(payload)
    out = []
    try:
        h = r.packed()
    except EOFError:
        return out
    out.append((h, r.left()))
    return out


def dump_group(name: str, specs: list[dict]) -> None:
    bits: list[int] = []
    for sp in specs:
        bits.extend(payload_bits(sp))
    first = specs[0]
    pm = PackageMap()
    pos = 0
    exports = None
    if first.get("bHasPackageMapExports"):
        res = pm.read_export_bunch(bits)
        exports = res["num"]
        pos = res["reader"].pos
    header = None
    if first.get("bOpen"):
        gr = GuidReader(bits, pos)
        header = read_new_actor(gr, pm)
        pos = gr.pos
    print(f"\n--- {name}: total_bits={len(bits)} exports={exports}")
    if exports:
        for gid, path in sorted(pm.guid_to_path.items()):
            print(f"      export guid={gid} path={path}")
    if header:
        print(f"      newActor guid={header.get('netguid')} "
              f"archetype={header.get('archetypePath')} level={header.get('levelPath')} "
              f"loc={header.get('location')} rot={header.get('rotation')} "
              f"scale={header.get('has_scale')} incomplete={header.get('incomplete')}")
    blocks = read_content_blocks(Bits(bits, pos), total_bits=len(bits))
    for i, b in enumerate(blocks):
        meta = {k: v for k, v in b.items() if k != "payload"}
        print(f"      block[{i}] {meta}")
        if b.get("hasRepLayout") and b.get("payload"):
            print(f"                 first_handle={read_handles(b['payload'])}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ch", nargs="*", type=int, default=[3])
    args = ap.parse_args()

    stream = json.load(open(STREAM))
    for ch in args.ch:
        idxs = [i for i, x in enumerate(stream) if x["chIndex"] == ch]
        print(f"\n================ channel {ch}: {len(idxs)} bunches at {idxs}")
        # group partial chains
        group: list[dict] = []
        gidx: list[int] = []
        for i in idxs:
            sp = stream[i]
            if sp.get("bPartial"):
                if sp.get("bPartialInitial"):
                    group, gidx = [sp], [i]
                else:
                    group.append(sp)
                    gidx.append(i)
                if sp.get("bPartialFinal") and group:
                    dump_group(f"ch{ch} src={gidx}", group)
                    group, gidx = [], []
            else:
                dump_group(f"ch{ch} src=[{i}]", [sp])


if __name__ == "__main__":
    main()
