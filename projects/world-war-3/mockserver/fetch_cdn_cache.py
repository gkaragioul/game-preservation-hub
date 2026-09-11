#!/usr/bin/env python3
"""Fetch ALL /ww3-content/ URLs referenced by replay_map.json into content_cache/."""
from __future__ import annotations

import json
import os
import re
import socket
import ssl
import subprocess
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAP = HERE / "replay_map.json"
CACHE = HERE / "content_cache" / "ww3-content"
HOST = "api.storage.fxtools.gl"


def real_ip() -> str:
    r = subprocess.run(["nslookup", HOST, "1.1.1.1"], capture_output=True, text=True, timeout=15)
    text = r.stdout + "\n" + r.stderr
    ips = []
    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("address:"):
            ip = line.split(":", 1)[1].strip()
            if ip.count(".") == 3 and ip != "1.1.1.1":
                ips.append(ip)
    if not ips:
        raise RuntimeError("could not resolve real storage IP")
    return ips[-1]


def collect_paths(obj, out: set[str]):
    if isinstance(obj, dict):
        for v in obj.values():
            collect_paths(v, out)
    elif isinstance(obj, list):
        for v in obj:
            collect_paths(v, out)
    elif isinstance(obj, str) and "/ww3-content/" in obj:
        m = re.search(r"/ww3-content/([^?#]+)", obj)
        if m:
            out.add(urllib.parse.unquote(m.group(1)).rstrip())


def _dechunk(body: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(body):
        j = body.find(b"\r\n", i)
        if j < 0:
            break
        try:
            n = int(body[i:j], 16)
        except ValueError:
            break
        i = j + 2
        if n == 0:
            break
        out.extend(body[i : i + n])
        i = i + n + 2
    return bytes(out)


def http_get(ip: str, rel: str) -> tuple[int, bytes]:
    enc = "/ww3-content/" + "/".join(urllib.parse.quote(p, safe="") for p in rel.split("/"))
    ctx = ssl._create_unverified_context()
    s = ctx.wrap_socket(socket.create_connection((ip, 443), timeout=30), server_hostname=HOST)
    req = f"GET {enc} HTTP/1.1\r\nHost: {HOST}\r\nConnection: close\r\nUser-Agent: ww3-cdn-cache/1.0\r\n\r\n".encode()
    s.sendall(req)
    data = b""
    while True:
        c = s.recv(65536)
        if not c:
            break
        data += c
    s.close()
    head, _, body = data.partition(b"\r\n\r\n")
    try:
        status = int(head.split(b" ", 2)[1])
    except Exception:
        status = 0
    if b"transfer-encoding:" in head.lower() and b"chunked" in head.lower():
        body = _dechunk(body)
    return status, body


def main():
    m = json.loads(MAP.read_text(encoding="utf-8"))
    paths: set[str] = set()
    collect_paths(m, paths)
    print(f"[*] unique /ww3-content paths in replay_map: {len(paths)}")
    ip = real_ip()
    print(f"[*] {HOST} -> {ip}")
    CACHE.mkdir(parents=True, exist_ok=True)
    ok = skip = fail = 0
    for rel in sorted(paths):
        dest = CACHE / rel.replace("/", os.sep)
        if dest.exists() and dest.stat().st_size > 64:
            skip += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            status, body = http_get(ip, rel)
            if status != 200 or len(body) < 32 or body[:1] in (b"{", b"["):
                print(f"[!] {rel} -> HTTP {status} len={len(body)}")
                fail += 1
                continue
            dest.write_bytes(body)
            ok += 1
            print(f"[+] {rel} ({len(body)} b)")
        except Exception as e:
            print(f"[!] {rel} -> {e}")
            fail += 1
    print(f"\n[OK] downloaded={ok} skipped={skip} failed={fail}\n     {CACHE}")


if __name__ == "__main__":
    main()
