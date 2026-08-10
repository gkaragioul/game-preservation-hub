#!/usr/bin/env python3
"""Validate a JWT against the FXID schema recovered from working WW3 logs."""
import base64
import json
import sys
from pathlib import Path

REQUIRED = {
    "sub": int,
    "id": int,
    "auth_type": str,
    "public_tags": str,
    "soc_ids": dict,
    "email": str,
    "nbf": int,
    "exp": int,
    "iat": int,
    "iss": str,
    "aud": str,
}


def decode(segment: str):
    return json.loads(base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4)))


def main(path: str) -> int:
    token = Path(path).read_text(encoding="utf-8").strip()
    parts = token.split(".")
    if len(parts) != 3:
        print("FAIL: JWT must have 3 segments")
        return 1
    header, payload = decode(parts[0]), decode(parts[1])
    errors = []
    if header.get("alg") != "HS512":
        errors.append(f"alg is {header.get('alg')!r}, expected 'HS512'")
    for key, typ in REQUIRED.items():
        if key not in payload:
            errors.append(f"missing {key}")
        elif not isinstance(payload[key], typ):
            errors.append(f"{key} is {type(payload[key]).__name__}, expected {typ.__name__}")
    for key in ("steam", "email"):
        if key not in payload.get("soc_ids", {}):
            errors.append(f"soc_ids missing {key}")
    if errors:
        print("FAIL: " + "; ".join(errors))
        return 1
    print("PASS: token matches recovered FXID schema (HS512, 11 required claims)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
