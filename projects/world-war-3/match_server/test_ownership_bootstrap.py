#!/usr/bin/env python3
"""Tests for M4 ownership bootstrap slice + ambient queue."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def test_build_ownership_bootstrap():
    subprocess.check_call([sys.executable, str(HERE / "build_ownership_bootstrap.py")], cwd=HERE)
    path = HERE / "ownership_bootstrap.json"
    assert path.is_file(), "ownership_bootstrap.json missing"
    boot = json.loads(path.read_text(encoding="utf-8"))
    assert len(boot) >= 22
    src = {b.get("_src_idx") for b in boot}
    opens = {b["chIndex"] for b in boot if b.get("bOpen")}

    assert 2 in opens, "PC channel open missing"
    assert 3 in opens, "Pawn channel open missing"
    assert 7 in opens, "local PlayerState channel (ch7 / NetGUID 9362) missing"
    assert 6 not in opens, "foreign PlayerState ch6 (NetGUID 516) must not be in bootstrap"
    assert 53 in opens, "GameState channel open missing"
    assert 4 in opens and 5 in opens, "local weapon channel opens missing"

    assert 20 in src and 21 in src, "local PlayerState bunches (src 20–21) missing"
    assert 18 not in src and 19 not in src, "foreign PlayerState (src 18–19) must be excluded"
    assert {14, 15, 16, 17} <= src, "local weapon bunches missing"
    assert {5, 6, 7} <= src, "streaming missing"
    assert {119, 120, 121} <= src, "GameState bunches missing"
    assert {212, 213} <= src, "clothing missing"
    assert {181, 192} <= src, "pawn nudges missing"
    assert 215 in src and 275 in src, "GameState follow-ups missing"

    # PS-early: local PS (20) right after PC open (0–1), before HUD/streaming/pawn.
    order = [b.get("_src_idx") for b in boot]
    assert order.index(0) < order.index(20) < order.index(2), "PS must follow PC open, before HUD"
    assert order.index(20) < order.index(10), "PS must spawn before pawn"
    assert order.index(2) < order.index(5) < order.index(10), "HUD → streaming → pawn"
    assert order.index(7) < order.index(119), "streaming before GameState"
    # src 9 appears twice: once in 2–17, once as post-PS rebind nudge
    idx9 = [i for i, s in enumerate(order) if s == 9]
    assert len(idx9) == 2, f"expected src 9 twice, got {len(idx9)}"
    assert order.index(20) < idx9[1], "resend src 9 must come after PS"

    print(f"[ok] ownership bootstrap {len(boot)} bunches opens={sorted(opens)}")


def test_ambient_appended_after_ownership():
    sys.path.insert(0, str(HERE))
    import server as srv

    class FakeConn:
        pass

    conn = FakeConn()
    os.environ["WW3_BOOTSTRAP"] = "ownership"
    os.environ["WW3_AMBIENT_LIMIT"] = "40"
    os.environ.pop("WW3_NO_WORLD_REPLAY", None)

    ms = srv.MatchServer.__new__(srv.MatchServer)
    ms.queue_world_after_pc(conn, str(HERE), skip=2)
    assert hasattr(conn, "replay_queue")
    ambient = [b for b in conn.replay_queue if b.get("_ambient")]
    owned = [b for b in conn.replay_queue if not b.get("_ambient")]
    assert len(owned) >= 15, f"expected ownership rest, got {len(owned)}"
    assert len(ambient) > 0, "ambient window missing"
    assert any(b.get("_src_idx") == 18 for b in ambient), "ambient should include foreign PS 18"
    assert not any(b.get("_src_idx") in (20, 21, 119, 120, 121) for b in ambient), \
        "ambient must not re-send ownership GameState/local PS"
    print(f"[ok] ambient appended: ownership_rest={len(owned)} ambient={len(ambient)}")


if __name__ == "__main__":
    test_build_ownership_bootstrap()
    test_ambient_appended_after_ownership()
    print("ALL ownership bootstrap tests passed")
