#!/usr/bin/env python3
"""Tail client_log with share-mode read; print sync-related lines."""
from __future__ import annotations

import glob
import os
import sys

LOG_DIR = os.path.join(os.path.dirname(__file__), "live_log", "client_log")
KEYS = (
    "OnSynchronized",
    "Client Synchronization",
    "Character Attachments",
    "AttachmentIds Num",
    "WeaponsAttachments",
    "InventoryManager:",
)


def main() -> int:
    logs = sorted(
        glob.glob(os.path.join(LOG_DIR, "client_*.log")),
        key=os.path.getmtime,
        reverse=True,
    )
    logs = [p for p in logs if not p.endswith("_net.log")]
    if not logs:
        print("no client log")
        return 1
    path = logs[0]
    print(f"path={path}")
    # FILE_SHARE_READ|WRITE|DELETE
    import msvcrt
    import ctypes
    from ctypes import wintypes

    GENERIC_READ = 0x80000000
    FILE_SHARE_ALL = 0x7
    OPEN_EXISTING = 3
    FILE_ATTRIBUTE_NORMAL = 0x80
    INVALID = ctypes.c_void_p(-1).value
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    CreateFileW = k32.CreateFileW
    CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    CreateFileW.restype = wintypes.HANDLE
    h = CreateFileW(path, GENERIC_READ, FILE_SHARE_ALL, None, OPEN_EXISTING,
                    FILE_ATTRIBUTE_NORMAL, None)
    if h == wintypes.HANDLE(-1).value or h == 0xFFFFFFFF:
        print(f"CreateFile failed err={ctypes.get_last_error()}")
        return 1
    fd = msvcrt.open_osfhandle(int(h), os.O_RDONLY)
    with os.fdopen(fd, "rb", closefd=True) as f:
        f.seek(0, 2)
        size = f.tell()
        start = max(0, size - int(sys.argv[1]) if len(sys.argv) > 1 else 4_000_000)
        f.seek(start)
        data = f.read().decode("utf-8", "replace")
    hits = [ln for ln in data.splitlines() if any(k in ln for k in KEYS)]
    print(f"bytes_from={start} size={size} hits={len(hits)}")
    for ln in hits[-80:]:
        print(ln[-300:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
