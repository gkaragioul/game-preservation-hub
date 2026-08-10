#!/usr/bin/env python3
"""Recover the capture's CapturePoint actor channels from the raw pcap.

`real_replay_stream.json` holds only the *partial-initial* bunch of each capture
point channel -- the structural sanitiser dropped the continuation fragments, the
same way it dropped ch3 after the pawn's OPEN.  A partial-initial with no
continuation is not replayable: the client would sit in reassembly forever.

The live client shows why this matters.  It has 3 local `AWW3CapturePoint`
actors from the level, but their replicated state never arrives, so the deploy
screen has no active capture point to offer, the spawn list renders empty and
DEPLOY reads NOT READY.

    src 180 -> ch 83  WW3_Gobi_New_P.PersistentLevel.WW3TdmCapturePoint_1
    src 354 -> ch 84  WW3_Gobi_New_P.PersistentLevel.WW3TdmCapturePoint2

This walks the whole capture, collects every bunch on those channels in wire
order, and writes them to `capturepoint_stream.json` in the same schema
`build_replay_bunch` already consumes.  Read-only with respect to the existing
streams: nothing else is touched.

Usage:
    python match_server/_extract_capturepoints.py            # report only
    python match_server/_extract_capturepoints.py --write
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "match_analysis"))

import control_channel as cc  # noqa: E402
from pcap_tools import parse_pcap  # noqa: E402

# The capture's dedicated server, same anchors `_ground_truth_pawn_ch3.py` uses.
SERVER_IP, SERVER_PORT = "213.183.62.18", 7868

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PCAP = os.path.join(ROOT, "captures", "24July26", "W3_match_full_2.pcapng")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "capturepoint_stream.json")
CHANNELS = (83, 84)


def bunch_payload_bits(b):
    r = b["reader"]
    return [r.read_bit() for _ in range(b["payloadBits"])] if b["payloadBits"] else []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--pcap", default=PCAP)
    args = ap.parse_args()

    print(f"Loading {args.pcap} ...")
    pk = parse_pcap(args.pcap)
    s2c = [pl for ts, src, sp, dst, dp, pl in pk
           if src == SERVER_IP and sp == SERVER_PORT]
    print(f"  {len(pk)} packets, {len(s2c)} S->C")

    raw = {ch: [] for ch in CHANNELS}
    for pkt_idx, data in enumerate(s2c):
        try:
            pkt = cc.read_packet(data)
        except Exception:
            continue
        if pkt.get("is_handshake") or pkt.get("truncated"):
            continue
        for b in pkt.get("bunches", []) or []:
            ch = int(b.get("chIndex", -1))
            if ch in raw:
                raw[ch].append((pkt_idx, b, bunch_payload_bits(b)))

    # Reassemble partial runs into whole bunches.  A fresh bPartialInitial resets
    # the accumulator, which is what discards ch84's superseded 1113-bit open at
    # pkt 280 -- the same dangling fragment that is all `real_replay_stream.json`
    # kept of these channels.
    out = []
    for ch in CHANNELS:
        groups, cur = [], None
        for pkt_idx, b, bits in raw[ch]:
            if b.get("bPartial"):
                if b.get("bPartialInitial"):
                    # A dangling partial-initial (one that never gets its
                    # bPartialFinal) is NOT junk here: on ch83/ch84 it is the
                    # bunch that carries the capture point's NetGUID identity
                    # export -- the full outer chain
                    #   /Game/Maps/Main/Dunhuang_v3/WW3_Gobi_New_P ->
                    #   WW3_Gobi_New_P -> PersistentLevel -> WW3TdmCapturePoint2
                    # which is what makes the actor RESOLVABLE to the client.
                    # The later complete open at pkt 370 exports only
                    # `WW3CapturePointMarker`.  Dropping these as "superseded"
                    # is what left our client with capture points it could not
                    # name, and therefore could not offer as spawns.
                    if cur is not None and cur["pme"] and cur["frags"] == 1:
                        cur["dangling_export"] = True
                        groups.append(cur)
                    cur = {"pkt": pkt_idx, "bits": list(bits), "frags": 1,
                           "open": int(b.get("bOpen", 0)),
                           "reliable": int(b.get("bReliable", 0)),
                           "pme": int(b.get("bHasPackageMapExports", 0)),
                           "close": int(b.get("bClose", 0))}
                elif cur is not None:
                    cur["bits"].extend(bits)
                    cur["frags"] += 1
                    if b.get("bPartialFinal"):
                        groups.append(cur)
                        cur = None
            else:
                groups.append({"pkt": pkt_idx, "bits": list(bits), "frags": 1,
                               "open": int(b.get("bOpen", 0)),
                               "reliable": int(b.get("bReliable", 0)),
                               "pme": int(b.get("bHasPackageMapExports", 0)),
                               "close": int(b.get("bClose", 0))})
        print(f"\n=== channel {ch}: {len(raw[ch])} bunches -> "
              f"{len(groups)} whole bunches (dangling: {'yes' if cur else 'no'}) ===")
        for g in groups[:6]:
            print(f"  pkt {g['pkt']:6d} frags={g['frags']} bits={len(g['bits']):5d} "
                  f"open={g['open']} reliable={g['reliable']} pme={g['pme']}")
        if len(groups) > 6:
            print(f"  ... {len(groups) - 6} more")
        # A channel index is reused: ch83/ch84 are re-opened at pkt 11174 for
        # *different* actors (netguid 18056/18060, dynamic, with world locations)
        # rather than the static capture points (netguid 113/109, no location).
        # Tag every group with the open it belongs to so a replay cannot apply a
        # later actor's property updates to the earlier one.
        actor_seq = -1
        for g in groups:
            # A dangling identity-export bunch belongs to the SAME actor as the
            # open that follows it -- it is that actor's NetGUID->path export.
            # Incrementing on it would orphan the real open and every update
            # behind a later sequence number.
            if g["open"] and not g.get("dangling_export"):
                actor_seq += 1
            g["actor_seq"] = max(actor_seq, 0)
        for gi, g in enumerate(groups):
            payload = "".join("1" if x else "0" for x in g["bits"])
            out.append({
                "_actor_seq": g["actor_seq"],
                "_dangling_export": bool(g.get("dangling_export")),
                "chIndex": ch,
                "chType": 2,
                "bits": len(payload),
                "payload": payload,
                "bOpen": g["open"],
                "bClose": g["close"],
                "bReliable": g["reliable"],
                "bPartial": 0,
                "bPartialInitial": 0,
                "bPartialFinal": 0,
                "bHasPackageMapExports": g["pme"],
                "bHasMustBeMappedGUIDs": 0,
                "_pkt": g["pkt"],
                "_group": gi,
            })

    if args.write:
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(out, fh)
        digest = hashlib.sha256(
            json.dumps(out, sort_keys=True).encode("utf-8")).hexdigest()
        print(f"\nwrote {OUT}  ({len(out)} bunches)  sha256={digest[:16]}")
    else:
        print("\n(report only; pass --write to emit capturepoint_stream.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
