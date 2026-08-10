#!/usr/bin/env python3
"""Bidirectional timeline around the capture's deploy handshake.

The live client's `AWW3GamePlayerController::CapturePointsComponents` (0x1730) is
**empty** (Num=0) and `SpectatePoint.SpectateCapturePoint.CapturePoint` is NULL,
even though 3 `UWW3CaptureAreaComponent` and 3 `AWW3CapturePoint` exist in its
world.  That empty array is why the client never sends h305
`Server_SpectatorAttachToCapturePoint` and therefore never sends h287.

So: what had the real server sent by the time its client filled that array?
`_c2s_deploy_timeline.py` gives the client side; this interleaves both directions
by pcap timestamp so the server-side precondition is visible.

    C->S pkt 38  h281  deploy screen up
    C->S pkt 154 h208 + h310 + h305   loadout + spectator + FIRST capture-point attach
    C->S pkt 209 h287                 DEPLOY

Usage:
    python match_server/_deploy_bidir_timeline.py
    python match_server/_deploy_bidir_timeline.py --around 154 --window 4.0

`--window` is in SECONDS.  (It briefly had to be passed as ~4000 because
`pcap_tools` hardcoded a microsecond divisor while these pcapng files declare
nanoseconds, so timestamps arrived 1000x too large.  The reader now reads
`if_tsresol` per interface, so seconds are seconds.)
"""
from __future__ import annotations

import argparse
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
NOISE_C2S = {78, 79, 73, 191}
# Leaf-local listing index + 130 == wire handle; validated on 6 anchors.
NAMES = {281: "Server_OnMapOpened", 310: "Server_StartSpectator",
         305: "Server_SpectatorAttachToCapturePoint",
         287: "Server_RequestRespawnAtCapturePoint",
         208: "Server_SetProfileMainEquipmentLoadoutIndex",
         280: "Server_OnMapClosed", 279: "Server_OnClientPreloadWeaponsFinished",
         64: "ServerAcknowledgePossession", 231: "Client_OnCapturePointRespawnRequestStatusChanged"}


def bits_of(b):
    r = b["reader"]
    return [r.read_bit() for _ in range(b["payloadBits"])] if b["payloadBits"] else []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pcap", default=PCAP)
    ap.add_argument("--around", type=int, default=154)
    ap.add_argument("--window", type=float, default=6.0)
    args = ap.parse_args()

    pk = parse_pcap(args.pcap)
    c2s_idx, rows = 0, []
    for ts, src, sp, dst, dp, pl in pk:
        out = (dst == SERVER_IP and dp == SERVER_PORT)
        if out:
            i = c2s_idx
            c2s_idx += 1
        else:
            i = None
        if not out and not (src == SERVER_IP and sp == SERVER_PORT):
            continue
        rows.append((ts, out, i, pl))

    anchor = None
    for ts, out, i, _pl in rows:
        if out and i == args.around:
            anchor = ts
            break
    if anchor is None:
        print(f"C->S packet {args.around} not found")
        return 2
    lo, hi = anchor - args.window, anchor + args.window
    print(f"anchor: C->S packet {args.around} at t={anchor:.3f}; "
          f"window +/-{args.window}s\n")

    for ts, out, i, pl in rows:
        if not (lo <= ts <= hi):
            continue
        try:
            pkt = cc.read_packet(pl)
        except Exception:
            continue
        if pkt.get("is_handshake") or pkt.get("truncated"):
            continue
        for b in pkt.get("bunches", []) or []:
            ch = int(b.get("chIndex", -1))
            bits = bits_of(b)
            try:
                fields = parse_actor_rpc_fields(bits)
            except Exception:
                fields = []
            hs = [int(h) for h, _p in fields]
            if out:
                hs = [h for h in hs if h not in NOISE_C2S]
                if not hs:
                    continue
                tag = f"C->S pkt{i}"
            else:
                tag = "S->C      "
                if not hs and not b.get("bOpen"):
                    continue
            named = ", ".join(f"h{h}" + (f" {NAMES[h]}" if h in NAMES else "")
                              for h in hs) or "(no rpc)"
            opn = " OPEN" if b.get("bOpen") else ""
            print(f"  t={ts - anchor:+8.3f}  {tag}  ch{ch:<3}{opn:5} {named}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
