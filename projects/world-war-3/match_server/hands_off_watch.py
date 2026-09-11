#!/usr/bin/env python3
"""Hands-off match watcher — network/logs only. No keyboard/mouse.

Polls hub :8701 and match console. When a client hits UDP 7871, reports
AckPossession / channel C→S signals. Does not synthesize input.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MS = ROOT / "match_server"
LOG = MS / "live_log"
HUB = "http://127.0.0.1:8701"


def http_get(path: str) -> dict | None:
    try:
        with urllib.request.urlopen(f"{HUB}{path}", timeout=3) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"[hub] {path} fail: {e}")
        return None


def console_path() -> Path | None:
    p = LOG / "CURRENT_CONSOLE.txt"
    if not p.exists():
        return None
    return Path(p.read_text(encoding="utf-8", errors="replace").strip())


def tail_text(path: Path, n: int = 80) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except Exception:
        return ""


def main() -> int:
    timeout = float(sys.argv[1]) if len(sys.argv) > 1 else 180.0
    print(f"[watch] network-only, timeout={timeout}s (no KBM)")
    st = http_get("/status")
    print(f"[watch] hub status={st}")
    # Arm match handoff if client already on hub (ignored until findLobby — still OK to fire)
    m = http_get("/match")
    print(f"[watch] /match -> {m}")

    t0 = time.time()
    saw_client = False
    while time.time() - t0 < timeout:
        cp = console_path()
        text = tail_text(cp) if cp else ""
        if "Hello from" in text or "NMT_Login" in text or "Welcome" in text or "client" in text.lower() and "connected" in text.lower():
            if not saw_client and ("Welcome" in text or "Login" in text or "handshake" in text.lower()):
                saw_client = True
                print("[watch] match traffic detected")
                print(text[-1500:])
        if "AckPossession(Pawn" in text:
            print("[watch] SUCCESS AckPossession(Pawn)")
            print(text[-2000:])
            return 0
        if "CHANNEL CLOSE" in text or "lobby kick" in text.lower():
            print("[watch] notable close/kick")
            print(text[-1500:])
        time.sleep(2.0)

    cp = console_path()
    print("[watch] TIMEOUT — last console:")
    print(tail_text(cp, 40) if cp else "(no console)")
    print("[watch] Client must call findLobbyForParty (Quick Play). Hub force-push alone is ignored.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
