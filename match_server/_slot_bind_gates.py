#!/usr/bin/env python3
"""Read the live client's value for every gate in the slot->PlayerState bind.

`AWW3TeamManager::BindSlotToPlayerState` (exe `0x1409739b0`, reached from the
`TM_Synchronize` handler `0x140969db0` for each slot whose `+0x60` is set) is the
only path that can populate `AWW3PlayerState::CurrentSquad`.  Its decompiled
preconditions are, in order:

    if (!IsValid(slot))                       return;
    if (slot->[0x60] == 0)                    return;   // "bound" flag on the wire
    if (slot->[0x34] == 0)                    return;   // PlayerStateUniqueID
    World = TeamManager->GetWorld();
    for (AWW3PlayerState* ps : TActorRange<AWW3PlayerState>(World)) {
        if (!IsValid(ps))                        continue;
        if (!ps->UniqueId.IsValid())             continue;   // +0x3A0, vtable +0x20
        if (ps->InternalNetId == 0)              continue;   // +0x790
        if (ps->PlayerStateUniqueID != slot->[0x34]) continue; // +0x774
        if (slot->[0x30] != ps->InternalNetId)   continue;
        slot->[0x61]     = false;
        slot->PlayerState = ps;                              // +0x58
        if (!IsValid(TeamManager->LocalPlayerState))         // +0x448
            if (IsValid(Cast<...>(ps->Owner)))               // +0x108
                TeamManager->LocalPlayerState = ps;
                TeamManager->[0x450]          = ps->InternalNetId;
                AWW3PlayerState::SetCurrentSquad(ps, slot->Squad);   // 0x1410FB3C0
        return;
    }

So the packet's slot record must carry the live `InternalNetId` in `+0x30` and
the live `PlayerStateUniqueID` in `+0x34`, and three *client-side* facts have to
already hold.  This prints all of them so the packet is built from measured
values instead of assumed ones.

Read-only: PROCESS_QUERY_INFORMATION | PROCESS_VM_READ.

Usage:
    python match_server/_slot_bind_gates.py
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _ps_sync_live import Mem, find_pid, main_module  # noqa: E402
from _team_graph_live import live_instances  # noqa: E402
from _uobject_live import (  # noqa: E402
    DUMP_ROOT,
    OBJ_CLASS,
    Objects,
    load_dump,
    super_chain,
)

# `AWW3PlayerController::StaticClass()` (exe 0x1417A99A0) caches the UClass in
# this global; the bind's `Cast<AWW3PlayerController>(ps->Owner)` uses it.
WW3_PC_CLASS_GLOBAL_RVA = 0x145DDB940 - 0x140000000

PS_OWNER = 0x108           # AActor::Owner
PS_PLAYER_NAME = 0x338     # APlayerState::PlayerName (FString) -> slot +0x40
# APlayerState::UniqueId is FUniqueNetIdRepl at 0x398; its
# TSharedPtr<const FUniqueNetId> sits at +0x08, i.e. 0x3A0.
PS_UNIQUE_NET_ID = 0x3A0
PS_CURRENT_SQUAD = 0x710
PS_UNIQUE_ID = 0x774       # uint32 PlayerStateUniqueID
PS_INTERNAL_NET_ID = 0x790  # uint32 InternalNetId

TM_LOCAL_PLAYER_STATE = 0x448
TM_LOCAL_NET_ID = 0x450

# The nine leading `TM_Synchronize` header values are pure `AWW3TeamManager`
# configuration: the handler (exe 0x140969DB0) copies each straight into the
# TeamManager.  Echoing the client's own current values keeps the header a
# verified no-op instead of an invented one.
#   wire idx -> (action offset, TeamManager offset, TeamManager field width)
SYNC_HEADER_MAP = [
    (0, 0x38, 0x440, 1),
    (1, 0x39, 0x3FC, 1),
    (2, 0x3A, 0x3E8, 4),
    (3, 0x3B, 0x3EC, 4),
    (4, 0x3C, 0x3F0, 4),
    (5, 0x3D, 0x3F4, 4),
    (6, 0x3E, 0x3F8, 4),
    (7, 0x3F, 0x428, 4),
    (8, 0x40, 0x42C, 4),
]

WATCH = ["WW3.WW3PlayerState", "WW3.WW3TeamManager"]


def u32(mem: Mem, addr: int):
    b = mem.read(addr, 4)
    return None if b is None else struct.unpack("<I", b)[0]


def u64(mem: Mem, addr: int):
    b = mem.read(addr, 8)
    return None if b is None else struct.unpack("<Q", b)[0]


def fstring(mem: Mem, addr: int) -> str | None:
    """Read a UE `FString` (TArray<TCHAR>: Data, Num, Max) out of the client."""
    head = mem.read(addr, 16)
    if head is None:
        return None
    data, num, _mx = struct.unpack("<Qii", head)
    if not data or num <= 0 or num > 1024:
        return ""
    raw = mem.read(data, num * 2)
    if raw is None:
        return None
    return raw.decode("utf-16-le", errors="replace").rstrip("\x00")


def name_of(mem: Mem, objs: Objects, by_index, ptr: int) -> str:
    if not ptr:
        return "NULL"
    cls = u64(mem, ptr + OBJ_CLASS)
    if not cls:
        return f"{ptr:#x} <no class>"
    idx = u32(mem, cls + 0x0C)
    nm = by_index.get(idx, "?") if idx is not None else "?"
    return f"{ptr:#x} ({nm})"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=str(DUMP_ROOT / "GObjects-Dump.txt"))
    args = ap.parse_args()

    pid = find_pid()
    mem = Mem(pid)
    mod_base, _ = main_module(pid)
    objs = Objects(mem, mod_base)
    by_index, by_name = load_dump(Path(args.dump))
    print(f"pid={pid}  {objs.num_elements} live UObjects")

    found = live_instances(mem, objs, by_name, WATCH)

    pc_class = u64(mem, mod_base + WW3_PC_CLASS_GLOBAL_RVA) or 0
    print(f"AWW3PlayerController::StaticClass() = {pc_class:#x}")

    def is_ww3_pc(ptr: int) -> bool:
        cls = u64(mem, ptr + OBJ_CLASS) if ptr else None
        if not cls or not pc_class:
            return False
        return cls == pc_class or pc_class in super_chain(mem, cls, limit=16)

    for _i, ps, _c, _f in found.get("WW3.WW3PlayerState", []):
        owner = u64(mem, ps + PS_OWNER)
        uid_ptr = u64(mem, ps + PS_UNIQUE_NET_ID)
        print(f"\n=== AWW3PlayerState {ps:#x}")
        print(f"  InternalNetId        (+0x790) = {u32(mem, ps + PS_INTERNAL_NET_ID)}"
              "   -> slot +0x30")
        print(f"  PlayerStateUniqueID  (+0x774) = {u32(mem, ps + PS_UNIQUE_ID)}"
              "   -> slot +0x34")
        print(f"  CurrentSquad         (+0x710) = "
              f"{u64(mem, ps + PS_CURRENT_SQUAD):#x}")
        print(f"  PlayerName           (+0x338) = {fstring(mem, ps + PS_PLAYER_NAME)!r}"
              "   -> slot +0x40")
        print(f"  UniqueId ptr         (+0x3A0) = {uid_ptr:#x}"
              f"   {'OK' if uid_ptr else 'NULL -> gate FAILS'}")
        ok_pc = is_ww3_pc(owner or 0)
        print(f"  Owner                (+0x108) = "
              f"{name_of(mem, objs, by_index, owner or 0)}")
        print(f"    Cast<AWW3PlayerController>   = "
              f"{'OK' if ok_pc else 'FAILS -> LocalPlayerState/CurrentSquad never set'}")

    for _i, tm, _c, _f in found.get("WW3.WW3TeamManager", []):
        lps = u64(mem, tm + TM_LOCAL_PLAYER_STATE)
        print(f"\n=== AWW3TeamManager {tm:#x}")
        print(f"  LocalPlayerState     (+0x448) = "
              f"{name_of(mem, objs, by_index, lps or 0)}"
              f"   {'already set -> SetCurrentSquad SKIPPED' if lps else 'NULL -> OK'}")
        print(f"  LocalNetId           (+0x450) = {u32(mem, tm + TM_LOCAL_NET_ID)}")
        print("  TM_Synchronize header (echo these back):")
        vals = []
        for widx, aoff, toff, width in SYNC_HEADER_MAP:
            raw = mem.read(tm + toff, width)
            v = 0 if raw is None else int.from_bytes(raw, "little")
            vals.append(v)
            print(f"    wire[{widx}] action+{aoff:#04x} <- TM+{toff:#05x} "
                  f"(u{width * 8}) = {v}")
        print(f"    header tuple = {tuple(vals)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
