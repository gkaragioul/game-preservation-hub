#!/usr/bin/env python3
"""Scan the LIVE session jsonl for C->S bunches, tally by chIndex, and dump any
pawn(3)/weapon(4,5) C->S bunch found (the exact signal the task cares about)."""
import json
import sys
import binascii
import collections

sys.path.insert(0, "match_server")
import control_channel as cc

path = sys.argv[1] if len(sys.argv) > 1 else "match_server/live_log/session_20260805_181405.jsonl"

counts = collections.Counter()
pawn_weapon_hits = []
ack_possession_like = []
total_c2s = 0
parse_fail = 0

with open(path, encoding="utf-8", errors="replace") as f:
    for line_no, line in enumerate(f):
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("dir") != "C->S":
            continue
        total_c2s += 1
        try:
            data = binascii.unhexlify(d["hex"])
        except Exception:
            continue
        try:
            p = cc.read_packet(data)
        except Exception:
            parse_fail += 1
            continue
        if p.get("is_handshake"):
            continue
        for b in p.get("bunches", []):
            ch = b["chIndex"]
            counts[ch] += 1
            if ch in (3, 4, 5):
                pawn_weapon_hits.append((line_no, d["t"], ch, b, d["hex"]))

print(f"total C->S datagrams: {total_c2s}  parse_fail: {parse_fail}")
print("chIndex histogram (C->S):")
for ch, c in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"  ch={ch:4d}  n={c}")

print()
print(f"pawn/weapon (ch 3/4/5) C->S bunches found: {len(pawn_weapon_hits)}")
for ln, t, ch, b, hexs in pawn_weapon_hits[:20]:
    print(f"  line={ln} t={t} ch={ch} bOpen={b.get('bOpen')} bClose={b.get('bClose')} "
          f"bits={b.get('bunchDataBits')} hex_len={len(hexs)//2}")
