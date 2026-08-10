#!/usr/bin/env python3
"""Force a UE crash on the hung WW3 process so CrashReporter writes WW3.log.

EAC blocks ReadProcessMemory; we still try RaiseException via remote thread
so the UE fatal path can flush LogWW3ClientSynchronization into the crash log.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import subprocess
import sys
import time

PROCESS_ALL_ACCESS = 0x1F0FFF
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
PAGE_EXECUTE_READWRITE = 0x40
EXCEPTION_BREAKPOINT = 0x80000003

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll", use_last_error=True)


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wt.DWORD), ("HighPart", ctypes.c_long)]


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [("PrivilegeCount", wt.DWORD), ("Luid", LUID), ("Attributes", wt.DWORD)]


def enable_debug() -> None:
    h_token = wt.HANDLE()
    advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(), 0x28, ctypes.byref(h_token)
    )
    luid = LUID()
    advapi32.LookupPrivilegeValueW(None, "SeDebugPrivilege", ctypes.byref(luid))
    tp = TOKEN_PRIVILEGES(1, luid, 0x2)
    advapi32.AdjustTokenPrivileges(h_token, False, ctypes.byref(tp), 0, None, None)
    kernel32.CloseHandle(h_token)


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
    s = (r.stdout or "").strip()
    if not s:
        raise SystemExit("WW3 not running")
    return int(s)


def main() -> None:
    enable_debug()
    pid = find_pid()
    print("pid", pid)
    h = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    print("OpenProcess", bool(h), "err", ctypes.get_last_error())
    if not h:
        raise SystemExit(1)

    # x64 shellcode: mov ecx, EXCEPTION_BREAKPOINT; xor edx,edx; mov r8,0; mov r9,0; call RaiseException
    # Simpler: remote thread entry = kernel32!RaiseException with args on stack — hard on x64.
    # Use shellcode that calls RaiseException(0x80000003, 0, 0, 0) then int3.
    raise_exc = kernel32.GetProcAddress(
        kernel32.GetModuleHandleW("kernel32.dll"), b"RaiseException"
    )
    print(f"RaiseException=0x{raise_exc:x}")

    # shellcode (x64):
    # sub rsp, 28h
    # xor r9d, r9d
    # xor r8d, r8d
    # xor edx, edx
    # mov ecx, 0xE06D7363   ; use STATUS_BREAKPOINT instead
    # mov ecx, 0x80000003
    # mov rax, RaiseException
    # call rax
    # int3
    sc = bytearray()
    sc += b"\x48\x83\xEC\x28"  # sub rsp,0x28
    sc += b"\x45\x33\xC9"  # xor r9d,r9d
    sc += b"\x45\x33\xC0"  # xor r8d,r8d
    sc += b"\x33\xD2"  # xor edx,edx
    sc += b"\xB9\x03\x00\x00\x80"  # mov ecx, 0x80000003
    sc += b"\x48\xB8" + raise_exc.to_bytes(8, "little")  # mov rax, imm64
    sc += b"\xFF\xD0"  # call rax
    sc += b"\xCC"  # int3

    remote = kernel32.VirtualAllocEx(
        h, None, len(sc), MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE
    )
    print(f"VirtualAllocEx=0x{remote or 0:x} err={ctypes.get_last_error()}")
    if not remote:
        # fallback: NtRaiseException in-process via debug?
        print("alloc failed — trying DebugBreakProcess")
        ok = kernel32.DebugBreakProcess(h)
        print("DebugBreakProcess", ok, "err", ctypes.get_last_error())
        kernel32.CloseHandle(h)
        return

    written = ctypes.c_size_t()
    ok = kernel32.WriteProcessMemory(
        h, remote, bytes(sc), len(sc), ctypes.byref(written)
    )
    print("WriteProcessMemory", ok, "written", written.value, "err", ctypes.get_last_error())
    if not ok:
        print("WPM blocked — DebugBreakProcess fallback")
        kernel32.VirtualFreeEx(h, remote, 0, 0x8000)
        ok = kernel32.DebugBreakProcess(h)
        print("DebugBreakProcess", ok, "err", ctypes.get_last_error())
        kernel32.CloseHandle(h)
        return

    tid = wt.DWORD()
    th = kernel32.CreateRemoteThread(
        h, None, 0, remote, None, 0, ctypes.byref(tid)
    )
    print(
        "CreateRemoteThread",
        bool(th),
        "tid",
        tid.value,
        "err",
        ctypes.get_last_error(),
    )
    if th:
        kernel32.WaitForSingleObject(th, 5000)
        kernel32.CloseHandle(th)
    kernel32.CloseHandle(h)
    print("done — wait for CrashReporter / new Saved\\Crashes")


if __name__ == "__main__":
    main()
