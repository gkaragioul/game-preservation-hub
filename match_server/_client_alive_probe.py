#!/usr/bin/env python3
r"""How long did the client keep talking after its pawn channel opened?

The measurement that reframed turn 5. Every experiment this project runs fires
*after* possession, so the only question that matters before reading any oracle
is: was the client still processing when the experiment landed?

Measured over six sessions, the answer was consistently **no**. The client's
network thread stops permanently 2.7-3.8 s after the ch3 pawn channel opens --
with `WW3_TEAM_ACTION_REPLICATOR` on or off, with the action probe on or off --
while exactly one thread keeps burning ~99% of a core (`_thread_rip.py`). So the
sync-checklist / team-graph readings taken minutes later in turns 3 and 4 were
all taken from a client whose netcode had already stopped.

This turns that into a one-command regression check: point it at the packet log
and it prints the pawn-open time, the client's last inbound packet, and the
survival window. Use it as the FIRST gate on every future live run -- if the
window is ~3 s, nothing downstream of it means anything.

Usage:
    python match_server/_client_alive_probe.py                  # newest session
    python match_server/_client_alive_probe.py --all            # every session
    python match_server/_client_alive_probe.py live_log/session_X.jsonl
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import control_channel as cc  # noqa: E402

# Below this, the client died during the bootstrap and no later oracle is valid.
HEALTHY_WINDOW_S = 10.0


def measure(path: str) -> dict:
    first_c2s = None
    last_c2s = 0.0
    last_s2c = 0.0
    n_c2s = 0
    pawn_open = None
    for line in open(path, encoding="utf-8"):
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec["dir"] == "C->S":
            if first_c2s is None:
                first_c2s = rec["t"]
            last_c2s = max(last_c2s, rec["t"])
            n_c2s += 1
            continue
        last_s2c = max(last_s2c, rec["t"])
        if pawn_open is not None:
            continue
        data = bytes.fromhex(rec["hex"])
        if not data or (data[0] & 1) == 1:
            continue
        try:
            pkt = cc.read_packet(data)
        except Exception:
            continue
        for b in pkt.get("bunches", []):
            if b.get("chIndex") == 3 and b.get("bOpen"):
                pawn_open = rec["t"]
                break
    return {
        "path": path,
        "c2s_packets": n_c2s,
        "pawn_open": pawn_open,
        "last_c2s": last_c2s,
        "last_s2c": last_s2c,
        "alive_after_pawn": (last_c2s - pawn_open) if pawn_open else None,
        "trailing_silence": last_s2c - last_c2s,
    }


def report(m: dict) -> bool:
    name = os.path.basename(m["path"])
    if m["pawn_open"] is None:
        print(f"{name:<34} C->S={m['c2s_packets']:6d}  no ch3 pawn open -- "
              f"the bootstrap never got that far")
        return False
    window = m["alive_after_pawn"]
    verdict = "OK  " if window >= HEALTHY_WINDOW_S else "DEAD"
    print(f"{name:<34} C->S={m['c2s_packets']:6d}  pawnOpen@{m['pawn_open']:8.3f}  "
          f"lastC2S@{m['last_c2s']:8.3f}  alive_after_pawn={window:7.3f}s  "
          f"silence={m['trailing_silence']:7.1f}s  [{verdict}]")
    return window >= HEALTHY_WINDOW_S


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("session", nargs="?", default=None)
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    if args.session:
        paths = [args.session]
    else:
        found = sorted(glob.glob(str(HERE / "live_log" / "session_*.jsonl")),
                       key=os.path.getmtime)
        if not found:
            print("no session logs found")
            return 2
        paths = found if args.all else found[-1:]

    ok = False
    for p in paths:
        ok = report(measure(p)) or ok
    if not args.all and not ok:
        print(f"\nThe client stopped transmitting within {HEALTHY_WINDOW_S:.0f}s of "
              f"possession. Any checklist / team-graph / ack reading taken after "
              f"that point describes a hung client, not a failed hypothesis.\n"
              f"Next: python match_server/_thread_rip.py --stack")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
