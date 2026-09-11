#!/usr/bin/env python3
"""Tests for the ClientRestart send path (M4 experiment #2/#3B wiring).

These exist because session 20260805_193023 produced no `ClientRestart` line and the
console gave no way to tell whether the flag was off, a gate held it, or the code was
broken. Every branch below must either send or say why it didn't.
"""
from __future__ import annotations

import hashlib
import os
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import control_channel as cc  # noqa: E402
import server as srvmod  # noqa: E402
from actor_channel import Bits, write_content_block  # noqa: E402
from netguid import GuidWriter  # noqa: E402
from possess_rpc import (PAWN_NETGUID, is_ack_possession_pawn,
                         parse_actor_rpc_fields, parse_actor_rpc_handles,
                         write_int_wrapped)  # noqa: E402

RESTART_ENV = (
    "WW3_CLIENT_RESTART",
    "WW3_CLIENT_RESTART_MUSTMAP",
    "WW3_CLIENT_RESTART_SEND_RETRY",
    "WW3_CLIENT_RESTART_MAX_SPRAYS",
    "WW3_CLIENT_RESTART_AFTER_PAWN_MS",
    "WW3_CLIENT_RESTART_REQUIRE_CH3_ACK",
    "WW3_CLIENT_RESTART_GATE_TIMEOUT_S",
    "WW3_CLIENT_RESTART_MBM_FALLBACK_S",
    "WW3_PC_SET_PAWN",
    "WW3_RESTART_CALIBRATE",
    "WW3_CLIENT_RESTART_PAWN_GUID",
    "WW3_POST_PAWN_PC_STATE",
    "WW3_CLIENT_SHOW_INFANTRY_WIDGET",
    "WW3_CLEAR_SPECTATOR_WAITING",
    "WW3_FORCE_GAMESTATE_INPROGRESS",
    "WW3_CHARACTER_RESPAWN_SUCCESS",
    "WW3_BEFORE_SPECTATOR_RETURN",
    "WW3_BEFORE_SPECTATOR_EAGER",
    "WW3_CLIENT_AUTO_DEPLOY",
    "WW3_CLIENT_STOP_SPECTATOR_BEFORE_DEPLOY",
    "WW3_CLIENT_STOP_SPECTATOR",
    "WW3_DEPLOY_ON_PRELOAD",
    "WW3_FINAL_VIEW_TARGET_ONLY",
    "WW3_REPLAY_GAMESTATE_TAIL_AFTER_SPECTATOR",
    "WW3_POST_SPECTATOR_WAM_SYNC_KICK",
    "WW3_POST_SPECTATOR_CAM_IM_REBIND",
    "WW3_INV_ATTACH",
    "WW3_CLOTHING_RESEND",
    "WW3_CAM_STRIP_CATALOG",
    "WW3_STRICT_PLAYER_IN_GAME_ORDER",
    "WW3_PROFILE_PROLOGUE",
    "WW3_PROFILE_PROLOGUE_DELAY_S",
    "WW3_PROFILE_PROLOGUE_MODE",
    "WW3_PROFILE_PROLOGUE_STEP_S",
    "WW3_PS_MASTER_LINK",
    "WW3_PS_LOCK_VEHICLE_REPLY",
    "WW3_TEAM_ACTION_REPLICATOR",
    "WW3_TEAM_ACTION_REPLICATOR_DELAY_S",
    "WW3_ACTION_PROBE",
    "WW3_ACTION_PROBE_DELAY_S",
    "WW3_ACTION_PROBE_LIVENESS_S",
    "WW3_TEAM_SYNC_BIND",
    "WW3_TEAM_SYNC_BIND_DELAY_S",
    "WW3_TEAM_SYNC_BIND_LIVENESS_S",
    "WW3_TEAM_SYNC_BIND_NET_ID",
    "WW3_TEAM_SYNC_BIND_UNIQUE_ID",
    "WW3_TEAM_SYNC_BIND_NAME",
    "WW3_INV_SYNC_BIND",
    "WW3_INV_SYNC_BIND_DELAY_S",
    "WW3_INV_SYNC_BIND_LIVENESS_S",
    "WW3_INV_SYNC_BIND_MODE",
    "WW3_INV_SYNC_BIND_PRIMARY",
    "WW3_INV_SYNC_BIND_SECONDARY",
    "WW3_DEPLOY_RELEASE",
    "WW3_DEPLOY_RELEASE_DELAY_S",
    "WW3_DEPLOY_RELEASE_LIVENESS_S",
    "WW3_DEPLOY_AFTER_SPECTATOR",
    "WW3_DEPLOY_AFTER_SPECTATOR_DELAY_S",
    "WW3_TEAM_SYNC_BIND_REQUIRE_PROBE_ACK",
    "WW3_ACTION_REPLICATOR_ALLOW_DOUBLE_OPEN",
    "WW3_DEPLOY_REPEAT_AFTER_SPECTATOR",
    "WW3_DEPLOY_REPEAT_AFTER_SPECTATOR_DELAY_S",
)


class FakeSock:
    def __init__(self):
        self.sent = []

    def sendto(self, data, addr):
        self.sent.append(data)
        return len(data)


def _fixture(pawn_open_age_s=5.0, **env):
    for k in RESTART_ENV:
        os.environ.pop(k, None)
    # Keep these unit tests focused on the standalone ClientRestart bunch.  The
    # live launcher enables the captured post-pawn PC transition bundle, which is
    # deliberately tested through the integration run rather than this byte-count
    # fixture.
    os.environ.setdefault("WW3_POST_PAWN_PC_STATE", "0")
    os.environ.update({k: str(v) for k, v in env.items()})
    srv = srvmod.MatchServer()
    conn = srvmod.Conn()
    conn.state = "JOINING"
    conn.pawn_sent = True
    conn._ownership_done = True
    conn._pawn_open_t = time.time() - pawn_open_age_s
    return srv, conn, FakeSock(), ("127.0.0.1", 1234)


def _bunches(sock):
    out = []
    for data in sock.sent:
        out.extend(cc.read_packet(data)["bunches"])
    return out


def _payload_bits(b):
    r = b["reader"]
    start, n = b["payloadStart"], b["bunchDataBits"]
    return [((r.data[(start + i) >> 3] >> ((start + i) & 7)) & 1) for i in range(n)]


def _playerstate_rpc_bunch(channel, handle, params=()):
    """Build a C->S PlayerState RPC field with the captured ValueMax=82."""
    field = GuidWriter()
    write_int_wrapped(field, handle, 82)
    field.write_packed(len(params))
    for bit in params:
        field.write_bit(bit)
    framed = GuidWriter()
    raw = field.get_bytes()
    write_content_block(framed, [
        (raw[i >> 3] >> (i & 7)) & 1 for i in range(field.num)
    ], has_rep_layout=0)
    packet = cc.write_packet(
        1, [], [cc.make_bunch(
            framed.num, framed.get_bytes(), ch_index=channel, ch_seq=1,
            ch_type=cc.CHTYPE_ACTOR, bReliable=1)])
    return cc.read_packet(packet)["bunches"][0]


def _controller_rpc_bunch(handle, params=()):
    field = GuidWriter()
    write_int_wrapped(field, handle, 315)
    field.write_packed(len(params))
    for bit in params:
        field.write_bit(bit)
    framed = GuidWriter()
    raw = field.get_bytes()
    write_content_block(framed, [
        (raw[i >> 3] >> (i & 7)) & 1 for i in range(field.num)
    ], has_rep_layout=0)
    packet = cc.write_packet(
        1, [], [cc.make_bunch(
            framed.num, framed.get_bytes(), ch_index=2, ch_seq=1,
            ch_type=cc.CHTYPE_ACTOR, bReliable=1)])
    return cc.read_packet(packet)["bunches"][0]


def test_player_in_game_notify_replies_once_on_identified_ps_channel():
    """Dropping PS h65 must fail; exact source1056 must answer it once."""
    srv, conn, sock, addr = _fixture()
    conn.ps_opened = True
    conn.ps_channel = 17  # response must follow identity, not assume capture channel 7
    inbound = _playerstate_rpc_bunch(17, 65)

    assert srv.handle_bunch(sock, addr, conn, inbound) is True
    bunches = _bunches(sock)
    assert len(bunches) == 1
    assert bunches[0]["chIndex"] == 17
    expected = [int(x) for x in "0101111000011110010000001"]
    assert _payload_bits(bunches[0]) == expected
    assert parse_actor_rpc_fields(expected, value_max=82) == [(30, [1])]

    sent = len(sock.sent)
    assert srv.handle_bunch(sock, addr, conn, inbound) is False
    assert len(sock.sent) == sent, "duplicate h65 must not duplicate the reliable reply"
    print("[ok] PS Server_PlayerInGameNotify gets exact captured source1056 once")


def test_disabled_flag_is_reported():
    srv, conn, sock, addr = _fixture(WW3_CLIENT_RESTART=0)
    assert srv.maybe_send_client_restart(sock, addr, conn) is False
    assert not sock.sent, "disabled Restart must not put anything on the wire"
    assert any("WW3_CLIENT_RESTART=0" in w for w in conn._restart_skips), conn._restart_skips
    print("[ok] WW3_CLIENT_RESTART=0 declines AND says so (root cause of the 193023 run)")


def test_single_shot_restart_handle_no_retry():
    srv, conn, sock, addr = _fixture(
        WW3_CLIENT_RESTART=1, WW3_CLIENT_RESTART_MUSTMAP=1,
        WW3_CLIENT_RESTART_SEND_RETRY=0, WW3_CLIENT_RESTART_MAX_SPRAYS=1)
    assert srv.maybe_send_client_restart(sock, addr, conn) is True
    bunches = [b for b in _bunches(sock) if b["chIndex"] == 2]
    assert len(bunches) == 1, f"single-shot must be exactly one bunch, got {len(bunches)}"
    b = bunches[0]
    assert b["bHasMustBeMappedGUIDs"] == 1, "MustBeMapped must reach the bunch header"
    bits = _payload_bits(b)
    # MustBeMapped prefix (uint16 count + packed guid) precedes the RPC content block.
    handles = parse_actor_rpc_handles(bits[16 + 16:])
    expect = __import__("possess_rpc").restart_handles()[0]
    assert handles and handles[0] == (expect, [PAWN_NETGUID]), handles
    # Budget spent: a second call must decline, not spray.
    assert srv.maybe_send_client_restart(sock, addr, conn) is False
    assert any("budget" in w for w in conn._restart_skips), conn._restart_skips
    print(f"[ok] single-shot handle {expect}, MustBeMapped 9372, SEND_RETRY=0, "
          "no second spray")


def test_after_pawn_ms_gate():
    srv, conn, sock, addr = _fixture(pawn_open_age_s=0.0, WW3_CLIENT_RESTART=1,
                                     WW3_CLIENT_RESTART_AFTER_PAWN_MS=1500,
                                     WW3_CLIENT_RESTART_MAX_SPRAYS=1)
    assert srv.maybe_send_client_restart(sock, addr, conn) is False
    assert not sock.sent
    assert conn._delayed_restart_at > 0, "a held Restart must re-arm the keepalive retry"
    assert any("after pawn open" in w for w in conn._restart_skips), conn._restart_skips
    conn._pawn_open_t = time.time() - 2.0
    assert srv.maybe_send_client_restart(sock, addr, conn, reason="delayed") is True
    assert conn._delayed_restart_at == 0
    print("[ok] WW3_CLIENT_RESTART_AFTER_PAWN_MS holds then releases the Restart")


def test_require_ch3_ack_gate_and_timeout():
    was = srvmod.ACK_AUDIT
    srvmod.ACK_AUDIT = True
    try:
        srv, conn, sock, addr = _fixture(pawn_open_age_s=1.0, WW3_CLIENT_RESTART=1,
                                         WW3_CLIENT_RESTART_REQUIRE_CH3_ACK=1,
                                         WW3_CLIENT_RESTART_GATE_TIMEOUT_S=20,
                                         WW3_CLIENT_RESTART_MAX_SPRAYS=1)
        assert srv.maybe_send_client_restart(sock, addr, conn) is False
        srv.audit_note_acks(conn, [5])            # unrelated ack: still not ready
        assert srv.restart_gates_ready(conn)[0] is False
        conn.pkt_audit[6] = {"t": time.time(), "tag": "ch3 OPEN partial-init src=10",
                             "acked": None}
        srv.audit_note_acks(conn, [6])
        assert conn._ch3_open_acked is True
        assert srv.maybe_send_client_restart(sock, addr, conn) is True

        # A gate must never stall a live run forever.
        _, conn2, _, _ = _fixture(pawn_open_age_s=99.0, WW3_CLIENT_RESTART=1,
                                  WW3_CLIENT_RESTART_REQUIRE_CH3_ACK=1,
                                  WW3_CLIENT_RESTART_GATE_TIMEOUT_S=20)
        assert srv.restart_gates_ready(conn2)[0] is True
    finally:
        srvmod.ACK_AUDIT = was
    print("[ok] WW3_CLIENT_RESTART_REQUIRE_CH3_ACK gate + GATE_TIMEOUT_S escape hatch")


def test_pc_set_pawn_precedes_restart():
    srv, conn, sock, addr = _fixture(WW3_CLIENT_RESTART=1, WW3_PC_SET_PAWN=1,
                                     WW3_CLIENT_RESTART_MUSTMAP=0,
                                     WW3_CLIENT_RESTART_MAX_SPRAYS=1)
    assert srv.maybe_send_client_restart(sock, addr, conn) is True
    bunches = [b for b in _bunches(sock) if b["chIndex"] == 2]
    # The binding helper intentionally restates both PC::PlayerState and
    # PC::Pawn before the RPC, so the reliable sequence is two RepLayout
    # bunches followed by ClientRestart.
    assert len(bunches) == 3, f"expected PC PlayerState + Pawn then Restart, got {len(bunches)}"
    from actor_channel import Bits, read_content_blocks
    for b in bunches[:2]:
        first = read_content_blocks(Bits(_payload_bits(b)))[0]
        assert first["hasRepLayout"] and first["isActor"], "PC binding block must be a RepLayout"
    expect = __import__("possess_rpc").restart_handles()[0]
    assert parse_actor_rpc_handles(_payload_bits(bunches[2]))[0] == (expect, [PAWN_NETGUID])
    # Ordering matters and it must not repeat.
    conn._client_restart_sprays = 0
    sock.sent.clear()
    srv.maybe_send_client_restart(sock, addr, conn)
    assert len([b for b in _bunches(sock) if b["chIndex"] == 2]) == 1, "PC Pawn is once-only"
    print("[ok] WW3_PC_SET_PAWN sends PC::Pawn=9372 immediately before ClientRestart, once")


def test_mbm_fallback_sends_executable_shot_first():
    """Both framings requested => non-MustBeMapped MUST go out first.

    An unresolvable MustBeMapped bunch parks in UActorChannel::QueuedBunches and blocks
    every later reliable bunch on that channel. Live 20260805_194518 sent MustBeMapped
    first and the follow-up never got a reply, on a connection that stayed healthy.
    """
    for mustmap in (0, 1):
        srv, conn, sock, addr = _fixture(WW3_CLIENT_RESTART=1,
                                         WW3_CLIENT_RESTART_MUSTMAP=mustmap,
                                         WW3_CLIENT_RESTART_MBM_FALLBACK_S=8,
                                         WW3_CLIENT_RESTART_MAX_SPRAYS=2)
        assert srv.maybe_send_client_restart(sock, addr, conn) is True
        first = [x for x in _bunches(sock) if x["chIndex"] == 2][0]
        assert first["bHasMustBeMappedGUIDs"] == 0, (
            f"WW3_CLIENT_RESTART_MUSTMAP={mustmap}: first shot must be executable")
        assert conn._mbm_fallback_at > time.time(), "fallback must be armed"
        sock.sent.clear()
        assert srv.maybe_send_client_restart(sock, addr, conn, reason="mbm-fallback") is True
        second = [x for x in _bunches(sock) if x["chIndex"] == 2][0]
        assert second["bHasMustBeMappedGUIDs"] == 1, "fallback carries the MustBeMapped GUID"
        assert srv.maybe_send_client_restart(sock, addr, conn) is False, "budget is 2"
    print("[ok] MBM fallback: non-MustBeMapped first, MustBeMapped second, either MUSTMAP")


def test_mustmap_alone_is_honoured():
    """With no fallback configured, WW3_CLIENT_RESTART_MUSTMAP still picks the framing."""
    srv, conn, sock, addr = _fixture(WW3_CLIENT_RESTART=1, WW3_CLIENT_RESTART_MUSTMAP=1,
                                     WW3_CLIENT_RESTART_MAX_SPRAYS=1)
    assert srv.maybe_send_client_restart(sock, addr, conn) is True
    assert [x for x in _bunches(sock) if x["chIndex"] == 2][0]["bHasMustBeMappedGUIDs"] == 1
    print("[ok] WW3_CLIENT_RESTART_MUSTMAP alone still controls the single shot")


def test_ack_pawn_stops_everything():
    srv, conn, sock, addr = _fixture(WW3_CLIENT_RESTART=1)
    conn._ack_possess_pawn = True
    assert srv.maybe_send_client_restart(sock, addr, conn) is False
    assert not sock.sent
    P = __import__("possess_rpc")
    assert is_ack_possession_pawn(
        P.build_object_rpc_bits(P.RPC_SERVER_ACK_POSSESSION, PAWN_NETGUID))
    print("[ok] AckPossession(Pawn) short-circuits further Restarts")


def test_calibrate_ps_sends_ps_guid_not_pawn():
    """WW3_RESTART_CALIBRATE=ps must swap the RPC argument, never chase MustBeMapped,
    and skip #3B's PC::Pawn=9372 set (that would contradict a PS-guid control test)."""
    from possess_rpc import PS_NETGUID

    srv, conn, sock, addr = _fixture(
        WW3_CLIENT_RESTART=1, WW3_RESTART_CALIBRATE="ps",
        WW3_CLIENT_RESTART_MUSTMAP=1,        # must be overridden to False for calibration
        WW3_PC_SET_PAWN=1,                   # must be skipped for calibration
        WW3_CLIENT_RESTART_MAX_SPRAYS=1)
    assert srv.maybe_send_client_restart(sock, addr, conn) is True
    bunches = [b for b in _bunches(sock) if b["chIndex"] == 2]
    assert len(bunches) == 1, "calibration must not also send #3B's PC::Pawn block"
    assert bunches[0]["bHasMustBeMappedGUIDs"] == 0, "calibration must never use MustBeMapped"
    handles = parse_actor_rpc_handles(_payload_bits(bunches[0]))
    expect = __import__("possess_rpc").restart_handles()[0]
    assert handles and handles[0] == (expect, [PS_NETGUID]), handles
    assert not getattr(conn, "_pc_set_pawn_done", False)
    print("[ok] WW3_RESTART_CALIBRATE=ps sends the Restart handle with the PS GUID, no MBM, no #3B")


def test_explicit_pawn_guid_override_wins_over_calibrate():
    srv, conn, sock, addr = _fixture(
        WW3_CLIENT_RESTART=1, WW3_RESTART_CALIBRATE="ps",
        WW3_CLIENT_RESTART_PAWN_GUID=4242,
        WW3_CLIENT_RESTART_MAX_SPRAYS=1)
    assert srv.maybe_send_client_restart(sock, addr, conn) is True
    bunches = [b for b in _bunches(sock) if b["chIndex"] == 2]
    handles = parse_actor_rpc_handles(_payload_bits(bunches[0]))
    expect = __import__("possess_rpc").restart_handles()[0]
    assert handles and handles[0] == (expect, [4242]), handles
    print("[ok] WW3_CLIENT_RESTART_PAWN_GUID explicit override beats WW3_RESTART_CALIBRATE=ps")


def test_show_infantry_widget_is_opt_in_zero_arg_rpc():
    srv, conn, sock, addr = _fixture(WW3_CLIENT_SHOW_INFANTRY_WIDGET=0)
    assert srv.maybe_send_infantry_widget(sock, addr, conn) is False
    assert not sock.sent

    srv, conn, sock, addr = _fixture(WW3_CLIENT_SHOW_INFANTRY_WIDGET=1)
    assert srv.maybe_send_infantry_widget(sock, addr, conn) is True
    bunches = [b for b in _bunches(sock) if b["chIndex"] == 2]
    assert len(bunches) == 1
    assert parse_actor_rpc_handles(_payload_bits(bunches[0])) == [(151, [])]
    assert srv.maybe_send_infantry_widget(sock, addr, conn) is False
    print("[ok] Client_ShowInfantryWidget is opt-in, zero-arg, and single-shot")


def test_clear_spectator_waiting_sends_raw_false_bool():
    srv, conn, sock, addr = _fixture(WW3_CLEAR_SPECTATOR_WAITING=1)
    assert srv.maybe_clear_spectator_waiting(sock, addr, conn) is True
    bunches = [b for b in _bunches(sock) if b["chIndex"] == 2]
    assert len(bunches) == 1
    assert parse_actor_rpc_fields(_payload_bits(bunches[0])) == [(49, [0])]
    assert srv.maybe_clear_spectator_waiting(sock, addr, conn) is False
    print("[ok] ClientSetSpectatorWaiting(false) carries one raw bool bit")


def test_post_spectator_callback_finalizes_once_in_order():
    srv, conn, sock, addr = _fixture(WW3_POST_SPECTATOR_ONLINE_SESSION=1)
    calls = []
    for name in ("maybe_force_gamestate_inprogress", "maybe_replay_captured_gamestate_tail", "maybe_send_post_pawn_pc_state", "maybe_send_player_respawned",
                 "maybe_send_game_started", "maybe_send_domination_match_started",
                 "maybe_send_infantry_widget", "maybe_send_camera_rebind",
                 "maybe_send_final_view_target_only", "maybe_send_online_session_started"):
        setattr(srv, name, lambda *_args, _name=name, **kwargs:
                calls.append((_name, kwargs.get("force"))))
    assert srv.maybe_finalize_post_spectator(sock, addr, conn) is True
    assert calls == [
        ("maybe_force_gamestate_inprogress", True),
        ("maybe_replay_captured_gamestate_tail", True),
        ("maybe_send_post_pawn_pc_state", True),
        ("maybe_send_player_respawned", True),
        ("maybe_send_game_started", True),
        ("maybe_send_domination_match_started", True),
        ("maybe_send_infantry_widget", True),
        ("maybe_send_camera_rebind", True),
        ("maybe_send_final_view_target_only", True),
        ("maybe_send_online_session_started", True),
    ]
    assert srv.maybe_finalize_post_spectator(sock, addr, conn) is False
    print("[ok] Server_OnPostSpectatorReturnToGame finalizes gameplay once and in order")


def test_post_spectator_finalizer_replays_batch3_wam_generation_once():
    """A 282 barrier must cause a new WAM generation on all four owned weapons."""
    srv, conn, sock, addr = _fixture(WW3_POST_SPECTATOR_WAM_SYNC_KICK=1)

    assert srv.maybe_finalize_post_spectator(sock, addr, conn) is True
    wam = [b for b in _bunches(sock) if b["chIndex"] in (4, 5, 86, 87)]
    assert [(b["chIndex"], b["bunchDataBits"]) for b in wam] == [
        (4, 372),
        (5, 372),
        (86, 180),
        (87, 180),
    ]

    before = len(sock.sent)
    assert srv.maybe_finalize_post_spectator(sock, addr, conn) is False
    assert len(sock.sent) == before
    print("[ok] post-spectator finalizer emits one BatchID=3 WAM generation")


def test_post_spectator_finalizer_rebinds_cam_im_after_wam_generation():
    """The owner binding must be replayed after WAM completion, not before it."""
    srv, conn, sock, addr = _fixture(
        WW3_POST_SPECTATOR_WAM_SYNC_KICK=1,
        WW3_POST_SPECTATOR_CAM_IM_REBIND=1,
        WW3_INV_ATTACH=1,
        WW3_CLOTHING_RESEND=1,
        WW3_CAM_STRIP_CATALOG=0,
    )

    assert srv.maybe_finalize_post_spectator(sock, addr, conn) is True
    ch3 = [b for b in _bunches(sock) if b["chIndex"] == 3]
    assert [b["bunchDataBits"] for b in ch3] == [2065, 3104]
    print("[ok] post-spectator finalizer replays captured CAM/IM chain after BatchID=3")


def test_post_spectator_gamestate_tail_is_bit_exact_capture():
    srv, conn, sock, addr = _fixture(WW3_REPLAY_GAMESTATE_TAIL_AFTER_SPECTATOR=1)
    assert srv.maybe_replay_captured_gamestate_tail(sock, addr, conn) is True
    bunches = [b for b in _bunches(sock) if b["chIndex"] == 53]
    assert len(bunches) == 2
    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
    for bunch, src in zip(bunches, (215, 275)):
        expected = [int(x) for x in stream[src]["payload"]]
        assert _payload_bits(bunch) == expected
    assert srv.maybe_replay_captured_gamestate_tail(sock, addr, conn, force=True) is False
    print("[ok] post-spectator GameState tail replays exact captured src215/src275 once")


def test_final_view_target_is_exact_capture_and_blocks_later_camera_retries():
    srv, conn, sock, addr = _fixture(WW3_FINAL_VIEW_TARGET_ONLY=1)
    assert srv.maybe_send_final_view_target_only(sock, addr, conn) is True
    bunches = [b for b in _bunches(sock) if b["chIndex"] == 2]
    assert len(bunches) == 1
    fields = parse_actor_rpc_fields(_payload_bits(bunches[0]))
    assert len(fields) == 1 and fields[0][0] == 50, fields
    assert len(fields[0][1]) == 86, fields
    sent = len(sock.sent)
    assert srv.maybe_send_camera_rebind(sock, addr, conn, force=True) is False
    assert len(sock.sent) == sent
    assert srv.maybe_send_final_view_target_only(sock, addr, conn, force=True) is False
    print("[ok] final view target is captured handle 50 only and remains final")


def test_near_squad_request_gets_success_response():
    srv, conn, sock, addr = _fixture()
    os.environ["WW3_CHARACTER_RESPAWN_SUCCESS"] = "1"
    assert srv.maybe_accept_character_respawn(sock, addr, conn) is True
    bunches = [b for b in _bunches(sock) if b["chIndex"] == 2]
    assert len(bunches) == 1
    response = parse_actor_rpc_fields(_payload_bits(bunches[0]))
    assert response[0][0] == 235 and len(response[0][1]) == 67
    assert srv.maybe_accept_character_respawn(sock, addr, conn) is False
    print("[ok] Server_RespawnPlayerNearSquadLeader gets one success response")


def test_near_squad_success_is_disabled_by_default():
    srv, conn, sock, addr = _fixture()
    os.environ.pop("WW3_CHARACTER_RESPAWN_SUCCESS", None)
    assert srv.maybe_accept_character_respawn(sock, addr, conn) is False
    assert not [b for b in _bunches(sock) if b["chIndex"] == 2]
    print("[ok] unverified character-respawn success RPC is disabled by default")


def test_eager_before_spectator_callback_is_not_duplicated():
    srv, conn, sock, addr = _fixture(
        WW3_BEFORE_SPECTATOR_RETURN="1",
        WW3_BEFORE_SPECTATOR_EAGER="1",
        WW3_CLIENT_AUTO_DEPLOY="1",
        WW3_CLIENT_STOP_SPECTATOR_BEFORE_DEPLOY="0",
        WW3_CLIENT_STOP_SPECTATOR="0",
    )
    srv.maybe_send_late_transition = lambda *_args, **_kwargs: False
    srv.maybe_send_camera_rebind = lambda *_args, **_kwargs: False
    assert srv.maybe_send_before_spectator_return(sock, addr, conn) is True
    assert srv.maybe_send_auto_deploy(sock, addr, conn, force=True) is True
    handles = []
    for bunch in _bunches(sock):
        if bunch["chIndex"] == 2:
            handles.extend(h[0] for h in parse_actor_rpc_handles(_payload_bits(bunch)))
    assert handles.count(226) == 1, handles
    print("[ok] eager before-spectator callback remains single-shot")


def test_preload_marks_ready_without_consuming_deploy_by_default():
    srv, conn, sock, addr = _fixture()
    calls = []
    srv.maybe_send_before_spectator_return = lambda *_a, **_k: calls.append("before")
    srv.maybe_send_auto_deploy = lambda *_a, **_k: calls.append("deploy")
    assert srv.maybe_send_post_preload_deploy(sock, addr, conn) is False
    assert conn._preload_weapons_finished is True
    assert calls == []
    print("[ok] weapon preload defers deploy to ownership-settle timer")


def test_strict_player_in_game_orders_h65_profiles_then_fresh_h279():
    srv, conn, sock, addr = _fixture(WW3_STRICT_PLAYER_IN_GAME_ORDER="1")
    conn.ps_opened = True
    conn.ps_channel = 17

    # No forced timer/post-attachment caller may bypass the strict gate.
    assert srv.maybe_send_late_transition(sock, addr, conn, force=True) is False
    assert not sock.sent
    # A preload callback observed before h65/profile completion is stale readiness.
    assert srv.handle_bunch(sock, addr, conn, _controller_rpc_bunch(279)) is False
    assert not sock.sent
    assert not getattr(conn, "_preload_weapons_finished", False)

    h65 = _playerstate_rpc_bunch(17, 65)
    assert srv.handle_bunch(sock, addr, conn, h65) is True
    first = _bunches(sock)
    assert len(first) == 1 and first[0]["chIndex"] == 17
    assert parse_actor_rpc_fields(_payload_bits(first[0]), value_max=82) == [(30, [1])]

    # Advance beyond the last captured profile deadline.  The scheduler must retain
    # exact capture order and payload while adapting reliable ChSequence only.
    assert srv.maybe_service_strict_player_in_game(
        sock, addr, conn, now=conn._strict_profile_started_at + 2.0) is True
    expected_sources = list(srvmod.STRICT_PROFILE_SYNC_SOURCES)
    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
    sent = _bunches(sock)[1:]
    assert len(sent) == len(expected_sources)
    for bunch, source_index in zip(sent, expected_sources):
        source = stream[source_index]
        assert bunch["chIndex"] == 2
        assert bunch["bReliable"] == source["bReliable"] == 1
        assert bunch["bHasMustBeMappedGUIDs"] == source.get("bHasMustBeMappedGUIDs", 0) == 0
        assert _payload_bits(bunch) == [int(x) for x in source["payload"]]
    assert conn._strict_profiles_complete is True

    before = len(sock.sent)
    assert srv.handle_bunch(sock, addr, conn, h65) is False
    assert len(sock.sent) == before, "duplicate h65 must not replay h30/profiles"

    # Actor dispatch remains ack-driven and returns False even when the nested
    # transition helper emitted a packet; wire output is the authoritative result.
    assert srv.handle_bunch(sock, addr, conn, _controller_rpc_bunch(279)) is False
    transition = _bunches(sock)[-1]
    expected_transition = stream[1934]
    assert transition["chIndex"] == expected_transition["chIndex"]
    assert _payload_bits(transition) == [int(x) for x in expected_transition["payload"]]
    before = len(sock.sent)
    assert srv.handle_bunch(sock, addr, conn, _controller_rpc_bunch(279)) is False
    assert len(sock.sent) == before
    assert srv.maybe_send_late_transition(sock, addr, conn, force=True) is False
    assert len(sock.sent) == before
    print("[ok] strict order ignores pre-h65 h279, then h30/profile chain -> fresh h279/src1934 once")


def test_team_action_replicator_is_opt_in_bit_exact_partial_pair():
    """ch80 `WW3ActionReplicator` — the actor that carries the squad graph.

    The client's "Client Synchronization" checklist is one bitmask byte, and its
    `PlayerState` bit is set only when `AWW3PlayerState::CurrentSquad` (offset
    0x710) is valid.  `UWW3SquadObject` has no Net properties: the client builds
    the Team/Squad/Slot graph locally from `UWW3ReplicatedAction_TM_*` objects
    delivered by an `AWW3ActionReplicator`.  The working capture opens exactly
    one, on ch80, as a two-bunch partial pair (src 174 initial + 175 final); our
    curated bootstrap never sends it.

    The pair must stay together and in order — a partial-initial without its
    final leaves the channel half-open forever.
    """
    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))

    # Off by default.
    srv, conn, sock, addr = _fixture()
    conn._ownership_done_t = time.time() - 100
    assert srv.maybe_service_team_action_replicator(sock, addr, conn) is False
    assert not sock.sent

    srv, conn, sock, addr = _fixture(WW3_TEAM_ACTION_REPLICATOR="1",
                                     WW3_TEAM_ACTION_REPLICATOR_DELAY_S="2.0")
    t0 = time.time()
    conn._ownership_done_t = t0

    # Gated on ownership completing, then on the arm delay.
    conn._ownership_done = False
    assert srv.maybe_service_team_action_replicator(sock, addr, conn, now=t0 + 5.0) is False
    conn._ownership_done = True
    assert srv.maybe_service_team_action_replicator(sock, addr, conn, now=t0 + 1.0) is False
    assert not sock.sent

    assert srv.maybe_service_team_action_replicator(sock, addr, conn, now=t0 + 2.0) is True
    sent = _bunches(sock)
    assert len(sent) == 2, "the partial pair must go out together"
    assert len(sock.sent) == 1, "both bunches belong in one packet, as in the capture"

    for bunch, source_index in zip(sent, srvmod.TEAM_ACTION_REPLICATOR_SOURCES):
        source = stream[source_index]
        assert source["chIndex"] == 80
        assert bunch["chIndex"] == 80
        assert bunch["chType"] == cc.CHTYPE_ACTOR
        assert bunch["bReliable"] == source["bReliable"] == 1
        assert bunch["bOpen"] == source["bOpen"]
        assert bunch["bPartial"] == source["bPartial"] == 1
        assert bunch["bPartialInitial"] == source["bPartialInitial"]
        assert bunch["bPartialFinal"] == source["bPartialFinal"]
        assert bunch["bHasPackageMapExports"] == source["bHasPackageMapExports"]
        assert _payload_bits(bunch) == [int(x) for x in source["payload"]]

    assert list(srvmod.TEAM_ACTION_REPLICATOR_SOURCES) == [174, 175]
    assert sent[0]["bPartialInitial"] == 1 and sent[0]["bPartialFinal"] == 0
    assert sent[1]["bPartialInitial"] == 0 and sent[1]["bPartialFinal"] == 1

    # Sent exactly once.
    before = len(sock.sent)
    assert srv.maybe_service_team_action_replicator(sock, addr, conn, now=t0 + 60.0) is False
    assert len(sock.sent) == before

    # Fails closed if the capture artifact ever changes underneath it.
    srv, conn, sock, addr = _fixture(WW3_TEAM_ACTION_REPLICATOR="1",
                                     WW3_TEAM_ACTION_REPLICATOR_DELAY_S="0")
    conn._ownership_done_t = time.time() - 100
    good = srvmod.TEAM_ACTION_REPLICATOR_SPECS
    try:
        srvmod.TEAM_ACTION_REPLICATOR_SPECS = ((174, 1369, "deadbeef" * 8),
                                               good[1])
        assert srv.maybe_service_team_action_replicator(sock, addr, conn) is False
        assert not sock.sent
    finally:
        srvmod.TEAM_ACTION_REPLICATOR_SPECS = good
    print("OK team action replicator ch80 is opt-in, bit-exact and fails closed")


def _action_replicator_rpc_bunch(handle, params=(), channel=80):
    """Build a C->S ch80 RPC field with AWW3ActionReplicator's ValueMax=14."""
    field = GuidWriter()
    write_int_wrapped(field, handle, 14)
    field.write_packed(len(params))
    for bit in params:
        field.write_bit(bit)
    framed = GuidWriter()
    raw = field.get_bytes()
    write_content_block(framed, [
        (raw[i >> 3] >> (i & 7)) & 1 for i in range(field.num)
    ], has_rep_layout=0)
    packet = cc.write_packet(
        1, [], [cc.make_bunch(
            framed.num, framed.get_bytes(), ch_index=channel, ch_seq=1,
            ch_type=cc.CHTYPE_ACTOR, bReliable=1)])
    return cc.read_packet(packet)["bunches"][0]


def test_action_probe_is_opt_in_one_shot_and_fails_closed():
    """The empty `TM_Synchronize` transport probe on ch80.

    It must never fire without the channel that carries it, must go out exactly
    once, must be bit-identical to the pure builder, and must refuse to send at
    all if the payload it built is not the reviewed one.
    """
    import action_replicator as ar

    expected_bits = ar.build_client_receive_packet_bits(
        ar.build_empty_tm_synchronize_packet())

    # 1. Off by default.
    srv, conn, sock, addr = _fixture()
    conn._action_replicator_done = True
    conn._action_replicator_done_t = time.time() - 100
    assert srv.maybe_send_action_probe(sock, addr, conn) is False
    assert not sock.sent

    # 2. On, but the channel it rides was never opened -> must stay silent.
    srv, conn, sock, addr = _fixture(WW3_ACTION_PROBE="1",
                                     WW3_ACTION_PROBE_DELAY_S="0")
    assert srv.maybe_send_action_probe(sock, addr, conn) is False
    assert not sock.sent

    # 3. Channel open, but the arm delay has not elapsed.
    srv, conn, sock, addr = _fixture(WW3_TEAM_ACTION_REPLICATOR="1",
                                     WW3_ACTION_PROBE="1",
                                     WW3_ACTION_PROBE_DELAY_S="2.0")
    t0 = time.time()
    conn._action_replicator_done = True
    conn._action_replicator_done_t = t0
    conn._last_client_bunch_t = t0 + 2.0        # client is talking (see liveness test)
    assert srv.maybe_send_action_probe(sock, addr, conn, now=t0 + 1.0) is False
    assert not sock.sent

    # 4. Fires once, on ch80, reliable, whole (never partial), no exports.
    assert srv.maybe_send_action_probe(sock, addr, conn, now=t0 + 2.0) is True
    sent = _bunches(sock)
    assert len(sent) == 1
    bunch = sent[0]
    assert bunch["chIndex"] == 80
    assert bunch["chType"] == cc.CHTYPE_ACTOR
    assert bunch["bReliable"] == 1
    assert bunch["bOpen"] == 0
    assert bunch["bPartial"] == 0
    assert bunch["bHasPackageMapExports"] == 0
    assert _payload_bits(bunch) == expected_bits
    assert len(expected_bits) == 255

    # The handle must decode with ch80's ClassNetCache and carry the 25-byte packet.
    fields = ar.parse_action_replicator_fields(_payload_bits(bunch))
    assert [h for h, _p in fields] == [ar.RPC_CLIENT_RECEIVE_PACKET]
    body = Bits(fields[0][1])
    assert body.bit() == 1 and body.read(16) == 25
    assert bytes(body.read(8) for _ in range(25)) == ar.build_empty_tm_synchronize_packet()

    # 5. Exactly once.
    before = len(sock.sent)
    assert srv.maybe_send_action_probe(sock, addr, conn, now=t0 + 60.0) is False
    assert len(sock.sent) == before

    # 6. Fails closed when the payload is not the reviewed one.
    srv, conn, sock, addr = _fixture(WW3_TEAM_ACTION_REPLICATOR="1",
                                     WW3_ACTION_PROBE="1",
                                     WW3_ACTION_PROBE_DELAY_S="0")
    conn._action_replicator_done = True
    conn._action_replicator_done_t = time.time() - 100
    good = srvmod.ACTION_PROBE_PACKET_SHA256
    try:
        srvmod.ACTION_PROBE_PACKET_SHA256 = "00" * 32
        assert srv.maybe_send_action_probe(sock, addr, conn) is False
        assert not sock.sent
    finally:
        srvmod.ACTION_PROBE_PACKET_SHA256 = good
    print("OK ch80 action probe is opt-in, one-shot, bit-exact and fails closed")


def test_action_probe_refuses_to_fire_at_a_silent_client():
    """A one-shot experiment must not be spent on a client that stopped talking.

    Turn 5's first live run wasted its only shot exactly this way: the client's
    net thread stalled while streaming the map at t=458.6 and the probe went out
    at t=459.7, so the single `Client_ReceivePacket` landed in a dead socket and
    the run proved nothing. Liveness is measured from real inbound bunches.
    """
    srv, conn, sock, addr = _fixture(WW3_TEAM_ACTION_REPLICATOR="1",
                                     WW3_ACTION_PROBE="1",
                                     WW3_ACTION_PROBE_DELAY_S="0",
                                     WW3_ACTION_PROBE_LIVENESS_S="2.0")
    t0 = time.time()
    conn._action_replicator_done = True
    conn._action_replicator_done_t = t0 - 10

    # Never heard from the client at all -> refuse.
    assert srv.maybe_send_action_probe(sock, addr, conn, now=t0) is False
    assert not sock.sent

    # Heard from it, but too long ago -> still refuse.
    conn._last_client_bunch_t = t0 - 5.0
    assert srv.maybe_send_action_probe(sock, addr, conn, now=t0) is False
    assert not sock.sent

    # Fresh inbound traffic -> fire.
    conn._last_client_bunch_t = t0 - 0.5
    assert srv.maybe_send_action_probe(sock, addr, conn, now=t0) is True
    assert len(_bunches(sock)) == 1

    # And real inbound bunches are what actually set the stamp.
    srv2, conn2, sock2, addr2 = _fixture(WW3_TEAM_ACTION_REPLICATOR="1")
    assert getattr(conn2, "_last_client_bunch_t", 0) == 0
    srv2.handle_bunch(sock2, addr2, conn2, _controller_rpc_bunch(279))
    assert time.time() - conn2._last_client_bunch_t < 1.0
    print("OK ch80 action probe refuses to fire at a silent client")


def test_client_ch80_ack_is_decoded_with_the_action_replicator_value_max():
    """`Server_AckActionsReceived` (handle 12) is the transport oracle.

    It must be decoded with ValueMax 14; the PlayerController parser would read
    the same bits as a different handle entirely.
    """
    srv, conn, sock, addr = _fixture(WW3_TEAM_ACTION_REPLICATOR="1")
    conn._action_replicator_done = True

    inbound = _action_replicator_rpc_bunch(12)
    srv.handle_bunch(sock, addr, conn, inbound)
    assert getattr(conn, "_action_ack_count", 0) == 1
    assert getattr(conn, "_action_probe_acked", False) is True

    srv.handle_bunch(sock, addr, conn, inbound)
    assert conn._action_ack_count == 2

    # A ch80 bunch must never be run through the PlayerController decoder.
    assert parse_actor_rpc_fields(_payload_bits(inbound)) != [(12, [])]
    print("OK client ch80 Server_AckActionsReceived is observed on its own ValueMax")


def test_action_probe_never_touches_other_actor_channels():
    """The ch80 observer must not change how ch2 / the PS channel are handled."""
    srv, conn, sock, addr = _fixture(WW3_TEAM_ACTION_REPLICATOR="1")
    conn._action_replicator_done = True
    conn.ps_opened = True
    conn.ps_channel = 7

    srv.handle_bunch(sock, addr, conn, _controller_rpc_bunch(279))
    assert getattr(conn, "_action_ack_count", 0) == 0

    srv.handle_bunch(sock, addr, conn, _playerstate_rpc_bunch(7, 65))
    assert getattr(conn, "_action_ack_count", 0) == 0
    print("OK ch80 observation is scoped to ch80")


def test_profile_prologue_is_opt_in_bit_exact_and_notes_the_h177_ack():
    """The capture opens profile replication *before* h281/h65; we never sent it.

    src 204 `Client_ForceClearCurrentPlayersProfileReplication` and src 321
    `Client_ReceiveServerStartDate` are the two self-contained captured bunches
    that start that conversation, and the client answers the second one with
    C->S h177 `Server_ClientReceivedServerStartDate`.
    """
    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))

    # Off by default: no captured prologue may leak into unrelated sessions.
    srv, conn, sock, addr = _fixture()
    conn._ownership_done_t = time.time() - 100
    assert srv.maybe_service_profile_prologue(sock, addr, conn) is False
    assert not sock.sent

    srv, conn, sock, addr = _fixture(WW3_PROFILE_PROLOGUE="1",
                                     WW3_PROFILE_PROLOGUE_DELAY_S="2.0")
    t0 = time.time()
    conn._ownership_done_t = t0

    # Nothing before the arm delay, and nothing at all until ownership completes.
    conn._ownership_done = False
    assert srv.maybe_service_profile_prologue(sock, addr, conn, now=t0 + 5.0) is False
    conn._ownership_done = True
    assert srv.maybe_service_profile_prologue(sock, addr, conn, now=t0 + 1.0) is False
    assert not sock.sent

    # Capture order, one bunch at a time, on the connection's PC channel.
    assert srv.maybe_service_profile_prologue(sock, addr, conn, now=t0 + 2.0) is True
    sent = _bunches(sock)
    assert len(sent) == 1, "src 321 must wait out its captured delta"
    assert srv.maybe_service_profile_prologue(sock, addr, conn, now=t0 + 2.0) is False

    assert srv.maybe_service_profile_prologue(sock, addr, conn, now=t0 + 4.0) is True
    sent = _bunches(sock)
    expected_sources = list(srvmod.STRICT_PROFILE_PROLOGUE_SOURCES)
    assert expected_sources == [204, 321]
    assert len(sent) == len(expected_sources)
    for bunch, source_index in zip(sent, expected_sources):
        source = stream[source_index]
        assert bunch["chIndex"] == 2
        assert bunch["bReliable"] == source["bReliable"] == 1
        assert bunch["bOpen"] == 0 and bunch["bPartial"] == 0
        assert bunch["bHasMustBeMappedGUIDs"] == source.get("bHasMustBeMappedGUIDs", 0) == 0
        assert _payload_bits(bunch) == [int(x) for x in source["payload"]]
    assert parse_actor_rpc_fields(_payload_bits(sent[0]))[0][0] == 111
    assert parse_actor_rpc_fields(_payload_bits(sent[1]))[0][0] == 132
    assert conn._profile_prologue_done is True

    # Idempotent: a later service pass must not replay the conversation.
    before = len(sock.sent)
    assert srv.maybe_service_profile_prologue(sock, addr, conn, now=t0 + 60.0) is False
    assert len(sock.sent) == before

    # The client's ACK of Client_ReceiveServerStartDate is recorded exactly once.
    assert getattr(conn, "_profile_prologue_acked", False) is False
    assert srv.handle_bunch(sock, addr, conn, _controller_rpc_bunch(177)) is False
    assert conn._profile_prologue_acked is True
    assert len(sock.sent) == before, "h177 is an observation, not a trigger"
    print("[ok] profile prologue is opt-in, bit-exact, single-shot, and notes h177")


def test_profile_prologue_full_mode_replays_the_whole_pre_h65_chain():
    """`min` opens the list; only `full` fills and finishes it.

    Between the capture client's first `Server_OnClientPreloadWeaponsFinished`
    (C->S h279, src~354) and its `Server_OnMapOpened` + PS
    `Server_PlayerInGameNotify` (src~1050) the working server sends *nothing*
    except the profile conversation: h111 clear, 20x h140 profile pages, two
    h110 finishes, plus h132/h133/h137/h146.  Shipping only src 204/321 leaves
    the client's profile list opened and never closed.
    """
    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
    profile_handles = {110, 111, 132, 133, 137, 140, 146}

    full = srvmod.STRICT_PROFILE_PROLOGUE_FULL_SPECS
    sources = [spec[0] for spec in full]
    assert sources == sorted(sources), "capture order"
    assert len(sources) == len(set(sources)), "no duplicate sources"
    assert sources[0] == 204, "the chain must open with h111 ForceClear"
    assert sources[-1] == 1031, "the chain must stop before the client's h281/h65"
    # Both `Client_FinishPlayersProfileData` passes have to be in it.
    finishes = [
        src for src in sources
        if 110 in {h for h, _p in parse_actor_rpc_fields(
            [int(c) for c in stream[src]["payload"]])}
    ]
    assert finishes == [569, 858], finishes
    # Every source is a real, unopened ch2 bunch carrying only profile RPCs.
    for source_index, _delay, bits, digest in full:
        source = stream[source_index]
        assert source["chIndex"] == 2 and not source.get("bOpen")
        assert source["bits"] == bits
        assert hashlib.sha256(source["payload"].encode("ascii")).hexdigest() == digest
        handles = {h for h, _p in parse_actor_rpc_fields(
            [int(c) for c in source["payload"]])}
        assert handles and handles <= profile_handles, (source_index, handles)
    assert set(srvmod.STRICT_PROFILE_PROLOGUE_SOURCES) <= set(sources)

    # Default mode stays the two-bunch opener.
    srv, _conn, _sock, _addr = _fixture(WW3_PROFILE_PROLOGUE="1")
    assert [s[0] for s in srv.profile_prologue_specs()] == [204, 321]

    # `full` replays the whole chain, in capture order, bit-exact, on ch2.
    srv, conn, sock, addr = _fixture(WW3_PROFILE_PROLOGUE="1",
                                     WW3_PROFILE_PROLOGUE_MODE="full",
                                     WW3_PROFILE_PROLOGUE_DELAY_S="0",
                                     WW3_PROFILE_PROLOGUE_STEP_S="0.05")
    assert [s[0] for s in srv.profile_prologue_specs()] == sources
    t0 = time.time()
    conn._ownership_done = True
    conn._ownership_done_t = t0
    assert srv.maybe_service_profile_prologue(sock, addr, conn, now=t0) is True
    assert len(_bunches(sock)) == 1, "the step delay must pace the chain"
    assert srv.maybe_service_profile_prologue(
        sock, addr, conn, now=t0 + 0.05 * len(sources)) is True
    sent = _bunches(sock)
    assert len(sent) == len(sources)
    for bunch, source_index in zip(sent, sources):
        source = stream[source_index]
        assert bunch["chIndex"] == 2
        assert bunch["bReliable"] == source["bReliable"] == 1
        assert bunch["bOpen"] == 0 and bunch["bPartial"] == 0
        assert _payload_bits(bunch) == [int(x) for x in source["payload"]]
    assert conn._profile_prologue_done is True
    before = len(sock.sent)
    assert srv.maybe_service_profile_prologue(sock, addr, conn, now=t0 + 600) is False
    assert len(sock.sent) == before
    print(f"[ok] profile prologue full mode replays {len(sources)} captured "
          "bunches incl. both h110 finishes")


def test_ps_master_link_and_lock_vehicle_reply_are_opt_in_bit_exact():
    """The two ch7 PlayerState updates the capture sends before h281/h65.

    `_decode_all_blocks.py --ch 7` over the whole capture finds exactly three
    local-PlayerState bunches before the client reports InGame: the open
    (src 20/21) and then

        src 372  h54 bIsConnectedToMaster = true   (right after the first h279)
        src 888  h40 LockVehicleMode = 3           (the reply to C->S PS h71)

    Our bootstrap sends only the open, so the client's PlayerState never reports
    itself connected to the master — which is what `PlayerState: false` in the
    client synchronization checklist means (the printer has a separate `nullptr`
    spelling for a missing object).  Both bunches are UNRELIABLE in the capture
    and must stay that way on the wire.
    """
    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
    for source_index, bits, digest in (
        (srvmod.PS_MASTER_LINK_SOURCE, srvmod.PS_MASTER_LINK_BITS,
         srvmod.PS_MASTER_LINK_SHA256),
        (srvmod.PS_LOCK_VEHICLE_REPLY_SOURCE, srvmod.PS_LOCK_VEHICLE_REPLY_BITS,
         srvmod.PS_LOCK_VEHICLE_REPLY_SHA256),
    ):
        source = stream[source_index]
        assert source["chIndex"] == 7 and source["bits"] == bits
        assert source["bReliable"] == 0, "capture sends these unreliable"
        assert not source.get("bOpen") and not source.get("bPartial")
        assert hashlib.sha256(source["payload"].encode("ascii")).hexdigest() == digest

    # Off by default.
    srv, conn, sock, addr = _fixture()
    conn.ps_opened, conn.ps_channel = True, 17
    assert srv.maybe_send_ps_master_link(sock, addr, conn) is False
    assert srv.maybe_send_lock_vehicle_reply(sock, addr, conn) is False
    assert not sock.sent

    # On: bit-exact, unreliable, on the *identified* PS channel, once each.
    srv, conn, sock, addr = _fixture(WW3_PS_MASTER_LINK="1",
                                     WW3_PS_LOCK_VEHICLE_REPLY="1")
    conn.ps_opened, conn.ps_channel = True, 17
    assert srv.maybe_send_ps_master_link(sock, addr, conn) is True
    assert srv.maybe_send_ps_master_link(sock, addr, conn) is False
    assert srv.maybe_send_lock_vehicle_reply(sock, addr, conn) is True
    assert srv.maybe_send_lock_vehicle_reply(sock, addr, conn) is False
    sent = _bunches(sock)
    assert len(sent) == 2
    for bunch, source_index in zip(
            sent, (srvmod.PS_MASTER_LINK_SOURCE, srvmod.PS_LOCK_VEHICLE_REPLY_SOURCE)):
        source = stream[source_index]
        assert bunch["chIndex"] == 17, "must follow PS identity, not capture ch7"
        assert bunch["bReliable"] == 0
        assert bunch["bOpen"] == 0 and bunch["bPartial"] == 0
        assert _payload_bits(bunch) == [int(x) for x in source["payload"]]

    # Without an identified PlayerState channel nothing may go out.
    srv, conn, sock, addr = _fixture(WW3_PS_MASTER_LINK="1")
    conn.ps_opened = False
    assert srv.maybe_send_ps_master_link(sock, addr, conn) is False
    assert not sock.sent

    # The client's first h279 is the capture's own trigger for src 372.
    srv, conn, sock, addr = _fixture(WW3_PS_MASTER_LINK="1")
    conn.ps_opened, conn.ps_channel = True, 7
    srv.handle_bunch(sock, addr, conn, _controller_rpc_bunch(279))
    ps_bunches = [b for b in _bunches(sock) if b["chIndex"] == 7]
    assert len(ps_bunches) == 1
    assert _payload_bits(ps_bunches[0]) == [
        int(x) for x in stream[srvmod.PS_MASTER_LINK_SOURCE]["payload"]]
    print("[ok] PS master link (src 372) and LockVehicleMode reply (src 888) are "
          "opt-in, unreliable and bit-exact")


def test_strict_h71_fallback_and_real_h65_cancellation():
    # No h65: the first h71 arms a captured-delta fallback and it fires once.
    srv, conn, sock, addr = _fixture(WW3_STRICT_PLAYER_IN_GAME_ORDER="1")
    conn.ps_opened = True
    conn.ps_channel = 17
    h71 = _playerstate_rpc_bunch(17, 71, [1])
    assert srv.handle_bunch(sock, addr, conn, h71) is False
    due = conn._strict_h65_fallback_at
    assert due > 0
    assert srv.handle_bunch(sock, addr, conn, h71) is False
    assert conn._strict_h65_fallback_at == due, "duplicate h71 must not re-arm the timer"
    assert srv.maybe_service_strict_player_in_game(sock, addr, conn, now=due + 0.001) is True
    assert parse_actor_rpc_fields(_payload_bits(_bunches(sock)[0]), value_max=82) == [(30, [1])]
    assert conn._strict_h65_synthetic is True
    count = len(sock.sent)
    assert srv.maybe_service_strict_player_in_game(sock, addr, conn, now=due + 0.002) is False
    assert len(sock.sent) == count

    # Real h65 before the deadline cancels the fallback; only its one h30 is sent.
    srv2, conn2, sock2, addr2 = _fixture(WW3_STRICT_PLAYER_IN_GAME_ORDER="1")
    conn2.ps_opened = True
    conn2.ps_channel = 17
    assert srv2.handle_bunch(sock2, addr2, conn2, h71) is False
    old_due = conn2._strict_h65_fallback_at
    assert srv2.handle_bunch(sock2, addr2, conn2, _playerstate_rpc_bunch(17, 65)) is True
    assert conn2._strict_h65_fallback_at == 0
    assert srv2.maybe_service_strict_player_in_game(sock2, addr2, conn2,
                                                    now=old_due + 0.001) is True
    h30_count = sum(
        parse_actor_rpc_fields(_payload_bits(b), value_max=82) == [(30, [1])]
        for b in _bunches(sock2) if b["chIndex"] == 17)
    assert h30_count == 1
    print("[ok] strict h71 fallback fires once; real h65 cancels synthetic readiness")


def test_team_sync_bind_is_opt_in_one_shot_and_fails_closed():
    """The non-empty `TM_Synchronize` that can make `CurrentSquad` valid.

    Unlike the empty probe this one *changes client state*: its slot record
    satisfies `0x1409739b0`'s bind predicate, so the client will resolve its own
    `AWW3PlayerState` and call `SetCurrentSquad`.  That makes every gate below
    load-bearing -- it must never fire without the channel that carries it, must
    go out exactly once, must be bit-identical to the pure builder, and must
    refuse outright if the payload or the identity it was configured with is not
    the reviewed one.
    """
    import action_replicator as ar

    expected_bits = ar.build_client_receive_packet_bits(
        ar.build_local_bind_packet(811019, 1, name=""))

    # 1. Off by default.
    srv, conn, sock, addr = _fixture()
    conn._action_replicator_done = True
    conn._action_replicator_done_t = time.time() - 100
    conn._last_client_bunch_t = time.time()
    assert srv.maybe_send_team_sync_bind(sock, addr, conn) is False
    assert not sock.sent

    # 2. On, but ch80 was never opened -> stay silent.
    srv, conn, sock, addr = _fixture(WW3_TEAM_SYNC_BIND="1",
                                     WW3_TEAM_SYNC_BIND_DELAY_S="0")
    conn._last_client_bunch_t = time.time()
    assert srv.maybe_send_team_sync_bind(sock, addr, conn) is False
    assert not sock.sent

    # 3. Channel open, arm delay not elapsed.
    srv, conn, sock, addr = _fixture(WW3_TEAM_ACTION_REPLICATOR="1",
                                     WW3_TEAM_SYNC_BIND="1",
                                     WW3_TEAM_SYNC_BIND_DELAY_S="2.0")
    t0 = time.time()
    conn._action_replicator_done = True
    conn._action_replicator_done_t = t0
    conn._last_client_bunch_t = t0 + 2.0
    assert srv.maybe_send_team_sync_bind(sock, addr, conn, now=t0 + 1.0) is False
    assert not sock.sent

    # 4. Fires once, on ch80, reliable, whole, no exports, bit-exact.
    assert srv.maybe_send_team_sync_bind(sock, addr, conn, now=t0 + 2.0) is True
    sent = _bunches(sock)
    assert len(sent) == 1
    bunch = sent[0]
    assert bunch["chIndex"] == 80
    assert bunch["chType"] == cc.CHTYPE_ACTOR
    assert bunch["bReliable"] == 1
    assert bunch["bOpen"] == 0
    assert bunch["bPartial"] == 0
    assert bunch["bHasPackageMapExports"] == 0
    assert _payload_bits(bunch) == expected_bits

    # The handle must decode with ch80's ClassNetCache and carry the 79-byte packet.
    fields = ar.parse_action_replicator_fields(_payload_bits(bunch))
    assert [h for h, _p in fields] == [ar.RPC_CLIENT_RECEIVE_PACKET]
    body = Bits(fields[0][1])
    assert body.bit() == 1 and body.read(16) == ar.LOCAL_BIND_PACKET_BYTES
    packet = bytes(body.read(8) for _ in range(ar.LOCAL_BIND_PACKET_BYTES))
    assert packet == ar.build_local_bind_packet(811019, 1, name="")

    # And the slot it carries really would bind, by the native predicate.
    teams, _flag, _cfg = ar.read_tm_synchronize_body(
        ar.read_action_packet(packet)["body"][1:])
    slot = teams[0].squads[0].slots[0]
    assert ar.slot_binds_to(slot, 811019, 1)

    # 5. Exactly once.
    before = len(sock.sent)
    assert srv.maybe_send_team_sync_bind(sock, addr, conn, now=t0 + 60.0) is False
    assert len(sock.sent) == before

    # 6. Fails closed when the payload is not the reviewed one.
    srv, conn, sock, addr = _fixture(WW3_TEAM_ACTION_REPLICATOR="1",
                                     WW3_TEAM_SYNC_BIND="1",
                                     WW3_TEAM_SYNC_BIND_DELAY_S="0")
    conn._action_replicator_done = True
    conn._action_replicator_done_t = time.time() - 100
    conn._last_client_bunch_t = time.time()
    good = srvmod.TEAM_SYNC_BIND_PACKET_SHA256
    try:
        srvmod.TEAM_SYNC_BIND_PACKET_SHA256 = "00" * 32
        assert srv.maybe_send_team_sync_bind(sock, addr, conn) is False
        assert not sock.sent
    finally:
        srvmod.TEAM_SYNC_BIND_PACKET_SHA256 = good

    # 7. An identity that cannot bind is refused rather than transmitted.
    srv, conn, sock, addr = _fixture(WW3_TEAM_ACTION_REPLICATOR="1",
                                     WW3_TEAM_SYNC_BIND="1",
                                     WW3_TEAM_SYNC_BIND_DELAY_S="0",
                                     WW3_TEAM_SYNC_BIND_UNIQUE_ID="0")
    conn._action_replicator_done = True
    conn._action_replicator_done_t = time.time() - 100
    conn._last_client_bunch_t = time.time()
    assert srv.maybe_send_team_sync_bind(sock, addr, conn) is False
    assert not sock.sent
    print("OK ch80 TM_Synchronize bind is opt-in, one-shot, bit-exact, fails closed")


def test_team_sync_bind_waits_for_a_live_client_and_for_the_probe():
    """Liveness, and deterministic ordering behind the transport probe.

    `_client_alive_probe.py` showed three turns of experiments fired into a
    client whose net thread had already stopped.  And when the empty probe is
    also enabled, the bind must follow its ack so a live A/B can attribute any
    change to the payload rather than to the transport.
    """
    srv, conn, sock, addr = _fixture(WW3_TEAM_ACTION_REPLICATOR="1",
                                     WW3_TEAM_SYNC_BIND="1",
                                     WW3_TEAM_SYNC_BIND_DELAY_S="0",
                                     WW3_TEAM_SYNC_BIND_LIVENESS_S="2.0")
    t0 = time.time()
    conn._action_replicator_done = True
    conn._action_replicator_done_t = t0 - 10

    assert srv.maybe_send_team_sync_bind(sock, addr, conn, now=t0) is False   # never heard
    conn._last_client_bunch_t = t0 - 5.0
    assert srv.maybe_send_team_sync_bind(sock, addr, conn, now=t0) is False   # stale
    assert not sock.sent
    conn._last_client_bunch_t = t0 - 0.5
    assert srv.maybe_send_team_sync_bind(sock, addr, conn, now=t0) is True
    assert len(_bunches(sock)) == 1

    # With the probe enabled, the bind holds until the probe has actually gone out.
    srv2, conn2, sock2, addr2 = _fixture(WW3_TEAM_ACTION_REPLICATOR="1",
                                         WW3_ACTION_PROBE="1",
                                         WW3_TEAM_SYNC_BIND="1",
                                         WW3_TEAM_SYNC_BIND_DELAY_S="0",
                                         WW3_ACTION_PROBE_DELAY_S="0")
    conn2._action_replicator_done = True
    conn2._action_replicator_done_t = t0 - 10
    conn2._last_client_bunch_t = t0 - 0.5
    assert srv2.maybe_send_team_sync_bind(sock2, addr2, conn2, now=t0) is False
    assert not sock2.sent
    assert srv2.maybe_send_action_probe(sock2, addr2, conn2, now=t0) is True
    assert srv2.maybe_send_team_sync_bind(sock2, addr2, conn2, now=t0) is True
    assert len(_bunches(sock2)) == 2
    print("OK ch80 TM_Synchronize bind waits for a live client and for the probe")


def test_inv_sync_bind_is_opt_in_one_shot_bit_exact_and_fails_closed():
    """The ch3 `SvReplicatedInventory` block that can flip the last two bits.

    `_delegate_live.py` proves `0x1411c0f30` is bound to the delegate at
    `UWW3InventoryManagerBase+0xF0`; `_delegate_broadcast_scan.py` finds exactly
    two sites broadcasting it, both gated on
    `UWW3InventoryManagerBase::IsSynchronized` (0x140c37770); and
    `_inv_sync_gates.py` reads the three inputs that predicate needs as
    unsatisfied on the live client.  This block supplies them, so -- like the
    TM_Synchronize bind -- it changes client state and every gate is
    load-bearing.
    """
    import inventory_sync as inv

    expected_bits = inv.build_inventory_sync_block_bits()

    # 1. Off by default.
    srv, conn, sock, addr = _fixture()
    conn._ownership_done_t = time.time() - 100
    conn._last_client_bunch_t = time.time()
    assert srv.maybe_send_inv_sync_bind(sock, addr, conn) is False
    assert not sock.sent

    # 2. On, but ownership never completed -> stay silent.
    srv, conn, sock, addr = _fixture(WW3_INV_SYNC_BIND="1",
                                     WW3_INV_SYNC_BIND_DELAY_S="0")
    conn._last_client_bunch_t = time.time()
    assert srv.maybe_send_inv_sync_bind(sock, addr, conn) is False
    assert not sock.sent

    # 3. Ownership done, arm delay not elapsed.
    srv, conn, sock, addr = _fixture(WW3_INV_SYNC_BIND="1",
                                     WW3_INV_SYNC_BIND_DELAY_S="2.0")
    t0 = time.time()
    conn._ownership_done_t = t0
    conn._last_client_bunch_t = t0 + 2.0
    assert srv.maybe_send_inv_sync_bind(sock, addr, conn, now=t0 + 1.0) is False
    assert not sock.sent

    # 4. Fires once, on ch3, reliable, whole, no exports, bit-exact.
    assert srv.maybe_send_inv_sync_bind(sock, addr, conn, now=t0 + 2.0) is True
    sent = _bunches(sock)
    assert len(sent) == 1
    bunch = sent[0]
    assert bunch["chIndex"] == 3
    assert bunch["chType"] == cc.CHTYPE_ACTOR
    assert bunch["bReliable"] == 1
    assert bunch["bOpen"] == 0
    assert bunch["bPartial"] == 0
    assert bunch["bHasPackageMapExports"] == 0
    assert _payload_bits(bunch) == expected_bits

    # 5. Exactly once.
    before = len(sock.sent)
    assert srv.maybe_send_inv_sync_bind(sock, addr, conn, now=t0 + 60.0) is False
    assert len(sock.sent) == before

    # 6. Fails closed when the payload is not the reviewed one.
    srv, conn, sock, addr = _fixture(WW3_INV_SYNC_BIND="1",
                                     WW3_INV_SYNC_BIND_DELAY_S="0")
    conn._ownership_done_t = time.time() - 100
    conn._last_client_bunch_t = time.time()
    good = srvmod.INV_SYNC_PACKET_SHA256
    try:
        srvmod.INV_SYNC_PACKET_SHA256 = "00" * 32
        assert srv.maybe_send_inv_sync_bind(sock, addr, conn) is False
        assert not sock.sent
    finally:
        srvmod.INV_SYNC_PACKET_SHA256 = good

    # 7. A struct that provably cannot satisfy the native predicate is refused.
    srv, conn, sock, addr = _fixture(WW3_INV_SYNC_BIND="1",
                                     WW3_INV_SYNC_BIND_DELAY_S="0",
                                     WW3_INV_SYNC_BIND_MODE="bogus")
    conn._ownership_done_t = time.time() - 100
    conn._last_client_bunch_t = time.time()
    assert srv.maybe_send_inv_sync_bind(sock, addr, conn) is False
    assert not sock.sent
    print("OK ch3 SvReplicatedInventory bind is opt-in, one-shot, bit-exact, fails closed")


def test_inv_sync_bind_waits_for_a_live_client():
    """Same liveness rule as every other one-shot: never spend it on a client
    whose net thread has stopped (`_client_alive_probe.py`)."""
    srv, conn, sock, addr = _fixture(WW3_INV_SYNC_BIND="1",
                                     WW3_INV_SYNC_BIND_DELAY_S="0",
                                     WW3_INV_SYNC_BIND_LIVENESS_S="2.0")
    t0 = time.time()
    conn._ownership_done_t = t0 - 10
    assert srv.maybe_send_inv_sync_bind(sock, addr, conn, now=t0) is False   # never heard
    conn._last_client_bunch_t = t0 - 5.0
    assert srv.maybe_send_inv_sync_bind(sock, addr, conn, now=t0) is False   # stale
    assert not sock.sent
    conn._last_client_bunch_t = t0 - 0.5
    assert srv.maybe_send_inv_sync_bind(sock, addr, conn, now=t0) is True
    assert len(_bunches(sock)) == 1
    print("OK ch3 SvReplicatedInventory bind waits for a live client")


def _capture_1934_payload():
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "real_replay_stream.json"), encoding="utf-8") as fh:
        return json.load(fh)[srvmod.STRICT_TRANSITION_SOURCE]["payload"]


def _deploy_ready_conn(srv, conn, t0):
    """The exact client-side evidence turn 8 measured on the live session."""
    conn._strict_profiles_complete = True
    conn._client_map_opened = True
    conn._client_map_opened_t = t0
    conn._client_player_in_game = True
    conn._last_client_bunch_t = t0
    return conn


def test_deploy_release_is_opt_in_one_shot_and_replays_capture_1934():
    """Release the captured deploy transition on client evidence, not on h279.

    Turn 8 measured the deadlock exactly: with `WW3_STRICT_PLAYER_IN_GAME_ORDER=1`
    the profile chain completes and the server then waits for a *fresh* h279
    before it will release captured source 1934.  In the capture that h279
    arrives right after the human presses DEPLOY -- but our client cannot press
    DEPLOY (`ClRespawnTarget` is NULL, `_deploy_gates_live.py`), and it already
    spent its only h279 before the profile chain finished.  So the client sits on
    the deploy screen waiting for the server while the server waits for the
    client.

    This releases the same bit-exact, SHA-pinned bunch on evidence the client has
    actually produced -- h281 `Server_OnMapOpened` and PS h65
    `Server_PlayerInGameNotify` -- instead of on an event that can no longer
    happen.  It adds no new bytes to the wire: identity validation still runs
    inside `maybe_send_late_transition`.
    """
    capture_payload = _capture_1934_payload()
    assert len(capture_payload) == srvmod.STRICT_TRANSITION_BITS

    # 1. Off by default, even with every precondition satisfied.
    t0 = time.time()
    srv, conn, sock, addr = _fixture(WW3_STRICT_PLAYER_IN_GAME_ORDER="1")
    _deploy_ready_conn(srv, conn, t0 - 100)
    assert srv.maybe_release_deploy_transition(sock, addr, conn, now=t0) is False
    assert not sock.sent

    # 2. On, but the client never reported Server_OnMapOpened.
    srv, conn, sock, addr = _fixture(WW3_STRICT_PLAYER_IN_GAME_ORDER="1",
                                     WW3_DEPLOY_RELEASE="1",
                                     WW3_DEPLOY_RELEASE_DELAY_S="0")
    _deploy_ready_conn(srv, conn, t0 - 100)
    conn._client_map_opened = False
    assert srv.maybe_release_deploy_transition(sock, addr, conn, now=t0) is False
    assert not sock.sent

    # 3. Map opened, but no PS h65 -- the client is not in game yet.
    srv, conn, sock, addr = _fixture(WW3_STRICT_PLAYER_IN_GAME_ORDER="1",
                                     WW3_DEPLOY_RELEASE="1",
                                     WW3_DEPLOY_RELEASE_DELAY_S="0")
    _deploy_ready_conn(srv, conn, t0 - 100)
    conn._client_player_in_game = False
    assert srv.maybe_release_deploy_transition(sock, addr, conn, now=t0) is False
    assert not sock.sent

    # 4. Strict order on but its profile chain has not completed -- never jump it.
    srv, conn, sock, addr = _fixture(WW3_STRICT_PLAYER_IN_GAME_ORDER="1",
                                     WW3_DEPLOY_RELEASE="1",
                                     WW3_DEPLOY_RELEASE_DELAY_S="0")
    _deploy_ready_conn(srv, conn, t0 - 100)
    conn._strict_profiles_complete = False
    assert srv.maybe_release_deploy_transition(sock, addr, conn, now=t0) is False
    assert not sock.sent

    # 5. All evidence present, arm delay not yet elapsed.
    srv, conn, sock, addr = _fixture(WW3_STRICT_PLAYER_IN_GAME_ORDER="1",
                                     WW3_DEPLOY_RELEASE="1",
                                     WW3_DEPLOY_RELEASE_DELAY_S="3.0")
    _deploy_ready_conn(srv, conn, t0)
    conn._last_client_bunch_t = t0 + 1.0
    assert srv.maybe_release_deploy_transition(sock, addr, conn, now=t0 + 1.0) is False
    assert not sock.sent

    # 6. Fires exactly once, and is the captured bunch bit for bit.
    conn._last_client_bunch_t = t0 + 3.0
    assert srv.maybe_release_deploy_transition(sock, addr, conn, now=t0 + 3.0) is True
    sent = _bunches(sock)
    assert len(sent) == 1, f"expected one bunch, got {len(sent)}"
    b = sent[0]
    assert b["chIndex"] == 2
    assert b["bOpen"] == 0 and b["bClose"] == 0
    assert b["bReliable"] == 1
    assert b["bPartial"] == 0
    assert b["bunchDataBits"] == srvmod.STRICT_TRANSITION_BITS
    got = "".join(str(x) for x in _payload_bits(b))
    assert got == capture_payload, "released bunch is not capture source 1934"
    assert hashlib.sha256(got.encode("ascii")).hexdigest() == \
        srvmod.STRICT_TRANSITION_SHA256

    # 7. One-shot: a second call is silent even though everything still holds.
    before = len(sock.sent)
    assert srv.maybe_release_deploy_transition(sock, addr, conn, now=t0 + 9.0) is False
    assert len(sock.sent) == before
    print("OK deploy release is opt-in, one-shot and bit-exact capture src 1934")


def test_deploy_release_refuses_a_silent_client():
    """A one-shot must not be spent on a client that has stopped transmitting.

    `_client_alive_probe.py` was written because three turns of experiments were
    fired into a wedged client.  The deploy transition is the most expensive
    one-shot in the server -- it can only be released once per connection -- so it
    gets the same liveness gate as the other one-shots.
    """
    t0 = time.time()
    srv, conn, sock, addr = _fixture(WW3_STRICT_PLAYER_IN_GAME_ORDER="1",
                                     WW3_DEPLOY_RELEASE="1",
                                     WW3_DEPLOY_RELEASE_DELAY_S="0",
                                     WW3_DEPLOY_RELEASE_LIVENESS_S="2.0")
    _deploy_ready_conn(srv, conn, t0 - 100)

    conn._last_client_bunch_t = 0                       # never heard from
    assert srv.maybe_release_deploy_transition(sock, addr, conn, now=t0) is False
    conn._last_client_bunch_t = t0 - 5.0                # stale
    assert srv.maybe_release_deploy_transition(sock, addr, conn, now=t0) is False
    assert not sock.sent
    conn._last_client_bunch_t = t0 - 0.5                # live
    assert srv.maybe_release_deploy_transition(sock, addr, conn, now=t0) is True
    assert len(_bunches(sock)) == 1
    print("OK deploy release refuses a silent client")


def test_deploy_release_fires_immediately_on_the_captures_own_trigger():
    """h287 `Server_RequestRespawnAtCapturePoint` is what the capture answers.

    In `24July26/W3_match_full_2.pcapng` the client presses DEPLOY (C->S h287,
    src~1841) and the server answers with source 1934.  That is the faithful
    trigger, so when the client can produce it, it must win: no arming delay, and
    it must not be gated on the h281/h65 fallback evidence at all.
    """
    t0 = time.time()
    srv, conn, sock, addr = _fixture(WW3_STRICT_PLAYER_IN_GAME_ORDER="1",
                                     WW3_DEPLOY_RELEASE="1",
                                     WW3_DEPLOY_RELEASE_DELAY_S="600")
    conn._strict_profiles_complete = True
    conn._last_client_bunch_t = t0
    # No h281, no h65 -- the fallback evidence is absent on purpose.
    assert srv.maybe_release_deploy_transition(sock, addr, conn, now=t0) is False
    assert not sock.sent

    assert srv.note_client_respawn_requested(conn) is True
    assert conn._client_respawn_requested is True
    assert srv.maybe_release_deploy_transition(sock, addr, conn, now=t0) is True
    sent = _bunches(sock)
    assert len(sent) == 1
    assert sent[0]["bunchDataBits"] == srvmod.STRICT_TRANSITION_BITS
    got = "".join(str(x) for x in _payload_bits(sent[0]))
    assert got == _capture_1934_payload()
    print("OK deploy release fires immediately on C->S h287 (capture's own trigger)")


def test_deploy_release_still_refuses_a_silent_client_on_the_h287_path():
    """Even the faithful trigger must not be spent on a client that went quiet."""
    t0 = time.time()
    srv, conn, sock, addr = _fixture(WW3_STRICT_PLAYER_IN_GAME_ORDER="1",
                                     WW3_DEPLOY_RELEASE="1",
                                     WW3_DEPLOY_RELEASE_LIVENESS_S="2.0")
    conn._strict_profiles_complete = True
    srv.note_client_respawn_requested(conn)
    conn._last_client_bunch_t = t0 - 30.0
    assert srv.maybe_release_deploy_transition(sock, addr, conn, now=t0) is False
    assert not sock.sent
    print("OK h287 path still honours the liveness gate")


def test_deploy_release_records_client_map_opened_and_in_game():
    """The evidence the release depends on must actually be recorded from the wire."""
    srv, conn, sock, addr = _fixture()
    assert getattr(conn, "_client_map_opened", False) is False
    assert getattr(conn, "_client_player_in_game", False) is False

    srv.note_client_map_opened(conn, now=1000.0)
    assert conn._client_map_opened is True
    assert conn._client_map_opened_t == 1000.0
    srv.note_client_map_opened(conn, now=2000.0)          # first sighting wins
    assert conn._client_map_opened_t == 1000.0

    srv.note_client_player_in_game(conn)
    assert conn._client_player_in_game is True
    print("OK client map-opened / in-game evidence is recorded")


def test_deploy_after_spectator_holds_source1934_until_h310():
    """Turn 8's run spent source 1934 *before* the client started spectating.

    Measured, not inferred, in
    `live_log/match_console_20260809_2315_WORLDFILL_DEPLOY.out.txt`:

    ```
    line 2086  *** M4: captured late transition replayed (stream index 1934) ***
    line 2087  *** strict order: fresh post-profile h279 accepted; released once ***
    line 2344  *** client ch2 RPC handles=[281, 200, 200] ***   deploy screen up
    line 2374  *** client ch2 RPC handles=[208, 310] ***        Server_StartSpectator
    ```

    Source 1934 is the capture's *leave spectator and possess* bundle
    (`Client_OnStopSpectatorBeforeDeploy`, `Client_StopSpectator`,
    `ClientSetViewTarget`, `ClientRestart(9372)`, `ClientSetViewTarget`,
    `ClientSetCameraMode`, `ClientSetRotation`).  Delivering it 288 log lines
    *before* the client entered spectator meant the client restarted, then
    followed its own flow back onto the deploy screen and into spectator -- where
    it has been flooding h73 `ServerSetSpectatorLocation` ever since.

    In the capture the bundle always answers a client that is already spectating
    (h310 at src~1626, source 1934 at src 1934).  This mode reverses the proven
    bad ordering with one rule and no new bytes: hold source 1934 -- from *every*
    sender, including `force=True`, the strict fresh-h279 path and the timers --
    until the client has actually sent h310, then release the same SHA-pinned
    bunch exactly once.
    """
    capture_payload = _capture_1934_payload()
    t0 = time.time()

    # 1. Off by default: the strict fresh-h279 path still releases immediately,
    #    so this mode cannot change any existing run that does not ask for it.
    srv, conn, sock, addr = _fixture(WW3_STRICT_PLAYER_IN_GAME_ORDER="1")
    conn._strict_post_profile_h279_ready = True
    assert srv.maybe_send_late_transition(sock, addr, conn, force=True) is True
    assert len(_bunches(sock)) == 1

    # 2. On: the central hold covers force=True and the strict h279 path.
    srv, conn, sock, addr = _fixture(WW3_STRICT_PLAYER_IN_GAME_ORDER="1",
                                     WW3_DEPLOY_AFTER_SPECTATOR="1")
    conn._strict_post_profile_h279_ready = True
    assert srv.maybe_send_late_transition(sock, addr, conn, force=True) is False
    assert srv.maybe_send_late_transition(sock, addr, conn, force=False) is False
    assert not sock.sent
    assert getattr(conn, "_strict_transition_done", False) is False

    # 3. The h281/h65 evidence fallback cannot jump it either.  The client is
    #    live throughout -- it floods h73 ServerSetSpectatorLocation -- so the
    #    liveness gate is satisfied and the hold is the only thing refusing.
    _deploy_ready_conn(srv, conn, t0 - 100)
    conn._last_client_bunch_t = t0
    assert srv.maybe_release_deploy_transition(sock, addr, conn, now=t0) is False
    assert not sock.sent

    # 4. Nor can the capture's own h287 trigger, while h310 is still outstanding.
    #    A held release must not consume the one-shot.
    assert srv.note_client_respawn_requested(conn) is True
    assert srv.maybe_release_deploy_transition(sock, addr, conn, now=t0) is False
    assert not sock.sent
    assert getattr(conn, "_deploy_release_done", False) is False

    # 5. h310 releases it, bit for bit, exactly once.
    assert srv.note_client_start_spectator(conn, now=t0) is True
    assert srv.maybe_release_deploy_transition(sock, addr, conn, now=t0) is True
    sent = _bunches(sock)
    assert len(sent) == 1, f"expected one bunch, got {len(sent)}"
    b = sent[0]
    assert b["chIndex"] == 2
    assert b["bOpen"] == 0 and b["bClose"] == 0
    assert b["bReliable"] == 1
    assert b["bPartial"] == 0
    assert b["bunchDataBits"] == srvmod.STRICT_TRANSITION_BITS
    got = "".join(str(x) for x in _payload_bits(b))
    assert got == capture_payload, "released bunch is not capture source 1934"
    assert hashlib.sha256(got.encode("ascii")).hexdigest() == \
        srvmod.STRICT_TRANSITION_SHA256

    # 6. One-shot, and the hold does not resurrect afterwards.
    before = len(sock.sent)
    assert srv.maybe_release_deploy_transition(sock, addr, conn, now=t0 + 9.0) is False
    assert srv.maybe_send_late_transition(sock, addr, conn, force=True) is False
    assert len(sock.sent) == before
    print("OK source 1934 is held until C->S h310 and then released once")


def test_deploy_after_spectator_needs_no_h281_or_h65():
    """The live run that produced h310 never sent a real PS h65 at all.

    Its strict sequence started from the synthetic h71 timeout
    (`*** strict player-in-game order started from synthetic readiness after h71
    timeout ***`) and `handles=[65]` appears nowhere in the 33 244-line console.
    So the h281/h65 evidence fallback must not be a precondition of this mode --
    h310 is the trigger, and it is sufficient on its own.
    """
    t0 = time.time()
    srv, conn, sock, addr = _fixture(WW3_STRICT_PLAYER_IN_GAME_ORDER="1",
                                     WW3_DEPLOY_AFTER_SPECTATOR="1",
                                     WW3_DEPLOY_RELEASE_DELAY_S="600")
    conn._strict_profiles_complete = True
    conn._last_client_bunch_t = t0
    assert getattr(conn, "_client_map_opened", False) is False
    assert getattr(conn, "_client_player_in_game", False) is False

    srv.note_client_start_spectator(conn, now=t0)
    assert srv.maybe_release_deploy_transition(sock, addr, conn, now=t0) is True
    sent = _bunches(sock)
    assert len(sent) == 1
    assert "".join(str(x) for x in _payload_bits(sent[0])) == _capture_1934_payload()
    print("OK h310 alone releases the transition; no h281/h65 required")


def test_deploy_after_spectator_honours_delay_liveness_and_strict_profiles():
    """The new trigger inherits every guard the existing one-shots already have."""
    t0 = time.time()

    # Strict profile chain incomplete -- never jump the experiment it layers on.
    srv, conn, sock, addr = _fixture(WW3_STRICT_PLAYER_IN_GAME_ORDER="1",
                                     WW3_DEPLOY_AFTER_SPECTATOR="1")
    conn._last_client_bunch_t = t0
    srv.note_client_start_spectator(conn, now=t0)
    conn._strict_profiles_complete = False
    assert srv.maybe_release_deploy_transition(sock, addr, conn, now=t0) is False
    assert not sock.sent
    conn._strict_profiles_complete = True

    # A settle delay after h310, when one is asked for.
    srv, conn, sock, addr = _fixture(WW3_STRICT_PLAYER_IN_GAME_ORDER="1",
                                     WW3_DEPLOY_AFTER_SPECTATOR="1",
                                     WW3_DEPLOY_AFTER_SPECTATOR_DELAY_S="2.0")
    conn._strict_profiles_complete = True
    conn._last_client_bunch_t = t0 + 1.0
    srv.note_client_start_spectator(conn, now=t0)
    assert srv.maybe_release_deploy_transition(sock, addr, conn, now=t0 + 1.0) is False
    assert not sock.sent
    conn._last_client_bunch_t = t0 + 2.5
    assert srv.maybe_release_deploy_transition(sock, addr, conn, now=t0 + 2.5) is True
    assert len(_bunches(sock)) == 1

    # A silent client still refuses the one-shot.
    srv, conn, sock, addr = _fixture(WW3_STRICT_PLAYER_IN_GAME_ORDER="1",
                                     WW3_DEPLOY_AFTER_SPECTATOR="1",
                                     WW3_DEPLOY_RELEASE_LIVENESS_S="2.0")
    conn._strict_profiles_complete = True
    srv.note_client_start_spectator(conn, now=t0)
    conn._last_client_bunch_t = t0 - 30.0
    assert srv.maybe_release_deploy_transition(sock, addr, conn, now=t0) is False
    assert not sock.sent
    conn._last_client_bunch_t = t0 - 0.5
    assert srv.maybe_release_deploy_transition(sock, addr, conn, now=t0) is True
    assert len(_bunches(sock)) == 1
    print("OK h310 release honours strict profiles, settle delay and liveness")


def test_deploy_transition_can_be_repeated_once_after_h310():
    """Holding source 1934 for h310 deadlocks; h310 is *caused* by source 1934.

    Measured this turn on a fully synchronized client (mask 0xff, h281
    `Server_OnMapOpened` and a real PS h65 `Server_PlayerInGameNotify` both on
    the wire): with the bundle held, **h310 never arrived** in 3 minutes.  Both
    runs that ever produced h208+h310 had already delivered source 1934 --

        turn 8 deploy-release:  h281 -> h65 -> 1934 -> h64 -> [208, 310]
        turn 8 world-fill:      1934 (line 2086) ... -> h281 (2344) -> [208,310] (2374)

    -- so `Client_StopSpectator` + `ClientRestart(9372)` is what moves the
    controller out of its initial state and lets the deploy screen re-enter
    spectator properly.

    The capture's shape is preserved by *repeating*, not by holding: the capture
    answers a client that is already spectating (h310 at src~1626, source 1934
    at src 1934).  So release once on the proven h281/h65 trigger, then send the
    same SHA-pinned bunch once more after h310 -- which is the capture's own
    position for it.  Bit-identical payload, one extra copy, never more.
    """
    capture_payload = _capture_1934_payload()
    t0 = time.time()

    def ready(**env):
        srv, conn, sock, addr = _fixture(**env)
        conn._strict_profiles_complete = True
        conn._last_client_bunch_t = t0
        conn._deploy_release_done = True          # 1934 already went out once
        return srv, conn, sock, addr

    # 1. Off by default.
    srv, conn, sock, addr = ready()
    srv.note_client_start_spectator(conn, now=t0)
    assert srv.maybe_repeat_deploy_transition(sock, addr, conn, now=t0) is False
    assert not sock.sent

    # 2. On, but the client has not started spectating -- this is the whole
    #    point of the repeat, so it must not fire early.
    srv, conn, sock, addr = ready(WW3_DEPLOY_REPEAT_AFTER_SPECTATOR="1")
    assert srv.maybe_repeat_deploy_transition(sock, addr, conn, now=t0) is False
    assert not sock.sent

    # 3. On, spectating, but source 1934 was never delivered in the first place:
    #    a repeat of something that never happened is not a repeat.
    srv, conn, sock, addr = ready(WW3_DEPLOY_REPEAT_AFTER_SPECTATOR="1")
    conn._deploy_release_done = False
    srv.note_client_start_spectator(conn, now=t0)
    assert srv.maybe_repeat_deploy_transition(sock, addr, conn, now=t0) is False
    assert not sock.sent

    # 4. Fires once, bit for bit.
    srv, conn, sock, addr = ready(WW3_DEPLOY_REPEAT_AFTER_SPECTATOR="1")
    srv.note_client_start_spectator(conn, now=t0)
    assert srv.maybe_repeat_deploy_transition(sock, addr, conn, now=t0) is True
    sent = _bunches(sock)
    assert len(sent) == 1
    b = sent[0]
    assert b["chIndex"] == 2 and b["bOpen"] == 0 and b["bClose"] == 0
    assert b["bReliable"] == 1 and b["bPartial"] == 0
    assert b["bunchDataBits"] == srvmod.STRICT_TRANSITION_BITS
    got = "".join(str(x) for x in _payload_bits(b))
    assert got == capture_payload
    assert hashlib.sha256(got.encode("ascii")).hexdigest() == \
        srvmod.STRICT_TRANSITION_SHA256

    # 5. One-shot -- the client floods h73 while spectating, so this is called a lot.
    before = len(sock.sent)
    assert srv.maybe_repeat_deploy_transition(sock, addr, conn, now=t0 + 30) is False
    assert len(sock.sent) == before

    # 6. Silent client still refuses it, and the settle delay is honoured.
    srv, conn, sock, addr = ready(WW3_DEPLOY_REPEAT_AFTER_SPECTATOR="1",
                                  WW3_DEPLOY_REPEAT_AFTER_SPECTATOR_DELAY_S="2.0",
                                  WW3_DEPLOY_RELEASE_LIVENESS_S="2.0")
    srv.note_client_start_spectator(conn, now=t0)
    assert srv.maybe_repeat_deploy_transition(sock, addr, conn, now=t0 + 0.5) is False
    conn._last_client_bunch_t = t0 - 30.0
    assert srv.maybe_repeat_deploy_transition(sock, addr, conn, now=t0 + 3.0) is False
    assert not sock.sent
    conn._last_client_bunch_t = t0 + 3.0
    assert srv.maybe_repeat_deploy_transition(sock, addr, conn, now=t0 + 3.0) is True
    assert len(_bunches(sock)) == 1
    print("OK source 1934 can be repeated exactly once after h310")


def test_action_replicator_is_not_opened_twice_when_world_fill_already_did():
    """`WW3_WORLD_FILL=1` already opens ch80 with the capture's own src 174+175.

    Measured this turn, from the generator rather than from a guess:

    ```
    WW3_WORLD_FILL=0: 42 bunches, ch80=0, src174=False src175=False
    WW3_WORLD_FILL=1: 260 bunches, ch80=2, src174=True  src175=True
    ```

    `WW3_TEAM_ACTION_REPLICATOR=1` then opened the *same* channel with the *same*
    two sources ~2 s later, so NetGUID 9400 was opened twice on one connection.
    The outcome is racy: turn 8 kept its `AWW3ActionReplicator` and answered the
    probe with `Server_AckActionsReceived` in 19 ms, turn 9 ended with **zero**
    live `WW3.WW3ActionReplicator` instances, no ack, no squad graph, and the
    checklist stalled at 0xfd (missing only bit1, PlayerState).

    The capture opens ch80 exactly once.  So when the bootstrap already carries
    that open, the second one must not be sent -- this removes bytes from the
    wire and moves toward the capture, it does not add anything.
    """
    ch = srvmod.TEAM_ACTION_REPLICATOR_CHANNEL
    other = [{"chIndex": 3, "bOpen": 1}, {"chIndex": ch, "bOpen": 0}]
    assert srvmod.bootstrap_opens_action_replicator(other) is False
    assert srvmod.bootstrap_opens_action_replicator([]) is False
    assert srvmod.bootstrap_opens_action_replicator(
        other + [{"chIndex": ch, "bOpen": 1}]) is True

    t0 = time.time()
    # World fill did not open it -- the standalone open still runs.
    srv, conn, sock, addr = _fixture(WW3_TEAM_ACTION_REPLICATOR="1",
                                     WW3_TEAM_ACTION_REPLICATOR_DELAY_S="0")
    conn._ownership_done_t = t0 - 10
    assert srv.maybe_service_team_action_replicator(sock, addr, conn, now=t0) is True
    assert len(_bunches(sock)) == 2
    assert all(b["chIndex"] == ch for b in _bunches(sock))

    # World fill already opened it -- no second open.  But "the queue contains
    # the open" is not "the client has the actor": the bootstrap is a 266-bunch
    # drip, and turn 9b fired the probe ~100 log lines after queueing, long
    # before ch80 came out of the queue.  The client answered nothing even
    # though the actor did eventually spawn.  So the channel only counts as
    # open once the drip has actually transmitted that bunch.
    srv, conn, sock, addr = _fixture(WW3_TEAM_ACTION_REPLICATOR="1",
                                     WW3_TEAM_ACTION_REPLICATOR_DELAY_S="0")
    conn._ownership_done_t = t0 - 10
    conn._bootstrap_opens_action_replicator = True
    assert srv.maybe_service_team_action_replicator(sock, addr, conn, now=t0) is False
    assert not sock.sent
    assert getattr(conn, "_action_replicator_done", False) is False, \
        "queued != sent; the probe must not be armed yet"

    # An unrelated bunch, and the ch80 *non*-open bunch, do not arm it.
    srv.note_replay_bunch_sent(conn, {"chIndex": 3, "bOpen": 1}, now=t0 + 1)
    srv.note_replay_bunch_sent(conn, {"chIndex": ch, "bOpen": 0}, now=t0 + 1)
    assert getattr(conn, "_action_replicator_done", False) is False

    # The drip transmits the ch80 open -- now the channel is really open, and
    # the probe's own arming delay is measured from that moment.
    srv.note_replay_bunch_sent(conn, {"chIndex": ch, "bOpen": 1}, now=t0 + 5)
    assert conn._action_replicator_done is True
    assert conn._action_replicator_done_t == t0 + 5
    assert srv.maybe_service_team_action_replicator(sock, addr, conn, now=t0 + 5) is False
    assert not sock.sent, "still must not open it a second time"

    # Reversible: turn 8 reached mask 0xff *with* the duplicate, so the old
    # behaviour has to stay reachable for attribution if this regresses.
    srv, conn, sock, addr = _fixture(WW3_TEAM_ACTION_REPLICATOR="1",
                                     WW3_TEAM_ACTION_REPLICATOR_DELAY_S="0",
                                     WW3_ACTION_REPLICATOR_ALLOW_DOUBLE_OPEN="1")
    conn._ownership_done_t = t0 - 10
    conn._bootstrap_opens_action_replicator = True
    assert srv.maybe_service_team_action_replicator(sock, addr, conn, now=t0) is True
    assert len(_bunches(sock)) == 2
    print("OK ch80 is not opened twice when the bootstrap already opened it")


def test_team_sync_bind_requires_a_dispatched_probe_not_just_a_sent_one():
    """A sent probe proves nothing; only `Server_AckActionsReceived` proves dispatch.

    Turn 9 spent the `TM_Synchronize` one-shot into a client that had no
    `AWW3ActionReplicator` at all: the probe was sent (`_action_probe_done`), its
    datagram was ACKed in 2 ms, and the client never answered handle 12.  The
    existing gate only checked `_action_probe_done`, which is 'we transmitted',
    not 'the client dispatched it' -- the exact distinction Checkpoint 18 already
    had to learn once for the inventory block.
    """
    t0 = time.time()
    srv, conn, sock, addr = _fixture(WW3_TEAM_ACTION_REPLICATOR="1",
                                     WW3_ACTION_PROBE="1",
                                     WW3_TEAM_SYNC_BIND="1",
                                     WW3_TEAM_SYNC_BIND_DELAY_S="0",
                                     WW3_TEAM_SYNC_BIND_REQUIRE_PROBE_ACK="1")
    conn._action_replicator_done = True
    conn._action_probe_done = True          # transmitted...
    conn._last_client_bunch_t = t0
    conn._ownership_done_t = t0 - 10
    assert getattr(conn, "_action_probe_acked", False) is False
    assert srv.maybe_send_team_sync_bind(sock, addr, conn, now=t0) is False
    assert not sock.sent, "the one-shot must not be spent without a dispatched probe"

    conn._action_probe_acked = True          # ...and dispatched
    assert srv.maybe_send_team_sync_bind(sock, addr, conn, now=t0) is True
    assert len(_bunches(sock)) == 1

    # Default off: existing runs keep the turn-8 behaviour exactly.
    srv, conn, sock, addr = _fixture(WW3_TEAM_ACTION_REPLICATOR="1",
                                     WW3_ACTION_PROBE="1",
                                     WW3_TEAM_SYNC_BIND="1",
                                     WW3_TEAM_SYNC_BIND_DELAY_S="0")
    conn._action_replicator_done = True
    conn._action_probe_done = True
    conn._last_client_bunch_t = t0
    conn._ownership_done_t = t0 - 10
    assert srv.maybe_send_team_sync_bind(sock, addr, conn, now=t0) is True
    print("OK team sync bind can require a dispatched (acked) probe")


def test_deploy_after_spectator_records_h310_once():
    """First sighting wins: the client floods h73 and may repeat h310."""
    srv, conn, sock, addr = _fixture()
    assert getattr(conn, "_client_start_spectator", False) is False
    assert srv.note_client_start_spectator(conn, now=1000.0) is True
    assert conn._client_start_spectator is True
    assert conn._client_start_spectator_t == 1000.0
    assert srv.note_client_start_spectator(conn, now=2000.0) is False
    assert conn._client_start_spectator_t == 1000.0
    assert srvmod.PC_RPC_START_SPECTATOR == 310
    print("OK h310 evidence is recorded once")


if __name__ == "__main__":
    try:
        test_player_in_game_notify_replies_once_on_identified_ps_channel()
        test_disabled_flag_is_reported()
        test_single_shot_restart_handle_no_retry()
        test_after_pawn_ms_gate()
        test_require_ch3_ack_gate_and_timeout()
        test_pc_set_pawn_precedes_restart()
        test_mbm_fallback_sends_executable_shot_first()
        test_mustmap_alone_is_honoured()
        test_ack_pawn_stops_everything()
        test_calibrate_ps_sends_ps_guid_not_pawn()
        test_explicit_pawn_guid_override_wins_over_calibrate()
        test_show_infantry_widget_is_opt_in_zero_arg_rpc()
        test_clear_spectator_waiting_sends_raw_false_bool()
        test_post_spectator_callback_finalizes_once_in_order()
        test_post_spectator_finalizer_replays_batch3_wam_generation_once()
        test_post_spectator_finalizer_rebinds_cam_im_after_wam_generation()
        test_post_spectator_gamestate_tail_is_bit_exact_capture()
        test_final_view_target_is_exact_capture_and_blocks_later_camera_retries()
        test_near_squad_request_gets_success_response()
        test_near_squad_success_is_disabled_by_default()
        test_eager_before_spectator_callback_is_not_duplicated()
        test_preload_marks_ready_without_consuming_deploy_by_default()
        test_strict_player_in_game_orders_h65_profiles_then_fresh_h279()
        test_profile_prologue_is_opt_in_bit_exact_and_notes_the_h177_ack()
        test_profile_prologue_full_mode_replays_the_whole_pre_h65_chain()
        test_ps_master_link_and_lock_vehicle_reply_are_opt_in_bit_exact()
        test_strict_h71_fallback_and_real_h65_cancellation()
        test_team_action_replicator_is_opt_in_bit_exact_partial_pair()
        test_action_probe_is_opt_in_one_shot_and_fails_closed()
        test_action_probe_refuses_to_fire_at_a_silent_client()
        test_client_ch80_ack_is_decoded_with_the_action_replicator_value_max()
        test_action_probe_never_touches_other_actor_channels()
        test_team_sync_bind_is_opt_in_one_shot_and_fails_closed()
        test_team_sync_bind_waits_for_a_live_client_and_for_the_probe()
        test_inv_sync_bind_is_opt_in_one_shot_bit_exact_and_fails_closed()
        test_inv_sync_bind_waits_for_a_live_client()
        test_deploy_release_is_opt_in_one_shot_and_replays_capture_1934()
        test_deploy_release_refuses_a_silent_client()
        test_deploy_release_fires_immediately_on_the_captures_own_trigger()
        test_deploy_release_still_refuses_a_silent_client_on_the_h287_path()
        test_deploy_release_records_client_map_opened_and_in_game()
        test_deploy_after_spectator_holds_source1934_until_h310()
        test_deploy_after_spectator_needs_no_h281_or_h65()
        test_deploy_after_spectator_honours_delay_liveness_and_strict_profiles()
        test_deploy_after_spectator_records_h310_once()
        test_deploy_transition_can_be_repeated_once_after_h310()
        test_action_replicator_is_not_opened_twice_when_world_fill_already_did()
        test_team_sync_bind_requires_a_dispatched_probe_not_just_a_sent_one()
        print("ALL restart gating tests passed")
    finally:
        for _k in RESTART_ENV:
            os.environ.pop(_k, None)
