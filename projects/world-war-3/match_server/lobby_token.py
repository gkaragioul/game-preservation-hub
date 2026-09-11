#!/usr/bin/env python3
r"""
lobby_token.py -- mint/validate the WW3 lobbyToken (HS256 JWT), match-server side.

The client presents this JWT in its NMT_Login (see docs/M2_ControlChannel_Findings.md). It's
HS256, so we control the secret: our hub (mockserver/hub_server.py, M2) MINTS it and our match
server VALIDATES it -- no studio key. Secret must match the hub's ("ww3-local-private").

Real captured payload (structure locked, field-for-field):
  {type:"LobbyToken", lobbyId, playerId, serverGroup, team:{id}, isServerAssigned,
   server:{serverId,matchId,address,gamePort,queryPort,serverGroup,map,gameMode}, iat, exp}
"""
import hmac, hashlib, json, base64, time

SECRET = b"ww3-local-private"        # MUST match mockserver/hub_server.py mint_lobby_token()

def _b64url_decode(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

def _b64url_encode(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")

def decode(token):
    """Decode WITHOUT verifying (for inspection). Returns (header, payload) dicts."""
    h, p, _ = token.split(".")
    return json.loads(_b64url_decode(h)), json.loads(_b64url_decode(p))

def validate(token, secret=SECRET, now=None, verify_exp=True):
    """Verify signature (+ exp). Returns the claims dict, or None if invalid."""
    try:
        h_b64, p_b64, sig_b64 = token.split(".")
    except ValueError:
        return None
    signing_input = f"{h_b64}.{p_b64}".encode()
    expected = hmac.new(secret, signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _b64url_decode(sig_b64)):
        return None
    claims = json.loads(_b64url_decode(p_b64))
    if verify_exp:
        t = int(now if now is not None else time.time())
        if "exp" in claims and t > claims["exp"]:
            return None
    return claims

def mint(claims, secret=SECRET):
    """Mint an HS256 lobbyToken (mirror of the hub's minter)."""
    header = {"alg": "HS256", "typ": "JWT"}
    h = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    p = _b64url_encode(json.dumps(claims, separators=(",", ":")).encode())
    sig = _b64url_encode(hmac.new(secret, f"{h}.{p}".encode(), hashlib.sha256).digest())
    return f"{h}.{p}.{sig}"


if __name__ == "__main__":
    # mint -> validate round-trip
    now = 1784897698
    claims = {"type": "LobbyToken", "lobbyId": 70121, "playerId": 100002,
              "serverGroup": "default", "team": {"id": 1}, "isServerAssigned": True,
              "server": {"serverId": 17659577, "matchId": "17659577-1784897330704",
                         "address": "127.0.0.1", "gamePort": 7871, "queryPort": 27115,
                         "serverGroup": "default", "map": "WW3_Gobi_New_P", "gameMode": 47},
              "iat": now, "exp": now + 3600}
    tok = mint(claims)
    got = validate(tok, now=now)
    assert got and got["server"]["map"] == "WW3_Gobi_New_P", got
    assert validate(tok, now=now + 4000) is None, "expired token must fail"
    assert validate(tok[:-4] + "AAAA", now=now) is None, "tampered sig must fail"
    print(f"[OK] lobby_token mint/validate round-trips (map={got['server']['map']}, team={got['team']['id']})")
    # the captured token (studio secret) won't validate against ours, but must DECODE:
    cap = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0eXBlIjoiTG9iYnlUb2tlbiIsImxvYmJ5SWQiOjcwMTIx"
           "LCJwbGF5ZXJJZCI6ODExMDE5LCJzZXJ2ZXJHcm91cCI6ImRlZmF1bHQiLCJ0ZWFtIjp7ImlkIjoxfSwiaXNT"
           "ZXJ2ZXJBc3NpZ25lZCI6dHJ1ZSwic2VydmVyIjp7InNlcnZlcklkIjoxNzY1OTU3NywibWF0Y2hJZCI6IjE3"
           "NjU5NTc3LTE3ODQ4OTczMzA3MDQiLCJhZGRyZXNzIjoiMjEzLjE4My42Mi4xOCIsImdhbWVQb3J0Ijo3ODY4"
           "LCJxdWVyeVBvcnQiOjI3MTEyLCJzZXJ2ZXJHcm91cCI6ImRlZmF1bHQiLCJtYXAiOiJXVzNfR29iaV9OZXdf"
           "UCIsImdhbWVNb2RlIjo0N30sImlhdCI6MTc4NDg5NzY5OCwiZXhwIjoxNzg0OTAxMjk4fQ.x-_m9JEi2ljW2Z"
           "9VTI4bbUtzBZk9BMWmyqQEwyDmHQ8")
    _, payload = decode(cap)
    print(f"[OK] captured token decodes: map={payload['server']['map']} team={payload['team']['id']} "
          f"playerId={payload['playerId']}")
