#!/usr/bin/env python3
"""Tests for WW3_WORLD_FILL — replaying the capture's pre-deploy world.

The curated ownership slice opens 16 actor channels.  The working server had 108
open (ch2..ch110) before the client reported `Server_OnMapOpened`, so the live
client's deploy map has no capture points, bases or spawn points to display and
closes itself immediately (observed: five `Server_OnMapClosed`, never one
`Server_OnMapOpened`).  World fill adds the missing channels, bit-exactly and in
capture order, without touching the local player's own channels.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_ownership_bootstrap as bob  # noqa: E402

STREAM = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
# Every actor channel the working server had opened by the time the client sent
# Server_OnMapOpened (stream index 1050).
CAPTURE_PRE_DEPLOY_CHANNELS = {
    e["chIndex"] for i, e in enumerate(STREAM) if e["bOpen"] and i <= 1050
}


def _build(**env):
    for k in ("WW3_WORLD_FILL", "WW3_INV_ATTACH", "WW3_BOOTSTRAP"):
        os.environ.pop(k, None)
    os.environ.update({k: str(v) for k, v in env.items()})
    return bob.write_bootstrap("ownership")


def _opens(boot):
    return [b for b in boot if b.get("bOpen")]


def test_world_fill_is_off_by_default():
    boot = _build(WW3_INV_ATTACH=1)
    channels = {b["chIndex"] for b in _opens(boot)}
    assert not any(b.get("_world_fill") for b in boot)
    assert channels == {2, 3, 4, 5, 7, 53, 54, 55, 56, 57, 58, 59, 85, 86, 87, 88}
    print(f"[ok] default bootstrap still opens exactly {len(channels)} channels")


def test_world_fill_completes_the_capture_pre_deploy_world():
    baseline = {b["chIndex"] for b in _opens(_build(WW3_INV_ATTACH=1))}
    boot = _build(WW3_INV_ATTACH=1, WW3_WORLD_FILL=1)
    opens = _opens(boot)
    channels = {b["chIndex"] for b in opens}

    assert channels == CAPTURE_PRE_DEPLOY_CHANNELS, (
        sorted(CAPTURE_PRE_DEPLOY_CHANNELS - channels),
        sorted(channels - CAPTURE_PRE_DEPLOY_CHANNELS))
    assert channels > baseline
    print(f"[ok] world fill opens {len(channels)} channels (was {len(baseline)})")


def test_world_fill_never_reopens_a_channel_or_touches_local_ones():
    boot = _build(WW3_INV_ATTACH=1, WW3_WORLD_FILL=1)
    seen: dict[int, int] = {}
    for b in _opens(boot):
        seen[b["chIndex"]] = seen.get(b["chIndex"], 0) + 1
    duplicates = {ch: n for ch, n in seen.items() if n > 1}
    assert not duplicates, f"duplicate channel opens would make UE close them: {duplicates}"

    added = [b for b in boot if b.get("_world_fill")]
    assert added, "world fill produced nothing"
    local = bob.WORLD_FILL_LOCAL_CHANNELS
    assert not [b for b in added if b["chIndex"] in local], (
        "world fill must not race the curated local-player channels")
    print(f"[ok] {len(added)} world bunches, no duplicate opens, no local channels")


def test_world_fill_is_bit_exact_and_in_capture_order():
    boot = _build(WW3_INV_ATTACH=1, WW3_WORLD_FILL=1)
    added = [b for b in boot if b.get("_world_fill")]
    indices = [b["_src_idx"] for b in added]
    assert indices == sorted(indices), "world fill must preserve capture order"
    for b in added:
        source = STREAM[b["_src_idx"]]
        assert b["payload"] == source["payload"]
        assert b["bits"] == source["bits"]
        assert b["chIndex"] == source["chIndex"]
        assert b["bReliable"] == source["bReliable"]
    print(f"[ok] {len(added)} world bunches are bit-exact and ordered")


def test_partial_chains_are_never_cut():
    boot = _build(WW3_INV_ATTACH=1, WW3_WORLD_FILL=1)
    present = {b["_src_idx"] for b in boot if b.get("_world_fill")}
    for idx in sorted(present):
        if not STREAM[idx]["bPartialInitial"]:
            continue
        j = idx
        while j < len(STREAM) and not STREAM[j]["bPartialFinal"]:
            j += 1
        missing = [k for k in range(idx, j + 1)
                   if STREAM[k]["chIndex"] not in bob.WORLD_FILL_LOCAL_CHANNELS
                   and k not in present]
        assert not missing, f"partial chain {idx}..{j} is cut: missing {missing}"
    print("[ok] every world-fill partial chain reaches its final bunch")


if __name__ == "__main__":
    try:
        test_world_fill_is_off_by_default()
        test_world_fill_completes_the_capture_pre_deploy_world()
        test_world_fill_never_reopens_a_channel_or_touches_local_ones()
        test_world_fill_is_bit_exact_and_in_capture_order()
        test_partial_chains_are_never_cut()
        print("ALL world fill tests passed")
    finally:
        for _k in ("WW3_WORLD_FILL", "WW3_INV_ATTACH", "WW3_BOOTSTRAP"):
            os.environ.pop(_k, None)
        bob.write_bootstrap("ownership")
