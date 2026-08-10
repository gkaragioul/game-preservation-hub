#!/usr/bin/env python3
"""Fast read-only dump of already-identified WAM component addresses."""
from __future__ import annotations

import argparse
import ctypes
import struct
import subprocess

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


def find_pid() -> int:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process WW3-Win64-Shipping -EA SilentlyContinue | Select -First 1).Id"],
        capture_output=True, text=True, check=False)
    value = (result.stdout or "").strip()
    if not value:
        raise SystemExit("WW3-Win64-Shipping not running")
    return int(value)


def rpm(handle, address: int, size: int) -> bytes:
    buffer = (ctypes.c_char * size)()
    read = ctypes.c_size_t()
    if not kernel32.ReadProcessMemory(
            handle, ctypes.c_uint64(address), buffer, size, ctypes.byref(read)):
        raise OSError(ctypes.get_last_error(), f"ReadProcessMemory 0x{address:x}")
    return bytes(buffer[:read.value])


def dump(handle, comp: int) -> None:
    raw = rpm(handle, comp, 0x4C0)
    batch = raw[0x2B8:0x2E0]
    batch_id = struct.unpack_from("<I", batch, 0)[0]
    num_rep = batch[4]
    ids_ptr, ids_num, ids_max = struct.unpack_from("<Qii", batch, 0x08)
    rep_ptr, rep_num, rep_max = struct.unpack_from("<Qii", batch, 0x18)
    applied_id = struct.unpack_from("<I", raw, 0x2E0)[0]
    applied_ptr, applied_num, applied_max = struct.unpack_from("<Qii", raw, 0x2E8)
    all_obj_ptr, all_obj_num, all_obj_max = struct.unpack_from("<Qii", raw, 0x1B8)
    all_ids_ptr, all_ids_num, all_ids_max = struct.unpack_from("<Qii", raw, 0x1C8)
    temporary = struct.unpack_from("<i", raw, 0x310)[0]
    parent_delegates = struct.unpack_from("<i", raw, 0x370)[0]
    mesh_delegates = struct.unpack_from("<i", raw, 0x380)[0]
    owner = struct.unpack_from("<Q", raw, 0x4A8)[0]
    print(f"WAM 0x{comp:x} owner=0x{owner:x}")
    print(f"  replicated: id={batch_id} numRep={num_rep} ids={ids_num}/{ids_max} "
          f"rep={rep_num}/{rep_max} idsPtr=0x{ids_ptr:x} repPtr=0x{rep_ptr:x}")
    print(f"  applied: id={applied_id} ids={applied_num}/{applied_max} ptr=0x{applied_ptr:x}")
    print(f"  objects={all_obj_num}/{all_obj_max} ids={all_ids_num}/{all_ids_max} "
          f"temporary={temporary} meshDelegates={mesh_delegates} "
          f"parentDelegates={parent_delegates}")
    print(f"  Pad298={raw[0x298:0x2B8].hex()}")
    print(f"  Pad318={raw[0x318:0x350].hex()}")
    print(f"  Pad3F0={raw[0x3F0:0x428].hex()}")
    if all_ids_ptr and 0 < all_ids_num <= 32:
        ids = struct.unpack("<" + "H" * all_ids_num,
                            rpm(handle, all_ids_ptr, all_ids_num * 2))
        print(f"  allIds={ids}")
    if all_obj_ptr and 0 < all_obj_num <= 32:
        objects = struct.unpack("<" + "Q" * all_obj_num,
                                rpm(handle, all_obj_ptr, all_obj_num * 8))
        print("  objectPtrs=" + ",".join(f"0x{x:x}" for x in objects))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, default=0)
    parser.add_argument("--comp", action="append", required=True,
                        help="WAM component address, decimal or 0x-prefixed")
    args = parser.parse_args()
    pid = args.pid or find_pid()
    handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not handle:
        raise SystemExit(f"OpenProcess failed pid={pid}")
    try:
        print(f"pid={pid}")
        for value in args.comp:
            dump(handle, int(value, 0))
    finally:
        kernel32.CloseHandle(handle)


if __name__ == "__main__":
    main()
