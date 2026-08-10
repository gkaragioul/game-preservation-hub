#!/usr/bin/env python3
r"""RED/GREEN tests for the ch80 `AWW3ActionReplicator` action transport.

Everything asserted here is grounded in one of three places, never in a guess:

* **The shipping client's own code.** `AWW3ActionReplicator::Client_ReceivePacket_
  Implementation` at exe `0x140873980` (stitched + disassembled with
  `_fn_dump.py`) buffers `InData` into `ReceiveBuffer` (+0x380), latches
  `ExpectedTotal` (+0x364) from `int32 buffer[0]` the first time the buffer goes
  from empty to >= 4 bytes, returns until `ReceiveBuffer.Num == ExpectedTotal`,
  then `Seek(4)`, reads `int32 ActionCount`, and loops `uint8 ActionType` ->
  factory (0x140872d30) -> body serialiser (vtable +0x240).  So the size prefix
  counts ITSELF.

* **The Dumper-7 SDK of the live build**, for the ClassNetCache: `AActor`
  contributes 10 NetFields, `AWW3ActionReplicator` adds exactly four Net
  functions and no Net properties, so `FieldsBase = 10`, `MaxIndex = 14` and
  `Client_ReceivePacket` is handle 10 / `Server_AckActionsReceived` is handle 12.
  The props+funcs model is the one that reproduces all 8 live wire anchors on the
  PlayerController chain (`derive_net_handles.py`).

* **The capture**, for the parameter encoding.  `Client_SendPlayersProfileData`
  (handle 140, `uint32` + `TArray<uint8>`) occurs 33 times in
  `real_replay_stream.json` and every one of them decodes to exactly
  `[Send][uint32][Send][uint16 Num][Num*8]` with zero bits left over -- which is
  `FRepLayout::SendPropertiesForRPC` + `SerializeProperties_DynamicArray_r`.
  `Client_ReceivePacket` uses the same two pieces, so the capture pins our
  encoder rather than the UE source doing it alone.

Run:  python match_server/test_action_replicator.py
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from actor_channel import Bits  # noqa: E402
from possess_rpc import parse_actor_rpc_fields, read_int_wrapped  # noqa: E402

import action_replicator as ar  # noqa: E402


# SHA-256 of the 25-byte empty `TM_Synchronize` probe packet. Pinned so that a
# layout edit has to be a deliberate, reviewed change to this constant.
EMPTY_PROBE_SHA256 = "b6d2b409db3eaa14dc3bc956300f989b52ef1f1a296da2ce7d9d7d0cc945203b"


def _bits_to_bytes(bits: list[int]) -> bytes:
    out = bytearray((len(bits) + 7) // 8)
    for i, b in enumerate(bits):
        if b:
            out[i >> 3] |= 1 << (i & 7)
    return bytes(out)


# --------------------------------------------------------------- ClassNetCache
def test_class_net_cache_constants_match_the_sdk_derivation():
    assert ar.ACTION_REPLICATOR_MAX_INDEX == 14
    assert ar.RPC_CLIENT_RECEIVE_PACKET == 10
    assert ar.RPC_CLIENT_REQUEST_RESPONSE == 11
    assert ar.RPC_SERVER_ACK_ACTIONS_RECEIVED == 12
    assert ar.RPC_SERVER_ACK_SERVER_REQUEST == 13
    assert ar.ACTION_REPLICATOR_CHANNEL == 80


def test_field_handle_is_four_bits_not_the_playercontroller_width():
    """`SerializeInt(10, 14)` is 4 bits; the PC's ValueMax 315 would spend 9.

    This is the single most dangerous place to be wrong: a handle written at the
    PlayerController width desynchronises the whole reliable channel.
    """
    bits = ar.build_field_index_bits(ar.RPC_CLIENT_RECEIVE_PACKET)
    assert bits == [0, 1, 0, 1], bits            # 10 == 0b1010, LSB first
    assert len(bits) == 4

    # ValueMax 14 (`GetMaxIndex()`) and 15 (`MaxIndex+1`) are indistinguishable
    # for every handle this class owns, so the open question in
    # `class_net_cache_ww3.json` cannot bite us here.
    for handle in (10, 11, 12, 13):
        assert (ar.write_int_max_bits(handle, 14)
                == ar.write_int_max_bits(handle, 15)), handle

    assert read_int_wrapped(Bits(bits), 14) == ar.RPC_CLIENT_RECEIVE_PACKET
    assert read_int_wrapped(Bits(bits), 15) == ar.RPC_CLIENT_RECEIVE_PACKET


# ----------------------------------------------------- TArray<uint8> parameter
def test_byte_array_param_reproduces_captured_h140_bits_exactly():
    """Rebuild a real captured `Client_SendPlayersProfileData` payload bit for bit.

    If our `TArray<uint8>` encoder is wrong in any way -- missing Send bit, wrong
    count width, wrong bit order -- this cannot match 4146 captured bits.
    """
    stream = json.load(open(HERE / "real_replay_stream.json", encoding="utf-8"))
    samples = 0
    for spec in stream:
        if spec.get("chIndex") != 2 or spec.get("bPartial"):
            continue
        payload = spec.get("payload", "")
        if not payload:
            continue
        try:
            fields = parse_actor_rpc_fields([int(c) for c in payload])
        except Exception:
            continue
        for handle, param in fields:
            if handle != 140:
                continue
            r = Bits(param)
            assert r.bit() == 1
            for_player = r.read(32)
            assert r.bit() == 1
            num = r.read(16)
            assert r.left() == num * 8, (spec.get("_src_idx"), num, r.left())
            data = bytes(r.read(8) for _ in range(num))

            rebuilt = (ar.build_send_bit_uint32_bits(for_player)
                       + ar.build_byte_array_param_bits(data))
            assert rebuilt == param, "captured h140 payload not reproduced"
            samples += 1
    assert samples >= 30, f"expected the capture's ~33 h140 blocks, saw {samples}"


def test_byte_array_param_layout_is_send_bit_then_uint16_then_bytes():
    bits = ar.build_byte_array_param_bits(b"\x01\x80")
    assert len(bits) == 1 + 16 + 16
    assert bits[0] == 1                                   # Send
    assert bits[1:17] == [0, 1] + [0] * 14                # uint16 2, LSB first
    assert bits[17:25] == [1, 0, 0, 0, 0, 0, 0, 0]        # 0x01
    assert bits[25:33] == [0, 0, 0, 0, 0, 0, 0, 1]        # 0x80


def test_empty_byte_array_still_sends_a_count():
    bits = ar.build_byte_array_param_bits(b"")
    assert len(bits) == 1 + 16
    assert bits[0] == 1 and bits[1:] == [0] * 16


# ---------------------------------------------------------------- action frame
def test_empty_tm_synchronize_action_body_is_sixteen_bytes():
    """`TM_Synchronize::Serialize` (0x140990c90): int32 bool, 8 x uint8, int32 NumTeams.

    The function's save and load halves are structurally identical (the load half
    additionally calls NewObject for team/squad/slot), which is what pins the
    field order and widths.
    """
    body = ar.build_tm_synchronize_body(teams=())
    assert body == struct.pack("<i", 0) + bytes(8) + struct.pack("<i", 0)
    assert len(body) == 16


def test_action_blob_prefixes_the_type_byte_once():
    blob = ar.build_action_blob(ar.ACTION_TM_SYNCHRONIZE,
                                ar.build_tm_synchronize_body(teams=()))
    assert blob[0] == 1
    assert len(blob) == 17


def test_packet_size_prefix_counts_itself():
    packet = ar.build_action_packet([ar.build_action_blob(
        ar.ACTION_TM_SYNCHRONIZE, ar.build_tm_synchronize_body(teams=()))])
    assert len(packet) == 25
    assert struct.unpack_from("<i", packet, 0)[0] == len(packet) == 25
    assert struct.unpack_from("<i", packet, 4)[0] == 1        # ActionCount
    assert packet[8] == ar.ACTION_TM_SYNCHRONIZE
    assert packet[9:] == bytes(16)
    # Lock the exact bytes: any future edit to the layout must be deliberate.
    assert packet.hex() == ("19000000" "01000000" "01"
                            "00000000" "0000000000000000" "00000000")
    assert hashlib.sha256(packet).hexdigest() == EMPTY_PROBE_SHA256


def test_empty_probe_packet_helper_matches_the_hand_built_one():
    assert ar.build_empty_tm_synchronize_packet() == ar.build_action_packet(
        [ar.build_action_blob(ar.ACTION_TM_SYNCHRONIZE,
                              ar.build_tm_synchronize_body(teams=()))])


# ------------------------------------------------------------- the whole bunch
def test_client_receive_packet_block_round_trips_through_the_actor_parser():
    data = ar.build_empty_tm_synchronize_packet()
    bits = ar.build_client_receive_packet_bits(data)

    fields = parse_actor_rpc_fields(bits, value_max=ar.ACTION_REPLICATOR_MAX_INDEX)
    assert len(fields) == 1
    handle, param = fields[0]
    assert handle == ar.RPC_CLIENT_RECEIVE_PACKET

    r = Bits(param)
    assert r.bit() == 1
    assert r.read(16) == len(data)
    assert bytes(r.read(8) for _ in range(len(data))) == data
    assert r.left() == 0


def test_client_receive_packet_block_has_the_exact_expected_width():
    data = ar.build_empty_tm_synchronize_packet()
    bits = ar.build_client_receive_packet_bits(data)
    param_bits = 1 + 16 + 8 * len(data)                 # 217
    field_bits = 4 + 16 + param_bits                    # handle + packed(217) + body
    assert len(bits) == 1 + 1 + 16 + field_bits == 255
    assert bits[0] == 0                                 # bHasRepLayout
    assert bits[1] == 1                                 # bIsActor


def test_probe_bunch_never_carries_a_replayout_flag():
    """A RepLayout block on ch80 would be read as properties, not as an RPC."""
    bits = ar.build_client_receive_packet_bits(b"\x08\x00\x00\x00\x00\x00\x00\x00")
    assert bits[0] == 0


# --------------------------------------------------------- C->S ack observation
def test_server_ack_actions_received_is_decoded_from_a_client_bunch():
    """The client's natural reply is a zero-arg handle 12 on the same channel."""
    bits = ar.build_zero_arg_action_replicator_bits(
        ar.RPC_SERVER_ACK_ACTIONS_RECEIVED)
    names = ar.describe_action_replicator_fields(bits)
    assert names == [(12, "Server_AckActionsReceived", 0)]


def test_action_replicator_fields_are_not_decodable_with_the_pc_value_max():
    """Guards the ch80 observer against being wired to the default parser."""
    bits = ar.build_zero_arg_action_replicator_bits(
        ar.RPC_SERVER_ACK_ACTIONS_RECEIVED)
    wrong = parse_actor_rpc_fields(bits)                 # ValueMax 315
    assert wrong != [(12, [])]


def _run() -> int:
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in fns:
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"[FAIL] {name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"[ERROR] {name}: {type(exc).__name__}: {exc}")
        else:
            print(f"[ok]   {name}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())
