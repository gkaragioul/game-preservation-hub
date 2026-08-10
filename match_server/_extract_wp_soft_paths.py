#!/usr/bin/env python3
"""Extract full /Game/... SoftClass paths for capture WAM AttachmentIds from live process."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as w
import re
import subprocess
import sys

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000

CLASSES = [
    "BP_WP_Rail_086_01",
    "BP_WP_Muzzle_020_01",
    "BP_WP_Magazine_108_01",
    "BP_WP_Barrel_024_01",
    "BP_WP_Barrel_033_01",
    "BP_WP_Magazine_116_01",
    "BP_WP_Handguard_021_01",
    "BP_WP_Stock_029_01",
    "BP_WP_PistolGrip_017_01",
    "BP_WP_Muzzle_013_01",
    "BP_WP_Receiver_008_02",
    "BP_WP_Upper_091_01",
    "BP_WP_UpperMinor_026_06_PST_Sidearm",
    "BP_WP_UpperMinor_026_02_PST_BR",
    "BP_WP_Side_006_01",
    "BP_CH_Hat_004_01",
]


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


def pid() -> int:
    out = subprocess.check_output(["tasklist", "/FO", "CSV", "/NH"], text=True, errors="replace")
    for line in out.splitlines():
        if line.upper().startswith('"WW3-WIN64-SHIPPING.EXE"'):
            return int(line.split('","')[1].strip('"'))
    raise SystemExit("WW3 not running")


def main():
    p = pid()
    print(f"pid={p}", flush=True)
    h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, p)
    if not h:
        raise SystemExit(f"OpenProcess failed {ctypes.get_last_error()}")
    mbi = MEMORY_BASIC_INFORMATION()
    addr = 0
    buf = ctypes.create_string_buffer(2 << 20)
    found: dict[str, set[str]] = {c: set() for c in CLASSES}
    path_re = re.compile(rb"/Game/[A-Za-z0-9_./]+BP_WP_[A-Za-z0-9_]+")
    path_re_u16 = re.compile(
        "(/Game/[A-Za-z0-9_./]+BP_WP_[A-Za-z0-9_]+)".encode("utf-16le")
    )
    # also ascii class with nearby /Game
    while kernel32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        base = mbi.BaseAddress or 0
        size = mbi.RegionSize or 0
        prot = mbi.Protect & 0xFF
        if mbi.State == MEM_COMMIT and prot in (0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80) and size:
            off = 0
            while off < size:
                chunk = min(len(buf), size - off)
                nread = ctypes.c_size_t(0)
                ok = kernel32.ReadProcessMemory(
                    h, ctypes.c_void_p(base + off), buf, chunk, ctypes.byref(nread)
                )
                if ok and nread.value:
                    data = buf.raw[: nread.value]
                    for m in path_re.finditer(data):
                        s = m.group(0).decode("ascii", "ignore")
                        for c in CLASSES:
                            if c in s:
                                found[c].add(s)
                    # utf16 /Game paths
                    for m in re.finditer(rb"(?:/\x00G\x00a\x00m\x00e\x00(?:[\x20-\x7e]\x00){10,200})", data):
                        try:
                            s = m.group(0).decode("utf-16le", "ignore")
                        except Exception:
                            continue
                        for c in CLASSES:
                            if c in s:
                                # trim to path-like
                                mm = re.search(r"/Game/[A-Za-z0-9_./]+" + re.escape(c), s)
                                if mm:
                                    found[c].add(mm.group(0))
                    # also look for class.uasset near /Game ascii
                    for c in CLASSES:
                        nd = c.encode("ascii")
                        p0 = 0
                        while True:
                            i = data.find(nd, p0)
                            if i < 0:
                                break
                            window = data[max(0, i - 100) : i + len(nd) + 40]
                            # try recover path ending at class
                            ascii_win = "".join(chr(b) if 32 <= b < 127 else "|" for b in window)
                            mm = re.search(r"/Game/[A-Za-z0-9_./]+" + re.escape(c), ascii_win)
                            if mm:
                                found[c].add(mm.group(0))
                            elif "Attachments" in ascii_win and c in ascii_win:
                                found[c].add("CTX:" + ascii_win.replace("|", "")[:160])
                            p0 = i + len(nd)
                off += chunk
        nxt = base + size
        if nxt <= addr:
            break
        addr = nxt
        if addr > 0x7FFFFFFFFFFF:
            break
    kernel32.CloseHandle(h)
    out_path = "live_log/_wp_softclass_paths.txt"
    lines = []
    for c in CLASSES:
        lines.append(f"{c}:")
        for s in sorted(found[c]):
            lines.append(f"  {s}")
        if not found[c]:
            lines.append("  (none)")
    text = "\n".join(lines) + "\n"
    open(out_path, "w", encoding="utf-8").write(text)
    # ascii-safe print
    sys.stdout.buffer.write(text.encode("utf-8", "replace"))
    print(f"\nwrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
