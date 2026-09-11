from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import anyio
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.protocol import logic
from app.routes import logic as logic_route
from app.models.save import LocalProfile
from app.protocol.logic import build_player_data, pack_frame, unpack_frame
from app.protocol.protobuf import encode_varint, field_bytes, field_text, field_varint
from app.security.logic_token import issue_logic_token
from app.storage.profile_store import ProfileStore


def _decode_varint(payload: bytes, index: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while index < len(payload):
        byte = payload[index]
        index += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, index
        shift += 7
    raise ValueError("truncated test protobuf varint")


@dataclass
class Fields:
    values: dict[int, list[tuple[int, int | bytes]]]

    def varint(self, number: int) -> int:
        wire_type, value = self.values[number][0]
        assert wire_type == 0
        assert isinstance(value, int)
        return value

    def message(self, number: int) -> "Fields":
        wire_type, value = self.values[number][0]
        assert wire_type == 2
        assert isinstance(value, bytes)
        return decode_fields(value)

    def messages(self, number: int) -> list["Fields"]:
        return [
            decode_fields(value)
            for wire_type, value in self.values[number]
            if wire_type == 2 and isinstance(value, bytes)
        ]


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
            raise AssertionError(f"unsupported test protobuf wire type {wire_type}")
        values.setdefault(number, []).append((wire_type, value))
    return Fields(values)


def test_player_data_is_tutorial_complete_and_contains_main_lineup():
    profile = LocalProfile(stage_results={10002: 3, 10001: 1})

    fields = decode_fields(build_player_data(profile))

    assert fields.varint(9) == 64
    base = fields.message(1)
    assert [entry.varint(1) for entry in base.messages(15)] == [2001, 2004, 2028]
    assert [entry.varint(1) for entry in base.messages(16)] == [2002, 2005, 2029]
    assert [entry.varint(1) for entry in base.messages(17)] == [2003, 2006, 2030]
    assert [entry.message(2).varint(1) for entry in base.messages(15)] == [1, 1, 1]
    assert [entry.message(2).varint(1) for entry in base.messages(16)] == [1, 1, 1]
    assert [entry.message(2).varint(1) for entry in base.messages(17)] == [1, 1, 1]
    lineup = base.messages(23)[0]
    assert lineup.varint(1) == 1
    lineup_value = lineup.message(2)
    assert lineup_value.varint(2) == 1
    assert lineup_value.varint(3) == 1
    assert 4 not in lineup_value.values
    assert lineup_value.varint(5) == 0
    assert [
        (
            entry.message(2).varint(1),
            entry.message(2).varint(2),
            entry.message(2).varint(3),
        )
        for entry in lineup_value.messages(1)
    ] == [(2001, 2002, 2003), (2004, 2005, 2006), (2028, 2029, 2030)]
    assert [
        (entry.varint(1), entry.varint(2)) for entry in fields.messages(6)
    ] == [(10001, 1), (10002, 3)]


def test_first_stage_delta_is_the_recovered_exact_wire_contract():
    chapter_delta = getattr(logic, "build_chapter_result_delta", lambda *_: b"")
    chapter_ack = getattr(logic, "build_chapter_opr_ack", lambda *_: b"")
    race_end = getattr(logic, "build_race_end", lambda: b"")

    assert chapter_delta(10001, 1).hex() == "320508914e1001"
    assert chapter_ack(3) == b"\x08\x03"
    assert race_end() == b"\x08\x0e"


def test_chapter_operation_parser_accepts_packed_use_parts():
    parse = getattr(
        logic,
        "parse_chapter_operation",
        lambda _: SimpleNamespace(use_parts=()),
    )
    payload = b"".join(
        (
            field_varint(1, 1),
            field_varint(2, 10001),
            field_varint(3, 9_223_372_036_854_775_807),
            field_varint(4, 1),
            field_varint(5, 1),
            field_bytes(
                6,
                b"".join(encode_varint(part) for part in (2001, 2002, 2003)),
            ),
        )
    )

    assert parse(payload).use_parts == (2001, 2002, 2003)


def test_chapter_operation_parser_applies_signed_protobuf_integer_widths():
    payload = b"".join(
        (
            field_varint(1, -1),
            field_varint(2, -2_147_483_648),
            field_varint(3, 0xFFFF_FFFF),
            field_varint(4, -2_147_483_647),
            field_varint(5, -1),
        )
    )

    parsed = logic.parse_chapter_operation(payload)

    assert parsed.operation == -1
    assert parsed.chapter_key == -2_147_483_648
    assert parsed.chapter_version == 4_294_967_295
    assert parsed.result == -2_147_483_647
    assert parsed.self_win_num == -1


def test_chapter_operation_parser_rejects_packed_varints_that_cross_the_field_boundary():
    payload = b"".join(
        (
            field_varint(1, 3),
            field_varint(2, 10001),
            field_bytes(6, b"\x80"),
            b"\x00",
        )
    )

    with pytest.raises(ValueError):
        logic.parse_chapter_operation(payload)


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
    websocket.send_bytes(
        pack_frame(1111, field_text(1, issue_logic_token(profile)))
    )
    return [_receive_frame(websocket) for _ in range(4)]


def _chapter_operation(
    operation: int,
    chapter_key: int,
    *,
    chapter_version: int = 9_223_372_036_854_775_807,
    result: int | None = None,
    self_win_num: int | None = None,
    use_parts: tuple[int, ...] = (),
) -> bytes:
    fields = [
        field_varint(1, operation),
        field_varint(2, chapter_key),
        field_varint(3, chapter_version),
    ]
    if result is not None:
        fields.append(field_varint(4, result))
    if self_win_num is not None:
        fields.append(field_varint(5, self_win_num))
    fields.extend(field_varint(6, part) for part in use_parts)
    return b"".join(fields)


def test_first_stage_win_persists_and_reappears_after_reconnect(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    profile = ProfileStore(tmp_path).load("local")

    with TestClient(app).websocket_connect("/ws") as websocket:
        assert [net_id for net_id, _ in _login(websocket, profile)] == [
            1,
            2,
            5,
            129,
        ]
        websocket.send_bytes(pack_frame(163, field_varint(1, 0)))
        websocket.send_bytes(pack_frame(131, b""))
        assert _receive_frame(websocket) == (132, b"")

        websocket.send_bytes(pack_frame(166, bytes.fromhex("080310914e")))
        assert _receive_frame(websocket) == (167, b"\x08\x03")

        websocket.send_bytes(
            pack_frame(
                166,
                _chapter_operation(
                    1,
                    10001,
                    result=1,
                    self_win_num=1,
                    use_parts=(2001, 2002, 2003),
                ),
            )
        )
        assert [_receive_frame(websocket) for _ in range(3)] == [
            (1, bytes.fromhex("320508914e1001")),
            (167, b"\x08\x01"),
            (140, b"\x08\x0e"),
        ]

    restored = ProfileStore(tmp_path).load("local")
    assert restored.stage_results[10001] == 1
    assert 10001 in restored.stages_completed
    assert '"chapter_version": 9223372036854775807' in (
        tmp_path / "logic-frames.jsonl"
    ).read_text(encoding="utf-8")

    with TestClient(app).websocket_connect("/ws") as websocket:
        player_data, _, _, _ = _login(websocket, restored)
    player_fields = decode_fields(player_data[1])
    assert [
        (entry.varint(1), entry.varint(2))
        for entry in player_fields.messages(6)
    ] == [(10001, 1)]


def test_first_stage_query_acknowledges_without_fabricating_chapter_data(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    profile = ProfileStore(tmp_path).load("local")

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(166, field_varint(1, 0) + field_varint(2, 10001))
        )
        assert _receive_frame(websocket) == (167, b"\x08\x00")

    assert ProfileStore(tmp_path).load("local").stage_results == {}


def test_negative_chapter_version_is_preserved_in_the_journal(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    profile = ProfileStore(tmp_path).load("local")

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                166,
                _chapter_operation(0, 10001, chapter_version=-7),
            )
        )
        assert _receive_frame(websocket) == (167, b"\x08\x00")

    journal = [
        json.loads(line)
        for line in (tmp_path / "logic-frames.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    chapter_receives = [
        entry
        for entry in journal
        if entry["direction"] == "recv" and entry["net_id"] == 166
    ]
    assert len(chapter_receives) == 1
    assert chapter_receives[0]["chapter_version"] == -7


def test_negative_self_win_num_closes_without_saving_a_stage_result(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")
    profile.stage_results = {10001: 3}
    profile.stages_completed = [10001]
    store.save(profile)
    save_calls: list[LocalProfile] = []
    original_save = ProfileStore.save

    def recording_save(self, saved_profile: LocalProfile) -> None:
        save_calls.append(saved_profile)
        original_save(self, saved_profile)

    monkeypatch.setattr(ProfileStore, "save", recording_save)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                166,
                _chapter_operation(
                    1,
                    10001,
                    result=1,
                    self_win_num=-1,
                    use_parts=(2001, 2002, 2003),
                ),
            )
        )
        message = _receive_message(websocket)

    assert message["type"] == "websocket.close"
    assert message["code"] == 1008
    assert save_calls == []
    restored = store.load("local")
    assert restored.stage_results == {10001: 3}
    assert restored.stages_completed == [10001]


def test_stage_win_merges_new_stars_with_the_saved_result(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")
    profile.stage_results = {10001: 3}
    profile.stages_completed = [10001]
    store.save(profile)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(
            pack_frame(
                166,
                _chapter_operation(
                    1,
                    10001,
                    result=5,
                    self_win_num=1,
                    use_parts=(2001, 2002, 2003),
                ),
            )
        )
        assert [_receive_frame(websocket) for _ in range(3)] == [
            (1, bytes.fromhex("320508914e1007")),
            (167, b"\x08\x01"),
            (140, b"\x08\x0e"),
        ]

    assert store.load("local").stage_results[10001] == 7


def test_stale_connection_merges_its_result_with_the_latest_saved_stage(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    store = ProfileStore(tmp_path)
    profile = store.load("local")
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as first, client.websocket_connect(
            "/ws"
        ) as second:
            _login(first, profile)
            _login(second, profile)
            first.send_bytes(
                pack_frame(
                    166,
                    _chapter_operation(
                        1, 10001, result=3, self_win_num=1
                    ),
                )
            )
            assert _receive_frame(first) == (
                1,
                bytes.fromhex("320508914e1003"),
            )
            _receive_frame(first)
            _receive_frame(first)

            second.send_bytes(
                pack_frame(
                    166,
                    _chapter_operation(
                        1, 10001, result=5, self_win_num=1
                    ),
                )
            )
            assert _receive_frame(second) == (
                1,
                bytes.fromhex("320508914e1007"),
            )
            _receive_frame(second)
            _receive_frame(second)

    assert store.load("local").stage_results[10001] == 7


def test_id166_and_profile_put_share_one_profile_transaction(
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
    original_parse = logic_route.parse_chapter_operation
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
        if saved_profile.stage_results:
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
                        json={"level": 4, "stages_unlocked": [1, 2]},
                    )
                )
        except BaseException as error:
            put_errors.append(error)

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        monkeypatch.setattr(ProfileStore, "load", pausing_load)
        monkeypatch.setattr(ProfileStore, "save", recording_save)
        monkeypatch.setattr(
            logic_route, "parse_chapter_operation", recording_parse
        )
        put_thread = threading.Thread(target=run_put)
        try:
            put_thread.start()
            assert put_loaded.wait(3)
            websocket.send_bytes(
                pack_frame(
                    166,
                    _chapter_operation(
                        1,
                        10001,
                        result=1,
                        self_win_num=1,
                    ),
                )
            )
            assert logic_parsed.wait(3)
            assert not logic_saved.wait(0.2)
        finally:
            release_put.set()
            put_thread.join(3)

        assert [_receive_frame(websocket)[0] for _ in range(3)] == [
            1,
            167,
            140,
        ]

    assert not put_thread.is_alive()
    assert put_errors == []
    assert len(put_result) == 1
    assert put_result[0].status_code == 200
    restored = store.load("local")
    assert (restored.level, restored.stages_unlocked) == (4, [1, 2])
    assert restored.stage_results == {10001: 1}
    assert restored.stages_completed == [10001]
    assert not (tmp_path / "local.json.tmp").exists()


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(b"\x08", id="truncated-protobuf"),
        pytest.param(_chapter_operation(3, 10002), id="unknown-stage"),
        pytest.param(
            _chapter_operation(3, 10001, use_parts=(2001, 2002, 2003)),
            id="start-with-parts",
        ),
        pytest.param(
            _chapter_operation(1, 10001, result=2, self_win_num=1),
            id="invalid-result-mask",
        ),
    ],
)
def test_invalid_chapter_operations_close_with_policy_violation(
    monkeypatch, tmp_path: Path, payload: bytes
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    profile = ProfileStore(tmp_path).load("local")

    with TestClient(app).websocket_connect("/ws") as websocket:
        _login(websocket, profile)
        websocket.send_bytes(pack_frame(166, payload))
        message = _receive_message(websocket)

    assert message["type"] == "websocket.close"
    assert message["code"] == 1008
