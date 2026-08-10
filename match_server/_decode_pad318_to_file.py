#!/usr/bin/env python3
"""Decode Pad_318 pre-clear TSharedPtr object addrs; dump to live_log/_pad318_decode.txt."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import struct
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent / "live_log" / "_pad318_decode.txt"
# Pre-clear addrs from live_log/_gs_sync_blocks_dump.txt WAM @0x28b3f060650
# Filled from the current read-only WAM scan before running this decoder.
WAMS = [0x21B3B1260A0, 0x21A4B2A3620]

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)


class MODULEINFO(ctypes.Structure):
    _fields_ = [
        ("lpBaseOfDll", ctypes.c_void_p),
        ("SizeOfImage", wt.DWORD),
        ("EntryPoint", ctypes.c_void_p),
    ]


def main():
    lines = []
    pid_s = subprocess.check_output(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "(Get-Process WW3-Win64-Shipping -EA SilentlyContinue|Select -First 1).Id",
        ],
        text=True,
    ).strip()
    if not pid_s:
        lines.append("NO_PROCESS")
        OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("NO_PROCESS")
        return 1
    pid = int(pid_s)
    h = k32.OpenProcess(0x0410, False, pid)
    if not h:
        lines.append(f"OpenProcess fail err={ctypes.get_last_error()}")
        OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 1
    read = ctypes.c_size_t()

    def rpm(addr, n):
        buf = (ctypes.c_char * n)()
        if not k32.ReadProcessMemory(
            h, ctypes.c_uint64(addr), buf, n, ctypes.byref(read)
        ):
            return None
        return bytes(buf[: read.value])

    lines.append(f"# Pad_318 decode pid={pid}")
    hMods = (ctypes.c_uint64 * 1024)()
    needed = wt.DWORD()
    psapi.EnumProcessModulesEx(h, hMods, ctypes.sizeof(hMods), ctypes.byref(needed), 3)
    name = ctypes.create_unicode_buffer(260)
    base = size = None
    for i in range(min(needed.value // 8, 1024)):
        psapi.GetModuleBaseNameW(h, ctypes.c_uint64(hMods[i]), name, 260)
        if "WW3-Win64-Shipping" in name.value:
            mi = MODULEINFO()
            psapi.GetModuleInformation(
                h, ctypes.c_uint64(hMods[i]), ctypes.byref(mi), ctypes.sizeof(mi)
            )
            base, size = hMods[i], mi.SizeOfImage
            break
    lines.append(f"module {hex(base) if base else None} {hex(size) if size else None}")

    def looks_uobject(addr):
        r = rpm(addr, 0x28)
        if not r or not base:
            return False
        vt = struct.unpack_from("<Q", r, 0)[0]
        cls = struct.unpack_from("<Q", r, 0x10)[0]
        return base <= vt < base + size and cls > 0x10000

    for WAM in WAMS:
        raw = rpm(WAM, 0x4C0)
        if not raw:
            lines.append(f"## live WAM {hex(WAM)} RPM_FAIL (process may have recycled)")
            continue
        lines.append(f"## live WAM {hex(WAM)} Pad_318={raw[0x318:0x350].hex()}")
        lines.append(f"  b2A4={raw[0x2A4:0x2A8].hex()} i2B4={struct.unpack_from('<i', raw, 0x2B4)[0]}")
        all_n = struct.unpack_from("<i", raw, 0x1C0)[0]
        all_data = struct.unpack_from("<Q", raw, 0x1B8)[0]
        ids_data = struct.unpack_from("<Q", raw, 0x1C8)[0]
        att_by_ptr = {}
        if all_data and 0 < all_n <= 32:
            objs_blob = rpm(all_data, all_n * 8)
            ids_blob = rpm(ids_data, all_n * 2)
            if objs_blob and ids_blob:
                objs = struct.unpack("<" + str(all_n) + "Q", objs_blob)
                ids = struct.unpack("<" + str(all_n) + "H", ids_blob)
                att_by_ptr = {p: ids[i] for i, p in enumerate(objs)}
                lines.append(f"  WAM atts { {hex(p): i for p, i in att_by_ptr.items()} }")
        lines.append("## live Pad_318 object addrs")
        preclear = [(f"s{i}", struct.unpack_from('<Q', raw, 0x320 + i*16)[0]) for i in range(3)]
        controls = [(f"c{i}", struct.unpack_from('<Q', raw, 0x328 + i*16)[0]) for i in range(3)]
        for label, a in preclear:
            blob = rpm(a, 0x80)
            if not blob:
                lines.append(f"=== {label} @{hex(a)} UNREADABLE")
                continue
            data, num, mx = struct.unpack_from("<Qii", blob, 0)
            lines.append(
            f"=== {label} @{hex(a)} asTArray data={hex(data)} num={num} max={mx} head16={blob[:16].hex()}"
            )
            if data and 0 < num <= 64 and num <= mx <= 4096:
                try:
                    ptrs = struct.unpack("<" + str(num) + "Q", rpm(data, num * 8))
                except Exception as e:
                    lines.append(f"  ptrs fail: {e}")
                    continue
                for i, p in enumerate(ptrs):
                    u = looks_uobject(p)
                    if u:
                        r = rpm(p, 0x28)
                        n = struct.unpack_from("<ii", r, 0x18)
                        cls = struct.unpack_from("<Q", r, 0x10)[0]
                        ci = struct.unpack_from("<i", rpm(cls + 0xC, 4))[0]
                        lines.append(
                        f"  [{i}] {hex(p)} uobj=1 Name={n} ClassIdx={ci} attId={att_by_ptr.get(p)}"
                        )
                    else:
                        r = rpm(p, 16)
                        lines.append(f"  [{i}] {hex(p)} uobj=0 raw16={r.hex() if r else None}")
            else:
            # Not a TArray — dump as possible FSoftObjectPath / shared state
                lines.append(f"  notTArray-or-empty; qwords={[hex(struct.unpack_from('<Q', blob, o)[0]) for o in range(0, 64, 8)]}")

        lines.append("## live control-block addrs")
        for label, a in controls:
            blob = rpm(a, 0x40)
            if not blob:
                lines.append(f"=== {label} @{hex(a)} UNREADABLE")
                continue
            lines.append(f"=== {label} @{hex(a)} {blob.hex()}")
            obj = struct.unpack_from("<Q", blob, 0)[0]
            lines.append(f"  qword0={hex(obj)} looks_uobj={looks_uobject(obj)}")

    text = "\n".join(lines) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)
    print("wrote", OUT)
    k32.CloseHandle(h)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
