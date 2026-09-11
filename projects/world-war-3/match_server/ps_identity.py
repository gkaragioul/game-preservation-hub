#!/usr/bin/env python3
"""Patch capture PlayerState identity bits to match the live client's NMT_Login.

Live hang scan (2026-08-04): PlayerState sync stayed false while MapLevels/GameState
were true. Decoded NMT_Login vs PS RepLayout (src 21):

  Login:  Name=OfflinePlayer  UniqueId=76561198000000000
  PS:     PlayerName=Player    UniqueId=76561199000000000  (capture player)

Same-length SteamID swap is bit-safe. PlayerName length differs — align the hub
login Name to the capture name (Player) instead of resizing the RepLayout FString.
"""
from __future__ import annotations

import re
from typing import Optional

CAPTURE_PS_STEAM = b"76561199000000000"
CAPTURE_PS_NAME = b"Player"


def bits_to_bytes(bits: list[int], off: int = 0) -> bytes:
    b = bits[off:]
    out = bytearray()
    for i in range(len(b) // 8):
        v = 0
        for j in range(8):
            v |= (b[i * 8 + j] & 1) << j
        out.append(v)
    return bytes(out)


def replace_ascii_in_bits(bits: list[int], old: bytes, new: bytes) -> bool:
    """LSB-first packed ASCII replace. old/new must be equal length."""
    if len(old) != len(new) or not old:
        return False
    for off in range(8):
        raw = bytearray(bits_to_bytes(bits, off))
        p = raw.find(old)
        if p < 0:
            continue
        for bi, byte in enumerate(new):
            abs_byte = p + bi
            for j in range(8):
                bits[off + abs_byte * 8 + j] = (byte >> j) & 1
        return True
    return False


def find_ascii_in_bits(bits: list[int], needle: bytes) -> bool:
    for off in range(8):
        if needle in bits_to_bytes(bits, off):
            return True
    return False


def patch_ps_steam(bits: list[int], live_steam: str) -> bool:
    """Replace capture SteamID with the live client's UniqueId (17-digit Steam)."""
    live = live_steam.encode("ascii")
    if len(live) != len(CAPTURE_PS_STEAM):
        return False
    if find_ascii_in_bits(bits, live):
        return True  # already patched
    return replace_ascii_in_bits(bits, CAPTURE_PS_STEAM, live)


def steam_from_login_bits(bits_after_url: list[int]) -> Optional[str]:
    for off in range(8):
        raw = bits_to_bytes(bits_after_url, off)
        m = re.search(rb"7656119\d{10}", raw)
        if m:
            return m.group().decode("ascii")
    return None


def name_from_login_url(url: str) -> Optional[str]:
    for part in url.split("?"):
        if part.startswith("Name="):
            return part[5:] or None
    return None
