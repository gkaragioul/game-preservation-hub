#!/usr/bin/env python3
"""Recover the bunches that make Domination's capture points RESOLVABLE.

Turn 13.  The deploy screen needs two objects per spawn:

    h305 Server_SpectatorAttachToCapturePoint(<capture point actor>)
    h287 Server_RequestRespawnAtCapturePoint(<that point's "First Spawn Zone">)

and the client can only name either if their NetGUID -> path exports arrived.
Confirmed on four independent captures (24July StrongHold/DMZ/full_3, 3Aug
war_smolensk): `BP_CapturePoint_*` are static level actors that frequently open
**no actor channel of their own** -- they enter the client's PackageMap purely as
exports riding on *other* actors' open bunches.

In the Gobi capture that is exactly what happens.  The capture points Domination
actually uses are `BP_CapturePoint_A` / `BP_CapturePoint_B`, in the streaming
sublevel `WW3_Dunhuang_Gameplay_New_DOM` -- NOT the `WW3TdmCapturePoint_1/2` in
the persistent level that `_extract_capturepoints.py` replays (those look like
TDM leftovers, and replicating them produced a spawn tile that could not be
selected).  A/B are exported on two other players' PlayerState opens:

    ch  6  pkt 174   2 frags -> 4755 bits   BP_CapturePoint_B + "First Spawn Zone"
    ch 40  pkt 216   2 frags -> 4650 bits   BP_CapturePoint_A + "First Spawn Zone"

`real_replay_stream.json` holds only the partial-initial of each (src 18 / 92),
and the ownership bootstrap skips both entirely (it jumps src 17 -> 20), so our
client has never received them.  Unlike the capture-point channels' dangling
export, these DO reassemble into complete, replayable bunches.

Usage:
    python match_server/_extract_cp_exports.py            # report only
    python match_server/_extract_cp_exports.py --write
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "match_analysis"))

import control_channel as cc  # noqa: E402
from pcap_tools import parse_pcap  # noqa: E402
from _channel_class_map import strings_in  # noqa: E402

PCAP = os.path.join(HERE, "..", "captures", "24July26", "W3_match_full_2.pcapng")
OUT = os.path.join(HERE, "capturepoint_export_stream.json")
SERVER_IP, SERVER_PORT = "213.183.62.18", 7868
CHANNELS = (6, 40)
MARKERS = ("BP_CapturePoint", "First Spawn Zone")


def bits_str(b):
    r = b["reader"]
    return "".join("1" if r.read_bit() else "0" for _ in range(b["payloadBits"]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pcap", default=PCAP)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    print(f"Loading {args.pcap} ...")
    pk = parse_pcap(args.pcap)
    s2c = [pl for ts, src, sp, dst, dp, pl in pk
           if src == SERVER_IP and sp == SERVER_PORT]
    print(f"  {len(s2c)} S->C packets")

    raw = {c: [] for c in CHANNELS}
    for i, d in enumerate(s2c):
        try:
            p = cc.read_packet(d)
        except Exception:
            continue
        if p.get("is_handshake") or p.get("truncated"):
            continue
        for b in p.get("bunches", []) or []:
            ch = int(b.get("chIndex", -1))
            if ch in raw:
                raw[ch].append((i, b, bits_str(b)))

    out = []
    for ch in CHANNELS:
        groups, cur = [], None
        for i, b, bs in raw[ch]:
            if b.get("bPartial"):
                if b.get("bPartialInitial"):
                    cur = {"pkt": i, "bits": bs, "frags": 1,
                           "open": int(b.get("bOpen", 0)),
                           "reliable": int(b.get("bReliable", 0)),
                           "pme": int(b.get("bHasPackageMapExports", 0)),
                           "close": int(b.get("bClose", 0))}
                elif cur is not None:
                    cur["bits"] += bs
                    cur["frags"] += 1
                    if b.get("bPartialFinal"):
                        groups.append(cur)
                        cur = None
            else:
                groups.append({"pkt": i, "bits": bs, "frags": 1,
                               "open": int(b.get("bOpen", 0)),
                               "reliable": int(b.get("bReliable", 0)),
                               "pme": int(b.get("bHasPackageMapExports", 0)),
                               "close": int(b.get("bClose", 0))})
        # Keep only the first complete OPEN that actually carries the markers --
        # that is the one bunch whose whole job here is the export chain.
        picked = None
        for g in groups:
            found = [s for s in strings_in(g["bits"])
                     if any(m in s for m in MARKERS)]
            if g["open"] and g["pme"] and found:
                picked = (g, found)
                break
        print(f"\n=== ch{ch}: {len(raw[ch])} bunches -> {len(groups)} complete")
        if not picked:
            print("  no complete OPEN carrying capture-point exports")
            continue
        g, found = picked
        print(f"  picked pkt{g['pkt']} frags={g['frags']} bits={len(g['bits'])} "
              f"open={g['open']} pme={g['pme']}")
        print(f"  exports: {sorted(set(found))}")
        out.append({
            "chIndex": ch,
            "chType": 2,
            "bits": len(g["bits"]),
            "payload": g["bits"],
            "bOpen": g["open"],
            "bClose": g["close"],
            "bReliable": g["reliable"],
            "bPartial": 0,
            "bPartialInitial": 0,
            "bPartialFinal": 0,
            "bHasPackageMapExports": g["pme"],
            "bHasMustBeMappedGUIDs": 0,
            "_pkt": g["pkt"],
            "_exports": sorted(set(found)),
        })

    if args.write:
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(out, fh)
        digest = hashlib.sha256(
            json.dumps(out, sort_keys=True).encode("utf-8")).hexdigest()
        print(f"\nwrote {OUT}  ({len(out)} bunches)  sha256={digest[:16]}")
    else:
        print("\n(report only; pass --write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
