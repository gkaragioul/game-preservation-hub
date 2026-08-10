#!/usr/bin/env python3
"""Tests for WW3_PAWN_EXPORT_PREFIX (pawn_export_prefix.py)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from netguid import PackageMap  # noqa: E402
from pawn_export_prefix import (  # noqa: E402
    build_pawn_export_prefix_bits,
    build_pawn_export_prefix_spec,
    find_pawn_open_index,
    maybe_insert_pawn_export_prefix,
)


def _real_pawn_open_spec():
    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
    return stream[10]


def test_slices_only_static_exports():
    open_spec = _real_pawn_open_spec()
    open_bits = [int(c) for c in open_spec["payload"]]
    prefix_bits = build_pawn_export_prefix_bits(open_bits, n_static_exports=2)
    assert prefix_bits is not None
    pm = PackageMap()
    res = pm.read_export_bunch(prefix_bits)
    assert res["num"] == 2
    guids = {e["netguid"] for e in res["exports"]}
    # Archetype chain (23 -> 21) + level chain (9 -> 7 -> 5). No pawn/subobject GUIDs (9372+).
    assert guids == {5, 7, 9, 21, 23}
    assert res["reader"].pos == len(prefix_bits), "no leftover/unused bits"


def test_rejects_non_export_bunch():
    assert build_pawn_export_prefix_bits([]) is None
    # A bunch with bHasRepLayoutExport=1 (first bit set) is not a plain export block.
    assert build_pawn_export_prefix_bits([1, 0, 0, 0]) is None


def test_build_spec_shape():
    open_spec = _real_pawn_open_spec()
    spec = build_pawn_export_prefix_spec(open_spec, carrier_ch_index=2)
    assert spec is not None
    assert spec["chIndex"] == 2
    assert spec["bOpen"] == 0 and spec["bClose"] == 0
    assert spec["bHasPackageMapExports"] == 1
    assert spec["bHasMustBeMappedGUIDs"] == 0
    assert spec["bits"] == len(spec["payload"])


def test_find_pawn_open_index():
    specs = [{"chIndex": 2, "bOpen": 1}, {"chIndex": 3, "bOpen": 0}, {"chIndex": 3, "bOpen": 1}]
    assert find_pawn_open_index(specs) == 2
    assert find_pawn_open_index([{"chIndex": 2, "bOpen": 1}]) is None


def test_insert_gated_by_env():
    open_spec = _real_pawn_open_spec()
    specs = [{"chIndex": 2, "bOpen": 1, "bits": 1, "payload": "0"}, dict(open_spec)]

    prev = os.environ.pop("WW3_PAWN_EXPORT_PREFIX", None)
    try:
        os.environ["WW3_PAWN_EXPORT_PREFIX"] = "0"
        out = maybe_insert_pawn_export_prefix(list(specs))
        assert len(out) == 2, "default OFF must not change the bootstrap"

        os.environ["WW3_PAWN_EXPORT_PREFIX"] = "1"
        out = maybe_insert_pawn_export_prefix(list(specs))
        assert len(out) == 3
        assert out[1]["_pawn_export_prefix"] == 1
        assert out[1]["chIndex"] == 2
        assert out[2] is specs[1], "the real pawn open bunch must stay untouched"
    finally:
        if prev is None:
            os.environ.pop("WW3_PAWN_EXPORT_PREFIX", None)
        else:
            os.environ["WW3_PAWN_EXPORT_PREFIX"] = prev


if __name__ == "__main__":
    test_slices_only_static_exports()
    print("[ok] export prefix carries only the archetype+level static chain")
    test_rejects_non_export_bunch()
    print("[ok] rejects non-export bunches")
    test_build_spec_shape()
    print("[ok] spec shape (ch2, non-open, EXP, no-MBM)")
    test_find_pawn_open_index()
    print("[ok] find_pawn_open_index")
    test_insert_gated_by_env()
    print("[ok] insertion gated by WW3_PAWN_EXPORT_PREFIX (default off, pawn open untouched)")
    print("ALL pawn_export_prefix tests passed")
