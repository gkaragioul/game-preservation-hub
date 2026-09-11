"""Provenance contract for the derived CN runtime APK.

The launcher installs a derived APK instead of the immutable source archive.
The only differences the preservation lab accepts are the debug signature and
the recompiled user-CA network security member. Any other divergence means a
build step silently rewrote game content, which is exactly how the corrupted
64-byte ``data/PartSuit`` table reached the emulator and wedged the Cocos boot
path with ``invalid wire type 7 at offset 1``.
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE_APK = ROOT / "cn_9game.apk"
RUNTIME_APK = ROOT / "patched" / "LuoXuanWarrior_cn_partsuit_userca_debug.apk"

NETWORK_SECURITY_MEMBER = "res/xml/lebian_network_security_config.xml"
BUNDLE_MEMBER = "assets/assets/main/index.jsc"
COMPILED_MEMBER_SHA256 = (
    "be19b1947c55c92325d53643a5a4aaed16f4b241dd7a7c9a522d25287107cec4"
)
BUNDLE_MEMBER_SHA256 = (
    "0770fe5fdcafde95ccb90b833034078ce358c74e223b9040c32b4cc0ec050880"
)
PART_SUIT_MEMBER = (
    "assets/assets/resources/native/b4/"
    "b4bc0aa8-8d49-434e-b2fe-722279cdc129.bin"
)
SIGNATURE_SUFFIXES = (".SF", ".RSA", ".DSA", ".EC")


def _is_signature_member(name: str) -> bool:
    if name == "META-INF/MANIFEST.MF":
        return True
    if not name.startswith("META-INF/"):
        return False
    return name.upper().endswith(SIGNATURE_SUFFIXES)


def _content_index(path: Path) -> dict[str, tuple[int, int]]:
    with zipfile.ZipFile(path) as archive:
        return {
            info.filename: (info.file_size, info.CRC)
            for info in archive.infolist()
            if not info.is_dir() and not _is_signature_member(info.filename)
        }


@pytest.mark.preservation_artifact
def test_runtime_apk_only_replaces_the_two_documented_members():
    source = _content_index(SOURCE_APK)
    runtime = _content_index(RUNTIME_APK)

    assert sorted(runtime) == sorted(source)

    divergent = sorted(name for name in source if source[name] != runtime[name])
    assert divergent == sorted((BUNDLE_MEMBER, NETWORK_SECURITY_MEMBER))


@pytest.mark.preservation_artifact
def test_runtime_apk_carries_the_reviewed_offline_bundle():
    with zipfile.ZipFile(RUNTIME_APK) as archive:
        bundle = archive.read(BUNDLE_MEMBER)

    assert hashlib.sha256(bundle).hexdigest() == BUNDLE_MEMBER_SHA256


@pytest.mark.preservation_artifact
def test_runtime_apk_keeps_the_empty_part_suit_table():
    with zipfile.ZipFile(RUNTIME_APK) as archive:
        part_suit = archive.read(PART_SUIT_MEMBER)

    # An empty protobuf message is the shipped table. A non-empty payload here
    # reaches PartSuitArray.decode() and aborts the client boot sequence.
    assert part_suit == b""


@pytest.mark.preservation_artifact
def test_runtime_apk_carries_the_reviewed_user_ca_member():
    with zipfile.ZipFile(RUNTIME_APK) as archive:
        member = archive.read(NETWORK_SECURITY_MEMBER)

    assert hashlib.sha256(member).hexdigest() == COMPILED_MEMBER_SHA256
