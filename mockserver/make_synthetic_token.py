#!/usr/bin/env python3
r"""
make_synthetic_token.py -- mint a SYNTHETIC FXID login token that never expires
(10 years), structurally identical to the real id.fx.gl token.

The client treats this token as an opaque courier: it POSTs it to /authenticate/fxgames
(our mock mints its own PlayerToken, ignoring it) and hands it to Epic's external_auth
grant (our epic_faker forges a 200, ignoring it). Nothing verifies its HS512 signature
locally, so any secret works. This is the last piece of forever-offline: no live
id.wishlistgames, no real Epic, no ~7-day token expiry.

Writes fxid_offline_token.txt (backing up whatever is there to .real.bak).
Run:  python make_synthetic_token.py
"""
import base64, json, hmac, hashlib, time, os, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
TOK  = os.path.join(HERE, "fxid_offline_token.txt")

# identity claims mirrored from the captured real token (this account's own ids)
SUB       = 100001
STEAM_ID  = "76561198000000000"
MYGAMESID = "11724744"
TEN_YEARS = 10 * 365 * 24 * 3600

def b64u(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def mint():
    now = int(time.time())
    header  = {"alg": "HS512", "typ": "JWT"}
    payload = {
        "sub": SUB, "id": SUB, "auth_type": "steam", "public_tags": [],
        "soc_ids": {"steam": STEAM_ID, "mygamesid": MYGAMESID},
        "nbf": now, "exp": now + TEN_YEARS, "iat": now,
        "iss": "https://id.fx.gl", "aud": "https://id.fx.gl",
    }
    seg = lambda o: b64u(json.dumps(o, separators=(",", ":")).encode())
    signing = seg(header) + "." + seg(payload)
    sig = hmac.new(b"ww3-local-private", signing.encode(), hashlib.sha512).digest()
    return signing + "." + b64u(sig)

if __name__ == "__main__":
    if os.path.exists(TOK) and not os.path.exists(TOK + ".real.bak"):
        shutil.copy(TOK, TOK + ".real.bak")
        print(f"[*] backed up existing (real) token -> {os.path.basename(TOK)}.real.bak")
    t = mint()
    open(TOK, "w").write(t)
    yrs = TEN_YEARS / 86400 / 365
    print(f"[OK] synthetic FXID token written ({len(t)} chars, exp +{yrs:.0f}y) -> {TOK}")
    print("     Now:  ww3_mock.ps1 forever   then   launch_offline.ps1 eac")
