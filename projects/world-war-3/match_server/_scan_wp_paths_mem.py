#!/usr/bin/env python3
"""Scan WW3 process memory for SoftClass package paths of BP_WP_* attachments."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as w
import re
import struct
import subprocess
import sys

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_READABLE = (0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80)


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", w.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", w.DWORD),
        ("Protect", w.DWORD),
        ("Type", w.DWORD),
    ]


def find_pids():
    out = subprocess.check_output(["tasklist", "/FO", "CSV", "/NH"], text=True, errors="replace")
    pids = []
    for line in out.splitlines():
        if "WW3" in line.upper() or "WORLD WAR" in line.upper():
            # "name","pid",...
            parts = [p.strip('"') for p in line.split('","')]
            if len(parts) >= 2 and parts[1].isdigit():
                pids.append((parts[0], int(parts[1])))
    return pids


def scan_pid(pid: int, needles: list[bytes], max_hits=40):
    h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        print("OpenProcess failed", ctypes.get_last_error())
        return []
    hits = []
    mbi = MEMORY_BASIC_INFORMATION()
    addr = 0
    ReadProcessMemory = kernel32.ReadProcessMemory
    VirtualQueryEx = kernel32.VirtualQueryEx
    buf = ctypes.create_string_buffer(1 << 20)
    while VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        base = mbi.BaseAddress or 0
        size = mbi.RegionSize or 0
        if mbi.State == MEM_COMMIT and (mbi.Protect & 0xFF) in PAGE_READABLE and size:
            # read in chunks
            off = 0
            while off < size and len(hits) < max_hits:
                chunk = min(len(buf), size - off)
                nread = ctypes.c_size_t(0)
                ok = ReadProcessMemory(
                    h, ctypes.c_void_p(base + off), buf, chunk, ctypes.byref(nread)
                )
                if ok and nread.value:
                    data = buf.raw[: nread.value]
                    for nd in needles:
                        p = 0
                        while True:
                            i = data.find(nd, p)
                            if i < 0:
                                break
                            # extract surrounding printable / utf16
                            start = max(0, i - 120)
                            end = min(len(data), i + len(nd) + 160)
                            raw = data[start:end]
                            # try utf16le around needle
                            ctx = raw.decode("utf-16le", "ignore")
                            if "BP_WP_" not in ctx and "BP_CH_" not in ctx:
                                ctx = raw.decode("ascii", "ignore")
                            hits.append((base + off + i, ctx.replace("\x00", "")[:200]))
                            if len(hits) >= max_hits:
                                break
                            p = i + len(nd)
                off += chunk
        next_addr = base + size
        if next_addr <= addr:
            break
        addr = next_addr
        if addr > 0x7FFFFFFFFFFF:
            break
    kernel32.CloseHandle(h)
    return hits


def main():
    pids = find_pids()
    print("pids", pids)
    if not pids:
        # fall back to known game pid file
        from pathlib import Path
        gp = Path("live_log/_game_pid.txt")
        if gp.exists():
            pids = [("file", int(gp.read_text().strip()))]
            print("using file pid", pids)
    needles_u16 = [
        "BP_WP_Rail_086".encode("utf-16le"),
        "BP_WP_Muzzle_020".encode("utf-16le"),
        "BP_WP_Magazine_108".encode("utf-16le"),
        "BP_WP_Barrel_033".encode("utf-16le"),
        "/Game/Blueprints/Weapons".encode("utf-16le"),
        "BP_CH_Hat_004".encode("utf-16le"),
    ]
    needles_a = [
        b"BP_WP_Rail_086",
        b"/Game/Blueprints/Weapons/Attachments",
        b"/Game/Blueprints/Weapons",
    ]
    for name, pid in pids[:2]:
        print(f"\n=== scan {name} pid={pid} ===")
        hits = scan_pid(pid, needles_u16 + needles_a, max_hits=30)
        for a, ctx in hits:
            if "BP_WP_" in ctx or "Attachments" in ctx or "Hat_004" in ctx:
                print(f"  @{a:#x}: {ctx}")


if __name__ == "__main__":
    main()
