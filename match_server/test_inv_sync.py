#!/usr/bin/env python3
r"""RED/GREEN tests for the `SvReplicatedInventory` block -- the property that
makes the last two synchronization bits (`InventoryManager` 0x04 and
`WeaponsAttachments` 0x10) reachable.

Every constant below is read out of the shipping client, off the live process, or
out of the capture.  Provenance, step by step:

The callback and its delegate
    `0x1411C0F30` is the only producer of the `InventoryManager` bit and one of
    two producers of `WeaponsAttachments` (`_exe_xref.py 0x1411D57F0`).  It has
    no call sites and no vtable slot; `AWW3Character`'s constructor
    (`0x141186910`) binds it to the multicast delegate at
    `UWW3InventoryManagerBase + 0xF0`.  `_delegate_live.py` reads that binding
    off the **live object**: the delegate's single
    `TBaseUObjectMethodDelegateInstance` carries method pointer -> exe
    `0x1411C0F30`, so the callback is demonstrably subscribed and the bit can
    only be missing because the delegate is never broadcast.

The broadcaster
    `TBaseMulticastDelegate<void>::Broadcast` is `0x140425920` -- confirmed by
    disassembly: `inc [rcx+0x14]` (LockInvocationList), reverse iteration over
    `Num` with stride 0x10, `call [rax+0x48]` (`ExecuteIfSafe`).
    `_delegate_broadcast_scan.py` finds exactly **two** sites in the whole image
    that call it with `owner + 0xF0`:

        0x140CACA24  in UWW3InventoryManagerBase::OnRep_ReplicatedInventory_Implementation
                     (0x140CAC020 -- resolved from the live UFunction's exec thunk
                     `WW3.WW3InventoryManagerBase.OnRep_ReplicatedInventory`)
        0x140C8F3E7  in the shared helper 0x140C8F390, tail-called by
                     OnRep_WeaponsNumber (0x140C46520) and called by
                     OnRep_CurrentItemRepInfo (0x140C41660) + 3 others

    (Checkpoint 17's two candidates called `0x140C53E30`, which disassembles to
    a `TArray<TDelegateBase>::Empty` -- delegate teardown, not broadcast.)

The guard both sites share
    `vtable[0x3D0]`, which on the live `UWW3InventoryManager` is `0x140C37770`:

        bool IsSynchronized() {
            if (!IsValid(OwnerCharacter@0xE0))          return false;
            if (GetCurrentItem() == nullptr)            return false;
            if (GetNetMode() <= NM_DedicatedServer)     return true;
            if (Owner->Role != ROLE_Authority
                && !bAcceptedReplicatedInventory@0x2B9) return false;
            return FWW3ReplicatedInventory::IsValid(GetActiveInventory());
        }

    `GetCurrentItem` (`0x140C2AD80`) returns `ClientCurrentItem` (+0x290) for a
    client; `GetActiveInventory` (`0x140C9B880`) returns `&SvReplicatedInventory`
    (+0x1F0) when `GetNetMode() >= NM_Client`; `+0x2B9` is written by
    `OnRep_ReplicatedInventory` itself (1 when it accepts a valid struct, 0 on
    the early-out).

`FWW3ReplicatedInventory::IsValid` (`0x140CA45D0`)
    `BatchID(+0x30) != 0`, then all five `EWW3InventorySlotState`s
    (+0x28..+0x2C) `!= None`, then -- per slot -- **only when the state is
    `Empty(1)`** it loads the item pointer and returns false if that pointer is
    a live (non-PendingKill) object.  `Assigned(2)` skips the pointer check
    entirely.  So "Assigned + real actor" and "Empty + null" both pass, and
    "Empty + live actor" is the only rejection.

Why this is not a capture replay
    `_im_stream_scan.py` walks every `UWW3InventoryManager` subobject block in
    the whole 10126-entry stream.  There are two, and between them the working
    server sends `SvReplicatedInventory.ForceReplicationVar` (h22) and nothing
    else -- h10..h21 are **never sent**.  The live client reads back exactly that
    shape (`ForceReplicationVar=2`, `BatchID=0`, five `None` states, five null
    pointers), so our replay of capture src 212/213 is faithful and the missing
    data was never on this wire.  Same situation as `TM_Synchronize`: the
    encoding, channel, subobject and NetGUIDs are capture-grounded, the values
    are not a replay.

NetGUIDs
    9410 (primary HK417) and 9412 (secondary Glock) are the capture's own values,
    decoded out of the same block at src 212/213:
    `WeaponsPreloadRequest.PrimaryWeapon` h27 and `.SecondaryWeapon` h29 -- the
    packed ints 37509/37513.  Both are open and ACKed on ch87/ch86 in the live
    session.
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import derive_rep_handles as D  # noqa: E402
import inventory_sync as IS  # noqa: E402
from _decode_rep_block import decode, layout  # noqa: E402
from cam_im_resend import _walk_content_blocks  # noqa: E402
from repblock import ceil_log_two, read_packed, read_u  # noqa: E402

IM_CLASS = "UWW3InventoryManager"


def _sdk():
    sdk = Path(os.environ.get("WW3_DUMPER7_DIR", str(D.DEFAULT_DUMP)))
    if sdk.name != "SDK":
        sdk = sdk / "CppSDK" / "SDK"
    return sdk


def _layout():
    classes, structs = D.parse_sdk(_sdk())
    return layout(IM_CLASS, classes, structs), D.parse_enums(_sdk())


# --------------------------------------------------------------------------
# 1. The native predicates, mirrored


def test_replicated_inventory_is_valid_rejects_zero_batch_id():
    inv = IS.SvInventory(batch_id=0, primary_weapon=9410, secondary_weapon=9412,
                         states=(2, 2, 1, 1, 1))
    assert not IS.replicated_inventory_is_valid(inv), \
        "BatchID == 0 must fail (0x140CA45EA: cmp [rcx+0x30],0; je false)"


def test_replicated_inventory_is_valid_rejects_any_none_slot_state():
    for i in range(5):
        states = [2, 2, 1, 1, 1]
        states[i] = IS.SLOT_NONE
        inv = IS.SvInventory(batch_id=1, primary_weapon=9410,
                             secondary_weapon=9412, states=tuple(states))
        assert not IS.replicated_inventory_is_valid(inv), \
            f"slot {i} == None must fail"


def test_empty_slot_with_a_live_item_is_the_only_pointer_rejection():
    # Empty(1) + a live item -> false; Empty(1) + null -> true;
    # Assigned(2) + live item -> true (the pointer check is skipped).
    bad = IS.SvInventory(batch_id=1, primary_weapon=9410, secondary_weapon=0,
                         states=(IS.SLOT_EMPTY, 1, 1, 1, 1))
    assert not IS.replicated_inventory_is_valid(bad, live_netguids={9410})
    ok_null = IS.SvInventory(batch_id=1, primary_weapon=0, secondary_weapon=0,
                             states=(1, 1, 1, 1, 1))
    assert IS.replicated_inventory_is_valid(ok_null, live_netguids={9410})
    ok_assigned = IS.SvInventory(batch_id=1, primary_weapon=9410,
                                 secondary_weapon=0,
                                 states=(IS.SLOT_ASSIGNED, 1, 1, 1, 1))
    assert IS.replicated_inventory_is_valid(ok_assigned, live_netguids={9410})


def test_is_synchronized_mirrors_the_client_branch_of_0x140c37770():
    inv = IS.default_sv_inventory()
    assert IS.is_synchronized(owner_valid=True, client_current_item=9412,
                              accepted=True, sv=inv, live_netguids={9410, 9412})
    assert not IS.is_synchronized(owner_valid=False, client_current_item=9412,
                                  accepted=True, sv=inv, live_netguids={9410, 9412})
    assert not IS.is_synchronized(owner_valid=True, client_current_item=0,
                                  accepted=True, sv=inv, live_netguids={9410, 9412}), \
        "ClientCurrentItem == NULL must fail -- this is the live client's state"
    assert not IS.is_synchronized(owner_valid=True, client_current_item=9412,
                                  accepted=False, sv=inv, live_netguids={9410, 9412}), \
        "+0x2B9 == 0 must fail -- this is the live client's state"


def test_the_live_clients_measured_state_is_reproduced_as_not_synchronized():
    """`_inv_sync_gates.py` on PID 65836: everything zero. Must be False."""
    zero = IS.SvInventory(batch_id=0, primary_weapon=0, secondary_weapon=0,
                          states=(0, 0, 0, 0, 0))
    assert not IS.is_synchronized(owner_valid=True, client_current_item=0,
                                  accepted=False, sv=zero, live_netguids=set())


# --------------------------------------------------------------------------
# 2. The payload, round-tripped through the wire-validated decoder


def test_slot_state_enum_is_two_bits_on_the_wire():
    (_by_h, _types), enums = _layout()
    assert enums["EWW3InventorySlotState"] == 3
    assert ceil_log_two(enums["EWW3InventorySlotState"]) == IS.SLOT_STATE_BITS == 2


def test_payload_round_trips_through_the_capture_validated_decoder():
    (by_h, types), enums = _layout()
    payload = IS.build_inventory_sync_payload()
    r = decode(payload, by_h, types, enums=enums)
    assert r["closed"], f"payload must exact-consume: {r['reason']} left={r['left']}"
    assert r["left"] == 0, r["left"]
    handles = [h for h, *_x in r["seq"]]
    assert handles == [3, 4, 5, 10, 11, 15, 16, 17, 18, 19, 20], handles
    got = {}
    for h, name, _t, w, _note, pos in r["seq"]:
        if name.endswith("CurrentItem") or "Weapon" in name and "State" not in name:
            got[h] = read_packed(payload, pos)[0]
        else:
            got[h] = read_u(payload, pos, w)
    assert got[3] == IS.CAPTURE_SECONDARY_WEAPON, got[3]
    assert got[10] == IS.CAPTURE_PRIMARY_WEAPON, got[10]
    assert got[11] == IS.CAPTURE_SECONDARY_WEAPON, got[11]
    assert got[15] == IS.SLOT_ASSIGNED and got[16] == IS.SLOT_ASSIGNED
    assert got[17] == got[18] == got[19] == IS.SLOT_EMPTY
    assert got[20] == 1, got[20]


def test_payload_never_touches_handles_the_capture_owns():
    """h22 ForceReplicationVar and the WeaponsPreloadRequest handles are the
    capture's; overwriting them would diverge from the working reference."""
    (by_h, types), enums = _layout()
    r = decode(IS.build_inventory_sync_payload(), by_h, types, enums=enums)
    handles = {h for h, *_x in r["seq"]}
    assert 22 not in handles, "must not rewrite SvReplicatedInventory.ForceReplicationVar"
    assert not handles.intersection(range(23, 42)), \
        "must not rewrite WeaponsPreloadRequest / gadget handles"


def test_force_replication_var_is_opt_in_and_decodes_as_h22():
    """The diagnostic handle: off unless asked for, and when asked for it is the
    one handle the client has provably already applied from the capture."""
    (by_h, types), enums = _layout()
    base = decode(IS.build_inventory_sync_payload(), by_h, types, enums=enums)
    assert 22 not in {h for h, *_x in base["seq"]}
    r = decode(IS.build_inventory_sync_payload(force_replication_var=7),
               by_h, types, enums=enums)
    assert r["closed"] and r["left"] == 0, r["reason"]
    seq = {h: (w, pos) for h, _n, _t, w, _note, pos in r["seq"]}
    assert 22 in seq, "force_replication_var must emit h22"
    w, pos = seq[22]
    assert w == 32 and read_u(IS.build_inventory_sync_payload(
        force_replication_var=7), pos, 32) == 7


def test_default_payload_would_satisfy_the_native_predicate():
    inv = IS.default_sv_inventory()
    assert IS.replicated_inventory_is_valid(inv, live_netguids={9410, 9412, 9408, 9402})
    assert IS.is_synchronized(owner_valid=True,
                              client_current_item=IS.CAPTURE_SECONDARY_WEAPON,
                              accepted=True, sv=inv,
                              live_netguids={9410, 9412, 9408, 9402})


def test_empty_mode_is_also_valid_and_smaller():
    """The bisect variant: all five slots Empty with null pointers."""
    inv = IS.default_sv_inventory(mode="empty")
    assert inv.states == (IS.SLOT_EMPTY,) * 5
    assert inv.primary_weapon == 0 and inv.secondary_weapon == 0
    assert IS.replicated_inventory_is_valid(inv, live_netguids={9410, 9412})
    small = IS.build_inventory_sync_payload(mode="empty")
    assert len(small) < len(IS.build_inventory_sync_payload())


# --------------------------------------------------------------------------
# 3. Framing on the real channel/subobject


def test_block_is_a_stably_named_ch3_subobject_block_for_9384():
    bits = IS.build_inventory_sync_block_bits()
    blocks = _walk_content_blocks(bits)
    assert len(blocks) == 1, len(blocks)
    b = blocks[0]
    assert b["subNetGUID"] == IS.IM_NETGUID == 9384, b["subNetGUID"]
    assert b["isActor"] is False
    assert b["stablyNamed"] == 1
    assert b["hasRepLayout"] == 1
    assert b["payload"] == IS.build_inventory_sync_payload()


def test_subobject_matches_the_one_the_capture_uses():
    from cam_im_resend import IM_NETGUID as CAPTURE_IM
    assert IS.IM_NETGUID == CAPTURE_IM, \
        "must reuse the capture's InventoryManager subobject, not a new one"


# --------------------------------------------------------------------------
# 4. Fail-closed identity gate


def test_packet_sha256_pins_the_default_payload():
    bits = IS.build_inventory_sync_block_bits()
    raw = bytes(int("".join(str(b) for b in bits[i:i + 8][::-1]), 2)
                for i in range(0, len(bits) - len(bits) % 8, 8))
    digest = hashlib.sha256(bytes(bits)).hexdigest()
    assert IS.INV_SYNC_PACKET_SHA256 == digest, (
        "the pinned SHA must match the built packet; if you changed the payload "
        f"on purpose, review it and update the constant to {digest}")
    assert raw is not None


def test_a_changed_payload_changes_the_sha():
    a = hashlib.sha256(bytes(IS.build_inventory_sync_block_bits())).hexdigest()
    b = hashlib.sha256(bytes(IS.build_inventory_sync_block_bits(
        primary_weapon=9999))).hexdigest()
    assert a != b


def test_builder_refuses_a_payload_that_cannot_satisfy_the_predicate():
    """Fail closed: never put a struct on a live channel that provably cannot
    flip the bit -- that would spend a live A/B for no information."""
    try:
        IS.build_inventory_sync_payload(batch_id=0)
    except ValueError as exc:
        assert "BatchID" in str(exc) or "IsValid" in str(exc), exc
    else:
        raise AssertionError("batch_id=0 must raise, not emit an invalid struct")
    try:
        IS.build_inventory_sync_payload(states=(0, 2, 1, 1, 1))
    except ValueError:
        pass
    else:
        raise AssertionError("a None slot state must raise")


def _run() -> int:
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in fns:
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"[FAIL] {name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"[ERROR] {name}: {type(exc).__name__}: {exc}")
        else:
            print(f"[ok]   {name}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())
