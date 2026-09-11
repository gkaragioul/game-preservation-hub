#!/usr/bin/env python3
r"""Name the function a live WW3 thread is executing, without a debugger.

Why
---
Measured across six sessions, the client's network thread stops permanently
2.7-3.8 s after the ch3 pawn channel opens, while exactly one thread keeps
burning ~99% of a core (`Responding=False`, memory and handle count flat). That
is an infinite loop on the game thread, and it makes every later experiment --
the ch80 open, the action probe, the profile tail -- land in a client that
cannot process anything. Fixing it is upstream of the whole squad-graph effort,
so the loop has to be named.

`_force_ue_crash.py` already established that this build's EAC blocks
`WriteProcessMemory` (err=998) and no-ops `DebugBreakProcess`, so no debugger can
attach. But naming a loop only needs the thread's RIP:

    OpenThread(THREAD_GET_CONTEXT|THREAD_QUERY_INFORMATION|THREAD_SUSPEND_RESUME)
    SuspendThread -> GetThreadContext -> ResumeThread

The suspend window is a few microseconds and the thread is put straight back, so
this observes the client rather than changing it. Samples repeatedly, because one
RIP from a loop body is an address while a histogram is a diagnosis.

RIP is then resolved through the main module's `.pdata` (`_exe_fn.FnIndex`) to the
containing function, so the answer is "this loop is in function 0x1409xxxxx",
which `_fn_dump.py` can then disassemble.

Usage:
    python match_server/_thread_rip.py                       # busiest thread
    python match_server/_thread_rip.py --tid 75596 --samples 40
    python match_server/_thread_rip.py --all                 # every running thread
"""
from __future__ import annotations

import argparse
import collections
import ctypes
import ctypes.wintypes as wt
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _exe_fn import FnIndex  # noqa: E402
from _exe_pe import PE  # noqa: E402
from _ps_sync_live import find_pid, main_module  # noqa: E402

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

THREAD_GET_CONTEXT = 0x0008
THREAD_SUSPEND_RESUME = 0x0002
THREAD_QUERY_INFORMATION = 0x0040
CONTEXT_CONTROL = 0x00100001
TH32CS_SNAPTHREAD = 0x00000004


class THREADENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD),
                ("th32ThreadID", wt.DWORD), ("th32OwnerProcessID", wt.DWORD),
                ("tpBasePri", ctypes.c_long), ("tpDeltaPri", ctypes.c_long),
                ("dwFlags", wt.DWORD)]


class M128A(ctypes.Structure):
    _fields_ = [("Low", ctypes.c_ulonglong), ("High", ctypes.c_longlong)]


class CONTEXT64(ctypes.Structure):
    """Only the fields up to Rip matter here; the rest is padding to the real size."""
    _pack_ = 16
    _fields_ = [
        ("P1Home", ctypes.c_ulonglong), ("P2Home", ctypes.c_ulonglong),
        ("P3Home", ctypes.c_ulonglong), ("P4Home", ctypes.c_ulonglong),
        ("P5Home", ctypes.c_ulonglong), ("P6Home", ctypes.c_ulonglong),
        ("ContextFlags", wt.DWORD), ("MxCsr", wt.DWORD),
        ("SegCs", wt.WORD), ("SegDs", wt.WORD), ("SegEs", wt.WORD),
        ("SegFs", wt.WORD), ("SegGs", wt.WORD), ("SegSs", wt.WORD),
        ("EFlags", wt.DWORD),
        ("Dr0", ctypes.c_ulonglong), ("Dr1", ctypes.c_ulonglong),
        ("Dr2", ctypes.c_ulonglong), ("Dr3", ctypes.c_ulonglong),
        ("Dr6", ctypes.c_ulonglong), ("Dr7", ctypes.c_ulonglong),
        ("Rax", ctypes.c_ulonglong), ("Rcx", ctypes.c_ulonglong),
        ("Rdx", ctypes.c_ulonglong), ("Rbx", ctypes.c_ulonglong),
        ("Rsp", ctypes.c_ulonglong), ("Rbp", ctypes.c_ulonglong),
        ("Rsi", ctypes.c_ulonglong), ("Rdi", ctypes.c_ulonglong),
        ("R8", ctypes.c_ulonglong), ("R9", ctypes.c_ulonglong),
        ("R10", ctypes.c_ulonglong), ("R11", ctypes.c_ulonglong),
        ("R12", ctypes.c_ulonglong), ("R13", ctypes.c_ulonglong),
        ("R14", ctypes.c_ulonglong), ("R15", ctypes.c_ulonglong),
        ("Rip", ctypes.c_ulonglong),
        ("FltSave", ctypes.c_byte * 512),
        ("VectorRegister", M128A * 26), ("VectorControl", ctypes.c_ulonglong),
        ("DebugControl", ctypes.c_ulonglong), ("LastBranchToRip", ctypes.c_ulonglong),
        ("LastBranchFromRip", ctypes.c_ulonglong), ("LastExceptionToRip", ctypes.c_ulonglong),
        ("LastExceptionFromRip", ctypes.c_ulonglong),
    ]


def thread_ids(pid: int) -> list[int]:
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    if snap == -1:
        raise SystemExit("CreateToolhelp32Snapshot failed")
    out: list[int] = []
    te = THREADENTRY32()
    te.dwSize = ctypes.sizeof(THREADENTRY32)
    kernel32.Thread32First.argtypes = [wt.HANDLE, ctypes.POINTER(THREADENTRY32)]
    kernel32.Thread32Next.argtypes = [wt.HANDLE, ctypes.POINTER(THREADENTRY32)]
    ok = kernel32.Thread32First(snap, ctypes.byref(te))
    while ok:
        if te.th32OwnerProcessID == pid:
            out.append(te.th32ThreadID)
        ok = kernel32.Thread32Next(snap, ctypes.byref(te))
    kernel32.CloseHandle(snap)
    return out


def sample_context(tid: int) -> tuple[int, int] | None:
    """Suspend just long enough to read (Rip, Rsp), then resume. None if denied."""
    h = kernel32.OpenThread(
        THREAD_GET_CONTEXT | THREAD_QUERY_INFORMATION | THREAD_SUSPEND_RESUME,
        False, tid)
    if not h:
        return None
    try:
        if kernel32.SuspendThread(h) == 0xFFFFFFFF:
            return None
        try:
            ctx = CONTEXT64()
            ctx.ContextFlags = CONTEXT_CONTROL
            if not kernel32.GetThreadContext(h, ctypes.byref(ctx)):
                return None
            return int(ctx.Rip), int(ctx.Rsp)
        finally:
            kernel32.ResumeThread(h)
    finally:
        kernel32.CloseHandle(h)


def sample_rip(tid: int) -> int | None:
    got = sample_context(tid)
    return got[0] if got else None


def busiest_thread(pid: int, window_s: float = 2.0) -> int | None:
    """The thread accumulating the most CPU over `window_s` -- the spinner."""
    import subprocess
    ps = (f"$p=Get-Process -Id {pid}; $a=@{{}}; foreach($t in $p.Threads)"
          f"{{$a[$t.Id]=$t.TotalProcessorTime.TotalMilliseconds}};"
          f"Start-Sleep -Milliseconds {int(window_s*1000)}; $p.Refresh();"
          "$b=foreach($t in $p.Threads){if($a.ContainsKey($t.Id)){"
          "[pscustomobject]@{Id=$t.Id;D=($t.TotalProcessorTime.TotalMilliseconds-$a[$t.Id])}}};"
          "($b|Sort-Object D -Descending|Select-Object -First 1).Id")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True, check=False)
    txt = (r.stdout or "").strip()
    return int(txt) if txt.isdigit() else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tid", type=int, default=None)
    ap.add_argument("--samples", type=int, default=25)
    ap.add_argument("--all", action="store_true", help="sample every thread once")
    ap.add_argument("--stack", action="store_true",
                    help="scan the thread stack for return addresses (pseudo call chain)")
    ap.add_argument("--stack-bytes", type=int, default=0x4000)
    args = ap.parse_args()

    pid = find_pid()
    base, size = main_module(pid)
    pe = PE()
    idx = FnIndex(pe)

    def describe(rip: int) -> str:
        if not (base <= rip < base + size):
            return f"{rip:#x}  (outside the main module)"
        # The PE index is built at the image's preferred base; live RIPs are at
        # the load base, so rebase before asking .pdata.
        static = rip - base + pe.image_base
        fn = idx.primary(static)
        where = f"fn {fn.beg:#x}+{static - fn.beg:#x}" if fn else "no .pdata entry"
        return f"{rip:#x}  static {static:#x}  {where}"

    if args.all:
        for tid in thread_ids(pid):
            rip = sample_rip(tid)
            if rip:
                print(f"tid {tid:>7}  {describe(rip)}")
        return 0

    tid = args.tid or busiest_thread(pid)
    if not tid:
        print("could not identify a busy thread")
        return 1

    if args.stack:
        # A frame-pointer-less x64 walk needs unwind data; scanning the stack for
        # qwords that land inside a known function is enough to name the call
        # chain, which is all we need to find the loop's owner. Frames are
        # reported outermost-last (stack grows down), duplicates collapsed.
        import struct as _struct
        from _ps_sync_live import Mem as _Mem
        mem = _Mem(pid)
        got = sample_context(tid)
        if not got:
            print("could not read the thread context")
            return 1
        rip, rsp = got
        print(f"pid {pid}  tid {tid}\n  RIP {describe(rip)}\n  RSP {rsp:#x}\n")
        # Read page by page: a single large read fails outright if any page in
        # the range is a guard page, which the top of a UE stack usually has.
        chunks: list[bytes] = []
        for page in range(0, args.stack_bytes, 0x1000):
            got_page = mem.read(rsp + page, 0x1000)
            chunks.append(got_page if got_page else b"\x00" * 0x1000)
        blob = b"".join(chunks)
        if not any(chunks):
            print("could not read the stack")
            return 1
        seen: list[tuple[int, int]] = []
        seen_fns: set[int] = set()
        for off in range(0, len(blob) - 8, 8):
            (val,) = _struct.unpack_from("<Q", blob, off)
            if not (base <= val < base + size):
                continue
            static = val - base + pe.image_base
            fn = idx.primary(static)
            if not fn or fn.beg in seen_fns:
                continue
            seen_fns.add(fn.beg)
            seen.append((off, static))
        print(f"return-address candidates on the stack ({len(seen)} distinct functions):")
        for off, static in seen[:40]:
            fn = idx.primary(static)
            print(f"  rsp+{off:#06x}  ret {static:#x}  fn {fn.beg:#x}")
        return 0

    print(f"pid {pid}  sampling tid {tid}  ({args.samples} samples)\n")

    hist: collections.Counter = collections.Counter()
    fns: collections.Counter = collections.Counter()
    denied = 0
    for _ in range(args.samples):
        rip = sample_rip(tid)
        if rip is None:
            denied += 1
        else:
            hist[rip] += 1
            if base <= rip < base + size:
                static = rip - base + pe.image_base
                fn = idx.primary(static)
                fns[fn.beg if fn else 0] += 1
        time.sleep(0.02)

    if denied:
        print(f"!! {denied}/{args.samples} samples denied (EAC blocked the handle)")
    if not hist:
        return 1
    print("top RIPs:")
    for rip, n in hist.most_common(8):
        print(f"  {n:3d}x  {describe(rip)}")
    print("\nloop is inside:")
    for fn, n in fns.most_common(5):
        print(f"  {n:3d}x  fn {fn:#x}   <- python match_server/_fn_dump.py {fn:#x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
