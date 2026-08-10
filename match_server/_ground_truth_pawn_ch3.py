#!/usr/bin/env python3
"""Ground-truth: reconstruct EVERY ch3 (pawn) bunch across the whole real match capture,
reassemble partials, and report whether an isActor=True content block (the pawn's OWN
RepLayout) EVER appears on ch3, and if so, when (packet index) relative to the pawn open.

Also dumps a per-bunch summary (open/partial/exports/size) for the first N ch3 bunches
so we can see the exact real cadence the client received without guessing.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "match_analysis"))

from pcap_tools import parse_pcap
import control_channel as cc
from actor_channel import read_content_blocks, read_new_actor, Bits
from netguid import PackageMap

ROOT = os.path.join(os.path.dirname(__file__), "..")
PCAP = os.path.join(ROOT, "captures", "24July26", "W3_match_full_2.pcapng")


def bunch_payload_bits(b):
    r = b["reader"]
    return [r.read_bit() for _ in range(b["payloadBits"])] if b["payloadBits"] else []


def main():
    print(f"Loading {PCAP} ...")
    pk = parse_pcap(PCAP)
    sip, sport = "213.183.62.18", 7868
    s2c = [pl for ts, src, sp, dst, dp, pl in pk if src == sip and sp == sport]
    print(f"S->C packets: {len(s2c)}")

    ch3_bunches = []   # (pkt_i, bunch dict, payload bits)
    for pkt_i, d in enumerate(s2c):
        try:
            p = cc.read_packet(d)
        except Exception:
            continue
        if p.get("is_handshake") or p.get("truncated"):
            continue
        for b in p.get("bunches", []):
            if b["chIndex"] == 3:
                ch3_bunches.append((pkt_i, b, bunch_payload_bits(b)))

    print(f"Total ch3 bunches across match: {len(ch3_bunches)}")

    # Reassemble partial groups in order (ChSequence not tracked here; assume in-order
    # arrival which held for the earlier bit-identical comparison).
    groups = []
    cur = None
    for pkt_i, b, bits in ch3_bunches:
        if b.get("bPartial"):
            if b.get("bPartialInitial"):
                cur = {"start_pkt": pkt_i, "bits": list(bits), "meta": [ (pkt_i,b) ]}
            elif cur is not None:
                cur["bits"].extend(bits)
                cur["meta"].append((pkt_i, b))
                if b.get("bPartialFinal"):
                    groups.append(cur)
                    cur = None
        else:
            groups.append({"start_pkt": pkt_i, "bits": list(bits), "meta": [(pkt_i, b)]})

    print(f"Reassembled ch3 groups: {len(groups)}")
    print()
    print("=== First 15 ch3 groups: header + content-block scan ===")
    found_actor_block_at = None
    for gi, g in enumerate(groups[:60]):
        first_b = g["meta"][0][1]
        bits = g["bits"]
        pm = PackageMap()
        pos = 0
        exports = None
        if first_b.get("bHasPackageMapExports"):
            res = pm.read_export_bunch(bits)
            exports = res["num"]
            r = res["reader"]
            pos = r.pos
        actor_info = None
        blocks = []
        try:
            if first_b.get("bOpen"):
                from netguid import GuidReader
                r2 = GuidReader(bits, pos)
                info = read_new_actor(r2, pm)
                actor_info = info.get("netguid")
                pos = r2.pos
            rb = Bits(bits, pos)
            blocks = read_content_blocks(rb, total_bits=len(bits))
        except Exception as e:
            blocks = [{"error": str(e)}]

        has_actor_block = any(bl.get("isActor") for bl in blocks if isinstance(bl, dict))
        if has_actor_block and found_actor_block_at is None:
            found_actor_block_at = gi

        print(f"[group {gi:3d}] pkt={g['start_pkt']:5d} bOpen={first_b.get('bOpen')} "
              f"exports={exports} newActorGUID={actor_info} nBlocks={len(blocks)} "
              f"isActorBlockPresent={has_actor_block} bits={len(bits)}")
        for bl in blocks:
            if not isinstance(bl, dict):
                continue
            print("    block:", {k: v for k, v in bl.items() if k not in ("payload",)})

    print()
    if found_actor_block_at is not None:
        print(f"*** pawn's OWN isActor=True content block FIRST appears in group {found_actor_block_at} ***")
    else:
        print("*** isActor=True content block for the pawn NEVER found in first 60 groups ***")

    # Full-match scan (no per-block dump) to see if it EVER appears at all.
    print()
    print("=== Full-match scan for isActor=True on ch3 ===")
    any_found = []
    for gi, g in enumerate(groups):
        first_b = g["meta"][0][1]
        bits = g["bits"]
        pm = PackageMap()
        pos = 0
        try:
            if first_b.get("bHasPackageMapExports"):
                res = pm.read_export_bunch(bits)
                pos = res["reader"].pos
            if first_b.get("bOpen"):
                from netguid import GuidReader
                r2 = GuidReader(bits, pos)
                info = read_new_actor(r2, pm)
                pos = r2.pos
            rb = Bits(bits, pos)
            blocks = read_content_blocks(rb, total_bits=len(bits))
        except Exception:
            continue
        if any(bl.get("isActor") for bl in blocks if isinstance(bl, dict)):
            any_found.append(gi)
    print(f"groups (of {len(groups)}) with isActor=True block: {len(any_found)}")
    print("first 20 indices:", any_found[:20])


if __name__ == "__main__":
    main()
