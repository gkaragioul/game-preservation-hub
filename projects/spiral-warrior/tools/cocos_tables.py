#!/usr/bin/env python3
"""Shared reader for the shipped Cocos Creator binary data tables.

The game's static data lives in `resources/native/<xx>/<uuid>.bin`, reached
through the bundle config: `data/<Name>` is an entry in
``resources/config.json``'s ``paths``, whose index selects a compressed uuid
in ``uuids``; decoding that uuid gives the file name.

Each table is a protobuf message holding one length-delimited record per row.
Field numbers come from the generated `encode` functions in the decrypted
bundle, so every extractor names its own.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "cn_apk" / "assets" / "assets" / "resources"

BASE64_KEYS = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
)
BASE64_VALUES = {character: index for index, character in enumerate(BASE64_KEYS)}
HEX_CHARS = "0123456789abcdef"


def decode_uuid(compressed: str) -> str:
    """Expand a Cocos compressed asset uuid into its dashed form."""
    if len(compressed) != 22:
        return compressed
    digits = [compressed[0], compressed[1]]
    for index in range(2, 22, 2):
        left = BASE64_VALUES[compressed[index]]
        right = BASE64_VALUES[compressed[index + 1]]
        digits.append(HEX_CHARS[left >> 2])
        digits.append(HEX_CHARS[((left & 3) << 2) | (right >> 4)])
        digits.append(HEX_CHARS[right & 0xF])
    joined = "".join(digits)
    return (
        f"{joined[:8]}-{joined[8:12]}-{joined[12:16]}"
        f"-{joined[16:20]}-{joined[20:]}"
    )


def resolve_table(resources: Path, table_path: str) -> Path:
    config = json.loads((resources / "config.json").read_text(encoding="utf-8"))
    for index, entry in config["paths"].items():
        if entry and str(entry[0]) == table_path:
            uuid = decode_uuid(config["uuids"][int(index)])
            return resources / "native" / uuid[:2] / f"{uuid}.bin"
    raise SystemExit(f"{table_path} is absent from the resources bundle")


def _varint(buffer: bytes, index: int) -> tuple[int, int]:
    value = shift = 0
    while True:
        byte = buffer[index]
        index += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, index
        shift += 7


def fields(buffer: bytes):
    index = 0
    while index < len(buffer):
        key, index = _varint(buffer, index)
        number, wire = key >> 3, key & 7
        if wire == 0:
            value, index = _varint(buffer, index)
            yield number, wire, value
        elif wire == 2:
            length, index = _varint(buffer, index)
            yield number, wire, buffer[index:index + length]
            index += length
        elif wire == 5:
            yield number, wire, buffer[index:index + 4]
            index += 4
        elif wire == 1:
            yield number, wire, buffer[index:index + 8]
            index += 8
        else:
            raise ValueError(f"unsupported wire type {wire}")


def signed(value: int) -> int:
    """Reinterpret a varint as the int32 the table actually stores."""
    return value - (1 << 64) if value >= (1 << 63) else value


def read_records(
    table: Path,
    key_field: int,
    repeated: frozenset[int] = frozenset(),
) -> list[dict[int, int | tuple[int, ...]]]:
    """Return every row's scalar fields, skipping rows without `key_field`.

    Field numbers named in `repeated` accumulate into a tuple instead of
    keeping only the last value, which is how a `repeated int32` column such
    as `ExportIdArray` is stored.
    """
    records = []
    for _, wire, payload in fields(table.read_bytes()):
        if wire != 2:
            continue
        record: dict[int, int | tuple[int, ...]] = {}
        try:
            for number, inner_wire, value in fields(payload):
                if inner_wire != 0:
                    continue
                if number in repeated:
                    previous = record.get(number, ())
                    assert isinstance(previous, tuple)
                    record[number] = previous + (value,)
                else:
                    record[number] = value
        except (IndexError, ValueError):
            continue
        if key_field in record:
            records.append(record)
    return records
