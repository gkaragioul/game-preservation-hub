#!/usr/bin/env python3
"""Dump WW3_* environment variables of a *running* process (Windows, same user).

Root-cause tool: our match server's flags come from the launcher's env, so a
console log alone can't prove which flags were live. Reads PEB ->
RTL_USER_PROCESS_PARAMETERS -> Environment out of the target process.

Usage: python _read_proc_env.py <pid> [prefix]
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010


class PROCESS_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("Reserved1", ctypes.c_void_p),
        ("PebBaseAddress", ctypes.c_void_p),
        ("Reserved2", ctypes.c_void_p * 2),
        ("UniqueProcessId", ctypes.c_void_p),
        ("Reserved3", ctypes.c_void_p),
    ]


def read_env(pid: int) -> dict[str, str]:
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    nt = ctypes.WinDLL("ntdll", use_last_error=True)
    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        raise OSError(f"OpenProcess({pid}) failed: {ctypes.get_last_error()}")
    try:
        pbi = PROCESS_BASIC_INFORMATION()
        rl = ctypes.c_ulong()
        if nt.NtQueryInformationProcess(h, 0, ctypes.byref(pbi),
                                        ctypes.sizeof(pbi), ctypes.byref(rl)):
            raise OSError("NtQueryInformationProcess failed")

        def rd(addr, size):
            buf = (ctypes.c_char * size)()
            n = ctypes.c_size_t()
            if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size,
                                         ctypes.byref(n)):
                raise OSError(f"ReadProcessMemory @{addr:#x} failed")
            return bytes(buf[:n.value])

        peb = ctypes.cast(pbi.PebBaseAddress, ctypes.c_void_p).value
        # x64 PEB: +0x20 ProcessParameters
        params = int.from_bytes(rd(peb + 0x20, 8), "little")
        # RTL_USER_PROCESS_PARAMETERS x64: +0x80 Environment, +0x3F0 EnvironmentSize
        env_addr = int.from_bytes(rd(params + 0x80, 8), "little")
        env_size = int.from_bytes(rd(params + 0x3F0, 8), "little")
        if not 0 < env_size < (1 << 22):
            env_size = 1 << 16
        raw = rd(env_addr, env_size).decode("utf-16-le", "replace")
    finally:
        k32.CloseHandle(h)
    out: dict[str, str] = {}
    for entry in raw.split("\x00"):
        if "=" in entry[1:]:
            k, _, v = entry.partition("=")
            out[k] = v
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    pid = int(sys.argv[1])
    prefix = sys.argv[2] if len(sys.argv) > 2 else "WW3_"
    env = read_env(pid)
    hits = {k: v for k, v in env.items() if k.startswith(prefix)}
    print(f"pid={pid} total_env={len(env)} matching '{prefix}': {len(hits)}")
    for k in sorted(hits):
        print(f"  {k}={hits[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
