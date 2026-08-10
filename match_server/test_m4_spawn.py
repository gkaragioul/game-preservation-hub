#!/usr/bin/env python3
"""M4 unit tests: rotation codec + capture-faithful PC spawn rebuild."""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from actor_channel import (
    Bits,
    read_new_actor,
    read_content_blocks,
    write_new_actor,
    write_export_block,
    write_content_block,
    write_subobject_content_block,
    write_rotator_net,
    read_rotator_net,
)
from netguid import GuidWriter, PackageMap, GuidReader


def test_rotator_roundtrip():
    w = GuidWriter()
    write_rotator_net(w, (1.40625, 90.0, 0.0))
    bits = [(w.get_bytes()[i >> 3] >> (i & 7)) & 1 for i in range(w.num)]
    assert len(bits) == 27
    deg, comps = read_rotator_net(Bits(bits))
    assert comps == [2, 128, 0]
    assert abs(deg[1] - 90.0) < 1e-6
    print("[ok] rotator round-trip 27 bits -> yaw 90")


def test_capture_pc_spawn_complete():
    specs = json.load(open(os.path.join(HERE, "real_spawn_bunches.json")))
    bits = []
    for sp in specs:
        bits.extend(int(c) for c in sp["payload"])
    pm = PackageMap()
    gr = GuidReader(bits)
    gr.bit()
    n = gr.i32()
    for _ in range(n):
        pm.load_object(gr, exporting=True)
    assert gr.pos == 3257
    r = Bits(bits, gr.pos)
    info = read_new_actor(r, pm)
    assert not info.get("incomplete"), info
    assert info["has_rotation"]
    assert abs(info["rotation"][1] - 90.0) < 1e-6
    blocks = read_content_blocks(r)
    assert r.left() == 0
    assert len(blocks) == 5
    assert blocks[0]["isActor"] and blocks[0]["hasRepLayout"] and blocks[0]["payloadBits"] == 819
    for i, gid in enumerate((9364, 9366, 9368, 9370)):
        assert blocks[i + 1]["subNetGUID"] == gid
        assert blocks[i + 1]["payloadBits"] == 0
    print("[ok] capture PC spawn fully parsed (rotation + 5 content blocks)")


def test_generated_body_matches_capture():
    specs = json.load(open(os.path.join(HERE, "real_spawn_bunches.json")))
    bits = []
    for sp in specs:
        bits.extend(int(c) for c in sp["payload"])
    pm = PackageMap()
    gr = GuidReader(bits)
    gr.bit()
    n = gr.i32()
    for _ in range(n):
        pm.load_object(gr, exporting=True)
    r = Bits(bits, gr.pos)
    info = read_new_actor(r, pm)
    blocks = read_content_blocks(r)
    rep = blocks[0]["payload"]

    w = GuidWriter()
    write_new_actor(
        w, 9360, 13, 5, location=info["location"], rotation=info["rotation"]
    )
    write_content_block(w, rep, has_rep_layout=1)
    for gid in (9364, 9366, 9368, 9370):
        write_subobject_content_block(w, gid, stably_named=1)
    got = [(w.get_bytes()[i >> 3] >> (i & 7)) & 1 for i in range(w.num)]
    expect = bits[3257:]
    assert got == expect, f"body mismatch len {len(got)} vs {len(expect)}"
    print(f"[ok] generated PC body bit-identical to capture ({len(got)} bits)")


def test_pawn_open_exports():
    specs = json.load(open(os.path.join(HERE, "real_pawn_bunches.json")))
    bits = []
    for sp in specs:
        bits.extend(int(c) for c in sp["payload"])
    pm = PackageMap()
    gr = GuidReader(bits)
    gr.bit()
    n = gr.i32()
    assert n == 8
    paths = []
    for _ in range(n):
        gid, _ = pm.load_object(gr, exporting=True)
        paths.append(pm.guid_to_path.get(gid))
    assert "Default__BP_PlayerPawn_01_C" in paths
    assert "InventoryManager" in paths
    r = Bits(bits, gr.pos)
    info = read_new_actor(r, pm)
    assert info["archetypePath"] == "Default__BP_PlayerPawn_01_C"
    assert info["location"] == (-1787.0, -10060.0, -562.5)
    assert info["has_rotation"]
    assert abs(info["rotation"][1] - 90.0) < 1e-6
    assert info.get("has_scale")
    assert not info.get("incomplete"), info
    assert len(info.get("scale_raw_bits") or []) == 109
    blocks = read_content_blocks(r)
    subs = [b.get("subNetGUID") for b in blocks if not b.get("isActor")]
    assert subs[:5] == [9374, 9376, 9378, 9380, 9382]
    assert 9384 in subs
    assert r.left() == 0
    print("[ok] pawn open fully parsed (scale 109b + component stubs)")


def test_replay_bunch_threads_must_be_mapped_guids():
    """build_replay_bunch() must forward bHasMustBeMappedGUIDs from the spec instead of
    always hardcoding 0. real_replay_stream.json never captured this bit (ground-truthed
    as 0 for every bunch we currently replay -- see _ground_truth_mbm.py), so today this
    is a no-behaviour-change correctness fix; it only matters once a spec sets the flag
    (this test), or if real_replay_stream.json is ever re-extracted with the real bit."""
    import control_channel as cc
    from server import MatchServer, Conn

    srv = MatchServer()
    conn = Conn()

    def decode(spec):
        nbits, raw = srv.build_replay_bunch(conn, spec)
        r = cc.CReader(raw)
        r.num = len(raw) * 8  # bunch bytes are byte-padded; term just needs to bound reads
        return cc._read_bunch(r, r.num)

    base = {"chIndex": 3, "bOpen": 1, "bClose": 0, "bReliable": 1,
            "bHasPackageMapExports": 0, "bPartial": 0, "payload": "1010"}

    b_default = decode(dict(base))
    assert b_default["bHasMustBeMappedGUIDs"] == 0, "default (no key in spec) must stay 0"

    b_off = decode({**base, "bHasMustBeMappedGUIDs": 0})
    assert b_off["bHasMustBeMappedGUIDs"] == 0

    b_on = decode({**base, "bHasMustBeMappedGUIDs": 1})
    assert b_on["bHasMustBeMappedGUIDs"] == 1, "spec-provided flag must be honoured"
    print("[ok] build_replay_bunch threads bHasMustBeMappedGUIDs from spec (default 0 unchanged)")


def test_ack_audit():
    """WW3_ACK_AUDIT only watches pawn/weapon channels, and only when enabled."""
    import server

    specs_pawn = [{"chIndex": 2, "_src_idx": 9},
                  {"chIndex": 3, "bOpen": 1, "bPartial": 1, "bPartialInitial": 1, "_src_idx": 10}]
    specs_boring = [{"chIndex": 2, "_src_idx": 9}, {"chIndex": 53, "bOpen": 1, "_src_idx": 119}]

    was = server.ACK_AUDIT
    try:
        server.ACK_AUDIT = False
        assert server.MatchServer._audit_tag_for(specs_pawn) is None, "audit must be inert when off"

        server.ACK_AUDIT = True
        assert server.MatchServer._audit_tag_for(specs_boring) is None, "ch2/ch53 must not be tagged"
        tag = server.MatchServer._audit_tag_for(specs_pawn)
        assert tag and "ch3" in tag and "OPEN" in tag and "src=10" in tag, tag

        srv = server.MatchServer()
        conn = server.Conn()
        conn.pkt_audit = {7: {"t": time.time(), "tag": tag, "acked": None},
                          8: {"t": time.time() - 60, "tag": tag, "acked": None}}
        srv.audit_note_acks(conn, [7, 999])
        assert 7 not in conn.pkt_audit, "acked packet must be resolved and dropped"
        assert 8 in conn.pkt_audit, "unrelated packet must stay under watch"
        srv.audit_tick(conn)
        assert 8 not in conn.pkt_audit, "stale unacked packet must be reported and dropped"
    finally:
        server.ACK_AUDIT = was
    print("[ok] WW3_ACK_AUDIT tags only pawn channels and resolves acked/unacked packets")


if __name__ == "__main__":
    test_rotator_roundtrip()
    test_capture_pc_spawn_complete()
    test_generated_body_matches_capture()
    test_pawn_open_exports()
    test_replay_bunch_threads_must_be_mapped_guids()
    test_ack_audit()
    print("\nALL M4 spawn tests passed")
