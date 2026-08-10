#!/usr/bin/env python3
r"""Ground-truth: read `bHasMustBeMappedGUIDs` off the real wire for the PlayerController
bunches the bootstrap replays, and decode the MustBeMapped GUID list that precedes their
payload.

This matters because `real_replay_stream.json` never captured the flag, so every replayed
bunch goes out with it clear. Capture stream index 8 carries the real server's own
`ClientRestart(9372)` together with `Client_OnPlayerRespawned` and `ClientGameStarted`,
and it is sent *before* the pawn channel opens (index 10). On the real server that bunch
can only have worked if it was MustBeMapped-queued on 9372 and released when the pawn
arrived. Replaying it with the flag clear makes the client run all three RPCs against a
pawn it does not have yet.

  python match_server/_ground_truth_mbm_ch2.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "match_analysis"))

import control_channel as cc  # noqa: E402
from pcap_tools import parse_pcap  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PCAP = os.path.join(ROOT, "captures", "24July26", "W3_match_full_2.pcapng")
STREAM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "real_replay_stream.json")

# Everything the ownership bootstrap replays on ch2, plus the two skipped possession
# bunches (204/208-211/214 window) for comparison.
TARGETS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 13, 204, 208, 209, 210, 211, 214]


def bunch_payload_bits(b):
    r = b["reader"]
    return [r.read_bit() for _ in range(b["payloadBits"])] if b["payloadBits"] else []


def main() -> None:
    stream = json.load(open(STREAM))
    targets = {i: [int(c) for c in stream[i]["payload"]] for i in TARGETS
               if i < len(stream) and stream[i]["chIndex"] == 2}
    print(f"targets on ch2: {sorted(targets)}")

    print(f"Loading {PCAP} ...")
    pk = parse_pcap(PCAP)
    sip, sport = "213.183.62.18", 7868
    s2c = [pl for ts, src, sp, dst, dp, pl in pk if src == sip and sp == sport]
    print(f"S->C packets: {len(s2c)}")

    found: dict[int, dict] = {}
    for pkt_i, d in enumerate(s2c):
        try:
            p = cc.read_packet(d)
        except Exception:
            continue
        if p.get("is_handshake") or p.get("truncated"):
            continue
        for b in p.get("bunches", []):
            if b["chIndex"] != 2 or b["payloadBits"] == 0:
                continue
            pb = bunch_payload_bits(b)
            for idx, want in targets.items():
                if idx in found or len(pb) != len(want) or pb != want:
                    continue
                found[idx] = {
                    "pkt": pkt_i,
                    "bOpen": b["bOpen"],
                    "bPartial": b["bPartial"],
                    "bPartialInitial": b.get("bPartialInitial"),
                    "bPartialFinal": b.get("bPartialFinal"),
                    "bHasPackageMapExports": b["bHasPackageMapExports"],
                    "bHasMustBeMappedGUIDs": b["bHasMustBeMappedGUIDs"],
                    "mustBeMappedGUIDs": b.get("mustBeMappedGUIDs"),
                }
        if len(found) == len(targets):
            break

    print()
    for idx in sorted(targets):
        info = found.get(idx)
        print(f"src={idx:4d} -> {info if info else 'NOT FOUND (no exact bit match)'}")


if __name__ == "__main__":
    main()
