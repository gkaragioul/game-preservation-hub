#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import os
import struct
import sys
from pathlib import Path

DELTA = 0x9E3779B9
MASK = 0xFFFFFFFF

BUNDLE_KEY_VAR = "SPIRAL_BUNDLE_KEY"
BUNDLE_KEY_LENGTH = 16


def bundle_key() -> bytes:
    """The client's script-bundle key, supplied by the operator.

    The key belongs to the copy of the client being preserved, so it is read
    from the environment and never committed. Without it this repository
    carries no means of decrypting anything.
    """
    value = os.environ.get(BUNDLE_KEY_VAR, "")
    if len(value.encode("utf-8")) != BUNDLE_KEY_LENGTH:
        raise SystemExit(
            f"{BUNDLE_KEY_VAR} must be set to the {BUNDLE_KEY_LENGTH}-byte "
            "bundle key from your own copy of the client"
        )
    return value.encode("utf-8")


def _words(data: bytes, include_length: bool) -> list[int]:
    count = (len(data) + 3) // 4
    padded = data.ljust(count * 4, b"\0")
    values = list(struct.unpack(f"<{count}I", padded)) if count else []
    if include_length:
        values.append(len(data))
    return values


def _bytes(values: list[int], include_length: bool) -> bytes:
    raw = struct.pack(f"<{len(values)}I", *values)
    if not include_length:
        return raw
    declared = values[-1]
    maximum = (len(values) - 1) * 4
    if declared < maximum - 3 or declared > maximum:
        raise ValueError("invalid XXTEA plaintext length")
    return raw[:declared]


def _mx(total: int, y: int, z: int, p: int, e: int, key: list[int]) -> int:
    return (
        (((z >> 5) ^ ((y << 2) & MASK)) + ((y >> 3) ^ ((z << 4) & MASK)))
        ^ ((total ^ y) + (key[(p & 3) ^ e] ^ z))
    ) & MASK


def encrypt_xxtea(data: bytes, key: bytes) -> bytes:
    if not data:
        return data
    values = _words(data, include_length=True)
    key_words = _words(key[:16].ljust(16, b"\0"), include_length=False)
    n = len(values) - 1
    rounds = 6 + 52 // (n + 1)
    total = 0
    z = values[n]
    for _ in range(rounds):
        total = (total + DELTA) & MASK
        e = (total >> 2) & 3
        for p in range(n):
            y = values[p + 1]
            z = values[p] = (values[p] + _mx(total, y, z, p, e, key_words)) & MASK
        y = values[0]
        z = values[n] = (values[n] + _mx(total, y, z, n, e, key_words)) & MASK
    return _bytes(values, include_length=False)


def decrypt_xxtea(data: bytes, key: bytes) -> bytes:
    if not data:
        return data
    values = _words(data, include_length=False)
    key_words = _words(key[:16].ljust(16, b"\0"), include_length=False)
    n = len(values) - 1
    rounds = 6 + 52 // (n + 1)
    total = (rounds * DELTA) & MASK
    y = values[0]
    while total:
        e = (total >> 2) & 3
        for p in range(n, 0, -1):
            z = values[p - 1]
            y = values[p] = (values[p] - _mx(total, y, z, p, e, key_words)) & MASK
        z = values[n]
        y = values[0] = (values[0] - _mx(total, y, z, 0, e, key_words)) & MASK
        total = (total - DELTA) & MASK
    return _bytes(values, include_length=True)


def unpack_jsc(data: bytes, key: bytes) -> bytes:
    return gzip.decompress(decrypt_xxtea(data, key))


def pack_jsc(source: bytes, key: bytes) -> bytes:
    return encrypt_xxtea(gzip.compress(source, mtime=0), key)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("unpack", "pack"))
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--key",
        help=(
            f"16-byte bundle key from your own copy of the client; "
            f"defaults to ${BUNDLE_KEY_VAR}"
        ),
    )
    args = parser.parse_args()
    key = args.key.encode("utf-8") if args.key else bundle_key()
    operation = unpack_jsc if args.mode == "unpack" else pack_jsc
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(operation(args.input.read_bytes(), key))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
