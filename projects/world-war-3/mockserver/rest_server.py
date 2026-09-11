#!/usr/bin/env python3
"""
WW3 path-aware HTTPS mock — serves the REST layer with real-shaped responses
learned from the working-day client log:

  meta.prod.ww3.fxtools.gl:443
      GET /friends/getAll                 -> {"result":[...friends...]}
      GET /friends/getReceivedInvitations -> {"result":[]}
  api.public.dev.ww3.fxtools.gl:443
      *  (DateTimeKeeper)                  -> {"serverTimestamp": <ms>}  (best-effort)
  anything else                           -> {"success":true,"status":"APPROVED",...}

One self-signed cert covers *.ww3.fxtools.gl / *.ww3.my.games / *.fx.gl / localhost.
The client runs libcurl with bVerifyPeer=false, so any cert is accepted.
"""
import http.server, ssl, json, os, datetime, time, sys, urllib.parse
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import ipaddress

CERT = "mock_cert.pem"
KEY = "mock_key.pem"
EPIC_CERT = os.path.join("epic_ca", "epic_cert.pem")   # CA-signed, SANs for *.epicgames.dev
EPIC_KEY  = os.path.join("epic_ca", "epic_key.pem")

# Fold in the EOS-Auth faker so ONE server on :443 handles both the game backend
# (ww3 hosts, mock_cert) and Epic (epicgames.dev, epic_cert) -- forever-offline.
try:
    import epic_faker as EPIC
    print("[*] epic_faker loaded -- api.epicgames.dev token grants will be FORGED (WW3-scoped)")
except Exception as _e:
    EPIC = None
    print(f"[!] epic_faker unavailable ({_e}); Epic hosts will NOT be forged")

# --- WW3-SCOPING: only forge Epic requests that are actually WW3's. Everything else
#     (Hunt, Fortnite, any EOS game) is transparently proxied to the REAL Epic so it
#     keeps working even if this stack is left running. WW3's own ClientId/Product/
#     Deployment/Sandbox ids identify its traffic. ---
import socket as _socket, subprocess as _sp
WW3_EPIC_IDS = (
    "xyza78913PNJAxLsnw1B5OGzaAYR4zPW",   # WW3 ClientId
    "fd268a599d7e49dda99dd002488e9fa2",   # WW3 ProductId
    "0bf47cddeab54c08b0358c134ec54408",   # WW3 DeploymentId
    "54ddf5e8d6b3441ea0d56726677dd234",   # WW3 SandboxId
)
_EPIC_REAL_IP = [None]
def _real_epic_ip():
    """Resolve the REAL api.epicgames.dev via public DNS (bypassing our hosts redirect)."""
    if _EPIC_REAL_IP[0]:
        return _EPIC_REAL_IP[0]
    try:
        out = _sp.run(["powershell", "-NoProfile", "-Command",
            "(Resolve-DnsName api.epicgames.dev -Type A -Server 1.1.1.1 -EA SilentlyContinue|"
            "?{$_.Type -eq 'A'}|Select-Object -First 1).IPAddress"],
            capture_output=True, text=True, timeout=8).stdout.strip()
        _EPIC_REAL_IP[0] = out or None
    except Exception:
        pass
    return _EPIC_REAL_IP[0]

def gen_cert():
    if os.path.exists(CERT) and os.path.exists(KEY):
        return
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u"*.ww3.fxtools.gl"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"WW3 Local Mock"),
    ])
    cert = (x509.CertificateBuilder()
        .subject_name(subject).issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName([
            x509.DNSName(u"*.ww3.fxtools.gl"),
            x509.DNSName(u"*.ww3.my.games"),
            x509.DNSName(u"*.fx.gl"),
            x509.DNSName(u"*.prod-my.games"),
            x509.DNSName(u"localhost"),
            x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        ]), critical=False)
        .sign(key, hashes.SHA256()))
    open(KEY, "wb").write(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption()))
    open(CERT, "wb").write(cert.public_bytes(serialization.Encoding.PEM))
    print("[*] cert generated")

def now_ms():
    return int(time.time() * 1000)

try:
    sys.stdout.reconfigure(line_buffering=True)   # so request logs appear live in the file
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

# --- captured responses (from build_replay_map.py) --------------------------
import re as _re, hmac as _hmac, hashlib as _hashlib, base64 as _b64lib
_MAP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "replay_map.json")
_CONTENT_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content_cache")
REPLAY = json.load(open(_MAP_PATH, encoding="utf-8")).get("http", {}) if os.path.exists(_MAP_PATH) else {}
def _norm(p):
    return _re.sub(r"/\d{5,}", "/{id}", p.split("?")[0])
print(f"[*] loaded {len(REPLAY)} captured endpoints from replay_map.json")
if os.path.isdir(_CONTENT_CACHE):
    print(f"[*] content cache ready: {_CONTENT_CACHE}")

try:
    import entitlements as ENT
    print(f"[*] entitlements loaded (default={ENT.resolve_tier([])})")
except Exception as _e:
    ENT = None
    print(f"[!] entitlements unavailable: {_e}")

try:
    import progression_runtime as PROG
except Exception as _e:
    PROG = None
    print(f"[!] progression_runtime unavailable: {_e}")

def _request_ids(handler, path: str) -> list:
    """Collect Steam / FX ids from URL, auth, or body for entitlement lookup."""
    ids = []
    m = _re.search(r"/(\d{5,})", path)
    if m:
        ids.append(m.group(1))
    auth = handler.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        parts = auth.split(" ", 1)[1].split(".")
        if len(parts) > 1:
            try:
                pad = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
                payload = json.loads(_b64lib.urlsafe_b64decode(pad))
                for k in ("id", "playerId", "steamId", "steamid"):
                    if k in payload:
                        ids.append(payload[k])
                plat = payload.get("platformId") or {}
                if isinstance(plat, dict):
                    for v in plat.values():
                        ids.append(v)
            except Exception:
                pass
    try:
        body = json.loads((getattr(handler, "_body", b"") or b"{}").decode("utf-8", "replace") or "{}")
        if isinstance(body, dict):
            for k in ("playerId", "id", "steamId", "accountId"):
                if k in body:
                    ids.append(body[k])
    except Exception:
        pass
    # Offline mock identity fallback when the request carries no player ids
    if not ids:
        ids.append(PLAYER_ID)
        ids.append(FXGAMES_ID)
    return ids

def _tier_for(handler, path: str) -> str:
    if ENT is None:
        return "public"
    return ENT.resolve_tier(_request_ids(handler, path))

def _ensure_helper_inventory():
    """Helpers get progression-tree unlocks (not BP awards)."""
    inv_entry = REPLAY.get("GET /inventory/get")
    prog_entry = REPLAY.get("GET /progression/getProgressionTree")
    if not isinstance(inv_entry, dict) or not isinstance(prog_entry, dict):
        return
    inv = (inv_entry.get("body") or {}).get("result")
    prog = (prog_entry.get("body") or {}).get("result")
    if not isinstance(inv, dict) or not isinstance(prog, dict):
        return
    ids = set()
    for ent in prog.get("entities") or []:
        for lvl in (ent.get("levels") or []):
            for it in ((lvl.get("rewards") or {}).get("items") or []):
                try:
                    ids.add(int(it))
                except (TypeError, ValueError):
                    pass
    owned = {it.get("id") for it in (inv.get("player") or []) if isinstance(it, dict)}
    added = 0
    for iid in ids:
        if iid not in owned:
            inv.setdefault("player", []).append({"id": iid, "visited": True, "attachments": []})
            owned.add(iid)
            added += 1
    if added:
        print(f"[ENT] helper inventory +{added} progression items")

def _content_type_for(path: str) -> str:
    low = path.lower()
    if low.endswith(".png"): return "image/png"
    if low.endswith((".jpg", ".jpeg")): return "image/jpeg"
    if low.endswith(".jfif"): return "image/jpeg"
    if low.endswith(".webp"): return "image/webp"
    if low.endswith(".gif"): return "image/gif"
    if low.endswith(".svg"): return "image/svg+xml"
    return "application/octet-stream"

def _lookup_content_cache(url_path: str):
    """Serve /ww3-content/... files from content_cache (downloaded BP/shop art)."""
    raw = url_path.split("?")[0]
    # clients sometimes send spaces unencoded
    try:
        from urllib.parse import unquote
        raw = unquote(raw)
    except Exception:
        pass
    marker = "/ww3-content/"
    i = raw.lower().find(marker)
    if i < 0:
        return None
    rel = raw[i + len(marker):].lstrip("/\\")
    if not rel or ".." in rel.replace("\\", "/").split("/"):
        return None
    full = os.path.normpath(os.path.join(_CONTENT_CACHE, "ww3-content", rel.replace("/", os.sep)))
    root = os.path.normpath(os.path.join(_CONTENT_CACHE, "ww3-content"))
    if not full.startswith(root) or not os.path.isfile(full):
        return None
    try:
        data = open(full, "rb").read()
    except Exception:
        return None
    if len(data) < 16:
        return None
    return data, _content_type_for(full)

# Mutable season/shop helpers for buy/claim (item 5 polish)
def _season_result():
    entry = REPLAY.get("GET /season/getSeason")
    if not isinstance(entry, dict):
        return None
    body = entry.get("body")
    if isinstance(body, dict) and isinstance(body.get("result"), dict):
        return body["result"]
    return None

def _apply_bp_purchase(kind="premium"):
    """Player bought/activated the battle pass — does NOT grant track levels."""
    seas = _season_result()
    if not isinstance(seas, dict):
        return False
    seas["battlePassStatus"] = "activated"
    seas["isVisitedSeason"] = True
    bp = seas.get("battlePass")
    supported = seas.get("supportedBattlePasses") or {}
    if isinstance(bp, dict):
        if kind == "premium" and isinstance(supported, dict) and supported.get("premium") is not None:
            bp["id"] = supported["premium"]
        elif kind == "normal" and isinstance(supported, dict) and supported.get("normal") is not None:
            bp["id"] = supported["normal"]
        # Leave unlockedLevels / progression as-is — earned from play.
    print(f"[BP] purchase applied kind={kind} status=activated passId={(bp or {}).get('id')} "
          f"(track unchanged; levels come from play)")
    return True

def _apply_bp_claim_or_skip():
    """Tier-skip / claim: small unlock only — never god-complete the track."""
    seas = _season_result()
    if not isinstance(seas, dict):
        return False
    seas["battlePassStatus"] = "activated"
    bp = seas.get("battlePass")
    levels = (seas.get("progressionTree") or {}).get("levels") or []
    max_lvl = max((lv.get("level") or 0 for lv in levels), default=51)
    if isinstance(bp, dict):
        cur = int(bp.get("unlockedLevels") or 0)
        # One tier skip at a time (shop product), capped at track max.
        bp["unlockedLevels"] = min(max_lvl, cur + 1)
        print(f"[BP] tier-skip -> unlockedLevels={bp['unlockedLevels']}")
    if isinstance(seas.get("progression"), dict):
        # Keep progression level in sync with unlockedLevels if behind.
        ul = int((bp or {}).get("unlockedLevels") or 0)
        if int(seas["progression"].get("level") or 0) < ul:
            seas["progression"]["level"] = ul
    return True

def _bump_challenges_after_match(step=1):
    """Disabled — challenge progress must come from real dedicated-server play."""
    return

# --- token minting: the client treats these JWTs as opaque couriers between our
#     own services, so we forge HS256 tokens with a FUTURE expiry (any secret). ---
PLAYER_ID  = 100001            # from capture (george's account)
FXGAMES_ID = 100001
HUB_WS     = "ws://127.0.0.1:8700"
# M3 dedicated-server identity (env-overridable so M2's handoff can be aligned to it)
DS_SERVER_ID = int(os.environ.get("WW3_DS_SERVER_ID", "286109716"))
DS_MATCH_ID  = os.environ.get("WW3_DS_MATCH_ID", f"{DS_SERVER_ID}-0")
def _b64u(d):
    return _b64lib.urlsafe_b64encode(d).decode("ascii").rstrip("=")
def mint_jwt(payload):
    payload = dict(payload); now = int(time.time())
    payload.setdefault("iat", now); payload.setdefault("exp", now + 30 * 24 * 3600)  # 30 days
    header = {"alg": "HS256", "typ": "JWT"}
    signing = ".".join(_b64u(json.dumps(p, separators=(",", ":")).encode()) for p in (header, payload))
    sig = _hmac.new(b"ww3-local-private", signing.encode(), _hashlib.sha256).digest()
    return signing + "." + _b64u(sig)

class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, obj, code=200, content_type=None):
        if isinstance(obj, (bytes, bytearray)):
            body = bytes(obj)
            ctype = content_type or "application/octet-stream"
        else:
            body = json.dumps(obj).encode()
            ctype = content_type or "application/json"
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(body)

    def _epic_is_ww3(self, path):
        """True only if this Epic request carries WW3's identifiers (ClientId in Basic
        auth, our forged token's claims in Bearer auth, or the ids in the URL/body)."""
        blob = path
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Basic "):
            try: blob += " " + _b64lib.b64decode(auth.split(" ", 1)[1]).decode("latin1", "replace")
            except Exception: pass
        elif auth.startswith("Bearer "):
            parts = auth.split(" ", 1)[1].split(".")
            if len(parts) > 1:
                try: blob += " " + _b64lib.urlsafe_b64decode(parts[1] + "==").decode("latin1", "replace")
                except Exception: pass
        blob += " " + (getattr(self, "_body", b"") or b"").decode("latin1", "replace")
        return any(i in blob for i in WW3_EPIC_IDS)

    def _epic_passthrough(self, method, path):
        """Relay a NON-WW3 Epic request to the real api.epicgames.dev and return its real
        response verbatim -- so other EOS games are never affected by our faker."""
        ip = _real_epic_ip()
        if not ip:
            print(f"[EPIC] passthrough DNS-fail for {path} -> 502"); self._send({"errorCode": "passthrough_dns"}, 502); return
        body = getattr(self, "_body", b"") or b""
        hdrs = "".join(f"{k}: {v}\r\n" for k, v in self.headers.items()
                       if k.lower() not in ("host", "content-length", "connection"))
        req = (f"{method} {path} HTTP/1.1\r\nHost: api.epicgames.dev\r\n{hdrs}"
               f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n").encode() + body
        try:
            ctx = ssl.create_default_context()
            s = ctx.wrap_socket(_socket.create_connection((ip, 443), timeout=15), server_hostname="api.epicgames.dev")
            s.sendall(req); resp = b""
            while True:
                c = s.recv(65536)
                if not c: break
                resp += c
            s.close()
        except Exception as e:
            print(f"[EPIC] passthrough FAILED {path}: {e} -> 502"); self._send({"errorCode": "passthrough_fail"}, 502); return
        print(f"[EPIC] passthrough (NON-WW3) {method} {path} -> real Epic ({len(resp)}b relayed)")
        self.wfile.write(resp); self.close_connection = True

    def _epic_route(self, p):
        """Forge Epic EOS-Auth responses so a synthetic token boots offline forever --
        but ONLY for WW3. Anything else is proxied to the real Epic (see _epic_passthrough)."""
        if not self._epic_is_ww3(p):
            # NOT positively WW3 -> forward to the REAL Epic so other EOS games (Hunt, etc.)
            # keep working. Epic itself never shuts down, so WW3's own game-agnostic calls
            # (sdk config, jwks) resolve correctly against real Epic too when online.
            self._epic_passthrough(self.command, p)
            return None, None                       # signal: response already written
        lp = p.lower()
        if "/oauth/token" in lp:
            form = urllib.parse.parse_qs((self._body or b"").decode("latin1", "replace"))
            grant = (form.get("grant_type") or ["?"])[0]
            print(f"[EPIC] FORGED token grant={grant} -> 200 (our RS256, +10y)")
            return EPIC.forge_token_response(grant, form), 200
        if any(x in lp for x in ("jwks", ".well-known", "openid-configuration", "/discovery")):
            print(f"[EPIC] KEYS {p} -> our JWKS/discovery")
            if "openid-configuration" in lp or "/discovery" in lp:
                return EPIC.DISCOVERY, 200
            return EPIC.JWKS, 200
        canned = EPIC.canned_lookup(self.command, p)
        if canned is not None:
            print(f"[EPIC] canned {self.command} {p} -> 200 (real captured shape)")
            return canned, 200
        print(f"[EPIC] stub {self.command} {p} -> 200 {{}}")
        return {}, 200

    def route(self):
        p = self.path.split("?")[0]
        host = self.headers.get("Host", "").lower()
        if EPIC and "epicgames" in host:
            return self._epic_route(p)

        # Serve Battle Pass / shop CDN images from local cache (real bytes, not JSON)
        cached = _lookup_content_cache(self.path)
        if cached is not None:
            data, ctype = cached
            print(f"[<] GET {p}  -> content-cache ({len(data)} bytes, {ctype})")
            return data, 200, ctype

        # 0) AUTH-CRITICAL endpoints: mint fresh tokens (never replay stale/error ones)
        if p.endswith("/authenticate/fxgames"):
            tok = mint_jwt({"id": PLAYER_ID, "platformId": {"fxGames": FXGAMES_ID}, "type": "PlayerToken"})
            print(f"[<] POST /authenticate/fxgames -> minted PlayerToken")
            return {"result": tok}, 200
        if p.endswith("/events/getClientWebSocketUrl"):
            hub = mint_jwt({"id": PLAYER_ID, "platformId": {"fxGames": FXGAMES_ID},
                            "appType": "gameClient", "type": "Client", "remoteAddress": "127.0.0.1"})
            url = f"{HUB_WS}/client/{hub}"
            print(f"[<] GET /events/getClientWebSocketUrl -> {url[:48]}...")
            return {"result": url}, 200
        if p.endswith("/xmpp/serverConfig"):
            return {"result": {"serverAddress": "xmpp.prod.ww3.fxtools.gl",
                               "serverDomain": "xmpp.prod.ww3.fxtools.gl"}}, 200

        # --- M3: DEDICATED-SERVER-ROLE endpoints (the headless match server talks to us) ---
        if p.endswith("/events/getWebSocketUrl"):     # the SERVER's hub url (client uses getClientWebSocketUrl)
            hub = mint_jwt({"id": PLAYER_ID, "platformId": {"fxGames": FXGAMES_ID},
                            "appType": "gameServer", "type": "Server", "remoteAddress": "127.0.0.1"})
            url = f"{HUB_WS}/server/{hub}"
            print(f"[M3] GET /events/getWebSocketUrl -> {url[:46]}... (dedicated server hub)")
            return {"result": url}, 200
        if p.endswith("/server/register"):
            reg = (self._body or b"").decode("latin1", "replace")[:600]
            print(f"[M3] POST /server/register  BODY: {reg}")     # log to learn the exact shape
            return {"result": {"serverId": DS_SERVER_ID, "matchId": DS_MATCH_ID,
                               "registered": True, "serverGroup": "default"}}, 200
        if p.endswith(("/server/update", "/server/lock", "/server/lockRejoin", "/server/unregister")):
            print(f"[M3] {self.command} {p} -> ok")
            return {"result": True}, 200
        if p.endswith("/server/getSpawnersIps"):
            return {"result": []}, 200
        if "/AuthenticateUserTicket/" in p:            # DS validating a joining player
            pid = p.rstrip("/").split("/")[-1]
            print(f"[M3] AuthenticateUserTicket {pid} -> authenticated")
            return {"result": {"authenticated": True, "playerId": pid, "id": pid,
                               "platformId": {"fxGames": FXGAMES_ID}}}, 200
        if p.endswith("/matchmaking/lobby/getAll"):
            print(f"[M3] GET /matchmaking/lobby/getAll")
            return {"result": []}, 200
        if p.endswith("/playerChallenge/getRelevantForDedicatedServer"):
            # Hand the DS the same active challenge set the menu shows, so match play
            # can progress them (when a dedicated server reports events).
            ch_entry = REPLAY.get("GET /challenges", {})
            body = ch_entry.get("body") if isinstance(ch_entry, dict) else None
            result = body.get("result") if isinstance(body, dict) else None
            out = []
            if isinstance(result, dict):
                for bucket in ("dailyChallenges", "weeklyChallenges", "seasonChallenges"):
                    for c in result.get(bucket) or []:
                        if isinstance(c, dict) and c.get("active") and not c.get("completed"):
                            out.append(c)
            print(f"[M3] getRelevantForDedicatedServer -> {len(out)} active challenges")
            return {"result": out}, 200
        if "/DedicatedServer/matchSummary/" in p or "/ClearMatchSummaryFlag/" in p:
            # Apply whatever XP/events the DS posted (multiplied by entitlement tier).
            if PROG is not None:
                tier = _tier_for(self, p)
                mult = ENT.xp_multiplier(tier) if ENT else 1.0
                PROG.ingest_ds_payload(REPLAY, p, getattr(self, "_body", b""), xp_mult=mult)
            return {"result": True}, 200
        # Dedicated-server / meta writes that should mutate season or challenges
        # (exclude shop/BP buy+claim — those are handled below)
        _low_early = p.lower()
        if self.command in ("POST", "PUT") and not any(
            t in _low_early for t in ("/buy", "/claim", "/activate", "/exchange", "/purchase")
        ) and any(
            t in _low_early for t in (
                "/playerchallenge/", "/challenge/", "/season/", "/progression/",
                "/experience", "/xp", "/matchresult", "/matchresults",
            )
        ):
            if PROG is not None:
                tier = _tier_for(self, p)
                mult = ENT.xp_multiplier(tier) if ENT else 1.0
                PROG.ingest_ds_payload(REPLAY, p, getattr(self, "_body", b""), xp_mult=mult)
                print(f"[M3] progression ingest {self.command} {p} tier={tier} x{mult}")
                return {"result": {"ok": True}}, 200

        key = f"{self.command} {_norm(p)}"
        low = p.lower()

        # --- 5) Battle Pass / shop buy & claim: mutate season state, then ACK ---
        if self.command in ("POST", "PUT") and any(
            t in low for t in ("/buy", "/claim", "/activate", "/exchange", "/purchase")
        ):
            if "shop" in low or "season" in low or "battlepass" in low or "battle-pass" in low:
                kind = "premium"
                try:
                    req = json.loads(getattr(self, "_body", b"") or b"{}")
                    blob = json.dumps(req).lower() if isinstance(req, (dict, list)) else ""
                    if "normal" in blob or "85946530" in blob:
                        kind = "normal"
                except Exception:
                    req = {}
                if "claim" in low or "skip" in low or "tier" in low:
                    _apply_bp_claim_or_skip()
                else:
                    _apply_bp_purchase(kind)
                print(f"[<] {self.command} {p}  -> BP buy/claim ack")
                return {"result": {"__void__": "", "ok": True}}, 200

        # 1) serve the REAL captured response if we recorded this endpoint
        if key in REPLAY:
            entry = REPLAY[key]
            code = int(str(entry.get("status", "200")).split()[0])
            body = entry.get("body", {})
            # Entitlement overlays
            tier = _tier_for(self, p)
            if tier == "helper" and "inventory/get" in low:
                _ensure_helper_inventory()
                body = REPLAY[key].get("body", body)
            if "profileNew" in low and isinstance(body, dict) and isinstance(body.get("AccountInfo"), dict):
                # Keep profile season fields aligned with live season progression object
                seas_entry = REPLAY.get("GET /season/getSeason", {})
                seas = ((seas_entry.get("body") or {}).get("result") or {}) if isinstance(seas_entry, dict) else {}
                prog = seas.get("progression") if isinstance(seas, dict) else None
                if isinstance(prog, dict):
                    body = json.loads(json.dumps(body))  # shallow detach
                    body["AccountInfo"]["playerSeasonLevel"] = prog.get("level", 0)
                    body["AccountInfo"]["playerSeasonExperience"] = prog.get("experience", 0)
            print(f"[<] {self.command} {p}  -> replay ({entry.get('status')}) tier={tier}")
            return body, code
        # 2) fallbacks for anything not captured, shaped like the REAL responses.
        # The captured endpoints use exactly two conventions, so an uncaptured endpoint
        # should imitate whichever fits -- returning a bare {} matches neither and is the
        # most likely way an un-exercised menu screen breaks:
        #    collections      -> "result": []                (friends/getReceivedInvitations,
        #                                                     playerEffects/getBoosters, maps/getAll)
        #    void / ack calls -> "result": {"__void__": ""}   (PlayerStatistics,
        #                                                     inventory/markVisited, accountConfig)
        if p.endswith(("/friends/getAll", "/friends/getReceivedInvitations", "/friends/getSentInvitations")):
            return {"result": []}, 200
        if "datetime" in low or "/time" in low:
            return {"serverTimestamp": now_ms(), "timestamp": now_ms()}, 200

        COLLECTION = ("getall", "getactive", "getreceived", "getsent", "getlist", "/list",
                      "notifications", "challenges", "scores", "getscoresdata", "getboosters",
                      "leaderboard", "ranking", "invitations", "getitems", "history")
        VOID = ("/update", "/set", "/delete", "/remove", "/add", "/buy", "/claim", "/markvisited",
                "/accept", "/decline", "/report", "/ack", "/activate", "/exchange", "/consume")

        # VOID is checked FIRST: an action verb wins over the noun it acts on, so
        # /notifications/delete is an ack, not a collection.
        if self.command in ("POST", "PUT", "DELETE") or any(t in low for t in VOID):
            print(f"[<] {self.command} {p}  -> generic (void ack)")
            return {"result": {"__void__": ""}}, 200
        if any(t in low for t in COLLECTION):
            print(f"[<] {self.command} {p}  -> generic (collection -> [])")
            return {"result": []}, 200
        print(f"[<] {self.command} {p}  -> generic")
        return {"success": True, "status": "APPROVED", "serverTimestamp": now_ms(), "result": {}}, 200

    def _ws_hold(self):
        """Complete the WebSocket upgrade for Epic's notifications/presence channel and
        hold it open (reply to pings) so the SDK sees a live 'communication service' and
        stops the every-2-min 'lost connection' popup. Presence-only; no data required."""
        key = self.headers.get("Sec-WebSocket-Key", "")
        accept = _b64lib.b64encode(_hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        self.wfile.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
                          f"Connection: Upgrade\r\nSec-WebSocket-Accept: {accept}\r\n\r\n").encode())
        self.wfile.flush()
        print(f"[EPIC] notifications WS upgraded (101) + held open -> presence stays 'connected'")
        sock = self.connection
        try:
            sock.settimeout(600)
            while True:
                data = sock.recv(4096)
                if not data: break
                if len(data) >= 2 and (data[0] & 0x0F) == 0x8: break          # close frame
                if len(data) >= 2 and (data[0] & 0x0F) == 0x9: sock.sendall(b"\x8a\x00")  # ping -> pong
        except Exception:
            pass
        self.close_connection = True

    def _handle(self):
        if "websocket" in self.headers.get("Upgrade", "").lower():
            self._ws_hold(); return
        n = int(self.headers.get("Content-Length", 0) or 0)
        self._body = self.rfile.read(n) if n else b""   # keep body (Epic token grant needs it)
        routed = self.route()
        if routed is None:
            return
        if len(routed) == 2:
            obj, code = routed
            ctype = None
        else:
            obj, code, ctype = routed
        if obj is None and code is None:                # pass-through already wrote the response
            return
        self._send(obj, code, content_type=ctype)

    do_GET = _handle
    do_POST = _handle
    do_PUT = _handle
    do_DELETE = _handle

    def log_message(self, *a):
        return

def run(port, use_tls):
    gen_cert()
    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", port), Handler)
    scheme = "http"
    if use_tls:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(CERT, KEY)
        # SNI: present the CA-signed Epic cert for epicgames.dev, mock cert for ww3 hosts
        if EPIC and os.path.exists(EPIC_CERT) and os.path.exists(EPIC_KEY):
            epic_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            epic_ctx.load_cert_chain(EPIC_CERT, EPIC_KEY)
            def _sni(sock, name, _c):
                if name and name.lower().endswith("epicgames.dev"):
                    sock.context = epic_ctx
            ctx.sni_callback = _sni
            print("[*] SNI cert selection active (epic_cert for *.epicgames.dev)")
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
        scheme = "https"
    print(f"[*] WW3 REST mock on {scheme}://0.0.0.0:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    # usage: rest_server.py <port> <tls:0|1>
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 443
    tls = (sys.argv[2] == "1") if len(sys.argv) > 2 else True
    run(port, tls)
