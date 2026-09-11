from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
import threading

import anyio
import pytest
from fastapi import WebSocket
from fastapi.testclient import TestClient

from app.main import app
from app.models.save import LocalProfile, RogueLikeNodeState
from app.protocol import logic
from app.protocol.logic import (
    build_player_data,
    build_roguelike_info,
    pack_frame,
    unpack_frame,
)
from app.protocol.protobuf import encode_varint, field_bytes, field_varint
from app.routes import logic as logic_route
from app.security.logic_token import issue_logic_token
from app.storage import profile_store as profile_store_module
from app.storage.profile_store import ProfileStore


@dataclass
class Fields:
    values: dict[int, list[tuple[int, int | bytes]]]

    def varint(self, number: int) -> int:
        wire_type, value = self.values[number][0]
        assert wire_type == 0
        assert isinstance(value, int)
        return value

    def varints(self, number: int) -> list[int]:
        result: list[int] = []
        for wire_type, value in self.values.get(number, []):
            if wire_type == 0:
                assert isinstance(value, int)
                result.append(value)
            else:
                assert wire_type == 2
                assert isinstance(value, bytes)
                index = 0
                while index < len(value):
                    item, index = _decode_varint(value, index)
                    result.append(item)
        return result

    def message(self, number: int) -> "Fields":
        wire_type, value = self.values[number][0]
        assert wire_type == 2
        assert isinstance(value, bytes)
        return decode_fields(value)

    def messages(self, number: int) -> list["Fields"]:
        return [
            decode_fields(value)
            for wire_type, value in self.values.get(number, [])
            if wire_type == 2 and isinstance(value, bytes)
        ]

    def text(self, number: int) -> str:
        wire_type, value = self.values[number][0]
        assert wire_type == 2
        assert isinstance(value, bytes)
        return value.decode("utf-8")


def _decode_varint(payload: bytes, index: int) -> tuple[int, int]:
    value = 0
    for byte_index in range(10):
        if index >= len(payload):
            raise ValueError("truncated test protobuf varint")
        byte = payload[index]
        index += 1
        value |= (byte & 0x7F) << (byte_index * 7)
        if byte < 0x80:
            return value, index
    raise ValueError("invalid test protobuf varint")


def decode_fields(payload: bytes) -> Fields:
    index = 0
    values: dict[int, list[tuple[int, int | bytes]]] = {}
    while index < len(payload):
        key, index = _decode_varint(payload, index)
        number, wire_type = key >> 3, key & 7
        if wire_type == 0:
            value, index = _decode_varint(payload, index)
        elif wire_type == 2:
            size, index = _decode_varint(payload, index)
            value = payload[index : index + size]
            assert len(value) == size
            index += size
        else:
            raise AssertionError(
                f"unsupported test protobuf wire type {wire_type}"
            )
        values.setdefault(number, []).append((wire_type, value))
    return Fields(values)


def _signed32(value: int) -> int:
    value &= 0xFFFF_FFFF
    return value - 0x1_0000_0000 if value & 0x8000_0000 else value


def _items_by_id(payload: bytes) -> dict[int, Fields]:
    return {
        _signed32(item.varint(1)): item
        for item in decode_fields(payload).messages(2)
    }


def _request_event(event_id: int, exports: tuple[int, ...] = ()) -> bytes:
    return field_varint(1, event_id) + b"".join(
        field_varint(2, export) for export in exports
    )


def _request_node(
    location: int,
    event_id: int | None = None,
    exports: tuple[int, ...] = (),
) -> bytes:
    payload = field_varint(1, location)
    if event_id is not None:
        payload += field_bytes(2, _request_event(event_id, exports))
    return payload


def _request_top(hp: int, buffs: tuple[int, ...] = ()) -> bytes:
    return field_varint(1, hp) + b"".join(
        field_varint(2, buff) for buff in buffs
    )


def _enter_map_payload(
    *,
    version: int = 0,
    chapter_id: int = -1,
    chapter_level: int = 1,
    seed: int = 123456,
    init_location: int = 3,
    hp: tuple[int, int, int] = (1000, 900, 800),
    is_buy_key: int = 0,
    map_id: int = 0,
    cost_key: int = 1,
) -> bytes:
    enter_map = b"".join(
        (
            field_varint(1, chapter_id),
            field_varint(2, chapter_level),
            field_varint(3, seed),
            field_bytes(4, _request_node(init_location)),
            *(field_bytes(5, _request_top(value)) for value in hp),
            field_varint(6, is_buy_key),
            field_varint(7, map_id),
            field_varint(9, cost_key),
        )
    )
    return field_varint(1, version) + field_bytes(2, enter_map)


def _enter_node_payload(
    *,
    version: int,
    location: int,
    event_id: int | None = None,
    exports: tuple[int, ...] = (),
    refresh: int = 0,
    chapter_id: int = -1,
) -> bytes:
    enter_node = field_bytes(
        1, _request_node(location, event_id, exports)
    ) + field_varint(2, refresh)
    return (
        field_varint(1, version)
        + field_bytes(2, enter_node)
        + field_varint(3, chapter_id)
    )


def _trigger_payload(
    *,
    version: int,
    location: int,
    event_id: int,
    exports: tuple[int, ...],
    path: tuple[int, ...],
    hp: tuple[int, int, int],
    energy_type: int,
    clear: int,
    chapter_id: int = -1,
    extra_trigger_fields: bytes = b"",
    top_buffs: tuple[tuple[int, ...], ...] = ((), (), ()),
    all_node: int = 0,
) -> bytes:
    trigger = b"".join(
        (
            field_bytes(1, _request_node(location, event_id, exports)),
            *(field_varint(2, event) for event in path),
            field_varint(3, 0),
            *(
                field_bytes(4, _request_top(value, buffs))
                for value, buffs in zip(hp, top_buffs)
            ),
            field_varint(5, all_node),
            field_varint(6, energy_type),
            field_varint(8, clear),
            extra_trigger_fields,
        )
    )
    return (
        field_varint(1, version)
        + field_bytes(2, trigger)
        + field_varint(3, chapter_id)
    )


def _active_profile() -> LocalProfile:
    part_ids = {
        1: (2001, 2002, 2003),
        2: (2004, 2005, 2006),
        3: (2028, 2029, 2030),
    }
    return LocalProfile.model_validate(
        {
            "roguelike_keys": 2,
            "default_items": {
                "1194340400": 5,
                "1295005745": 1,
                "1295005746": 1,
            },
            "roguelike_run": {
                "version": 7,
                "random_seed": 123456,
                "location": 10003,
                "toy_tops": {
                    str(top): {
                        "hp": hp,
                        "buffs": {"3861": 2} if top == 1 else {},
                        "parts": {
                            str(part_id): {
                                "level": 2 if part_id == 2001 else 1,
                                "current_skin": 3 if part_id == 2001 else 0,
                                "location_kerns": (
                                    {"4": 5001} if part_id == 2001 else {}
                                ),
                            }
                            for part_id in parts
                        },
                    }
                    for top, hp, parts in (
                        (1, 1000, part_ids[1]),
                        (2, 900, part_ids[2]),
                        (3, 800, part_ids[3]),
                    )
                },
                "nodes": {
                    "3": {"status": 3},
                    "10003": {
                        "status": 1,
                        "event_id": 110019,
                        "location_exports": [100095, 100080, 100090],
                    },
                },
                "event_buffs": {"4214": 2},
            },
        }
    )


def _battle_profile(
    *,
    status: int,
    pending_reward: bool,
    hp: tuple[int, int, int] = (1000, 900, 800),
) -> LocalProfile:
    profile = _active_profile()
    run = profile.roguelike_run
    assert run is not None
    run.location = 20002
    run.nodes[10003].status = 3
    run.nodes[20002] = RogueLikeNodeState(
        status=status,
        event_id=110001,
        location_exports=[100001, 100002, 100003],
    )
    for top_index, value in enumerate(hp, start=1):
        run.toy_tops[top_index].hp = value
    run.pending_battle_reward = pending_reward
    profile.default_items = (
        {
            1194340400: 5,
            1295005745: 1,
            1295005746: 1,
        }
        if pending_reward
        else {}
    )
    return profile


def _receive_message(websocket) -> dict[str, object]:
    async def receive_with_timeout():
        with anyio.fail_after(1):
            return await websocket._send_rx.receive()

    try:
        message = websocket.portal.call(receive_with_timeout)
    except TimeoutError:
        pytest.fail("logic socket did not return the required response")
    if isinstance(message, BaseException):
        raise message
    return message


def _receive_frame(websocket) -> tuple[int, bytes]:
    message = _receive_message(websocket)
    assert message["type"] == "websocket.send"
    payload = message.get("bytes")
    assert isinstance(payload, bytes)
    return unpack_frame(payload)


def _login(websocket, profile: LocalProfile) -> list[tuple[int, bytes]]:
    from app.protocol.protobuf import field_text

    websocket.send_bytes(
        pack_frame(1111, field_text(1, issue_logic_token(profile)))
    )
    return [_receive_frame(websocket) for _ in range(4)]


def _run_version() -> int:
    """The map version the gateway assigned to the active run.

    RogueLikeMap.Version is a timestamp, so tests cannot hardcode it; the
    client echoes back whatever the enter-map response carried.
    """
    run = ProfileStore().load("local").roguelike_run
    assert run is not None
    return run.version


def _start_run(websocket) -> None:
    websocket.send_bytes(pack_frame(181, _enter_map_payload()))
    assert [_receive_frame(websocket)[0] for _ in range(3)] == [5, 1, 180]
    websocket.send_bytes(
        pack_frame(182, _enter_node_payload(version=_run_version(), location=3))
    )
    assert [_receive_frame(websocket)[0] for _ in range(2)] == [5, 180]


def _reach_story(websocket) -> None:
    _start_run(websocket)
    websocket.send_bytes(
        pack_frame(
            182,
            _enter_node_payload(
                version=_run_version(),
                location=10003,
                event_id=110000,
            ),
        )
    )
    assert [_receive_frame(websocket)[0] for _ in range(2)] == [5, 180]


def _reach_chip_branch(websocket) -> None:
    _reach_story(websocket)
    websocket.send_bytes(
        pack_frame(
            182,
            _enter_node_payload(
                version=_run_version(),
                location=10003,
                event_id=110019,
                refresh=1,
            ),
        )
    )
    assert [_receive_frame(websocket)[0] for _ in range(2)] == [5, 180]


def _reach_talk_branch(websocket) -> None:
    _reach_story(websocket)
    websocket.send_bytes(
        pack_frame(
            182,
            _enter_node_payload(
                version=_run_version(),
                location=10003,
                event_id=110005,
                refresh=1,
            ),
        )
    )
    assert [_receive_frame(websocket)[0] for _ in range(2)] == [5, 180]


def _finish_chip_branch(websocket, selected_export: int = 100095) -> None:
    _reach_chip_branch(websocket)
    websocket.send_bytes(
        pack_frame(
            184,
            _trigger_payload(
                version=_run_version(),
                location=10003,
                event_id=110019,
                exports=(selected_export,),
                path=(110000, 110019),
                hp=(1000, 900, 800),
                energy_type=-1,
                clear=0,
            ),
        )
    )
    assert [_receive_frame(websocket)[0] for _ in range(2)] == [5, 180]


def _enter_first_battle(websocket, location: int = 20002) -> None:
    _finish_chip_branch(websocket)
    websocket.send_bytes(
        pack_frame(
            182,
            _enter_node_payload(
                version=_run_version(),
                location=location,
                event_id=110001,
                exports=(100001, 100002, 100003),
            ),
        )
    )
    assert [_receive_frame(websocket)[0] for _ in range(2)] == [5, 180]


EXPECTED_RUN_PARTS = {
    1: {2001, 2002, 2003},
    2: {2004, 2005, 2006},
    3: {2028, 2029, 2030},
}


def _win_first_battle(websocket) -> None:
    _enter_first_battle(websocket)
    websocket.send_bytes(
        pack_frame(
            184,
            _trigger_payload(
                version=_run_version(),
                location=20002,
                event_id=110001,
                exports=(100001, 100002, 100003),
                path=(110001,),
                hp=(900, 800, 700),
                energy_type=0,
                clear=1,
            ),
        )
    )
    assert [_receive_frame(websocket)[0] for _ in range(3)] == [5, 1, 180]


def _assert_restart_login_state(
    frames: list[tuple[int, bytes]],
    *,
    battle_status: int,
    hp: tuple[int, int, int],
    event_buffs: dict[int, int],
) -> None:
    assert [net_id for net_id, _ in frames] == [1, 2, 5, 129]

    player_data = decode_fields(frames[0][1])
    assert [
        (entry.varint(1), entry.varint(2))
        for entry in player_data.message(1).messages(22)
    ] == [
        (1194340400, 5),
        (1295005745, 1),
        (1295005746, 1),
    ]
    assert player_data.message(17).varint(3) == 0

    run_map = decode_fields(frames[2][1]).message(1)
    assert (
        run_map.varint(1),
        _signed32(run_map.varint(3)),
        run_map.varint(4),
        run_map.varint(5),
        run_map.varint(7),
) == (_run_version(), -1, 1, 123456, 0)
    status = run_map.message(2)
    assert (status.varint(1), status.varint(2), status.varint(3)) == (
        20002,
        1,
        0,
    )
    tops = {
        entry.varint(1): entry.message(2) for entry in status.messages(4)
    }
    assert set(tops) == {1, 2, 3}
    assert tuple(tops[index].varint(1) for index in (1, 2, 3)) == hp
    for top_index, top in tops.items():
        assert top.messages(2) == []
        parts = {
            entry.varint(1): entry.message(2) for entry in top.messages(3)
        }
        assert set(parts) == EXPECTED_RUN_PARTS[top_index]
        for part in parts.values():
            assert (part.varint(1), part.varint(2)) == (1, 0)
            assert part.messages(3) == []
    assert {
        entry.varint(1): entry.varint(2) for entry in status.messages(5)
    } == event_buffs

    nodes = {
        entry.varint(1): entry.message(2)
        for entry in run_map.messages(6)
    }
    battle = nodes[20002]
    assert battle.varint(1) == battle_status
    event = battle.message(2)
    assert event.varint(1) == 110001
    assert [
        entry.varint(2) for entry in event.messages(2)
    ] == [100001, 100002, 100003]


def test_player_data_bootstrap_unlocks_adventure_and_persists_roguelike_keys():
    profile = LocalProfile()

    player_data = decode_fields(build_player_data(profile))
    base = player_data.message(1)
    unlock = base.message(74)
    guide = base.message(82)
    roguelike_item = player_data.message(17)

    assert (unlock.varint(1), unlock.varint(2)) == (12, 1)
    assert (guide.text(1), guide.text(2)) == (
        "GuideGrid: 51412444209",
        "true",
    )
    assert roguelike_item.varint(3) == profile.roguelike_keys
    assert profile.roguelike_keys >= 1


def test_migrated_profile_defaults_to_no_active_roguelike_run():
    profile = LocalProfile.model_validate(
        {
            "account_id": "local",
            "stage_results": {"10001": 3},
        }
    )

    assert profile.roguelike_keys == 1
    assert profile.default_items == {}
    assert profile.roguelike_run is None
    assert profile.stage_results == {10001: 3}


def test_profile_round_trips_complete_typed_roguelike_run_state():
    profile = LocalProfile.model_validate(
        {
            "roguelike_run": {
                "version": 7,
                "random_seed": 12345,
                "toy_tops": {
                    "1": {
                        "hp": 900,
                        "buffs": {"3812": 2},
                        "parts": {
                            "2001": {
                                "level": 2,
                                "current_skin": 3,
                                "location_kerns": {"4": 5001},
                            }
                        },
                    },
                    "2": {"hp": 800},
                    "3": {"hp": 700},
                },
                "nodes": {
                    "10003": {
                        "status": 1,
                        "event_id": 110019,
                        "location_exports": [100095, 100080, 100090],
                    }
                },
                "event_buffs": {"4214": 1},
                "battle_wins": 1,
                "pending_battle_reward": True,
            }
        }
    )

    run = profile.roguelike_run
    assert run is not None
    assert (run.chapter_id, run.chapter_level, run.map_id) == (-1, 1, 0)
    assert (run.location, run.main_top, run.emitter) == (3, 1, 0)
    assert run.toy_tops[1].buffs == {3812: 2}
    part = run.toy_tops[1].parts[2001]
    assert (part.level, part.current_skin, part.location_kerns) == (
        2,
        3,
        {4: 5001},
    )
    assert run.nodes[10003].location_exports == [100095, 100080, 100090]
    assert run.event_buffs == {4214: 1}
    assert (run.battle_wins, run.pending_battle_reward) == (1, True)


def test_canonical_signed_integer_decoder_enforces_declared_widths():
    assert logic.decode_canonical_int32(encode_varint(0), 0) == (0, 1)
    assert logic.decode_canonical_int32(encode_varint(2_147_483_647), 0) == (
        2_147_483_647,
        5,
    )
    assert logic.decode_canonical_int32(encode_varint(-1), 0) == (-1, 10)
    assert logic.decode_canonical_int32(
        encode_varint(-2_147_483_648), 0
    ) == (-2_147_483_648, 10)
    assert logic.decode_canonical_int64(encode_varint(0xFFFF_FFFF), 0) == (
        0xFFFF_FFFF,
        5,
    )
    assert logic.decode_canonical_int64(encode_varint(-1), 0) == (-1, 10)

    for invalid in (
        b"\x80\x00",
        bytes.fromhex("ff ff ff ff 0f"),
        encode_varint(0x8000_0000),
        encode_varint(0xFFFF_FFFF),
    ):
        with pytest.raises(ValueError):
            logic.decode_canonical_int32(invalid, 0)


def test_roguelike_request_parsers_preserve_all_source_fields_and_order():
    enter_map = logic.parse_roguelike_enter_map(_enter_map_payload())
    assert enter_map.roguelike_version == 0
    assert (
        enter_map.chapter_id,
        enter_map.chapter_level,
        enter_map.seed,
    ) == (-1, 1, 123456)
    assert enter_map.init_node.location == 3
    assert enter_map.init_node.event is None
    assert [top.hp for top in enter_map.init_toy_tops] == [1000, 900, 800]
    assert [top.buffs for top in enter_map.init_toy_tops] == [(), (), ()]
    assert (enter_map.is_buy_key, enter_map.map_id) == (0, 0)
    assert enter_map.node_distribute is None
    assert enter_map.cost_key == 1

    enter_node = logic.parse_roguelike_enter_node(
        _enter_node_payload(
            version=7,
            location=10003,
            event_id=110019,
            exports=(100095, 100080, 100090),
            refresh=1,
        )
    )
    assert (enter_node.roguelike_version, enter_node.chapter_id) == (7, -1)
    assert enter_node.new_node.location == 10003
    assert enter_node.new_node.event is not None
    assert (
        enter_node.new_node.event.event_id,
        enter_node.new_node.event.location_exports,
    ) == (110019, (100095, 100080, 100090))
    assert enter_node.refresh_node == 1

    trigger = logic.parse_roguelike_trigger(
        _trigger_payload(
            version=7,
            location=20002,
            event_id=110001,
            exports=(100001, 100002, 100003),
            path=(110001,),
            hp=(800, 700, 600),
            energy_type=0,
            clear=1,
        )
    )
    assert (trigger.roguelike_version, trigger.chapter_id) == (7, -1)
    assert trigger.cur_node.location == 20002
    assert trigger.cur_node.event is not None
    assert trigger.cur_node.event.location_exports == (
        100001,
        100002,
        100003,
    )
    assert trigger.trigger_path == (110001,)
    assert [top.hp for top in trigger.now_toy_tops] == [800, 700, 600]
    assert (
        trigger.trigger_location,
        trigger.trigger_all_node,
        trigger.energy_type,
        trigger.clear_next_battle_buff,
    ) == (0, 0, 0, 1)
    assert (
        trigger.use_buff,
        trigger.refresh_times,
        trigger.bargain_times,
        trigger.steal_times,
        trigger.discount_list,
        trigger.discount_list_present,
        trigger.is_steal,
    ) == (None, None, None, None, (), False, None)


def test_roguelike_parser_rejects_duplicate_unknown_and_truncated_fields():
    valid = _enter_node_payload(version=7, location=3)
    invalid_payloads = (
        valid + field_varint(1, 7),
        valid + field_varint(4, 0),
        valid[:-1],
    )

    for payload in invalid_payloads:
        with pytest.raises(ValueError):
            logic.parse_roguelike_enter_node(payload)


def test_player_data_builders_encode_absolute_keys_and_default_item_totals():
    profile = _active_profile()

    full = decode_fields(build_player_data(profile))
    delta = decode_fields(logic.build_roguelike_player_delta(profile))
    expected_items = [
        (1194340400, 5),
        (1295005745, 1),
        (1295005746, 1),
    ]
    for player_data in (full, delta):
        base = player_data.message(1)
        assert [
            (entry.varint(1), entry.varint(2))
            for entry in base.messages(22)
        ] == expected_items
        assert player_data.message(17).varint(3) == 2


def test_roguelike_snapshot_builder_encodes_complete_keyed_run_state():
    snapshot = decode_fields(logic.build_roguelike_info(_active_profile()))
    run_map = snapshot.message(1)

    assert (
        run_map.varint(1),
        _signed32(run_map.varint(3)),
        run_map.varint(4),
        run_map.varint(5),
        run_map.varint(7),
    ) == (7, -1, 1, 123456, 0)
    status = run_map.message(2)
    assert (status.varint(1), status.varint(2), status.varint(3)) == (
        10003,
        1,
        0,
    )
    tops = {
        entry.varint(1): entry.message(2) for entry in status.messages(4)
    }
    assert sorted(tops) == [1, 2, 3]
    assert [tops[index].varint(1) for index in (1, 2, 3)] == [
        1000,
        900,
        800,
    ]
    assert [
        (entry.varint(1), entry.varint(2))
        for entry in tops[1].messages(2)
    ] == [(3861, 2)]
    parts = {
        entry.varint(1): entry.message(2)
        for entry in tops[1].messages(3)
    }
    assert sorted(parts) == [2001, 2002, 2003]
    assert (parts[2001].varint(1), parts[2001].varint(2)) == (2, 3)
    assert [
        (entry.varint(1), entry.varint(2))
        for entry in parts[2001].messages(3)
    ] == [(4, 5001)]
    assert [
        (entry.varint(1), entry.varint(2))
        for entry in status.messages(5)
    ] == [(4214, 2)]

    nodes = {
        entry.varint(1): entry.message(2)
        for entry in run_map.messages(6)
    }
    assert sorted(nodes) == [3, 10003]
    assert nodes[3].varint(1) == 3
    story = nodes[10003]
    assert story.varint(1) == 1
    event = story.message(2)
    assert event.varint(1) == 110019
    assert [
        (entry.varint(1), entry.varint(2))
        for entry in event.messages(2)
    ] == [(0, 100095), (1, 100080), (2, 100090)]


@pytest.mark.parametrize(
    ("code", "rewards"),
    [
        pytest.param(10, (), id="enter-map"),
        pytest.param(20, (), id="enter-node"),
        pytest.param(31, (), id="empty-trigger"),
        pytest.param(
            31,
            ((1194340400, 5), (1295005745, 1), (1295005746, 1)),
            id="reward-trigger",
        ),
    ],
)
def test_roguelike_response_builder_encodes_all_success_shapes(
    code: int, rewards: tuple[tuple[int, int], ...]
):
    response = decode_fields(
        logic.build_roguelike_response(
            code=code,
            location=20002,
            rewards=rewards,
        )
    )

    assert (response.varint(1), response.varint(4)) == (code, 20002)
    if code != 31:
        assert 3 not in response.values
        return
    get_items = response.message(3)
    assert get_items.varint(1) == 16
    items_detail = get_items.message(2)
    assert [
        (entry.varint(1), entry.varint(2))
        for entry in items_detail.messages(1)
    ] == list(rewards)
    assert _signed32(response.varint(5)) == -1


def test_enter_prologue_persists_complete_run_before_ordered_responses(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(pack_frame(181, _enter_map_payload()))
        frames = [_receive_frame(websocket) for _ in range(3)]

    assert [net_id for net_id, _ in frames] == [5, 1, 180]
    snapshot = decode_fields(frames[0][1]).message(1)
    assert (
        snapshot.varint(1),
        _signed32(snapshot.varint(3)),
        snapshot.varint(4),
        snapshot.varint(5),
        snapshot.varint(7),
) == (_run_version(), -1, 1, 123456, 0)
    status = snapshot.message(2)
    assert (status.varint(1), status.varint(2), status.varint(3)) == (
        3,
        1,
        0,
    )
    tops = {
        entry.varint(1): entry.message(2) for entry in status.messages(4)
    }
    assert [tops[index].varint(1) for index in (1, 2, 3)] == [
        1000,
        900,
        800,
    ]
    assert {
        index: sorted(
            entry.varint(1) for entry in tops[index].messages(3)
        )
        for index in (1, 2, 3)
    } == {
        1: [2001, 2002, 2003],
        2: [2004, 2005, 2006],
        3: [2028, 2029, 2030],
    }
    key_delta = decode_fields(frames[1][1])
    assert key_delta.message(17).varint(3) == 0
    response = decode_fields(frames[2][1])
    assert (response.varint(1), response.varint(4)) == (10, 3)

    restored = store.load("local")
    run = restored.roguelike_run
    assert restored.roguelike_keys == 0
    assert run is not None
    # Version is an assigned map timestamp, not a counter.
    assert run.version > MIN_MAP_VERSION
    assert run.model_dump() == {
        "version": run.version,
        "chapter_id": -1,
        "chapter_level": 1,
        "random_seed": 123456,
        "map_id": 0,
        "location": 3,
        "main_top": 1,
        "emitter": 0,
        "toy_tops": {
            1: {
                "hp": 1000,
                "max_hp": 1000,
                "buffs": {},
                "parts": {
                    2001: {
                        "level": 1,
                        "current_skin": 0,
                        "location_kerns": {},
                    },
                    2002: {
                        "level": 1,
                        "current_skin": 0,
                        "location_kerns": {},
                    },
                    2003: {
                        "level": 1,
                        "current_skin": 0,
                        "location_kerns": {},
                    },
                },
            },
            2: {
                "hp": 900,
                "max_hp": 900,
                "buffs": {},
                "parts": {
                    2004: {
                        "level": 1,
                        "current_skin": 0,
                        "location_kerns": {},
                    },
                    2005: {
                        "level": 1,
                        "current_skin": 0,
                        "location_kerns": {},
                    },
                    2006: {
                        "level": 1,
                        "current_skin": 0,
                        "location_kerns": {},
                    },
                },
            },
            3: {
                "hp": 800,
                "max_hp": 800,
                "buffs": {},
                "parts": {
                    2028: {
                        "level": 1,
                        "current_skin": 0,
                        "location_kerns": {},
                    },
                    2029: {
                        "level": 1,
                        "current_skin": 0,
                        "location_kerns": {},
                    },
                    2030: {
                        "level": 1,
                        "current_skin": 0,
                        "location_kerns": {},
                    },
                },
            },
        },
        "nodes": {},
        "event_buffs": {},
        "battle_wins": 0,
        "pending_battle_reward": False,
    }
    journal = [
        json.loads(line)
        for line in (tmp_path / "logic-frames.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    receive = [
        entry
        for entry in journal
        if entry["direction"] == "recv" and entry["net_id"] == 181
    ]
    assert len(receive) == 1
    assert {
        key: value for key, value in receive[0].items() if key != "time"
    } == {
        "direction": "recv",
        "net_id": 181,
        "known": True,
        "roguelike_version": 0,
        "chapter_id": -1,
        "location": 3,
    }


def test_automatic_start_completes_initial_node(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(pack_frame(181, _enter_map_payload()))
        for _ in range(3):
            _receive_frame(websocket)
        websocket.send_bytes(
            pack_frame(
                182,
                _enter_node_payload(version=_run_version(), location=3),
            )
        )
        frames = [_receive_frame(websocket) for _ in range(2)]

    assert [net_id for net_id, _ in frames] == [5, 180]
    run_map = decode_fields(frames[0][1]).message(1)
    status = run_map.message(2)
    assert status.varint(1) == 3
    nodes = {
        entry.varint(1): entry.message(2)
        for entry in run_map.messages(6)
    }
    assert nodes[3].varint(1) == 3
    assert 2 not in nodes[3].values
    response = decode_fields(frames[1][1])
    assert (response.varint(1), response.varint(4)) == (20, 3)
    restored = store.load("local").roguelike_run
    assert restored is not None
    assert restored.location == 3
    assert restored.nodes[3].model_dump() == {
        "status": 3,
        "event_id": None,
        "location_exports": [],
    }


def test_enter_story_persists_initial_event(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        _start_run(websocket)
        websocket.send_bytes(
            pack_frame(
                182,
                _enter_node_payload(
                    version=_run_version(),
                    location=10003,
                    event_id=110000,
                ),
            )
        )
        frames = [_receive_frame(websocket) for _ in range(2)]

    assert [net_id for net_id, _ in frames] == [5, 180]
    run_map = decode_fields(frames[0][1]).message(1)
    assert run_map.message(2).varint(1) == 10003
    nodes = {
        entry.varint(1): entry.message(2)
        for entry in run_map.messages(6)
    }
    assert nodes[3].varint(1) == 3
    story = nodes[10003]
    assert story.varint(1) == 1
    assert story.message(2).varint(1) == 110000
    assert 2 not in story.message(2).values
    response = decode_fields(frames[1][1])
    assert (response.varint(1), response.varint(4)) == (20, 10003)
    restored = store.load("local").roguelike_run
    assert restored is not None
    assert restored.location == 10003
    assert restored.nodes[10003].model_dump() == {
        "status": 1,
        "event_id": 110000,
        "location_exports": [],
    }
    journal = [
        json.loads(line)
        for line in (tmp_path / "logic-frames.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    receive = [
        entry
        for entry in journal
        if entry["direction"] == "recv"
        and entry["net_id"] == 182
        and entry.get("location") == 10003
    ]
    assert {
        key: value for key, value in receive[0].items() if key != "time"
    } == {
        "direction": "recv",
        "net_id": 182,
        "known": True,
        "roguelike_version": _run_version(),
        "chapter_id": -1,
        "location": 10003,
        "event_id": 110000,
    }


def test_choose_chip_branch_persists_three_fixed_starter_exports(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        _reach_story(websocket)
        websocket.send_bytes(
            pack_frame(
                182,
                _enter_node_payload(
                    version=_run_version(),
                    location=10003,
                    event_id=110019,
                    refresh=1,
                ),
            )
        )
        frames = [_receive_frame(websocket) for _ in range(2)]

    assert [net_id for net_id, _ in frames] == [5, 180]
    run_map = decode_fields(frames[0][1]).message(1)
    nodes = {
        entry.varint(1): entry.message(2)
        for entry in run_map.messages(6)
    }
    story = nodes[10003]
    assert story.varint(1) == 1
    event = story.message(2)
    assert event.varint(1) == 110019
    assert [
        (entry.varint(1), entry.varint(2))
        for entry in event.messages(2)
    ] == [(0, 100095), (1, 100080), (2, 100090)]
    response = decode_fields(frames[1][1])
    assert (response.varint(1), response.varint(4)) == (20, 10003)
    restored = store.load("local").roguelike_run
    assert restored is not None
    assert restored.nodes[10003].model_dump() == {
        "status": 1,
        "event_id": 110019,
        "location_exports": [100095, 100080, 100090],
    }


@pytest.mark.parametrize(
    ("selected_export", "expected_buff"),
    [
        pytest.param(100095, 4214, id="heal-starter"),
        pytest.param(100080, 4223, id="utility-starter"),
        pytest.param(100090, 4233, id="skill-starter"),
    ],
)
def test_finish_chip_branch_applies_selected_global_buff(
    monkeypatch,
    tmp_path: Path,
    selected_export: int,
    expected_buff: int,
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        _reach_chip_branch(websocket)
        websocket.send_bytes(
            pack_frame(
                184,
                _trigger_payload(
                    version=_run_version(),
                    location=10003,
                    event_id=110019,
                    exports=(selected_export,),
                    path=(110000, 110019),
                    hp=(1000, 900, 800),
                    energy_type=-1,
                    clear=0,
                ),
            )
        )
        frames = [_receive_frame(websocket) for _ in range(2)]

    assert [net_id for net_id, _ in frames] == [5, 180]
    run_map = decode_fields(frames[0][1]).message(1)
    status = run_map.message(2)
    assert [
        (entry.varint(1), entry.varint(2))
        for entry in status.messages(5)
    ] == [(expected_buff, 1)]
    nodes = {
        entry.varint(1): entry.message(2)
        for entry in run_map.messages(6)
    }
    story = nodes[10003]
    assert story.varint(1) == 3
    assert [
        entry.varint(2) for entry in story.message(2).messages(2)
    ] == [100095, 100080, 100090]
    response = decode_fields(frames[1][1])
    assert (response.varint(1), response.varint(4)) == (31, 10003)
    get_items = response.message(3)
    assert get_items.varint(1) == 16
    assert get_items.message(2).messages(1) == []
    restored = store.load("local").roguelike_run
    assert restored is not None
    assert restored.nodes[10003].status == 3
    assert restored.nodes[10003].location_exports == [
        100095,
        100080,
        100090,
    ]
    assert restored.event_buffs == {expected_buff: 1}
    assert [
        restored.toy_tops[index].hp for index in (1, 2, 3)
    ] == [1000, 900, 800]


def test_choose_talk_branch_persists_empty_exports(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        _reach_story(websocket)
        websocket.send_bytes(
            pack_frame(
                182,
                _enter_node_payload(
                    version=_run_version(),
                    location=10003,
                    event_id=110005,
                    refresh=1,
                ),
            )
        )
        frames = [_receive_frame(websocket) for _ in range(2)]

    assert [net_id for net_id, _ in frames] == [5, 180]
    run_map = decode_fields(frames[0][1]).message(1)
    nodes = {
        entry.varint(1): entry.message(2)
        for entry in run_map.messages(6)
    }
    story = nodes[10003]
    assert story.varint(1) == 1
    event = story.message(2)
    assert event.varint(1) == 110005
    assert 2 not in event.values
    response = decode_fields(frames[1][1])
    assert (response.varint(1), response.varint(4)) == (20, 10003)
    restored = store.load("local").roguelike_run
    assert restored is not None
    assert restored.nodes[10003].model_dump() == {
        "status": 1,
        "event_id": 110005,
        "location_exports": [],
    }


def test_finish_talk_branch_completes_without_event_buff(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        _reach_talk_branch(websocket)
        websocket.send_bytes(
            pack_frame(
                184,
                _trigger_payload(
                    version=_run_version(),
                    location=10003,
                    event_id=110005,
                    exports=(),
                    path=(110000, 110005),
                    hp=(1000, 900, 800),
                    energy_type=-1,
                    clear=0,
                ),
            )
        )
        frames = [_receive_frame(websocket) for _ in range(2)]

    assert [net_id for net_id, _ in frames] == [5, 180]
    run_map = decode_fields(frames[0][1]).message(1)
    status = run_map.message(2)
    assert 5 not in status.values
    nodes = {
        entry.varint(1): entry.message(2)
        for entry in run_map.messages(6)
    }
    assert nodes[10003].varint(1) == 3
    event = nodes[10003].message(2)
    assert event.varint(1) == 110005
    assert 2 not in event.values
    response = decode_fields(frames[1][1])
    assert (response.varint(1), response.varint(4)) == (31, 10003)
    assert response.message(3).message(2).messages(1) == []
    restored = store.load("local").roguelike_run
    assert restored is not None
    assert restored.nodes[10003].status == 3
    assert restored.event_buffs == {}


@pytest.mark.parametrize("location", [20002, 20004])
def test_enter_battle_persists_source_event_and_exports(
    monkeypatch, tmp_path: Path, location: int
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        _finish_chip_branch(websocket)
        websocket.send_bytes(
            pack_frame(
                182,
                _enter_node_payload(
                    version=_run_version(),
                    location=location,
                    event_id=110001,
                    exports=(100001, 100002, 100003),
                ),
            )
        )
        frames = [_receive_frame(websocket) for _ in range(2)]

    assert [net_id for net_id, _ in frames] == [5, 180]
    run_map = decode_fields(frames[0][1]).message(1)
    assert run_map.message(2).varint(1) == location
    nodes = {
        entry.varint(1): entry.message(2)
        for entry in run_map.messages(6)
    }
    battle = nodes[location]
    assert battle.varint(1) == 1
    event = battle.message(2)
    assert event.varint(1) == 110001
    assert [
        entry.varint(2) for entry in event.messages(2)
    ] == [100001, 100002, 100003]
    response = decode_fields(frames[1][1])
    assert (response.varint(1), response.varint(4)) == (20, location)
    restored = store.load("local").roguelike_run
    assert restored is not None
    assert restored.location == location
    assert restored.nodes[location].model_dump() == {
        "status": 1,
        "event_id": 110001,
        "location_exports": [100001, 100002, 100003],
    }


def test_battle_win_persists_hp_and_awards_exact_rewards_once(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        _enter_first_battle(websocket)
        websocket.send_bytes(
            pack_frame(
                184,
                _trigger_payload(
                    version=_run_version(),
                    location=20002,
                    event_id=110001,
                    exports=(100001, 100002, 100003),
                    path=(110001,),
                    hp=(900, 800, 700),
                    energy_type=0,
                    clear=1,
                ),
            )
        )
        frames = [_receive_frame(websocket) for _ in range(3)]

    assert [net_id for net_id, _ in frames] == [5, 1, 180]
    run_map = decode_fields(frames[0][1]).message(1)
    status = run_map.message(2)
    tops = {
        entry.varint(1): entry.message(2) for entry in status.messages(4)
    }
    assert [tops[index].varint(1) for index in (1, 2, 3)] == [
        900,
        800,
        700,
    ]
    nodes = {
        entry.varint(1): entry.message(2)
        for entry in run_map.messages(6)
    }
    battle = nodes[20002]
    assert battle.varint(1) == 2
    assert [
        entry.varint(2) for entry in battle.message(2).messages(2)
    ] == [100001, 100002, 100003]

    player_delta = decode_fields(frames[1][1])
    assert [
        (entry.varint(1), entry.varint(2))
        for entry in player_delta.message(1).messages(22)
    ] == [
        (1194340400, 5),
        (1295005745, 1),
        (1295005746, 1),
    ]
    response = decode_fields(frames[2][1])
    assert (response.varint(1), response.varint(4)) == (31, 20002)
    assert _signed32(response.varint(5)) == -1
    get_items = response.message(3)
    assert get_items.varint(1) == 16
    assert [
        (entry.varint(1), entry.varint(2))
        for entry in get_items.message(2).messages(1)
    ] == [
        (1194340400, 5),
        (1295005745, 1),
        (1295005746, 1),
    ]

    restored = store.load("local")
    run = restored.roguelike_run
    assert run is not None
    assert run.nodes[20002].status == 2
    assert run.nodes[20002].location_exports == [
        100001,
        100002,
        100003,
    ]
    assert [run.toy_tops[index].hp for index in (1, 2, 3)] == [
        900,
        800,
        700,
    ]
    assert run.battle_wins == 1
    assert run.pending_battle_reward is True
    assert restored.default_items == {
        1194340400: 5,
        1295005745: 1,
        1295005746: 1,
    }
    journal = [
        json.loads(line)
        for line in (tmp_path / "logic-frames.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    battle_win_receive = [
        entry
        for entry in journal
        if entry["direction"] == "recv" and entry["net_id"] == 184
    ][-1]
    assert {
        key: value
        for key, value in battle_win_receive.items()
        if key != "time"
    } == {
        "direction": "recv",
        "net_id": 184,
        "known": True,
        "roguelike_version": _run_version(),
        "chapter_id": -1,
        "location": 20002,
        "event_id": 110001,
        "location_exports": [100001, 100002, 100003],
        "trigger_path": [110001],
        "toy_tops": [{"hp": 900}, {"hp": 800}, {"hp": 700}],
    }


POSTBATTLE_CASES = [
    (100066, 4201),
    (100067, 4202),
    (100068, 4203),
    (100069, 4204),
    (100070, 4205),
    (100071, 4206),
    (100072, 4207),
    (100073, 4208),
    (100074, 4209),
    (100075, 4210),
    (100076, 4211),
    (100077, 4212),
    (100078, 4221),
    (100079, 4222),
    (100081, 4224),
    (100082, 4225),
    (100083, 4226),
    (100084, 4227),
    (100085, 4228),
    (100088, 4231),
]


def test_production_postbattle_export_pool_matches_approved_mapping():
    assert logic_route.POSTBATTLE_EXPORTS == {
        100066: 4201,
        100067: 4202,
        100068: 4203,
        100069: 4204,
        100070: 4205,
        100071: 4206,
        100072: 4207,
        100073: 4208,
        100074: 4209,
        100075: 4210,
        100076: 4211,
        100077: 4212,
        100078: 4221,
        100079: 4222,
        100081: 4224,
        100082: 4225,
        100083: 4226,
        100084: 4227,
        100085: 4228,
        100088: 4231,
    }
    assert len(logic_route.POSTBATTLE_EXPORTS) == 20


def _expected_claim_hp(export_key: int, saved_hp: int) -> int:
    if export_key == 100069:
        return (11 * saved_hp + 9) // 10
    if export_key == 100077:
        return (6 * saved_hp + 4) // 5
    return saved_hp


@pytest.mark.parametrize(
    ("selected_export", "expected_buff"), POSTBATTLE_CASES
)
def test_postbattle_claim_applies_exact_pool_buff_and_hp_effect(
    monkeypatch,
    tmp_path: Path,
    selected_export: int,
    expected_buff: int,
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = _battle_profile(
        status=2,
        pending_reward=True,
        hp=(900, 800, 700),
    )
    store.save(profile)
    expected_hp = tuple(
        _expected_claim_hp(selected_export, value)
        for value in (900, 800, 700)
    )

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                184,
                _trigger_payload(
                    version=7,
                    location=20002,
                    event_id=110001,
                    exports=(selected_export,),
                    path=(),
                    hp=expected_hp,
                    energy_type=-1,
                    clear=0,
                ),
            )
        )
        frames = [_receive_frame(websocket) for _ in range(2)]

    assert [net_id for net_id, _ in frames] == [5, 180]
    run_map = decode_fields(frames[0][1]).message(1)
    status = run_map.message(2)
    tops = {
        entry.varint(1): entry.message(2) for entry in status.messages(4)
    }
    assert tuple(tops[index].varint(1) for index in (1, 2, 3)) == (
        expected_hp
    )
    event_buffs = {
        entry.varint(1): entry.varint(2)
        for entry in status.messages(5)
    }
    assert event_buffs[expected_buff] == 1
    nodes = {
        entry.varint(1): entry.message(2)
        for entry in run_map.messages(6)
    }
    battle = nodes[20002]
    assert battle.varint(1) == 3
    assert [
        entry.varint(2) for entry in battle.message(2).messages(2)
    ] == [100001, 100002, 100003]
    response = decode_fields(frames[1][1])
    assert (response.varint(1), response.varint(4)) == (31, 20002)
    assert response.message(3).message(2).messages(1) == []

    restored = store.load("local")
    run = restored.roguelike_run
    assert run is not None
    assert run.nodes[20002].status == 3
    assert run.nodes[20002].location_exports == [
        100001,
        100002,
        100003,
    ]
    assert run.pending_battle_reward is False
    assert tuple(
        run.toy_tops[index].hp for index in (1, 2, 3)
    ) == expected_hp
    assert run.event_buffs[expected_buff] == 1


def test_restart_after_battle_win_restores_full_wire_and_typed_state(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")

    with TestClient(app) as first_client:
        with first_client.websocket_connect("/ws") as websocket:
            _login(websocket, profile)
            _win_first_battle(websocket)

    persisted = store.load("local")
    with TestClient(app) as restarted_client:
        with restarted_client.websocket_connect("/ws") as websocket:
            restart_frames = _login(websocket, persisted)

    _assert_restart_login_state(
        restart_frames,
        battle_status=2,
        hp=(900, 800, 700),
        event_buffs={4214: 1},
    )
    run = persisted.roguelike_run
    assert run is not None
    assert run.battle_wins == 1
    assert run.pending_battle_reward is True


def test_restart_after_postbattle_claim_preserves_battle_exports(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")

    with TestClient(app) as first_client:
        with first_client.websocket_connect("/ws") as websocket:
            _login(websocket, profile)
            _win_first_battle(websocket)

    won_profile = store.load("local")
    with TestClient(app) as claim_client:
        with claim_client.websocket_connect("/ws") as websocket:
            _login(websocket, won_profile)
            websocket.send_bytes(
                pack_frame(
                    184,
                    _trigger_payload(
                        version=_run_version(),
                        location=20002,
                        event_id=110001,
                        exports=(100069,),
                        path=(),
                        hp=(990, 880, 770),
                        energy_type=-1,
                        clear=0,
                    ),
                )
            )
            assert [
                _receive_frame(websocket)[0] for _ in range(2)
            ] == [5, 180]

    claimed = store.load("local")
    with TestClient(app) as restarted_client:
        with restarted_client.websocket_connect("/ws") as websocket:
            restart_frames = _login(websocket, claimed)

    _assert_restart_login_state(
        restart_frames,
        battle_status=3,
        hp=(990, 880, 770),
        event_buffs={4204: 1, 4214: 1},
    )
    run = claimed.roguelike_run
    assert run is not None
    assert run.nodes[20002].location_exports == [
        100001,
        100002,
        100003,
    ]
    assert 100069 not in run.nodes[20002].location_exports
    assert run.battle_wins == 1
    assert run.pending_battle_reward is False


def test_permuted_battle_exports_survive_win_claim_and_restart(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")
    battle_exports = (100003, 100001, 100002)

    with TestClient(app) as first_client:
        with first_client.websocket_connect("/ws") as websocket:
            _login(websocket, profile)
            _finish_chip_branch(websocket)
            websocket.send_bytes(
                pack_frame(
                    182,
                    _enter_node_payload(
                        version=_run_version(),
                        location=20002,
                        event_id=110001,
                        exports=battle_exports,
                    ),
                )
            )
            assert [
                _receive_frame(websocket)[0] for _ in range(2)
            ] == [5, 180]
            websocket.send_bytes(
                pack_frame(
                    184,
                    _trigger_payload(
                        version=_run_version(),
                        location=20002,
                        event_id=110001,
                        exports=battle_exports,
                        path=(110001,),
                        hp=(900, 800, 700),
                        energy_type=0,
                        clear=1,
                    ),
                )
            )
            assert [
                _receive_frame(websocket)[0] for _ in range(3)
            ] == [5, 1, 180]
            websocket.send_bytes(
                pack_frame(
                    184,
                    _trigger_payload(
                        version=_run_version(),
                        location=20002,
                        event_id=110001,
                        exports=(100066,),
                        path=(),
                        hp=(900, 800, 700),
                        energy_type=-1,
                        clear=0,
                    ),
                )
            )
            assert [
                _receive_frame(websocket)[0] for _ in range(2)
            ] == [5, 180]

    persisted = store.load("local")
    with TestClient(app) as restarted_client:
        with restarted_client.websocket_connect("/ws") as websocket:
            restart_frames = _login(websocket, persisted)

    assert [net_id for net_id, _ in restart_frames] == [1, 2, 5, 129]
    run_map = decode_fields(restart_frames[2][1]).message(1)
    nodes = {
        entry.varint(1): entry.message(2)
        for entry in run_map.messages(6)
    }
    battle = nodes[20002]
    assert battle.varint(1) == 3
    assert [
        entry.varint(2) for entry in battle.message(2).messages(2)
    ] == list(battle_exports)
    run = persisted.roguelike_run
    assert run is not None
    assert run.nodes[20002].location_exports == list(battle_exports)
    assert run.pending_battle_reward is False


def _assert_rejected_without_save(
    *,
    monkeypatch,
    tmp_path: Path,
    profile: LocalProfile,
    net_id: int,
    payload: bytes,
) -> None:
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    store.save(profile)
    saved_path = tmp_path / "local.json"
    before = saved_path.read_text(encoding="utf-8")
    original_save = ProfileStore.save
    save_calls: list[LocalProfile] = []

    def recording_save(self, saved_profile: LocalProfile) -> None:
        save_calls.append(saved_profile.model_copy(deep=True))
        original_save(self, saved_profile)

    monkeypatch.setattr(ProfileStore, "save", recording_save)
    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(pack_frame(net_id, payload))
        message = _receive_message(websocket)

    assert message["type"] == "websocket.close"
    assert message["code"] == 1008
    assert save_calls == []
    assert saved_path.read_text(encoding="utf-8") == before
    assert not (tmp_path / "local.json.tmp").exists()


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(_enter_map_payload(version=1), id="wrong-version"),
        pytest.param(_enter_map_payload(chapter_id=0), id="wrong-chapter"),
        pytest.param(_enter_map_payload(chapter_level=2), id="wrong-level"),
        pytest.param(_enter_map_payload(seed=-1), id="negative-seed"),
        pytest.param(
            _enter_map_payload(seed=157_600_000), id="too-large-seed"
        ),
        pytest.param(_enter_map_payload(init_location=4), id="wrong-node"),
        pytest.param(
            _enter_map_payload(hp=(1000, 0, 800)), id="dead-initial-top"
        ),
        pytest.param(_enter_map_payload(is_buy_key=1), id="bought-key"),
        pytest.param(_enter_map_payload(map_id=1), id="wrong-map"),
        pytest.param(_enter_map_payload(cost_key=0), id="wrong-key-cost"),
    ],
)
def test_invalid_enter_map_semantics_close_without_save(
    monkeypatch, tmp_path: Path, payload: bytes
):
    _assert_rejected_without_save(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        profile=LocalProfile(),
        net_id=181,
        payload=payload,
    )


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(
            _trigger_payload(
                version=8,
                location=20002,
                event_id=110001,
                exports=(100001, 100002, 100003),
                path=(110001,),
                hp=(900, 800, 700),
                energy_type=0,
                clear=1,
            ),
            id="wrong-version",
        ),
        pytest.param(
            _trigger_payload(
                version=7,
                chapter_id=0,
                location=20002,
                event_id=110001,
                exports=(100001, 100002, 100003),
                path=(110001,),
                hp=(900, 800, 700),
                energy_type=0,
                clear=1,
            ),
            id="wrong-chapter",
        ),
        pytest.param(
            _trigger_payload(
                version=7,
                location=20004,
                event_id=110001,
                exports=(100001, 100002, 100003),
                path=(110001,),
                hp=(900, 800, 700),
                energy_type=0,
                clear=1,
            ),
            id="wrong-location",
        ),
        pytest.param(
            _trigger_payload(
                version=7,
                location=20002,
                event_id=110005,
                exports=(100001, 100002, 100003),
                path=(110001,),
                hp=(900, 800, 700),
                energy_type=0,
                clear=1,
            ),
            id="wrong-event",
        ),
        pytest.param(
            _trigger_payload(
                version=7,
                location=20002,
                event_id=110001,
                exports=(100001, 100002, 100003),
                path=(110000,),
                hp=(900, 800, 700),
                energy_type=0,
                clear=1,
            ),
            id="wrong-path",
        ),
        pytest.param(
            _trigger_payload(
                version=7,
                location=20002,
                event_id=110001,
                exports=(100001, 100002),
                path=(110001,),
                hp=(900, 800, 700),
                energy_type=0,
                clear=1,
            ),
            id="wrong-export-set",
        ),
        pytest.param(
            _trigger_payload(
                version=7,
                location=20002,
                event_id=110001,
                exports=(100001, 100002, 100003),
                path=(110001,),
                hp=(900, 800, 700),
                energy_type=0,
                clear=1,
                extra_trigger_fields=field_varint(7, 1),
            ),
            id="unsupported-use-buff",
        ),
        pytest.param(
            _trigger_payload(
                version=7,
                location=20002,
                event_id=110001,
                exports=(100001, 100002, 100003),
                path=(110001,),
                hp=(900, 800, 700),
                energy_type=0,
                clear=1,
                extra_trigger_fields=field_bytes(12, b""),
            ),
            id="unsupported-empty-discount-field",
        ),
    ],
)
def test_invalid_battle_contract_closes_without_save(
    monkeypatch, tmp_path: Path, payload: bytes
):
    _assert_rejected_without_save(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        profile=_battle_profile(status=1, pending_reward=False),
        net_id=184,
        payload=payload,
    )


@pytest.mark.parametrize(
    "case",
    [
        "enter-map-replay",
        "automatic-start-replay",
        "story-wrong-authoritative-location",
        "choose-chip-replay",
        "finish-chip-replay",
        "choose-talk-replay",
        "finish-talk-replay",
        "cross-branch-trigger",
        "enter-battle-replay",
        "battle-win-replay",
        "postbattle-claim-replay",
    ],
)
def test_invalid_replay_or_state_transition_closes_without_save(
    monkeypatch, tmp_path: Path, case: str
):
    profile = _active_profile()
    run = profile.roguelike_run
    assert run is not None
    if case == "enter-map-replay":
        net_id, payload = 181, _enter_map_payload()
    elif case == "automatic-start-replay":
        net_id, payload = 182, _enter_node_payload(version=7, location=3)
    elif case == "story-wrong-authoritative-location":
        run.location = 999
        run.nodes = {3: RogueLikeNodeState(status=3)}
        net_id, payload = 182, _enter_node_payload(
            version=7,
            location=10003,
            event_id=110000,
        )
    elif case == "choose-chip-replay":
        net_id, payload = 182, _enter_node_payload(
            version=7,
            location=10003,
            event_id=110019,
            refresh=1,
        )
    elif case == "finish-chip-replay":
        run.nodes[10003].status = 3
        net_id, payload = 184, _trigger_payload(
            version=7,
            location=10003,
            event_id=110019,
            exports=(100095,),
            path=(110000, 110019),
            hp=(1000, 900, 800),
            energy_type=-1,
            clear=0,
        )
    elif case == "choose-talk-replay":
        run.nodes[10003] = RogueLikeNodeState(
            status=1,
            event_id=110005,
        )
        net_id, payload = 182, _enter_node_payload(
            version=7,
            location=10003,
            event_id=110005,
            refresh=1,
        )
    elif case == "finish-talk-replay":
        run.nodes[10003] = RogueLikeNodeState(
            status=3,
            event_id=110005,
        )
        net_id, payload = 184, _trigger_payload(
            version=7,
            location=10003,
            event_id=110005,
            exports=(),
            path=(110000, 110005),
            hp=(1000, 900, 800),
            energy_type=-1,
            clear=0,
        )
    elif case == "cross-branch-trigger":
        net_id, payload = 184, _trigger_payload(
            version=7,
            location=10003,
            event_id=110005,
            exports=(),
            path=(110000, 110005),
            hp=(1000, 900, 800),
            energy_type=-1,
            clear=0,
        )
    elif case == "enter-battle-replay":
        profile = _battle_profile(status=1, pending_reward=False)
        net_id, payload = 182, _enter_node_payload(
            version=7,
            location=20002,
            event_id=110001,
            exports=(100001, 100002, 100003),
        )
    elif case == "battle-win-replay":
        profile = _battle_profile(status=2, pending_reward=True)
        net_id, payload = 184, _trigger_payload(
            version=7,
            location=20002,
            event_id=110001,
            exports=(100001, 100002, 100003),
            path=(110001,),
            hp=(900, 800, 700),
            energy_type=0,
            clear=1,
        )
    else:
        profile = _battle_profile(status=3, pending_reward=False)
        net_id, payload = 184, _trigger_payload(
            version=7,
            location=20002,
            event_id=110001,
            exports=(100066,),
            path=(),
            hp=(1000, 900, 800),
            energy_type=-1,
            clear=0,
        )
    _assert_rejected_without_save(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        profile=profile,
        net_id=net_id,
        payload=payload,
    )


@pytest.mark.parametrize(
    ("net_id", "payload"),
    [
        pytest.param(181, b"\x08", id="malformed-truncated"),
        pytest.param(
            182,
            _enter_node_payload(version=7, location=3)
            + field_varint(4, 0),
            id="malformed-unknown-field",
        ),
        pytest.param(
            182,
            _enter_node_payload(version=7, location=3)
            + field_varint(1, 7),
            id="malformed-duplicate-field",
        ),
        pytest.param(
            182,
            field_varint(1, 7)
            + field_bytes(2, b"\x0a\x02\x08")
            + field_varint(3, -1),
            id="malformed-truncated-nesting",
        ),
        pytest.param(
            182,
            b"\x08\x87\x00"
            + _enter_node_payload(version=7, location=3)[2:],
            id="noncanonical-version",
        ),
        pytest.param(183, b"", id="unsupported-id183"),
    ],
)
def test_malformed_noncanonical_or_unsupported_request_closes_without_save(
    monkeypatch, tmp_path: Path, net_id: int, payload: bytes
):
    _assert_rejected_without_save(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        profile=_active_profile(),
        net_id=net_id,
        payload=payload,
    )
    journal = [
        json.loads(line)
        for line in (tmp_path / "logic-frames.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    receive = [
        entry
        for entry in journal
        if entry["direction"] == "recv" and entry["net_id"] == net_id
    ][-1]
    assert set(receive) == {"time", "direction", "net_id", "known"}


@pytest.mark.parametrize(
    "hp",
    [
        pytest.param((1001, 800, 700), id="tampered-hp-increase"),
        pytest.param((0, 0, 0), id="tampered-all-dead"),
    ],
)
def test_tampered_battle_win_hp_closes_without_save(
    monkeypatch, tmp_path: Path, hp: tuple[int, int, int]
):
    _assert_rejected_without_save(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        profile=_battle_profile(status=1, pending_reward=False),
        net_id=184,
        payload=_trigger_payload(
            version=7,
            location=20002,
            event_id=110001,
            exports=(100001, 100002, 100003),
            path=(110001,),
            hp=hp,
            energy_type=0,
            clear=1,
        ),
    )


@pytest.mark.parametrize(
    ("selected_export", "offset"),
    [
        pytest.param(100069, -1, id="ten-percent-minus-one"),
        pytest.param(100069, 1, id="ten-percent-plus-one"),
        pytest.param(100077, -1, id="twenty-percent-minus-one"),
        pytest.param(100077, 1, id="twenty-percent-plus-one"),
    ],
)
def test_tampered_postbattle_claim_hp_closes_without_save(
    monkeypatch,
    tmp_path: Path,
    selected_export: int,
    offset: int,
):
    saved_hp = (900, 800, 700)
    expected = tuple(
        _expected_claim_hp(selected_export, value) for value in saved_hp
    )
    tampered = (expected[0] + offset, expected[1], expected[2])
    _assert_rejected_without_save(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        profile=_battle_profile(
            status=2, pending_reward=True, hp=saved_hp
        ),
        net_id=184,
        payload=_trigger_payload(
            version=7,
            location=20002,
            event_id=110001,
            exports=(selected_export,),
            path=(),
            hp=tampered,
            energy_type=-1,
            clear=0,
        ),
    )


@pytest.mark.parametrize(
    "exports",
    [
        pytest.param((999999,), id="invalid-unknown-export"),
        pytest.param(
            (100066, 100067), id="invalid-multiple-exports"
        ),
    ],
)
def test_invalid_postbattle_export_selection_closes_without_save(
    monkeypatch, tmp_path: Path, exports: tuple[int, ...]
):
    _assert_rejected_without_save(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        profile=_battle_profile(status=2, pending_reward=True),
        net_id=184,
        payload=_trigger_payload(
            version=7,
            location=20002,
            event_id=110001,
            exports=exports,
            path=(),
            hp=(1000, 900, 800),
            energy_type=-1,
            clear=0,
        ),
    )


def test_roguelike_and_profile_put_share_one_profile_transaction(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")
    put_loaded = threading.Event()
    release_put = threading.Event()
    logic_parsed = threading.Event()
    logic_saved = threading.Event()
    put_result: list[object] = []
    put_errors: list[BaseException] = []
    original_load = ProfileStore.load
    original_save = ProfileStore.save
    original_parse = logic.parse_roguelike_enter_map
    pause_lock = threading.Lock()
    pause_next_load = True

    def pausing_load(self, account: str = "local"):
        nonlocal pause_next_load
        loaded = original_load(self, account)
        with pause_lock:
            should_pause = pause_next_load
            if should_pause:
                pause_next_load = False
        if should_pause:
            put_loaded.set()
            assert release_put.wait(3)
        return loaded

    def recording_save(self, saved_profile: LocalProfile) -> None:
        if saved_profile.roguelike_run is not None:
            logic_saved.set()
        original_save(self, saved_profile)

    def recording_parse(payload: bytes):
        parsed = original_parse(payload)
        logic_parsed.set()
        return parsed

    def run_put() -> None:
        try:
            with TestClient(app) as client:
                put_result.append(
                    client.put(
                        "/profile",
                        json={"level": 5, "stages_unlocked": [1, 2, 3]},
                    )
                )
        except BaseException as error:
            put_errors.append(error)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        monkeypatch.setattr(ProfileStore, "load", pausing_load)
        monkeypatch.setattr(ProfileStore, "save", recording_save)
        monkeypatch.setattr(
            logic_route,
            "parse_roguelike_enter_map",
            recording_parse,
            raising=False,
        )
        put_thread = threading.Thread(target=run_put)
        try:
            put_thread.start()
            assert put_loaded.wait(3)
            websocket.send_bytes(pack_frame(181, _enter_map_payload()))
            assert logic_parsed.wait(3)
            assert not logic_saved.wait(0.2)
        finally:
            release_put.set()
            put_thread.join(3)

        assert [_receive_frame(websocket)[0] for _ in range(3)] == [
            5,
            1,
            180,
        ]

    assert not put_thread.is_alive()
    assert put_errors == []
    assert len(put_result) == 1
    assert put_result[0].status_code == 200
    restored = store.load("local")
    assert (restored.level, restored.stages_unlocked) == (5, [1, 2, 3])
    assert restored.roguelike_run is not None
    assert restored.roguelike_run.random_seed == 123456
    assert restored.roguelike_keys == 0
    assert not (tmp_path / "local.json.tmp").exists()


def test_roguelike_save_before_send(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    profile = ProfileStore(tmp_path).load("local")
    original_save = ProfileStore.save
    original_send = WebSocket.send_bytes
    operation_active = threading.Event()
    events: list[str] = []

    def recording_save(self, saved_profile: LocalProfile) -> None:
        if operation_active.is_set():
            events.append("save")
        original_save(self, saved_profile)

    async def recording_send(self, data: bytes) -> None:
        if operation_active.is_set():
            events.append("send")
        await original_send(self, data)

    monkeypatch.setattr(ProfileStore, "save", recording_save)
    monkeypatch.setattr(WebSocket, "send_bytes", recording_send)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        operation_active.set()
        websocket.send_bytes(pack_frame(181, _enter_map_payload()))
        assert [_receive_frame(websocket)[0] for _ in range(3)] == [
            5,
            1,
            180,
        ]

    assert events == ["save", "send", "send", "send"]


def test_websocket_send_and_close_happen_after_profile_transaction(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    profile = ProfileStore(tmp_path).load("local")
    original_transaction = profile_store_module.profile_transaction
    original_send = WebSocket.send_bytes
    original_close = WebSocket.close
    held_depth = threading.local()
    operation_active = threading.Event()
    observations: list[tuple[str, int]] = []

    @contextmanager
    def tracked_transaction():
        depth = getattr(held_depth, "value", 0)
        held_depth.value = depth + 1
        try:
            with original_transaction():
                yield
        finally:
            held_depth.value -= 1

    async def tracked_send(self, data: bytes) -> None:
        if operation_active.is_set():
            observations.append(("send", getattr(held_depth, "value", 0)))
        await original_send(self, data)

    async def tracked_close(
        self, code: int = 1000, reason: str | None = None
    ) -> None:
        if operation_active.is_set():
            observations.append(("close", getattr(held_depth, "value", 0)))
        await original_close(self, code=code, reason=reason)

    monkeypatch.setattr(
        logic_route,
        "profile_transaction",
        tracked_transaction,
        raising=False,
    )
    monkeypatch.setattr(WebSocket, "send_bytes", tracked_send)
    monkeypatch.setattr(WebSocket, "close", tracked_close)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        operation_active.set()
        payload = _enter_map_payload()
        websocket.send_bytes(pack_frame(181, payload))
        assert [_receive_frame(websocket)[0] for _ in range(3)] == [
            5,
            1,
            180,
        ]
        websocket.send_bytes(pack_frame(181, payload))
        message = _receive_message(websocket)

    assert message["type"] == "websocket.close"
    assert message["code"] == 1008
    assert observations == [
        ("send", 0),
        ("send", 0),
        ("send", 0),
        ("close", 0),
    ]


def _run_duplicate_trigger_race(
    *,
    monkeypatch,
    tmp_path: Path,
    profile: LocalProfile,
    payload: bytes,
    accepted_ids: list[int],
) -> tuple[
    list[tuple[str, object]],
    list[LocalProfile],
    list[tuple[str, int]],
]:
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    store.save(profile)
    original_parse = logic.parse_roguelike_trigger
    original_transaction = profile_store_module.profile_transaction
    original_send = WebSocket.send_bytes
    original_close = WebSocket.close
    parse_barrier = threading.Barrier(2)
    held_depth = threading.local()
    track_io = threading.local()
    observations: list[tuple[str, int]] = []
    observation_lock = threading.Lock()

    def barrier_parse(payload_bytes: bytes):
        parsed = original_parse(payload_bytes)
        parse_barrier.wait(3)
        track_io.value = True
        return parsed

    @contextmanager
    def tracked_transaction():
        depth = getattr(held_depth, "value", 0)
        held_depth.value = depth + 1
        try:
            with original_transaction():
                yield
        finally:
            held_depth.value -= 1

    async def tracked_send(self, data: bytes) -> None:
        if getattr(track_io, "value", False):
            with observation_lock:
                observations.append(
                    ("send", getattr(held_depth, "value", 0))
                )
        await original_send(self, data)

    async def tracked_close(
        self, code: int = 1000, reason: str | None = None
    ) -> None:
        if getattr(track_io, "value", False):
            with observation_lock:
                observations.append(
                    ("close", getattr(held_depth, "value", 0))
                )
        await original_close(self, code=code, reason=reason)

    monkeypatch.setattr(
        logic_route,
        "parse_roguelike_trigger",
        barrier_parse,
        raising=False,
    )
    monkeypatch.setattr(
        logic_route,
        "profile_transaction",
        tracked_transaction,
        raising=False,
    )
    monkeypatch.setattr(WebSocket, "send_bytes", tracked_send)
    monkeypatch.setattr(WebSocket, "close", tracked_close)
    original_save = ProfileStore.save
    save_calls: list[LocalProfile] = []
    save_lock = threading.Lock()

    def recording_save(self, saved_profile: LocalProfile) -> None:
        with save_lock:
            save_calls.append(saved_profile.model_copy(deep=True))
        original_save(self, saved_profile)

    monkeypatch.setattr(ProfileStore, "save", recording_save)
    outcomes: list[tuple[str, object]] = []
    errors: list[BaseException] = []
    outcome_lock = threading.Lock()

    def worker() -> None:
        try:
            with TestClient(app) as client:
                current = store.load("local")
                with client.websocket_connect("/ws") as websocket:
                    _login(websocket, current)
                    websocket.send_bytes(pack_frame(184, payload))
                    first = _receive_message(websocket)
                    if first["type"] == "websocket.close":
                        outcome = ("close", first["code"])
                    else:
                        frame_payload = first.get("bytes")
                        assert isinstance(frame_payload, bytes)
                        ids = [unpack_frame(frame_payload)[0]]
                        ids.extend(
                            _receive_frame(websocket)[0]
                            for _ in range(len(accepted_ids) - 1)
                        )
                        outcome = ("frames", ids)
                    with outcome_lock:
                        outcomes.append(outcome)
        except BaseException as error:
            with outcome_lock:
                errors.append(error)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(6)

    assert all(not thread.is_alive() for thread in threads)
    assert errors == []
    assert sorted(outcomes, key=lambda item: item[0]) == [
        ("close", 1008),
        ("frames", accepted_ids),
    ]
    return outcomes, save_calls, observations


def _seed_duplicate_race_profile(profile: LocalProfile) -> None:
    profile.nickname = "Race Account Sentinel"
    profile.player_id = 246_813_579
    profile.level = 27
    profile.stages_unlocked = [1, 4, 9]
    profile.stages_completed = [10001, 10002]
    profile.stage_results = {10001: 7, 10002: 3}


def _assert_duplicate_race_profile_survived(profile: LocalProfile) -> None:
    assert (
        profile.account_id,
        profile.nickname,
        profile.player_id,
        profile.level,
    ) == ("local", "Race Account Sentinel", 246_813_579, 27)
    assert profile.stages_unlocked == [1, 4, 9]
    assert profile.stages_completed == [10001, 10002]
    assert profile.stage_results == {10001: 7, 10002: 3}


def test_concurrent_duplicate_battle_win_commits_once(
    monkeypatch, tmp_path: Path
):
    profile = _battle_profile(status=1, pending_reward=False)
    _seed_duplicate_race_profile(profile)
    payload = _trigger_payload(
        version=7,
        location=20002,
        event_id=110001,
        exports=(100001, 100002, 100003),
        path=(110001,),
        hp=(900, 800, 700),
        energy_type=0,
        clear=1,
    )

    _, save_calls, observations = _run_duplicate_trigger_race(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        profile=profile,
        payload=payload,
        accepted_ids=[5, 1, 180],
    )

    assert len(save_calls) == 1
    restored = ProfileStore(tmp_path).load("local")
    run = restored.roguelike_run
    assert run is not None
    assert run.nodes[20002].status == 2
    assert run.battle_wins == 1
    assert run.pending_battle_reward is True
    assert [run.toy_tops[index].hp for index in (1, 2, 3)] == [
        900,
        800,
        700,
    ]
    assert restored.default_items == {
        1194340400: 5,
        1295005745: 1,
        1295005746: 1,
    }
    _assert_duplicate_race_profile_survived(restored)
    assert sorted(kind for kind, _ in observations) == [
        "close",
        "send",
        "send",
        "send",
    ]
    assert {depth for _, depth in observations} == {0}


def test_concurrent_duplicate_postbattle_claim_commits_once(
    monkeypatch, tmp_path: Path
):
    profile = _battle_profile(status=2, pending_reward=True)
    _seed_duplicate_race_profile(profile)
    payload = _trigger_payload(
        version=7,
        location=20002,
        event_id=110001,
        exports=(100066,),
        path=(),
        hp=(1000, 900, 800),
        energy_type=-1,
        clear=0,
    )

    _, save_calls, observations = _run_duplicate_trigger_race(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        profile=profile,
        payload=payload,
        accepted_ids=[5, 180],
    )

    assert len(save_calls) == 1
    restored = ProfileStore(tmp_path).load("local")
    run = restored.roguelike_run
    assert run is not None
    assert run.nodes[20002].status == 3
    assert run.pending_battle_reward is False
    assert run.event_buffs[4201] == 1
    assert run.nodes[20002].location_exports == [100001, 100002, 100003]
    _assert_duplicate_race_profile_survived(restored)
    assert sorted(kind for kind, _ in observations) == [
        "close",
        "send",
        "send",
    ]
    assert {depth for _, depth in observations} == {0}


@pytest.mark.preservation_artifact
def test_pinned_roguelike_resources_match_reviewed_provenance():
    repository_root = Path(__file__).resolve().parents[2]
    relative_paths = {
        "exports": (
            "cn_apk/assets/assets/resources/native/3f/"
            "3f1233de-f635-459a-8da3-d614ef7801bd.bin"
        ),
        "items": (
            "cn_apk/assets/assets/resources/native/31/"
            "31ff3bb8-b74b-438d-bd47-2be2c04b3922.bin"
        ),
        "skills": (
            "cn_apk/assets/assets/resources/native/6b/"
            "6b3af1c5-70ca-4e06-853f-015ddecfcbe6.bin"
        ),
        "buffs": (
            "cn_apk/assets/assets/resources/native/f1/"
            "f1bdab08-5c31-4765-aa9d-bab68944f141.bin"
        ),
        "part_suits": (
            "cn_apk/assets/assets/resources/native/b4/"
            "b4bc0aa8-8d49-434e-b2fe-722279cdc129.bin"
        ),
    }
    expected_hashes = {
        "exports": "614131b962f90d46dec584fd12fb61c939b17b3a5d91494a95db657915bef393",
        "items": "5c93fcef0dd37afc330a6c6f659b7c137eb243802d2ad56035bec6988d204d43",
        "skills": "71137a629d91edfc4d0cc784743670fe230e6b986208c9ec8e5722b3aa531ac3",
        "buffs": "b4adfbf1842d09d91784ba51ebad9c5f46e3fe59fdf53f204a116f88cfb6dab9",
        "part_suits": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    }
    payloads = {
        name: (repository_root / relative_path).read_bytes()
        for name, relative_path in relative_paths.items()
    }

    assert {
        name: hashlib.sha256(payload).hexdigest()
        for name, payload in payloads.items()
    } == expected_hashes
    assert payloads["part_suits"] == b""

    expected_pool = {
        100066: 4201,
        100067: 4202,
        100068: 4203,
        100069: 4204,
        100070: 4205,
        100071: 4206,
        100072: 4207,
        100073: 4208,
        100074: 4209,
        100075: 4210,
        100076: 4211,
        100077: 4212,
        100078: 4221,
        100079: 4222,
        100081: 4224,
        100082: 4225,
        100083: 4226,
        100084: 4227,
        100085: 4228,
        100088: 4231,
    }
    exports = _items_by_id(payloads["exports"])
    reviewed_pool = {
        export_key: item.varint(2)
        for export_key, item in exports.items()
        if _signed32(item.varint(7)) == -1
        and 1 in item.varints(8)
        and item.varint(9) == 10
        and item.varint(10) > 0
    }
    assert reviewed_pool == expected_pool
    assert len(reviewed_pool) == 20
    for export_key in expected_pool:
        assert exports[export_key].varint(3) == 2
        assert exports[export_key].varint(5) == 1

    chiji_items = _items_by_id(payloads["items"])
    skills = _items_by_id(payloads["skills"])
    buffs = _items_by_id(payloads["buffs"])
    hp_chains = {
        4204: (1861, 3861, 1000),
        4212: (1812, 3812, 2000),
    }
    for item_id, (skill_id, buff_id, factor) in hp_chains.items():
        assert chiji_items[item_id].varint(6) == skill_id
        skill = skills[skill_id]
        assert skill.varint(6) == 23
        assert [entry.varint(1) for entry in skill.messages(16)] == [buff_id]
        buff = buffs[buff_id]
        matching_effects = [
            effect
            for effect in buff.messages(6)
            if effect.varint(3) == 25
        ]
        assert [effect.varint(4) for effect in matching_effects] == [factor]


def _misc_opr_payload(
    *,
    version: int,
    opr_type: int,
    param: int | None = None,
    chapter_id: int | None = None,
) -> bytes:
    """Encode CS_RogueLikeMiscOpr exactly as the client does.

    Field numbers come from the generated encoder in the decrypted bundle:
    CS_RogueLikeMiscOpr{1 RogueLikeVersion, 2 MiscOpr, 3 chapterId} and
    RogueLikeMiscOpr{1 OprType, 2 param}. RogueLike_BattleOverSelect leaves
    chapterId unset.
    """
    inner = field_varint(1, opr_type)
    if param is not None:
        inner += field_varint(2, param)
    payload = field_varint(1, version) + field_bytes(2, inner)
    if chapter_id is not None:
        payload += field_varint(3, chapter_id)
    return payload


@pytest.mark.parametrize(
    ("selected_export", "expected_buff"), POSTBATTLE_CASES
)
def test_battle_over_select_claims_the_chip(
    monkeypatch,
    tmp_path: Path,
    selected_export: int,
    expected_buff: int,
):
    """The live client claims the chip with net 183, not the net 184 trigger.

    RogueLike_BattleOverSelect sends CS_RogueLikeMiscOpr with
    RL_MiscOpr_BattleOverSelect (3) and the chosen export in param, and waits
    for SC_RogueLikeRet code 61 (BattleOverSelectSuccess).
    """
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = _battle_profile(
        status=2, pending_reward=True, hp=(900, 800, 700)
    )
    store.save(profile)
    expected_hp = tuple(
        _expected_claim_hp(selected_export, value)
        for value in (900, 800, 700)
    )

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                183,
                _misc_opr_payload(
                    version=7, opr_type=3, param=selected_export
                ),
            )
        )
        frames = [_receive_frame(websocket) for _ in range(2)]

    assert [net_id for net_id, _ in frames] == [5, 180]
    response = decode_fields(frames[1][1])
    assert response.varint(1) == 61
    assert response.varint(4) == 20002

    restored = store.load("local")
    run = restored.roguelike_run
    assert run is not None
    assert run.nodes[20002].status == 3
    assert run.pending_battle_reward is False
    assert run.event_buffs[expected_buff] == 1
    assert tuple(
        run.toy_tops[index].hp for index in (1, 2, 3)
    ) == expected_hp


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(
            _misc_opr_payload(version=7, opr_type=3, param=999999),
            id="export-outside-pool",
        ),
        pytest.param(
            _misc_opr_payload(version=6, opr_type=3, param=100066),
            id="stale-version",
        ),
        pytest.param(
            _misc_opr_payload(version=7, opr_type=3),
            id="missing-param",
        ),
        pytest.param(
            _misc_opr_payload(version=7, opr_type=2, param=0),
            id="unmodelled-giveup",
        ),
        pytest.param(
            _misc_opr_payload(version=7, opr_type=14, param=0),
            id="unmodelled-battle-failed",
        ),
    ],
)
def test_rejected_misc_opr_closes_without_save(
    monkeypatch, tmp_path: Path, payload: bytes
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = _battle_profile(
        status=2, pending_reward=True, hp=(900, 800, 700)
    )
    store.save(profile)
    before = store.load("local").roguelike_run
    assert before is not None
    buffs_before = dict(before.event_buffs)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(pack_frame(183, payload))
        message = _receive_message(websocket)

    assert message["type"] == "websocket.close"
    assert message["code"] == 1008
    run = store.load("local").roguelike_run
    assert run is not None
    assert run.nodes[20002].status == 2
    assert run.pending_battle_reward is True
    assert run.event_buffs == buffs_before
    assert tuple(
        run.toy_tops[index].hp for index in (1, 2, 3)
    ) == (900, 800, 700)


def test_battle_over_select_without_pending_reward_closes(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = _battle_profile(
        status=1, pending_reward=False, hp=(900, 800, 700)
    )
    store.save(profile)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                183,
                _misc_opr_payload(version=7, opr_type=3, param=100066),
            )
        )
        message = _receive_message(websocket)

    assert message["type"] == "websocket.close"
    assert message["code"] == 1008
    run = store.load("local").roguelike_run
    assert run is not None
    assert run.nodes[20002].status == 1


def test_give_up_map_ends_the_run(monkeypatch, tmp_path: Path):
    """RL_MiscOpr_GiveUpMap abandons the run and answers code 60.

    The client sends this whenever it cannot resume a map, including a run
    whose postbattle reward was never claimed. Refusing it leaves the player
    permanently stuck on the map screen.
    """
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = _battle_profile(
        status=2, pending_reward=True, hp=(900, 800, 700)
    )
    store.save(profile)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                183,
                _misc_opr_payload(
                    version=7, opr_type=2, chapter_id=-1
                ),
            )
        )
        frames = [_receive_frame(websocket) for _ in range(2)]

    assert [net_id for net_id, _ in frames] == [5, 180]
    assert decode_fields(frames[1][1]).varint(1) == 60

    restored = store.load("local")
    assert restored.roguelike_run is None
    # Abandoning does not refund the key that opened the map.
    assert restored.roguelike_keys == profile.roguelike_keys


def test_give_up_map_without_a_run_closes(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")
    assert profile.roguelike_run is None

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                183,
                _misc_opr_payload(version=0, opr_type=2, chapter_id=-1),
            )
        )
        message = _receive_message(websocket)

    assert message["type"] == "websocket.close"
    assert message["code"] == 1008


def test_exchange_key_grants_a_run_key(monkeypatch, tmp_path: Path):
    """RL_MiscOpr_ExchangeKey refills an adventure key and answers code 50.

    The retired service charged for this from a live price table. Offline the
    lab grants the key outright: the currency it would have cost is already
    local-only, and the protocol contract (OprType 1, ExchangeKeySuccess) is
    what the client actually checks.
    """
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")
    profile.roguelike_keys = 0
    store.save(profile)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(183, _misc_opr_payload(version=0, opr_type=1))
        )
        frames = [_receive_frame(websocket) for _ in range(2)]

    assert [net_id for net_id, _ in frames] == [5, 180]
    assert decode_fields(frames[1][1]).varint(1) == 50
    assert store.load("local").roguelike_keys == 1


def test_exchange_key_stops_at_the_daily_cap(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")
    profile.roguelike_keys = 8
    store.save(profile)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(183, _misc_opr_payload(version=0, opr_type=1))
        )
        message = _receive_message(websocket)

    assert message["type"] == "websocket.close"
    assert message["code"] == 1008
    assert store.load("local").roguelike_keys == 8


def _utc_today() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def test_enter_map_refills_keys_once_a_day_when_empty(
    monkeypatch, tmp_path: Path
):
    """An empty key count refills once per day, as the client advertises.

    The Adventure screen shows a refresh countdown, but the local service
    never granted keys, so the count could only fall and the mode became
    permanently unplayable after the starting key was spent.
    """
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")
    profile.roguelike_keys = 0
    store.save(profile)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(pack_frame(181, _enter_map_payload()))
        frames = [_receive_frame(websocket) for _ in range(3)]

    assert [net_id for net_id, _ in frames] == [5, 1, 180]
    restored = store.load("local")
    assert restored.roguelike_run is not None
    # Refilled to the cap, then charged for this run.
    assert restored.roguelike_keys == logic.ROGUELIKE_KEY_CAP - 1
    assert restored.roguelike_keys_refreshed_on == _utc_today()


def test_enter_map_refills_only_once_per_day(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")
    profile.roguelike_keys = 0
    profile.roguelike_keys_refreshed_on = _utc_today()
    store.save(profile)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(pack_frame(181, _enter_map_payload()))
        message = _receive_message(websocket)

    assert message["type"] == "websocket.close"
    assert message["code"] == 1008
    restored = store.load("local")
    assert restored.roguelike_run is None
    assert restored.roguelike_keys == 0


# RogueLikeMap.Version is seconds since 2018-01-01T00:00:00+08:00, the client's
# getDateTime2018 base. loadLocalStorage() rejects anything older than
# minMapVersion (1594872e6 ms = 2020-07-16).
MAP_EPOCH_MS = 1_514_736_000_000
MIN_MAP_VERSION_MS = 1_594_872_000_000
MIN_MAP_VERSION = (MIN_MAP_VERSION_MS - MAP_EPOCH_MS) // 1000


def test_enter_map_version_is_a_timestamp_the_client_accepts(
    monkeypatch, tmp_path: Path
):
    """RogueLikeMap.Version is a map timestamp, not a counter.

    The client runs getRealTime(Version) and abandons the run when the result
    predates minMapVersion, so a constant 1 renders as 2018 and it gives up
    the moment the map screen loads.
    """
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(pack_frame(181, _enter_map_payload()))
        [_receive_frame(websocket) for _ in range(3)]

    run = store.load("local").roguelike_run
    assert run is not None
    assert run.version > MIN_MAP_VERSION
    # And it is a real "seconds since 2018" clock, not an arbitrary big number.
    from datetime import datetime, timezone

    expected = int(
        (
            datetime.now(timezone.utc)
            - datetime.fromtimestamp(MAP_EPOCH_MS / 1000, timezone.utc)
        ).total_seconds()
    )
    assert abs(run.version - expected) < 300


def test_second_battle_node_is_accepted_by_event_type(
    monkeypatch, tmp_path: Path
):
    """A run must not strand after the first battle.

    The prologue has two Lv1BattleEvent nodes under different ids, 110001 and
    110017. Keying the battle branch on the id and on locations 20002/20004
    refused the second one, so the client could never reach the boss. The live
    client sends location 30004 with event 110017.
    """
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = _battle_profile(status=3, pending_reward=False)
    store.save(profile)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                182,
                _enter_node_payload(
                    version=7,
                    location=30004,
                    event_id=110017,
                    exports=(100001, 100002, 100003),
                ),
            )
        )
        frames = [_receive_frame(websocket) for _ in range(2)]

    assert [net_id for net_id, _ in frames] == [5, 180]
    assert decode_fields(frames[1][1]).varint(1) == 20

    run = store.load("local").roguelike_run
    assert run is not None
    assert run.location == 30004
    assert run.nodes[30004].status == 1
    assert run.nodes[30004].event_id == 110017
    assert run.nodes[30004].location_exports == [100001, 100002, 100003]


def test_battle_node_from_an_incomplete_current_node_is_refused(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    # Standing on a battle node that is still pending its reward.
    profile = _battle_profile(status=2, pending_reward=True)
    store.save(profile)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                182,
                _enter_node_payload(
                    version=7,
                    location=30004,
                    event_id=110017,
                    exports=(100001, 100002, 100003),
                ),
            )
        )
        message = _receive_message(websocket)

    assert message["type"] == "websocket.close"
    assert message["code"] == 1008
    run = store.load("local").roguelike_run
    assert run is not None
    assert 30004 not in run.nodes


def test_non_battle_event_at_a_new_location_is_still_refused(
    monkeypatch, tmp_path: Path
):
    """The boss and shop nodes stay unmodelled until their contracts are known."""
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = _battle_profile(status=3, pending_reward=False)
    store.save(profile)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                182,
                _enter_node_payload(
                    version=7, location=40003, event_id=110018
                ),
            )
        )
        message = _receive_message(websocket)

    assert message["type"] == "websocket.close"
    assert message["code"] == 1008
    run = store.load("local").roguelike_run
    assert run is not None
    assert 40003 not in run.nodes


def test_second_battle_can_be_won_and_claimed(monkeypatch, tmp_path: Path):
    """The win and claim must work for any battle node, not just the first."""
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = _battle_profile(status=3, pending_reward=False)
    run = profile.roguelike_run
    assert run is not None
    run.location = 30004
    run.nodes[30004] = RogueLikeNodeState(
        status=1,
        event_id=110017,
        location_exports=[100001, 100002, 100003],
    )
    for index, value in enumerate((900, 800, 700), start=1):
        run.toy_tops[index].hp = value
    store.save(profile)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                184,
                _trigger_payload(
                    version=7,
                    location=30004,
                    event_id=110017,
                    exports=(100001, 100002, 100003),
                    path=(110017,),
                    hp=(450, 400, 350),
                    energy_type=0,
                    clear=1,
                ),
            )
        )
        win = [_receive_frame(websocket) for _ in range(3)]

        assert [net_id for net_id, _ in win] == [5, 1, 180]
        websocket.send_bytes(
            pack_frame(
                184,
                _trigger_payload(
                    version=7,
                    location=30004,
                    event_id=110017,
                    exports=(100083,),
                    path=(),
                    hp=(450, 400, 350),
                    energy_type=-1,
                    clear=0,
                ),
            )
        )
        claim = [_receive_frame(websocket) for _ in range(2)]

    assert [net_id for net_id, _ in claim] == [5, 180]

    restored = store.load("local").roguelike_run
    assert restored is not None
    assert restored.battle_wins == 1
    assert restored.pending_battle_reward is False
    assert restored.nodes[30004].status == 3
    assert restored.event_buffs[4226] == 1


def _boss_ready_profile() -> LocalProfile:
    """A run standing on a completed battle node, boss reachable."""
    profile = _battle_profile(status=3, pending_reward=False)
    run = profile.roguelike_run
    assert run is not None
    for index, value in enumerate((900, 800, 700), start=1):
        run.toy_tops[index].hp = value
    return profile


def test_boss_node_is_entered_like_a_battle(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = _boss_ready_profile()
    store.save(profile)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                182,
                _enter_node_payload(
                    version=7,
                    location=50003,
                    event_id=110018,
                    exports=(100015, 100016, 100017, 100102),
                ),
            )
        )
        frames = [_receive_frame(websocket) for _ in range(2)]

    assert [net_id for net_id, _ in frames] == [5, 180]
    run = store.load("local").roguelike_run
    assert run is not None
    assert run.location == 50003
    assert run.nodes[50003].status == 1
    assert run.nodes[50003].event_id == 110018


def test_boss_win_completes_the_node_without_a_chip_claim(
    monkeypatch, tmp_path: Path
):
    """The client never offers a chip after the boss.

    doTrigger routes FinalBossEvent through the battle branch but guards the
    postbattle chooser with `eventType !== FinalBossEvent`, so leaving the
    node pending a claim would strand the run exactly as an unclaimed reward
    did before.
    """
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = _boss_ready_profile()
    run = profile.roguelike_run
    assert run is not None
    run.location = 50003
    run.nodes[50003] = RogueLikeNodeState(
        status=1,
        event_id=110018,
        location_exports=[100015, 100016, 100017, 100102],
    )
    store.save(profile)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                184,
                _trigger_payload(
                    version=7,
                    location=50003,
                    event_id=110018,
                    exports=(100015, 100016, 100017, 100102),
                    path=(110018,),
                    hp=(450, 400, 350),
                    energy_type=0,
                    clear=1,
                ),
            )
        )
        frames = [_receive_frame(websocket) for _ in range(3)]

    assert [net_id for net_id, _ in frames] == [5, 1, 180]

    restored = store.load("local").roguelike_run
    assert restored is not None
    assert restored.nodes[50003].status == 3
    assert restored.pending_battle_reward is False
    assert restored.battle_wins == 1
    assert tuple(
        restored.toy_tops[index].hp for index in (1, 2, 3)
    ) == (450, 400, 350)


@pytest.mark.parametrize(
    ("location", "event_id", "kind"),
    [
        pytest.param(40002, 110003, "reward", id="reward-chest"),
        pytest.param(40003, 110002, "select", id="select"),
        pytest.param(40004, 110012, "talk", id="talk"),
    ],
)
def test_known_node_kinds_can_be_entered(
    monkeypatch, tmp_path: Path, location: int, event_id: int, kind: str
):
    """Entering is uniform across node kinds; only resolving differs.

    Refusing entry is what strands a run, so every event id declared for the
    chapter is enterable even where its trigger is not modelled yet.
    """
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = _battle_profile(status=3, pending_reward=False)
    store.save(profile)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                182,
                _enter_node_payload(
                    version=7, location=location, event_id=event_id
                ),
            )
        )
        frames = [_receive_frame(websocket) for _ in range(2)]

    assert [net_id for net_id, _ in frames] == [5, 180]
    run = store.load("local").roguelike_run
    assert run is not None
    assert run.location == location
    assert run.nodes[location].status == 1
    assert run.nodes[location].event_id == event_id


def test_undeclared_event_id_cannot_be_entered(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = _battle_profile(status=3, pending_reward=False)
    store.save(profile)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                182,
                _enter_node_payload(
                    version=7, location=40005, event_id=999999
                ),
            )
        )
        message = _receive_message(websocket)

    assert message["type"] == "websocket.close"
    assert message["code"] == 1008
    run = store.load("local").roguelike_run
    assert run is not None
    assert 40005 not in run.nodes


def test_battle_failed_ends_the_run(monkeypatch, tmp_path: Path):
    """A lost battle ends the run through its own operation.

    RogueLike_BattleFailEx sends RL_MiscOpr_BattleFailed (14). It is a
    run-ending operation exactly like GiveUpMap - both emit MapClose client
    side - and ERogueLikeCode has no failure-specific result, so the run ends
    and the client is answered with GiveUpMapSuccess. Refusing it strands the
    player on the map with no way out after a defeat.
    """
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = _battle_profile(status=1, pending_reward=False)
    store.save(profile)
    keys_before = store.load("local").roguelike_keys

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                183,
                _misc_opr_payload(
                    version=7, opr_type=14, chapter_id=-1
                ),
            )
        )
        frames = [_receive_frame(websocket) for _ in range(2)]

    assert [net_id for net_id, _ in frames] == [5, 180]
    assert decode_fields(frames[1][1]).varint(1) == 60

    restored = store.load("local")
    assert restored.roguelike_run is None
    assert restored.roguelike_keys == keys_before


def test_battle_failed_without_a_run_closes(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")
    assert profile.roguelike_run is None

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                183,
                _misc_opr_payload(version=0, opr_type=14, chapter_id=-1),
            )
        )
        message = _receive_message(websocket)

    assert message["type"] == "websocket.close"
    assert message["code"] == 1008

def _select_profile(
    *,
    hp: tuple[int, int, int] = (1000, 900, 800),
    max_hp: tuple[int, int, int] = (1000, 900, 800),
) -> LocalProfile:
    """A run standing on an entered, unresolved repair station."""
    profile = _battle_profile(status=3, pending_reward=False)
    run = profile.roguelike_run
    assert run is not None
    run.location = 10004
    run.nodes[10004] = RogueLikeNodeState(status=1, event_id=110002)
    for index, (value, ceiling) in enumerate(zip(hp, max_hp), start=1):
        run.toy_tops[index].hp = value
        run.toy_tops[index].max_hp = ceiling
    return profile


def _select_payload(
    *,
    item_id: int,
    top_index: int,
    hp: tuple[int, int, int],
    version: int = 7,
    location: int = 10004,
    event_id: int = 110002,
    path: tuple[int, ...] = (110002,),
) -> bytes:
    """What RogueLike_Trigger_Export_Select puts on the wire.

    It clears Event.LocationExports and names the pick only by marking the
    chosen top with the export's item id.
    """
    buffs: list[tuple[int, ...]] = [(), (), ()]
    buffs[top_index] = (item_id,)
    return _trigger_payload(
        version=version,
        location=location,
        event_id=event_id,
        exports=(),
        path=path,
        hp=hp,
        energy_type=-1,
        clear=0,
        top_buffs=tuple(buffs),
    )


def test_enter_map_records_each_top_max_hp(monkeypatch, tmp_path: Path):
    """A run starts at full health, so the initial hp is the ceiling.

    Nothing else on the wire carries it, and without it a repair node cannot
    be sized: its reward is a percentage of maximum health.
    """
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(181, _enter_map_payload(hp=(3095, 4071, 4560)))
        )
        assert [_receive_frame(websocket)[0] for _ in range(3)] == [5, 1, 180]

    run = store.load("local").roguelike_run
    assert run is not None
    assert tuple(
        run.toy_tops[index].max_hp for index in (1, 2, 3)
    ) == (3095, 4071, 4560)


def test_repair_station_restores_the_shipped_percentage(
    monkeypatch, tmp_path: Path
):
    """The heal is the export row's ExportNum, not a number we chose.

    `setChijiItem` calls `dealHp(ExportNum / 100, index, true)` before
    sending, so the confirm carries the healed value and the gateway checks
    it rather than applying its own.
    """
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = _select_profile(hp=(1000, 400, 800), max_hp=(1000, 4071, 800))
    store.save(profile)
    repaired = 400 + -(-4071 * 40 // 100)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                184,
                _select_payload(
                    item_id=1, top_index=1, hp=(1000, repaired, 800)
                ),
            )
        )
        frames = [_receive_frame(websocket) for _ in range(2)]

    assert [net_id for net_id, _ in frames] == [5, 180]
    assert decode_fields(frames[1][1]).varint(1) == 31

    run = store.load("local").roguelike_run
    assert run is not None
    assert run.nodes[10004].status == 3
    assert run.toy_tops[2].hp == repaired
    assert run.toy_tops[2].buffs == {}
    assert run.toy_tops[1].hp == 1000
    assert run.toy_tops[3].hp == 800


def test_repair_station_never_exceeds_the_ceiling(monkeypatch, tmp_path: Path):
    """dealHp does not clamp, but the stored value does.

    getToyTopMaxHp clamps the client's own array on its next recompute, so
    accepting the overshoot and storing the ceiling keeps both sides equal.
    """
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = _select_profile(hp=(1000, 900, 800), max_hp=(1000, 900, 800))
    store.save(profile)
    overshoot = 1000 + -(-1000 * 40 // 100)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                184,
                _select_payload(
                    item_id=1, top_index=0, hp=(overshoot, 900, 800)
                ),
            )
        )
        assert [_receive_frame(websocket)[0] for _ in range(2)] == [5, 180]

    run = store.load("local").roguelike_run
    assert run is not None
    assert run.toy_tops[1].hp == 1000


def test_repair_station_revives_a_defeated_top_at_half(
    monkeypatch, tmp_path: Path
):
    """onBtnConfirm warns that reviving restores half the row's percentage."""
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = _select_profile(hp=(1000, 0, 800), max_hp=(1000, 4071, 800))
    store.save(profile)
    # Live capture: the confirm for a defeated 4071 hp top carried 815.
    revived = -(-4071 * 40 // 200)
    assert revived == 815

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                184,
                _select_payload(
                    item_id=1, top_index=1, hp=(1000, revived, 800)
                ),
            )
        )
        assert [_receive_frame(websocket)[0] for _ in range(2)] == [5, 180]

    run = store.load("local").roguelike_run
    assert run is not None
    assert run.toy_tops[2].hp == revived


def test_repair_station_chip_choice_attaches_to_the_chosen_top(
    monkeypatch, tmp_path: Path
):
    """The other two Select rows grant a chip instead of health."""
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = _select_profile()
    store.save(profile)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                184,
                _select_payload(
                    item_id=4301, top_index=2, hp=(1000, 900, 800)
                ),
            )
        )
        assert [_receive_frame(websocket)[0] for _ in range(2)] == [5, 180]

    run = store.load("local").roguelike_run
    assert run is not None
    assert run.nodes[10004].status == 3
    assert run.toy_tops[3].buffs == {4301: 1}
    assert tuple(
        run.toy_tops[index].hp for index in (1, 2, 3)
    ) == (1000, 900, 800)


def test_chip_choice_does_not_need_a_recorded_ceiling(
    monkeypatch, tmp_path: Path
):
    """Only a repair is a percentage of maximum health.

    A run started before the ceiling was recorded can still take the chip;
    gating the whole node on it strands that run at the repair station.
    """
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = _select_profile(hp=(0, 0, 2144), max_hp=(0, 0, 0))
    store.save(profile)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                184,
                _select_payload(
                    item_id=4301, top_index=2, hp=(0, 0, 2144)
                ),
            )
        )
        assert [_receive_frame(websocket)[0] for _ in range(2)] == [5, 180]

    run = store.load("local").roguelike_run
    assert run is not None
    assert run.nodes[10004].status == 3
    assert run.toy_tops[3].buffs == {4301: 1}


def test_repair_without_a_recorded_ceiling_closes_without_save(
    monkeypatch, tmp_path: Path
):
    """The heal cannot be sized, so it is refused rather than guessed."""
    _assert_rejected_without_save(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        profile=_select_profile(hp=(0, 0, 2144), max_hp=(0, 0, 0)),
        net_id=184,
        payload=_select_payload(item_id=1, top_index=2, hp=(0, 0, 2144)),
    )


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        pytest.param(
            _select_payload(
                item_id=4231, top_index=0, hp=(1000, 900, 800)
            ),
            "a postbattle chip is not a Select export",
            id="undeclared-item",
        ),
        pytest.param(
            _select_payload(
                item_id=1, top_index=0, hp=(1000, 900, 800), path=()
            ),
            "the confirm always carries the node's own event",
            id="empty-trigger-path",
        ),
        pytest.param(
            _select_payload(
                item_id=1, top_index=0, hp=(999, 900, 800)
            ),
            "the repaired value has to match the client's own dealHp",
            id="wrong-repaired-hp",
        ),
        pytest.param(
            _trigger_payload(
                version=7,
                location=10004,
                event_id=110002,
                exports=(),
                path=(110002,),
                hp=(1000, 900, 800),
                energy_type=-1,
                clear=0,
                top_buffs=((1,), (4301,), ()),
            ),
            "exactly one top is chosen; two marks would be two rewards",
            id="two-marked-tops",
        ),
        pytest.param(
            _trigger_payload(
                version=7,
                location=10004,
                event_id=110002,
                exports=(),
                path=(110002,),
                hp=(1000, 900, 800),
                energy_type=-1,
                clear=0,
            ),
            "an unmarked confirm names no choice at all",
            id="no-marked-top",
        ),
        pytest.param(
            _trigger_payload(
                version=7,
                location=10004,
                event_id=110002,
                exports=(),
                path=(110002,),
                hp=(1000, 900, 800),
                energy_type=-1,
                clear=0,
                top_buffs=((1, 4301), (), ()),
            ),
            "one confirm resolves one export",
            id="two-marks-on-one-top",
        ),
    ],
)
def test_invalid_select_confirm_closes_without_save(
    monkeypatch, tmp_path: Path, payload: bytes, reason: str
):
    _assert_rejected_without_save(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        profile=_select_profile(),
        net_id=184,
        payload=payload,
    )


def test_marked_tops_are_still_refused_outside_a_select_node(
    monkeypatch, tmp_path: Path
):
    """Only a Select confirm may mark a top; a battle win may not."""
    _assert_rejected_without_save(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        profile=_battle_profile(status=1, pending_reward=False),
        net_id=184,
        payload=_trigger_payload(
            version=7,
            location=20002,
            event_id=110001,
            exports=(100001, 100002, 100003),
            path=(110001,),
            hp=(450, 400, 350),
            energy_type=0,
            clear=1,
            top_buffs=((4301,), (), ()),
        ),
    )


@pytest.mark.parametrize(
    ("event_id", "exports", "reason"),
    [
        pytest.param(
            110018,
            (100015, 100016, 100017),
            "the boss rolls four exports, not a battle's three",
            id="boss-with-three-exports",
        ),
        pytest.param(
            110017,
            (100001, 100002, 100003, 100004),
            "a battle rolls three, not the boss's four",
            id="battle-with-four-exports",
        ),
    ],
)
def test_export_count_is_taken_from_the_event_not_the_kind(
    monkeypatch,
    tmp_path: Path,
    event_id: int,
    exports: tuple[int, ...],
    reason: str,
):
    """RandomTime is per event; one hardcoded count refuses the other kind.

    Demanding three exports of every fightable node is what refused the
    chapter boss outright, so the count comes from the shipped table.
    """
    _assert_rejected_without_save(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        profile=_boss_ready_profile(),
        net_id=182,
        payload=_enter_node_payload(
            version=7,
            location=50003 if event_id == 110018 else 30003,
            event_id=event_id,
            exports=exports,
        ),
    )


def test_journal_records_the_exports_a_node_request_carried(
    monkeypatch, tmp_path: Path
):
    """A refused node request has to be diagnosable from the trace.

    The gateway answers an unacceptable request by closing, so the exports
    the client offered are the only way to tell a permutation from a wrong
    count - or, as with the starter-chip branch, from none at all.
    """
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    profile = ProfileStore(tmp_path).load("local")
    rolled = (100003, 100001, 100002)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        _reach_talk_branch(websocket)
        websocket.send_bytes(
            pack_frame(
                184,
                _trigger_payload(
                    version=_run_version(),
                    location=10003,
                    event_id=110005,
                    exports=(),
                    path=(110000, 110005),
                    hp=(1000, 900, 800),
                    energy_type=-1,
                    clear=0,
                ),
            )
        )
        assert [_receive_frame(websocket)[0] for _ in range(2)] == [5, 180]
        websocket.send_bytes(
            pack_frame(
                182,
                _enter_node_payload(
                    version=_run_version(),
                    location=20002,
                    event_id=110001,
                    exports=rolled,
                ),
            )
        )
        assert [_receive_frame(websocket)[0] for _ in range(2)] == [5, 180]

    journal = [
        json.loads(line)
        for line in (tmp_path / "logic-frames.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    battle_enter = [
        entry
        for entry in journal
        if entry["direction"] == "recv" and entry.get("event_id") == 110001
    ]
    assert len(battle_enter) == 1
    assert battle_enter[0]["location_exports"] == list(rolled)

    # A branch whose list is declared sends none, and the trace says so.
    talk_frames = [
        entry
        for entry in journal
        if entry["direction"] == "recv" and entry.get("event_id") == 110005
    ]
    assert len(talk_frames) == 2
    assert all(
        "location_exports" not in entry for entry in talk_frames
    )


def test_journal_records_a_trigger_path_and_marked_top(
    monkeypatch, tmp_path: Path
):
    """A refused trigger has to be diagnosable from the trace too.

    Which top a Select confirm marked, and with what, is the whole content
    of the request; without it a refusal is indistinguishable from silence.
    """
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = _select_profile(hp=(0, 900, 800), max_hp=(3095, 4071, 4560))
    store.save(profile)
    revived = -(-3095 * 40 // 200)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                184,
                _select_payload(
                    item_id=1, top_index=0, hp=(revived, 900, 800)
                ),
            )
        )
        assert [_receive_frame(websocket)[0] for _ in range(2)] == [5, 180]

    journal = [
        json.loads(line)
        for line in (tmp_path / "logic-frames.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    confirm = [
        entry
        for entry in journal
        if entry["direction"] == "recv" and entry["net_id"] == 184
    ]
    assert len(confirm) == 1
    assert confirm[0]["trigger_path"] == [110002]
    assert confirm[0]["toy_tops"] == [
        {"hp": revived, "buffs": [1]},
        {"hp": 900},
        {"hp": 800},
    ]


def _reward_profile() -> LocalProfile:
    """A run standing on an entered, unclaimed reward chest."""
    profile = _battle_profile(status=3, pending_reward=False)
    run = profile.roguelike_run
    assert run is not None
    run.location = 40005
    run.nodes[40005] = RogueLikeNodeState(
        status=1,
        event_id=110003,
        location_exports=[100023, 100022, 100021],
    )
    profile.default_items = {}
    return profile


def test_reward_chest_grants_every_declared_item(monkeypatch, tmp_path: Path):
    """A reward node has no choice: doTrigger sends all of its exports.

    Refusing the confirm left the chest sitting open on a cleared map with
    the socket closing on every tap.
    """
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = _reward_profile()
    store.save(profile)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                184,
                _trigger_payload(
                    version=7,
                    location=40005,
                    event_id=110003,
                    exports=(100023, 100022, 100021),
                    path=(110003,),
                    hp=(1000, 900, 800),
                    energy_type=-1,
                    clear=0,
                ),
            )
        )
        frames = [_receive_frame(websocket) for _ in range(3)]

    assert [net_id for net_id, _ in frames] == [5, 1, 180]
    response = decode_fields(frames[2][1])
    assert (response.varint(1), response.varint(4)) == (31, 40005)
    get_items = response.message(3)
    assert get_items.varint(1) == 16
    assert sorted(
        (_signed32(reward.varint(1)), reward.varint(2))
        for reward in get_items.message(2).messages(1)
    ) == sorted(((2028, 2), (2004, 2), (1227894833, 500)))

    restored = store.load("local")
    run = restored.roguelike_run
    assert run is not None
    assert run.nodes[40005].status == 3
    assert restored.default_items == {
        2028: 2,
        2004: 2,
        1227894833: 500,
    }
    assert tuple(
        run.toy_tops[index].hp for index in (1, 2, 3)
    ) == (1000, 900, 800)


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        pytest.param(
            _trigger_payload(
                version=7,
                location=40005,
                event_id=110003,
                exports=(100023, 100022),
                path=(110003,),
                hp=(1000, 900, 800),
                energy_type=-1,
                clear=0,
            ),
            "a reward node confirms with every export it was entered with",
            id="partial-exports",
        ),
        pytest.param(
            _trigger_payload(
                version=7,
                location=40005,
                event_id=110003,
                exports=(100023, 100022, 100018),
                path=(110003,),
                hp=(1000, 900, 800),
                energy_type=-1,
                clear=0,
            ),
            "a Select row is not a reward row",
            id="foreign-export",
        ),
        pytest.param(
            _trigger_payload(
                version=7,
                location=40005,
                event_id=110003,
                exports=(100023, 100022, 100021),
                path=(110003,),
                hp=(1000, 900, 700),
                energy_type=-1,
                clear=0,
            ),
            "a chest does not change anyone's health",
            id="altered-hp",
        ),
    ],
)
def test_invalid_reward_confirm_closes_without_save(
    monkeypatch, tmp_path: Path, payload: bytes, reason: str
):
    _assert_rejected_without_save(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        profile=_reward_profile(),
        net_id=184,
        payload=payload,
    )


def test_cleared_chapter_survives_the_run_it_was_cleared_in():
    """A clear has to outlive the run, and the snapshot is the only carrier.

    `checkIsUnlock` reads `RogueLikeRecord.LevelProcess[<difficulty>]` and
    compares it to a chapter id, so that map is the whole record of what has
    been beaten. The builder returned an empty message whenever no run was
    active, which threw the record away the moment a run ended.
    """
    profile = LocalProfile.model_validate(
        {
            "roguelike_cleared_chapters": {"1": -1},
            "roguelike_enter_map_num": 3,
        }
    )
    assert profile.roguelike_run is None

    record = decode_fields(build_roguelike_info(profile)).message(2)

    assert [
        (entry.varint(1), _signed32(entry.varint(2)))
        for entry in record.messages(4)
    ] == [(1, -1)]
    assert record.varint(5) == 3


def test_active_run_carries_both_the_map_and_the_record():
    profile = _battle_profile(status=3, pending_reward=False)
    profile.roguelike_cleared_chapters = {1: -1}
    profile.roguelike_enter_map_num = 2

    info = decode_fields(build_roguelike_info(profile))

    assert info.message(1).varint(1) == 7  # the map is still field 1
    assert info.message(2).varint(5) == 2


def test_beating_the_boss_records_the_chapter_as_cleared(
    monkeypatch, tmp_path: Path
):
    """The boss win is the clear; no separate frame reports it.

    The client shows 通关成功 by itself and sends nothing, so the only moment
    the gateway can record the chapter is the trigger that completes the boss.
    """
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = _boss_ready_profile()
    run = profile.roguelike_run
    assert run is not None
    run.location = 50003
    run.nodes[50003] = RogueLikeNodeState(
        status=1,
        event_id=110018,
        location_exports=[100015, 100016, 100017, 100102],
    )
    store.save(profile)
    assert store.load("local").roguelike_cleared_chapters == {}

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                184,
                _trigger_payload(
                    version=7,
                    location=50003,
                    event_id=110018,
                    exports=(100015, 100016, 100017, 100102),
                    path=(110018,),
                    hp=(450, 400, 350),
                    energy_type=0,
                    clear=1,
                ),
            )
        )
        assert [_receive_frame(websocket)[0] for _ in range(3)] == [5, 1, 180]

    restored = store.load("local")
    assert restored.roguelike_cleared_chapters == {1: -1}


def test_entering_a_map_counts_toward_the_record(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")
    assert profile.roguelike_enter_map_num == 0

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(pack_frame(181, _enter_map_payload()))
        assert [_receive_frame(websocket)[0] for _ in range(3)] == [5, 1, 180]

    assert store.load("local").roguelike_enter_map_num == 1


def test_a_second_clear_never_lowers_the_record(monkeypatch, tmp_path: Path):
    """LevelProcess holds the furthest chapter, so replaying cannot regress."""
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = _boss_ready_profile()
    profile.roguelike_cleared_chapters = {1: 4}
    run = profile.roguelike_run
    assert run is not None
    run.location = 50003
    run.nodes[50003] = RogueLikeNodeState(
        status=1,
        event_id=110018,
        location_exports=[100015, 100016, 100017, 100102],
    )
    store.save(profile)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                184,
                _trigger_payload(
                    version=7,
                    location=50003,
                    event_id=110018,
                    exports=(100015, 100016, 100017, 100102),
                    path=(110018,),
                    hp=(450, 400, 350),
                    energy_type=0,
                    clear=1,
                ),
            )
        )
        assert [_receive_frame(websocket)[0] for _ in range(3)] == [5, 1, 180]

    assert store.load("local").roguelike_cleared_chapters == {1: 4}


def _boss_trigger(*, all_node: int) -> bytes:
    return _trigger_payload(
        version=7,
        location=50003,
        event_id=110018,
        exports=(100015, 100016, 100017, 100102),
        path=(110018,),
        hp=(450, 400, 350),
        energy_type=0,
        clear=1,
        all_node=all_node,
    )


def _on_the_boss(profile: LocalProfile) -> LocalProfile:
    run = profile.roguelike_run
    assert run is not None
    run.location = 50003
    run.nodes[50003] = RogueLikeNodeState(
        status=1,
        event_id=110018,
        location_exports=[100015, 100016, 100017, 100102],
    )
    return profile


def test_a_fully_explored_map_ends_when_the_boss_dies(
    monkeypatch, tmp_path: Path
):
    """TriggerAllNode is the only report that a run finished the whole map.

    `isCompleteAll` is true only while standing on the boss with every other
    node done, and it rides on the boss trigger. `doEndMap` - the client's own
    GiveUpMap path - runs on a loss only, so nothing else ever closes a won
    run. Refusing the flag left the player on a dead map with every node grey
    and no way back to the chapter list.
    """
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = _on_the_boss(_boss_ready_profile())
    store.save(profile)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(pack_frame(184, _boss_trigger(all_node=1)))
        assert [_receive_frame(websocket)[0] for _ in range(3)] == [5, 1, 180]

    restored = store.load("local")
    assert restored.roguelike_run is None
    # The clear still has to be recorded, and the rewards still granted.
    assert restored.roguelike_cleared_chapters == {1: -1}
    assert restored.default_items[1194340400] == 5


def test_an_unfinished_map_stays_open_after_the_boss(
    monkeypatch, tmp_path: Path
):
    """With optional nodes left the client reports 0, and they stay takeable."""
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = _on_the_boss(_boss_ready_profile())
    store.save(profile)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(pack_frame(184, _boss_trigger(all_node=0)))
        assert [_receive_frame(websocket)[0] for _ in range(3)] == [5, 1, 180]

    restored = store.load("local")
    assert restored.roguelike_run is not None
    assert restored.roguelike_run.nodes[50003].status == 3
    assert restored.roguelike_cleared_chapters == {1: -1}


def test_all_node_is_refused_away_from_the_boss(monkeypatch, tmp_path: Path):
    """isCompleteAll only ever returns 1 on the boss grid."""
    _assert_rejected_without_save(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        profile=_battle_profile(status=1, pending_reward=False),
        net_id=184,
        payload=_trigger_payload(
            version=7,
            location=20002,
            event_id=110001,
            exports=(100001, 100002, 100003),
            path=(110001,),
            hp=(450, 400, 350),
            energy_type=0,
            clear=1,
            all_node=1,
        ),
    )
