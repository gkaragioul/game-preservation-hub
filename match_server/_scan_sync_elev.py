#!/usr/bin/env python3
"""Elevated Client-Sync memory scan (SeDebugPrivilege + PROCESS_ALL_ACCESS)."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import re
import subprocess
import sys

PROCESS_ALL_ACCESS = 0x1F0FFF
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_NOACCESS = 0x01
PAGE_GUARD = 0x100

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wt.DWORD), ("HighPart", ctypes.c_long)]


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [("PrivilegeCount", wt.DWORD), ("Luid", LUID), ("Attributes", wt.DWORD)]


class MBI(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_uint64),
        ("AllocationBase", ctypes.c_uint64),
        ("AllocationProtect", wt.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wt.DWORD),
        ("Protect", wt.DWORD),
        ("Type", wt.DWORD),
    ]


def enable_debug() -> None:
    TOKEN_ADJUST_PRIVILEGES = 0x0020
    TOKEN_QUERY = 0x0008
    SE_PRIVILEGE_ENABLED = 0x2
    h_token = wt.HANDLE()
    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(),
        TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
        ctypes.byref(h_token),
    ):
        print("OpenProcessToken fail", ctypes.get_last_error())
        return
    luid = LUID()
    if not advapi32.LookupPrivilegeValueW(None, "SeDebugPrivilege", ctypes.byref(luid)):
        print("LookupPrivilegeValue fail", ctypes.get_last_error())
        return
    tp = TOKEN_PRIVILEGES(1, luid, SE_PRIVILEGE_ENABLED)
    ok = advapi32.AdjustTokenPrivileges(h_token, False, ctypes.byref(tp), 0, None, None)
    print("SeDebugPrivilege", "ok" if ok else "fail", "err", ctypes.get_last_error())
    kernel32.CloseHandle(h_token)


def main() -> None:
    enable_debug()
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
    pid_s = (r.stdout or "").strip()
    if not pid_s:
        raise SystemExit("WW3 not running")
    pid = int(pid_s)
    print("pid", pid)

    h = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    print("OpenProcess ALL_ACCESS", bool(h), "err", ctypes.get_last_error())
    if not h:
        h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        print("OpenProcess QUERY|VM_READ", bool(h), "err", ctypes.get_last_error())
    if not h:
        raise SystemExit(1)

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
        b"Missing gamestate",
        b"Deploy: IsAsyncLoading",
        b"OnSynchronized",
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
            "CharacterAttachments: true",
            "WeaponsAttachments: false",
            "WeaponsAttachments: true",
            "NoPlayerState",
            "Missing gamestate",
            "Deploy: IsAsyncLoading",
            "OnSynchronized",
        )
    ]
    needles = ascii_needles + wide_needles
    hits = {n: 0 for n in needles}
    samples: list[tuple[bytes, str]] = []

    mbi = MBI()
    addr = 0
    commit = readable = read_ok = read_fail = scanned = 0
    readn = ctypes.c_size_t()
    protect_hist: dict[int, int] = {}
    while kernel32.VirtualQueryEx(h, ctypes.c_uint64(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        base = mbi.BaseAddress
        size = mbi.RegionSize
        nxt = base + size
        if mbi.State == MEM_COMMIT:
            commit += 1
            prot = mbi.Protect
            protect_hist[prot] = protect_hist.get(prot, 0) + 1
            if (
                not (prot & PAGE_NOACCESS)
                and not (prot & PAGE_GUARD)
                and 0 < size <= 64 * 1024 * 1024
            ):
                readable += 1
                buf = (ctypes.c_char * size)()
                ok = kernel32.ReadProcessMemory(
                    h, ctypes.c_uint64(base), buf, size, ctypes.byref(readn)
                )
                if ok and readn.value:
                    read_ok += 1
                    data = bytes(buf[: readn.value])
                    scanned += readn.value
                    for n in needles:
                        c = data.count(n)
                        if not c:
                            continue
                        hits[n] += c
                        if len(samples) < 25:
                            i = data.find(n)
                            chunk = re.sub(
                                rb"[^ -~\n\t]", b".", data[max(0, i - 40) : i + 160]
                            ).decode("ascii", "replace")
                            samples.append((n, chunk))
                else:
                    read_fail += 1
                    if read_fail <= 8:
                        print(
                            f"RPM fail base=0x{base:x} size={size} "
                            f"prot=0x{prot:x} err={ctypes.get_last_error()}"
                        )
        addr = nxt
        if addr <= base:
            break

    kernel32.CloseHandle(h)
    print(
        f"commit={commit} readable_try={readable} read_ok={read_ok} "
        f"read_fail={read_fail} scanned={scanned}"
    )
    print("protect top", sorted(protect_hist.items(), key=lambda x: -x[1])[:12])
    print("HITS:")
    for n, c in sorted(hits.items(), key=lambda x: -x[1]):
        if not c:
            continue
        lab = (
            n.decode("utf-16le", "replace")
            if (len(n) > 2 and n[1] == 0)
            else n.decode("latin1", "replace")
        )
        print(f"  {c} {lab!r}")
    print("SAMPLES:")
    for n, a in samples:
        print("---", n[:48])
        print(a)


if __name__ == "__main__":
    main()
