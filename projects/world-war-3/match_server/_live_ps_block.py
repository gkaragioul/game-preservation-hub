#!/usr/bin/env python3
"""Decode the local PlayerState blocks we actually put on the wire this session.

The capture's PS open is patched live (SteamID rewrite, PS rebind), so "the
bootstrap replays src 20/21" is not the same claim as "the client received the
capture's property set".  This reads the S->C packets straight out of a session
jsonl and decodes every ch7 actor property block, so our wire data can be diffed
against `_decode_all_blocks.py --ch 7`.

Usage:
    python match_server/_live_ps_block.py live_log/session_20260809_174717.jsonl
    python match_server/_live_ps_block.py <jsonl> --ch 7 --dir S->C
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import control_channel as cc  # noqa: E402
import derive_rep_handles as D  # noqa: E402
from _decode_rep_block import decode, layout  # noqa: E402
from actor_channel import Bits, read_content_blocks, read_new_actor  # noqa: E402
from netguid import PackageMap  # noqa: E402
from ps_rebind import bunch_payload_bits  # noqa: E402
from repblock import read_u  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--ch", type=int, default=7)
    ap.add_argument("--leaf", default="AWW3DominationPlayerState")
    ap.add_argument("--max", type=int, default=25)
    args = ap.parse_args()

    sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)
    by_h, types = layout(args.leaf, classes, structs)

    shown = 0
    for line in Path(args.jsonl).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("dir") != "S->C":
            continue
        try:
            pkt = cc.read_packet(bytes.fromhex(rec["hex"]))
        except Exception:
            continue
        for b in pkt.get("bunches", []):
            if b["chIndex"] != args.ch:
                continue
            bits = bunch_payload_bits(b)
            r = Bits(bits)
            pm = PackageMap()
            if b.get("bHasPackageMapExports"):
                try:
                    pm.read_export_bunch(bits)
                except Exception:
                    pass
            if b.get("bOpen"):
                try:
                    read_new_actor(r, pm)
                except Exception:
                    pass
            try:
                blocks = read_content_blocks(r)
            except Exception as exc:
                print(f"t={rec['t']:.3f} ch{args.ch} bits={len(bits)} "
                      f"open={b.get('bOpen')} -- content parse failed: {exc}")
                continue
            for cb in blocks:
                if not cb.get("isActor"):
                    continue
                res = decode(cb["payload"], by_h, types, enums=enums)
                print(f"\nt={rec['t']:.3f} ch{args.ch} bunchBits={len(bits)} "
                      f"open={b.get('bOpen', 0)} rel={b.get('bReliable', 0)} "
                      f"blockBits={len(cb['payload'])} closed={res['closed']} "
                      f"reason={res['reason']}")
                for h, name, typ, w, note, p0 in res["seq"]:
                    val = note if (w > 32 or note.startswith(("obj", "str", "uid", "name")))\
                        else read_u(cb["payload"], p0, w)
                    print(f"   h{h:<3} {name:<44} w={w:<5} {val}")
                shown += 1
                if shown >= args.max:
                    return 0
    if not shown:
        print(f"no ch{args.ch} actor property blocks in {args.jsonl}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
