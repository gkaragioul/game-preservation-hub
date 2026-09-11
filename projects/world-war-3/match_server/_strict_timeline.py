#!/usr/bin/env python3
"""Bidirectional timeline of the working capture around the player-in-game handoff.

Ground truth for the strict-order experiment: what does the *client* send between
`Client_RejoinIsPossible` (S->C source 1056) and the deploy transition bundle
(S->C source 1934), and what does the server send back in between?

S->C bunch indices are aligned to `real_replay_stream.json` by matching payload bit
strings, so the printed `src=N` values are directly comparable with the STRICT_*
specs in server.py.

Usage:
    python match_server/_strict_timeline.py --from 1040 --to 1960
    python match_server/_strict_timeline.py --summary
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


def load_stream() -> list[dict]:
    return json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pcap", default=str(PCAP))
    ap.add_argument("--sip", default=SERVER_IP)
    ap.add_argument("--sport", type=int, default=SERVER_PORT)
    ap.add_argument("--from", dest="lo", type=int, default=1040)
    ap.add_argument("--to", dest="hi", type=int, default=1960)
    ap.add_argument("--skip-c2s", type=int, nargs="*", default=[78],
                    help="C->S handles to suppress (per-tick spam)")
    ap.add_argument("--summary", action="store_true")
    args = ap.parse_args()

    skip = set(args.skip_c2s)
    stream = load_stream()
    # Align: real_replay_stream.json is a prefix-ordered subset of the S->C bunches.
    # Walk both in order and advance the stream cursor on payload match.
    cursor = 0
    nstream = len(stream)

    pkts = list(parse_pcap(args.pcap))
    rows: list[tuple] = []
    t0 = None
    c2s_first: dict[tuple[int, int], tuple] = {}
    c2s_count: collections.Counter = collections.Counter()
    s2c_seen = 0
    aligned = 0

    for ts, sip, sp, dip, dp, pl in pkts:
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
            if from_server:
                s2c_seen += 1
                idx = None
                if cursor < nstream:
                    try:
                        got = "".join(str(x) for x in bunch_payload_bits(b))
                    except Exception:
                        got = None
                    if got is not None and got == stream[cursor]["payload"]:
                        idx = cursor
                        cursor += 1
                        aligned += 1
                if idx is None:
                    continue
                if t0 is None and idx >= args.lo:
                    t0 = ts
                if args.lo <= idx <= args.hi and not args.summary:
                    ch = b.get("chIndex")
                    try:
                        fields = parse_actor_rpc_fields(
                            bunch_payload_bits(b),
                            value_max=PS_VALUE_MAX if ch == 7 else None)
                    except Exception:
                        fields = []
                    rows.append((ts, "S->C", idx, ch, b.get("bunchDataBits"),
                                 [int(h) for h, _ in fields] or None))
            else:
                ch = b.get("chIndex")
                try:
                    bits = bunch_payload_bits(b)
                except Exception:
                    continue
                vmax = PS_VALUE_MAX if ch == 7 else None
                try:
                    fields = parse_actor_rpc_fields(bits, value_max=vmax)
                except Exception:
                    fields = []
                hs = [int(h) for h, _ in fields]
                for h in hs:
                    c2s_count[(ch, h)] += 1
                    c2s_first.setdefault((ch, h), (ts, cursor))
                shown = [h for h in hs if h not in skip]
                if shown and args.lo <= cursor <= args.hi and not args.summary:
                    rows.append((ts, "C->S", cursor, ch, None, shown))

    print(f"# S->C bunches in flow: {s2c_seen}; aligned to stream: {aligned}/{nstream}")

    if args.summary:
        print(f"\n{'ch':>3} {'handle':>7} {'count':>7}  first-seen-near-src")
        for (ch, h), (ts, si) in sorted(c2s_first.items(), key=lambda kv: kv[1][1]):
            print(f"{ch:>3} {h:>7} {c2s_count[(ch, h)]:>7}  src~{si}")
        return 0

    if t0 is None:
        t0 = rows[0][0] if rows else 0
    print(f"\n{'t(s)':>9}  dir   {'src':>6}  ch  detail")
    for ts, d, i, ch, bits, hs in rows:
        rel = ts - t0
        if d == "S->C":
            extra = f" RPC handles={hs}" if hs else ""
            print(f"{rel:9.3f}  S->C  {i:>6}  {ch:<3} bits={bits}{extra}")
        else:
            print(f"{rel:9.3f}  C->S  ~{i:>5}  {ch:<3} RPC handles={hs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
