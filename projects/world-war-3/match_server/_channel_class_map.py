#!/usr/bin/env python3
"""Map every capture actor channel to the class it opens, by pulling the NetGUID
export path strings straight out of the bunch bits.

The replay stream stores payloads as '0'/'1' bit strings.  UE serialises FString
bytes LSB-first and contiguously, so ASCII survives at a fixed bit phase - no
full bunch parse is needed to recover the export paths.

This exists because the synchronization work needed an inventory of *which*
actors the working server opened, not just how many: the client's PlayerState
checklist item turned out to depend on `AWW3PlayerState::CurrentSquad`, which is
built from `AWW3TeamManager` / `AWW3ActionReplicator` traffic.

Usage:
    python match_server/_channel_class_map.py
    python match_server/_channel_class_map.py --grep Squad
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
STREAM = HERE / "real_replay_stream.json"
ASCII_RUN = re.compile(rb"[ -~]{4,}")


def strings_in(bits: str) -> list[str]:
    """Every printable run in the payload, across all eight bit phases."""
    out: list[str] = []
    seen: set[str] = set()
    for phase in range(8):
        s = bits[phase:]
        by = bytearray()
        for i in range(0, len(s) - 7, 8):
            by.append(int(s[i:i + 8][::-1], 2))
        for m in ASCII_RUN.finditer(bytes(by)):
            t = m.group().decode("ascii")
            if t not in seen:
                seen.add(t)
                out.append(t)
    return out


def classify(strings: list[str]) -> str:
    for t in strings:
        if t.startswith("Default__"):
            return t[len("Default__"):]
    for t in strings:
        if t.startswith("BP_") or t.startswith("WW3"):
            return t
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grep", default="")
    ap.add_argument("--stream", default=str(STREAM))
    args = ap.parse_args()

    stream = json.loads(Path(args.stream).read_text())
    rows = []
    for idx, e in enumerate(stream):
        if not e.get("bOpen") or e.get("chType") != 2:
            continue
        strs = strings_in(e["payload"])
        rows.append((idx, e["chIndex"], classify(strs), strs))

    print(f"{len(rows)} actor-channel opens in {args.stream}\n")
    print(f"{'src':>5} {'ch':>4}  class")
    for idx, ch, cls, strs in rows:
        if args.grep and not any(args.grep.lower() in s.lower() for s in strs):
            continue
        extra = [s for s in strs if s != cls][:3]
        print(f"{idx:>5} {ch:>4}  {cls or '?':<42} {extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
