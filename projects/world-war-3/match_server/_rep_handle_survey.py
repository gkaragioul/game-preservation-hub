#!/usr/bin/env python3
r"""Read-only: survey actor RepLayout property handles across every channel in the
capture, and dump the pawn channel's handles bit-exactly.

Why: the pawn (ch3) receives no actor RepLayout at all in its open bunch and only two
19-bit updates in the entire match (src 181/192, both `handle 10` + a 3-bit value). If
`ROLE_AutonomousProxy` is not reaching the client, `UCharacterMovementComponent` never
runs `ReplicateMoveToServer` and ch3 C->S stays empty -- exactly the live symptom. A
handle that appears on the locally-controlled pawn and on no simulated character is a
strong candidate for `RemoteRole`.

  python match_server/_rep_handle_survey.py
"""
from __future__ import annotations

import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from actor_channel import Bits, read_content_blocks, read_new_actor  # noqa: E402
from netguid import GuidReader, PackageMap  # noqa: E402

STREAM = os.path.join(HERE, "real_replay_stream.json")


def groups(stream: list) -> list[tuple[list[int], list[dict]]]:
    out = []
    pending_idx: dict[int, list[int]] = {}
    pending: dict[int, list[dict]] = {}
    for i, sp in enumerate(stream):
        ch = sp["chIndex"]
        if sp.get("bPartial"):
            if sp.get("bPartialInitial"):
                pending[ch], pending_idx[ch] = [sp], [i]
            elif ch in pending:
                pending[ch].append(sp)
                pending_idx[ch].append(i)
            if sp.get("bPartialFinal") and ch in pending:
                out.append((pending_idx.pop(ch), pending.pop(ch)))
        else:
            out.append(([i], [sp]))
    return out


def rep_blocks(idxs: list[int], group: list[dict]):
    bits: list[int] = []
    for sp in group:
        bits.extend(int(c) for c in sp["payload"])
    first = group[0]
    pm = PackageMap()
    pos = 0
    if first.get("bHasPackageMapExports"):
        try:
            pos = pm.read_export_bunch(bits)["reader"].pos
        except Exception:
            return None, []
    arch = None
    if first.get("bOpen"):
        try:
            gr = GuidReader(bits, pos)
            info = read_new_actor(gr, pm)
            pos = gr.pos
            arch = info.get("archetypePath")
        except Exception:
            return None, []
    try:
        return arch, read_content_blocks(Bits(bits, pos), total_bits=len(bits))
    except Exception:
        return arch, []


def parse_rep_stream(payload: list[int]) -> list[tuple[int, list[int]]] | None:
    """packed handle, <unknown-width value>, ... , packed 0. Only decodable when a single
    property is present: handle, then everything up to the packed-0 terminator."""
    r = Bits(payload)
    try:
        h = r.packed()
    except EOFError:
        return None
    if h == 0:
        return []
    rest = r.left()
    if rest < 8:
        return None
    value = [r.b[r.pos + i] for i in range(rest - 8)]
    r.pos += rest - 8
    try:
        term = r.packed()
    except EOFError:
        return None
    if term != 0:
        return None  # more than one property; widths unknown
    return [(h, value)]


def main() -> None:
    stream = json.load(open(STREAM))
    archetypes: dict[int, str] = {}
    per_channel: dict[int, collections.Counter] = collections.defaultdict(collections.Counter)
    single_prop: dict[int, set[int]] = collections.defaultdict(set)

    print("=== pawn channel (ch3) RepLayout, bit-exact ===")
    for idxs, group in groups(stream):
        ch = group[0]["chIndex"]
        arch, blocks = rep_blocks(idxs, group)
        if arch and ch not in archetypes:
            archetypes[ch] = arch
        for b in blocks:
            if not b.get("isActor") or not b.get("hasRepLayout") or b.get("bad"):
                continue
            payload = b.get("payload") or []
            parsed = parse_rep_stream(payload)
            if parsed:
                for h, val in parsed:
                    per_channel[ch][h] += 1
                    single_prop[h].add(ch)
                    if ch == 3:
                        print(f"  src={idxs} handle={h} value_bits={len(val)} "
                              f"bits={''.join(str(x) for x in val)} "
                              f"lsb_first_int={sum(v << i for i, v in enumerate(val))}")
            elif ch == 3:
                r = Bits(payload)
                try:
                    h = r.packed()
                except EOFError:
                    h = None
                print(f"  src={idxs} multi-property block, first handle={h}, "
                      f"payload_bits={len(payload)} (widths unknown)")

    print("\n=== channels carrying each single-property handle ===")
    for h in sorted(single_prop):
        chs = sorted(single_prop[h])
        tag = "  <-- ch3 ONLY" if chs == [3] else ("  (incl ch3)" if 3 in chs else "")
        print(f"  handle {h:4}: {len(chs):3} channels {chs[:14]}{'...' if len(chs) > 14 else ''}{tag}")

    print("\n=== archetypes seen per channel (first 40) ===")
    for ch in sorted(archetypes)[:40]:
        print(f"  ch{ch:4}: {archetypes[ch]}")


if __name__ == "__main__":
    main()
