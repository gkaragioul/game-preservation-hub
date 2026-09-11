#!/usr/bin/env python3
r"""RED/GREEN tests for a **non-empty** `TM_Synchronize` -- the packet that can
make `AWW3PlayerState::CurrentSquad` valid.

Every constant below is read out of the shipping client or off the live process;
none of it is guessed.  Provenance, field by field:

Wire layout -- `UWW3ReplicatedAction_TM_Synchronize::Serialize` @ `0x140990C90`.
`_archive_fields.py` walks the stitched function and reports both the archive
size and the *store* destination, which matters because
`FArchive::operator<<(bool&)` moves an `int32` through a scratch slot and only
then writes one byte.  The save half and the load half agree field for field:

    int32(bool) +0x38 ; 8 x uint8 +0x39..+0x40 ; int32 NumTeams
      per team:   int32 NumSquads
        per squad: uint8 +0x70, int64 +0x78, int32(bool) +0x80, uint8 +0x83,
                   int32 NumSlots
          per slot: int32 +0x30, int64 +0x38, int32(bool) +0x50,
                    int32(bool) +0x60, int32 +0x34, int32(bool) +0x61,
                    FString +0x40

(the `+0x61` bool and the FString's `+0x40` home both correct Checkpoint 12,
which had six slot fields and put the string at `[rcx]`.)

Field *meaning* -- from the handlers that write the same offsets:

* `AWW3TeamManager::ApplyAction` (`0x1409523F0`) reads the action's
  `vtable[0x248]` as `GetActionType()` and jumps a 32-entry table; case 1
  tail-calls the `TM_Synchronize` handler `0x140969DB0`.
* That handler copies the nine header values straight into the TeamManager
  (`action+0x39 -> TM+0x3FC`, `+0x38 -> TM+0x440`, `+0x3A..+0x3E ->
  TM+0x3E8..+0x3F8`, `+0x3F -> TM+0x428`, `+0x40 -> TM+0x42C`), so the header is
  pure TeamManager configuration.  `_slot_bind_gates.py` reads all nine off the
  live client as **0**, so an all-zero header is a measured no-op.
* For each slot with `+0x60` set it calls `0x1409739B0`, whose preconditions are
  `slot->[0x60] != 0`, `slot->[0x34] != 0`, and then a scan of every live
  `AWW3PlayerState` for `ps->InternalNetId (+0x790) == slot->[0x30]` **and**
  `ps->PlayerStateUniqueID (+0x774) == slot->[0x34]`.  On a match it sets
  `slot->PlayerState`, and -- if `TeamManager->LocalPlayerState` is still null and
  `Cast<AWW3PlayerController>(ps->Owner)` succeeds -- calls
  `AWW3PlayerState::SetCurrentSquad` (`0x1410FB3C0`, which is the function that
  touches `+0x710`).
* `TM_PlayerStateBindedToSlot`'s handler (`0x1409611A0`) writes the same slot
  record: `slot->[0x34] = action->[0x3C]`, `*(uint16*)&slot->[0x60] = 1` (so
  `+0x60 = 1` and `+0x61 = 0` together), and `FString::operator=(&slot->[0x40],
  &action->[0x40])` -- which names `+0x34`, `+0x60`, `+0x61` and the string.
* `TM_SteamSquadPlayerRegisteredToNewSteamSquad`'s handler (`0x1409693C0`) writes
  `squad->[0x78] = action int64`, `squad->[0x80] = 1`, `slot->[0x38] = the same
  int64` -- so both int64s are the Steam-party squad id, and `+0x80` is the
  locked flag (`TM_ChangeSquadLockedState`'s handler `0x140953080` writes
  `squad->[0x80]` too).  `TM_SquadRespawnMaskChanged`'s handler (`0x1409681B0`)
  routes its value through `0x140972860`, which writes `squad->[0x83]`.
* The plain random-registration handler (`0x1409657A0`) sets only
  `squad->[0x70]`, `slot->[0x30]` and `slot->[0x50] = 1`, leaving the Steam id
  and locked flag zero -- which is exactly the state a solo player's squad has.

Live identity (`_slot_bind_gates.py` against client PID 32328):
`InternalNetId = 811019`, `PlayerStateUniqueID = 1`, `PlayerName = ''`,
`UniqueId` non-null, `Owner` casts to `AWW3PlayerController`,
`TeamManager->LocalPlayerState` still NULL.

Run:  python match_server/test_tm_synchronize.py
"""
from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from action_replicator import (  # noqa: E402
    ACTION_TM_SYNCHRONIZE,
    LOCAL_BIND_PACKET_SHA256,
    SyncSlot,
    SyncSquad,
    SyncTeam,
    build_action_blob,
    build_action_packet,
    build_local_bind_packet,
    build_tm_synchronize_body,
    encode_fstring,
    read_action_packet,
    read_tm_synchronize_body,
    slot_binds_to,
)

LIVE_INTERNAL_NET_ID = 811019
LIVE_PLAYER_STATE_UNIQUE_ID = 1


def _local_slot() -> SyncSlot:
    return SyncSlot(player_id=LIVE_INTERNAL_NET_ID, steam_squad_id=0,
                    registered=True, player_state_bound=True,
                    unique_id=LIVE_PLAYER_STATE_UNIQUE_ID,
                    pending_rebind=False, name="")


def _local_graph():
    return (SyncTeam(squads=(SyncSquad(number=0, steam_squad_id=0, locked=False,
                                       respawn_mask=0,
                                       slots=(_local_slot(),)),)),)


# --------------------------------------------------------------- exact bytes
def test_minimal_local_bind_packet_is_the_exact_hand_derived_79_bytes():
    """Byte-for-byte from the disassembled field order -- the layout identity."""
    expected = (
        struct.pack("<i", 79)             # TotalSize, counts itself (0x140873AD0)
        + struct.pack("<i", 1)            # ActionCount
        + bytes([ACTION_TM_SYNCHRONIZE])  # type byte, written once (0x14088BF30)
        + struct.pack("<i", 0)            # header bool   action+0x38 -> TM+0x440
        + bytes(8)                        # header uint8s action+0x39..+0x40
        + struct.pack("<i", 1)            # NumTeams
        + struct.pack("<i", 1)            # NumSquads
        + bytes([0])                      # squad +0x70 number
        + struct.pack("<q", 0)            # squad +0x78 steam squad id
        + struct.pack("<i", 0)            # squad +0x80 locked
        + bytes([0])                      # squad +0x83 respawn mask
        + struct.pack("<i", 1)            # NumSlots
        + struct.pack("<i", LIVE_INTERNAL_NET_ID)   # slot +0x30
        + struct.pack("<q", 0)                      # slot +0x38 steam squad id
        + struct.pack("<i", 1)                      # slot +0x50 registered
        + struct.pack("<i", 1)                      # slot +0x60 bound  <- the gate
        + struct.pack("<i", LIVE_PLAYER_STATE_UNIQUE_ID)  # slot +0x34
        + struct.pack("<i", 0)                      # slot +0x61 pending rebind
        + struct.pack("<i", 0)                      # FString "" -> length 0
    )
    assert len(expected) == 79, len(expected)
    got = build_local_bind_packet(LIVE_INTERNAL_NET_ID,
                                  LIVE_PLAYER_STATE_UNIQUE_ID, name="")
    assert got == expected, f"\n got {got.hex()}\nwant {expected.hex()}"


def test_local_bind_packet_sha256_is_pinned():
    """A layout edit must not reach a live reliable channel unreviewed."""
    packet = build_local_bind_packet(LIVE_INTERNAL_NET_ID,
                                     LIVE_PLAYER_STATE_UNIQUE_ID, name="")
    assert hashlib.sha256(packet).hexdigest() == LOCAL_BIND_PACKET_SHA256


def test_size_prefix_counts_itself_and_the_client_parser_accepts_it():
    packet = build_local_bind_packet(LIVE_INTERNAL_NET_ID,
                                     LIVE_PLAYER_STATE_UNIQUE_ID, name="")
    parsed = read_action_packet(packet)
    assert parsed["total"] == len(packet)
    assert parsed["count"] == 1


# ------------------------------------------------------------------ round trip
def test_round_trip_recovers_every_team_squad_and_slot_field():
    teams = (
        SyncTeam(squads=(
            SyncSquad(number=3, steam_squad_id=0x0123456789ABCDEF, locked=True,
                      respawn_mask=0x2A,
                      slots=(SyncSlot(player_id=811019, steam_squad_id=7,
                                      registered=True, player_state_bound=True,
                                      unique_id=1, pending_rebind=True,
                                      name="Player"),
                             SyncSlot(player_id=42, steam_squad_id=0,
                                      registered=False, player_state_bound=False,
                                      unique_id=0, pending_rebind=False,
                                      name=""))),
            SyncSquad(number=4, steam_squad_id=0, locked=False, respawn_mask=0,
                      slots=()))),
        SyncTeam(squads=()),
    )
    header = (0, 1, 2, 3, 4, 5, 6, 7)
    body = build_tm_synchronize_body(teams, flag=True, settings=header)
    back_teams, back_flag, back_settings = read_tm_synchronize_body(body)
    assert back_flag is True
    assert back_settings == header
    assert back_teams == teams


def test_round_trip_consumes_the_whole_body_with_nothing_left_over():
    body = build_tm_synchronize_body(_local_graph())
    read_tm_synchronize_body(body)          # raises if trailing bytes remain
    truncated = body[:-1]
    try:
        read_tm_synchronize_body(truncated)
    except ValueError:
        pass
    else:
        raise AssertionError("a truncated body must not parse")


# ------------------------------------------------------------------- encodings
def test_bools_are_int32_on_the_wire_not_single_bytes():
    """`FArchive::operator<<(bool&)` moves an int32; the byte store is internal."""
    a = build_tm_synchronize_body((), flag=False)
    b = build_tm_synchronize_body((), flag=True)
    assert len(a) == len(b) == 4 + 8 + 4
    assert a[:4] == struct.pack("<i", 0)
    assert b[:4] == struct.pack("<i", 1)


def test_fstring_is_ansi_with_a_counted_null_terminator():
    assert encode_fstring("") == struct.pack("<i", 0)
    assert encode_fstring("Player") == struct.pack("<i", 6) + b"Player\x00"


def test_fstring_switches_to_negative_length_ucs2_for_non_ascii():
    """0x141884C80's load half negates the count to signal UCS2 (`sets r14b`)."""
    got = encode_fstring("é")
    assert got == struct.pack("<i", -2) + "é\x00".encode("utf-16-le")


def test_squad_and_slot_byte_fields_are_range_checked():
    for bad in (-1, 256):
        try:
            build_tm_synchronize_body((SyncTeam(squads=(
                SyncSquad(number=bad, steam_squad_id=0, locked=False,
                          respawn_mask=0, slots=()),)),))
        except ValueError:
            pass
        else:
            raise AssertionError(f"squad number {bad} must be rejected")


# --------------------------------------------------- the native bind predicate
def test_slot_binds_only_when_the_native_predicate_would_fire():
    """Mirrors 0x1409739B0: +0x60 set, +0x34 non-zero, and both ids match."""
    good = _local_slot()
    assert slot_binds_to(good, LIVE_INTERNAL_NET_ID, LIVE_PLAYER_STATE_UNIQUE_ID)

    import dataclasses
    unbound = dataclasses.replace(good, player_state_bound=False)
    assert not slot_binds_to(unbound, LIVE_INTERNAL_NET_ID,
                             LIVE_PLAYER_STATE_UNIQUE_ID)

    zero_uid = dataclasses.replace(good, unique_id=0)
    assert not slot_binds_to(zero_uid, LIVE_INTERNAL_NET_ID, 0)

    wrong_net = dataclasses.replace(good, player_id=LIVE_INTERNAL_NET_ID + 1)
    assert not slot_binds_to(wrong_net, LIVE_INTERNAL_NET_ID,
                             LIVE_PLAYER_STATE_UNIQUE_ID)


def test_the_local_bind_packet_would_actually_bind_the_live_playerstate():
    packet = build_local_bind_packet(LIVE_INTERNAL_NET_ID,
                                     LIVE_PLAYER_STATE_UNIQUE_ID, name="")
    body = read_action_packet(packet)["body"]
    assert body[0] == ACTION_TM_SYNCHRONIZE
    teams, _flag, _settings = read_tm_synchronize_body(body[1:])
    slots = [s for t in teams for q in t.squads for s in q.slots]
    assert len(slots) == 1
    assert slot_binds_to(slots[0], LIVE_INTERNAL_NET_ID,
                         LIVE_PLAYER_STATE_UNIQUE_ID)


def test_header_defaults_to_the_measured_all_zero_teammanager_config():
    """`_slot_bind_gates.py` reads TM+0x3E8..+0x440 as 0 on the live client."""
    body = build_tm_synchronize_body(())
    assert body[:12] == bytes(12)


# ------------------------------------------------------- empty form unchanged
def test_the_empty_probe_packet_is_untouched_by_the_new_code():
    """The 25-byte transport probe already proven GREEN on the wire must not move."""
    body = build_tm_synchronize_body(())
    packet = build_action_packet([build_action_blob(ACTION_TM_SYNCHRONIZE, body)])
    assert len(packet) == 25
    assert hashlib.sha256(packet).hexdigest().startswith("b6d2b409db3eaa14")


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
