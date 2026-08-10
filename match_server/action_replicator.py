#!/usr/bin/env python3
r"""ch80 `AWW3ActionReplicator` transport: the only wire path that can build the
client's team/squad/slot graph.

Why this module exists
----------------------
`_sync_checklist.py` reads the client's synchronization bitmask; bit1
(`PlayerState`) is `IsValid(AWW3PlayerState::CurrentSquad)` at +0x710.
`UWW3SquadObject` has **zero** `Net` properties -- it is never replicated -- and
`_team_graph_live.py` shows the live client with one `AWW3TeamManager` whose
`Teams` / `ActionReplicators` / `WarmupEntities` are empty and whose
`LocalPlayerState` is NULL.  The graph is built locally from
`UWW3ReplicatedAction_TM_*` objects, and the only delivery mechanism for those is

    AWW3ActionReplicator::Client_ReceivePacket(const TArray<uint8>& InData)

which is a reliable `NetClient` RPC on the ch80 actor.

Wire format, read out of the shipping client
--------------------------------------------
`Client_ReceivePacket_Implementation` @ exe `0x140873980` (stitch + disassemble
with `_fn_dump.py`):

    ReceiveBuffer(+0x380).Append(InData)
    if (buffer was empty before the append and now holds >= 4 bytes):
        ExpectedTotal(+0x364) = int32 buffer[0]        # counts ITSELF
    if (ReceiveBuffer.Num != ExpectedTotal) return     # wait for more fragments
    if (ExpectedTotal == 0) return
    Ar = FMemoryReader(ReceiveBuffer); Ar.Seek(4)      # 0x140873ba5, edx = 4
    int32 ActionCount                                  # -> [rbp+0xd0]
    repeat ActionCount:
        uint8 ActionType                               # -> [rbp+0xc0]
        act = CreateActionFromType(ActionType)         # factory 0x140872d30
        act->vtable[0x240](Ar, 0, &bOk)                # body (de)serialiser
        if (!bOk) break
        if (Count == 0 and act->vtable[0x250]()):      # applies immediately
            0x14089b6e0(act)
        else: append to ClHead/ClTail, Count(+0x358)++
    ReceiveBuffer.Num = 0; ExpectedTotal = 0

Both the "incomplete" early-out at `0x140873b44` and the end of the parse fall
into the same epilogue at `0x140873d43`, which tail-jumps to `0x141672bc0` --
`ProcessEvent(FindFunctionChecked(<name at 0x145dcb148>))`, i.e.
`Server_AckActionsReceived`.  **The ack is therefore unconditional**: it proves
the RPC dispatched, and nothing about whether the payload parsed.  Treat it as a
transport oracle only; the parse oracle is the ActionReplicator's own
`ReceiveBuffer.Num` / `ExpectedTotal` / action `Count`, which `_action_live.py`
reads out of the running client.

`TM_Synchronize::Serialize` @ `0x140990c90` -- the function has two structurally
identical halves (save, then load; the load half additionally calls
`NewObject<UWW3TeamObject>` 0x1418207a0, squad 0x140975de0, slot 0x1409755b0),
and they agree field for field.  `_archive_fields.py` reports the archive size
and the *store* destination separately, which matters because
`FArchive::operator<<(bool&)` moves an `int32` through a scratch slot and only
then writes one byte:

    int32(bool) +0x38 ; 8 x uint8 +0x39..+0x40 ; int32 NumTeams
      per team:  int32 NumSquads
        per squad: uint8 +0x70, int64 +0x78, int32(bool) +0x80, uint8 +0x83,
                   int32 NumSlots
          per slot: int32 +0x30, int64 +0x38, int32(bool) +0x50,
                    int32(bool) +0x60, int32 +0x34, int32(bool) +0x61,
                    FString +0x40

What the fields mean
--------------------
`AWW3TeamManager::ApplyAction` (0x1409523f0) reads the action's `vtable[0x248]`
as `GetActionType()` and jumps a 32-entry table; case 1 tail-calls the
`TM_Synchronize` handler at **0x140969db0**.  That handler:

* copies the nine header values straight into the TeamManager -- `+0x38 ->
  TM+0x440`, `+0x39 -> TM+0x3FC`, `+0x3A..+0x3E -> TM+0x3E8..+0x3F8`,
  `+0x3F -> TM+0x428`, `+0x40 -> TM+0x42C` -- so the header is TeamManager
  configuration and nothing else.  `_slot_bind_gates.py` reads all nine off the
  live client as 0, which is why the default header is all zeros;
* for every slot whose `+0x60` is set, calls `0x1409739b0`, which requires
  `slot->[0x34] != 0` and then scans live `AWW3PlayerState`s for
  `InternalNetId (+0x790) == slot->[0x30]` **and** `PlayerStateUniqueID
  (+0x774) == slot->[0x34]`.  On a match it stores `slot->PlayerState` and, if
  `TeamManager->LocalPlayerState` is null and `Cast<AWW3PlayerController>
  (ps->Owner)` succeeds, calls `AWW3PlayerState::SetCurrentSquad`
  (0x1410fb3c0 -- the function that writes `+0x710`).

The remaining offsets are named by the handlers that write the same slots:
`TM_PlayerStateBindedToSlot` (0x1409611a0) does `slot->[0x34] = <uid>` and
`*(uint16*)&slot->[0x60] = 1`, i.e. `+0x60 = 1` with `+0x61 = 0`, then
`FString::operator=(&slot->[0x40], ...)`; `TM_SteamSquadPlayerRegisteredToNew
SteamSquad` (0x1409693c0) writes the same int64 into `squad->[0x78]` and
`slot->[0x38]` and sets `squad->[0x80] = 1`, and
`TM_ChangeSquadLockedState` (0x140953080) also writes `squad->[0x80]`, so that
int64 is the Steam-party squad id and `+0x80` is the locked flag;
`TM_SquadRespawnMaskChanged` (0x1409681b0) routes its byte through 0x140972860,
which writes `squad->[0x83]`.  The plain random-registration handler
(0x1409657a0) leaves the Steam id and the locked flag at zero, which is the
state a solo player's squad has.

ClassNetCache
-------------
`AActor` contributes 10 NetFields; `AWW3ActionReplicator` declares four `Net`
functions and no `Net` properties, so `FieldsBase = 10` and `MaxIndex = 14`
(`derive_net_handles.py --chain Object,Actor,WW3ActionReplicator`, props+funcs
model -- the model that reproduces all 8 live wire anchors on the
PlayerController chain).  The channel actor's archetype in the capture is
`Default__WW3ActionReplicator`, i.e. the class itself and not a BP subclass, so
there are no extra trailing NetFields to widen the handle.
"""
from __future__ import annotations

import dataclasses
import hashlib
import struct

from actor_channel import Bits, write_content_block
from netguid import GuidWriter
from possess_rpc import parse_actor_rpc_fields, write_int_wrapped

# ----------------------------------------------------------------- constants
ACTION_REPLICATOR_CHANNEL = 80

# `FClassNetCache::GetMaxIndex()` for AWW3ActionReplicator.  UE writes the field
# index as `SerializeInt(index, ValueMax)`; ValueMax is either GetMaxIndex() or
# GetMaxIndex()+1 depending on how you read `ReadFieldHeaderAndPayload`, and for
# every handle this class owns the two are bit-identical -- see
# `test_field_handle_is_four_bits_not_the_playercontroller_width`.
ACTION_REPLICATOR_MAX_INDEX = 14

RPC_CLIENT_RECEIVE_PACKET = 10
RPC_CLIENT_REQUEST_RESPONSE = 11
RPC_SERVER_ACK_ACTIONS_RECEIVED = 12
RPC_SERVER_ACK_SERVER_REQUEST = 13

ACTION_REPLICATOR_HANDLE_NAMES = {
    RPC_CLIENT_RECEIVE_PACKET: "Client_ReceivePacket",
    RPC_CLIENT_REQUEST_RESPONSE: "Client_RequestResponse",
    RPC_SERVER_ACK_ACTIONS_RECEIVED: "Server_AckActionsReceived",
    RPC_SERVER_ACK_SERVER_REQUEST: "Server_AckServerRequest",
}

# `EWW3ReplicatedActionType`, recovered from the factory jump table at
# 0x1408731a4 by `_action_type_map.py` (values from the binary, not from string
# order).  Only the one we need is named here.
ACTION_TM_SYNCHRONIZE = 1

# `Client_ReceivePacket` header: int32 TotalSize (inclusive) + int32 ActionCount.
ACTION_PACKET_HEADER_BYTES = 8


# -------------------------------------------------------------- bit utilities
def _bits(w: GuidWriter) -> list[int]:
    raw = w.get_bytes()
    return [((raw[i >> 3] >> (i & 7)) & 1) for i in range(w.num)]


def write_int_max_bits(value: int, value_max: int) -> list[int]:
    """`FBitWriter::SerializeInt(value, value_max)` as a bit list."""
    w = GuidWriter()
    write_int_wrapped(w, value, value_max)
    return _bits(w)


def build_field_index_bits(handle: int) -> list[int]:
    """The ClassNetCache field index for a ch80 RPC.

    Deliberately does **not** honour `WW3_RPC_HANDLE_BITS` /
    `WW3_RPC_HANDLE_VALUE_MAX`: those are PlayerController A/B controls, and
    letting them widen a ch80 handle would desynchronise a reliable channel.
    """
    return write_int_max_bits(handle, ACTION_REPLICATOR_MAX_INDEX)


def build_field_bits(handle: int, param_bits: list[int]) -> list[int]:
    """One `WriteFieldHeaderAndPayload` field: index, packed bit length, params."""
    w = GuidWriter()
    write_int_wrapped(w, handle, ACTION_REPLICATOR_MAX_INDEX)
    w.write_packed(len(param_bits))
    for b in param_bits:
        w.write_bit(b)
    return _bits(w)


# --------------------------------------------------- RPC parameter serialisers
def build_send_bit_uint32_bits(value: int) -> list[int]:
    """One `uint32` RPC parameter: `SendPropertiesForRPC`'s Send bit, then 32 bits."""
    w = GuidWriter()
    w.write_bit(1)
    w.write_bits(value & 0xFFFFFFFF, 32)
    return _bits(w)


def build_byte_array_param_bits(data: bytes) -> list[int]:
    """One `TArray<uint8>` RPC parameter.

    `FRepLayout::SendPropertiesForRPC` writes a per-parameter Send bit, then
    `SerializeProperties_DynamicArray_r` writes `uint16 ArrayNum` followed by one
    `UByteProperty::NetSerializeItem` (8 bits) per element.  Verified bit-exact
    against all 33 captured `Client_SendPlayersProfileData` payloads.
    """
    if len(data) > 0xFFFF:
        raise ValueError(f"TArray<uint8> count {len(data)} does not fit in uint16")
    w = GuidWriter()
    w.write_bit(1)                                  # Send: differs from the default
    w.write_bits(len(data) & 0xFFFF, 16)
    for byte in data:
        w.write_bits(byte, 8)
    return _bits(w)


# ------------------------------------------------------------ graph value types
@dataclasses.dataclass(frozen=True)
class SyncSlot:
    """One `UWW3SlotObject` record inside a `TM_Synchronize`."""

    player_id: int            # +0x30  matched against AWW3PlayerState::InternalNetId
    steam_squad_id: int       # +0x38  Steam-party squad id; 0 for a solo player
    registered: bool          # +0x50  set with the player id by the registration path
    player_state_bound: bool  # +0x60  gates 0x1409739b0 -- the bind
    unique_id: int            # +0x34  matched against PlayerStateUniqueID; must be != 0
    pending_rebind: bool      # +0x61  cleared with +0x60 as one uint16 by the bind
    name: str = ""            # FString +0x40, display name only


@dataclasses.dataclass(frozen=True)
class SyncSquad:
    """One `UWW3SquadObject` record."""

    number: int               # +0x70  squad number
    steam_squad_id: int       # +0x78  Steam-party squad id; 0 for a random squad
    locked: bool              # +0x80  TM_ChangeSquadLockedState writes this
    respawn_mask: int         # +0x83  TM_SquadRespawnMaskChanged writes this
    slots: tuple = ()


@dataclasses.dataclass(frozen=True)
class SyncTeam:
    """One `UWW3TeamObject` record.  The team carries no fields of its own on the
    wire -- only its squad count -- because the handler derives `TeamId` from the
    index into `AWW3TeamManager::Teams`."""

    squads: tuple = ()


# The nine leading header values are `AWW3TeamManager` settings (see the module
# docstring).  `_slot_bind_gates.py` reads every one of them as 0 on the live
# client, so echoing zeros makes the header a measured no-op.
SYNC_HEADER_SETTINGS_LEN = 8
DEFAULT_SYNC_HEADER_SETTINGS = (0,) * SYNC_HEADER_SETTINGS_LEN


def _u8(name: str, value: int) -> bytes:
    if not 0 <= value <= 0xFF:
        raise ValueError(f"{name} {value} does not fit in uint8")
    return bytes([value])


def _bool32(value) -> bytes:
    """`FArchive::operator<<(bool&)` -- an int32 on the wire, a byte in memory."""
    return struct.pack("<i", 1 if value else 0)


def encode_fstring(text: str) -> bytes:
    """`FString` as 0x141884c80 loads it.

    The load half reads `int32 SaveNum`, takes `SaveNum < 0` (`sets r14b`) to mean
    UCS2 and negates it, and the count includes the null terminator.  An empty
    string is a bare `0`.
    """
    if text == "":
        return struct.pack("<i", 0)
    if all(ord(c) < 0x80 for c in text):
        raw = text.encode("ascii") + b"\x00"
        return struct.pack("<i", len(raw)) + raw
    raw = (text + "\x00").encode("utf-16-le")
    return struct.pack("<i", -(len(text) + 1)) + raw


def decode_fstring(data: bytes, off: int):
    if off + 4 > len(data):
        raise ValueError("FString length runs past the end of the body")
    (num,) = struct.unpack_from("<i", data, off)
    off += 4
    if num == 0:
        return "", off
    if num < 0:
        n = -num
        end = off + n * 2
        if end > len(data):
            raise ValueError("FString runs past the end of the body")
        return data[off:end].decode("utf-16-le").rstrip("\x00"), end
    end = off + num
    if end > len(data):
        raise ValueError("FString runs past the end of the body")
    return data[off:end].decode("ascii").rstrip("\x00"), end


# ---------------------------------------------------------------- action frame
def build_tm_synchronize_body(teams=(), flag: bool = False,
                              settings=DEFAULT_SYNC_HEADER_SETTINGS) -> bytes:
    """`TM_Synchronize` body, i.e. everything after the action type byte."""
    settings = tuple(settings)
    if len(settings) != SYNC_HEADER_SETTINGS_LEN:
        raise ValueError(f"header needs {SYNC_HEADER_SETTINGS_LEN} uint8 settings")
    out = [_bool32(flag)]                                     # +0x38
    out += [_u8(f"header setting {i}", v) for i, v in enumerate(settings)]
    teams = tuple(teams)
    out.append(struct.pack("<i", len(teams)))                 # int32 NumTeams
    for team in teams:
        squads = tuple(team.squads)
        out.append(struct.pack("<i", len(squads)))            # int32 NumSquads
        for squad in squads:
            out.append(_u8("squad number", squad.number))               # +0x70
            out.append(struct.pack("<q", squad.steam_squad_id))         # +0x78
            out.append(_bool32(squad.locked))                           # +0x80
            out.append(_u8("respawn mask", squad.respawn_mask))         # +0x83
            slots = tuple(squad.slots)
            out.append(struct.pack("<i", len(slots)))         # int32 NumSlots
            for slot in slots:
                out.append(struct.pack("<i", slot.player_id))           # +0x30
                out.append(struct.pack("<q", slot.steam_squad_id))      # +0x38
                out.append(_bool32(slot.registered))                    # +0x50
                out.append(_bool32(slot.player_state_bound))            # +0x60
                out.append(struct.pack("<i", slot.unique_id))           # +0x34
                out.append(_bool32(slot.pending_rebind))                # +0x61
                out.append(encode_fstring(slot.name))                   # +0x40
    return b"".join(out)


def read_tm_synchronize_body(body: bytes):
    """Mirror of the load half -- proves the encoder against the same layout.

    Returns `(teams, flag, settings)` and raises if any byte is left over.
    """
    def i32(off):
        if off + 4 > len(body):
            raise ValueError("body truncated")
        return struct.unpack_from("<i", body, off)[0], off + 4

    def i64(off):
        if off + 8 > len(body):
            raise ValueError("body truncated")
        return struct.unpack_from("<q", body, off)[0], off + 8

    def u8(off):
        if off + 1 > len(body):
            raise ValueError("body truncated")
        return body[off], off + 1

    raw_flag, off = i32(0)
    settings = []
    for _ in range(SYNC_HEADER_SETTINGS_LEN):
        v, off = u8(off)
        settings.append(v)
    n_teams, off = i32(off)
    teams = []
    for _ in range(n_teams):
        n_squads, off = i32(off)
        squads = []
        for _ in range(n_squads):
            number, off = u8(off)
            steam, off = i64(off)
            locked, off = i32(off)
            mask, off = u8(off)
            n_slots, off = i32(off)
            slots = []
            for _ in range(n_slots):
                pid, off = i32(off)
                s_steam, off = i64(off)
                registered, off = i32(off)
                bound, off = i32(off)
                uid, off = i32(off)
                pending, off = i32(off)
                name, off = decode_fstring(body, off)
                slots.append(SyncSlot(player_id=pid, steam_squad_id=s_steam,
                                      registered=bool(registered),
                                      player_state_bound=bool(bound),
                                      unique_id=uid,
                                      pending_rebind=bool(pending), name=name))
            squads.append(SyncSquad(number=number, steam_squad_id=steam,
                                    locked=bool(locked), respawn_mask=mask,
                                    slots=tuple(slots)))
        teams.append(SyncTeam(squads=tuple(squads)))
    if off != len(body):
        raise ValueError(f"{len(body) - off} trailing byte(s) after the graph")
    return tuple(teams), bool(raw_flag), tuple(settings)


def slot_binds_to(slot: SyncSlot, internal_net_id: int, unique_id: int) -> bool:
    """Would `0x1409739b0` bind this slot to that PlayerState?

    The native preconditions, in order: `slot->[0x60] != 0`, `slot->[0x34] != 0`,
    `ps->InternalNetId != 0`, `ps->PlayerStateUniqueID == slot->[0x34]`,
    `slot->[0x30] == ps->InternalNetId`.
    """
    return bool(slot.player_state_bound
                and slot.unique_id != 0
                and internal_net_id != 0
                and slot.unique_id == unique_id
                and slot.player_id == internal_net_id)


def build_action_blob(action_type: int, body: bytes) -> bytes:
    """One action on the wire: the type byte (written once) then the body.

    `UWW3ReplicatedAction::Serialize` (0x14088bf30) writes the type byte only when
    the archive is saving; on load the parse loop has already consumed it, so it
    appears exactly once.
    """
    if not 0 <= action_type <= 0xFF:
        raise ValueError(f"action type {action_type} out of range")
    return bytes([action_type]) + body


def build_action_packet(blobs) -> bytes:
    """`int32 TotalSize` (counting itself) + `int32 ActionCount` + the blobs."""
    blobs = list(blobs)
    body = b"".join(blobs)
    total = ACTION_PACKET_HEADER_BYTES + len(body)
    return struct.pack("<ii", total, len(blobs)) + body


def build_empty_tm_synchronize_packet() -> bytes:
    """The transport probe: one well-formed `TM_Synchronize` carrying zero teams.

    Zero teams means the load path creates no team/squad/slot objects, so the
    client's graph is left exactly as it was -- it exercises framing only.
    """
    return build_action_packet(
        [build_action_blob(ACTION_TM_SYNCHRONIZE, build_tm_synchronize_body())])


def build_local_bind_packet(internal_net_id: int, unique_id: int,
                            name: str = "") -> bytes:
    """The smallest graph that can make `CurrentSquad` valid: one team, one
    squad, one slot already bound to this connection's own PlayerState.

    Everything is either measured off the live client (`_slot_bind_gates.py`:
    `InternalNetId`, `PlayerStateUniqueID`, `PlayerName`, the all-zero
    TeamManager header) or fixed by the registration path a solo player takes
    (`0x1409657a0` leaves the Steam id and the locked flag zero, and sets
    `slot->[0x50] = 1`); `+0x60 = 1` / `+0x61 = 0` is the bound state
    `TM_PlayerStateBindedToSlot` writes as one uint16.
    """
    if internal_net_id == 0 or unique_id == 0:
        raise ValueError("the bind predicate rejects a zero id")
    slot = SyncSlot(player_id=internal_net_id, steam_squad_id=0, registered=True,
                    player_state_bound=True, unique_id=unique_id,
                    pending_rebind=False, name=name)
    squad = SyncSquad(number=0, steam_squad_id=0, locked=False, respawn_mask=0,
                      slots=(slot,))
    body = build_tm_synchronize_body((SyncTeam(squads=(squad,)),))
    return build_action_packet([build_action_blob(ACTION_TM_SYNCHRONIZE, body)])


# Identity of the packet built for the live session (InternalNetId 811019,
# PlayerStateUniqueID 1, empty name).  `server.py` refuses to transmit unless the
# bytes it is about to send hash to this, so a layout edit cannot reach a live
# reliable channel unreviewed.
LOCAL_BIND_PACKET_BYTES = 79
LOCAL_BIND_PACKET_SHA256 = (
    "69e0f560f5d1ec73ce72da18d97d7ce5c6672a5285f53522c97b3021e558078c")


# ----------------------------------------------------------------- whole bunch
def build_client_receive_packet_bits(data: bytes) -> list[int]:
    """Actor content block carrying `Client_ReceivePacket(data)` for ch80."""
    w = GuidWriter()
    write_content_block(
        w, build_field_bits(RPC_CLIENT_RECEIVE_PACKET,
                            build_byte_array_param_bits(data)),
        has_rep_layout=0)
    return _bits(w)


def build_zero_arg_action_replicator_bits(handle: int) -> list[int]:
    """Actor content block for a zero-argument ch80 RPC (used by the tests)."""
    w = GuidWriter()
    write_content_block(w, build_field_bits(handle, []), has_rep_layout=0)
    return _bits(w)


# ------------------------------------------------------------ C->S observation
def parse_action_replicator_fields(bits):
    """Decode ch80 RPC fields with this class's ClassNetCache bound, not the PC's."""
    return parse_actor_rpc_fields(bits, value_max=ACTION_REPLICATOR_MAX_INDEX)


def describe_action_replicator_fields(bits):
    """-> [(handle, name, param_bit_count)] for logging client ch80 traffic."""
    return [(int(h), ACTION_REPLICATOR_HANDLE_NAMES.get(int(h), f"handle{int(h)}"),
             len(p)) for h, p in parse_action_replicator_fields(bits)]


def read_action_packet(data: bytes):
    """Mirror of the client's parse loop -- used by the tests to prove framing.

    Returns `{"total", "count", "actions": [(type, body_bytes)]}` or raises.
    Bodies are returned raw because only `TM_Synchronize`'s layout is pinned.
    """
    if len(data) < ACTION_PACKET_HEADER_BYTES:
        raise ValueError("packet shorter than its header")
    total, count = struct.unpack_from("<ii", data, 0)
    if total != len(data):
        raise ValueError(f"size prefix {total} != actual {len(data)}")
    return {"total": total, "count": count, "body": data[ACTION_PACKET_HEADER_BYTES:]}


if __name__ == "__main__":
    packet = build_empty_tm_synchronize_packet()
    bits = build_client_receive_packet_bits(packet)
    print(f"empty TM_Synchronize probe: {len(packet)} bytes {packet.hex()}")
    print(f"  parsed back: {read_action_packet(packet)}")
    print(f"  ch80 bunch payload: {len(bits)} bits")
    print(f"  fields: {describe_action_replicator_fields(bits)}")
