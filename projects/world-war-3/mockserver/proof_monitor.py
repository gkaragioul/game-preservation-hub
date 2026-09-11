#!/usr/bin/env python3
r"""
proof_monitor.py -- live "this game is running on MY private server" dashboard.

Read-only: it watches the mock request logs + the game's live TCP connections and
serves an auto-refreshing web page proving the game's menu backend is local.

    python proof_monitor.py            # dashboard on http://127.0.0.1:9010
"""
import http.server, json, os, re, subprocess, threading, time

LOGDIR = r"F:\Dev_Work\GameDev\WW3\windows\mock_logs"
PORT = 9010
_STAMP = re.compile(r"-> (replay|generic|minted PlayerToken|ws://\S+)")

def read_served():
    path = os.path.join(LOGDIR, "https.out.log")
    reqs = []
    try:
        for line in open(path, encoding="utf-8", errors="replace"):
            m = re.match(r"\[<\] ([A-Z]+) (\S+)\s+-> (.*)", line.strip())
            if m:
                kind = m.group(3).split("(")[0].strip()
                reqs.append({"method": m.group(1), "path": m.group(2), "served": kind})
    except Exception:
        pass
    return reqs

def game_conns():
    # ask PowerShell for the game's established remote endpoints
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "$g=Get-Process WW3-Win64-Shipping -ErrorAction SilentlyContinue;"
             "if($g){Get-NetTCPConnection -OwningProcess $g.Id -State Established -EA SilentlyContinue|"
             "Select-Object -Unique RemoteAddress,RemotePort|ConvertTo-Json -Compress}"],
            capture_output=True, text=True, timeout=6).stdout.strip()
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return [f"{d['RemoteAddress']}:{d['RemotePort']}" for d in data]
    except Exception:
        return []

STATE = {"served": [], "conns": [], "running": False}
def poll():
    while True:
        served = read_served()
        conns = game_conns()
        STATE["served"] = served
        STATE["conns"] = conns
        STATE["running"] = any(c.endswith(":8700") and c.startswith("127.0.0.1") for c in conns)
        time.sleep(2)

HTML = r"""<!doctype html><html><head><meta charset=utf-8><title>WW3 - Running Locally</title><style>
 body{margin:0;font-family:Segoe UI,system-ui,sans-serif;background:#0b0f17;color:#e6edf3}
 .wrap{max-width:920px;margin:0 auto;padding:26px}
 h1{font-size:22px;margin:0 0 2px}.sub{color:#7d8590;font-size:13px;margin-bottom:20px}
 .banner{border-radius:12px;padding:18px 20px;margin-bottom:20px;font-size:18px;font-weight:600;display:flex;align-items:center;gap:12px}
 .ok{background:#0f2417;border:1px solid #238636;color:#3fb950}.bad{background:#241110;border:1px solid #8b3a30;color:#f0883e}
 .dot{width:14px;height:14px;border-radius:50%;background:currentColor;box-shadow:0 0 0 0 currentColor;animation:p 1.5s infinite}
 @keyframes p{0%{box-shadow:0 0 0 0 rgba(63,185,80,.6)}70%{box-shadow:0 0 0 14px rgba(63,185,80,0)}100%{box-shadow:0 0 0 0 rgba(63,185,80,0)}}
 .cards{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:22px}
 .card{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:16px}
 .card .n{font-size:30px;font-weight:700}.card .l{color:#7d8590;font-size:12px;text-transform:uppercase;letter-spacing:.5px}
 .sec{font-size:13px;color:#7d8590;text-transform:uppercase;letter-spacing:.5px;margin:0 0 10px}
 table{width:100%;border-collapse:collapse;font-size:13px}td,th{text-align:left;padding:6px 8px;border-bottom:1px solid #21262d}
 th{color:#7d8590;font-weight:500}.loc{color:#3fb950;font-weight:600}.real{color:#8b949e}
 .mut{color:#7d8590}code{color:#79c0ff}
</style></head><body><div class=wrap>
 <h1>World War 3 &mdash; Private Server Monitor</h1><div class=sub>proof the game's menu backend is running on THIS machine</div>
 <div id=banner class=banner></div>
 <div class=cards>
  <div class=card><div class=n id=served>0</div><div class=l>Requests served locally</div></div>
  <div class=card><div class=n id=local>0</div><div class=l>Game conns to 127.0.0.1</div></div>
  <div class=card><div class=n id=uptime>live</div><div class=l>Status</div></div>
 </div>
 <p class=sec>The game's live connections</p>
 <table><thead><tr><th>Remote endpoint</th><th>Verdict</th></tr></thead><tbody id=conns></tbody></table>
 <p class=sec style=margin-top:22px>Requests your server answered (most recent)</p>
 <table><thead><tr><th>Method</th><th>Path</th><th>Served by</th></tr></thead><tbody id=feed></tbody></table>
</div><script>
async function tick(){
 try{const d=await (await fetch('/data')).json();
  const b=document.getElementById('banner');
  if(d.running){b.className='banner ok';b.innerHTML='<span class=dot></span> RUNNING ON YOUR PRIVATE SERVER &mdash; the Hub (menu brain) is a live WebSocket to 127.0.0.1:8700';}
  else{b.className='banner bad';b.innerHTML='&#9679; Hub not currently connected to 127.0.0.1:8700 (launch the game with the mocks up)';}
  document.getElementById('served').textContent=d.served.length;
  document.getElementById('local').textContent=d.conns.filter(c=>c.startsWith('127.0.0.1')).length;
  document.getElementById('conns').innerHTML=d.conns.map(c=>{const loc=c.startsWith('127.0.0.1');
    return `<tr><td>${c}</td><td class=${loc?'loc':'real'}>${loc?'&#10003; YOUR machine':'external (login/EAC/voice)'}</td></tr>`}).join('')||'<tr><td colspan=2 class=mut>no game connections (game not running?)</td></tr>';
  document.getElementById('feed').innerHTML=d.served.slice(-25).reverse().map(r=>
    `<tr><td>${r.method}</td><td><code>${r.path}</code></td><td class=loc>${r.served}</td></tr>`).join('')||'<tr><td colspan=3 class=mut>no requests yet</td></tr>';
 }catch(e){}
}
setInterval(tick,1500);tick();
</script></body></html>"""

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/data"):
            body = json.dumps(STATE).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
        else:
            body = HTML.encode(); self.send_response(200); self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass

if __name__ == "__main__":
    threading.Thread(target=poll, daemon=True).start()
    print(f"[*] proof monitor -> http://127.0.0.1:{PORT}  (Ctrl+C to stop)")
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
