#!/usr/bin/env python3
"""Read the client's OWN UE log, as uploaded to our hub.

The WW3 client streams its log lines back to the backend over the hub websocket
(`{"context":"debug","method":"log", ...}`) and includes Warning/Error severity —
the exact level at which UE explains why a replicated actor never appeared:

    LogNet: Warning: UActorChannel::ProcessBunch: SerializeNewActor failed to find/spawn actor
    LogNet: Warning: UActorChannel::ProcessQueuedBunches: Queued bunches for longer than...
    LogNetPackageMap: Warning: InternalLoadObject: Unable to resolve object from path
    LogNetPartialBunch: Warning: Corrupt partial bunch...
    LogNetPackageMap: Error: Network checksum mismatch

`mockserver/hub_server.py` records those to match_server/live_log/client_log/ (see
WW3_CLIENT_LOG_CAPTURE). This tool reads the newest capture. Read-only.

    python match_server/watch_client_log.py             # summary of the newest capture
    python match_server/watch_client_log.py --follow    # live tail of net-relevant lines
    python match_server/watch_client_log.py --all       # don't filter
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.environ.get("WW3_CLIENT_LOG_DIR") or os.path.join(HERE, "live_log", "client_log")

# The lines that would actually settle the M4 possession question.
SMOKING_GUNS = re.compile(
    r"SerializeNewActor|QueuedBunches|Queued bunches|Corrupt partial bunch|"
    r"checksum mismatch|Unable to resolve|Unable to read Archetype|"
    r"outdated bunch|Received unreliable bunch before open|"
    r"failed to find/spawn actor|Bunch had error|AcknowledgePossession|ClientRestart",
    re.IGNORECASE)


def newest(suffix: str) -> str | None:
    if not os.path.isdir(LOG_DIR):
        return None
    files = [os.path.join(LOG_DIR, f) for f in os.listdir(LOG_DIR) if f.endswith(suffix)]
    return max(files, key=os.path.getmtime) if files else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--follow", "-f", action="store_true", help="tail the file live")
    ap.add_argument("--all", action="store_true", help="use the unfiltered capture")
    ap.add_argument("--path", help="explicit capture file")
    args = ap.parse_args()

    path = args.path or newest(".log" if args.all else "_net.log")
    if not path:
        print(f"no client log capture in {LOG_DIR}")
        print("The hub records these only while WW3_CLIENT_LOG_CAPTURE != 0 and a client")
        print("is connected to it; restart mockserver/hub_server.py to start capturing.")
        return 1
    print(f"[client-log] {path}")

    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()
        hits = [ln.rstrip() for ln in lines if SMOKING_GUNS.search(ln)]
        print(f"[client-log] {len(lines)} lines, {len(hits)} possession-relevant")
        for ln in hits[-40:]:
            print("  " + ln)
        if not args.follow:
            return 0
        print("[client-log] following (Ctrl-C to stop)...")
        try:
            while True:
                where = fh.tell()
                ln = fh.readline()
                if not ln:
                    time.sleep(0.5)
                    fh.seek(where)
                    continue
                mark = "!!" if SMOKING_GUNS.search(ln) else "  "
                print(mark + " " + ln.rstrip())
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    sys.exit(main())
