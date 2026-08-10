#!/usr/bin/env python3
r"""
record_proxy.py -- WW3 HTTPS recording proxy (man-in-the-middle logger) with a
live terminal feed + a web dashboard so you can SEE it working.

Sits on 0.0.0.0:443. The WW3 game client (libcurl, bVerifyPeer=false) is
redirected here via the hosts file, so it accepts our self-signed cert. For each
connection we read the requested host from TLS SNI, open a real TLS connection to
the genuine backend (real IP from real_ips.json), and relay traffic both ways --
logging every request/response in PLAINTEXT.

  * Live terminal feed : every captured exchange prints as it happens.
  * Web dashboard      : http://127.0.0.1:9009  (pulsing activity + graphs).

Usage:  python record_proxy.py [listen_port=443] [logdir] [dash_port=9009]
Needs:  mock_cert.pem / mock_key.pem  and  real_ips.json  in the working dir.
"""
import socket, ssl, threading, json, os, sys, time, datetime, http.server, re

CERT, KEY, CONFIG = "mock_cert.pem", "mock_key.pem", "real_ips.json"
LISTEN_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 443
LOGDIR      = sys.argv[2] if len(sys.argv) > 2 else "record_logs"
DASH_PORT   = int(sys.argv[3]) if len(sys.argv) > 3 else 9009
os.makedirs(LOGDIR, exist_ok=True)

# ---- enable ANSI colour on Windows terminals ----
try:
    import ctypes
    k = ctypes.windll.kernel32
    k.SetConsoleMode(k.GetStdHandle(-11), 7)
except Exception:
    pass
C = dict(reset="\033[0m", dim="\033[2m", grn="\033[92m", yel="\033[93m",
         red="\033[91m", cyn="\033[96m", mag="\033[95m", bold="\033[1m")

_lock = threading.Lock()
STATS = {"started": time.time(), "requests": 0, "responses": 0,
         "bytes_up": 0, "bytes_down": 0, "hosts": {}, "recent": [],
         "last_event": 0.0, "errors": 0,
         # passively-sniffed plaintext channels
         "hub": {"messages": 0, "recent": []},     # WebSocket JSON-RPC (menu brain), :8705
         "xmpp": {"messages": 0, "recent": []}}    # XMPP presence, :5222

def stamp():
    return datetime.datetime.now().strftime("%H:%M:%S")

# --- STREAM-SAFE redaction -------------------------------------------------
# Applied to everything DISPLAYED (terminal feed + web dashboard) so a live
# stream/recording never shows your Steam ID, tokens, JWTs or email. The raw
# log FILES on disk keep full data for private analysis (don't open them on stream).
_RX = [
    (re.compile(r"eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}"), "JWT"),
    (re.compile(r"\b7656119\d{10}\b"), "STEAMID"),
    (re.compile(r'("(?:access|refresh|session|auth|id)?[Tt]oken|jwt|secret|apiKey|password)"\s*:\s*"[^"]*"'), r'\1":"HIDDEN"'),
    (re.compile(r"([Bb]earer)\s+[A-Za-z0-9._~+/=-]{8,}"), r"\1 HIDDEN"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "email@hidden"),
    (re.compile(r"V2:WW3:::[0-9A-Fa-f]{16,}"), "V2:WW3:::HIDDEN"),
    # in-game identity (shows up in LobbyChange on the live feed)
    (re.compile(r'("(?:playerName|displayName|nickname|userName)"\s*:\s*")[^"]*(")'), r"\1PLAYER\2"),
    (re.compile(r"\bprod-\d{4,}\b"), "prod-PLAYER"),
]
def redact(s):
    if not s:
        return s
    for rx, repl in _RX:
        s = rx.sub(repl, s)
    return s

def log_file(host, text):
    with _lock:
        for path in (os.path.join(LOGDIR, f"{host}.log"), os.path.join(LOGDIR, "_session.log")):
            with open(path, "a", encoding="utf-8", errors="replace") as f:
                f.write(text + "\n")

def record_exchange(host, method, path, status, size_up, size_down):
    now = time.time()
    dpath = redact(path)                 # stream-safe path for display
    with _lock:
        STATS["requests"] += 1
        STATS["responses"] += 1
        STATS["bytes_up"] += size_up
        STATS["bytes_down"] += size_down
        STATS["last_event"] = now
        h = STATS["hosts"].setdefault(host, {"count": 0, "bytes": 0})
        h["count"] += 1
        h["bytes"] += size_down
        h["last"] = f"{method} {dpath} -> {status}"
        STATS["recent"].insert(0, {"t": stamp(), "host": host, "method": method,
                                   "path": dpath, "status": status, "size": size_down})
        del STATS["recent"][40:]
    col = C["grn"] if str(status).startswith("2") else (C["yel"] if str(status).startswith(("3", "4")) else C["red"])
    short = host.split(".")[0]
    print(f"{C['dim']}[{stamp()}]{C['reset']} {C['cyn']}{short:<9}{C['reset']} "
          f"{C['bold']}{method:<5}{C['reset']} {dpath[:52]:<52} {col}{status}{C['reset']} "
          f"{C['dim']}({size_down}B){C['reset']}", flush=True)

def note_error(host, msg):
    with _lock:
        STATS["errors"] += 1
    print(f"{C['red']}[{stamp()}] ! {host}: {msg}{C['reset']}", flush=True)

REAL_IPS = json.load(open(CONFIG)) if os.path.exists(CONFIG) else {}

# ------------------------------------------------------------------ HTTP framing
class Buf:
    def __init__(self, sock): self.sock, self.buf = sock, b""
    def _fill(self):
        c = self.sock.recv(65536)
        if not c: return False
        self.buf += c; return True
    def read_until(self, sep=b"\r\n\r\n"):
        while sep not in self.buf:
            if not self._fill():
                return self.buf or None
        i = self.buf.find(sep) + len(sep)
        d, self.buf = self.buf[:i], self.buf[i:]; return d
    def read_n(self, n):
        while len(self.buf) < n:
            if not self._fill(): break
        d, self.buf = self.buf[:n], self.buf[n:]; return d
    def read_line(self): return self.read_until(b"\r\n")

def parse_headers(hb):
    lines = hb.split(b"\r\n"); start = lines[0].decode("latin1"); headers = {}
    for ln in lines[1:]:
        if b":" in ln:
            k, _, v = ln.partition(b":"); headers[k.decode("latin1").strip().lower()] = v.decode("latin1").strip()
    return start, headers

def read_body(buf, headers):
    if "chunked" in headers.get("transfer-encoding", "").lower():
        raw, body = b"", b""
        while True:
            sz = buf.read_line()
            if not sz: break
            raw += sz
            try: n = int(sz.strip().split(b";")[0], 16)
            except ValueError: break
            if n == 0:
                t = buf.read_until(b"\r\n");  raw += t or b""; break
            ch = buf.read_n(n + 2); raw += ch; body += ch[:n]
        return raw, body
    cl = headers.get("content-length")
    if cl:
        try: n = int(cl)
        except ValueError: n = 0
        d = buf.read_n(n); return d, d
    return b"", b""

def pretty(body, headers):
    if "json" in headers.get("content-type", "") or body[:1] in (b"{", b"["):
        try: return json.dumps(json.loads(body.decode("utf-8")), indent=2, ensure_ascii=False)
        except Exception: pass
    try: return body.decode("utf-8")
    except Exception: return f"<{len(body)} bytes binary>"

def _upstream_ips(host):
    """real_ips.json may store a string or a list of A records."""
    v = REAL_IPS.get(host)
    if not v:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v if x]
    return [str(v)]

def _connect_upstream(host, ip):
    ctx = ssl.create_default_context()
    try:
        ctx.set_alpn_protocols(["http/1.1"])
    except NotImplementedError:
        pass
    return ctx.wrap_socket(socket.create_connection((ip, 443), timeout=15), server_hostname=host)

def _exchange_once(up, head, rawb):
    """Send one HTTP request on an upstream socket; return (rhead, rrawb, rstart, rheaders, rbody)."""
    up.sendall(head + rawb)
    ubuf = Buf(up)
    rhead = ubuf.read_until(b"\r\n\r\n")
    if not rhead:
        return None
    rstart, rheaders = parse_headers(rhead)
    rrawb, rbody = read_body(ubuf, rheaders)
    return rhead, rrawb, rstart, rheaders, rbody

# ------------------------------------------------------------------ per connection
def handle(client_sock, sni):
    host = sni.get("host") or "unknown"
    ips = _upstream_ips(host)
    if not ips:
        note_error(host, f"no real IP in {CONFIG}"); client_sock.close(); return
    ip_i = 0
    try:
        up = _connect_upstream(host, ips[ip_i])
    except Exception as e:
        note_error(host, f"upstream connect failed: {e}"); client_sock.close(); return
    log_file(host, f"\n===== [{datetime.datetime.now()}] {host} ({ips[ip_i]}) =====")
    cbuf = Buf(client_sock)
    try:
        while True:
            head = cbuf.read_until(b"\r\n\r\n")
            if not head: break
            start, headers = parse_headers(head)
            rawb, body = read_body(cbuf, headers)
            method, path = (start.split(" ") + ["", ""])[:2]
            blk = [f"[{stamp()}] >>> {start}"]
            for k, v in headers.items():
                vv = v[:20] + "...(redacted)" if ("auth" in k or "token" in k or k == "cookie") else v
                blk.append(f"    {k}: {vv}")
            if body: blk.append("    body: " + pretty(body, headers).replace("\n", "\n    "))
            log_file(host, "\n".join(blk))

            got = None
            try:
                got = _exchange_once(up, head, rawb)
            except Exception as e:
                note_error(host, f"upstream send failed: {e}")
            # Auth through one gateway node sometimes returns Invalid Token while
            # another node accepts the same FXID JWT — retry other resolved IPs.
            if (got and "/authenticate/fxgames" in path and len(ips) > 1
                    and got[4] and b"Invalid Token" in got[4]):
                for j, alt in enumerate(ips):
                    if j == ip_i:
                        continue
                    try:
                        try: up.close()
                        except Exception: pass
                        up = _connect_upstream(host, alt)
                        ip_i = j
                        log_file(host, f"\n===== [{datetime.datetime.now()}] {host} ({alt}) auth-retry =====")
                        got = _exchange_once(up, head, rawb)
                        if got and got[4] and b"Invalid Token" not in got[4]:
                            break
                    except Exception as e:
                        note_error(host, f"auth-retry {alt} failed: {e}")

            if not got:
                break
            rhead, rrawb, rstart, rheaders, rbody = got
            client_sock.sendall(rhead + rrawb)
            status = rstart.split(" ")[1] if len(rstart.split(" ")) > 1 else "?"
            rblk = [f"[{stamp()}] <<< {rstart}"]
            rblk.append("    body: " + pretty(rbody, rheaders).replace("\n", "\n    ") if rbody else f"    (no body)")
            log_file(host, "\n".join(rblk))
            try:
                rec = {"host": host, "method": method, "path": path, "status": status}
                ct = rheaders.get("content-type", "")
                if rbody and ("json" in ct or rbody[:1] in (b"{", b"[")):
                    try: rec["json"] = json.loads(rbody.decode("utf-8"))
                    except Exception: rec["json"] = None
                with _lock:
                    with open(os.path.join(LOGDIR, "captures.jsonl"), "a", encoding="utf-8") as jf:
                        jf.write(json.dumps(rec, ensure_ascii=False) + "\n")
            except Exception:
                pass
            record_exchange(host, method, path, status, len(rawb) + len(head), len(rrawb) + len(rhead))
            if headers.get("connection", "").lower() == "close" or rheaders.get("connection", "").lower() == "close":
                break
    except Exception as e:
        note_error(host, f"relay error: {e}")
    finally:
        for s in (up, client_sock):
            try: s.close()
            except Exception: pass

# ------------------------------------------------------------------ passive sniffer
# The Hub (WebSocket JSON-RPC, :8705) and XMPP (:5222) are PLAINTEXT, so instead of
# redirecting them (which could break the live session) we passively COPY the packets
# with WinDivert in SNIFF mode, reassemble each TCP stream, and decode.
# Hub (menu brain) WebSocket port. Build 1795 uses 8700 (was 8705 in June); watch both.
HUB_PORTS = (8700, 8705)
XMPP_PORT = 5222

def record_hub_msg(direction, text):
    now = time.time()
    try: pretty_t = json.dumps(json.loads(text), ensure_ascii=False)
    except Exception: pretty_t = text
    dmsg = redact(pretty_t)              # stream-safe message for display
    with _lock:
        STATS["hub"]["messages"] += 1
        STATS["last_event"] = now
        STATS["hub"]["recent"].insert(0, {"t": stamp(), "dir": direction, "msg": dmsg[:160]})
        del STATS["hub"]["recent"][30:]
    log_file("hub", f"[{stamp()}] {direction} {pretty_t}")   # FULL data to disk
    arrow = "C>S" if direction == ">" else "S>C"
    print(f"{C['dim']}[{stamp()}]{C['reset']} {C['mag']}hub{C['reset']}      "
          f"{C['bold']}{arrow}{C['reset']} {dmsg[:80]}", flush=True)

def record_xmpp_msg(direction, text):
    text = text.strip()
    if not text: return
    dtext = redact(text)                 # stream-safe for display
    with _lock:
        STATS["xmpp"]["messages"] += 1
        STATS["last_event"] = time.time()
        STATS["xmpp"]["recent"].insert(0, {"t": stamp(), "dir": direction, "msg": dtext[:160]})
        del STATS["xmpp"]["recent"][30:]
    log_file("xmpp", f"[{stamp()}] {direction} {text}")

class WSDeframer:
    """Incrementally decode a one-directional WebSocket byte stream into text messages."""
    def __init__(self, on_message):
        self.buf = b""
        self.frag = b""
        self.on_message = on_message
    def feed(self, data):
        self.buf += data
        while True:
            if len(self.buf) < 2: return
            b0, b1 = self.buf[0], self.buf[1]
            fin = b0 & 0x80; opcode = b0 & 0x0f
            masked = b1 & 0x80; ln = b1 & 0x7f
            off = 2
            if ln == 126:
                if len(self.buf) < 4: return
                ln = int.from_bytes(self.buf[2:4], "big"); off = 4
            elif ln == 127:
                if len(self.buf) < 10: return
                ln = int.from_bytes(self.buf[2:10], "big"); off = 10
            if masked:
                if len(self.buf) < off + 4: return
                mask = self.buf[off:off+4]; off += 4
            if len(self.buf) < off + ln: return
            payload = self.buf[off:off+ln]
            self.buf = self.buf[off+ln:]
            if masked:
                payload = bytes(payload[i] ^ mask[i & 3] for i in range(len(payload)))
            if opcode == 0x8: return                # close
            if opcode in (0x9, 0xa): continue        # ping/pong
            if opcode in (0x1, 0x2, 0x0):
                self.frag += payload
                if fin:
                    try: msg = self.frag.decode("utf-8", "replace")
                    except Exception: msg = repr(self.frag)
                    self.frag = b""
                    if msg.strip(): self.on_message(msg)

class Flow:
    """Reassembles one TCP connection's two directions for a given app port."""
    def __init__(self, kind):
        self.kind = kind
        if kind == "hub":
            self.up = WSDeframer(lambda m: record_hub_msg(">", m))    # client->server
            self.down = WSDeframer(lambda m: record_hub_msg("<", m))  # server->client
            self.up_started = self.down_started = False
        else:
            self.tls = False
            self.noted_enc = False
    def _skip_http(self, payload, started_attr):
        # WebSocket frames begin after the HTTP upgrade handshake (\r\n\r\n).
        if getattr(self, started_attr):
            return payload
        idx = payload.find(b"\r\n\r\n")
        if idx != -1:                       # saw the handshake end -> frames follow
            setattr(self, started_attr, True)
            return payload[idx+4:]
        if payload[:4] in (b"GET ", b"HTTP"):
            return b""                       # handshake in progress; wait for its end
        # No handshake in view: we joined an existing connection mid-stream.
        # Best-effort: start deframing from here (may miss until it resyncs).
        setattr(self, started_attr, True)
        return payload
    def add(self, to_server, payload):
        if not payload: return
        if self.kind == "hub":
            if to_server:
                self.up.feed(self._skip_http(payload, "up_started"))
            else:
                self.down.feed(self._skip_http(payload, "down_started"))
        else:
            if self.tls: return
            # Detect encrypted (TLS) XMPP: if the bytes aren't mostly printable, it's
            # ciphertext -- note it ONCE and stop spamming the feed with gibberish.
            printable = sum(1 for b in payload if b in (9, 10, 13) or 32 <= b < 127)
            if len(payload) and printable / len(payload) < 0.85:
                if not self.noted_enc:
                    record_xmpp_msg("*", "[XMPP is encrypted (TLS) - not readable via passive sniff]")
                    self.noted_enc = True
                self.tls = True
                return
            try: txt = payload.decode("utf-8", "replace")
            except Exception: return
            if "<starttls" in txt or "<proceed" in txt:
                record_xmpp_msg(">" if to_server else "<", txt)
                self.tls = True
                record_xmpp_msg("*", "[STARTTLS negotiated - remainder encrypted]")
                return
            record_xmpp_msg(">" if to_server else "<", txt)

def sniff_loop():
    try:
        import pydivert
    except Exception as e:
        print(f"{C['yel']}[sniff] pydivert unavailable ({e}); Hub/XMPP capture disabled.{C['reset']}")
        return
    all_ports = tuple(HUB_PORTS) + (XMPP_PORT,)
    port_clause = " or ".join(f"tcp.SrcPort=={p} or tcp.DstPort=={p}" for p in all_ports)
    flt = f"tcp and ({port_clause})"
    flows = {}
    try:
        with pydivert.WinDivert(flt, flags=pydivert.Flag.SNIFF) as w:
            print(f"{C['grn']}[sniff] passive Hub(:{'/'.join(map(str,HUB_PORTS))})+XMPP(:{XMPP_PORT}) capture active (WinDivert).{C['reset']}", flush=True)
            for p in w:
                if not p.tcp or not p.payload:
                    continue
                if p.dst_port in all_ports:
                    to_server, port, other = True, p.dst_port, (p.src_addr, p.src_port)
                elif p.src_port in all_ports:
                    to_server, port, other = False, p.src_port, (p.dst_addr, p.dst_port)
                else:
                    continue
                kind = "hub" if port in HUB_PORTS else "xmpp"
                key = (kind, other)
                fl = flows.get(key)
                if fl is None:
                    fl = flows[key] = Flow(kind)
                try:
                    fl.add(to_server, bytes(p.payload))
                except Exception:
                    pass
    except Exception as e:
        hint = "  (need to run elevated / as admin for WinDivert)" if "denied" in str(e).lower() else ""
        print(f"{C['red']}[sniff] Hub/XMPP capture unavailable: {e}{hint}{C['reset']}", flush=True)
        print(f"{C['yel']}[sniff] HTTPS recording continues normally.{C['reset']}", flush=True)

# ------------------------------------------------------------------ dashboard
DASH_HTML = r"""<!doctype html><html><head><meta charset=utf-8><title>WW3 Recorder</title>
<style>
 body{margin:0;font-family:Segoe UI,system-ui,sans-serif;background:#0b0f17;color:#e6edf3}
 .wrap{max-width:1000px;margin:0 auto;padding:24px}
 h1{font-size:20px;font-weight:600;margin:0 0 4px;display:flex;align-items:center;gap:12px}
 .sub{color:#7d8590;font-size:13px;margin-bottom:20px}
 .brain{width:46px;height:46px;border-radius:50%;background:radial-gradient(circle at 40% 35%,#3fb950,#238636);
   box-shadow:0 0 0 0 rgba(63,185,80,.7);animation:none;flex:0 0 auto}
 .brain.live{animation:pulse 1.4s infinite}
 .brain.idle{background:radial-gradient(circle at 40% 35%,#8b949e,#484f58)}
 @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(63,185,80,.6)}70%{box-shadow:0 0 0 22px rgba(63,185,80,0)}100%{box-shadow:0 0 0 0 rgba(63,185,80,0)}}
 .cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:22px}
 .card{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:16px}
 .card .n{font-size:30px;font-weight:700}.card .l{color:#7d8590;font-size:12px;text-transform:uppercase;letter-spacing:.5px}
 .sec{font-size:13px;color:#7d8590;text-transform:uppercase;letter-spacing:.5px;margin:0 0 10px}
 .bar{display:flex;align-items:center;gap:10px;margin:6px 0}
 .bar .name{width:150px;font-size:13px;color:#c9d1d9}.bar .track{flex:1;background:#21262d;border-radius:6px;height:16px;overflow:hidden}
 .bar .fill{height:100%;background:linear-gradient(90deg,#1f6feb,#3fb950);width:0}
 .bar .c{width:44px;text-align:right;font-variant-numeric:tabular-nums;font-size:13px}
 table{width:100%;border-collapse:collapse;font-size:13px}
 td,th{text-align:left;padding:6px 8px;border-bottom:1px solid #21262d}
 th{color:#7d8590;font-weight:500}
 .s2{color:#3fb950}.s3,.s4{color:#d29922}.s5{color:#f85149}
 .mut{color:#7d8590}
</style></head><body><div class=wrap>
 <h1><span id=brain class="brain idle"></span> WW3 Traffic Recorder</h1>
 <div class=sub id=statusline>connecting...</div>
 <div class=cards>
  <div class=card><div class=n id=req>0</div><div class=l>HTTPS exchanges</div></div>
  <div class=card><div class=n id=hub>0</div><div class=l>Hub messages (menu)</div></div>
  <div class=card><div class=n id=xmpp>0</div><div class=l>XMPP messages</div></div>
  <div class=card><div class=n id=up>0s</div><div class=l>Uptime</div></div>
 </div>
 <p class=sec>HTTPS requests per endpoint</p><div id=bars></div>
 <p class=sec style=margin-top:24px>HTTPS feed (meta / storage / gateway)</p>
 <table><thead><tr><th>Time</th><th>Endpoint</th><th>Method</th><th>Path</th><th>Status</th><th>Size</th></tr></thead>
 <tbody id=feed><tr><td colspan=6 class=mut>waiting for the game to make requests...</td></tr></tbody></table>
 <p class=sec style=margin-top:24px>Hub feed - the menu brain (WebSocket JSON-RPC :8700)</p>
 <table><thead><tr><th>Time</th><th>Dir</th><th>Message</th></tr></thead>
 <tbody id=hubfeed><tr><td colspan=3 class=mut>waiting for Hub traffic (needs WinDivert / admin)...</td></tr></tbody></table>
 <p class=sec style=margin-top:24px>XMPP feed (presence :5222)</p>
 <table><thead><tr><th>Time</th><th>Dir</th><th>Message</th></tr></thead>
 <tbody id=xmppfeed><tr><td colspan=3 class=mut>waiting for XMPP traffic...</td></tr></tbody></table>
</div><script>
function fmt(s){return s<60?s+'s':(s<3600?Math.floor(s/60)+'m '+(s%60)+'s':Math.floor(s/3600)+'h')}
async function tick(){
 try{
  const r=await fetch('/stats');const d=await r.json();
  const total=d.requests+(d.hub?d.hub.messages:0)+(d.xmpp?d.xmpp.messages:0);
  const idle=(Date.now()/1000-d.last_event)>3||total==0;
  const b=document.getElementById('brain');b.className='brain '+(idle?'idle':'live');
  document.getElementById('statusline').textContent=(total>0?'RECORDING - '+total+' messages captured':'Recorder up - waiting for game traffic')+' | https :443  hub :8700  xmpp :5222';
  document.getElementById('req').textContent=d.requests;
  document.getElementById('hub').textContent=d.hub?d.hub.messages:0;
  document.getElementById('xmpp').textContent=d.xmpp?d.xmpp.messages:0;
  document.getElementById('up').textContent=fmt(Math.floor(Date.now()/1000-d.started));
  const max=Math.max(1,...Object.values(d.hosts).map(h=>h.count));
  document.getElementById('bars').innerHTML=Object.entries(d.hosts).map(([h,v])=>
   `<div class=bar><div class=name title="${h}">${h.split('.')[0]}</div><div class=track><div class=fill style="width:${100*v.count/max}%"></div></div><div class=c>${v.count}</div></div>`).join('')||'<div class=mut>none yet</div>';
  document.getElementById('feed').innerHTML=d.recent.map(e=>
   `<tr><td class=mut>${e.t}</td><td>${e.host.split('.')[0]}</td><td>${e.method}</td><td>${e.path}</td><td class=s${String(e.status)[0]}>${e.status}</td><td class=mut>${e.size}B</td></tr>`).join('')||'<tr><td colspan=6 class=mut>waiting...</td></tr>';
  const hf=(d.hub&&d.hub.recent)||[];
  document.getElementById('hubfeed').innerHTML=hf.map(e=>
   `<tr><td class=mut>${e.t}</td><td>${e.dir=='>'?'C&gt;S':'S&gt;C'}</td><td style="font-family:Consolas,monospace">${e.msg.replace(/</g,'&lt;')}</td></tr>`).join('')||'<tr><td colspan=3 class=mut>waiting for Hub traffic (needs WinDivert / admin)...</td></tr>';
  const xf=(d.xmpp&&d.xmpp.recent)||[];
  document.getElementById('xmppfeed').innerHTML=xf.map(e=>
   `<tr><td class=mut>${e.t}</td><td>${e.dir}</td><td style="font-family:Consolas,monospace">${e.msg.replace(/</g,'&lt;')}</td></tr>`).join('')||'<tr><td colspan=3 class=mut>waiting for XMPP traffic...</td></tr>';
 }catch(e){document.getElementById('statusline').textContent='recorder not reachable';}
}
setInterval(tick,900);tick();
</script></body></html>"""

class DashHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/stats"):
            with _lock: body = json.dumps(STATS).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
        else:
            body = DASH_HTML.encode(); self.send_response(200); self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass

def start_dashboard():
    try:
        http.server.ThreadingHTTPServer(("127.0.0.1", DASH_PORT), DashHandler).serve_forever()
    except Exception as e:
        print(f"{C['red']}[dash] {e}{C['reset']}")

# ------------------------------------------------------------------ main
def main():
    print(f"{C['bold']}{C['grn']}"
          f"  WW3 TRAFFIC RECORDER{C['reset']}")
    print(f"  https   : MITM recording on :{LISTEN_PORT}  (meta / storage / gateway)")
    print(f"  hub+xmpp: passive WinDivert sniff on :{'/'.join(map(str,HUB_PORTS))} / :{XMPP_PORT}  (menu brain + presence)")
    print(f"  {C['cyn']}dashboard: http://127.0.0.1:{DASH_PORT}{C['reset']}  <- open this to watch")
    print(f"  logs    : {LOGDIR}/")
    print(f"  backends: {', '.join(REAL_IPS) or C['red']+'(real_ips.json empty!)'+C['reset']}")
    print(f"  {C['dim']}--- live feed (each line = one captured message) ---{C['reset']}\n")
    threading.Thread(target=start_dashboard, daemon=True).start()
    threading.Thread(target=sniff_loop, daemon=True).start()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", LISTEN_PORT)); srv.listen(64)
    while True:
        raw, _ = srv.accept()
        sni = {}
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(CERT, KEY)
        try: ctx.set_alpn_protocols(["http/1.1"])
        except NotImplementedError: pass
        ctx.sni_callback = lambda s, name, c, _h=sni: _h.__setitem__("host", name)
        try:
            tls = ctx.wrap_socket(raw, server_side=True)
        except Exception:
            try: raw.close()
            except Exception: pass
            continue
        threading.Thread(target=handle, args=(tls, sni), daemon=True).start()

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print(f"\n{C['yel']}[*] recorder stopped.{C['reset']}")
