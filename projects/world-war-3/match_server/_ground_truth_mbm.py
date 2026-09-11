#!/usr/bin/env python3
"""Ground-truth check: does the REAL pawn-open bunch in the original pcap have
bHasMustBeMappedGUIDs set? real_replay_stream.json never captured this bit (key is
absent), so build_replay_bunch() has always sent it as 0. This script re-parses the
original capture and finds the exact bunches (matched by payload bits) to read the
true on-wire value, instead of guessing.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "match_analysis"))

from pcap_tools import parse_pcap
import control_channel as cc

ROOT = os.path.join(os.path.dirname(__file__), "..")
PCAP = os.path.join(ROOT, "captures", "24July26", "W3_match_full_2.pcapng")
STREAM = os.path.join(os.path.dirname(__file__), "real_replay_stream.json")


def bits_of(payload_str):
    return [int(c) for c in payload_str]


def bunch_payload_bits(b):
    r = b["reader"]
    return [r.read_bit() for _ in range(b["payloadBits"])] if b["payloadBits"] else []


def main():
    stream = json.load(open(STREAM))
    targets = {}
    for idx in (10, 11, 212, 213, 181, 192):
        s = stream[idx]
        targets[idx] = bits_of(s["payload"])

    print(f"Loading {PCAP} ...")
    pk = parse_pcap(PCAP)
    sip, sport = "213.183.62.18", 7868
    s2c = [pl for ts, src, sp, dst, dp, pl in pk if src == sip and sp == sport]
    print(f"S->C packets: {len(s2c)}")

    found = {}
    for pkt_i, d in enumerate(s2c):
        try:
            p = cc.read_packet(d)
        except Exception:
            continue
        if p.get("is_handshake") or p.get("truncated"):
            continue
        for b in p.get("bunches", []):
            if b["chIndex"] != 3 or b["payloadBits"] == 0:
                continue
            pb = bunch_payload_bits(b)
            for idx, want in targets.items():
                if idx in found:
                    continue
                if len(pb) == len(want) and pb == want:
                    found[idx] = {
                        "pkt": pkt_i,
                        "bOpen": b["bOpen"],
                        "bPartial": b["bPartial"],
                        "bPartialInitial": b.get("bPartialInitial"),
                        "bPartialFinal": b.get("bPartialFinal"),
                        "bHasPackageMapExports": b["bHasPackageMapExports"],
                        "bHasMustBeMappedGUIDs": b["bHasMustBeMappedGUIDs"],
                    }
        if len(found) == len(targets):
            break

    print()
    for idx in targets:
        if idx in found:
            print(f"src={idx:4d} -> {found[idx]}")
        else:
            print(f"src={idx:4d} -> NOT FOUND in pcap S->C stream (no exact bit match)")


if __name__ == "__main__":
    main()
