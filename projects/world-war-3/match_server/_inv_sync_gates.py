#!/usr/bin/env python3
"""Read the live inputs of the `InventoryManager` / `WeaponsAttachments` bits.

`_exe_xref.py 0x1411d57f0` (the sole `MarkSynchronized` mutator) shows exactly
which call site sets which bit.  `0x1411c0f30` is the **only** producer of
`InventoryManager` (0x04) and one of two producers of `WeaponsAttachments`
(0x10, the other being `0x1411d6000`).  Decompiled:

    if (!Character->[0x848])                 return;   // the FSync object
    inv = Character->InventoryManager;                 // +0x7B0, named by the SDK
    if (!IsValid(inv))                       return;
    MarkSynchronized(Sync, 0x04);                      // InventoryManager
    if (!0x140C11320(inv))                   return;
    MarkSynchronized(Sync, 0x10);                      // WeaponsAttachments

and `0x140C11320` opens with `rdi = inv->[0xE0]; if (!IsValid(rdi)) return false`.

So the `InventoryManager` bit needs nothing but a valid
`AWW3Character::InventoryManager` -- plus this function actually being invoked;
it has no direct call sites, so it is reached through a delegate.  This prints
the live values so "the component is missing" and "the callback never fired" can
be told apart instead of guessed at.

The broadcaster (turn 7)
------------------------
`0x1411c0f30` is bound to the multicast delegate at `UWW3InventoryManagerBase +
0xF0` -- `_delegate_live.py` reads the binding off the live object, so that is
measured, not inferred.  `_delegate_broadcast_scan.py` finds exactly two sites in
the whole image that broadcast a delegate at `+0xF0` through the real
`TBaseMulticastDelegate<void>::Broadcast` (`0x140425920`):

    0x140caca24  inside UWW3InventoryManagerBase::OnRep_ReplicatedInventory_Implementation
                 (0x140cac020, the RepNotify of SvReplicatedInventory @0x1F0)
    0x140c8f3e7  inside the shared helper 0x140c8f390 ("NotifySynchronized"),
                 tail-called by OnRep_WeaponsNumber (0x140c46520),
                 OnRep_CurrentItemRepInfo (0x140c41660) and three others

Both are gated on the same virtual, `vtable[0x3D0]`, which on the live
`UWW3InventoryManager` is `0x140c37770`:

    bool IsSynchronized() {
        if (!IsValid(OwnerCharacter@0xE0))             return false;
        if (GetCurrentItem() == nullptr)               return false;  // client: ClientCurrentItem@0x290
        if (GetNetMode() <= NM_DedicatedServer)        return true;
        if (OwnerCharacter->Role != ROLE_Authority
            && !bAcceptedReplicatedInventory@0x2B9)    return false;
        return FWW3ReplicatedInventory::IsValid(       // 0x140ca45d0
                   GetNetMode() >= NM_Client ? &SvReplicatedInventory@0x1F0
                                             : &ClReplicatedInventory@0x238);
    }

`0x2B9` is written by `OnRep_ReplicatedInventory` itself: 1 once it accepts a
valid `SvReplicatedInventory`, 0 on the early-out when the struct is invalid.
`FWW3ReplicatedInventory::IsValid` requires `BatchID != 0` and all five
`EWW3InventorySlotState`s != `None`.  So both remaining bits are downstream of
one replicated property -- which is why this probe now evaluates the whole
predicate rather than only the two preconditions of `0x1411c0f30`.

Read-only: PROCESS_QUERY_INFORMATION | PROCESS_VM_READ.

Usage:
    python match_server/_inv_sync_gates.py
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _ps_sync_live import Mem, find_pid, main_module  # noqa: E402
from _team_graph_live import live_instances  # noqa: E402
from _uobject_live import DUMP_ROOT, OBJ_CLASS, Objects, load_dump  # noqa: E402

CH_SYNC = 0x848              # AWW3Character -> FSync*
CH_INVENTORY_MANAGER = 0x7B0  # UWW3InventoryManager*
SYNC_VALUE = 0x48
SYNC_REQUIRED = 0x4A
INV_GATE = 0xE0              # the object 0x140C11320 validates first

# UWW3InventoryManagerBase, from the Dumper-7 SDK plus the disassembly
INV_OWNER = 0xE0             # AWW3Character* (native, before AttachingToComponent)
INV_DELEGATE = 0xF0          # the multicast delegate 0x1411c0f30 is bound to
INV_CURRENT_ITEM_REP = 0x188  # FWW3CurrentItemRepInfo.CurrentItem
INV_SV_REPLICATED = 0x1F0    # FWW3ReplicatedInventory SvReplicatedInventory (Net, RepNotify)
INV_CL_REPLICATED = 0x238    # FWW3ReplicatedInventory ClReplicatedInventory
INV_CLIENT_CURRENT_ITEM = 0x290   # AWW3InventoryItem* ClientCurrentItem
INV_ACCEPTED = 0x2B9         # bool, set by OnRep_ReplicatedInventory
ACTOR_ROLE = 0x118           # AActor::Role

SLOT_STATES = {0: "None", 1: "Empty", 2: "Assigned", 3: "Max"}
# FWW3ReplicatedInventory, 0x48 bytes
RI_PTRS = [(0x00, "PrimaryWeapon"), (0x08, "SecondaryWeapon"),
           (0x10, "PrimaryGadget"), (0x18, "SecondaryGadget"),
           (0x20, "AdditionalGadget")]
RI_STATES = [(0x28, "PrimaryWeaponSlotState"), (0x29, "SecondaryWeaponSlotState"),
             (0x2A, "PrimaryGadgetSlotState"), (0x2B, "SecondaryGadgetSlotState"),
             (0x2C, "AdditionalGadgetSlotState")]

BITS = [(0x01, "Controller"), (0x02, "PlayerState"), (0x04, "InventoryManager"),
        (0x08, "CharacterAttachments"), (0x10, "WeaponsAttachments"),
        (0x20, "GameState"), (0x40, "LocalClientConfigs"), (0x80, "MapLevels")]


def u8(mem, a):
    b = mem.read(a, 1)
    return None if b is None else b[0]


def u64(mem, a):
    b = mem.read(a, 8)
    return None if b is None else struct.unpack("<Q", b)[0]


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

    # Every live UObject's address, so "is this pointer a live object?" is answered
    # by GObjects membership rather than by the pointer merely being non-null.
    live = {p for _i, p in objs.all_ptrs()}

    for _i, ch, _c, _f in live_instances(mem, objs, by_name,
                                         ["WW3.WW3Character"]).get("WW3.WW3Character", []):
        sync = u64(mem, ch + CH_SYNC) or 0
        inv = u64(mem, ch + CH_INVENTORY_MANAGER) or 0
        print(f"\n=== AWW3Character {ch:#x}")
        if sync:
            val = u8(mem, sync + SYNC_VALUE) or 0
            req = u8(mem, sync + SYNC_REQUIRED) or 0
            missing = req & ~val
            print(f"  Sync (+0x848) {sync:#x}  Value={val:#04x} Required={req:#04x}")
            print("    " + " ".join(f"{'+' if val & m else '-'}{n}" for m, n in BITS))
            print(f"    MISSING = {missing:#04x} -> "
                  f"{[n for m, n in BITS if missing & m]}")
        else:
            print("  Sync (+0x848) = NULL")
        print(f"  InventoryManager (+0x7B0) = {inv:#x}"
              f"   {'LIVE UObject' if inv in live else 'NOT a live UObject'}")
        if inv:
            cls = u64(mem, inv + OBJ_CLASS) or 0
            idx = None
            if cls:
                raw = mem.read(cls + 0x0C, 4)
                idx = struct.unpack("<i", raw)[0] if raw else None
            print(f"    class = {by_index.get(idx, '?')}")
            gate = u64(mem, inv + INV_GATE) or 0
            print(f"    +0xE0 (0x140C11320's first check) = {gate:#x}"
                  f"   {'LIVE UObject -> bit 0x10 reachable' if gate in live else 'NOT live -> bit 0x10 blocked'}")
            report_is_synchronized(mem, live, inv, ch)
    return 0


def replicated_inventory(mem, live, base: int, label: str) -> bool:
    """Print an FWW3ReplicatedInventory and evaluate 0x140ca45d0's own checks."""
    blob = mem.read(base, 0x48)
    if blob is None:
        print(f"    {label}: unreadable")
        return False
    batch = struct.unpack_from("<I", blob, 0x30)[0]
    cid = struct.unpack_from("<Q", blob, 0x38)[0]
    force = struct.unpack_from("<I", blob, 0x40)[0]
    print(f"    {label} @ {base:#x}")
    print(f"      BatchID={batch}  ClientInventoryID={cid}  ForceReplicationVar={force}")
    ok = batch != 0
    if not ok:
        print("      -> BatchID == 0 : FWW3ReplicatedInventory::IsValid FAILS here")
    for off, name in RI_STATES:
        v = blob[off]
        if v == 0:
            ok = False
        print(f"      {name:<26} = {v} {SLOT_STATES.get(v, '?')}"
              f"{'   <- None: IsValid fails' if v == 0 else ''}")
    for off, name in RI_PTRS:
        p = struct.unpack_from("<Q", blob, off)[0]
        print(f"      {name:<26} = {p:#x}"
              f"   {'live' if p in live else ('NULL' if not p else 'NOT live')}")
    return ok


def report_is_synchronized(mem, live, inv: int, ch: int) -> None:
    """Evaluate UWW3InventoryManagerBase::IsSynchronized (0x140c37770) live."""
    print(f"\n  --- IsSynchronized() [vtable 0x3D0 -> 0x140c37770] on {inv:#x}")
    owner = u64(mem, inv + INV_OWNER) or 0
    owner_ok = owner in live
    print(f"    OwnerCharacter (+0xE0)        = {owner:#x}  "
          f"{'IsValid' if owner_ok else 'INVALID -> returns false'}")

    cur = u64(mem, inv + INV_CLIENT_CURRENT_ITEM) or 0
    rep_cur = u64(mem, inv + INV_CURRENT_ITEM_REP) or 0
    print(f"    ClientCurrentItem (+0x290)    = {cur:#x}  "
          f"{'live' if cur in live else ('NULL -> GetCurrentItem()==null -> returns false' if not cur else 'NOT live')}")
    print(f"    CurrentItemRepInfo.CurrentItem(+0x188) = {rep_cur:#x}"
          f"   {'live' if rep_cur in live else ''}")

    role = mem.u8(ch + ACTOR_ROLE)
    accepted = mem.u8(inv + INV_ACCEPTED)
    print(f"    Character Role (+0x118)       = {role} "
          f"({'ROLE_Authority' if role == 3 else 'not authority'})")
    print(f"    bAcceptedReplicatedInventory (+0x2B9) = {accepted}"
          f"{'   <- 0: OnRep_ReplicatedInventory never accepted an inventory' if not accepted else ''}")

    sv_ok = replicated_inventory(mem, live, inv + INV_SV_REPLICATED,
                                 "SvReplicatedInventory (+0x1F0, Net RepNotify) [the one a client reads]")
    replicated_inventory(mem, live, inv + INV_CL_REPLICATED, "ClReplicatedInventory (+0x238)")

    dele = mem.read(inv + INV_DELEGATE, 0x18)
    if dele:
        num = struct.unpack_from("<i", dele, 8)[0]
        print(f"    OnSynchronized delegate (+0xF0) InvocationList.Num = {num}"
              f"   {'(0x1411c0f30 is bound -- see _delegate_live.py)' if num else '(EMPTY)'}")

    verdict = owner_ok and bool(cur) and (role == 3 or bool(accepted)) and sv_ok
    print(f"    => IsSynchronized() would return {verdict}")
    if not verdict:
        why = []
        if not owner_ok:
            why.append("owner character not valid")
        if not cur:
            why.append("ClientCurrentItem is NULL")
        if role != 3 and not accepted:
            why.append("+0x2B9 == 0 (no accepted SvReplicatedInventory)")
        if not sv_ok:
            why.append("SvReplicatedInventory fails FWW3ReplicatedInventory::IsValid")
        print(f"    BLOCKED BY: {'; '.join(why)}")


if __name__ == "__main__":
    raise SystemExit(main())
