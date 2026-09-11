#!/usr/bin/env python3
"""One-pass census of the working capture: every RPC handle, both directions.

Writes `match_server/live_log/strict_census.txt`:
  * S->C handle -> count / first stream index, per channel
  * C->S handle -> count / first stream index, per channel
  * a full ordered RPC-only timeline for a chosen stream-index window

S->C bunches are aligned to `real_replay_stream.json` indices by payload match.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "match_analysis"))

import control_channel as cc  # noqa: E402
from possess_rpc import parse_actor_rpc_fields  # noqa: E402
from ps_rebind import bunch_payload_bits  # noqa: E402
from pcap_tools import parse_pcap  # noqa: E402

PCAP = HERE.parent / "captures" / "24July26" / "W3_match_full_2.pcapng"
SERVER_IP, SERVER_PORT = "213.183.62.18", 7868
PS_VALUE_MAX = 82


def names_for(leaf: str) -> dict[int, str]:
    try:
        import derive_net_handles as d
    except Exception:
        return {}
    import os
    sdk = Path(os.environ.get("WW3_DUMPER7_DIR", str(d.DEFAULT_DUMP)))
    if sdk.name != "SDK":
        sdk = sdk / "CppSDK" / "SDK"
    if not sdk.is_dir():
        return {}
    classes = d.parse_classes(sdk)
    funcs = d.parse_net_functions(sdk)
    h, _ = d.build_cache(d.cpp_chain(leaf, classes), classes, funcs, True)
    return {v: k for k, v in h.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pcap", default=str(PCAP))
    ap.add_argument("--sip", default=SERVER_IP)
    ap.add_argument("--sport", type=int, default=SERVER_PORT)
    ap.add_argument("--from", dest="lo", type=int, default=0)
    ap.add_argument("--to", dest="hi", type=int, default=2100)
    ap.add_argument("--skip", type=int, nargs="*", default=[78, 73, 17, 191])
    ap.add_argument("--out", default=str(HERE / "live_log" / "strict_census.txt"))
    args = ap.parse_args()

    pc_names = names_for("AWW3DominationPlayerController")
    ps_names = names_for("AWW3DominationPlayerState")

    def nm(ch: int, h: int) -> str:
        tbl = ps_names if ch == 7 else pc_names
        return tbl.get(h, "?")

    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
    nstream = len(stream)
    cursor = 0
    skip = set(args.skip)

    s2c: collections.Counter = collections.Counter()
    c2s: collections.Counter = collections.Counter()
    s2c_first: dict = {}
    c2s_first: dict = {}
    rows: list[str] = []

    for ts, sip, sp, dip, dp, pl in parse_pcap(args.pcap):
        to_server = (dip == args.sip and dp == args.sport)
        from_server = (sip == args.sip and sp == args.sport)
        if not (to_server or from_server):
            continue
        try:
            p = cc.read_packet(pl)
        except Exception:
            continue
        if p.get("is_handshake"):
            continue
        for b in p.get("bunches", []):
            ch = b.get("chIndex")
            try:
                bits = bunch_payload_bits(b)
            except Exception:
                continue
            if from_server:
                idx = None
                if cursor < nstream and "".join(map(str, bits)) == stream[cursor]["payload"]:
                    idx = cursor
                    cursor += 1
                if idx is None:
                    continue
                pos = idx
            else:
                pos = cursor
            try:
                fields = parse_actor_rpc_fields(
                    bits, value_max=PS_VALUE_MAX if ch == 7 else None)
            except Exception:
                fields = []
            hs = [int(h) for h, _ in fields]
            if not hs:
                continue
            tgt, first = (s2c, s2c_first) if from_server else (c2s, c2s_first)
            for h in hs:
                tgt[(ch, h)] += 1
                first.setdefault((ch, h), pos)
            shown = [h for h in hs if h not in skip]
            if shown and args.lo <= pos <= args.hi:
                d = "S->C" if from_server else "C->S"
                pre = "" if from_server else "~"
                lbl = ", ".join(f"{h} {nm(ch, h)}" for h in shown)
                rows.append(f"  {d}  {pre}{pos:>6}  ch{ch:<3} {lbl}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        f.write(f"# aligned {cursor}/{nstream} stream entries\n")
        for label, tbl, first in (("S->C", s2c, s2c_first), ("C->S", c2s, c2s_first)):
            f.write(f"\n=== {label} handle census ===\n")
            f.write(f"{'ch':>3} {'h':>5} {'count':>7}  {'first@src':>9}  name\n")
            for (ch, h), pos in sorted(first.items(), key=lambda kv: kv[1]):
                f.write(f"{ch:>3} {h:>5} {tbl[(ch, h)]:>7}  {pos:>9}  {nm(ch, h)}\n")
        f.write(f"\n=== ordered RPC timeline, src {args.lo}..{args.hi} "
                f"(skipping {sorted(skip)}) ===\n")
        f.write("\n".join(rows) + "\n")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
