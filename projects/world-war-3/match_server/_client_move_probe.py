#!/usr/bin/env python3
"""Decode the client's pawn-channel (ch3) bunches from a live session jsonl.

The client only opens this traffic once it actually possesses a character, so the
payloads are the ground truth for "is the player moving?" even while a UI layer
still covers the viewport.

Usage:
    python match_server/_client_move_probe.py live_log/session_*.jsonl [--tail N]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "match_analysis"))

import control_channel as cc  # noqa: E402
from ps_rebind import bunch_payload_bits  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--ch", type=int, default=3)
    ap.add_argument("--tail", type=int, default=40)
    ap.add_argument("--since", type=float, default=0.0)
    args = ap.parse_args()

    rows: list[tuple[float, str]] = []
    sizes: Counter = Counter()
    for line in Path(args.jsonl).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("dir") != "C->S" or float(rec.get("t", 0)) < args.since:
            continue
        try:
            p = cc.read_packet(bytes.fromhex(rec["hex"]))
        except Exception:
            continue
        if p.get("is_handshake"):
            continue
        for b in p.get("bunches", []):
            if b.get("chIndex") != args.ch:
                continue
            try:
                bits = "".join(str(x) for x in bunch_payload_bits(b))
            except Exception:
                continue
            sizes[len(bits)] += 1
            rows.append((float(rec["t"]), bits))

    print(f"# ch{args.ch} C->S bunches: {len(rows)}  sizes={dict(sizes)}")
    if not rows:
        return 0
    print(f"# window t={rows[0][0]:.1f}s .. {rows[-1][0]:.1f}s")
    distinct = len({b for _t, b in rows})
    print(f"# distinct payloads: {distinct}/{len(rows)}")
    prev = None
    changes = 0
    for _t, bits in rows:
        if prev is not None and bits != prev:
            changes += 1
        prev = bits
    print(f"# consecutive changes: {changes}")
    for t, bits in rows[-args.tail:]:
        print(f"{t:10.3f}  {bits[:96]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
