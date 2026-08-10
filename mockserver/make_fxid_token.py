#!/usr/bin/env python3
"""Generate a schema-correct synthetic FXID JWT for local WW3 revival testing.

This token is deliberately not a captured credential.  It matches the claim
schema recovered from working WW3 logs so the client's local JWT parser can be
tested.  The signature uses a local-only key and is not expected to validate
against the retired FXID service.
"""
import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def main() -> None:
    now = int(time.time())
    header = {"alg": "HS512", "typ": "JWT"}
    payload = {
        "sub": 39422,
        "id": 39422,
        "auth_type": "steam",
        "public_tags": "[]",
        "soc_ids": {
            "steam": "76561198000000000",
            "email": "ww3-local@example.invalid",
            "mygamesid": "247395880",
        },
        "email": "ww3-local@example.invalid",
        "nbf": now - 60,
        "exp": now + 7 * 24 * 60 * 60,
        "iat": now - 60,
        "iss": "https://id.fx.gl",
        "aud": "https://id.fx.gl",
    }
    signing_input = ".".join(
        b64url(json.dumps(part, separators=(",", ":")).encode("utf-8"))
        for part in (header, payload)
    )
    key = os.environ.get("WW3_LOCAL_JWT_KEY", "ww3-local-revival-only").encode()
    signature = hmac.new(key, signing_input.encode(), hashlib.sha512).digest()
    token = signing_input + "." + b64url(signature)
    out = Path(__file__).with_name("fxid_token.txt")
    out.write_text(token, encoding="utf-8")
    os.chmod(out, 0o600)
    print(f"wrote {out} ({len(token)} chars, schema=FXID/HS512)")


if __name__ == "__main__":
    main()
