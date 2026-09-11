#!/usr/bin/env python3
r"""Read-only: dump every formatted "Client Synchronization" checklist instance found in
the running client, with its heap address, so two runs can be compared.

`scan_sync_status.py` proves *a* checklist exists but not *when* it was produced. UE's
`FString` for a re-logged line is normally reallocated, so an address that moves between
runs means the client is still printing the checklist (the values are current); an
address that stays put with identical text means the hit is a stale buffer.

Only PAGE_READWRITE / PAGE_WRITECOPY committed regions are read, which is where heap
FStrings live and which keeps a pass to a few tens of seconds instead of minutes.

  python match_server/_sync_snapshot.py            # one pass
  python match_server/_sync_snapshot.py --twice 30 # two passes 30s apart, diffed
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import subprocess
import time

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
RW_PROTECTS = (0x04, 0x08, 0x40, 0x80)  # READWRITE, WRITECOPY, EXECUTE_READWRITE, EXECUTE_WRITECOPY

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# "Client Synchronization" itself only exists as the `[%s][%s]` format literal in
# read-only memory. These two only ever occur in an already-formatted instance.
NEEDLES = [s.encode("utf-16le") for s in ("PlayerState: false", "PlayerState: true")]


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


def find_pid() -> int:
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process WW3-Win64-Shipping -EA SilentlyContinue | Select -First 1).Id"],
        capture_output=True, text=True, check=False,
    )
    pid = (r.stdout or "").strip()
    if not pid:
        raise SystemExit("WW3-Win64-Shipping not running")
    return int(pid)


def decode_utf16_run(data: bytes, start: int, max_chars: int = 700) -> str:
    """Decode UTF-16LE forward from `start` until a NUL wchar or `max_chars`."""
    out = []
    i = start
    while i + 1 < len(data) and len(out) < max_chars:
        ch = data[i] | (data[i + 1] << 8)
        if ch == 0:
            break
        out.append(chr(ch))
        i += 2
    return "".join(out)


def utf16_start(data: bytes, hit: int, max_back: int = 400) -> int:
    """Walk back from `hit` to the first NUL wchar, i.e. the start of the FString."""
    i = hit
    limit = max(0, hit - max_back * 2)
    while i - 2 >= limit:
        ch = data[i - 2] | (data[i - 1] << 8)
        if ch == 0:
            break
        i -= 2
    return i


def scan(pid: int) -> list[tuple[int, str]]:
    h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        raise SystemExit(f"OpenProcess failed err={ctypes.get_last_error()}")
    found: list[tuple[int, str]] = []
    mbi = MBI()
    addr = 0
    read = ctypes.c_size_t()
    scanned = 0
    while kernel32.VirtualQueryEx(h, ctypes.c_uint64(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        base, size = mbi.BaseAddress, mbi.RegionSize
        nxt = base + size
        if (mbi.State == MEM_COMMIT and mbi.Protect in RW_PROTECTS
                and not (mbi.Protect & PAGE_GUARD) and 0 < size <= 64 * 1024 * 1024):
            buf = (ctypes.c_char * size)()
            if kernel32.ReadProcessMemory(h, ctypes.c_uint64(base), buf, size, ctypes.byref(read)) \
                    and read.value:
                data = bytes(buf[: read.value])
                scanned += read.value
                for needle in NEEDLES:
                    off = data.find(needle)
                    while off != -1:
                        s = utf16_start(data, off)
                        found.append((base + s, decode_utf16_run(data, s)))
                        off = data.find(needle, off + 2)
        addr = nxt
        if addr <= base:
            break
    kernel32.CloseHandle(h)
    print(f"  scanned_rw_bytes={scanned} instances={len(found)}")
    return found


def show(tag: str, found: list[tuple[int, str]]) -> None:
    print(f"=== {tag} ===")
    for a, t in found:
        print(f"  @0x{a:x}")
        for line in t.splitlines():
            print("     " + line)
    if not found:
        print("  (no formatted checklist in RW memory)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--twice", type=float, default=0.0,
                    help="seconds between two passes; diff the results")
    args = ap.parse_args()

    pid = find_pid()
    print(f"pid={pid}")
    t0 = time.time()
    first = scan(pid)
    print(f"  pass 1 took {time.time() - t0:.1f}s")
    show("pass 1", first)
    if args.twice <= 0:
        return
    time.sleep(args.twice)
    second = scan(pid)
    show("pass 2", second)
    a1 = {a for a, _ in first}
    a2 = {a for a, _ in second}
    print("=== diff ===")
    print(f"  addresses only in pass 1: {[hex(a) for a in sorted(a1 - a2)]}")
    print(f"  addresses only in pass 2: {[hex(a) for a in sorted(a2 - a1)]}")
    print(f"  addresses in both:        {[hex(a) for a in sorted(a1 & a2)]}")
    t1 = {t for _, t in first}
    t2 = {t for _, t in second}
    print(f"  text changed: {t1 != t2}")


if __name__ == "__main__":
    main()
