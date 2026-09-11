#!/usr/bin/env python3
"""Source-anchored offline patches for the shipped CN Cocos bundle.

The retired 9game/DHUnion account service cannot initialise against local
services: its own telemetry reports ``SDK_CLIENT_LOGIN`` with
``登录失败：未初始化`` and the JS bridge receives ``DHSDK.onLogin false`` with an
empty payload, so the client never requests a logic token and never opens the
gateway socket.

Each patch rewrites one exact anchor recovered from the decrypted bundle. A
missing, duplicated, or already-rewritten anchor is a hard error, so a
different client build can never be patched blind.

The synthesized payload mirrors what the live SDK would have returned. The
account id stays numeric because ``requestToken`` feeds it through ``Number()``
before ``apply_address`` builds ``/auth/es?account=...``; a non-numeric id
arrives as ``NaN``. 100000001 is the same stable local player id the gateway
issues in its apply token.
"""

from __future__ import annotations

import argparse
from pathlib import Path

OFFLINE_ACCOUNT_ID = "100000001"
OFFLINE_LOGIN_TYPE = "LoginType_Quick_Visitor"

_LOGIN_ANCHOR = (
    "t.prototype.onLogin = function(e, t) {\n"
    "var n = this;\n"
    'p.x3.log("DHSDK.onLogin", e);'
)
_LOGIN_REPLACEMENT = (
    "t.prototype.onLogin = function(e, t) {\n"
    "var n = this;\n"
    "if (!1 === e) {\n"
    "e = !0;\n"
    "t = '{\"accountid\":\"" + OFFLINE_ACCOUNT_ID + "\",\"logintype\":\""
    + OFFLINE_LOGIN_TYPE + "\"}';\n"
    "}\n"
    'p.x3.log("DHSDK.onLogin", e);'
)

PATCHES: tuple[tuple[str, str, str], ...] = (
    ("offline-login", _LOGIN_ANCHOR, _LOGIN_REPLACEMENT),
)


class PatchError(RuntimeError):
    """An expected, user-actionable patch failure."""


def apply_offline_patches(source: bytes) -> bytes:
    """Rewrite every offline anchor in a decrypted bundle exactly once."""
    text = source.decode("utf-8")
    for name, anchor, replacement in PATCHES:
        found = text.count(anchor)
        if found != 1:
            raise PatchError(
                f"{name}: expected exactly one anchor, found {found}"
            )
        text = text.replace(anchor, replacement)
    return text.encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(
        apply_offline_patches(arguments.input.read_bytes())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
