#!/usr/bin/env python3
r"""Read the live client's `AWW3ActionReplicator` receive state, read-only.

Why this and not just the ack
-----------------------------
`Client_ReceivePacket_Implementation` (exe 0x140873980) tail-jumps to
`0x141672bc0` -> `ProcessEvent(FindFunctionChecked(...))` on **both** exit paths:
the "buffer is not complete yet" early-out at 0x140873b44 and the end of the
parse loop.  So `Server_AckActionsReceived` proves the RPC dispatched and says
nothing about whether the payload parsed.  These fields do:

    +0x348  ClHeadAction      UWW3ReplicatedAction*
    +0x350  ClTailAction      UWW3ReplicatedAction*
    +0x358  Count             int32   -- queued, not-yet-applied actions
    +0x364  ExpectedTotal     int32   -- latched from int32 buffer[0]
    +0x380  ReceiveBuffer     TArray<uint8> { Data, Num, Max }

Reading them tells the three outcomes apart:

  * `ExpectedTotal == 0` and `ReceiveBuffer.Num == 0`
        -> a complete packet was consumed and the buffer reset.  GREEN.
  * `ExpectedTotal == <our size>` and `ReceiveBuffer.Num < ExpectedTotal`
        -> the client is waiting for more fragments; our size prefix is too big.
  * `ExpectedTotal != <our size>` with a non-empty buffer
        -> the prefix was misread entirely (wrong parameter encoding).

`Count`/`ClHeadAction` additionally show whether the parsed action was *queued*
(the client will apply it later) or applied immediately -- the parse loop applies
the first action in-line when `act->vtable[0x250]()` returns true (0x140873cde),
in which case it is never added to the list and `Count` stays 0.

Read-only: PROCESS_QUERY_INFORMATION | PROCESS_VM_READ.

Usage:
    python match_server/_action_live.py
    python match_server/_action_live.py --expect 25
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _ps_sync_live import Mem, find_pid, main_module  # noqa: E402
from _uobject_live import (DUMP_ROOT, Objects, header, load_dump,  # noqa: E402
                           resolve, super_chain)

RF_CLASS_DEFAULT_OBJECT = 0x00000010
RF_ARCHETYPE_OBJECT = 0x00000020

AR_CL_HEAD = 0x348
AR_CL_TAIL = 0x350
AR_COUNT = 0x358
AR_EXPECTED_TOTAL = 0x364
AR_RECEIVE_BUFFER = 0x380


def live_instances(mem: Mem, objs: Objects, class_ptr: int, subclasses: bool = False):
    out = []
    for _idx, ptr in objs.all_ptrs():
        h = header(mem, ptr)
        if not h or not h["class"]:
            continue
        if h["flags"] & (RF_CLASS_DEFAULT_OBJECT | RF_ARCHETYPE_OBJECT):
            continue
        if h["class"] == class_ptr:
            out.append(ptr)
        elif subclasses and class_ptr in super_chain(mem, h["class"]):
            out.append(ptr)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=str(DUMP_ROOT / "GObjects-Dump.txt"))
    ap.add_argument("--expect", type=int, default=None,
                    help="the byte size of the packet we sent, for a verdict")
    args = ap.parse_args()

    pid = find_pid()
    if not pid:
        print("WW3-Win64-Shipping not running")
        return 2
    mem = Mem(pid)
    base, _size = main_module(pid)
    objs = Objects(mem, base)
    _by_index, by_name = load_dump(Path(args.dump))

    cls_index = resolve(objs, by_name, "WW3.WW3ActionReplicator")
    cls_ptr = objs.ptr(cls_index)
    reps = live_instances(mem, objs, cls_ptr)
    print(f"pid {pid}  live AWW3ActionReplicator instances: {len(reps)}")
    if not reps:
        print("  none -- ch80 was never opened in this session")
        return 1

    verdict_ok = False
    for ptr in reps:
        raw = mem.read(ptr + AR_CL_HEAD, 0x50)
        if raw is None:
            print(f"  {ptr:#x}: unreadable")
            continue
        cl_head, cl_tail = struct.unpack_from("<QQ", raw, 0)
        count = struct.unpack_from("<i", raw, AR_COUNT - AR_CL_HEAD)[0]
        expected = struct.unpack_from("<i", raw, AR_EXPECTED_TOTAL - AR_CL_HEAD)[0]
        buf_data, buf_num, buf_max = struct.unpack_from(
            "<Qii", raw, AR_RECEIVE_BUFFER - AR_CL_HEAD)
        print(f"  {ptr:#x}")
        print(f"    ClHeadAction   = {cl_head:#x}")
        print(f"    ClTailAction   = {cl_tail:#x}")
        print(f"    Count          = {count}")
        print(f"    ExpectedTotal  = {expected}")
        print(f"    ReceiveBuffer  = Data {buf_data:#x}  Num {buf_num}  Max {buf_max}")
        if buf_num and buf_data:
            head = mem.read(buf_data, min(buf_num, 64))
            if head:
                print(f"    buffer[:{len(head)}] = {head.hex()}")

        if args.expect is not None:
            if expected == 0 and buf_num == 0 and buf_max >= args.expect:
                print(f"    VERDICT: a {buf_max}-byte packet was buffered and fully "
                      f"consumed -- the size prefix and framing are correct")
                verdict_ok = True
            elif expected == args.expect and buf_num < expected:
                print(f"    VERDICT: waiting for {expected - buf_num} more bytes -- "
                      f"the size prefix over-counts")
            elif expected == 0 and buf_num == 0 and buf_max == 0:
                print("    VERDICT: nothing was ever delivered to this actor")
            else:
                print(f"    VERDICT: unexpected state (ExpectedTotal {expected} vs "
                      f"sent {args.expect})")

    if cl_head or count:
        print("\nqueued actions are pending; the client applies them on its own tick")
    return 0 if (args.expect is None or verdict_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
