#!/usr/bin/env python3
r"""`SvReplicatedInventory` -- the property the last two sync bits hang off.

Why this module exists
----------------------
`0x1411C0F30` is the only producer of the `InventoryManager` sync bit (0x04) and
one of two producers of `WeaponsAttachments` (0x10).  It has no call sites and no
vtable slot: `AWW3Character`'s constructor (`0x141186910`) binds it to the
multicast delegate at `UWW3InventoryManagerBase + 0xF0`, and
`_delegate_live.py` reads that binding off the *live object* -- the delegate's
one `TBaseUObjectMethodDelegateInstance` carries method pointer -> exe
`0x1411C0F30`.  So the callback is subscribed and simply never invoked.

`_delegate_broadcast_scan.py` finds exactly two sites in the image that call the
real `TBaseMulticastDelegate<void>::Broadcast` (`0x140425920`) with
`owner + 0xF0`:

    0x140CACA24  UWW3InventoryManagerBase::OnRep_ReplicatedInventory_Implementation
                 (0x140CAC020; resolved from the live UFunction exec thunk of
                 `WW3.WW3InventoryManagerBase.OnRep_ReplicatedInventory`)
    0x140C8F3E7  the shared helper 0x140C8F390, tail-called by
                 OnRep_WeaponsNumber (0x140C46520) and called by
                 OnRep_CurrentItemRepInfo (0x140C41660) + 3 others

Both are gated on `vtable[0x3D0]` = `0x140C37770`:

    bool UWW3InventoryManagerBase::IsSynchronized() {
        if (!IsValid(OwnerCharacter@0xE0))          return false;
        if (GetCurrentItem() == nullptr)            return false;   // client: +0x290
        if (GetNetMode() <= NM_DedicatedServer)     return true;
        if (Owner->Role != ROLE_Authority
            && !bAcceptedReplicatedInventory@0x2B9) return false;
        return FWW3ReplicatedInventory::IsValid(GetActiveInventory());
    }

`_inv_sync_gates.py` evaluates all of that on the live client: owner valid,
`ClientCurrentItem` NULL, `+0x2B9` 0, and `SvReplicatedInventory` entirely
zeroed.  So the whole tail is downstream of one replicated property.

Relationship to the capture
---------------------------
`_im_stream_scan.py` walks every `UWW3InventoryManager` subobject block in the
whole 10126-entry stream.  There are two, and together they carry
`SvReplicatedInventory.ForceReplicationVar` (h22) and nothing else -- h10..h21
are never sent by the working server, and the live client reads back exactly that
shape.  So this is not a replay: the channel (ch3), the subobject (9384), the
content-block framing, the RepLayout encoder and the weapon NetGUIDs are all
capture-grounded, but the values are synthesised -- the same standing as
`TM_Synchronize` in `action_replicator.py`.

`FWW3ReplicatedInventory::IsValid` (`0x140CA45D0`)
--------------------------------------------------
`BatchID != 0`, all five slot states `!= None`, and -- only for a slot whose
state is `Empty(1)` -- the corresponding item pointer must not be a live object.
`Assigned(2)` skips the pointer check entirely.
"""
from __future__ import annotations

import hashlib
from typing import Iterable, NamedTuple

from actor_channel import write_rep_properties, write_subobject_content_block
from netguid import GuidWriter

# The capture's own InventoryManager subobject on the pawn channel (ch3),
# the same one `cam_im_resend.py` resends from src 212/213.
IM_NETGUID = 9384
PAWN_CHANNEL = 3

# UWW3InventoryManager RepLayout handles (derive_rep_handles over the Dumper-7
# SDK; the same model that exact-consumes the capture's own 1978-bit IM block).
H_CURRENT_ITEM = 3
H_CURRENT_ITEM_FROM_RESET = 4
H_CURRENT_ITEM_FORCE_ID = 5
H_SV_PRIMARY_WEAPON = 10
H_SV_SECONDARY_WEAPON = 11
H_SV_PRIMARY_GADGET = 12
H_SV_SECONDARY_GADGET = 13
H_SV_ADDITIONAL_GADGET = 14
H_SV_SLOT_STATES = (15, 16, 17, 18, 19)
H_SV_BATCH_ID = 20
H_SV_FORCE_REPLICATION = 22          # the capture owns this one -- never rewrite it

# EWW3InventorySlotState : uint8 { None=0, Empty=1, Assigned=2, Max=3 }
SLOT_NONE = 0
SLOT_EMPTY = 1
SLOT_ASSIGNED = 2
# UEnumProperty::NetSerializeItem -> SerializeBits(CeilLogTwo(GetMaxEnumValue()))
SLOT_STATE_BITS = 2
BATCH_ID_BITS = 32
FORCE_ITEM_ID_BITS = 8

# Decoded out of the capture's own IM block at src 212/213:
# WeaponsPreloadRequest.PrimaryWeapon (h27, packed 37509) and
# .SecondaryWeapon (h29, packed 37513).  Both are opened and ACKed on ch87/ch86
# by the ownership bootstrap under WW3_INV_ATTACH.
CAPTURE_PRIMARY_WEAPON = 9410        # HK417A2, ch87
CAPTURE_SECONDARY_WEAPON = 9412      # Glock17, ch86


class SvInventory(NamedTuple):
    """FWW3ReplicatedInventory, 0x48 bytes, as the wire carries it."""

    batch_id: int
    primary_weapon: int = 0
    secondary_weapon: int = 0
    primary_gadget: int = 0
    secondary_gadget: int = 0
    additional_gadget: int = 0
    states: tuple[int, int, int, int, int] = (SLOT_NONE,) * 5

    @property
    def items(self) -> tuple[int, int, int, int, int]:
        return (self.primary_weapon, self.secondary_weapon, self.primary_gadget,
                self.secondary_gadget, self.additional_gadget)


def replicated_inventory_is_valid(inv: SvInventory,
                                  live_netguids: Iterable[int] = ()) -> bool:
    """Mirror of `FWW3ReplicatedInventory::IsValid` (`0x140CA45D0`).

    `live_netguids` stands in for the client's `IsValid(UObject*)`: a NetGUID in
    the set resolves to a live, non-PendingKill actor on the client.
    """
    live = set(live_netguids)
    if inv.batch_id == 0:                                  # cmp [rcx+0x30],0
        return False
    if any(s == SLOT_NONE for s in inv.states):            # the five byte tests
        return False
    for state, item in zip(inv.states, inv.items):
        # cmp <state>,1 ; jne next  -- only Empty inspects the pointer, and a
        # live object there is the rejection (shr 29 / test al,1 / je false).
        if state == SLOT_EMPTY and item and item in live:
            return False
    return True


def is_synchronized(owner_valid: bool, client_current_item: int, accepted: bool,
                    sv: SvInventory, live_netguids: Iterable[int] = (),
                    role_is_authority: bool = False) -> bool:
    """Mirror of `UWW3InventoryManagerBase::IsSynchronized` (`0x140C37770`) on the
    client branch (`GetNetMode() == NM_Client`, so no early `<= NM_DedicatedServer`
    return and `GetActiveInventory()` is `&SvReplicatedInventory`)."""
    if not owner_valid:
        return False
    if not client_current_item:                            # GetCurrentItem() -> +0x290
        return False
    if not role_is_authority and not accepted:             # +0x2B9
        return False
    return replicated_inventory_is_valid(sv, live_netguids)


def default_sv_inventory(mode: str = "weapons",
                         primary_weapon: int = CAPTURE_PRIMARY_WEAPON,
                         secondary_weapon: int = CAPTURE_SECONDARY_WEAPON,
                         batch_id: int = 1) -> SvInventory:
    """`weapons` (default): the two weapons the client already preloaded, both
    slots `Assigned`, the three gadget slots `Empty` with null pointers -- the
    coherent shape, and the one the client's own `WeaponsPreloadRequest` implies.

    `empty`: every slot `Empty` with null pointers.  Still passes
    `FWW3ReplicatedInventory::IsValid`, and is the smaller bisect variant if the
    weapons shape turns out to disturb the client.
    """
    if mode == "empty":
        return SvInventory(batch_id=batch_id, states=(SLOT_EMPTY,) * 5)
    if mode != "weapons":
        raise ValueError(f"unknown mode {mode!r} (weapons|empty)")
    return SvInventory(
        batch_id=batch_id,
        primary_weapon=primary_weapon,
        secondary_weapon=secondary_weapon,
        states=(SLOT_ASSIGNED, SLOT_ASSIGNED, SLOT_EMPTY, SLOT_EMPTY, SLOT_EMPTY),
    )


def _bits_u(value: int, width: int) -> list[int]:
    return [((int(value) >> i) & 1) for i in range(width)]


def _bits_packed(value: int) -> list[int]:
    w = GuidWriter()
    w.write_packed(int(value))
    raw = w.get_bytes()
    return [((raw[i >> 3] >> (i & 7)) & 1) for i in range(w.num)]


def build_inventory_sync_payload(mode: str = "weapons",
                                 primary_weapon: int = CAPTURE_PRIMARY_WEAPON,
                                 secondary_weapon: int = CAPTURE_SECONDARY_WEAPON,
                                 batch_id: int = 1,
                                 states: tuple[int, ...] | None = None,
                                 current_item: int | None = None,
                                 force_replication_var: int | None = None) -> list[int]:
    """RepLayout property bits for the InventoryManager subobject.

    Sends `CurrentItemRepInfo` (h3..h5) and `SvReplicatedInventory` (h10/h11 and
    h15..h20).  Deliberately omits h12..h14 (the gadget pointers, already null on
    the client and left null by the `Empty` slot states) and never touches h22 or
    the `WeaponsPreloadRequest` handles, which the capture owns.

    Fails closed: refuses to emit a struct that provably cannot satisfy
    `FWW3ReplicatedInventory::IsValid`, so a live one-shot cannot be spent on a
    packet that could not have worked.
    """
    inv = default_sv_inventory(mode=mode, primary_weapon=primary_weapon,
                              secondary_weapon=secondary_weapon, batch_id=batch_id)
    if states is not None:
        if len(states) != 5:
            raise ValueError(f"states must have 5 entries, got {len(states)}")
        inv = inv._replace(states=tuple(int(s) for s in states))
    if inv.batch_id == 0:
        raise ValueError(
            "BatchID must be non-zero: FWW3ReplicatedInventory::IsValid rejects 0 "
            "at 0x140CA45EA, so the block could never flip the bit")
    if any(s == SLOT_NONE for s in inv.states):
        raise ValueError(
            f"slot states {inv.states} contain None: IsValid rejects any None state")
    # The pointer rule can only be checked against the client's live set, so
    # assume the weapons we name are live -- that is the case this builds for.
    named_live = {g for g in inv.items if g}
    if not replicated_inventory_is_valid(inv, live_netguids=named_live):
        raise ValueError(
            f"{inv} cannot satisfy FWW3ReplicatedInventory::IsValid "
            "(an Empty slot names a live item)")

    cur = inv.secondary_weapon or inv.primary_weapon
    if current_item is not None:
        cur = int(current_item)

    props: list[tuple[int, list[int]]] = []
    if cur:
        # OnRep_CurrentItemRepInfo (0x140C41660) is what gives the client a
        # non-null ClientCurrentItem (+0x290) -- IsSynchronized' second gate --
        # and it also calls the shared NotifySynchronized helper.
        props.append((H_CURRENT_ITEM, _bits_packed(cur)))
        props.append((H_CURRENT_ITEM_FROM_RESET, [0]))
        props.append((H_CURRENT_ITEM_FORCE_ID, _bits_u(0, FORCE_ITEM_ID_BITS)))
    if inv.primary_weapon:
        props.append((H_SV_PRIMARY_WEAPON, _bits_packed(inv.primary_weapon)))
    if inv.secondary_weapon:
        props.append((H_SV_SECONDARY_WEAPON, _bits_packed(inv.secondary_weapon)))
    for handle, state in zip(H_SV_SLOT_STATES, inv.states):
        props.append((handle, _bits_u(state, SLOT_STATE_BITS)))
    props.append((H_SV_BATCH_ID, _bits_u(inv.batch_id, BATCH_ID_BITS)))
    if force_replication_var is not None:
        # Diagnostic only.  h22 is the one handle of this subobject the client has
        # provably already applied from the capture (`_inv_sync_gates.py` reads
        # `ForceReplicationVar=2`, which is the value at capture src 212/213).
        # Writing a different value makes "did this block reach the subobject at
        # all?" observable, separating a framing/sequencing failure from a wrong
        # handle model for h10..h20.  It has no side effect of its own: the struct
        # still fails IsValid unless the other handles land too.
        props.append((H_SV_FORCE_REPLICATION,
                      _bits_u(int(force_replication_var), 32)))
    return write_rep_properties(props)


def build_inventory_sync_block_bits(**kwargs) -> list[int]:
    """One stably-named subobject content block for 9384, ready for ch3."""
    payload = build_inventory_sync_payload(**kwargs)
    w = GuidWriter()
    write_subobject_content_block(w, IM_NETGUID, stably_named=1, has_rep_layout=1,
                                  payload_bits_list=payload)
    raw = w.get_bytes()
    return [((raw[i >> 3] >> (i & 7)) & 1) for i in range(w.num)]


def packet_sha256(bits: list[int]) -> str:
    return hashlib.sha256(bytes(bits)).hexdigest()


# Fail-closed identity gate, exactly like ACTION_PROBE_PACKET_SHA256 /
# TEAM_SYNC_BIND_PACKET_SHA256: server.py refuses to send unless the packet it
# built hashes to this, so a payload edit cannot reach a live channel unreviewed.
INV_SYNC_PACKET_SHA256 = (
    "57609efad7805af6760152aca3e400f39d460cca0ff194e18aee87ed7abb64cc")  # 231 bits


if __name__ == "__main__":
    bits = build_inventory_sync_block_bits()
    print(f"default packet: {len(bits)} bits, sha256={packet_sha256(bits)}")
    print(f"empty  packet: {len(build_inventory_sync_block_bits(mode='empty'))} bits")
