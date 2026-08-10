#!/usr/bin/env python3
"""Dump WW3's formatted "Client Synchronization" checklist from the live client.

`scan_sync_status.py` proves the strings exist; this prints the *formatted*
instances in full so the exact false item can be read off.  The checklist is the
LoadingMap gate: the loading screen stays up until every line is true.

Usage:
    python match_server/_sync_checklist.py
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

ITEMS = ("Controller", "PlayerState", "InventoryManager", "CharacterAttachments",
         "WeaponsAttachments", "GameState", "LocalClientConfigs", "MapLevels")


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


STAMP = re.compile(r"\[(\d{4}\.\d\d\.\d\d-[\d.:]+)]")


def blocks_from(text: str) -> list[tuple[str, dict[str, str]]]:
    """Pull `Item: value` pairs, plus the UE log stamp that orders the snapshots."""
    out = []
    # Anchor on the first checklist item rather than the header: the header can sit
    # in a different allocation, and only the item lines matter.
    for m in re.finditer(r"PlayerState: (?:true|false)", text):
        window = text[max(0, m.start() - 120):m.start() + 700]
        # A format-string template still has %s placeholders; skip those.
        state = {}
        for item in ITEMS:
            hit = re.search(rf"{item}: (true|false|%s|[A-Za-z_]+)", window)
            if hit:
                state[item] = hit.group(1)
        if not state or "%s" in state.values():
            continue
        prefix = text[max(0, m.start() - 120):m.start()]
        stamps = STAMP.findall(prefix)
        out.append((stamps[-1] if stamps else "", state))
    return out


def main() -> int:
    pid = find_pid()
    print(f"pid={pid}")
    h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        raise SystemExit(f"OpenProcess failed err={ctypes.get_last_error()}")

    mbi = MEMORY_BASIC_INFORMATION()
    addr = 0
    found: list[tuple[str, int, dict[str, str]]] = []
    read = ctypes.c_size_t()
    while kernel32.VirtualQueryEx(h, ctypes.c_uint64(addr), ctypes.byref(mbi),
                                  ctypes.sizeof(mbi)):
        base, size = mbi.BaseAddress, mbi.RegionSize
        nxt = base + size
        if (mbi.State == MEM_COMMIT and not (mbi.Protect & PAGE_NOACCESS)
                and not (mbi.Protect & PAGE_GUARD) and 0 < size <= 64 * 1024 * 1024):
            buf = (ctypes.c_char * size)()
            if kernel32.ReadProcessMemory(h, ctypes.c_uint64(base), buf, size,
                                          ctypes.byref(read)) and read.value:
                data = bytes(buf[:read.value])
                if b"PlayerState: " in data or \
                        "PlayerState: ".encode("utf-16le") in data:
                    for text in (data.decode("latin-1", "replace"),
                                 data.decode("utf-16le", "replace")):
                        for stamp, state in blocks_from(text):
                            found.append((stamp, base, state))
        addr = nxt
        if addr == 0:
            break

    if not found:
        print("no formatted checklist in memory")
        return 1
    seen = set()
    for stamp, base, state in sorted(found, key=lambda r: r[0]):
        key = tuple(sorted(state.items()))
        if key in seen:
            continue
        seen.add(key)
        false_items = [k for k, v in state.items() if v == "false"]
        print(f"\n--- checklist @0x{base:x} stamp={stamp or '?'} ---")
        for item in ITEMS:
            if item in state:
                mark = "OK " if state[item] == "true" else "!! "
                print(f"  {mark}{item}: {state[item]}")
        print(f"  BLOCKING: {false_items or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
