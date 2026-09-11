#!/usr/bin/env python3
"""Histogram every C->S PlayerController-channel RPC handle actually seen on the wire.

This is the ground truth that decides the *absolute* base of the PlayerController
ClassNetCache. `derive_net_handles.py` reconstructs the ordering from the Dumper-7 dump
and reproduces the observed spacings exactly, but the absolute offset has to come from
the wire: whichever handle dominates a live PC channel is `ServerUpdateCamera` (the
client sends it every tick), and that pins the whole table.

Sources:
  --session match_server/live_log/session_*.jsonl   (our mock server's own recording)
  --pcap    captures/24July26/W3_match_full_2.pcapng (a real, working dedicated match)
"""
from __future__ import annotations

import argparse
import binascii
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "match_analysis"))

import control_channel as cc  # noqa: E402
from actor_channel import Bits, read_content_blocks  # noqa: E402


def payload_bits(b: dict) -> list[int]:
    r = b["reader"]
    start = b["payloadStart"]
    n = b["bunchDataBits"]
    return [((r.data[(start + i) >> 3] >> ((start + i) & 7)) & 1) for i in range(n)]


def tally(bits: list[int], hist: collections.Counter, args_seen: dict) -> None:
    try:
        blocks = read_content_blocks(Bits(bits))
    except Exception:
        return
    for bl in blocks:
        if bl.get("hasRepLayout") or not bl.get("isActor"):
            continue
        pb = bl.get("payload") or []
        if not pb:
            continue
        r = Bits(pb)
        try:
            h = r.packed()
        except EOFError:
            continue
        if h > 400:
            continue
        hist[h] += 1
        vals = []
        try:
            while r.left() >= 8 and len(vals) < 3:
                vals.append(r.packed())
        except EOFError:
            pass
        info = args_seen.setdefault(h, {"paybits": collections.Counter(),
                                        "firstvals": collections.Counter()})
        info["paybits"][len(pb)] += 1
        if vals:
            info["firstvals"][vals[0]] += 1
        else:
            info["firstvals"]["<none>"] += 1


def scan_session(path: Path, chan: int) -> tuple[collections.Counter, dict]:
    hist: collections.Counter = collections.Counter()
    args_seen: dict = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("dir") != "C->S":
                continue
            try:
                p = cc.read_packet(binascii.unhexlify(d["hex"]))
            except Exception:
                continue
            if p.get("is_handshake"):
                continue
            for b in p.get("bunches", []):
                if b.get("chIndex") != chan:
                    continue
                try:
                    tally(payload_bits(b), hist, args_seen)
                except Exception:
                    continue
    return hist, args_seen


def scan_pcap(path: Path, chan: int, sip: str, sport: int) -> tuple[collections.Counter, dict]:
    from pcap_tools import parse_pcap

    pkts = list(parse_pcap(str(path)))
    if sip == "auto":
        flows: collections.Counter = collections.Counter()
        for ts, src, sp, dst, dp, pl in pkts:
            flows[(dst, dp)] += 1
        (sip, sport), n = flows.most_common(1)[0]
        print(f"  auto-detected server endpoint {sip}:{sport} ({n} C->S datagrams)")

    hist: collections.Counter = collections.Counter()
    args_seen: dict = {}
    for ts, src, sp, dst, dp, pl in pkts:
        if not (dst == sip and dp == sport):
            continue  # C->S only
        try:
            p = cc.read_packet(pl)
        except Exception:
            continue
        if p.get("is_handshake"):
            continue
        for b in p.get("bunches", []):
            if b.get("chIndex") != chan:
                continue
            try:
                tally(payload_bits(b), hist, args_seen)
            except Exception:
                continue
    return hist, args_seen


def report(label: str, hist: collections.Counter, args_seen: dict, top: int) -> None:
    total = sum(hist.values())
    print(f"\n=== {label}: {total} RPC blocks, {len(hist)} distinct handles ===")
    print(f"{'handle':>7} {'count':>8}  payload-bits(top3)          first-arg(top3)")
    for h, c in hist.most_common(top):
        info = args_seen.get(h, {})
        pb = ", ".join(f"{k}:{v}" for k, v in info.get("paybits",
                                                       collections.Counter()).most_common(3))
        fv = ", ".join(f"{k}:{v}" for k, v in info.get("firstvals",
                                                      collections.Counter()).most_common(3))
        print(f"{h:>7} {c:>8}  {pb:<27} {fv}")
    if hist:
        dom, domc = hist.most_common(1)[0]
        print(f"\n  dominant handle = {dom} (n={domc})")
        print(f"  if dominant == ServerUpdateCamera  -> ServerAcknowledgePossession = {dom - 14}")
        print(f"  (alphabetical Server* offsets from Ack: Camera+1 CheckPossession+3 "
              f"Notify+6 UpdateCamera+14 UpdateLevelVis+15)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", action="append", default=[])
    ap.add_argument("--pcap")
    ap.add_argument("--chan", type=int, default=2)
    ap.add_argument("--pcap-chan", type=int, default=None)
    ap.add_argument("--sip", default="213.183.62.18")
    ap.add_argument("--sport", type=int, default=7868)
    ap.add_argument("--top", type=int, default=30)
    args = ap.parse_args()

    for s in args.session:
        p = Path(s)
        if not p.is_file():
            print(f"missing {p}", file=sys.stderr)
            continue
        hist, seen = scan_session(p, args.chan)
        report(f"session {p.name} ch{args.chan}", hist, seen, args.top)

    if args.pcap:
        p = Path(args.pcap)
        if p.is_file():
            ch = args.chan if args.pcap_chan is None else args.pcap_chan
            hist, seen = scan_pcap(p, ch, args.sip, args.sport)
            report(f"pcap {p.name} ch{ch}", hist, seen, args.top)
        else:
            print(f"missing {p}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
