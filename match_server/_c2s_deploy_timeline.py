#!/usr/bin/env python3
"""Decode the CLIENT->SERVER direction of the real capture, in wire order.

Everything we believe about the deploy handshake -- that the real client pressed
DEPLOY (h287 `Server_RequestRespawnAtCapturePoint`) at src ~1841 and the server
answered with src 1856 then src 1934 -- has so far been read off the *server to
client* stream plus comments in `server.py`.  It has never been checked against
the client's own transmissions.

This decodes C->S with the exact parser `server.py` uses on live client bunches
(`parse_actor_rpc_fields`), so handle numbers are directly comparable to the
`client ch2 RPC handles=[...]` lines in our own logs.  Note server.py filters
{39, 78, 79, 9, 10} out of that log line (camera/possession probes), so those
appear here but not there.

Usage:
    python match_server/_c2s_deploy_timeline.py
    python match_server/_c2s_deploy_timeline.py --look 287,310,281,208,64
"""
from __future__ import annotations

import argparse
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "match_analysis"))

import control_channel as cc  # noqa: E402
from pcap_tools import parse_pcap  # noqa: E402
from possess_rpc import parse_actor_rpc_fields  # noqa: E402

PCAP = os.path.join(HERE, "..", "captures", "24July26", "W3_match_full_2.pcapng")
SERVER_IP, SERVER_PORT = "213.183.62.18", 7868


def bunch_payload_bits(b):
    r = b["reader"]
    return [r.read_bit() for _ in range(b["payloadBits"])] if b["payloadBits"] else []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pcap", default=PCAP)
    ap.add_argument("--look", default="287,310,281,208,64,279,73,299,235")
    ap.add_argument("--channels", default="")
    ap.add_argument("--sip", default=SERVER_IP)
    ap.add_argument("--sport", type=int, default=SERVER_PORT)
    ap.add_argument("--auto", action="store_true",
                    help="detect the busiest UDP flow as the game server")
    args = ap.parse_args()
    look = {int(x) for x in args.look.split(",") if x.strip()}
    only = {int(x) for x in args.channels.split(",") if x.strip()}

    print(f"Loading {args.pcap} ...")
    pk = parse_pcap(args.pcap)
    sip, sport = args.sip, args.sport
    if args.auto:
        # Each match runs on its own port (full_2 = :7868, full_1 = :7870),
        # so the endpoint cannot be hardcoded across captures.
        flows = collections.Counter()
        for _ts, src, sp, dst, dp, _pl in pk:
            flows[(dst, dp)] += 1
        (sip, sport), _n = flows.most_common(1)[0]
        print(f"  auto endpoint: {sip}:{sport}")
    c2s = [pl for ts, src, sp, dst, dp, pl in pk
           if dst == sip and dp == sport]
    print(f"  {len(pk)} packets, {len(c2s)} C->S\n")

    per_chan = collections.Counter()
    hist = collections.Counter()
    chan_hist = collections.defaultdict(collections.Counter)
    hits = []
    for i, data in enumerate(c2s):
        try:
            pkt = cc.read_packet(data)
        except Exception:
            continue
        if pkt.get("is_handshake") or pkt.get("truncated"):
            continue
        for b in pkt.get("bunches", []) or []:
            ch = int(b.get("chIndex", -1))
            if only and ch not in only:
                continue
            per_chan[ch] += 1
            bits = bunch_payload_bits(b)
            try:
                fields = parse_actor_rpc_fields(bits)
            except Exception:
                continue
            for h, _p in fields:
                h = int(h)
                hist[h] += 1
                chan_hist[ch][h] += 1
                if h in look:
                    hits.append((i, ch, h))

    print("C->S bunches per channel:")
    for ch, n in per_chan.most_common(12):
        print(f"  ch{ch:<4} {n}")

    print(f"\nC->S RPC handles seen ({len(hist)} distinct), same numbering as our logs:")
    for h, n in hist.most_common(40):
        chans = ",".join(f"ch{c}" for c in sorted(chan_hist) if chan_hist[c][h])
        print(f"  h{h:<5} {n:>7}   {chans}")

    print(f"\n=== looked-for handles {sorted(look)} ===")
    if not hits:
        print("  NONE of them appear anywhere in the client's transmissions.")
    else:
        seen = collections.Counter(h for _i, _c, h in hits)
        for h, n in sorted(seen.items()):
            first = next(x for x in hits if x[2] == h)
            print(f"  h{h}: {n} time(s), first at C->S packet {first[0]} on ch{first[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
