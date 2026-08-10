#!/usr/bin/env python3
"""Tests for ClientRestart / AckPossession RPC helpers."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import json  # noqa: E402

from possess_rpc import (  # noqa: E402
    PC_REP_HANDLE_PAWN,
    PC_REP_HANDLE_PLAYERSTATE,
    RPC_SERVER_ACK_POSSESSION,
    RPC_SERVER_CHECK_POSSESSION,
    RPC_SERVER_CHECK_POSSESSION_RELIABLE,
    RPC_SERVER_NOTIFY_LOADED_WORLD,
    PAWN_NETGUID,
    PS_NETGUID,
    build_client_restart_bits,
    build_field_bits,
    build_object_param_bits,
    build_before_spectator_param_bits,
    build_stop_spectator_before_deploy_param_bits,
    build_character_respawn_success_param_bits,
    build_gamestate_inprogress_bits,
    build_raw_rpc_bits,
    build_object_rpc_bits,
    build_must_be_mapped_prefix,
    build_pc_set_pawn_bits,
    build_pc_set_playerstate_bits,
    handle_value_max,
    is_ack_possession_null,
    is_ack_possession_pawn,
    is_check_possession,
    parse_actor_rpc_fields,
    parse_actor_rpc_handles,
    parse_object_param,
    pc_pawn_handle,
    read_int_wrapped,
    restart_handles,
    retry_handles,
    wrapped_width,
)
from actor_channel import Bits, read_content_blocks, write_content_block  # noqa: E402
from netguid import GuidWriter  # noqa: E402


def test_client_restart_roundtrip():
    bits = build_client_restart_bits(must_be_mapped=False)
    handles = parse_actor_rpc_handles(bits)
    assert handles[0] == (39, [PAWN_NETGUID])


def test_field_header_is_wrapped_plus_payload_length():
    """UE 4.21 writes SerializeInt(handle, MaxIndex+1) then SerializeIntPacked(bits).

    Regression guard for the bug that made every crafted ClientRestart a no-op: the old
    encoder wrote a *packed* handle and no payload-length field at all, so the client read
    our NetGUID as the length and abandoned the field chain.
    """
    field = build_field_bits(39, [1, 0, 1])
    assert len(field) == 9 + 8 + 3
    # 39 = 0b00100111 LSB first, then the 9th bit SerializeInt still spends at ValueMax 315
    assert field[:9] == [1, 1, 1, 0, 0, 1, 0, 0, 0]
    assert field[9:17] == [0, 1, 1, 0, 0, 0, 0, 0]             # packed 3
    assert field[17:] == [1, 0, 1]


def test_handle_width_is_value_dependent():
    """`SerializeInt(Value, ValueMax)`'s width depends on the value, not just the class.

    This is the whole bug. At ValueMax 315 every handle the client sends (all >= 64) is
    8 bits, so the old fixed-8 model matched 100% of C->S traffic -- while ClientRestart's
    handle 39 needs 9 and was written one bit short.
    """
    assert handle_value_max() == 315
    assert wrapped_width(39, 315) == 9                          # ClientRestart
    assert wrapped_width(40, 315) == 9                          # ClientRetryClientRestart
    for h in (64, 67, 68, 73, 75, 78, 79, 81):                  # every wire anchor
        assert wrapped_width(h, 315) == 8, h
    assert wrapped_width(310, 315) == 9                         # largest handle seen C->S
    assert len(build_field_bits(39, [])) == 9 + 8
    assert len(build_field_bits(64, [])) == 8 + 8


def test_client_restart_reproduces_the_live_overflow_when_mis_framed():
    """The client's own reader, run over the OLD 8-bit bits, must produce the log numbers.

    live_log/HANDLE_CALIBRATE_LIVE.md captured, from the real client:

        FBitReader::SetOverflowed() (ReadLen: 72, Remaining: 15, Max: 32)
        ReadFieldHeaderAndPayload: ... OutField: ClientRestart

    Reading our 8-bit handle with the client's 9-bit `SerializeInt` still yields 39 (hence
    the correct OutField name) but leaves the reader one bit inside the packed length, so
    NumPayloadBits decodes as 72 with 15 of 32 bits left. All three numbers must reproduce
    exactly, otherwise the diagnosis is wrong.
    """
    import os

    prev = os.environ.get("WW3_RPC_HANDLE_BITS")
    os.environ["WW3_RPC_HANDLE_BITS"] = "8"                     # the old, broken encoder
    try:
        os.environ["WW3_RPC_SEND_BIT"] = "0"                    # ...and no Send bit
        old = build_client_restart_bits(9362, handle=39, must_be_mapped=False)
    finally:
        os.environ.pop("WW3_RPC_SEND_BIT", None)
        if prev is None:
            os.environ.pop("WW3_RPC_HANDLE_BITS", None)
        else:
            os.environ["WW3_RPC_HANDLE_BITS"] = prev

    block = read_content_blocks(Bits(old))[0]
    payload = block["payload"]
    assert len(payload) == 32                                   # "Max: 32"

    r = Bits(payload)
    assert read_int_wrapped(r, 315) == 39                       # "OutField: ClientRestart"
    num_payload_bits = r.packed()
    assert num_payload_bits == 72                               # "ReadLen: 72"
    assert r.left() == 15                                       # "Remaining: 15"
    assert num_payload_bits > r.left()                          # -> SetOverflowed


def test_client_restart_num_payload_bits_matches_payload():
    """With the fix, the client's reader consumes our ClientRestart block exactly."""
    for guid in (9362, 9372, 0):
        bits = build_client_restart_bits(guid, handle=39, must_be_mapped=False)
        block = read_content_blocks(Bits(bits))[0]
        r = Bits(block["payload"])
        assert read_int_wrapped(r, handle_value_max()) == 39
        num_payload_bits = r.packed()
        assert num_payload_bits <= r.left(), "would SetOverflowed"
        param = [r.bit() for _ in range(num_payload_bits)]
        assert r.left() == 0, "field chain must consume the block exactly"
        assert num_payload_bits == len(param)
        assert parse_object_param(param) == guid
    # 9-bit handle + packed 16 + (Send bit + 2-byte packed GUID)
    bits = build_client_restart_bits(9372, handle=39, must_be_mapped=False)
    assert read_content_blocks(Bits(bits))[0]["payload"][:9] == [1, 1, 1, 0, 0, 1, 0, 0, 0]
    assert len(read_content_blocks(Bits(bits))[0]["payload"]) == 9 + 8 + 17


def test_object_param_matches_real_server_bits():
    """Ground truth: ServerAcknowledgePossession(APawn*) as the REAL server received it.

    captures/24July26/W3_match_full_2.pcapng, C->S ch2, handle 64, n=11 -- every one a
    17-bit payload. 17 is not a multiple of 8, so the NetGUID cannot be the whole payload:
    the leading bit is `FRepLayout::SendPropertiesForRPC`'s per-parameter Send bit.
    """
    real = [int(c) for c in "11001110001001001"]
    assert len(real) == 17
    assert parse_object_param(real) == PAWN_NETGUID == 9372
    assert build_object_param_bits(9372) == real
    # A null object is identical to the parameter default, so nothing follows the 0 bit.
    assert build_object_param_bits(0) == [0]
    assert parse_object_param([0]) == 0


def test_before_spectator_payload_layout_variants_are_bounded():
    """Diagnostic 226 layouts must be deterministic and length-framed safely."""
    expected = {"sendbits": 18, "raw": 48, "obj_send_float_raw": 49,
                "obj_raw_float_send": 49, "null": 2, "all_send": 50}
    for mode, n in expected.items():
        payload = build_before_spectator_param_bits(9362, 0.0, mode)
        assert len(payload) == n, (mode, len(payload), n)
        framed = build_raw_rpc_bits(226, payload)
        assert parse_actor_rpc_fields(framed) == [(226, payload)]
    try:
        build_before_spectator_param_bits(9362, 0.0, "bad")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown 226 layout must fail closed")
    print("[ok] Client_OnBeforeSpectatorReturnToGame payload A/B layouts")


def test_stop_spectator_before_deploy_serializes_vector_and_leave_source():
    """Handle 254 is FVector + EWW3SpectatorLeaveSource, never zero-arg.

    The generated 4.21 SDK declares exactly those two properties.  A nonzero
    spawn vector and FromCharacter (3 of MAX=6) therefore serialize as one
    property-presence bit + three IEEE floats, then one presence bit + a
    three-bit SerializeInt enum value.
    """
    import struct

    payload = build_stop_spectator_before_deploy_param_bits(
        (-1787.0, -10060.0, -562.5), leave_source=3)
    assert len(payload) == 101
    assert payload[0] == 1
    raw = bytearray(12)
    for i, bit in enumerate(payload[1:97]):
        if bit:
            raw[i >> 3] |= 1 << (i & 7)
    assert struct.unpack("<fff", raw) == (-1787.0, -10060.0, -562.5)
    # Live UE reports ReadLen=3 when only the former adaptive two bits remain:
    # RPC enum parameters use the fixed three-bit width for values 0..5.
    assert payload[97:] == [1, 1, 1, 0]  # present, enum 3 LSB-first

    default_source = build_stop_spectator_before_deploy_param_bits(
        (-1787.0, -10060.0, -562.5), leave_source=0)
    assert len(default_source) == 98
    assert default_source[-1] == 0


def test_character_respawn_success_reuses_captured_location_and_yaw():
    player_respawn = [int(x) for x in
        "110111010000010011100010110100011000111001110111101000000100"]
    payload = build_character_respawn_success_param_bits(player_respawn, status=1)
    assert len(payload) == 67
    # This is the retained opt-in uint8 diagnostic, not a capture-backed layout.
    assert payload[:9] == [1, 1, 0, 0, 0, 0, 0, 0, 0]
    # Handle 235 shares the captured location + yaw with handle 240, but has no
    # trailing keep-inventory bool.
    assert payload[9:] == player_respawn[:58]


def test_gamestate_inprogress_frames_match_state_and_elapsed_time():
    from actor_channel import Bits, read_content_blocks
    from repblock import read_name, read_packed, read_u

    framed = build_gamestate_inprogress_bits(elapsed_time=1)
    block = read_content_blocks(Bits(framed))[0]
    assert block["isActor"] and block["hasRepLayout"]
    payload = block["payload"]
    pos = 1  # bDoChecksum
    h, width = read_packed(payload, pos); pos += width
    assert h == 20
    state, width = read_name(payload, pos); pos += width
    assert state == "InProgress"
    h, width = read_packed(payload, pos); pos += width
    assert h == 21 and read_u(payload, pos, 32) == 1


def test_zero_arg_rpc_roundtrip():
    """A zero-argument RPC has an empty payload -- it must not look like Ack(null)."""
    framed = GuidWriter()
    write_content_block(framed, build_field_bits(RPC_SERVER_ACK_POSSESSION, []),
                        has_rep_layout=0)
    bits = [(framed.get_bytes()[i >> 3] >> (i & 7)) & 1 for i in range(framed.num)]
    assert parse_actor_rpc_fields(bits) == [(RPC_SERVER_ACK_POSSESSION, [])]
    assert not is_ack_possession_null(bits)


def test_multiple_fields_in_one_block():
    """One content block can carry several fields back to back, with no terminator."""
    payload = (build_field_bits(RPC_SERVER_CHECK_POSSESSION, [])
               + build_field_bits(RPC_SERVER_CHECK_POSSESSION_RELIABLE, []))
    framed = GuidWriter()
    write_content_block(framed, payload, has_rep_layout=0)
    bits = [(framed.get_bytes()[i >> 3] >> (i & 7)) & 1 for i in range(framed.num)]
    assert [h for h, _ in parse_actor_rpc_fields(bits)] == [
        RPC_SERVER_CHECK_POSSESSION, RPC_SERVER_CHECK_POSSESSION_RELIABLE]


def test_decodes_real_capture_rpcs():
    """Real C->S blocks lifted from live session 20260806_193422 (ch2, Domination).

    `ServerUpdateLevelVisibility`'s first parameter is the level package FName, so the
    payload literally spells out the map path -- semantic proof that handle 79 is that
    RPC, and therefore that the whole absolute table is anchored correctly.
    """
    samples = {
        # handle: (payload bit count, payload hex)
        RPC_SERVER_CHECK_POSSESSION_RELIABLE: (0, ""),
        75: (0, ""),                                    # ServerShortTimeout
        78: (51, "bb20478b71ee01"),                     # ServerUpdateCamera
        79: (531,                                       # ServerUpdateLevelVisibility
             "e9000000bc1c85b595bd3485c1cdbd3485a5b9bd10d5b9a1d585b99d7dd9cdbc5c5dcd7c"
             "11d5b9a1d585b99d7d1d85b595c1b185e57d3995dd7d113d35010000000004"),
    }
    for handle, (nbits, hexstr) in samples.items():
        raw = bytes.fromhex(hexstr)
        payload = [(raw[i >> 3] >> (i & 7)) & 1 for i in range(nbits)]
        framed = GuidWriter()
        write_content_block(framed, build_field_bits(handle, payload), has_rep_layout=0)
        bits = [(framed.get_bytes()[i >> 3] >> (i & 7)) & 1 for i in range(framed.num)]
        assert parse_actor_rpc_fields(bits) == [(handle, payload)]

    level_payload = samples[79]
    raw = bytes.fromhex(level_payload[1])
    bits = [(raw[i >> 3] >> (i & 7)) & 1 for i in range(level_payload[0])]
    length = sum(bits[2 + i] << i for i in range(32))          # 1 bit bHardcoded + pad
    name = "".join(chr(sum(bits[34 + 8 * c + i] << i for i in range(8)))
                   for c in range(length)).rstrip("\x00")
    assert name == "/Game/Maps/Main/Dunhuang_v3/WW3_Dunhuang_Gameplay_New_DOM"


def test_must_be_mapped_prefix():
    prefix = build_must_be_mapped_prefix([PAWN_NETGUID])
    # uint16 count=1 little-endian + packed guid
    assert len(prefix) >= 16 + 16
    body = build_object_rpc_bits(8, PAWN_NETGUID)
    framed = build_client_restart_bits(PAWN_NETGUID, handle=8, must_be_mapped=True)
    assert framed[: len(prefix)] == prefix
    assert framed[len(prefix) :] == body


def test_ack_null_detect():
    bits = build_object_rpc_bits(RPC_SERVER_ACK_POSSESSION, 0)
    assert is_ack_possession_null(bits)
    bits2 = build_client_restart_bits(must_be_mapped=False)
    assert not is_ack_possession_null(bits2)


def test_ack_pawn_detect():
    bits = build_object_rpc_bits(RPC_SERVER_ACK_POSSESSION, PAWN_NETGUID)
    assert is_ack_possession_pawn(bits)
    assert not is_ack_possession_null(bits)


def test_check_possession_detect():
    """Both CheckClientPossession variants are zero-arg; detection is handle-only."""
    for handle in (RPC_SERVER_CHECK_POSSESSION, RPC_SERVER_CHECK_POSSESSION_RELIABLE):
        framed = GuidWriter()
        write_content_block(framed, build_field_bits(handle, []), has_rep_layout=0)
        bits = [(framed.get_bytes()[i >> 3] >> (i & 7)) & 1 for i in range(framed.num)]
        assert is_check_possession(bits)


def test_handle_constants():
    """Derived from the Dumper-7 dump; all spacings are wire-verified.

    See match_server/derive_net_handles.py and live_log/HANDLE_DERIVE.md.
    """
    assert restart_handles() == [39]
    assert RPC_SERVER_ACK_POSSESSION == 64
    assert RPC_SERVER_CHECK_POSSESSION == 67
    assert RPC_SERVER_CHECK_POSSESSION_RELIABLE == 68
    assert RPC_SERVER_NOTIFY_LOADED_WORLD - RPC_SERVER_ACK_POSSESSION == 6


def test_retry_gated_by_env():
    """WW3_CLIENT_RESTART_SEND_RETRY defaults off — never spray wire-10 Retry unless
    explicitly opted in (the old always-Retry behavior sprayed handle 10 and got the
    client kicked to the lobby)."""
    import os

    prev = os.environ.pop("WW3_CLIENT_RESTART_SEND_RETRY", None)
    prev_multi = os.environ.pop("WW3_CLIENT_RETRY_HANDLES", None)
    try:
        os.environ.pop("WW3_CLIENT_RESTART_SEND_RETRY", None)
        assert retry_handles() == [], "default (unset) must not send any Retry handles"
        os.environ["WW3_CLIENT_RESTART_SEND_RETRY"] = "0"
        assert retry_handles() == [], "explicit 0 must not send any Retry handles"
        os.environ["WW3_CLIENT_RESTART_SEND_RETRY"] = "1"
        assert retry_handles() != [], "opt-in (=1) must send at least one Retry handle"
    finally:
        if prev is None:
            os.environ.pop("WW3_CLIENT_RESTART_SEND_RETRY", None)
        else:
            os.environ["WW3_CLIENT_RESTART_SEND_RETRY"] = prev
        if prev_multi is None:
            os.environ.pop("WW3_CLIENT_RETRY_HANDLES", None)
        else:
            os.environ["WW3_CLIENT_RETRY_HANDLES"] = prev_multi


def test_pc_set_pawn_matches_capture_bits():
    """Experiment #3B must use the capture's own encoding for PC::Pawn, not a guess.

    real_replay_stream src=13 (ch2, PC RepLayout) is bDoChecksum=0, packed handle 17,
    packed NetGUID 9372 — 25 bits. Our hand-built block must reproduce those exactly.
    (Those same 25 bits used to be read as "packed handle 34, one 0 bit, then the GUID":
    skipping the checksum bit doubles the first handle, since packed(2h) and
    0 ++ packed(h) are the same bits for h < 64.)
    """
    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
    capture = read_content_blocks(Bits([int(c) for c in stream[13]["payload"]]))[0]
    assert capture["isActor"] and capture["hasRepLayout"]
    ours = read_content_blocks(Bits(build_pc_set_pawn_bits()))
    assert len(ours) == 1
    assert ours[0]["isActor"] and ours[0]["hasRepLayout"]
    assert ours[0]["payload"][:25] == list(capture["payload"][:25])
    # bDoChecksum + handle + packed GUID, then the RepLayout terminator (packed 0).
    assert len(ours[0]["payload"]) == 25 + 8


def test_rep_block_starts_with_checksum_bit():
    """Every RepLayout block leads with FRepLayout::SendProperties' bDoChecksum bit."""
    from actor_channel import write_rep_properties

    rep = write_rep_properties([(17, [1, 0, 1])])
    assert rep[0] == 0
    assert rep[1:9] == [(34 >> i) & 1 for i in range(8)]     # packed(17) == byte 34
    assert rep[9:12] == [1, 0, 1]
    assert rep[12:20] == [0] * 8                             # packed(0) terminator
    assert len(rep) == 20


def test_pc_set_playerstate_block():
    """The controller binding must resolve the local PlayerState NetGUID."""
    blocks = read_content_blocks(Bits(build_pc_set_playerstate_bits()))
    assert len(blocks) == 1 and blocks[0]["isActor"] and blocks[0]["hasRepLayout"]
    p = blocks[0]["payload"]
    assert p[0] == 0
    r = Bits(p, 1)
    assert r.packed() == PC_REP_HANDLE_PLAYERSTATE
    assert r.packed() == PS_NETGUID
    assert r.packed() == 0
    assert r.left() == 0


def test_pawn_bind_props_block():
    """The synthesised ch3 block sets APawn::PlayerState(17) and ::Controller(18)."""
    from possess_rpc import (PAWN_REP_HANDLE_CONTROLLER, PAWN_REP_HANDLE_PLAYERSTATE,
                             PC_NETGUID, PS_NETGUID, build_pawn_bind_props_bits)

    blocks = read_content_blocks(Bits(build_pawn_bind_props_bits()))
    assert len(blocks) == 1 and blocks[0]["isActor"] and blocks[0]["hasRepLayout"]
    p = blocks[0]["payload"]
    assert p[0] == 0                                          # bDoChecksum
    r = Bits(p, 1)
    assert r.packed() == PAWN_REP_HANDLE_PLAYERSTATE
    assert r.packed() == PS_NETGUID
    assert r.packed() == PAWN_REP_HANDLE_CONTROLLER
    assert r.packed() == PC_NETGUID
    assert r.packed() == 0                                    # terminator
    assert r.left() == 0                                      # exact consumption


def test_ps_set_playerchar_block():
    """ch7 reverse-bind block sets AWW3PlayerStateBase::PlayerCharacter(22) -> 9372."""
    from possess_rpc import (PAWN_NETGUID, PS_REP_HANDLE_PLAYERCHARACTER,
                             build_ps_set_playerchar_bits, ps_playerchar_handle)

    assert ps_playerchar_handle() == PS_REP_HANDLE_PLAYERCHARACTER == 22
    blocks = read_content_blocks(Bits(build_ps_set_playerchar_bits()))
    assert len(blocks) == 1 and blocks[0]["isActor"] and blocks[0]["hasRepLayout"]
    p = blocks[0]["payload"]
    assert p[0] == 0
    r = Bits(p, 1)
    assert r.packed() == 22
    assert r.packed() == PAWN_NETGUID
    assert r.packed() == 0
    assert r.left() == 0


def test_pawn_open_synth_props_in_open():
    """Injected actor bind sits before subobjects — same order as PC/PS opens."""
    from possess_rpc import (PAWN_REP_HANDLE_CONTROLLER, PAWN_REP_HANDLE_PLAYERSTATE,
                             PC_NETGUID, PS_NETGUID, build_pawn_bind_props_bits)
    from pawn_patch import inject_pawn_open_synth_props
    from actor_channel import read_new_actor
    from netguid import PackageMap

    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
    body = [int(c) for c in stream[11]["payload"]]  # NewActor + SUBs (no exports)
    before_blocks = None
    pm0 = PackageMap()
    r0 = Bits(body)
    read_new_actor(r0, pm0)
    before_blocks = read_content_blocks(Bits(body, r0.pos))
    assert before_blocks and not before_blocks[0].get("isActor")

    synth = build_pawn_bind_props_bits()
    out = inject_pawn_open_synth_props(body, synth)
    assert len(out) == len(body) + len(synth)

    pm = PackageMap()
    r = Bits(out)
    info = read_new_actor(r, pm)
    assert info.get("netguid") == 9372 and not info.get("incomplete")
    blocks = read_content_blocks(Bits(out, r.pos))
    assert blocks[0]["isActor"] and blocks[0]["hasRepLayout"]
    p = blocks[0]["payload"]
    assert p[0] == 0
    pr = Bits(p, 1)
    assert pr.packed() == PAWN_REP_HANDLE_PLAYERSTATE
    assert pr.packed() == PS_NETGUID
    assert pr.packed() == PAWN_REP_HANDLE_CONTROLLER
    assert pr.packed() == PC_NETGUID
    assert pr.packed() == 0
    assert pr.left() == 0
    # Original subobject chain preserved after the injected actor block
    assert len(blocks) == 1 + len(before_blocks)
    for got, exp in zip(blocks[1:], before_blocks):
        assert got.get("isActor") is False
        assert got.get("subNetGUID") == exp.get("subNetGUID")
        assert got.get("payloadBits") == exp.get("payloadBits")
        assert got.get("hasRepLayout") == exp.get("hasRepLayout")
    # Idempotent
    assert inject_pawn_open_synth_props(out, synth) == out


def test_pc_pawn_handle_env_override():
    import os

    prev = os.environ.pop("WW3_PC_PAWN_HANDLE", None)
    try:
        assert pc_pawn_handle() == PC_REP_HANDLE_PAWN == 17
        os.environ["WW3_PC_PAWN_HANDLE"] = "35"
        assert pc_pawn_handle() == 35
        assert read_content_blocks(Bits(build_pc_set_pawn_bits()))[0]["payload"][:9] != \
            read_content_blocks(Bits(build_pc_set_pawn_bits(handle=17)))[0]["payload"][:9]
    finally:
        os.environ.pop("WW3_PC_PAWN_HANDLE", None)
        if prev is not None:
            os.environ["WW3_PC_PAWN_HANDLE"] = prev


if __name__ == "__main__":
    test_handle_constants()
    print("[ok] handle constants")
    test_retry_gated_by_env()
    print("[ok] Retry gated by WW3_CLIENT_RESTART_SEND_RETRY (default off)")
    test_client_restart_roundtrip()
    print("[ok] ClientRestart roundtrip")
    test_field_header_is_wrapped_plus_payload_length()
    print("[ok] field header = wrapped handle + packed payload length")
    test_handle_width_is_value_dependent()
    print("[ok] handle width is value-dependent (39 -> 9 bits, 64 -> 8 bits)")
    test_client_restart_reproduces_the_live_overflow_when_mis_framed()
    print("[ok] old 8-bit framing reproduces the live ReadLen:72/Remaining:15/Max:32")
    test_client_restart_num_payload_bits_matches_payload()
    print("[ok] NumPayloadBits == payload bit length; block consumes exactly")
    test_object_param_matches_real_server_bits()
    print("[ok] object param = Send bit + packed NetGUID (real capture bits)")
    test_before_spectator_payload_layout_variants_are_bounded()
    test_stop_spectator_before_deploy_serializes_vector_and_leave_source()
    test_character_respawn_success_reuses_captured_location_and_yaw()
    test_gamestate_inprogress_frames_match_state_and_elapsed_time()
    print("[ok] Client_OnStopSpectatorBeforeDeploy vector + leave-source payload")
    test_zero_arg_rpc_roundtrip()
    print("[ok] zero-arg RPC is not mistaken for Ack(null)")
    test_multiple_fields_in_one_block()
    print("[ok] multiple fields per content block")
    test_decodes_real_capture_rpcs()
    print("[ok] decodes real capture RPCs (incl. map path in ServerUpdateLevelVisibility)")
    test_must_be_mapped_prefix()
    print("[ok] MustBeMapped prefix")
    test_ack_null_detect()
    print("[ok] AckPossession(null) detect")
    test_ack_pawn_detect()
    print("[ok] AckPossession(pawn) detect")
    test_check_possession_detect()
    print("[ok] CheckPossession detect")
    test_pc_set_pawn_matches_capture_bits()
    print("[ok] PC RepLayout Pawn block matches capture bits (experiment #3B)")
    test_pc_set_playerstate_block()
    print("[ok] PC RepLayout PlayerState block round-trips")
    test_rep_block_starts_with_checksum_bit()
    print("[ok] RepLayout block leads with bDoChecksum bit")
    test_pawn_bind_props_block()
    print("[ok] synthesised pawn PlayerState/Controller block round-trips")
    test_ps_set_playerchar_block()
    print("[ok] synthesised PS PlayerCharacter reverse-bind block round-trips")
    test_pawn_open_synth_props_in_open()
    print("[ok] pawn open inject: actor bind before subobjects, round-trips")
    test_pc_pawn_handle_env_override()
    print("[ok] WW3_PC_PAWN_HANDLE override")
    print("ALL possess_rpc tests passed")
