#!/usr/bin/env python3
"""Restore match server with Ack-OK hist+warm (dead-pid safe).

Pins locked baseline; no SPAWN_ATTACH; STUB_4606=0. Does not launch game.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG = HERE / "live_log"

# Mirror BASE + softclass_hist074114_warm from _restart_spawn_attach.py
ENV = {
    "WW3_BOOTSTRAP": "ownership",
    "WW3_PAWN_EXPORT_PREFIX": "1",
    "WW3_CLIENT_RESTART": "1",
    "WW3_CLIENT_RESTART_MUSTMAP": "0",
    "WW3_CLIENT_RESTART_SEND_RETRY": "0",
    "WW3_CLIENT_RESTART_MAX_SPRAYS": "1",
    "WW3_PC_SET_PAWN": "0",
    "WW3_PAWN_SYNTH_PROPS": "0",
    "WW3_PAWN_SYNTH_IN_OPEN": "0",
    "WW3_PS_SET_PLAYERCHAR": "0",
    "WW3_PS_REBIND": "0",
    "WW3_PAWN_NO_SCALE": "0",
    "WW3_ACK_AUDIT": "1",
    "WW3_AMBIENT_LIMIT": "0",
    "WW3_AMBIENT_CHANNELS": "all",
    "WW3_STREAMING_PAUSE_MS": "15000",
    "WW3_WAIT_GAMEPLAY_DOM": "1",
    "WW3_FORCE_MAP": "WW3_Gobi_New_P",
    "WW3_WAM_SPAWN_ATTACH": "0",
    "WW3_WAM_KEEP_DYNAMIC": "0",
    "WW3_WAM_KEEP_CLOTHING": "0",
    "WW3_WAM_SOFTCLASS_CATALOG": "0",
    "WW3_WAM_SOFTCLASS_EXPORT": "0",
    "WW3_WAM_SOFTCLASS_WARM_EXPORT": "1",
    "WW3_WAM_SOFTCLASS_STUB_4606": "0",
    "WW3_WAM_SOFTCLASS_POST_STUB_4606": "0",
    "WW3_WAM_SOFTCLASS_MODE": "full",
    "WW3_WAM_SOFTCLASS_OPEN_ONLY": "0",
    "WW3_WAM_SOFTCLASS_KEEP_SKINS": "0",
    "WW3_WAM_EARLY_EMPTY_PARTS_REINFORCE": "1",
    "WW3_ISOLATE_EARLY_WPN": "1",
    "WW3_WAM_STRIP_CATALOG": "1",
    "WW3_WAM_STRIP_CHANNELS": "inv",
    "WW3_CAM_STRIP_CATALOG": "1",
    "WW3_WPN_ATTACH": "1",
    "WW3_INV_ATTACH": "1",
    "WW3_CAM_IM_AFTER_ACK": "1",
    "WW3_CLOTHING_RESEND": "1",
    "WW3_WAM_SPAWN_CHANNELS": "all",
    "WW3_WAM_SPAWN_HOST": "weapon",
    "WW3_WAM_SPAWN_STRIP_KEEP": "0",
}


def kill_match() -> None:
    r = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" |"
                " Where-Object { $_.CommandLine -match 'server\\.py.*7871' } |"
                " ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }"
            ),
        ],
        check=False,
    )
    _ = r
    time.sleep(1.0)


def main() -> int:
    LOG.mkdir(parents=True, exist_ok=True)
    kill_match()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    console = LOG / f"match_console_{stamp}.out.txt"
    (LOG / "CURRENT_CONSOLE.txt").write_text(str(console), encoding="utf-8")

    new_env = os.environ.copy()
    for k in list(new_env):
        if k.startswith("WW3_"):
            del new_env[k]
    new_env.update(ENV)
    new_env["PYTHONUNBUFFERED"] = "1"

    print("restoring match softclass_hist074114_warm + Ack-OK BASE:")
    for k in sorted(ENV):
        print(f"  {k}={ENV[k]}")

    out = open(console, "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        [sys.executable, "-u", str(HERE / "server.py"), "7871"],
        cwd=str(HERE),
        env=new_env,
        stdout=out,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
    )
    (LOG / "_match_pid.txt").write_text(str(proc.pid), encoding="utf-8")
    time.sleep(2.0)
    print(f"match_pid={proc.pid} console={console} poll={proc.poll()}")
    if proc.poll() is not None:
        print(console.read_text(encoding="utf-8", errors="replace")[-2000:])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
