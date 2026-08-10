#!/usr/bin/env python3
"""Decode the RPC handles carried by chosen `real_replay_stream.json` indices.

The live server replays a curated subset of the captured S->C stream.  To compare
"what the working server had delivered by src N" against "what we actually sent",
both sides need to be expressed in RPC handles, not stream indices.

Usage:
    python match_server/_stream_rpc_map.py --range 0 1065        # capture prefix
    python match_server/_stream_rpc_map.py --list 2,5,8,119-133  # live subset
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "match_analysis"))

from possess_rpc import parse_actor_rpc_fields  # noqa: E402

PS_VALUE_MAX = 82


def names_for(leaf: str) -> dict[int, str]:
    try:
        import os

        import derive_net_handles as d
    except Exception:
        return {}
    sdk = Path(os.environ.get("WW3_DUMPER7_DIR", str(d.DEFAULT_DUMP)))
    if sdk.name != "SDK":
        sdk = sdk / "CppSDK" / "SDK"
    if not sdk.is_dir():
        return {}
    classes = d.parse_classes(sdk)
    funcs = d.parse_net_functions(sdk)
    h, _ = d.build_cache(d.cpp_chain(leaf, classes), classes, funcs, True)
    return {v: k for k, v in h.items()}


def parse_list(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--range", nargs=2, type=int, metavar=("LO", "HI"))
    ap.add_argument("--list", dest="lst")
    ap.add_argument("--ps-channels", default="7",
                    help="comma list of channel indices that carry PlayerState RPCs")
    ap.add_argument("--only-rpc", action="store_true", default=True)
    args = ap.parse_args()

    ps_channels = {int(x) for x in args.ps_channels.split(",") if x.strip()}
    pc_names = names_for("AWW3DominationPlayerController")
    ps_names = names_for("AWW3DominationPlayerState")

    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
    if args.lst:
        idxs = parse_list(args.lst)
    elif args.range:
        idxs = list(range(args.range[0], min(args.range[1] + 1, len(stream))))
    else:
        idxs = list(range(len(stream)))

    for i in idxs:
        if i < 0 or i >= len(stream):
            continue
        e = stream[i]
        ch = e["chIndex"]
        bits = [int(c) for c in e["payload"]]
        vmax = PS_VALUE_MAX if ch in ps_channels else None
        try:
            fields = parse_actor_rpc_fields(bits, value_max=vmax)
        except Exception:
            fields = []
        if not fields:
            continue
        tbl = ps_names if ch in ps_channels else pc_names
        lbl = ", ".join(f"{int(h)} {tbl.get(int(h), '?')}" for h, _ in fields)
        flags = "".join(k for k, v in (("O", e["bOpen"]), ("R", e["bReliable"]),
                                       ("P", e["bPartial"])) if v)
        print(f"src {i:>5}  ch{ch:<4} bits={e['bits']:<6} {flags:<3}  {lbl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
