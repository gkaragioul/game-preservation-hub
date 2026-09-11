#!/usr/bin/env python3
"""Tests for PS identity SteamID bit-patching."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from ps_identity import (  # noqa: E402
    CAPTURE_PS_STEAM,
    find_ascii_in_bits,
    name_from_login_url,
    patch_ps_steam,
    steam_from_login_bits,
)


def test_patch_ps_steam_in_capture_body():
    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
    bits = [int(c) for c in stream[21]["payload"]]
    assert find_ascii_in_bits(bits, CAPTURE_PS_STEAM), "capture PS must contain capture SteamID"
    live = "76561198000000000"
    assert patch_ps_steam(bits, live)
    assert find_ascii_in_bits(bits, live.encode())
    assert not find_ascii_in_bits(bits, CAPTURE_PS_STEAM)
    # idempotent
    assert patch_ps_steam(bits, live)
    print("[ok] PS SteamID patch src=21")


def test_name_from_login_url():
    assert name_from_login_url(
        "/Game/Maps/Main/Hub/WW3_Hub_P?Name=OfflinePlayer?BuildIdOverride=51"
    ) == "OfflinePlayer"
    assert name_from_login_url(
        "/Game/Maps/Main/Hub/WW3_Hub_P?Name=Player?BuildIdOverride=51"
    ) == "Player"
    print("[ok] login URL Name= parse")


def test_steam_from_login_bits_roundtrip():
    # Build a tiny bit buffer containing a SteamID at bit offset 0
    steam = b"76561198000000000"
    bits = []
    for byte in steam:
        for j in range(8):
            bits.append((byte >> j) & 1)
    assert steam_from_login_bits(bits) == steam.decode()
    print("[ok] steam_from_login_bits")


if __name__ == "__main__":
    test_patch_ps_steam_in_capture_body()
    test_name_from_login_url()
    test_steam_from_login_bits_roundtrip()
    print("ALL ps_identity tests passed")
