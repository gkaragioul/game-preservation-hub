#!/usr/bin/env python3
"""Decide how UE 4.21 encodes the ClassNetCache field handle in an RPC content block.

`possess_rpc.py` / `actor_channel.py` assume:

    payload := ( SerializeIntPacked(handle) SerializeIntPacked(NumPayloadBits) bits... )*

But UE's `WriteFieldHeaderAndPayload` writes the handle with
`Bunch.WriteIntWrapped(FieldCache->FieldNetIndex, ClassCache->GetMaxIndex() + 1)` --
a *fixed-width* LSB-first int whose width depends on the actor class's max field index --
and only `NumPayloadBits` with `SerializeIntPacked`.

Those two models are nearly indistinguishable from block sizes alone (a 7-bit handle plus
an N-bit payload occupies the same space as an 8-bit packed handle plus an (N-1)-bit
payload), so this probe settles it structurally: a correct model must consume every
content-block payload *exactly*, field after field, with no bits left over. A wrong model
survives the common case and breaks on the short zero/one-arg RPCs.

Run against a real match capture (client -> real dedicated server), which contains the
full spread of PlayerController RPC sizes.
"""
from __future__ import annotations

import argparse
import collections
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


def read_packed(pb: list[int], pos: int) -> tuple[int, int]:
    v = 0
    c = 0
    while True:
        if pos + 8 > len(pb):
            raise EOFError
        x = 0
        for i in range(8):
            x |= pb[pos + i] << i
        pos += 8
        v += (x >> 1) << (7 * c)
        c += 1
        if not (x & 1):
            return v, pos


def read_fixed(pb: list[int], pos: int, nbits: int) -> tuple[int, int]:
    if pos + nbits > len(pb):
        raise EOFError
    v = 0
    for i in range(nbits):
        v |= pb[pos + i] << i
    return v, pos + nbits


def try_model(pb: list[int], handle_bits: int | None) -> list[int] | None:
    """Walk the field chain. Returns handles if the payload is consumed exactly."""
    pos = 0
    handles: list[int] = []
    while pos < len(pb):
        try:
            if handle_bits is None:
                h, pos = read_packed(pb, pos)
            else:
                h, pos = read_fixed(pb, pos, handle_bits)
            n, pos = read_packed(pb, pos)
        except EOFError:
            return None
        if pos + n > len(pb):
            return None
        pos += n
        handles.append(h)
    return handles if pos == len(pb) else None


def collect_blocks(pcap: Path, chan: int, sip: str, sport: int) -> list[list[int]]:
    from pcap_tools import parse_pcap

    pkts = list(parse_pcap(str(pcap)))
    if sip == "auto":
        flows: collections.Counter = collections.Counter()
        for ts, src, sp, dst, dp, pl in pkts:
            flows[(dst, dp)] += 1
        (sip, sport), n = flows.most_common(1)[0]
        print(f"auto-detected server endpoint {sip}:{sport} ({n} C->S datagrams)")

    out: list[list[int]] = []
    for ts, src, sp, dst, dp, pl in pkts:
        if not (dst == sip and dp == sport):
            continue
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
                blocks = read_content_blocks(Bits(payload_bits(b)))
            except Exception:
                continue
            for bl in blocks:
                if bl.get("hasRepLayout") or not bl.get("isActor"):
                    continue
                pb = bl.get("payload") or []
                if pb:
                    out.append(pb)
    return out


def collect_session(path: Path, chan: int) -> list[list[int]]:
    import binascii
    import json

    out: list[list[int]] = []
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
                    blocks = read_content_blocks(Bits(payload_bits(b)))
                except Exception:
                    continue
                for bl in blocks:
                    if bl.get("hasRepLayout") or not bl.get("isActor"):
                        continue
                    pb = bl.get("payload") or []
                    if pb:
                        out.append(pb)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pcap")
    ap.add_argument("--session")
    ap.add_argument("--chan", type=int, default=2)
    ap.add_argument("--sip", default="auto")
    ap.add_argument("--sport", type=int, default=7868)
    args = ap.parse_args()

    if args.session:
        blocks = collect_session(Path(args.session), args.chan)
    else:
        blocks = collect_blocks(Path(args.pcap), args.chan, args.sip, args.sport)
    print(f"collected {len(blocks)} isActor/no-RepLayout content-block payloads on "
          f"ch{args.chan}\n")

    models: list[tuple[str, int | None]] = [("packed", None)]
    models += [(f"fixed{n}", n) for n in range(4, 13)]

    print(f"{'model':>8} {'exact':>8} {'rate':>7}  distinct handles (top 14 by count)")
    results = {}
    for name, hb in models:
        ok = 0
        hist: collections.Counter = collections.Counter()
        for pb in blocks:
            hs = try_model(pb, hb)
            if hs is None:
                continue
            ok += 1
            for h in hs:
                hist[h] += 1
        results[name] = (ok, hist)
        top = ", ".join(f"{h}:{c}" for h, c in hist.most_common(14))
        rate = ok / len(blocks) if blocks else 0
        print(f"{name:>8} {ok:>8} {rate:>6.1%}  {top}")

    best = max(results.items(), key=lambda kv: kv[1][0])
    print(f"\nbest model: {best[0]}  ({best[1][0]}/{len(blocks)} exact)")
    print("full handle histogram for best model:")
    for h, c in sorted(best[1][1].items()):
        print(f"  handle {h:>4}  n={c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
