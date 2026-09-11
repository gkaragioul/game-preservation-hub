#!/usr/bin/env python3
"""Restart match server.py on :7871, preserving WW3_* env from the old pid."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from _read_proc_env import read_env

HERE = Path(__file__).resolve().parent
LOG = HERE / "live_log"


def main(argv=None) -> int:
    # The preserved WW3_* set wins over the caller's shell, so a flag that already
    # exists on the old pid cannot be changed by exporting it.  --set is the override.
    overrides: dict[str, str] = {}
    for arg in (argv if argv is not None else sys.argv[1:]):
        if arg.startswith("--set="):
            k, _, v = arg[len("--set="):].partition("=")
            overrides[k] = v
    pid_path = LOG / "_match_pid.txt"
    old_pid = int(pid_path.read_text(encoding="utf-8").strip()) if pid_path.exists() else None
    if old_pid is None:
        # fall back: find listener
        raise SystemExit("no _match_pid.txt")
    env = read_env(old_pid)
    ww3 = {k: v for k, v in env.items() if k.startswith("WW3_")}
    print(f"old_pid={old_pid} ww3_flags={len(ww3)}")
    for k in sorted(ww3):
        print(f"  {k}={ww3[k]}")

    # kill old
    subprocess.run(["taskkill", "/PID", str(old_pid), "/F"], check=False)
    time.sleep(1.0)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    console = LOG / f"match_console_{stamp}.out.txt"
    new_env = os.environ.copy()
    new_env.update(ww3)
    if overrides:
        new_env.update(overrides)
        print("overrides: " + " ".join(f"{k}={v}" for k, v in sorted(overrides.items())))
    # ensure python unbuffered
    new_env["PYTHONUNBUFFERED"] = "1"
    out = open(console, "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        [sys.executable, "-u", str(HERE / "server.py"), "7871"],
        cwd=str(HERE),
        env=new_env,
        stdout=out,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
    )
    pid_path.write_text(str(proc.pid), encoding="utf-8")
    (LOG / "CURRENT_CONSOLE.txt").write_text(str(console), encoding="utf-8")
    time.sleep(1.5)
    alive = proc.poll() is None
    print(f"new_pid={proc.pid} alive={alive} console={console}")
    if not alive:
        print(console.read_text(encoding="utf-8", errors="replace")[-2000:])
        return 1
    # smoke: flags line
    text = console.read_text(encoding="utf-8", errors="replace")
    print("--- console head ---")
    print("\n".join(text.splitlines()[:35]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
