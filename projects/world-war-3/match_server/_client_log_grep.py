#!/usr/bin/env python3
"""Grep the live WW3 client's heap for its own formatted UE log lines.

The shipping client writes no `Saved/Logs` file, but the formatted log strings
still live in the process heap (that is how `_sync_checklist.py` reads the
Client Synchronization block).  This generalises that trick: give it patterns,
get back every distinct log line the client has formatted this run.

Usage:
    python match_server/_client_log_grep.py                 # default patterns
    python match_server/_client_log_grep.py --pat "BP_WP_"  # extra pattern
    python match_server/_client_log_grep.py --raw           # no dedupe/sort
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import re
import subprocess
import sys

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
PAGE_NOACCESS = 0x01

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

DEFAULT_PATTERNS = (
    r"OnAttachmentManagerSynchronized\(\)[^\r\n]{0,120}",
    r"OnSynchronized: [^\r\n]{0,80}",
    r"AttachmentsStructure\.Attachments[^\r\n]{0,60}",
    r"GetMutableBatch\(\)\.AttachmentIds[^\r\n]{0,40}",
    r"Server_OnClientPreloadWeaponsFinished[^\r\n]{0,60}",
    r"SetNewPlayerState\][^\r\n]{0,90}",
    r"EWW3AudioMediatorEvent::MapLoading[^\r\n]{0,20}",
    r"BP_WP_[A-Za-z]+_\d+[A-Za-z0-9_]{0,30}",
    r"CreateAttachment[A-Za-z]{0,30}",
    r"AWW3InventoryWeapon::[A-Za-z_]{0,50}",
)


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_uint64),
        ("AllocationBase", ctypes.c_uint64),
        ("AllocationProtect", wt.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wt.DWORD),
        ("Protect", wt.DWORD),
        ("Type", wt.DWORD),
    ]


def find_pid() -> int:
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process WW3-Win64-Shipping -EA SilentlyContinue | Select -First 1).Id"],
        capture_output=True, text=True, check=False)
    pid = (r.stdout or "").strip()
    if not pid:
        raise SystemExit("WW3-Win64-Shipping not running")
    return int(pid)


def scan(pid: int, patterns: list[str], limit: int) -> dict[str, list[int]]:
    rx = re.compile("|".join(f"(?:{p})" for p in patterns))
    h = kernel32.OpenProcess(
        PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        raise SystemExit(f"OpenProcess failed {ctypes.get_last_error()}")
    hits: dict[str, list[int]] = {}
    mbi = MEMORY_BASIC_INFORMATION()
    addr = 0
    read = ctypes.c_size_t(0)
    while addr < 0x7FFFFFFFFFFF:
        if not kernel32.VirtualQueryEx(h, ctypes.c_uint64(addr),
                                       ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        base, size = mbi.BaseAddress, mbi.RegionSize
        nxt = base + size
        ok = (mbi.State == MEM_COMMIT
              and not (mbi.Protect & (PAGE_GUARD | PAGE_NOACCESS))
              and size <= (256 << 20))
        if ok:
            buf = (ctypes.c_char * size)()
            if kernel32.ReadProcessMemory(h, ctypes.c_uint64(base), buf, size,
                                          ctypes.byref(read)) and read.value:
                data = bytes(buf[:read.value])
                for text in (data.decode("latin-1", "replace"),
                             data.decode("utf-16le", "replace")):
                    for m in rx.finditer(text):
                        s = m.group(0).strip()
                        if len(s) < 6:
                            continue
                        slot = hits.setdefault(s, [])
                        if len(slot) < 3:
                            slot.append(base)
                        if len(hits) >= limit:
                            kernel32.CloseHandle(h)
                            return hits
        addr = nxt
        if addr == 0:
            break
    kernel32.CloseHandle(h)
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, default=None)
    ap.add_argument("--pat", action="append", default=[],
                    help="extra regex (repeatable); replaces defaults with --only")
    ap.add_argument("--only", action="store_true",
                    help="use only --pat patterns")
    ap.add_argument("--limit", type=int, default=20000)
    args = ap.parse_args()

    pats = list(args.pat) if args.only else list(DEFAULT_PATTERNS) + list(args.pat)
    if not pats:
        raise SystemExit("no patterns")
    pid = args.pid or find_pid()
    print(f"pid={pid}  patterns={len(pats)}")
    hits = scan(pid, pats, args.limit)
    if not hits:
        print("no matching log text in memory")
        return 1
    for s in sorted(hits):
        addrs = " ".join(f"0x{a:x}" for a in hits[s])
        print(f"  {s}    [{addrs}]")
    print(f"\n{len(hits)} distinct strings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
