#!/usr/bin/env python3
"""Find ClientRestart-like S->C RPCs in the Gobi/full-match capture stream + pcap.

Result (2026-08-05): capture has ZERO non-null AckPossession and no handle+9372
ClientRestart RPC. Listen-server path uses PC RepLayout Pawn=9372 (src13) only.
Dedicated mock must craft ClientRestart wire handle 9 (see possess_rpc.py).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "match_analysis"))

from actor_channel import Bits, read_content_blocks  # noqa: E402
from possess_rpc import parse_actor_rpc_handles, build_object_rpc_bits, PAWN_NETGUID  # noqa: E402
import control_channel as cc  # noqa: E402


def packed_bits(v: int) -> list[int]:
    bits: list[int] = []
    while True:
        byte = (v & 0x7F) << 1
        v >>= 7
        if v:
            byte |= 1
        for i in range(8):
            bits.append((byte >> i) & 1)
        if not v:
            break
    return bits


def dump_rpc_blocks(bits: list[int], label: str) -> None:
    print(f"--- {label} bits={len(bits)} ---")
    try:
        blocks = read_content_blocks(Bits(bits))
    except Exception as e:
        print("  read_content_blocks fail", e)
        return
    for bi, bl in enumerate(blocks):
        pb = bl.get("payload") or []
        print(
            f"  bl{bi}: isActor={bl.get('isActor')} hasRep={bl.get('hasRepLayout')} "
            f"sub={bl.get('subNetGUID')} pay={len(pb)}"
        )
        if bl.get("hasRepLayout") or not pb:
            continue
        r = Bits(pb)
        try:
            h = r.packed()
        except EOFError:
            continue
        vals = []
        try:
            while r.left() >= 8 and len(vals) < 6:
                vals.append(r.packed())
        except EOFError:
            pass
        by = bytearray((len(pb) + 7) // 8)
        for i, bit in enumerate(pb):
            if bit:
                by[i >> 3] |= 1 << (i & 7)
        print(f"    handle={h} vals={vals} rem={r.left()} hex={by.hex()}")


def analyze_stream() -> None:
    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
    needle = packed_bits(PAWN_NETGUID)
    print(f"=== stream scan for packed {PAWN_NETGUID} in ch2 actor RPC payloads ===")
    hits = []
    for i, b in enumerate(stream[:400]):
        if b.get("chIndex") != 2:
            continue
        bits = [int(c) for c in b["payload"]]
        # find needle aligned as packed int after a small handle
        try:
            blocks = read_content_blocks(Bits(bits))
        except Exception:
            continue
        for bi, bl in enumerate(blocks):
            if bl.get("hasRepLayout") or not bl.get("isActor"):
                continue
            pb = bl.get("payload") or []
            if len(pb) < 16:
                continue
            # search for 9372 bit pattern
            for p in range(len(pb) - len(needle) + 1):
                if pb[p : p + len(needle)] != needle:
                    continue
                # try decode handle if pattern starts after packed handle
                try:
                    r = Bits(pb)
                    h = r.packed()
                    if r.pos == p:
                        hits.append((i, bi, h, p, len(pb), b.get("bits"), b.get("bReliable")))
                        print(
                            f"  ALIGNED src={i} bl={bi} handle={h} guid@{p} "
                            f"pay={len(pb)} bunch={b['bits']} rel={b.get('bReliable')}"
                        )
                    else:
                        # unaligned mention
                        if p < 40:
                            print(
                                f"  unaligned src={i} bl={bi} 9372@{p} "
                                f"(first_packed would be handle? try skip)"
                            )
                except Exception:
                    pass
            # also: any handle < 80 with second packed == 9372
            try:
                r = Bits(pb)
                h = r.packed()
                if h == 0 or h > 200:
                    continue
                if r.left() < 8:
                    continue
                g = r.packed()
                if g == PAWN_NETGUID:
                    print(
                        f"  HANDLE+GUID src={i} bl={bi} h={h} g={g} "
                        f"pay={len(pb)} rem={r.left()} rel={b.get('bReliable')}"
                    )
            except Exception:
                pass

    print("\n=== detailed dump of ownership-critical srcs ===")
    for i in (3, 4, 8, 9, 12, 13, 10, 11, 204, 210):
        if i >= len(stream):
            continue
        b = stream[i]
        bits = [int(c) for c in b["payload"]]
        dump_rpc_blocks(
            bits,
            f"src={i} ch={b['chIndex']} bits={b['bits']} rel={b.get('bReliable')} "
            f"exp={b.get('bHasPackageMapExports')} P={b.get('bPartial')}",
        )

    # Compare our crafted ClientRestart(8) to anything in stream
    print("\n=== compare crafted ClientRestart handles 7-20 to stream payloads ===")
    for h in range(7, 21):
        crafted = build_object_rpc_bits(h, PAWN_NETGUID)
        for i, b in enumerate(stream[:300]):
            if b.get("chIndex") != 2:
                continue
            bits = [int(c) for c in b["payload"]]
            try:
                blocks = read_content_blocks(Bits(bits))
            except Exception:
                continue
            for bl in blocks:
                pb = bl.get("payload") or []
                # framed content block equals crafted?
                # crafted IS a full content block
                if bits == crafted or pb == crafted:
                    print(f"  EXACT match handle {h} at src {i}")
                # inner payload match
                inner = build_object_rpc_bits(h, PAWN_NETGUID)
                # get inner of crafted
                cbl = read_content_blocks(Bits(crafted))[0]["payload"]
                if pb == cbl:
                    print(f"  INNER match handle {h} at src {i} bunchbits={b['bits']}")


def analyze_pcap_acks() -> None:
    """In real pcap: find C->S AckPossession(non-null) and preceding S->C RPCs."""
    from pcap_tools import parse_pcap

    cap = HERE.parent / "captures" / "24July26" / "W3_match_full_2.pcapng"
    if not cap.exists():
        print("pcap missing", cap)
        return
    print(f"\n=== pcap {cap.name} AckPossession timeline ===")
    pk = parse_pcap(str(cap))
    sip, sport = "213.183.62.18", 7868
    events = []
    for ts, src, sp, dst, dp, pl in pk:
        if (dst == sip and dp == sport) or (src == sip and sp == sport):
            direction = "C->S" if dst == sip else "S->C"
            events.append((ts, direction, pl))

    # Find first Actor channel traffic after Join-ish; look for Ack with non-zero
    ack_hits = []
    for idx, (ts, direction, pl) in enumerate(events):
        if direction != "C->S":
            continue
        try:
            p = cc.read_packet(pl)
        except Exception:
            continue
        if p.get("is_handshake"):
            continue
        for b in p.get("bunches") or []:
            if b.get("chIndex") != 2:
                continue
            nb = b.get("payloadBits") or 0
            if not b.get("bReliable") or nb > 300 or nb < 16:
                continue
            try:
                from ps_rebind import bunch_payload_bits

                bits = bunch_payload_bits(b)
                hs = parse_actor_rpc_handles(bits)
            except Exception:
                continue
            for h, vals in hs:
                if h == 34:  # ServerAcknowledgePossession
                    ack_hits.append((idx, ts, vals, nb))
                    print(f"  Ack @evt={idx} t={ts:.3f} vals={vals} bits={nb}")

    print(f"total AckPossession events: {len(ack_hits)}")
    # For first non-null ack, dump preceding S->C ch2 reliable small bunches
    for idx, ts, vals, nb in ack_hits[:5]:
        if not vals or vals[0] == 0:
            continue
        print(f"\n=== S->C before first non-null Ack vals={vals} (lookback 40 events) ===")
        for j in range(max(0, idx - 40), idx):
            ts2, d2, pl2 = events[j]
            if d2 != "S->C":
                continue
            try:
                p = cc.read_packet(pl2)
            except Exception:
                continue
            for b in p.get("bunches") or []:
                if b.get("chIndex") != 2 or not b.get("bReliable"):
                    continue
                nbb = b.get("payloadBits") or 0
                if nbb == 0 or nbb > 500:
                    continue
                try:
                    from ps_rebind import bunch_payload_bits

                    bits = bunch_payload_bits(b)
                    dump_rpc_blocks(
                        bits,
                        f"evt={j} bits={nbb} MBM={b.get('bHasMustBeMappedGUIDs')} "
                        f"exp={b.get('bHasPackageMapExports')}",
                    )
                except Exception as e:
                    print(f"  evt={j} bits={nbb} fail {e}")
        break
    else:
        print("No non-null AckPossession found in pcap (client may be host?)")
        # Still dump early S->C after first big actor open
        print("\n=== early S->C ch2 reliable (first 80 matching) ===")
        n = 0
        for j, (ts2, d2, pl2) in enumerate(events):
            if d2 != "S->C":
                continue
            try:
                p = cc.read_packet(pl2)
            except Exception:
                continue
            if p.get("is_handshake"):
                continue
            for b in p.get("bunches") or []:
                if b.get("chIndex") != 2 or not b.get("bReliable"):
                    continue
                nbb = b.get("payloadBits") or 0
                if nbb < 16 or nbb > 200:
                    continue
                try:
                    from ps_rebind import bunch_payload_bits

                    bits = bunch_payload_bits(b)
                    hs = parse_actor_rpc_handles(bits)
                except Exception:
                    continue
                if not hs:
                    continue
                # filter move false positives: only small handles
                rare = [(h, v) for h, v in hs if h < 80]
                if rare:
                    print(f"  evt={j} bits={nbb} MBM={b.get('bHasMustBeMappedGUIDs')} rpc={rare}")
                    n += 1
                    if n >= 80:
                        return


if __name__ == "__main__":
    analyze_stream()
    analyze_pcap_acks()
