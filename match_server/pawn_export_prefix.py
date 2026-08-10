#!/usr/bin/env python3
"""WW3_PAWN_EXPORT_PREFIX — pre-register the pawn open's static NetGUID chain early.

Reconciling the two-agent consult (`live_log/agent_runs/LATEST_SYNTHESIS.md`) against
`docs/M4_Possession_Findings.md` fact #1: `bHasMustBeMappedGUIDs` is genuinely **0** on the
real wire for the pawn open bunch (src=10) — that part of the ground-truth is not in
question and this module does NOT touch it (the pawn open bytes stay byte-identical).

What the agents actually proposed only makes sense as a *separate* bunch: the pawn open's
own PackageMap export table (`_dump_pawn_export_paths.py`) starts with two static, path-
resolvable top-level entries —

    NetGUID 21  (Default__BP_PlayerPawn_01_C, outer=23 the BP package) — the archetype
    NetGUID  5  (PersistentLevel, outer chain 9->7->5) — the spawn level

— followed by six dynamic subobject entries (outer=9372, the pawn itself, which does not
exist yet at export time). Only the first two are resolvable *before* the pawn exists, so
only those two are candidates for early registration.

Sending them standalone on ch3 before it opens is not legal UE4 framing (a channel's first
bunch must carry bOpen=1), but the real capture already proves exports-on-an-open-channel
is normal: `ownership_bootstrap.json`'s src=12 is a non-open, `bHasPackageMapExports=1`
bunch on ch2 (the PlayerController channel, opened long before). ch2 is guaranteed open by
the time the ownership bootstrap reaches the pawn (src=10 sits in the middle of the
capture-ordered PC traffic), so this module re-emits the archetype+level export chain,
byte-identical to the real open bunch, as a synthetic non-open ch2 bunch immediately before
it. The capture-faithful pawn open bunch itself is never modified.

Default OFF (`WW3_PAWN_EXPORT_PREFIX=0`). Rollback: unset/0, no other behavior changes.
"""
from __future__ import annotations

import os

from netguid import GuidReader, PackageMap

DEFAULT_STATIC_EXPORTS = 2   # archetype (guid 21, chain 23->21) + level (guid 5, chain 9->7->5)


def build_pawn_export_prefix_bits(open_bits: list[int], n_static_exports: int = DEFAULT_STATIC_EXPORTS):
    """Slice the first `n_static_exports` top-level PackageMap export entries out of a
    pawn-open bunch's own payload bits and re-header them as a standalone export block.

    Returns a list of 0/1 ints (a self-contained `ReceiveNetGUIDBunch` payload: 1 bit
    `bHasRepLayoutExport=0` + i32 count + the raw, untouched export bytes for those first
    N top-level calls), or None if `open_bits` doesn't look like an export-bearing bunch
    with at least that many top-level entries.
    """
    if not open_bits:
        return None
    r = GuidReader(open_bits, 0)
    has_rep_layout = r.bit()
    if has_rep_layout:
        return None
    num = r.i32()
    if num is None or num < n_static_exports:
        return None
    header_end = r.pos
    pm = PackageMap()
    scratch: list = []
    try:
        for _ in range(n_static_exports):
            pm.load_object(r, 0, scratch)
    except IndexError:
        return None
    body = open_bits[header_end:r.pos]
    header = [0] + [(n_static_exports >> i) & 1 for i in range(32)]
    return header + body


def find_pawn_open_index(specs: list[dict]):
    """Index of the pawn ch3 open bunch (bOpen=1) in a bootstrap spec list, or None."""
    for i, b in enumerate(specs):
        if int(b.get("chIndex", -1)) == 3 and b.get("bOpen"):
            return i
    return None


def build_pawn_export_prefix_spec(pawn_open_spec: dict, carrier_ch_index: int = 2,
                                   n_static_exports: int = DEFAULT_STATIC_EXPORTS):
    """Build the synthetic bootstrap spec dict for the export-prefix bunch, or None if the
    pawn open spec has no export table (or fewer than `n_static_exports` entries)."""
    payload = pawn_open_spec.get("payload")
    if not payload or not pawn_open_spec.get("bHasPackageMapExports"):
        return None
    open_bits = [int(c) for c in payload]
    prefix_bits = build_pawn_export_prefix_bits(open_bits, n_static_exports)
    if not prefix_bits:
        return None
    return {
        "chIndex": carrier_ch_index,
        "bOpen": 0,
        "bClose": 0,
        "bReliable": 1,
        "bHasPackageMapExports": 1,
        "bHasMustBeMappedGUIDs": 0,
        "bPartial": 0,
        "bPartialInitial": 0,
        "bPartialFinal": 0,
        "bits": len(prefix_bits),
        "payload": "".join(str(b) for b in prefix_bits),
        "_src_idx": 9998,
        "_pawn_export_prefix": 1,
    }


def maybe_insert_pawn_export_prefix(specs: list[dict]) -> list[dict]:
    """If `WW3_PAWN_EXPORT_PREFIX=1`, insert the export-prefix bunch right before the pawn
    ch3 open in `specs` (in place) and return it; otherwise return `specs` unchanged."""
    if os.environ.get("WW3_PAWN_EXPORT_PREFIX", "0") != "1":
        return specs
    idx = find_pawn_open_index(specs)
    if idx is None:
        print("[pawn-export-prefix] WW3_PAWN_EXPORT_PREFIX=1 but no pawn ch3 open found — skipped")
        return specs
    try:
        n = int(os.environ.get("WW3_PAWN_EXPORT_PREFIX_N", str(DEFAULT_STATIC_EXPORTS)))
    except ValueError:
        n = DEFAULT_STATIC_EXPORTS
    carrier = int(os.environ.get("WW3_PAWN_EXPORT_PREFIX_CH", "2"))
    prefix = build_pawn_export_prefix_spec(specs[idx], carrier_ch_index=carrier, n_static_exports=n)
    if prefix is None:
        print("[pawn-export-prefix] WW3_PAWN_EXPORT_PREFIX=1 but export slice failed — skipped")
        return specs
    specs.insert(idx, prefix)
    print(f"[pawn-export-prefix] inserted {prefix['bits']}-bit export prefix "
          f"({n} static NetGUID chain(s): archetype+level) on ch{carrier} before pawn ch3 open")
    return specs


if __name__ == "__main__":
    import json
    from pathlib import Path

    here = Path(__file__).resolve().parent
    stream = json.loads((here / "real_replay_stream.json").read_text(encoding="utf-8"))
    open_spec = stream[10]
    prefix = build_pawn_export_prefix_spec(open_spec)
    assert prefix is not None, "expected a prefix from the real pawn open bunch"
    bits = [int(c) for c in prefix["payload"]]
    pm = PackageMap()
    res = pm.read_export_bunch(bits)
    assert res["num"] == DEFAULT_STATIC_EXPORTS
    guids = {e["netguid"] for e in res["exports"]}
    assert {21, 5, 9, 7, 23}.issubset(guids), guids
    assert res["reader"].pos == len(bits), "prefix should be fully consumed, no leftover bits"
    print(f"[OK] pawn_export_prefix: {prefix['bits']} bits, exports={res['num']}, "
          f"guids={sorted(guids)}")
