#!/usr/bin/env python3
"""Scan a running WW3-Win64-Shipping process for Client Synchronization flag text.

Shipping often won't write Saved/Logs while hung; the sync checklist may still
exist as formatted UTF-16/ASCII in memory if LogWW3ClientSynchronization ran.

Usage (game must be running and stuck on LOADING MAP):
  python match_server/scan_sync_status.py
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import re
import subprocess
import sys

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_NOACCESS = 0x01
PAGE_GUARD = 0x100

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


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
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "(Get-Process WW3-Win64-Shipping -EA SilentlyContinue | Select -First 1).Id",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    pid = (r.stdout or "").strip()
    if not pid:
        raise SystemExit("WW3-Win64-Shipping not running")
    return int(pid)


def main() -> None:
    pid = find_pid()
    print(f"pid={pid}")
    h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        raise SystemExit(f"OpenProcess failed err={ctypes.get_last_error()}")

    ascii_needles = [
        b"Client Synchronization",
        b"MapLevels: false",
        b"MapLevels: true",
        b"InventoryManager: false",
        b"InventoryManager: true",
        b"PlayerState: false",
        b"PlayerState: true",
        b"GameState: false",
        b"GameState: true",
        b"CharacterAttachments: false",
        b"CharacterAttachments: true",
        b"WeaponsAttachments: false",
        b"WeaponsAttachments: true",
        b"Controller: true",
        b"NoPlayerState",
        b"OnSynchronized: Inventory",
        b"Missing gamestate",
        b"Deploy: IsAsyncLoading",
    ]
    wide_needles = [
        s.encode("utf-16le")
        for s in (
            "Client Synchronization",
            "MapLevels: false",
            "MapLevels: true",
            "InventoryManager: false",
            "InventoryManager: true",
            "PlayerState: false",
            "PlayerState: true",
            "GameState: false",
            "GameState: true",
            "CharacterAttachments: false",
            "WeaponsAttachments: false",
            "NoPlayerState",
            "Missing gamestate",
            "Deploy: IsAsyncLoading",
        )
    ]
    needles = ascii_needles + wide_needles
    hits = {n: 0 for n in needles}
    samples: list[tuple[bytes, str]] = []

    mbi = MEMORY_BASIC_INFORMATION()
    addr = 0
    scanned = 0
    regions = 0
    read = ctypes.c_size_t()
    while kernel32.VirtualQueryEx(h, ctypes.c_uint64(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        regions += 1
        base = mbi.BaseAddress
        size = mbi.RegionSize
        nxt = base + size
        if (
            mbi.State == MEM_COMMIT
            and not (mbi.Protect & PAGE_NOACCESS)
            and not (mbi.Protect & PAGE_GUARD)
            and 0 < size <= 64 * 1024 * 1024
        ):
            buf = (ctypes.c_char * size)()
            ok = kernel32.ReadProcessMemory(
                h, ctypes.c_uint64(base), buf, size, ctypes.byref(read)
            )
            if ok and read.value:
                data = bytes(buf[: read.value])
                scanned += read.value
                for n in needles:
                    c = data.count(n)
                    if not c:
                        continue
                    hits[n] += c
                    if len(samples) < 40:
                        i = data.find(n)
                        chunk = data[max(0, i - 60) : i + 180]
                        ascii = re.sub(rb"[^ -~\n\t]", b".", chunk).decode("ascii", "replace")
                        samples.append((n, ascii))
        addr = nxt
        if addr <= base:
            break
        if regions > 250_000:
            break

    kernel32.CloseHandle(h)
    print(f"scanned_bytes={scanned} regions={regions}")
    print("HIT COUNTS:")
    for n, c in sorted(hits.items(), key=lambda x: -x[1]):
        if not c:
            continue
        if b"\x00" in n[:4] or (len(n) > 2 and n[1] == 0):
            label = n.decode("utf-16le", "replace")
        else:
            label = n.decode("latin1", "replace")
        print(f"  {c:5} {label!r}")
    print("\nSAMPLES:")
    for n, a in samples[:25]:
        print("---", n[:48])
        print(a)


if __name__ == "__main__":
    main()
