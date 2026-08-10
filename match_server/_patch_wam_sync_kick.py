#!/usr/bin/env python3
"""Patch stuck WAM Pad_298/318 + ProcessEvent(OnRep_ReplicatedBatch)."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import struct
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

STUCK = [0x28B3F060650, 0x28C70C17B30]
PROCESS_EVENT_OFF = 0x01BD2F00
GOBJECTS_OFF = 0x05F2C148

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)


def rpm(h, addr, n):
    buf = (ctypes.c_char * n)()
    read = ctypes.c_size_t()
    if not k32.ReadProcessMemory(
        h, ctypes.c_uint64(addr), buf, n, ctypes.byref(read)
    ):
        return None
    return bytes(buf[: read.value])


def wpm(h, addr, data: bytes) -> bool:
    written = ctypes.c_size_t()
    return bool(
        k32.WriteProcessMemory(
            h, ctypes.c_uint64(addr), data, len(data), ctypes.byref(written)
        )
    )


def main() -> int:
    pid = int(
        subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-Process WW3-Win64-Shipping|Select -First 1).Id",
            ],
            text=True,
        ).strip()
    )
    access = 0x0010 | 0x0020 | 0x0008 | 0x0400 | 0x0002 | 0x0400
    # PROCESS_CREATE_THREAD|VM_OPS|VM_READ|VM_WRITE|QUERY
    access = 0x1F0FFF
    h = k32.OpenProcess(access, False, pid)
    if not h:
        raise SystemExit(f"OpenProcess {ctypes.get_last_error()}")

    hMods = (ctypes.c_uint64 * 1024)()
    needed = wt.DWORD()
    psapi.EnumProcessModulesEx(h, hMods, ctypes.sizeof(hMods), ctypes.byref(needed), 3)
    name = ctypes.create_unicode_buffer(260)
    base = None
    for i in range(min(needed.value // 8, 1024)):
        psapi.GetModuleBaseNameW(h, ctypes.c_uint64(hMods[i]), name, 260)
        if "WW3-Win64-Shipping" in name.value:
            base = int(hMods[i])
            break
    print(f"pid={pid} base={hex(base)}")
    pe = base + PROCESS_EVENT_OFF
    print(f"ProcessEvent={hex(pe)}")

    def pad_sum(wam):
        raw = rpm(h, wam, 0x4C0)
        i0, i1, i2, i3 = struct.unpack_from("<iiii", raw, 0x298)
        i2b4 = struct.unpack_from("<i", raw, 0x2B4)[0]
        b2a4 = raw[0x2A4:0x2A8].hex()
        ptrs = sum(
            1
            for off in range(0x320, 0x350, 8)
            if struct.unpack_from("<Q", raw, off)[0]
        )
        alln = struct.unpack_from("<i", raw, 0x1C0)[0]
        bid = struct.unpack_from("<I", raw, 0x2B8)[0]
        return f"Batch={bid} All={alln} ({i0},{i1},{i2},{i3}) b2A4={b2a4} i2B4={i2b4} p318={ptrs}"

    print("BEFORE")
    for w in STUCK:
        print(" ", hex(w), pad_sum(w))

    # Find OnRep_ReplicatedBatch via Children of AttachmentManager (WAM SuperStruct)
    wam_cls = struct.unpack("<Q", rpm(h, STUCK[0] + 0x10, 8))[0]
    am_cls = struct.unpack("<Q", rpm(h, wam_cls + 0x30, 8))[0]  # SuperStruct
    print(f"WAM class={hex(wam_cls)} AM Super={hex(am_cls)}")

    # Walk Children linked list; collect UFunctions (Class size / flags)
    # UFunction Class: find by comparing Class pointer among children that have ExecFunction
    children = struct.unpack("<Q", rpm(h, am_cls + 0x38, 8))[0]
    funcs = []
    cur = children
    for _ in range(200):
        if not cur:
            break
        nidx, nnum = struct.unpack("<ii", rpm(h, cur + 0x18, 8))
        cls = struct.unpack("<Q", rpm(h, cur + 0x10, 8))[0]
        # ExecFunction at +0xB0 if UFunction
        execf = struct.unpack("<Q", rpm(h, cur + 0xB0, 8) or b"\0" * 8)[0]
        nxt = struct.unpack("<Q", rpm(h, cur + 0x28, 8))[0]
        if execf and base <= execf < base + 0x654D000:
            funcs.append((cur, nidx, nnum, execf))
        cur = nxt
    print(f"AM Children UFunctions: {len(funcs)}")
    for f in funcs:
        print(f"  func={hex(f[0])} Name=({f[1]},{f[2]}) Exec={hex(f[3])}")

    if len(funcs) < 1:
        raise SystemExit("no OnRep functions found")

    # OnRep_ReplicatedBatch is typically first / the one we want — try both
    # Prefer Name that we'll identify: dump had OnRep_ReplicatedBatch then SkinsIds
    # Without ToString, call BOTH OnReps.

    # Patch pads
    print("PATCH pads")
    for w in STUCK:
        wpm(h, w + 0x2A4, bytes([0x01, 0x01, 0x00, 0x00]))
        wpm(h, w + 0x2B4, struct.pack("<i", 2))
        wpm(h, w + 0x320, b"\x00" * 0x30)
        print("  patched", hex(w), pad_sum(w))

    # Remote ProcessEvent stub:
    # sub rsp,0x28
    # mov rcx, imm64  ; this
    # mov rdx, imm64  ; func
    # xor r8d,r8d     ; parms
    # mov rax, imm64  ; ProcessEvent
    # call rax
    # add rsp,0x28
    # ret
    def make_stub(this_ptr, func_ptr):
        code = bytearray()
        code += b"\x48\x83\xEC\x28"  # sub rsp,0x28
        code += b"\x48\xB9" + struct.pack("<Q", this_ptr)  # mov rcx, this
        code += b"\x48\xBA" + struct.pack("<Q", func_ptr)  # mov rdx, func
        code += b"\x45\x33\xC0"  # xor r8d,r8d
        code += b"\x48\xB8" + struct.pack("<Q", pe)  # mov rax, ProcessEvent
        code += b"\xFF\xD0"  # call rax
        code += b"\x48\x83\xC4\x28"  # add rsp,0x28
        code += b"\xC3"  # ret
        return bytes(code)

    remote = k32.VirtualAllocEx(
        h, None, 0x1000, MEM_COMMIT := 0x1000 | 0x2000, 0x40
    )
    print(f"remote stub page={hex(remote) if remote else 0}")
    if not remote:
        raise SystemExit("VirtualAllocEx failed")

    for w in STUCK:
        for fi, (func, nidx, nnum, execf) in enumerate(funcs):
            stub = make_stub(w, func)
            wpm(h, remote, stub)
            thread = k32.CreateRemoteThread(
                h, None, 0, ctypes.c_uint64(remote), None, 0, None
            )
            print(
                f"CreateRemoteThread WAM={hex(w)} func#{fi} Name=({nidx},{nnum}) "
                f"thread={bool(thread)} err={ctypes.get_last_error()}"
            )
            if thread:
                k32.WaitForSingleObject(thread, 5000)
                code = wt.DWORD()
                k32.GetExitCodeThread(thread, ctypes.byref(code))
                print(f"  exit={code.value}")
                k32.CloseHandle(thread)
            time.sleep(0.2)

    time.sleep(2)
    print("AFTER")
    for w in STUCK:
        print(" ", hex(w), pad_sum(w))

    # Quick marker probe: Mag*_C_0 / sync live / wam true — limited scan
    needles = {
        "mag0": "BP_WP_Magazine_108_01_C_0".encode("utf-16le"),
        "sync7": "OnAttachmentManagerSynchronized() : 7 -".encode("utf-16le"),
        "wam_t": "WeaponsAttachments: true".encode("utf-16le"),
        "onsync": "OnSynchronized: Weapons Attachments".encode("utf-16le"),
    }
    counts = {k: 0 for k in needles}

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

    mbi = MBI()
    addr = 0
    read = ctypes.c_size_t()
    scanned = 0
    while k32.VirtualQueryEx(
        h, ctypes.c_uint64(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)
    ):
        b, size = mbi.BaseAddress, mbi.RegionSize
        nxt = b + size
        if (
            mbi.State == 0x1000
            and (mbi.Protect & 0xFF) in (2, 4, 8)
            and not (mbi.Protect & 0x100)
            and 0 < size <= 32 << 20
        ):
            left, off = size, 0
            while left > 0:
                n = min(1 << 20, left)
                buf = (ctypes.c_char * n)()
                if (
                    k32.ReadProcessMemory(
                        h, ctypes.c_uint64(b + off), buf, n, ctypes.byref(read)
                    )
                    and read.value
                ):
                    data = bytes(buf[: read.value])
                    scanned += read.value
                    for k, nd in needles.items():
                        counts[k] += data.count(nd)
                off += n
                left -= n
        addr = nxt
        if addr <= b:
            break
    print("MARKERS", counts, "scanned_gb", round(scanned / (1 << 30), 2))
    k32.VirtualFreeEx(h, ctypes.c_uint64(remote), 0, 0x8000)
    k32.CloseHandle(h)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
