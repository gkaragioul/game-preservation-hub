import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("cocos_jsc", ROOT / "tools" / "cocos_jsc.py")
cocos_jsc = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(cocos_jsc)

# The bundle key belongs to the operator's own copy of the client. It is
# supplied at runtime and never committed, so this repository carries no
# means of decrypting anything by itself.
KEY = b"0123456789abcdef"


def test_bundle_key_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("SPIRAL_BUNDLE_KEY", "f" * 16)
    assert cocos_jsc.bundle_key() == b"f" * 16


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        pytest.param(None, "unset", id="unset"),
        pytest.param("", "empty", id="empty"),
        pytest.param("short", "not sixteen bytes", id="too-short"),
        pytest.param("f" * 17, "not sixteen bytes", id="too-long"),
    ],
)
def test_missing_bundle_key_is_refused(monkeypatch, value, reason):
    if value is None:
        monkeypatch.delenv("SPIRAL_BUNDLE_KEY", raising=False)
    else:
        monkeypatch.setenv("SPIRAL_BUNDLE_KEY", value)
    with pytest.raises(SystemExit):
        cocos_jsc.bundle_key()


def test_xxtea_round_trip_preserves_non_word_aligned_bytes():
    source = b"Spiral Warrior\x00offline\xff"
    assert cocos_jsc.decrypt_xxtea(cocos_jsc.encrypt_xxtea(source, KEY), KEY) == source


@pytest.mark.preservation_artifact
def test_real_main_bundle_recovers_source_proof_without_writing_it():
    key = cocos_jsc.bundle_key()
    packed = (ROOT / "cn_apk/assets/assets/main/index.jsc").read_bytes()
    source = cocos_jsc.unpack_jsc(packed, key)
    assert len(source) == 11_974_432
    assert len(source.decode("utf-8")) == 11_933_269
    assert b"WebSocketApply" in source
    assert b"areaRet.decode" in source
    assert cocos_jsc.unpack_jsc(cocos_jsc.pack_jsc(source, key), key) == source
