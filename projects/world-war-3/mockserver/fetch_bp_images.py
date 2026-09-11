#!/usr/bin/env python3
"""Download Battle Pass / season CDN images into a local cache for the offline mock.

Bypasses hosts redirects by resolving api.storage.fxtools.gl via 1.1.1.1 and
fetching over TLS to that IP. Safe to re-run (skips existing files).
"""
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
    r = subprocess.run(
        ["nslookup", HOST, "1.1.1.1"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    text = r.stdout + "\n" + r.stderr
    ips = []
    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("address:"):
            ip = line.split(":", 1)[1].strip()
            if ip.count(".") == 3 and ip != "1.1.1.1":
                ips.append(ip)
        elif line.count(".") == 3 and line[0].isdigit() and line != "1.1.1.1":
            ips.append(line)
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
            # keep URL-decoded relative path; strip trailing whitespace
            out.add(urllib.parse.unquote(m.group(1)).rstrip())


def http_get(ip: str, path: str) -> tuple[int, bytes, str]:
    # path must start with /ww3-content/... ; encode spaces etc but keep /
    parts = path.split("/")
    enc = "/".join(urllib.parse.quote(p, safe="") if i else p for i, p in enumerate(parts))
    if not enc.startswith("/"):
        enc = "/" + enc
    ctx = ssl._create_unverified_context()
    s = ctx.wrap_socket(socket.create_connection((ip, 443), timeout=30), server_hostname=HOST)
    req = (
        f"GET {enc} HTTP/1.1\r\n"
        f"Host: {HOST}\r\n"
        "Connection: close\r\n"
        "User-Agent: ww3-offline-cache/1.0\r\n"
        "\r\n"
    ).encode()
    s.sendall(req)
    data = b""
    while True:
        chunk = s.recv(65536)
        if not chunk:
            break
        data += chunk
    s.close()
    head, _, body = data.partition(b"\r\n\r\n")
    status = 0
    try:
        status = int(head.split(b" ", 2)[1])
    except Exception:
        status = 0
    # handle chunked naively if needed
    ctype = "application/octet-stream"
    for line in head.split(b"\r\n"):
        if line.lower().startswith(b"content-type:"):
            ctype = line.split(b":", 1)[1].strip().decode("latin1", "replace")
        if line.lower().startswith(b"transfer-encoding:") and b"chunked" in line.lower():
            body = _dechunk(body)
    return status, body, ctype


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


def main():
    m = json.loads(MAP.read_text(encoding="utf-8"))
    paths: set[str] = set()
    collect_paths(m.get("http", {}).get("GET /season/getSeason"), paths)
    # also shop stub images
    collect_paths(m.get("http", {}).get("GET /shop/getShopItems"), paths)
    print(f"[*] unique /ww3-content paths from season/shop: {len(paths)}")
    ip = real_ip()
    print(f"[*] real {HOST} -> {ip}")
    CACHE.mkdir(parents=True, exist_ok=True)

    ok = skip = fail = 0
    for rel in sorted(paths):
        dest = CACHE / rel.replace("/", os.sep)
        if dest.exists() and dest.stat().st_size > 64:
            skip += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            status, body, ctype = http_get(ip, "/ww3-content/" + rel)
            if status != 200 or len(body) < 32:
                print(f"[!] {rel} -> HTTP {status} len={len(body)}")
                fail += 1
                continue
            # reject JSON error bodies
            if body[:1] in (b"{", b"[") and b"error" in body[:200].lower():
                print(f"[!] {rel} -> looks like JSON error")
                fail += 1
                continue
            dest.write_bytes(body)
            ok += 1
            print(f"[+] {rel} ({len(body)} bytes, {ctype})")
        except Exception as e:
            print(f"[!] {rel} -> {e}")
            fail += 1

    print(f"\n[OK] downloaded={ok} skipped={skip} failed={fail}")
    print(f"     cache: {CACHE}")


if __name__ == "__main__":
    main()
