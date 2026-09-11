#!/usr/bin/env python3
r"""
epic_probe.py -- MITM probe for Epic's EOS Auth (api.epicgames.dev).

Presents a cert signed by OUR CA (epic_ca/epic_cert.pem) for Epic hosts, forwards
to the real Epic, and logs everything. The ONE thing we're testing:

  * If the EOS SDK completes the TLS handshake and we see its requests  ->
    EOS trusts our CA (NOT pinned)  ->  MITM feasible, forever-offline possible.
  * If handshakes fail (TLS alert, no requests)  ->  EOS PINS its cert  ->
    MITM route closed, pivot to a patch/flag.

Needs epic_ca/rootCA.pem installed as a Windows Trusted Root first (epic_probe.ps1).
Run:  python epic_probe.py 443
"""
import socket, ssl, threading, json, os, sys, time, datetime, subprocess

CERT = "epic_ca/epic_cert.pem"
KEY  = "epic_ca/epic_key.pem"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 443

C = dict(reset="\033[0m", grn="\033[92m", yel="\033[93m", red="\033[91m", cyn="\033[96m", bold="\033[1m", dim="\033[2m")
try:
    import ctypes; k = ctypes.windll.kernel32; k.SetConsoleMode(k.GetStdHandle(-11), 7)
except Exception: pass

def stamp(): return datetime.datetime.now().strftime("%H:%M:%S")
_realips = {}
def real_ip(host):
    if host in _realips: return _realips[host]
    try:
        out = subprocess.run(["powershell","-NoProfile","-Command",
            f"(Resolve-DnsName -Name {host} -Type A -Server 1.1.1.1 -EA SilentlyContinue|?{{$_.Type -eq 'A'}}|Select -First 1).IPAddress"],
            capture_output=True, text=True, timeout=8).stdout.strip()
        _realips[host] = out or None; return _realips[host]
    except Exception: return None

accepted = set()
CAPTURE = "epic_ca/epic_auth_capture.log"   # full req+resp for oauth/token/auth endpoints
_lock = threading.Lock()
INTEREST = ("oauth", "/token", "auth", "verify", "exchange", "grant")

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
    def line(s): return s.until(b"\r\n")

def hdrs(hb):
    ls = hb.split(b"\r\n"); h = {}
    for l in ls[1:]:
        if b":" in l: k, _, v = l.partition(b":"); h[k.decode("latin1").strip().lower()] = v.decode("latin1").strip()
    return ls[0].decode("latin1", "replace"), h

def body(buf, h):
    if "chunked" in h.get("transfer-encoding", "").lower():
        raw = b""
        while True:
            sz = buf.line()
            if not sz: break
            raw += sz
            try: n = int(sz.strip().split(b";")[0], 16)
            except ValueError: break
            if n == 0: raw += buf.until(b"\r\n") or b""; break
            raw += buf.n(n + 2)
        return raw
    cl = h.get("content-length")
    if cl:
        try: n = int(cl)
        except ValueError: n = 0
        return buf.n(n)
    return b""

def _dechunk(b):
    """Strip HTTP chunked framing (size line + CRLFs) -> raw body bytes."""
    out = b""; i = 0
    while i < len(b):
        j = b.find(b"\r\n", i)
        if j < 0: break
        try: n = int(b[i:j].split(b";")[0], 16)
        except ValueError: break
        if n == 0: break
        out += b[j+2:j+2+n]; i = j + 2 + n + 2
    return out

def _decode(b, headers):
    if "chunked" in headers.get("transfer-encoding", "").lower():
        b = _dechunk(b)
    enc = headers.get("content-encoding", "").lower()
    import zlib
    try:
        if "gzip" in enc:
            b = zlib.decompressobj(31).decompress(b)   # streaming: ignores trailing framing
        elif "deflate" in enc:
            b = zlib.decompress(b)
        elif "br" in enc:
            import brotli; b = brotli.decompress(b)
    except Exception:
        pass
    return b

def _txt(b):
    try:
        s = b.decode("utf-8")
        if "�" not in s: return s[:12000]
    except Exception: pass
    import base64
    return "[BASE64] " + base64.b64encode(b).decode("ascii")

def logcap(host, reqline, reqbody, respline, respbody, reqh, resph):
    rb = _decode(reqbody, reqh); rrb = _decode(respbody, resph)
    with _lock:
        with open(CAPTURE, "a", encoding="utf-8", errors="replace") as f:
            f.write(f"\n===== [{stamp()}] {host} =====\n>>> {reqline}\n"
                    f"[req content-encoding: {reqh.get('content-encoding','none')}]\n{_txt(rb)[:4000]}\n"
                    f"<<< {respline}\n[resp content-encoding: {resph.get('content-encoding','none')}]\n{_txt(rrb)}\n")
    gt = ""
    try:
        import urllib.parse; gt = urllib.parse.parse_qs(rb.decode('latin1')).get('grant_type', [''])[0]
    except Exception: pass
    print(f"{C['yel']}{C['bold']}[CAPTURED AUTH] {host} {reqline.split(' ')[1][:50]} grant={gt} -> {respline}{C['reset']}", flush=True)

def handle(cli, sni):
    host = sni.get("host") or "?"
    if host not in accepted and "epic" in host.lower():
        accepted.add(host)
        print(f"{C['grn']}{C['bold']}[CERT ACCEPTED] EOS SDK trusts our CA for {host} -- MITM IS FEASIBLE!{C['reset']}", flush=True)
    ip = real_ip(host)
    if not ip:
        print(f"{C['red']}[!] can't resolve {host}{C['reset']}"); cli.close(); return
    try:
        up = ssl.create_default_context().wrap_socket(socket.create_connection((ip, 443), timeout=15), server_hostname=host)
    except Exception as e:
        print(f"{C['red']}[!] upstream {host} failed: {e}{C['reset']}"); cli.close(); return
    cb, ub = Buf(cli), Buf(up)
    try:
        while True:
            head = cb.until(b"\r\n\r\n")
            if not head: break
            rl, h = hdrs(head); rb = body(cb, h)
            up.sendall(head + rb)
            path = (rl.split(" ") + ["", ""])[1]
            # capture the WHOLE Epic surface this run (sdk config, connect, auth, ...),
            # skipping only noisy binary telemetry -- so this is the LAST capture.
            interesting = "telemetry" not in path.lower()
            if "epic" in host.lower():
                col = C['cyn']; print(f"{col}[{stamp()}] {host}  {rl[:80]}{C['reset']}", flush=True)
            rhead = ub.until(b"\r\n\r\n")
            if not rhead: break
            rrl, rh = hdrs(rhead); rrb = body(ub, rh)
            cli.sendall(rhead + rrb)
            if interesting and "epic" in host.lower():
                logcap(host, rl, rb, rrl, rrb, h, rh)
            if h.get("connection", "").lower() == "close" or rh.get("connection", "").lower() == "close":
                break
    except Exception: pass
    finally:
        try: up.close(); cli.close()
        except Exception: pass

def main():
    if not os.path.exists(CERT):
        sys.exit("epic_ca/epic_cert.pem missing — generate the CA first.")
    print(f"{C['bold']}{C['grn']}  EPIC EOS-AUTH MITM PROBE{C['reset']}  on :{PORT}")
    print(f"  presenting our CA-signed cert for Epic hosts, forwarding to real Epic.")
    print(f"  {C['yel']}watching for whether the EOS SDK accepts our cert...{C['reset']}\n")
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
        except ssl.SSLError as e:
            # a TLS alert here from an Epic client = cert REJECTED (pinning)
            print(f"{C['red']}[✗ handshake rejected] {e}{C['reset']}", flush=True)
            try: raw.close()
            except Exception: pass
            continue
        except Exception:
            try: raw.close()
            except Exception: pass
            continue
        threading.Thread(target=handle, args=(tls, sni), daemon=True).start()

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("\nprobe stopped.")
