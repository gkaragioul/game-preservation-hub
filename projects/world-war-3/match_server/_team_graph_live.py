#!/usr/bin/env python3
"""Read the live client's team/squad object graph, identified through GObjects.

The `PlayerState` checklist bit is `IsValid(AWW3PlayerState::CurrentSquad)`
(offset 0x710, see `_ps_sync_predicate.py`). `UWW3SquadObject` has zero Net
properties, so the graph is built client-side. This answers the question that
decides where to look next:

    does the client have Teams/Squads/Slots at all, or is only the
    PlayerState -> Slot binding missing?

Objects are found through the live `GObjects` array (`_uobject_live.py`), never
by scanning the heap for pointer patterns -- freed `AWW3PlayerState` allocations
keep both their vtable and their `PlayerCharacter` back-pointer long after they
die, so a heap scan reports several plausible-looking corpses.

Layout from the Dumper-7 SDK (`WW3_classes.hpp`):

    AWW3PlayerStateBase  +0x430  AWW3Character*        PlayerCharacter   (Net)
    AWW3PlayerState      +0x710  UWW3SquadObject*      CurrentSquad
                         +0x738  bool                  bIsConnected      (Net)
                         +0x774  uint32                PlayerStateUniqueID (Net)
                         +0x790  uint32                InternalNetId     (Net)
    AWW3TeamManager      +0x3D8  TArray<UWW3TeamObject*>       Teams
                         +0x408  TArray<FWW3WarmupEntity>      WarmupEntities
                         +0x430  TArray<AWW3ActionReplicator*> ActionReplicators
                         +0x448  AWW3PlayerState*              LocalPlayerState
    UWW3TeamObject       +0x28 TeamId, +0x30 TeamManager, +0x38 Squads
    UWW3SquadObject      +0x88 Team, +0x90 Slots, +0xC8 CurrentSquadLeader
    UWW3SlotObject       +0x28 Squad, +0x58 PlayerState
    AWW3ActionReplicator  ClHeadAction / ClTailAction / SvHeadAction / SvTailAction

Read-only: PROCESS_QUERY_INFORMATION | PROCESS_VM_READ. No writes, no injection.

Usage:
    python match_server/_team_graph_live.py
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _ps_sync_live import Mem, find_pid, main_module  # noqa: E402
from _uobject_live import (  # noqa: E402
    DUMP_ROOT,
    OBJ_CLASS,
    Objects,
    header,
    load_dump,
    super_chain,
)

RF_CLASS_DEFAULT = 0x10
RF_ARCHETYPE = 0x20

PS_PLAYER_CHARACTER = 0x430
PS_SQUAD_DELEGATE = 0x5A0
PS_CURRENT_SQUAD = 0x710
PS_IS_CONNECTED = 0x738
PS_UNIQUE_ID = 0x774
PS_INTERNAL_NET_ID = 0x790
PS_PLAYING_STATE = 0x800
PS_CONNECTED_TO_MASTER = 0x9D0

TM_TEAMS = 0x3D8
TM_WARMUP = 0x408
TM_ACTION_REPLICATORS = 0x430
TM_LOCAL_PLAYER_STATE = 0x448

TEAM_ID, TEAM_MANAGER, TEAM_SQUADS = 0x28, 0x30, 0x38
SQUAD_TEAM, SQUAD_SLOTS, SQUAD_LEADER = 0x88, 0x90, 0xC8
SLOT_SQUAD, SLOT_PLAYER_STATE = 0x28, 0x58

WATCH = ["WW3.WW3TeamManager", "WW3.WW3ActionReplicator", "WW3.WW3TeamObject",
         "WW3.WW3SquadObject", "WW3.WW3SlotObject", "WW3.WW3PlayerState",
         "WW3.WW3Character"]


def read_tarray(mem: Mem, addr: int, max_items: int = 64):
    head = mem.read(addr, 16)
    if head is None:
        return None
    data, num, mx = struct.unpack("<Qii", head)
    if num < 0 or mx < 0 or num > mx or mx > 4096:
        return None
    if num == 0:
        return []
    if not (0x10000 <= data < 0x7FFFFFFFFFFF):
        return None
    raw = mem.read(data, 8 * min(num, max_items))
    if raw is None:
        return None
    return list(struct.unpack(f"<{len(raw)//8}Q", raw))


def fmt(p) -> str:
    if p is None:
        return "<unreadable>"
    return f"{p:#x}" if p else "NULL"


def live_instances(mem: Mem, objs: Objects, by_name, names):
    targets = {}
    for nm in names:
        idx = by_name.get(nm)
        if idx is None:
            continue
        targets[objs.ptr(idx)] = nm
    out = {nm: [] for nm in targets.values()}
    cache: dict[int, str | None] = {}
    for i, p in objs.all_ptrs():
        b = mem.read(p, 0x28)
        if b is None:
            continue
        flags = struct.unpack_from("<I", b, 0x08)[0]
        if flags & (RF_CLASS_DEFAULT | RF_ARCHETYPE):
            continue
        cls = struct.unpack_from("<Q", b, OBJ_CLASS)[0]
        if not cls:
            continue
        if cls in targets:
            out[targets[cls]].append((i, p, cls, flags))
            continue
        if cls not in cache:
            found = None
            for anc in super_chain(mem, cls, limit=14):
                if anc in targets:
                    found = targets[anc]
                    break
            cache[cls] = found
        if cache[cls]:
            out[cache[cls]].append((i, p, cls, flags))
    return out


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
    print("\nlive (non-CDO) instance counts:")
    for nm in WATCH:
        print(f"  {nm:<28} {len(found.get(nm, []))}")

    for tm_i, tm, _c, _f in found.get("WW3.WW3TeamManager", []):
        print(f"\n=== AWW3TeamManager [{tm_i:#x}] {tm:#x}")
        teams = read_tarray(mem, tm + TM_TEAMS)
        reps = read_tarray(mem, tm + TM_ACTION_REPLICATORS)
        warm = read_tarray(mem, tm + TM_WARMUP)
        print(f"  Teams             (+0x3D8) = "
              f"{'?' if teams is None else len(teams)} {[hex(t) for t in (teams or [])]}")
        print(f"  WarmupEntities    (+0x408) = {'?' if warm is None else len(warm)}")
        print(f"  ActionReplicators (+0x430) = "
              f"{'?' if reps is None else len(reps)} {[hex(r) for r in (reps or [])]}")
        print(f"  LocalPlayerState  (+0x448) = {fmt(mem.u64(tm + TM_LOCAL_PLAYER_STATE))}")
        for ti, team in enumerate(teams or []):
            squads = read_tarray(mem, team + TEAM_SQUADS)
            print(f"    Team[{ti}] {team:#x} TeamId={mem.u8(team + TEAM_ID)} "
                  f"Squads={'?' if squads is None else len(squads)}")
            for si, sq in enumerate(squads or []):
                slots = read_tarray(mem, sq + SQUAD_SLOTS)
                print(f"      Squad[{si}] {sq:#x} Slots="
                      f"{'?' if slots is None else len(slots)} "
                      f"leader={fmt(mem.u64(sq + SQUAD_LEADER))}")
                for k, slot in enumerate(slots or []):
                    print(f"        Slot[{k}] {slot:#x} "
                          f"PlayerState={fmt(mem.u64(slot + SLOT_PLAYER_STATE))}")

    for ar_i, ar, _c, _f in found.get("WW3.WW3ActionReplicator", []):
        print(f"\n=== AWW3ActionReplicator [{ar_i:#x}] {ar:#x}")
        print(f"  (action list head/tail pointers live in the class's own "
              f"ObjectProperties; dump them with _uobject_live.py --netfields)")

    for ps_i, ps, cls, flags in found.get("WW3.WW3PlayerState", []):
        chain = super_chain(mem, cls, limit=6)
        names = []
        for c in chain:
            ch = header(mem, c)
            nm = by_index.get(ch["index"], (None, None))[1] if ch else None
            names.append(nm if (nm and objs.ptr(ch["index"]) == c) else hex(c))
        print(f"\n=== AWW3PlayerState [{ps_i:#x}] {ps:#x} flags={flags:#x}")
        print(f"  class chain: {' -> '.join(names[:4])}")
        print(f"  PlayerCharacter   (+0x430) = {fmt(mem.u64(ps + PS_PLAYER_CHARACTER))}")
        cur = mem.u64(ps + PS_CURRENT_SQUAD)
        print(f"  CurrentSquad      (+0x710) = {fmt(cur)}    <-- the checklist bit")
        print(f"  bIsConnected      (+0x738) = {mem.u8(ps + PS_IS_CONNECTED)}")
        print(f"  PlayerStateUniqueID(+0x774)= {mem.u32(ps + PS_UNIQUE_ID)}")
        print(f"  InternalNetId     (+0x790) = {mem.u32(ps + PS_INTERNAL_NET_ID)}")
        print(f"  PlayingState      (+0x800) = {mem.u8(ps + PS_PLAYING_STATE)}")
        print(f"  bIsConnectedToMaster(+0x9D0)={mem.u8(ps + PS_CONNECTED_TO_MASTER)}")
        d = read_tarray(mem, ps + PS_SQUAD_DELEGATE)
        print(f"  squad delegate    (+0x5A0) = {'?' if d is None else len(d)} bound")

    for ch_i, ch, cls, flags in found.get("WW3.WW3Character", []):
        print(f"\n=== AWW3Character [{ch_i:#x}] {ch:#x} flags={flags:#x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
