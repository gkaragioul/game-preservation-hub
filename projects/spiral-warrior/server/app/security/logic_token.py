import base64
import hashlib
import hmac
import json
import os

from app.models.save import LocalProfile


def _segment(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def _secret() -> bytes:
    return os.environ.get("SPIRAL_TOKEN_SECRET", "spiral-warrior-local-only").encode()


def issue_logic_token(profile: LocalProfile) -> str:
    header = _segment(b'{"alg":"HS256","typ":"JWT"}')
    payload = _segment(
        json.dumps(
            {
                "code": 1,
                "playerid": profile.player_id,
                "entry": "ws://10.0.2.2:23101/ws",
            },
            separators=(",", ":"),
        ).encode()
    )
    signature = _segment(
        hmac.new(_secret(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    )
    return f"{header}.{payload}.{signature}"


def verify_logic_token(token: str) -> dict[str, object]:
    header, payload, signature = token.split(".")
    expected = _segment(
        hmac.new(_secret(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(signature, expected):
        raise ValueError("invalid logic-token signature")
    return json.loads(_decode(payload))
