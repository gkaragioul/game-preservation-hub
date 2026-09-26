#!/usr/bin/env python3
"""Spiral Warrior local HTTP/HTTPS proxy and endpoint interceptor.

Handles:
- HTTP requests: intercepted domains → mock responses; others → upstream proxy
- HTTPS CONNECT: intercepted domains → mitm with generated certs; others → tunnel
- Generates persistent local-CA-signed certificates for intercepted domains
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json, urllib.parse, urllib.request, urllib.error, os, time, uuid
import re
import secrets
import shutil
import ssl, socket, threading, struct, select
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "server"
sys.path.insert(0, str(SERVER_ROOT))
from app.protocol.area import AREA_RESPONSE_TEXT

ZIP = ROOT / 'research' / 'local_resource_server' / 'lbres.zip'
LOG = ROOT / 'research' / 'local_resource_server' / 'requests.log'
CERT_DIR = Path(os.environ.get(
    "SPIRAL_CERT_DIR",
    ROOT / 'research' / 'local_resource_server' / 'certs',
))

INTERCEPT_HOSTS = {
    'lxys-area.17m3.com', 'lxys-audit-area.17m3.com', 'lxys-test-area.17m3.com',
    'lxys1-client.17m3.com', 'cdnsgp-x3jl-release.17m3.com',
    'cdn-spinarena.17m3.com', 'gm.17m3.com',
    'upsapi.17m3.com', 'sdk-config.17m3.com', 'ups-config.17m3.com',
    'ups-sdk-error.17m3.com', 'ups-sdk-log.17m3.com', 'luoxuan.17m3.com',
    'sdk-login-cn.17m3.com', 'hsdk-login-cn.17m3.com', 'passport.17m3.com',
    'sdk-heartbeat.17m3.com', 'sdk-sec.17m3.com',
    'thinkingdata.17m3.com', 'ups-sdk.17m3.com', 'sdk.17m3.com',
    'sdk-package-update-config.17m3.com', 'sdk-login-cocooversea.17m3.com',
    'sdk-pay-coco4game.17m3.com', 'service.e-soul.net', 'upload.e-soul.net',
    'm3guo.com', 'ssl-download1-m3syfkb.m3guo.com',
    'rcdnaws.loveota.net', 'loveota.net', '17m3.com',
    'f3rpeggx.crcn.loveota.com', 'f3rpeggx.cscn.loveota.com',
    'crcn.loveota.com', 'cscn.loveota.com',
}

# Cache for generated SSL contexts. Certificates are still validated before
# cached contexts are reused.
_certs = {}
_cert_lock = threading.RLock()
_openssl_executable = None

_ROOT_KEY_NAME = "spiral-local-ca.key"
_ROOT_CERT_NAME = "spiral-local-ca.pem"
_ROOT_SUBJECT = "/C=GR/O=Spiral Warrior Local Offline/CN=Spiral Warrior Local Root CA"
_DNS_NAME = re.compile(
    r"(?=^.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$"
)


def _resolve_openssl() -> Path:
    """Resolve the single OpenSSL executable used by this process."""
    global _openssl_executable
    if _openssl_executable is not None:
        return _openssl_executable

    configured = os.environ.get("SPIRAL_OPENSSL")
    found = shutil.which("openssl")
    candidates = [
        Path(configured).expanduser() if configured else None,
        Path(found) if found else None,
        Path(r"C:\Program Files\Git\usr\bin\openssl.exe"),
        Path(r"C:\Program Files\Git\mingw64\bin\openssl.exe"),
    ]
    for candidate in candidates:
        if candidate and candidate.is_file() and os.access(candidate, os.X_OK):
            _openssl_executable = candidate.resolve()
            return _openssl_executable
    searched = ", ".join(str(item) for item in candidates if item)
    raise RuntimeError(
        "OpenSSL is required for the local TLS CA; set SPIRAL_OPENSSL to an "
        f"executable. Searched: {searched}"
    )


def _run_openssl(
    *arguments: str, input_text: str | None = None
) -> subprocess.CompletedProcess:
    executable = _resolve_openssl()
    completed = subprocess.run(
        [str(executable), *map(str, arguments)],
        input=input_text,
        text=True,
        capture_output=True,
    )
    if completed.returncode:
        diagnostic = completed.stderr.strip() or completed.stdout.strip() or "(no output)"
        raise RuntimeError(
            f"OpenSSL command failed with exit code {completed.returncode}: {diagnostic}"
        )
    return completed


def _openssl_ok(*arguments: str) -> bool:
    try:
        _run_openssl(*arguments)
        return True
    except (OSError, RuntimeError):
        return False


def _public_key(certificate_or_key: Path, *, certificate: bool) -> str | None:
    try:
        if certificate:
            result = _run_openssl(
                "x509", "-in", str(certificate_or_key), "-noout", "-pubkey"
            )
        else:
            result = _run_openssl(
                "pkey", "-in", str(certificate_or_key), "-pubout"
            )
        return "".join(result.stdout.split())
    except (OSError, RuntimeError):
        return None


def _root_paths() -> tuple[Path, Path]:
    return CERT_DIR / _ROOT_CERT_NAME, CERT_DIR / _ROOT_KEY_NAME


def _root_is_valid(certificate: Path, key: Path) -> bool:
    if not certificate.is_file() or not key.is_file():
        return False
    if not _openssl_ok("pkey", "-in", str(key), "-check", "-noout"):
        return False
    if _public_key(certificate, certificate=True) != _public_key(key, certificate=False):
        return False
    if not _openssl_ok(
        "x509", "-in", str(certificate), "-noout", "-checkend", str(365 * 86400)
    ):
        return False
    if not _openssl_ok("verify", "-CAfile", str(certificate), str(certificate)):
        return False
    try:
        details = _run_openssl(
            "x509", "-in", str(certificate), "-noout", "-text"
        ).stdout
        identity = _run_openssl(
            "x509",
            "-in",
            str(certificate),
            "-noout",
            "-subject",
            "-issuer",
            "-nameopt",
            "compat",
        ).stdout.splitlines()
    except (OSError, RuntimeError):
        return False
    subject = next((line[8:].strip() for line in identity if line.startswith("subject=")), None)
    issuer = next((line[7:].strip() for line in identity if line.startswith("issuer=")), None)
    return all(
        (
            subject == _ROOT_SUBJECT,
            issuer == _ROOT_SUBJECT,
            "Signature Algorithm: sha256WithRSAEncryption" in details,
            "Public-Key: (4096 bit)" in details,
            "X509v3 Basic Constraints: critical" in details,
            "CA:TRUE, pathlen:0" in details,
            "X509v3 Key Usage: critical" in details,
            "Certificate Sign, CRL Sign" in details,
        )
    )


def _publish_pair(
    temp_key: Path, temp_certificate: Path, key: Path, certificate: Path
):
    """Publish a validated pair while all readers are held behind `_cert_lock`."""
    os.replace(temp_key, key)
    os.replace(temp_certificate, certificate)


def _create_root(certificate: Path, key: Path):
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".spiral-ca-", dir=CERT_DIR) as temp_name:
        temp = Path(temp_name)
        temp_key = temp / _ROOT_KEY_NAME
        temp_certificate = temp / _ROOT_CERT_NAME
        _run_openssl(
            "req",
            "-x509",
            "-newkey",
            "rsa:4096",
            "-sha256",
            "-nodes",
            "-keyout",
            str(temp_key),
            "-out",
            str(temp_certificate),
            "-days",
            "3650",
            "-subj",
            _ROOT_SUBJECT,
            "-addext",
            "basicConstraints=critical,CA:TRUE,pathlen:0",
            "-addext",
            "keyUsage=critical,keyCertSign,cRLSign",
            "-addext",
            "subjectKeyIdentifier=hash",
            "-addext",
            "authorityKeyIdentifier=keyid:always",
        )
        if not _root_is_valid(temp_certificate, temp_key):
            raise RuntimeError("new local root CA failed validation")
        _publish_pair(temp_key, temp_certificate, key, certificate)
    _certs.clear()


def _certificate_fingerprint(certificate: Path) -> str:
    output = _run_openssl(
        "x509", "-in", str(certificate), "-noout", "-fingerprint", "-sha256"
    ).stdout.strip()
    if "=" not in output:
        raise RuntimeError("OpenSSL did not return a SHA-256 certificate fingerprint")
    normalized = output.split("=", 1)[1].replace(":", "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        raise RuntimeError(f"invalid SHA-256 certificate fingerprint: {normalized!r}")
    return normalized


def _android_hash(certificate: Path) -> str:
    value = _run_openssl(
        "x509", "-in", str(certificate), "-noout", "-subject_hash_old"
    ).stdout.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{8}", value):
        raise RuntimeError(f"invalid Android subject_hash_old value: {value!r}")
    return value


def prepare_ca() -> dict[str, str]:
    """Create or validate the persistent root and return public metadata."""
    with _cert_lock:
        CERT_DIR.mkdir(parents=True, exist_ok=True)
        certificate, key = _root_paths()
        if not _root_is_valid(certificate, key):
            _create_root(certificate, key)
        if not _root_is_valid(certificate, key):
            raise RuntimeError("local root CA is not valid after generation")
        return {
            "certificate": str(certificate.resolve()),
            "fingerprint": _certificate_fingerprint(certificate),
            "androidHash": _android_hash(certificate),
        }


def _leaf_paths(hostname: str) -> tuple[Path, Path]:
    if not _DNS_NAME.fullmatch(hostname):
        raise ValueError(f"invalid intercepted DNS hostname: {hostname!r}")
    return CERT_DIR / f"{hostname}.pem", CERT_DIR / f"{hostname}.key"


def _leaf_is_valid(hostname: str, certificate: Path, key: Path, root: Path) -> bool:
    if not certificate.is_file() or not key.is_file():
        return False
    if _public_key(certificate, certificate=True) != _public_key(key, certificate=False):
        return False
    if not _openssl_ok(
        "verify", "-purpose", "sslserver", "-CAfile", str(root), str(certificate)
    ):
        return False
    if not _openssl_ok(
        "x509", "-in", str(certificate), "-noout", "-checkend", str(30 * 86400)
    ):
        return False
    try:
        details = _run_openssl(
            "x509", "-in", str(certificate), "-noout", "-text"
        ).stdout
        san_output = _run_openssl(
            "x509", "-in", str(certificate), "-noout", "-ext", "subjectAltName"
        ).stdout
        leaf_issuer = _run_openssl(
            "x509",
            "-in",
            str(certificate),
            "-noout",
            "-issuer",
            "-nameopt",
            "RFC2253",
        ).stdout.strip().removeprefix("issuer=").strip()
        root_subject = _run_openssl(
            "x509",
            "-in",
            str(root),
            "-noout",
            "-subject",
            "-nameopt",
            "RFC2253",
        ).stdout.strip().removeprefix("subject=").strip()
    except (OSError, RuntimeError):
        return False
    dns_names = set(re.findall(r"DNS:([^,\s]+)", san_output))
    return all(
        (
            leaf_issuer == root_subject,
            dns_names == {hostname},
            "Signature Algorithm: sha256WithRSAEncryption" in details,
            "Public-Key: (2048 bit)" in details,
            "X509v3 Basic Constraints: critical" in details,
            "CA:FALSE" in details,
            "X509v3 Key Usage: critical" in details,
            "Digital Signature, Key Encipherment" in details,
            "TLS Web Server Authentication" in details,
        )
    )


def _create_leaf(
    hostname: str, certificate: Path, key: Path, root: Path, root_key: Path
):
    with tempfile.TemporaryDirectory(prefix=".spiral-leaf-", dir=CERT_DIR) as temp_name:
        temp = Path(temp_name)
        temp_key = temp / key.name
        temp_certificate = temp / certificate.name
        request = temp / f"{hostname}.csr"
        extensions = temp / "leaf.ext"
        extensions.write_text(
            "[v3_leaf]\n"
            "basicConstraints=critical,CA:FALSE\n"
            "keyUsage=critical,digitalSignature,keyEncipherment\n"
            "extendedKeyUsage=serverAuth\n"
            f"subjectAltName=DNS:{hostname}\n"
            "subjectKeyIdentifier=hash\n"
            "authorityKeyIdentifier=keyid,issuer\n",
            encoding="ascii",
        )
        _run_openssl(
            "req",
            "-new",
            "-newkey",
            "rsa:2048",
            "-sha256",
            "-nodes",
            "-keyout",
            str(temp_key),
            "-out",
            str(request),
            "-subj",
            f"/C=GR/O=Spiral Warrior Local Offline/CN={hostname}",
        )
        _run_openssl(
            "x509",
            "-req",
            "-in",
            str(request),
            "-CA",
            str(root),
            "-CAkey",
            str(root_key),
            "-set_serial",
            f"0x{secrets.token_hex(16)}",
            "-out",
            str(temp_certificate),
            "-days",
            "825",
            "-sha256",
            "-extfile",
            str(extensions),
            "-extensions",
            "v3_leaf",
        )
        if not _leaf_is_valid(hostname, temp_certificate, temp_key, root):
            raise RuntimeError(f"new TLS leaf for {hostname} failed validation")
        _publish_pair(temp_key, temp_certificate, key, certificate)


def _ensure_leaf(hostname: str) -> tuple[Path, Path]:
    """Return a currently valid CA-signed leaf and key for *hostname*."""
    with _cert_lock:
        prepare_ca()
        root, root_key = _root_paths()
        certificate, key = _leaf_paths(hostname)
        if not _leaf_is_valid(hostname, certificate, key, root):
            _certs.pop(hostname, None)
            _create_leaf(hostname, certificate, key, root, root_key)
        if not _leaf_is_valid(hostname, certificate, key, root):
            raise RuntimeError(f"TLS leaf for {hostname} is invalid after generation")
        return certificate, key


def _log(msg):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open('a', encoding='utf-8') as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")

def _get_cert_for_host(hostname):
    """Generate or return a cached context for a valid CA-signed leaf."""
    with _cert_lock:
        certfile, keyfile = _ensure_leaf(hostname)
        if hostname not in _certs:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(str(certfile), str(keyfile))
            _certs[hostname] = ctx
        return _certs[hostname]

def _json_response(handler, body, status=200, send_body=True):
    data = json.dumps(body, ensure_ascii=False).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(data)))
    handler.end_headers()
    if send_body:
        handler.wfile.write(data)

def _bytes_response(handler, data: bytes, content_type: str, status: int = 200, send_body=True):
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    if send_body:
        handler.wfile.write(data)

def _area_payload() -> bytes:
    return AREA_RESPONSE_TEXT.encode("ascii")

def _html_response(handler, html, status=200, send_body=True):
    data = html.encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'text/html; charset=utf-8')
    handler.send_header('Content-Length', str(len(data)))
    handler.end_headers()
    if send_body:
        handler.wfile.write(data)


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        _log(f"HTTP {self.client_address[0]} {fmt % args}")

    def do_CONNECT(self):
        """Handle HTTPS CONNECT tunneling for intercepted domains."""
        host_port = self.path.split(':')
        hostname = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 443
        _log(f"CONNECT {hostname}:{port}")

        if hostname in INTERCEPT_HOSTS:
            # Send 200 directly to raw socket (bypass BaseHTTPRequestHandler buffering)
            resp = b'HTTP/1.1 200 Connection Established\r\n\r\n'
            self.connection.sendall(resp)
            # Wrap client socket with self-signed cert for MITM
            try:
                ctx = _get_cert_for_host(hostname)
                client_ssl = ctx.wrap_socket(self.connection, server_side=True)
                _log(f"CONNECT_SSL_OK {hostname}")
                # Now handle HTTPS requests on this SSL socket
                self._handle_https_intercepted(client_ssl, hostname)
                client_ssl.close()
            except Exception as e:
                _log(f"CONNECT_ERROR {hostname} {e!r}")
        else:
            if os.environ.get("OFFLINE_MODE", "1") == "1":
                self.send_response(502)
                self.send_header("Connection", "close")
                self.send_header("Content-Length", "0")
                self.end_headers()
                self.close_connection = True
                return
            # Forward tunnel to upstream
            self._tunnel_to_upstream(hostname, port)

    def _handle_https_intercepted(self, ssl_sock, hostname):
        """Handle decrypted HTTPS requests on intercepted domain."""
        try:
            while True:
                # Read HTTP request from SSL socket
                data = b''
                while b'\r\n\r\n' not in data:
                    chunk = ssl_sock.recv(4096)
                    if not chunk:
                        return
                    data += chunk
                header_end = data.index(b'\r\n\r\n') + 4
                headers_raw = data[:header_end].decode('utf-8', errors='replace')
                body_bytes = data[header_end:]

                first_line = headers_raw.split('\r\n')[0]
                parts = first_line.split(' ')
                method = parts[0] if parts else 'GET'
                path = parts[1] if len(parts) > 1 else '/'
                http_ver = parts[2] if len(parts) > 2 else 'HTTP/1.1'

                # Parse headers
                hdrs = {}
                for line in headers_raw.split('\r\n')[1:]:
                    if ':' in line:
                        k, v = line.split(':', 1)
                        hdrs[k.strip().lower()] = v.strip()

                content_length = int(hdrs.get('content-length', 0))
                while len(body_bytes) < content_length:
                    chunk = ssl_sock.recv(4096)
                    if not chunk:
                        break
                    body_bytes += chunk

                _log(f"HTTPS {hostname} {method} {path}")
                self._serve_intercepted(ssl_sock, hostname, method, path, hdrs, body_bytes)
        except (ssl.SSLError, ConnectionResetError, BrokenPipeError, OSError) as e:
            _log(f"HTTPS_DISCONNECT {hostname} {e!r}")

    def _serve_intercepted(self, sock, hostname, method, path, headers, body):
        """Serve a mock response for an intercepted HTTPS request."""
        query = ''
        if '?' in path:
            path_base, query = path.split('?', 1)
        else:
            path_base = path
        # Build a fake handler-like response
        response = self._build_response(hostname, method, path_base, query, headers, body)
        sock.sendall(response)

    def _build_response(self, hostname, method, path, query, headers, body_bytes):
        """Build raw HTTP response bytes for intercepted request."""
        status = 200
        resp_headers = {'Content-Type': 'application/json; charset=utf-8'}
        resp_body = b''

        if hostname in {'upsapi.17m3.com', 'ups-sdk-error.17m3.com', 'ups-sdk-log.17m3.com',
                        'sdk-heartbeat.17m3.com', 'sdk-sec.17m3.com'}:
            resp_body = json.dumps({'ok': True, 'code': 0, 'message': 'ok'}).encode()
        elif hostname == 'ups-config.17m3.com':
            resp_body = json.dumps({'code': 0, 'data': {'switch': 0, 'abtest': {}}}).encode()
        elif hostname == 'sdk-config.17m3.com':
            if '/config.json' in path:
                resp_body = json.dumps({
                    'code': 0, 'data': {
                        'autoLogin': True, 'guestLogin': True, 'loginType': 1,
                        'showAgreement': False, 'showLoginDialog': False,
                        'platform': '9game', 'appId': '1280858451',
                        'packageName': 'com.dianhun.lxys.aligames',
                    }
                }).encode()
            elif '/agreement.json' in path:
                resp_body = json.dumps({
                    'code': 0, 'data': {
                        'privacyUrl': '', 'userAgreementUrl': '',
                        'showPrivacy': False, 'showUserAgreement': False,
                        'privacyContent': '本地离线模式',
                        'userAgreementContent': '本地离线模式',
                    }
                }).encode()
            else:
                resp_body = json.dumps({'code': 0, 'data': {}}).encode()
        elif hostname == 'luoxuan.17m3.com':
            resp_headers['Content-Type'] = 'text/html; charset=utf-8'
            resp_body = '<html><body style="background:#1a1a2e;color:white;text-align:center;padding-top:200px;font-size:24px;"><p>螺旋勇士 - 本地离线模式</p><p>隐私协议已本地接受</p></body></html>'.encode()
        elif hostname in {'sdk-login-cn.17m3.com', 'hsdk-login-cn.17m3.com'}:
            resp_body = self._build_login_response(path)
        elif hostname == 'passport.17m3.com':
            resp_body = json.dumps({
                'code': 0, 'result': 0, 'msg': 'ok',
                'uid': 'local_offline_001',
                'token': f'local-token-{uuid.uuid4().hex[:16]}',
                'userName': '本地玩家', 'account': 'local_offline_001',
            }).encode()
        elif path.rstrip('/') == '/area/listV2':
            resp_body = _area_payload()
            resp_headers['Content-Type'] = 'text/plain; charset=US-ASCII'
        else:
            resp_body = json.dumps({'ok': True, 'code': 0, 'message': 'ok'}).encode()

        resp_headers['Content-Length'] = str(len(resp_body))
        resp_headers['Connection'] = 'keep-alive'

        raw = f'HTTP/1.1 {status} OK\r\n'
        for k, v in resp_headers.items():
            raw += f'{k}: {v}\r\n'
        raw += '\r\n'
        return raw.encode() + (b'' if method.upper() == 'HEAD' else resp_body)

    def _build_login_response(self, path):
        if '/Action_UserLogin.aspx' in path:
            return json.dumps({
                'code': 0, 'result': 0, 'msg': '登录成功',
                'uid': 'local_offline_001', 'userName': '本地玩家',
                'account': 'local_offline_001',
                'token': f'local-token-{uuid.uuid4().hex[:16]}',
                'channel': 'uc', 'channelUid': 'local_uc_001',
                'sessionId': f'local-session-{uuid.uuid4().hex[:8]}',
                'isFirstLogin': False,
            }).encode()
        elif '/AjaxQuickLoginSDK.ashx' in path:
            return json.dumps({
                'code': 0, 'result': 0, 'msg': '游客登录成功',
                'uid': 'local_guest_001', 'userName': '本地游客',
                'account': 'local_guest_001',
                'token': f'guest-token-{uuid.uuid4().hex[:16]}',
                'channel': 'uc', 'isGuest': True,
            }).encode()
        elif '/sdk2/index.html' in path:
            return '<html><body style="background:#1a1a2e;color:white;text-align:center;padding-top:100px;"><h2>螺旋勇士</h2><p>本地离线登录</p><p style="color:#4CAF50;font-size:36px;">✓ 已登录</p></body></html>'.encode()
        return json.dumps({'code': 0, 'result': 0, 'msg': 'ok'}).encode()

    def _tunnel_to_upstream(self, hostname, port):
        """Tunnel HTTPS traffic to upstream server."""
        try:
            upstream = socket.create_connection((hostname, port), timeout=10)
            # Send 200 directly to raw socket
            self.connection.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            client = self.connection
            client.setblocking(False)
            upstream.setblocking(False)
            sockets = [client, upstream]
            while True:
                readable, _, exceptional = select.select(sockets, [], sockets, 30)
                if exceptional:
                    break
                for s in readable:
                    data = s.recv(65536)
                    if not data:
                        return
                    target = upstream if s is client else client
                    target.sendall(data)
        except Exception as e:
            _log(f"TUNNEL_ERROR {hostname}:{port} {e!r}")
        finally:
            try: upstream.close()
            except: pass

    def do_HEAD(self):
        self._handle(send_body=False)

    def do_GET(self):
        self._handle(send_body=True)

    def do_POST(self):
        content_len = int(self.headers.get('Content-Length', 0))
        self._post_data = self.rfile.read(content_len) if content_len > 0 else b''
        self._handle(send_body=True)

    def _handle(self, send_body=True):
        _log(f"{self.command} {self.path} Host={self.headers.get('Host','')}")
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path if parsed.scheme else self.path.split('?',1)[0]
        host = parsed.netloc or self.headers.get('Host', '')
        if path == "/__health":
            _bytes_response(
                self,
                b'{"ok":true,"service":"spiral-edge"}',
                "application/json",
                send_body=send_body,
            )
            return
        if self._handle_local_game_api(host, path, parsed.query, send_body):
            return
        if path.endswith('/lbres.zip'):
            self._serve_zip(send_body)
            return
        if path.endswith('/getresdomain.php'):
            body = b'<uinfo domain="http://rcdnaws.loveota.net/" domainbak="http://rcdnaws.loveota.net/" />'
            self.send_response(200)
            self.send_header('Content-Type','text/xml; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            if send_body: self.wfile.write(body)
            return
        # Android sends 10.0.2.2 traffic to the configured proxy, so the edge
        # relays the emulator's host alias to the local gateway.
        if host.startswith('10.0.2.2:') or host == '10.0.2.2':
            local_host = host.replace('10.0.2.2', '127.0.0.1')
            local_target = f'{path}?{parsed.query}' if parsed.query else path
            local_url = f'http://{local_host}{local_target}'
            _log(f"GATEWAY_PROXY {self.path} -> {local_url}")
            try:
                post_data = self._post_data if self.command == 'POST' else None
                req = urllib.request.Request(local_url, data=post_data, method=self.command)
                for k, v in self.headers.items():
                    if k.lower() not in {'connection', 'proxy-connection', 'host', 'content-length', 'transfer-encoding'}:
                        req.add_header(k, v)
                with urllib.request.urlopen(req, timeout=20) as resp:
                    body = resp.read()
                    self.send_response(resp.status)
                    for k, v in resp.headers.items():
                        if k.lower() not in {'transfer-encoding', 'connection', 'content-length'}:
                            self.send_header(k, v)
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    if send_body: self.wfile.write(body)
            except Exception as exc:
                _log(f"GATEWAY_ERROR {local_url} {exc!r}")
                _json_response(self, {'ok': False, 'message': f'gateway proxy error: {exc}'}, status=502, send_body=send_body)
            return
        # Direct (origin-form) requests to the edge listener answer discovery
        # for operators and health probes. Absolute-form proxy requests stay
        # subject to the intercept list and the offline denial below.
        if not parsed.scheme and path.rstrip('/') == '/area/listV2':
            _bytes_response(self, _area_payload(), 'text/plain; charset=US-ASCII', send_body=send_body)
            return
        if os.environ.get("OFFLINE_MODE", "1") == "1":
            _json_response(
                self,
                {"ok": False, "message": "public upstream disabled in offline mode"},
                status=502,
                send_body=send_body,
            )
            return
        self._forward_upstream(send_body)

    def _handle_local_game_api(self, host, path, query='', send_body=True):
        host = host.split(':', 1)[0].lower()
        if host not in INTERCEPT_HOSTS:
            return False

        if host in {'upsapi.17m3.com', 'ups-sdk-error.17m3.com', 'ups-sdk-log.17m3.com',
                    'sdk-heartbeat.17m3.com', 'sdk-sec.17m3.com'}:
            _json_response(self, {'ok': True, 'code': 0, 'message': 'ok'}, send_body=send_body); return True
        if host == 'ups-config.17m3.com':
            _json_response(self, {'code': 0, 'data': {'switch': 0, 'abtest': {}}}, send_body=send_body); return True
        if host == 'sdk-config.17m3.com':
            if '/config.json' in path:
                _json_response(self, {
                    'code': 0, 'data': {
                        'autoLogin': True, 'guestLogin': True, 'loginType': 1,
                        'showAgreement': False, 'showLoginDialog': False,
                        'platform': '9game', 'appId': '1280858451',
                        'packageName': 'com.dianhun.lxys.aligames',
                    }}, send_body=send_body)
            elif '/agreement.json' in path:
                _json_response(self, {
                    'code': 0, 'data': {
                        'privacyUrl': '', 'userAgreementUrl': '',
                        'showPrivacy': False, 'showUserAgreement': False,
                        'privacyContent': '本地离线模式', 'userAgreementContent': '本地离线模式',
                    }}, send_body=send_body)
            else:
                _json_response(self, {'code': 0, 'data': {}}, send_body=send_body)
            return True
        if host == 'luoxuan.17m3.com':
            _html_response(self, '<html><body style="background:#1a1a2e;color:white;text-align:center;padding-top:200px;font-size:24px;"><p>螺旋勇士 - 本地离线模式</p><p>隐私协议已本地接受</p></body></html>', send_body=send_body)
            return True
        if host in {'sdk-login-cn.17m3.com', 'hsdk-login-cn.17m3.com'}:
            return self._handle_login_http(host, path, query, send_body)
        if host == 'passport.17m3.com':
            _json_response(self, {
                'code': 0, 'result': 0, 'msg': 'ok', 'uid': 'local_offline_001',
                'token': f'local-token-{uuid.uuid4().hex[:16]}',
                'userName': '本地玩家', 'account': 'local_offline_001'}, send_body=send_body)
            return True
        if path.rstrip('/') == '/area/listV2':
            _bytes_response(
                self,
                _area_payload(),
                'text/plain; charset=US-ASCII',
                send_body=send_body,
            )
            return True
        if '/chksdkupdate.php' in path:
            _json_response(self, {'code': 0, 'data': {'switch': 0, 'mustver': 280004, 'descr': ''}}, send_body=send_body)
            return True
        _json_response(self, {'ok': True, 'code': 0, 'message': 'ok'}, send_body=send_body); return True

    def _handle_login_http(self, host, path, query, send_body=True):
        if '/Action_UserLogin.aspx' in path:
            _json_response(self, {
                'code': 0, 'result': 0, 'msg': '登录成功',
                'uid': 'local_offline_001', 'userName': '本地玩家',
                'account': 'local_offline_001',
                'token': f'local-token-{uuid.uuid4().hex[:16]}',
                'channel': 'uc', 'channelUid': 'local_uc_001',
                'sessionId': f'local-session-{uuid.uuid4().hex[:8]}',
                'isFirstLogin': False}, send_body=send_body)
        elif '/AjaxQuickLoginSDK.ashx' in path:
            _json_response(self, {
                'code': 0, 'result': 0, 'msg': '游客登录成功',
                'uid': 'local_guest_001', 'userName': '本地游客',
                'account': 'local_guest_001',
                'token': f'guest-token-{uuid.uuid4().hex[:16]}',
                'channel': 'uc', 'isGuest': True}, send_body=send_body)
        elif '/sdk2/index.html' in path:
            _html_response(self, '<html><body style="background:#1a1a2e;color:white;text-align:center;padding-top:100px;"><h2>螺旋勇士</h2><p>本地离线登录</p></body></html>', send_body=send_body)
        else:
            _json_response(self, {'code': 0, 'result': 0, 'msg': 'ok'}, send_body=send_body)
        return True

    def _forward_upstream(self, send_body=True):
        url = self.path
        if not urllib.parse.urlparse(url).scheme:
            host = self.headers.get('Host')
            url = f'http://{host}{self.path}'
        try:
            connection_tokens = {
                token.strip().lower()
                for value in self.headers.get_all("Connection", [])
                for token in value.split(",")
            }
            hop_by_hop = {
                "connection",
                "keep-alive",
                "proxy-authenticate",
                "proxy-authorization",
                "proxy-connection",
                "te",
                "trailer",
                "transfer-encoding",
                "upgrade",
            } | connection_tokens
            headers = {
                name: value
                for name, value in self.headers.items()
                if name.lower() not in hop_by_hop
            }
            post_data = self._post_data if self.command == "POST" else None
            req = urllib.request.Request(
                url,
                data=post_data,
                headers=headers,
                method=self.command,
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read()
                upstream_content_length = resp.headers.get("Content-Length")
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() in {'transfer-encoding', 'connection', 'content-length'}: continue
                    self.send_header(k, v)
                content_length = (
                    upstream_content_length
                    if not send_body and upstream_content_length is not None
                    else str(len(body))
                )
                self.send_header('Content-Length', content_length)
                self.end_headers()
                if send_body: self.wfile.write(body)
        except Exception as exc:
            _log(f"UPSTREAM_ERROR {url} {exc!r}")
            body = f'upstream error: {exc}\n'.encode('utf-8', 'replace')
            self.send_response(502)
            self.send_header('Content-Type','text/plain')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            if send_body: self.wfile.write(body)

    def _serve_zip(self, send_body=True):
        size = ZIP.stat().st_size
        range_header = self.headers.get('Range')
        start, end = 0, size - 1
        status = 200
        if range_header and range_header.startswith('bytes='):
            spec = range_header.split('=',1)[1].split(',',1)[0]
            a,b = spec.split('-',1)
            start = int(a) if a else 0
            end = min(int(b) if b else size - 1, size - 1)
            status = 206
        if start > end or start >= size:
            self.send_response(416)
            self.send_header('Content-Range', f'bytes */{size}')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        length = end - start + 1
        self.send_response(status)
        self.send_header('Content-Type','application/zip')
        self.send_header('Accept-Ranges','bytes')
        self.send_header('Content-Length', str(length))
        if status == 206:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()
        if send_body:
            with ZIP.open('rb') as f:
                f.seek(start)
                remaining = length
                while remaining:
                    chunk = f.read(min(1024*1024, remaining))
                    if not chunk: break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)

class ThreadingHTTPServerMT(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

def main():
    if "--prepare-ca" in sys.argv[1:]:
        if sys.argv[1:] != ["--prepare-ca"]:
            print("--prepare-ca does not accept additional arguments", file=sys.stderr)
            return 2
        try:
            metadata = prepare_ca()
        except Exception as exc:
            print(f"prepare CA failed: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(metadata, separators=(",", ":"), sort_keys=False))
        return 0

    try:
        prepare_ca()
    except Exception as exc:
        print(f"prepare CA failed: {exc}", file=sys.stderr)
        return 1
    port = int(os.environ.get('PORT', '8888'))
    _log(f"START proxy on 0.0.0.0:{port} intercepting {len(INTERCEPT_HOSTS)} hosts")
    print(f'Serving Spiral Warrior HTTP/HTTPS proxy on 0.0.0.0:{port}')
    print(f'Intercepted hosts: {", ".join(sorted(INTERCEPT_HOSTS))}')
    ThreadingHTTPServerMT(('0.0.0.0', port), Handler).serve_forever()
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
