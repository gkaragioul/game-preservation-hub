import http.client
import importlib.util
import hashlib
import json
import socket
import subprocess
import threading
from http.server import BaseHTTPRequestHandler
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("edge", ROOT / "tools" / "serve_lbres_proxy.py")
edge = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(edge)


def request(server, method: str, target: str, headers=None, body=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        connection.request(method, target, body=body, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def raw_request(server, payload: bytes) -> bytes:
    connection = socket.create_connection(("127.0.0.1", server.server_port), timeout=3)
    try:
        connection.sendall(payload)
        chunks = []
        while chunk := connection.recv(4096):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        connection.close()


def split_response(response: bytes):
    head, body = response.split(b"\r\n\r\n", 1)
    lines = head.decode("iso-8859-1").split("\r\n")
    headers = {
        name.strip().lower(): value.strip()
        for name, value in (line.split(":", 1) for line in lines[1:])
    }
    return lines[0], headers, body


def test_proxy_health_area_and_offline_denial(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(edge, "LOG", tmp_path / "requests.log")
    monkeypatch.setenv("OFFLINE_MODE", "1")
    server = edge.ThreadingHTTPServerMT(("127.0.0.1", 0), edge.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, _, body = request(server, "GET", "/__health")
        assert (status, body) == (200, b'{"ok":true,"service":"spiral-edge"}')

        status, headers, body = request(
            server,
            "GET",
            "http://lxys-area.17m3.com/area/listV2?clientType=7",
        )
        assert status == 200
        assert headers["Content-Type"] == "text/plain; charset=US-ASCII"
        assert body == b"CMgBEgJvaxgHIh4IARIWaHR0cDovLzEwLjAuMi4yOjIzMTAxLxgCIAI="

        status, _, _ = request(server, "GET", "http://example.com/")
        assert status == 502
    finally:
        server.shutdown()
        server.server_close()


def serve(server) -> threading.Thread:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


def test_area_route_is_served_on_the_edge_listener(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(edge, "LOG", tmp_path / "requests.log")
    monkeypatch.setenv("OFFLINE_MODE", "1")
    server = edge.ThreadingHTTPServerMT(("127.0.0.1", 0), edge.Handler)
    serve(server)
    try:
        status, headers, body = request(server, "GET", "/area/listV2?plt=1&ver=1.0.348")
        assert status == 200
        assert headers["Content-Type"] == "text/plain; charset=US-ASCII"
        assert body == b"CMgBEgJvaxgHIh4IARIWaHR0cDovLzEwLjAuMi4yOjIzMTAxLxgCIAI="
    finally:
        server.shutdown()
        server.server_close()


def test_intercepted_sdk_update_reports_no_pending_update(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(edge, "LOG", tmp_path / "requests.log")
    monkeypatch.setenv("OFFLINE_MODE", "1")
    server = edge.ThreadingHTTPServerMT(("127.0.0.1", 0), edge.Handler)
    serve(server)
    try:
        status, _, body = request(
            server,
            "GET",
            "http://f3rpeggx.crcn.loveota.com/chksdkupdate.php?chid=70236&sdkver=280004",
        )
        assert status == 200
        payload = json.loads(body)
        assert payload["code"] == 0
        assert payload["data"]["switch"] == 0
    finally:
        server.shutdown()
        server.server_close()


def test_public_paths_never_bypass_offline_denial(monkeypatch, tmp_path: Path):
    """Game-shaped paths must not be answered for non-intercepted hosts.

    Serving these before the offline check let any upstream host collect a
    fabricated success body, which is how the SDK received JSON where it
    expected XML.
    """
    monkeypatch.setattr(edge, "LOG", tmp_path / "requests.log")
    monkeypatch.setenv("OFFLINE_MODE", "1")
    server = edge.ThreadingHTTPServerMT(("127.0.0.1", 0), edge.Handler)
    serve(server)
    try:
        for target in (
            "http://example.com/x3-hd/remote-assets/project.manifest",
            "http://example.com/x3-hd/remote-assets/version.manifest",
            "http://example.com/chksdkupdate.php?chid=70236",
            "http://example.com/area/listV2?plt=1",
        ):
            status, _, _ = request(server, "GET", target)
            assert status == 502, target
    finally:
        server.shutdown()
        server.server_close()


def test_gateway_alias_is_forwarded_with_query_to_the_local_gateway(
    monkeypatch, tmp_path: Path
):
    """The emulator reaches the gateway through the explicit proxy.

    Android sends 10.0.2.2 traffic to the configured proxy, so the edge has to
    relay it to the host loopback gateway with the query string intact.
    """
    seen = []

    class GatewayStub(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            seen.append(self.path)
            body = b"local-logic-token"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    gateway = edge.ThreadingHTTPServerMT(("127.0.0.1", 0), GatewayStub)
    serve(gateway)

    monkeypatch.setattr(edge, "LOG", tmp_path / "requests.log")
    monkeypatch.setenv("OFFLINE_MODE", "1")
    server = edge.ThreadingHTTPServerMT(("127.0.0.1", 0), edge.Handler)
    serve(server)
    try:
        status, _, body = request(
            server,
            "GET",
            f"http://10.0.2.2:{gateway.server_port}/auth/es?account=local",
        )
        assert (status, body) == (200, b"local-logic-token")
        assert seen == ["/auth/es?account=local"]
    finally:
        server.shutdown()
        server.server_close()
        gateway.shutdown()
        gateway.server_close()


def test_connect_public_host_is_denied_by_default(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(edge, "LOG", tmp_path / "requests.log")
    monkeypatch.delenv("OFFLINE_MODE", raising=False)
    server = edge.ThreadingHTTPServerMT(("127.0.0.1", 0), edge.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    connection.connect()
    upstream_calls = []

    def capture_upstream(address, timeout):
        upstream_calls.append((address, timeout))
        upstream, peer = socket.socketpair()
        peer.close()
        return upstream

    monkeypatch.setattr(edge.socket, "create_connection", capture_upstream)
    try:
        connection.request("CONNECT", "example.com:443")
        response = connection.getresponse()
        assert response.status == 502
        assert response.getheader("Connection") == "close"
        assert response.read() == b""
        assert upstream_calls == []
    finally:
        connection.close()
        server.shutdown()
        server.server_close()


def test_health_head_does_not_corrupt_persistent_connection(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(edge, "LOG", tmp_path / "requests.log")
    server = edge.ThreadingHTTPServerMT(("127.0.0.1", 0), edge.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        connection.request("HEAD", "/__health")
        response = connection.getresponse()
        assert response.status == 200
        assert response.getheader("Content-Length") == "35"
        assert response.read() == b""

        connection.request("GET", "/__health")
        response = connection.getresponse()
        assert response.status == 200
        assert response.read() == b'{"ok":true,"service":"spiral-edge"}'
    finally:
        connection.close()
        server.shutdown()
        server.server_close()


def test_area_head_keeps_get_length_and_writes_no_body(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(edge, "LOG", tmp_path / "requests.log")
    server = edge.ThreadingHTTPServerMT(("127.0.0.1", 0), edge.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        response = raw_request(
            server,
            (
                b"HEAD http://lxys-area.17m3.com/area/listV2?clientType=7 HTTP/1.1\r\n"
                b"Host: lxys-area.17m3.com\r\n"
                b"Connection: close\r\n\r\n"
            ),
        )
        status, headers, body = split_response(response)
        assert status == "HTTP/1.1 200 OK"
        assert headers["content-type"] == "text/plain; charset=US-ASCII"
        assert headers["content-length"] == "56"
        assert body == b""
    finally:
        server.shutdown()
        server.server_close()


def test_mitm_area_head_keeps_length_and_writes_no_body():
    handler = edge.Handler.__new__(edge.Handler)
    response = handler._build_response(
        "lxys-area.17m3.com",
        "HEAD",
        "/area/listV2",
        "clientType=7",
        {},
        b"",
    )
    status, headers, body = split_response(response)
    assert status == "HTTP/1.1 200 OK"
    assert headers["content-type"] == "text/plain; charset=US-ASCII"
    assert headers["content-length"] == "56"
    assert body == b""


def test_online_post_preserves_method_body_and_end_to_end_headers(monkeypatch, tmp_path: Path):
    captured = []

    class CaptureHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            pass

        def capture(self):
            content_length = int(self.headers.get("Content-Length", 0))
            captured.append(
                {
                    "method": self.command,
                    "body": self.rfile.read(content_length),
                    "headers": {name.lower(): value for name, value in self.headers.items()},
                }
            )
            body = b"captured"
            self.send_response(201)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = capture
        do_POST = capture

    capture_server = edge.ThreadingHTTPServerMT(("127.0.0.1", 0), CaptureHandler)
    capture_thread = threading.Thread(target=capture_server.serve_forever, daemon=True)
    capture_thread.start()

    monkeypatch.setattr(edge, "LOG", tmp_path / "requests.log")
    monkeypatch.setenv("OFFLINE_MODE", "0")
    proxy_server = edge.ThreadingHTTPServerMT(("127.0.0.1", 0), edge.Handler)
    proxy_thread = threading.Thread(target=proxy_server.serve_forever, daemon=True)
    proxy_thread.start()
    sentinel = b"spiral-post-sentinel"
    try:
        status, _, body = request(
            proxy_server,
            "POST",
            f"http://127.0.0.1:{capture_server.server_port}/capture",
            headers={
                "Content-Type": "application/x-spiral-sentinel",
                "X-Spiral-Trace": "preserve-me",
                "Connection": "X-Proxy-Hop",
                "X-Proxy-Hop": "drop-me",
                "Proxy-Connection": "keep-alive",
            },
            body=sentinel,
        )
        assert (status, body) == (201, b"captured")
        assert len(captured) == 1
        assert captured[0]["method"] == "POST"
        assert captured[0]["body"] == sentinel
        assert captured[0]["headers"]["content-type"] == "application/x-spiral-sentinel"
        assert captured[0]["headers"]["x-spiral-trace"] == "preserve-me"
        assert "proxy-connection" not in captured[0]["headers"]
        assert "x-proxy-hop" not in captured[0]["headers"]
    finally:
        proxy_server.shutdown()
        proxy_server.server_close()
        capture_server.shutdown()
        capture_server.server_close()


def openssl(*arguments: str) -> subprocess.CompletedProcess[str]:
    executable = edge._resolve_openssl()
    return subprocess.run(
        [str(executable), *arguments],
        text=True,
        capture_output=True,
        check=True,
    )


def test_persistent_ca_and_leaf_have_required_tls_constraints(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(edge, "CERT_DIR", tmp_path / "certs")
    edge._certs.clear()

    first = edge.prepare_ca()
    root = Path(first["certificate"])
    assert root.is_absolute()
    assert len(first["fingerprint"]) == 64
    assert first["fingerprint"] == first["fingerprint"].lower()
    assert len(first["androidHash"]) == 8
    assert first["androidHash"] == first["androidHash"].lower()

    root_text = openssl("x509", "-in", str(root), "-noout", "-text").stdout
    assert "CA:TRUE, pathlen:0" in root_text
    assert "Certificate Sign, CRL Sign" in root_text
    openssl("x509", "-in", str(root), "-noout", "-checkend", str(365 * 86400))

    leaf, key = edge._ensure_leaf("sdk-config.17m3.com")
    openssl(
        "verify",
        "-purpose",
        "sslserver",
        "-CAfile",
        str(root),
        str(leaf),
    )
    leaf_text = openssl("x509", "-in", str(leaf), "-noout", "-text").stdout
    assert "DNS:sdk-config.17m3.com" in leaf_text
    assert "TLS Web Server Authentication" in leaf_text
    assert "CA:FALSE" in leaf_text
    assert key.exists()

    second = edge.prepare_ca()
    assert second["fingerprint"] == first["fingerprint"]
    openssl_fingerprint = (
        openssl("x509", "-in", str(root), "-noout", "-fingerprint", "-sha256")
        .stdout.strip()
        .split("=", 1)[1]
        .replace(":", "")
        .lower()
    )
    assert openssl_fingerprint == first["fingerprint"]


def test_prepare_ca_replaces_foreign_valid_root_subject(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(edge, "CERT_DIR", tmp_path / "certs")
    edge.CERT_DIR.mkdir(parents=True)
    edge._certs.clear()
    foreign_root = edge.CERT_DIR / "spiral-local-ca.pem"
    foreign_key = edge.CERT_DIR / "spiral-local-ca.key"
    openssl(
        "req",
        "-x509",
        "-newkey",
        "rsa:4096",
        "-sha256",
        "-nodes",
        "-keyout",
        str(foreign_key),
        "-out",
        str(foreign_root),
        "-days",
        "3650",
        "-subj",
        "/C=US/O=Foreign Offline Root/CN=Foreign Root CA",
        "-addext",
        "basicConstraints=critical,CA:TRUE,pathlen:0",
        "-addext",
        "keyUsage=critical,keyCertSign,cRLSign",
        "-addext",
        "subjectKeyIdentifier=hash",
        "-addext",
        "authorityKeyIdentifier=keyid:always",
    )
    foreign_fingerprint = (
        openssl("x509", "-in", str(foreign_root), "-noout", "-fingerprint", "-sha256")
        .stdout.strip()
        .split("=", 1)[1]
        .replace(":", "")
        .lower()
    )

    metadata = edge.prepare_ca()

    assert metadata["fingerprint"] != foreign_fingerprint
    assert (
        openssl(
            "x509",
            "-in",
            metadata["certificate"],
            "-noout",
            "-subject",
            "-nameopt",
            "compat",
        ).stdout.strip()
        == "subject=/C=GR/O=Spiral Warrior Local Offline/CN=Spiral Warrior Local Root CA"
    )


def test_legacy_self_signed_leaf_is_replaced_by_ca_signed_leaf(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(edge, "CERT_DIR", tmp_path / "certs")
    edge._certs.clear()
    ca = edge.prepare_ca()
    host = "sdk-config.17m3.com"
    legacy_key = edge.CERT_DIR / f"{host}.key"
    legacy_cert = edge.CERT_DIR / f"{host}.pem"
    openssl(
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-keyout",
        str(legacy_key),
        "-out",
        str(legacy_cert),
        "-days",
        "1",
        "-subj",
        f"/CN={host}",
    )
    legacy_fingerprint = hashlib.sha256(legacy_cert.read_bytes()).hexdigest()

    context = edge._get_cert_for_host(host)
    assert context is edge._certs[host]
    assert hashlib.sha256(legacy_cert.read_bytes()).hexdigest() != legacy_fingerprint
    openssl(
        "verify",
        "-purpose",
        "sslserver",
        "-CAfile",
        ca["certificate"],
        str(legacy_cert),
    )


def test_prepare_ca_cli_emits_one_strict_json_object():
    completed = subprocess.run(
        [
            str(ROOT / "server" / ".venv_win" / "Scripts" / "python.exe"),
            str(ROOT / "tools" / "serve_lbres_proxy.py"),
            "--prepare-ca",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=5,
    )
    assert completed.returncode == 0, completed.stderr
    assert len(completed.stdout.splitlines()) == 1
    metadata = json.loads(completed.stdout)
    assert Path(metadata["certificate"]).is_absolute()
    assert len(metadata["fingerprint"]) == 64
    assert len(metadata["androidHash"]) == 8
