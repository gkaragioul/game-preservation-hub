#!/usr/bin/env python3
"""Read the live client's deploy-screen state and the pawn's world coordinates.

Turn 8 established, with proven-live frames (`_live_frame.py`), that the client is
past the loading screen and sitting on the **deploy screen**: match HUD up, the
spectator camera flying over Dunhuang, `ESC-MENU` / `M-MAP` hints, one BASE spawn
tile, and a `DEPLOY` button reading **NOT READY**.  The question this answers is
what "NOT READY" is a function of.

`AWW3GamePlayerController` (Dumper-7 SDK) carries the deploy screen's whole
client-side state:

    0x1590  TScriptInterface<IWW3RespawnScreenData>   ClObjectResponsibleForRespawn
    0x15A0  TScriptInterface<IWW3DeployMapSelectable> ClRespawnTarget    <- the pick
    0x1600  UWW3RespawnRequestBase*                   SvRespawnRequest
    0x1608  AWW3InventoryGadgetStrike*                StrikeToSpawnSpectatorWith
    0x16F0  AWW3PlayerState*                          PlayerILookAtSpectating

A `TScriptInterface` is {UObject* ObjectPointer; void* InterfacePointer}, so a
null first qword means "nothing selected".

The pawn transform comes from `AActor::RootComponent` (0x160) ->
`USceneComponent::RelativeLocation` (0x13C).  On a root component that is world
space, and it is the `Net`/`RepNotify` field, i.e. the same number the server
replicates.  `--watch` samples it so displacement can be attributed to an input
rather than to a timestamp bit.

Read-only: PROCESS_QUERY_INFORMATION | PROCESS_VM_READ.  No writes, no injection.

Usage:
    python match_server/_deploy_gates_live.py
    python match_server/_deploy_gates_live.py --watch 8 --interval 0.25
    python match_server/_deploy_gates_live.py --loc-only
"""
from __future__ import annotations

import argparse
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _ps_sync_live import Mem, find_pid, main_module  # noqa: E402
from _team_graph_live import live_instances  # noqa: E402
from _uobject_live import DUMP_ROOT, OBJ_CLASS, Objects, load_dump  # noqa: E402

# APawn / AController / AActor (Engine SDK)
PAWN_CONTROLLER = 0x368
PAWN_PLAYERSTATE = 0x350
CTRL_PLAYERSTATE = 0x338
CTRL_STATENAME = 0x358
CTRL_PAWN = 0x360
ACTOR_ROOTCOMPONENT = 0x160
ACTOR_ROLE = 0x118
SCENE_RELATIVE_LOCATION = 0x13C
SCENE_RELATIVE_ROTATION = 0x148

# AWW3GamePlayerController (WW3 SDK)
PC_RESPAWN_SCREEN_DATA = 0x1590
PC_RESPAWN_TARGET = 0x15A0
PC_SV_RESPAWN_REQUEST = 0x1600
PC_STRIKE_SPAWN = 0x1608
PC_PLAYER_I_LOOK_AT = 0x16F0
PC_FAKE_MINIMAP = 0x1500
PC_INGAME_BACKPACK = 0x1510

PC_FIELDS = [
    (PC_RESPAWN_SCREEN_DATA, "ClObjectResponsibleForRespawn", "TScriptInterface"),
    (PC_RESPAWN_TARGET, "ClRespawnTarget", "TScriptInterface"),
    (PC_SV_RESPAWN_REQUEST, "SvRespawnRequest", "ptr"),
    (PC_STRIKE_SPAWN, "StrikeToSpawnSpectatorWith", "ptr"),
    (PC_PLAYER_I_LOOK_AT, "PlayerILookAtSpectating", "ptr"),
    (PC_FAKE_MINIMAP, "FakeMinimap", "ptr"),
    (PC_INGAME_BACKPACK, "InGameBackpackWidget", "ptr"),
]


def u64(mem, a):
    b = mem.read(a, 8)
    return None if b is None else struct.unpack("<Q", b)[0]


def vec3(mem, a):
    b = mem.read(a, 12)
    return None if b is None else struct.unpack("<fff", b)


class Namer:
    def __init__(self, mem, objs, by_index):
        self.mem, self.objs, self.by_index = mem, objs, by_index
        self.live = {p for _i, p in objs.all_ptrs()}

    def is_live(self, ptr: int) -> bool:
        return bool(ptr) and ptr in self.live

    def class_of(self, ptr: int) -> str:
        if not self.is_live(ptr):
            return "NOT-A-LIVE-UOBJECT" if ptr else "NULL"
        cls = u64(self.mem, ptr + OBJ_CLASS) or 0
        if not cls:
            return "live (class unreadable)"
        idx = self.mem.read(cls + 0x0C, 4)
        if idx is None:
            return "live (class idx unreadable)"
        ci = struct.unpack("<i", idx)[0]
        ent = self.by_index.get(ci)
        return f"live {ent[1]}" if ent else f"live (runtime class idx={ci:#x})"


def pawn_location(mem, pawn: int):
    root = u64(mem, pawn + ACTOR_ROOTCOMPONENT) or 0
    if not root:
        return None, None, None
    return root, vec3(mem, root + SCENE_RELATIVE_LOCATION), \
        vec3(mem, root + SCENE_RELATIVE_ROTATION)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=str(DUMP_ROOT / "GObjects-Dump.txt"))
    ap.add_argument("--watch", type=int, default=0, help="sample location N times")
    ap.add_argument("--interval", type=float, default=0.25)
    ap.add_argument("--loc-only", action="store_true")
    args = ap.parse_args()

    pid = find_pid()
    mem = Mem(pid)
    mod_base, _ = main_module(pid)
    objs = Objects(mem, mod_base)
    by_index, by_name = load_dump(Path(args.dump))
    namer = Namer(mem, objs, by_index)
    print(f"pid={pid}  {objs.num_elements} live UObjects")

    chars = live_instances(mem, objs, by_name,
                           ["WW3.WW3Character"]).get("WW3.WW3Character", [])
    if not chars:
        print("no live AWW3Character")
        return 2

    for _i, ch, _c, _f in chars:
        role = mem.read(ch + ACTOR_ROLE, 1)
        role = role[0] if role else -1
        pc = u64(mem, ch + PAWN_CONTROLLER) or 0
        print(f"\n=== AWW3Character {ch:#x}  Role={role}")
        root, loc, rot = pawn_location(mem, ch)
        print(f"  RootComponent (+0x160) = {root:#x}")
        if loc:
            print(f"  LOCATION  X={loc[0]:.3f}  Y={loc[1]:.3f}  Z={loc[2]:.3f}")
        if rot:
            print(f"  ROTATION  P={rot[0]:.3f}  Y={rot[1]:.3f}  R={rot[2]:.3f}")
        if args.loc_only:
            continue

        print(f"  Controller (+0x368) = {pc:#x}  {namer.class_of(pc)}")
        if not namer.is_live(pc):
            continue
        cpawn = u64(mem, pc + CTRL_PAWN) or 0
        cps = u64(mem, pc + CTRL_PLAYERSTATE) or 0
        print(f"    AController::Pawn        (+0x360) = {cpawn:#x} "
              f"{'== this character' if cpawn == ch else namer.class_of(cpawn)}")
        print(f"    AController::PlayerState (+0x338) = {cps:#x}  {namer.class_of(cps)}")
        sn = mem.read(pc + CTRL_STATENAME, 8)
        if sn:
            cmp_, num = struct.unpack("<ii", sn)
            print(f"    AController::StateName   (+0x358) = FName(cmp={cmp_}, num={num})")

        print("    --- deploy screen state (AWW3GamePlayerController) ---")
        for off, name, kind in PC_FIELDS:
            v = u64(mem, pc + off) or 0
            extra = ""
            if kind == "TScriptInterface":
                iface = u64(mem, pc + off + 8) or 0
                extra = f"  iface={iface:#x}"
            print(f"      {name:<32} (+{off:#06x}) = {v:#x}  {namer.class_of(v)}{extra}")

    if args.watch:
        ch = chars[0][1]
        print(f"\n=== watching location of {ch:#x} "
              f"({args.watch} samples @ {args.interval}s)")
        first = None
        for i in range(args.watch):
            _r, loc, rot = pawn_location(mem, ch)
            if loc is None:
                print(f"  [{i}] unreadable")
            else:
                if first is None:
                    first = loc
                d = ((loc[0] - first[0]) ** 2 + (loc[1] - first[1]) ** 2
                     + (loc[2] - first[2]) ** 2) ** 0.5
                print(f"  [{i}] t={time.time():.3f} X={loc[0]:10.3f} Y={loc[1]:10.3f} "
                      f"Z={loc[2]:9.3f}  |d| from first = {d:.3f}"
                      + (f"  yaw={rot[1]:.2f}" if rot else ""))
            if i != args.watch - 1:
                time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
