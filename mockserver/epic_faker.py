#!/usr/bin/env python3
r"""
epic_faker.py -- BECOME Epic's EOS Auth (api.epicgames.dev) so offline login works
FOREVER, with a synthetic FXID token and no real Epic servers.

The offline crash was real Epic returning HTTP 401 at /auth/v1/oauth/token because
our synthetic FXID token isn't valid against the studio's IdP. We now own that host
(the EOS SDK trusts our CA -- proven by epic_probe). So instead of forwarding to real
Epic, we ANSWER:

  * POST /auth/v1/oauth/token  -> forged 200 with OUR-signed RS256 tokens (10y exp),
    mirroring the captured success shape (epic_ca/token_grants.json).
  * the JWKS / OIDC discovery    -> OUR RSA public key under Epic's own `kid`, so the
    SDK verifies our forged tokens' signatures against a key WE serve.
  * any other api.epicgames.dev path -> permissive 200 (logged, so we learn the set).

Keypair is generated once to epic_ca/forge_rsa_key.pem (kid matches Epic's token kid).
Run behind epic_faker.ps1 (installs CA, redirects api.epicgames.dev -> 127.0.0.1).
"""
import socket, ssl, threading, json, os, sys, time, datetime, base64, secrets, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
CERT = os.path.join(HERE, "epic_ca", "epic_cert.pem")
KEY  = os.path.join(HERE, "epic_ca", "epic_key.pem")
RSAK = os.path.join(HERE, "epic_ca", "forge_rsa_key.pem")
TMPL = os.path.join(HERE, "epic_ca", "token_grants.json")
LOG  = os.path.join(HERE, "epic_ca", "epic_faker.log")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 443

# Epic's own key id, taken from the captured token headers -- the SDK looks up the
# verification key by THIS kid, so our served JWKS must use the same string.
KID = "2022-06-14T06:17:57.047928700Z"
TEN_YEARS = 10 * 365 * 24 * 3600

C = dict(reset="\033[0m", grn="\033[92m", yel="\033[93m", red="\033[91m", cyn="\033[96m", bold="\033[1m", dim="\033[2m")
try:
    import ctypes; k = ctypes.windll.kernel32; k.SetConsoleMode(k.GetStdHandle(-11), 7)
except Exception: pass
def stamp(): return datetime.datetime.now().strftime("%H:%M:%S")
_lock = threading.Lock()
def logline(s):
    with _lock:
        open(LOG, "a", encoding="utf-8", errors="replace").write(f"[{stamp()}] {s}\n")

# ---------------------------------------------------------------- RSA key + JWT
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import jwt as pyjwt

def load_key():
    if os.path.exists(RSAK):
        return serialization.load_pem_private_key(open(RSAK, "rb").read(), password=None)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    open(RSAK, "wb").write(key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    print(f"{C['grn']}[*] generated forge RSA key -> {RSAK}{C['reset']}")
    return key

PRIV = load_key()
PRIV_PEM = PRIV.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
_pub = PRIV.public_key().public_numbers()
def _b64u(i):
    b = i.to_bytes((i.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
JWKS = {"keys": [{"kty": "RSA", "use": "sig", "alg": "RS256", "kid": KID,
                  "n": _b64u(_pub.n), "e": _b64u(_pub.e)}]}
DISCOVERY = {"issuer": "https://api.epicgames.dev/auth/v1/oauth",
             "jwks_uri": "https://api.epicgames.dev/auth/v1/oauth/jwks",
             "id_token_signing_alg_values_supported": ["RS256"],
             "response_types_supported": ["code", "token"],
             "subject_types_supported": ["public"],
             "token_endpoint": "https://api.epicgames.dev/auth/v1/oauth/token"}
TEMPLATES = json.load(open(TMPL, encoding="utf-8")) if os.path.exists(TMPL) else {}

# Canned real Epic responses (captured live): sdk config + connect product-user search.
# Empty {} broke Connect Login (EOS_UnrecognizedResponse); these are the real shapes.
import re as _re
CANNED_PATH = os.path.join(HERE, "epic_ca", "epic_canned.json")
CANNED = json.load(open(CANNED_PATH, encoding="utf-8")) if os.path.exists(CANNED_PATH) else {}
def _norm_epic(p):
    return _re.sub(r"/[0-9a-f]{16,}", "/{id}", p.split("?")[0])
def canned_lookup(method, path):
    return CANNED.get(f"{method} {_norm_epic(path)}")

def mint(payload):
    p = dict(payload); now = int(time.time())
    p["iat"] = now; p["exp"] = now + TEN_YEARS
    if "nbf" in p: p["nbf"] = now
    p["jti"] = secrets.token_hex(16)
    return pyjwt.encode(p, PRIV_PEM, algorithm="RS256", headers={"kid": KID, "typ": "JWT"})

def _decode_jwt_payload(tok):
    try: return json.loads(base64.urlsafe_b64decode(tok.split(".")[1] + "=="))
    except Exception: return {}

def forge_token_response(grant, req_form):
    """Return the JSON dict for POST /auth/v1/oauth/token, our-signed, 10y exp."""
    tmpl = TEMPLATES.get(grant) or TEMPLATES.get("external_auth") or {}
    now = int(time.time()); exp = now + TEN_YEARS
    iso = datetime.datetime.utcfromtimestamp(exp).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    nonce = (req_form.get("nonce") or [None])[0] or base64.urlsafe_b64encode(secrets.token_bytes(16)).rstrip(b"=").decode()
    out = {k: v for k, v in tmpl.items() if k not in ("access_token", "id_token")}
    out["expires_at"] = iso; out["expires_in"] = TEN_YEARS
    out.setdefault("token_type", "bearer")
    # rebuild access_token from the captured payload claims (our signature, fresh exp/nonce)
    at = dict(_decode_jwt_payload(tmpl.get("access_token", ".e30.")) )
    if not at:  # no template -> synthesize minimal claims
        at = {"iss": "eos", "sub": "100001", "aud": at.get("clientId", ""),
              "clientId": "xyza78913PNJAxLsnw1B5OGzaAYR4zPW", "env": "prod"}
    if "nonce" in at or grant == "external_auth": at["nonce"] = nonce
    out["access_token"] = mint(at)
    if "nonce" in out: out["nonce"] = nonce
    if tmpl.get("id_token"):
        idt = dict(_decode_jwt_payload(tmpl["id_token"]))
        out["id_token"] = mint(idt)
    return out

# ---------------------------------------------------------------- HTTP plumbing
class Buf:
    def __init__(s, sock): s.sock, s.buf = sock, b""
    def fill(s):
        c = s.sock.recv(65536)
        if not c: return False
        s.buf += c; return True
    def until(s, sep=b"\r\n\r\n"):
        while sep not in s.buf:
            if not s.fill(): return s.buf or None
        i = s.buf.find(sep) + len(sep); d, s.buf = s.buf[:i], s.buf[i:]; return d
    def n(s, k):
        while len(s.buf) < k:
            if not s.fill(): break
        d, s.buf = s.buf[:k], s.buf[k:]; return d

def parse(head):
    ls = head.split(b"\r\n"); rl = ls[0].decode("latin1", "replace"); h = {}
    for l in ls[1:]:
        if b":" in l: k, _, v = l.partition(b":"); h[k.decode("latin1").strip().lower()] = v.decode("latin1").strip()
    parts = (rl.split(" ") + ["", ""]); return parts[0], parts[1], h

def send_json(sock, obj, status="200 OK"):
    body = json.dumps(obj).encode()
    sock.sendall(f"HTTP/1.1 {status}\r\nContent-Type: application/json\r\n"
                 f"Content-Length: {len(body)}\r\nConnection: keep-alive\r\n\r\n".encode() + body)

def handle(cli, host):
    b = Buf(cli)
    try:
        while True:
            head = b.until(b"\r\n\r\n")
            if not head: break
            method, path, h = parse(head)
            body = b""
            cl = h.get("content-length")
            if cl:
                try: body = b.n(int(cl))
                except ValueError: pass
            lp = path.lower()
            if "/oauth/token" in lp:
                form = urllib.parse.parse_qs(body.decode("latin1", "replace"))
                grant = (form.get("grant_type") or ["?"])[0]
                resp = forge_token_response(grant, form)
                send_json(cli, resp)
                print(f"{C['grn']}{C['bold']}[FORGED] {host} {path}  grant={grant} -> 200 (our RS256, +10y){C['reset']}", flush=True)
                logline(f"FORGED token grant={grant} path={path}")
            elif any(x in lp for x in ("jwks", ".well-known", "openid-configuration", "/discovery")):
                if "openid-configuration" in lp or "/discovery" in lp:
                    send_json(cli, DISCOVERY)
                else:
                    send_json(cli, JWKS)
                print(f"{C['cyn']}[KEYS ] {host} {path} -> served our JWKS/discovery{C['reset']}", flush=True)
                logline(f"KEYS path={path}")
            else:
                # unknown epic endpoint: permissive success so the SDK keeps going; log it
                send_json(cli, {})
                print(f"{C['yel']}[stub ] {host} {method} {path} -> 200 {{}}{C['reset']}", flush=True)
                logline(f"STUB {method} {path}")
            if h.get("connection", "").lower() == "close": break
    except Exception as e:
        logline(f"handler error: {e}")
    finally:
        try: cli.close()
        except Exception: pass

def main():
    if not os.path.exists(CERT): sys.exit("epic_ca/epic_cert.pem missing -- generate the CA first.")
    print(f"{C['bold']}{C['grn']}  EPIC EOS-AUTH FAKER{C['reset']}  on :{PORT}   (forever-offline)")
    print(f"  we ARE api.epicgames.dev now: forging token grants + serving our JWKS (kid {KID[:10]}...).")
    print(f"  forge key: {RSAK}")
    print(f"  {C['yel']}launch the game offline; watch for [FORGED] and [KEYS] lines.{C['reset']}\n")
    open(LOG, "w").close()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", PORT)); srv.listen(64)
    while True:
        raw, _ = srv.accept()
        sni = {}
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(CERT, KEY)
        ctx.sni_callback = lambda s, name, c, _h=sni: _h.__setitem__("host", name)
        try:
            tls = ctx.wrap_socket(raw, server_side=True)
        except Exception:
            try: raw.close()
            except Exception: pass
            continue
        threading.Thread(target=handle, args=(tls, sni.get("host") or "?"), daemon=True).start()

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("\nfaker stopped.")
