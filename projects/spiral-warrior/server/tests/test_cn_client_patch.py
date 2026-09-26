"""Contract for the source-anchored offline patches applied to the CN bundle."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


patch = _load("cn_client_patch")
cocos_jsc = _load("cocos_jsc")

BUNDLE = ROOT / "cn_apk" / "assets" / "assets" / "main" / "index.jsc"

SHIPPED_LOGIN_CALLBACK = (
    't.prototype.onLogin = function(e, t) {\n'
    'var n = this;\n'
    'p.x3.log("DHSDK.onLogin", e);\n'
    'p.x3.log("DHSDK.onLogin resultData = ", t);\n'
    'if (!1 === e) {\n'
)


def test_offline_login_patch_rewrites_the_failed_callback_once():
    patched = patch.apply_offline_patches(SHIPPED_LOGIN_CALLBACK.encode("utf-8"))
    text = patched.decode("utf-8")

    assert text.count(patch.OFFLINE_ACCOUNT_ID) == 1
    assert "LoginType_Quick_Visitor" in text
    # The synthesized payload must survive replaceResultData() and JSON.parse().
    literal = re.search(r"t = '(\{.*?\})';", text)
    assert literal is not None
    claims = json.loads(literal.group(1))
    assert claims == {
        "accountid": patch.OFFLINE_ACCOUNT_ID,
        "logintype": "LoginType_Quick_Visitor",
    }
    # requestToken() feeds the account through Number(); a non-numeric id
    # would reach apply_address() as NaN.
    assert claims["accountid"].isdigit()


def test_missing_anchor_is_a_hard_error():
    with pytest.raises(patch.PatchError, match="anchor"):
        patch.apply_offline_patches(b"function unrelated() {}")


def test_already_patched_source_is_rejected():
    once = patch.apply_offline_patches(SHIPPED_LOGIN_CALLBACK.encode("utf-8"))
    with pytest.raises(patch.PatchError, match="anchor"):
        patch.apply_offline_patches(once)


@pytest.mark.preservation_artifact
def test_real_bundle_patches_and_round_trips():
    key = cocos_jsc.bundle_key()
    original = cocos_jsc.unpack_jsc(BUNDLE.read_bytes(), key)
    patched = patch.apply_offline_patches(original)

    assert patched != original
    assert len(patched) > len(original)

    repacked = cocos_jsc.pack_jsc(patched, key)
    assert cocos_jsc.unpack_jsc(repacked, key) == patched
    # Deterministic output keeps the derived APK reproducible.
    assert cocos_jsc.pack_jsc(patched, key) == repacked

    text = patched.decode("utf-8")
    assert text.count('"accountid":"100000001"') == 1
    assert 'p.x3.log("DHSDK.onLogin", e);' in text
