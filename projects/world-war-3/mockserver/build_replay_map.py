#!/usr/bin/env python3
r"""
build_replay_map.py -- turn captured recorder logs into a replay map the mock
servers can serve back. Parses the WW3_rec_* logs and produces replay_map.json:

  {
    "http": { "GET /playerData": {"status":"200 OK","body":{...}}, ... },
    "rpc":  { "onlineParameters.getParameters": <result>, "friends.changeStatus": true, ... },
    "lobby_pushes": [ <server-initiated Lobby* messages, in order> ]
  }

Usage:  python build_replay_map.py "F:\Dev_Work\GameDev\WW3\LOGS\23July26"
        (defaults to that folder). Writes replay_map.json next to this script.
"""
import json, os, re, sys, glob

LOGDIR = sys.argv[1] if len(sys.argv) > 1 else r"F:\Dev_Work\GameDev\WW3\LOGS\23July26"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "replay_map.json")

def norm_path(p):
    # collapse numeric ids so /accountConfig/76561... matches a generic handler
    return re.sub(r"/\d{5,}", "/{id}", p.split("?")[0])

# ---------------- parse HTTP-style logs (meta / endpoint / api.storage) ----------
def parse_http(text, http):
    lines = text.splitlines()
    i, n = 0, len(lines)
    req_re = re.compile(r"^\[[0-9:]+\] >>> ([A-Z]+) (\S+) HTTP")
    resp_re = re.compile(r"^\[[0-9:]+\] <<< HTTP/1\.1 (.+)$")
    def collect_body(start):
        # a "    body: ..." block runs until the next "[HH:MM:SS]" or "=====" line
        out = []
        j = start
        while j < n and not (lines[j].startswith("[") or lines[j].startswith("=====")):
            out.append(lines[j]); j += 1
        blob = "\n".join(out)
        m = re.search(r"body:\s*(.*)", blob, re.S)
        if not m: return None, j
        raw = m.group(1)
        # de-indent the 4-space continuation the recorder added
        raw = "\n".join(l[4:] if l.startswith("    ") else l for l in raw.splitlines())
        try: return json.loads(raw), j
        except Exception: return raw.strip(), j
    pending = []                      # FIFO queue of (method, path) awaiting responses
    while i < n:
        rm = req_re.match(lines[i])
        if rm:
            pending.append((rm.group(1), norm_path(rm.group(2))))
            i += 1; continue
        sm = resp_re.match(lines[i])
        if sm and pending:
            method, path = pending.pop(0)     # pair responses to requests in order
            status = sm.group(1).strip()
            body, j = collect_body(i + 1)
            key = f"{method} {path}"
            # prefer a real body over a previously-stored empty/error one
            better = body not in (None, "", {}) and not (isinstance(body, dict) and "error" in body)
            have_bad = key not in http or http[key].get("body") in (None, "", {}) or \
                       (isinstance(http.get(key, {}).get("body"), dict) and "error" in http[key]["body"])
            if key not in http or (better and have_bad):
                http[key] = {"status": status, "body": body}
            i = j; continue
        i += 1

# ---------------- parse hub log (WebSocket JSON-RPC) ------------------------------
def parse_hub(text, rpc, pushes):
    reqs, resps = {}, {}
    for line in text.splitlines():
        m = re.match(r"^\[[0-9:]+\] ([<>]) (\{.*\})\s*$", line)
        if not m: continue
        direction, payload = m.group(1), m.group(2)
        try: obj = json.loads(payload)
        except Exception: continue
        t = obj.get("type")
        if t == "RpcRequest" and "id" in obj:
            reqs[obj["id"]] = obj
        elif t == "RpcResponse" and "id" in obj:
            resps[obj["id"]] = obj.get("result")
        elif t and t.startswith("Lobby"):
            pushes.append(obj)
    for rid, req in reqs.items():
        ctx, meth = req.get("context"), req.get("method")
        if ctx and meth and rid in resps:
            key = f"{ctx}.{meth}"
            if key not in rpc:
                rpc[key] = resps[rid]

def parse_jsonl(path, http):
    # clean, correctly-paired captures from record_proxy's captures.jsonl
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        try: rec = json.loads(line)
        except Exception: continue
        if rec.get("json") is None:
            continue
        key = f"{rec['method']} {norm_path('/' + rec['path'].lstrip('/'))}"
        body = rec["json"]
        better = not (isinstance(body, dict) and "error" in body)
        if key not in http or (better and (isinstance(http[key].get("body"), dict) and "error" in http[key]["body"])):
            http[key] = {"status": rec.get("status", "200 OK"), "body": body}

def main():
    http, rpc, pushes = {}, {}, []
    jsonl = os.path.join(LOGDIR, "captures.jsonl")
    if os.path.exists(jsonl):
        print(f"[*] using structured captures.jsonl")
        parse_jsonl(jsonl, http)
    files = glob.glob(os.path.join(LOGDIR, "WW3_rec_*.log"))
    files = [f for f in files if not f.endswith(".SHAREABLE.log")]
    # also accept the raw record_logs naming (hub.log, meta.prod....log, etc.)
    if not files:
        files = [f for f in glob.glob(os.path.join(LOGDIR, "*.log"))
                 if not f.endswith(".SHAREABLE.log")]
    for f in files:
        text = open(f, "r", encoding="utf-8", errors="replace").read()
        base = os.path.basename(f).lower()
        if "hub" in base:
            parse_hub(text, rpc, pushes)
        elif "xmpp" in base or "session" in base or "proxy" in base:
            continue  # xmpp = encrypted; _session/proxy = duplicate/feed
        else:
            parse_http(text, http)
    # dedupe lobby pushes by type (keep one sample of each for reference)
    sample_pushes = {}
    for p in pushes:
        sample_pushes.setdefault(p.get("type"), p)
    result = {"http": http, "rpc": rpc, "lobby_push_types": sorted(sample_pushes.keys()),
              "lobby_push_samples": sample_pushes}
    json.dump(result, open(OUT, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"[OK] wrote {OUT}")
    print(f"\nHTTP endpoints captured ({len(http)}):")
    for k in sorted(http): print(f"   {k:<45} -> {http[k]['status']}")
    print(f"\nRPC methods captured ({len(rpc)}):")
    for k in sorted(rpc):
        v = json.dumps(rpc[k]) if not isinstance(rpc[k], str) else rpc[k]
        print(f"   {k:<40} -> {v[:60]}")
    print(f"\nLobby server-push types: {result['lobby_push_types']}")

if __name__ == "__main__":
    main()
