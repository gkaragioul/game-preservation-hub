#!/usr/bin/env python3
r"""Read-only: decode the PlayerController-channel (ch2) bunches the ownership bootstrap
skips, naming any RPC fields via class_net_cache_ww3.json.

The sync checklist blames PlayerState / InventoryManager / CharacterAttachments /
WeaponsAttachments, and the pawn channel is replayed in full (only six ch3 bunches exist
in the whole capture). ch2 is where the gap is: the bootstrap replays 12 of 92 bunches.
This lists what is in the other 80, so the ones that matter can be added deliberately
instead of by widening a window.

  python match_server/_ch2_gap_dump.py              # skipped ch2 bunches, first 40
  python match_server/_ch2_gap_dump.py --all        # every ch2 bunch, sent or not
  python match_server/_ch2_gap_dump.py --ch 7       # same for the local PlayerState
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from actor_channel import Bits, read_content_blocks  # noqa: E402
from possess_rpc import (handle_value_max, parse_object_param,  # noqa: E402
                         read_int_wrapped)

STREAM = os.path.join(HERE, "real_replay_stream.json")
CACHE = os.path.join(HERE, "class_net_cache_ww3.json")

OWNED_RANGES = [(0, 1), (20, 21), (2, 17), (9, 9), (181, 181), (192, 192),
                (212, 213), (119, 121), (215, 215), (275, 275)]


def owned_set() -> set[int]:
    s: set[int] = set()
    for a, b in OWNED_RANGES:
        s.update(range(a, b + 1))
    return s


def handle_names() -> dict[int, str]:
    try:
        doc = json.load(open(CACHE))
    except (OSError, ValueError):
        return {}
    return {int(v): k for k, v in ((doc.get("rpc_handles") or {}).get("PlayerController") or {}).items()}


def decode_rpc_fields(payload: list[int], vmax: int) -> list[tuple[int, int]] | None:
    """[(handle, payload_bits)] if the field chain consumes the block exactly, else None."""
    r = Bits(payload)
    out: list[tuple[int, int]] = []
    try:
        while r.left() > 0:
            h = read_int_wrapped(r, vmax)
            n = r.packed()
            if n > r.left():
                return None
            params = [r.bit() for _ in range(n)]
            out.append((h, params))
    except EOFError:
        return None
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ch", type=int, default=2)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args()

    stream = json.load(open(STREAM))
    owned = owned_set()
    names = handle_names()
    vmax = handle_value_max()
    print(f"handle_value_max={vmax}  named_handles={len(names)}")

    shown = 0
    pending: list[tuple[int, dict]] = []
    for i, sp in enumerate(stream):
        if sp["chIndex"] != args.ch:
            continue
        if sp.get("bPartial"):
            if sp.get("bPartialInitial"):
                pending = [(i, sp)]
            else:
                pending.append((i, sp))
            if not sp.get("bPartialFinal"):
                continue
            group = pending
            pending = []
        else:
            group = [(i, sp)]

        idxs = [g[0] for g in group]
        sent = all(x in owned for x in idxs)
        if sent and not args.all:
            continue
        if shown >= args.limit:
            break
        shown += 1

        bits: list[int] = []
        for _, g in group:
            bits.extend(int(c) for c in g["payload"])
        tag = "SENT" if sent else "skip"
        print(f"\n[{tag}] src={idxs} ch{args.ch} bits={len(bits)} "
              f"exports={group[0][1].get('bHasPackageMapExports')} "
              f"open={group[0][1].get('bOpen')}")
        pos = 0
        if group[0][1].get("bHasPackageMapExports"):
            from netguid import PackageMap
            pm = PackageMap()
            try:
                res = pm.read_export_bunch(bits)
                pos = res["reader"].pos
                for gid, path in sorted(pm.guid_to_path.items()):
                    print(f"        export guid={gid} path={path}")
            except Exception as exc:
                print(f"        (export block undecodable: {exc})")
                continue
        try:
            blocks = read_content_blocks(Bits(bits, pos), total_bits=len(bits))
        except Exception as exc:
            print(f"        (content blocks undecodable: {exc})")
            continue
        for bi, b in enumerate(blocks):
            kind = "actor" if b.get("isActor") else f"sub{b.get('subNetGUID')}"
            if b.get("bad"):
                print(f"        block[{bi}] {kind} BAD")
                continue
            n = b.get("payloadBits")
            if b.get("hasRepLayout"):
                first = None
                try:
                    rr = Bits(b["payload"])
                    first = rr.packed()
                except EOFError:
                    pass
                print(f"        block[{bi}] {kind} REP bits={n} first_handle={first}")
                continue
            fields = decode_rpc_fields(b.get("payload") or [], vmax)
            if fields is None:
                print(f"        block[{bi}] {kind} RPC bits={n} (chain did not consume exactly)")
                continue
            desc = []
            for h, params in fields:
                nm = names.get(h, f"handle{h}")
                arg = parse_object_param(params) if params else None
                desc.append(f"{nm}({h})[{len(params)}b"
                            + (f" obj={arg}" if arg else "") + "]")
            print(f"        block[{bi}] {kind} RPC bits={n}: " + ", ".join(desc))


if __name__ == "__main__":
    main()
