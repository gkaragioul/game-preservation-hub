import base64
import hashlib
import hmac
import json
from pathlib import Path

import anyio
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.protocol.logic import pack_frame, unpack_frame
from app.protocol.protobuf import field_bytes, field_text, field_varint
from app.security.logic_token import issue_logic_token
from app.storage.profile_store import ProfileStore


def _receive_frame(websocket) -> tuple[int, bytes]:
    async def receive_with_timeout():
        with anyio.fail_after(1):
            return await websocket._send_rx.receive()

    try:
        message = websocket.portal.call(receive_with_timeout)
    except TimeoutError:
        pytest.fail("logic socket did not return the required response")
    if isinstance(message, BaseException):
        raise message
    assert message["type"] == "websocket.send"
    payload = message.get("bytes")
    assert isinstance(payload, bytes)
    return unpack_frame(payload)


def _signed_logic_token(claims: object, secret: str) -> str:
    def segment(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

    header = segment(b'{"alg":"HS256","typ":"JWT"}')
    payload = segment(
        json.dumps(claims, separators=(",", ":")).encode("utf-8")
    )
    signature = segment(
        hmac.new(
            secret.encode("utf-8"),
            f"{header}.{payload}".encode("ascii"),
            hashlib.sha256,
        ).digest()
    )
    return f"{header}.{payload}.{signature}"


def test_frame_header_is_big_endian_and_length_includes_header():
    frame = pack_frame(1111, b"\x0a\x01x")
    assert frame.hex() == "0000000904570a0178"
    assert unpack_frame(frame) == (1111, b"\x0a\x01x")


def test_login_sends_player_playerinfo_roguelike_then_success(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    profile = ProfileStore(tmp_path).load("local")
    token = issue_logic_token(profile)
    with TestClient(app).websocket_connect("/ws") as websocket:
        websocket.send_bytes(pack_frame(1111, field_text(1, token)))
        frames = [_receive_frame(websocket) for _ in range(4)]
    assert [net_id for net_id, _ in frames] == [1, 2, 5, 129]
    player_data = frames[0][1]
    assert b"Local Warrior" in player_data
    assert frames[1][1] == b""
    # No run is active, but the RogueLikeRecord still travels: it carries the
    # cleared chapters, which have to outlive the run they were earned in.
    assert frames[2][1] == field_bytes(2, field_varint(5, 0))
    assert frames[3][1].startswith(b"\x08\x81\xc2\xd7\x2f")
    journal = (tmp_path / "logic-frames.jsonl").read_text(encoding="utf-8")
    assert '"direction": "recv", "net_id": 1111' in journal
    assert (
        sum('"direction": "send"' in line for line in journal.splitlines()) == 4
    )


def test_bad_token_closes_with_policy_violation():
    with TestClient(app).websocket_connect("/ws") as websocket:
        websocket.send_bytes(
            pack_frame(1111, field_text(1, "bad.token.value"))
        )
        message = websocket.receive()
    assert message["type"] == "websocket.close"
    assert message["code"] == 1008


def test_valid_token_with_truncated_trailing_key_closes_without_bootstrap(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    profile = ProfileStore(tmp_path).load("local")
    payload = field_text(1, issue_logic_token(profile)) + b"\x80"

    with TestClient(app).websocket_connect("/ws") as websocket:
        websocket.send_bytes(pack_frame(1111, payload))
        message = websocket.receive()

    assert message["type"] == "websocket.close"
    assert message["code"] == 1008
    journal = (tmp_path / "logic-frames.jsonl").read_text(encoding="utf-8")
    assert '"direction": "send"' not in journal


@pytest.mark.parametrize(
    "trailing",
    [
        pytest.param(field_text(1, "duplicate"), id="duplicate-token"),
        pytest.param(field_text(2, "unsupported"), id="unsupported-field"),
        pytest.param(field_varint(1, 0), id="unsupported-wire-type"),
    ],
)
def test_valid_token_with_unsupported_trailing_field_closes_without_bootstrap(
    monkeypatch, tmp_path: Path, trailing: bytes
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    profile = ProfileStore(tmp_path).load("local")
    payload = field_text(1, issue_logic_token(profile)) + trailing

    with TestClient(app).websocket_connect("/ws") as websocket:
        websocket.send_bytes(pack_frame(1111, payload))
        message = websocket.receive()

    assert message["type"] == "websocket.close"
    assert message["code"] == 1008
    journal = (tmp_path / "logic-frames.jsonl").read_text(encoding="utf-8")
    assert '"direction": "send"' not in journal


def test_base_info_carries_the_fields_the_lobby_reads():
    """The lobby HUD reads PlayerLevel/PlayerExp, not Level/Exp.

    ``SyncDataManager.getPlayerLv`` returns ``BaseInfo.PlayerLevel`` (field 70)
    and ``updatePlayerExp`` feeds it to ``levelDataManager.getItem``. Omitting
    it makes the lookup return null and the lobby throws before it renders.
    """
    from app.models.save import LocalProfile
    from app.protocol.logic import build_base_info

    payload = build_base_info(LocalProfile(level=3, experience=42))

    assert field_varint(70, 3) in payload
    assert field_varint(72, 42) in payload
    # The separate legacy counters stay populated too.
    assert field_varint(3, 3) in payload
    assert field_varint(7, 42) in payload


def shipped_login_node(token: str) -> bytes:
    """Encode CS_LoginNode exactly as the shipped client emits it.

    Field numbers and wire types come from the generated encoder in the
    decrypted bundle; the values are the ones captured from a live emulator
    login. ``devImei`` (field 8) is absent because the client omits it.
    """
    return b"".join(
        (
            field_text(1, token),
            field_varint(2, 0),
            field_text(3, "db0c28c28d33c7e0e1e06c824967bc57"),
            field_varint(4, 7),
            field_text(5, "1019"),
            field_text(6, "100441"),
            field_text(7, "100442"),
            field_varint(9, 0),
            field_text(10, "android"),
            field_varint(11, 100000001),
            field_text(12, "daa82f3a-82d00ffd-33a32b3a"),
        )
    )


def test_shipped_login_node_completes_the_bootstrap(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    profile = ProfileStore(tmp_path).load("local")

    with TestClient(app).websocket_connect("/ws") as websocket:
        websocket.send_bytes(
            pack_frame(1111, shipped_login_node(issue_logic_token(profile)))
        )
        frames = [unpack_frame(websocket.receive_bytes()) for _ in range(4)]

    assert [net_id for net_id, _ in frames] == [1, 2, 5, 129]
    assert b"Local Warrior" in frames[0][1]


def test_login_node_rejects_a_declared_field_with_the_wrong_wire_type(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    profile = ProfileStore(tmp_path).load("local")
    # clientType is declared int32; a length-delimited value is malformed.
    payload = field_text(1, issue_logic_token(profile)) + field_text(4, "7")

    with TestClient(app).websocket_connect("/ws") as websocket:
        websocket.send_bytes(pack_frame(1111, payload))
        message = websocket.receive()

    assert message["type"] == "websocket.close"
    assert message["code"] == 1008


def test_login_node_rejects_an_undeclared_field(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SPIRAL_SAVE_DIR", str(tmp_path))
    profile = ProfileStore(tmp_path).load("local")
    payload = field_text(1, issue_logic_token(profile)) + field_text(13, "x")

    with TestClient(app).websocket_connect("/ws") as websocket:
        websocket.send_bytes(pack_frame(1111, payload))
        message = websocket.receive()

    assert message["type"] == "websocket.close"
    assert message["code"] == 1008


def test_malformed_frame_closes_with_policy_violation():
    with TestClient(app).websocket_connect("/ws") as websocket:
        websocket.send_bytes(b"\x00")
        message = websocket.receive()
    assert message["type"] == "websocket.close"
    assert message["code"] == 1008


def test_post_login_client_message_before_authentication_closes_with_policy_violation():
    with TestClient(app).websocket_connect("/ws") as websocket:
        websocket.send_bytes(pack_frame(131, b""))
        message = websocket.receive()
    assert message["type"] == "websocket.close"
    assert message["code"] == 1008


@pytest.mark.parametrize(
    "claims",
    [
        pytest.param({}, id="missing-playerid"),
        pytest.param([], id="non-object"),
    ],
)
def test_structurally_invalid_signed_claims_close_with_policy_violation(
    monkeypatch, claims: object
):
    secret = "structurally-invalid-claims-test"
    monkeypatch.setenv("SPIRAL_TOKEN_SECRET", secret)
    token = _signed_logic_token(claims, secret)
    with TestClient(app).websocket_connect("/ws") as websocket:
        websocket.send_bytes(pack_frame(1111, field_text(1, token)))
        message = websocket.receive()
    assert message["type"] == "websocket.close"
    assert message["code"] == 1008
