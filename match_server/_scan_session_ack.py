#!/usr/bin/env python3
"""Scan latest session jsonl for possession RPCs."""
from __future__ import annotations

import glob
import json
import os

files = sorted(
    glob.glob("match_server/live_log/session_*.jsonl"),
    key=os.path.getmtime,
    reverse=True,
)
path = files[0]
print("file", path)
ack = check = restart_s2c = close = 0
samples = []
for line in open(path, encoding="utf-8", errors="replace"):
    try:
        ev = json.loads(line)
    except Exception:
        continue
    blob = line
    if "ServerAcknowledgePossession" in blob or "AcknowledgePossession" in blob:
        ack += 1
        if len(samples) < 8:
            samples.append(("ACK", blob[:400]))
    if "ServerCheckClientPossession" in blob:
        check += 1
        if len(samples) < 8:
            samples.append(("CHECK", blob[:400]))
    if "ClientRestart" in blob:
        restart_s2c += 1
    if "CHANNEL CLOSE" in blob or "bClose" in blob and '"dir": "C->S"' in blob:
        # rough
        pass
print(f"ack_mentions={ack} check_mentions={check}")
for kind, s in samples:
    print(kind, s)
    print("---")
