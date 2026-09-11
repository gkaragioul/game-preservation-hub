#!/usr/bin/env python3
"""Tests for post-NotifyLoadedWorld PS rebind helpers."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from ps_rebind import (  # noqa: E402
    build_pc_rep_layout_bunch_bits,
    extract_pc_rep_layout_bits,
    payload_has_loaded_world_marker,
    rebind_src_indices,
)
from actor_channel import Bits, read_content_blocks  # noqa: E402
from ps_identity import bits_to_bytes  # noqa: E402


def test_payload_marker():
    assert not payload_has_loaded_world_marker([0] * 32)
    raw = b"xxx/Game/Maps/Main/Dunhuang_v3/WW3_Gobi_New_Pyyy"
    bits = []
    for byte in raw:
        for i in range(8):
            bits.append((byte >> i) & 1)
    assert payload_has_loaded_world_marker(bits)


def test_extract_pc_rep():
    rep = extract_pc_rep_layout_bits()
    assert len(rep) == 819


def test_build_pc_rep_bunch():
    bits = build_pc_rep_layout_bunch_bits()
    blocks = read_content_blocks(Bits(bits))
    assert len(blocks) == 1
    assert blocks[0].get("isActor") and blocks[0].get("hasRepLayout")
    assert blocks[0]["payloadBits"] == 819


def test_rebind_indices():
    assert rebind_src_indices() == [20, 21, 3, 4, 9]


def test_late_rebind_is_opt_in(monkeypatch):
    """The post-clothing experiment must not mutate default live runs."""
    import server
    monkeypatch.delenv("WW3_LATE_PS_REBIND_AFTER_CLOTHING", raising=False)
    ms = server.MatchServer()
    conn = type("Conn", (), {
        "_late_ps_rebind_pending": True,
        "_ownership_done": True,
        "_late_ps_rebind_done": False,
    })()
    assert ms.maybe_send_late_ps_rebind(None, None, conn) is False
    assert not getattr(conn, "_late_ps_rebind_done", False)


def test_late_rebind_source_allowlist(monkeypatch):
    import server
    monkeypatch.setenv("WW3_LATE_PS_REBIND_AFTER_CLOTHING", "1")
    monkeypatch.setenv("WW3_LATE_PS_REBIND_SOURCES", "20,21,999")
    ms = server.MatchServer()
    conn = type("Conn", (), {
        "_late_ps_rebind_pending": True,
        "_ownership_done": True,
        "_late_ps_rebind_done": False,
    })()
    assert ms.maybe_send_late_ps_rebind(None, None, conn) is False
    assert not getattr(conn, "_late_ps_rebind_done", False)


if __name__ == "__main__":
    test_payload_marker()
    print("[ok] map-path marker")
    test_extract_pc_rep()
    print("[ok] extract PC RepLayout 819")
    test_build_pc_rep_bunch()
    print("[ok] framed PC RepLayout bunch")
    test_rebind_indices()
    # Keep the opt-in guard test runnable without pytest's monkeypatch fixture.
    import os
    old = os.environ.pop("WW3_LATE_PS_REBIND_AFTER_CLOTHING", None)
    try:
        import server
        ms = server.MatchServer()
        conn = type("Conn", (), {"_late_ps_rebind_pending": True,
                                  "_ownership_done": True,
                                  "_late_ps_rebind_done": False})()
        assert ms.maybe_send_late_ps_rebind(None, None, conn) is False
    finally:
        if old is not None:
            os.environ["WW3_LATE_PS_REBIND_AFTER_CLOTHING"] = old
    print("[ok] rebind indices")
    print("ALL ps_rebind tests passed")
