#!/usr/bin/env python3
"""Craft / detect PlayerController possession RPCs (ClientRestart / AckPossession).

Wire format (UE 4.21 `WriteFieldHeaderAndPayload`)
--------------------------------------------------
An RPC inside an actor content block is::

    SerializeInt(FieldNetIndex, ClassCache->GetMaxIndex() + 1)     # VALUE-DEPENDENT width
    SerializeIntPacked(NumPayloadBits)
    <NumPayloadBits bits of parameters>

repeated until the block payload is exhausted (no terminator).

The parameter payload is not the raw arguments either. `FRepLayout::SendPropertiesForRPC`
prefixes every non-`CPF_OutParm` parameter with a **"Send" bit** (1 = the value differs
from the parameter's default and follows; 0 = default, nothing follows), so a one-object
RPC is `1` + `SerializeIntPacked(NetGUID)` and a null one is the single bit `0`.

Both facts are ground-truthed against the real dedicated server in
`captures/24July26/W3_match_full_2.pcapng`: `ServerAcknowledgePossession` (handle 64,
n=11) carries a 17-bit payload `1 1001110001001001` -- Send bit, then packed 9372, the
pawn NetGUID. See `_rpc_payload_shapes.py`.

Handle width: `FBitWriter::SerializeInt(Value, ValueMax)` writes bits only while
`(WrittenSoFar + Mask) < ValueMax`, so the width depends on the *value*, not just the
class. With `HANDLE_VALUE_MAX = 315` a handle >= 59 takes 8 bits and a smaller one takes
9. Every handle the client ever sends is >= 64, which is why `_probe_field_header.py`'s
fixed-8-bit model scored 100% on C->S traffic and still wrote the S->C `ClientRestart`
handle 39 one bit short. That single missing bit is the whole of the client-side

    FBitReader::SetOverflowed() (ReadLen: 72, Remaining: 15, Max: 32)
    ReadFieldHeaderAndPayload: Error reading payload. OutField: ClientRestart

in `live_log/HANDLE_CALIBRATE_LIVE.md`: the client's 9-bit read of our 8-bit handle still
decoded to 39 (the 9th bit was the first 0 of the length byte, and 39 has no bit 8), but
it left the reader one bit into our packed length, so `NumPayloadBits` came out 72 rather
than 16 with 15 bits left of a 32-bit block. All three numbers reproduce exactly.

`HANDLE_VALUE_MAX = 315` is `AWW3GamePlayerController`'s `MaxIndex + 1` from the Dumper-7
dump. The wire brackets it independently to [311, 320]: handle 310 is observed C->S (so
ValueMax > 310) and handle 64 is read in 8 bits (so ValueMax <= 320).

Handles (match_server/class_net_cache_ww3.json, derived by `derive_net_handles.py`
from the Dumper-7 dump of this exact build; all 8 wire anchors reproduce exactly)::

    ClientRestart                        39      ServerAcknowledgePossession          64
    ClientRetryClientRestart             40      ServerCheckClientPossession          67
                                                 ServerCheckClientPossessionReliable  68
                                                 ServerNotifyLoadedWorld              70

The old table's `ClientRestart = 9` / `Ack = 34` came from decoding a fixed-8-bit
handle byte as a packed int, which halves it: byte 68 (`ServerCheckClientPossession-
Reliable`, a zero-arg RPC) decoded as "handle 34 with argument 0", i.e. the
`ServerAcknowledgePossession(null)` that every session reported was never sent at all.

RepLayout property handles are a *separate* space and genuinely are
`SerializeIntPacked` (`FRepLayout::WritePropertyHandle`) -- but they were bitten by the
same halving artefact for a different reason: the block's leading `bDoChecksum` bit was
not being skipped, so the first packed handle read as twice its real value. See
`PC_REP_HANDLE_PAWN` below and `repblock.py`.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from netguid import GuidWriter
from actor_channel import (write_content_block, write_rep_properties, Bits,
                           read_content_blocks)

# `ClassCache->GetMaxIndex() + 1` for the client's PlayerController class, i.e. the
# ValueMax of the field handle's SerializeInt. WW3_RPC_HANDLE_VALUE_MAX overrides.
HANDLE_VALUE_MAX = int(os.environ.get("WW3_RPC_HANDLE_VALUE_MAX", "315"))

# Legacy fixed-width handle model. Only used when WW3_RPC_HANDLE_BITS is set explicitly,
# as an A/B control against the correct wrapped encoding.
HANDLE_BITS = 8

# Server* handles verified on the wire (see module docstring).
RPC_SERVER_ACK_POSSESSION = 64
RPC_SERVER_CHECK_POSSESSION = 67
RPC_SERVER_CHECK_POSSESSION_RELIABLE = 68
RPC_SERVER_NOTIFY_LOADED_WORLD = 70

# Fallback if class_net_cache_ww3.json is missing / invalid.
_DEFAULT_RESTART_HANDLES = (39,)
_DEFAULT_RETRY_HANDLES = (40,)

# Capture local pawn NetGUID (SerializeNewActor on ch3).
PAWN_NETGUID = 9372

# PlayerState NetGUID the client actively uses (ch7 traffic, 1000+ C->S bunches per
# session) -- a resolvable, non-pawn object reference for the wire-handle calibration
# control test. See restart_calibration_pawn_guid().
PS_NETGUID = 9362

_CACHE: dict | None = None


def _cache_path() -> Path:
    env = os.environ.get("WW3_CLASS_NET_CACHE")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent / "class_net_cache_ww3.json"


def load_class_net_cache(force: bool = False) -> dict | None:
    """Load match_server/class_net_cache_ww3.json; None if missing or anchor fails."""
    global _CACHE
    if _CACHE is not None and not force:
        return _CACHE
    path = _cache_path()
    if not path.is_file():
        _CACHE = None
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _CACHE = None
        return None
    handles = (doc.get("rpc_handles") or {}).get("PlayerController") or {}
    ac = doc.get("anchor_check") or {}
    field = ac.get("field", "ServerAcknowledgePossession")
    expect = int(ac.get("index", RPC_SERVER_ACK_POSSESSION))
    if handles.get(field) != expect:
        _CACHE = None
        return None
    _CACHE = doc
    return _CACHE


def pc_rpc_handle(name: str, default: int | None = None) -> int | None:
    doc = load_class_net_cache()
    if not doc:
        return default
    handles = (doc.get("rpc_handles") or {}).get("PlayerController") or {}
    if name in handles:
        return int(handles[name])
    return default


def handle_value_max() -> int:
    """`ClassCache->GetMaxIndex() + 1` -- the ValueMax of the field handle's SerializeInt."""
    env = os.environ.get("WW3_RPC_HANDLE_VALUE_MAX")
    if env:
        return int(env)
    doc = load_class_net_cache()
    if doc and doc.get("handle_value_max"):
        return int(doc["handle_value_max"])
    return HANDLE_VALUE_MAX


def forced_handle_bits() -> int | None:
    """Fixed handle width, only when WW3_RPC_HANDLE_BITS pins one (A/B control)."""
    env = os.environ.get("WW3_RPC_HANDLE_BITS")
    return int(env) if env else None


def handle_bits(handle: int = 39) -> int:
    """Bits `SerializeInt` spends on `handle`. Value-dependent -- not a constant."""
    forced = forced_handle_bits()
    if forced is not None:
        return forced
    return wrapped_width(handle, handle_value_max())


def wrapped_width(value: int, value_max: int) -> int:
    """Bit count of `FBitWriter::SerializeInt(value, value_max)`."""
    written = 0
    mask = 1
    n = 0
    while (written + mask) < value_max and mask < (1 << 32):
        if value & mask:
            written |= mask
        n += 1
        mask <<= 1
    return n


def write_int_wrapped(w: GuidWriter, value: int, value_max: int) -> None:
    """`FBitWriter::SerializeInt(Value, ValueMax)` -- LSB first, value-dependent width.

    UE stops as soon as the value it has *already written* plus the next mask can no
    longer be below ValueMax, so the width depends on the value. A fixed-width writer
    agrees only for values >= ValueMax - 2^(k-1); that is exactly why the small
    `ClientRestart` handle was mis-framed while every large `Server*` handle was fine.
    """
    written = 0
    mask = 1
    while (written + mask) < value_max and mask < (1 << 32):
        bit = 1 if (value & mask) else 0
        if bit:
            written |= mask
        w.write_bit(bit)
        mask <<= 1


def read_int_wrapped(r: Bits, value_max: int) -> int:
    """`FBitReader::SerializeInt(Value, ValueMax)` -- mirror of write_int_wrapped."""
    value = 0
    mask = 1
    while (value + mask) < value_max and mask < (1 << 32):
        if r.left() < 1:
            raise EOFError("wrapped int past end")
        if r.bit():
            value |= mask
        mask <<= 1
    return value


def rpc_send_bit() -> bool:
    """FRepLayout::SendPropertiesForRPC's per-parameter "Send" bit (WW3_RPC_SEND_BIT=0 off)."""
    return os.environ.get("WW3_RPC_SEND_BIT", "1") != "0"


def restart_calibration_pawn_guid() -> int | None:
    """Argument NetGUID override for a ClientRestart HANDLE CALIBRATION run.

    Largely superseded by the 2026-08-06 derivation (fact #12): the reason those runs got
    ZERO reaction was that the RPC was both mis-numbered (9, not 39) and mis-framed (no
    payload-length field), so it could never dispatch. The control test below is still
    the cheapest way to separate "the RPC now runs" from "the pawn GUID never resolves"
    on the first rematch after the fix.

    This substitutes a NetGUID the client's PackageMap DEFINITELY already holds (the
    PlayerState, 9362 -- ch7 is live C->S traffic every session) as the RPC argument.
    UPackageMapClient::SerializeObject type-checks the resolved object against the
    parameter's declared class (APawn) and nulls it on mismatch instead of allowing an
    unsafe cast, so this is safe even though 9362 is not actually a Pawn: worst case is
    APlayerController::ClientRestart_Implementation(nullptr), which still takes a real,
    observable branch (ServerCheckClientPossessionReliable / no possession) instead of
    silence. Any reaction at all -- AckPossession(null), CheckClientPossession, or even
    AckPossession(9362) if the cast is somehow allowed -- proves handle 39 dispatches and
    the real bug is GUID 9372 specifically. Continued silence would mean the handle is
    still wrong and no amount of pawn-side work will help.

    WW3_CLIENT_RESTART_PAWN_GUID=<n> sets any explicit override; WW3_RESTART_CALIBRATE=ps
    is a shorthand for the PlayerState GUID specifically. Both OFF by default (None ->
    caller falls back to the real PAWN_NETGUID).
    """
    override = os.environ.get("WW3_CLIENT_RESTART_PAWN_GUID")
    if override:
        return int(override)
    if os.environ.get("WW3_RESTART_CALIBRATE", "").strip().lower() == "ps":
        return PS_NETGUID
    return None


def restart_pawn_guid() -> int:
    """Effective Pawn-argument NetGUID for the ClientRestart RPC (calibration-aware)."""
    calib = restart_calibration_pawn_guid()
    return PAWN_NETGUID if calib is None else calib


def restart_handles() -> list[int]:
    single = os.environ.get("WW3_CLIENT_RESTART_HANDLE")
    if single:
        return [int(single)]
    multi = os.environ.get("WW3_CLIENT_RESTART_HANDLES")
    if multi:
        return [int(x) for x in multi.split(",") if x.strip()]
    h = pc_rpc_handle("ClientRestart", _DEFAULT_RESTART_HANDLES[0])
    return [int(h)]


def retry_handles() -> list[int]:
    multi = os.environ.get("WW3_CLIENT_RETRY_HANDLES")
    if multi:
        return [int(x) for x in multi.split(",") if x.strip()]
    # First spray: restart only. Retry on CheckPossession (see server).
    if os.environ.get("WW3_CLIENT_RESTART_SEND_RETRY", "0") != "1":
        return []
    h = pc_rpc_handle("ClientRetryClientRestart", _DEFAULT_RETRY_HANDLES[0])
    return [int(h)]


# Back-compat aliases used by older tests / imports.
RPC_CLIENT_RESTART = int(
    os.environ.get(
        "WW3_CLIENT_RESTART_HANDLE",
        str(pc_rpc_handle("ClientRestart", _DEFAULT_RESTART_HANDLES[0])
            or _DEFAULT_RESTART_HANDLES[0]),
    )
)
RPC_CLIENT_RETRY_RESTART = int(
    os.environ.get(
        "WW3_CLIENT_RETRY_HANDLE",
        str(pc_rpc_handle("ClientRetryClientRestart", _DEFAULT_RETRY_HANDLES[0])
            or _DEFAULT_RETRY_HANDLES[0]),
    )
)

def _bits_from_writer(w: GuidWriter) -> list[int]:
    raw = w.get_bytes()
    return [((raw[i >> 3] >> (i & 7)) & 1) for i in range(w.num)]


def build_field_bits(handle: int, param_bits: list[int]) -> list[int]:
    """One `WriteFieldHeaderAndPayload` field: wrapped handle, packed length, params."""
    w = GuidWriter()
    forced = forced_handle_bits()
    if forced is None:
        write_int_wrapped(w, handle, handle_value_max())
    else:
        h = handle
        for _ in range(forced):
            w.write_bit(h & 1)
            h >>= 1
    w.write_packed(len(param_bits))
    for b in param_bits:
        w.write_bit(b)
    return _bits_from_writer(w)


def build_object_param_bits(netguid: int) -> list[int]:
    """One `UObject*` RPC parameter as `FRepLayout::SendPropertiesForRPC` writes it.

    Send bit, then `UPackageMapClient::SerializeObject`'s packed NetGUID. A null object
    is identical to the parameter default, so it is the single bit 0 with no GUID -- the
    real server's `ServerAcknowledgePossession` payloads in the 24 July capture are
    17 bits (`1` + packed 9372), never 16.
    """
    w = GuidWriter()
    if not rpc_send_bit():
        w.write_packed(netguid)
        return _bits_from_writer(w)
    if netguid == 0:
        w.write_bit(0)
        return _bits_from_writer(w)
    w.write_bit(1)
    w.write_packed(netguid)
    return _bits_from_writer(w)


def build_before_spectator_param_bits(netguid: int, delay: float = 0.0,
                                      layout: str = "sendbits",
                                      force_float: bool = False) -> list[int]:
    """Build candidate payloads for ``Client_OnBeforeSpectatorReturnToGame``.

    This RPC is not present in the captured listen-server stream, so its
    ``FRepLayout`` framing cannot be asserted from a ground-truth packet.  The
    generated SDK signature is ``(AWW3PlayerState*, float)``.  Keep the
    candidate layouts in one helper so live A/B runs can change only the
    parameter framing (``WW3_BEFORE_SPECTATOR_LAYOUT``), without changing the
    transition order or field header.

    ``sendbits`` is the historical implementation: UObject send bit + packed
    NetGUID, followed by a float default/send bit.  Other values intentionally
    model the common UE RPC alternatives and are diagnostic-only.
    """
    w = GuidWriter()
    mode = (layout or "sendbits").strip().lower()
    if mode == "raw":
        w.write_packed(netguid)
        w.write_float(delay)
    elif mode == "obj_send_float_raw":
        w.write_bit(0 if netguid == 0 else 1)
        if netguid:
            w.write_packed(netguid)
        w.write_float(delay)
    elif mode == "obj_raw_float_send":
        w.write_packed(netguid)
        w.write_bit(1)
        w.write_float(delay)
    elif mode == "null":
        w.write_bit(0)
        w.write_bit(0 if delay == 0.0 else 1)
        if delay != 0.0:
            w.write_float(delay)
    elif mode == "all_send":
        w.write_bit(0 if netguid == 0 else 1)
        if netguid:
            w.write_packed(netguid)
        w.write_bit(1)
        w.write_float(delay)
    elif mode == "sendbits":
        w.write_bit(0 if netguid == 0 else 1)
        if netguid:
            w.write_packed(netguid)
        if delay == 0.0 and not force_float:
            w.write_bit(0)
        else:
            w.write_bit(1)
            w.write_float(delay)
    else:
        raise ValueError(f"unknown before-spectator payload layout: {layout!r}")
    return _bits_from_writer(w)


def build_stop_spectator_before_deploy_param_bits(
        location: tuple[float, float, float], leave_source: int = 3) -> list[int]:
    """Serialize handle 254's ``(FVector, EWW3SpectatorLeaveSource)`` params.

    Dumper-7's generated UE 4.21 SDK identifies the first property as a plain
    ``FVector`` (three IEEE-754 floats), not ``FVector_NetQuantize``.  The enum's
    ``MAX`` sentinel is 6, so valid values are 0..5.  Live-client overflow
    diagnostics show that RPC enum parameters consume a fixed three-bit value
    after the RepLayout property-presence bit (rather than adaptive SerializeInt).
    """
    if len(location) != 3:
        raise ValueError("stop-spectator location must have three coordinates")
    if not 0 <= int(leave_source) < 6:
        raise ValueError("EWW3SpectatorLeaveSource must be in 0..5")
    w = GuidWriter()
    w.write_bit(1)
    for coordinate in location:
        w.write_float(float(coordinate))
    if int(leave_source) == 0:
        w.write_bit(0)
    else:
        w.write_bit(1)
        w.write_bits(int(leave_source), 3)
    return _bits_from_writer(w)


def build_character_respawn_success_param_bits(
        player_respawn_params: list[int], status: int = 1) -> list[int]:
    """Build handle 235 from captured handle-240 spawn coordinates.

    ``Client_OnCharacterRespawnRequestSucceeded`` prepends an
    ``EWW3CharacterRespawnStatus`` to the same FVector_NetQuantize + yaw pair
    carried by ``Client_OnPlayerRespawned``.  The latter's final two bits are
    its separate keep-inventory bool and therefore are intentionally omitted.
    """
    if len(player_respawn_params) != 60:
        raise ValueError("captured Client_OnPlayerRespawned payload must be 60 bits")
    if not 0 <= int(status) < 24:
        raise ValueError("EWW3CharacterRespawnStatus must be in 0..23")
    # Diagnostic framing only: no authoritative capture exists for handle 235.
    # The 8-bit storage layout is retained as the original opt-in probe; the
    # server keeps this RPC disabled by default because both 67- and 64-bit
    # variants have produced a client ReceivePropertiesForRPC mismatch.
    out = [1]
    out.extend((int(status) >> i) & 1 for i in range(8))
    out.extend(int(bit) & 1 for bit in player_respawn_params[:58])
    return out


def build_gamestate_inprogress_bits(elapsed_time: int = 1) -> list[int]:
    """Frame AGameState's MatchState=InProgress and ElapsedTime properties.

    RepLayout handles 20 and 21 come from this build's AWW3DominationGameState
    inheritance chain.  Use the non-hardcoded FName representation so the wire
    value is independent of the engine's internal EName table indices.
    """
    state = GuidWriter()
    state.write_bit(0)  # UPackageMap::SerializeName: not a hardcoded EName
    state.write_fstring("InProgress")
    state.write_bits(0, 32)  # FName number
    elapsed = GuidWriter()
    elapsed.write_bits(int(elapsed_time) & 0xFFFFFFFF, 32)
    rep = write_rep_properties([
        (20, _bits_from_writer(state)),
        (21, _bits_from_writer(elapsed)),
    ])
    framed = GuidWriter()
    write_content_block(framed, rep, has_rep_layout=1)
    return _bits_from_writer(framed)


def build_object_rpc_bits(handle: int, netguid: int, has_rep_layout: int = 0) -> list[int]:
    """Actor content block carrying one RPC whose single parameter is a UObject*."""
    framed = GuidWriter()
    write_content_block(framed, build_field_bits(handle, build_object_param_bits(netguid)),
                        has_rep_layout=has_rep_layout)
    return _bits_from_writer(framed)


def build_zero_arg_rpc_bits(handle: int) -> list[int]:
    """Build one actor RPC with no parameters (for ClientGameStarted, etc.)."""
    framed = GuidWriter()
    write_content_block(framed, build_field_bits(handle, []), has_rep_layout=0)
    return _bits_from_writer(framed)


def build_raw_rpc_bits(handle: int, param_bits: list[int]) -> list[int]:
    """Build one actor RPC while preserving an already decoded parameter payload.

    This is useful for captured RPCs whose parameter types are not simple UObject
    references (for example Client_OnPlayerRespawned).  ``param_bits`` must be the
    bits between the field header's packed length and the next field header.
    """
    framed = GuidWriter()
    write_content_block(framed, build_field_bits(handle, list(param_bits)),
                        has_rep_layout=0)
    return _bits_from_writer(framed)


def build_must_be_mapped_prefix(netguids: list[int]) -> list[int]:
    """Bunch-payload prefix when bHasMustBeMappedGUIDs=1: uint16 count + packed GUIDs."""
    w = GuidWriter()
    n = len(netguids)
    w.write_bits(n & 0xFF, 8)
    w.write_bits((n >> 8) & 0xFF, 8)
    for g in netguids:
        w.write_packed(g)
    return _bits_from_writer(w)


def build_client_restart_bits(
    pawn_netguid: int = PAWN_NETGUID,
    handle: int | None = None,
    must_be_mapped: bool = True,
) -> list[int]:
    h = RPC_CLIENT_RESTART if handle is None else handle
    body = build_object_rpc_bits(h, pawn_netguid)
    if not must_be_mapped:
        return body
    return build_must_be_mapped_prefix([pawn_netguid]) + body


def build_client_retry_restart_bits(
    pawn_netguid: int = PAWN_NETGUID,
    handle: int | None = None,
    must_be_mapped: bool = True,
) -> list[int]:
    h = RPC_CLIENT_RETRY_RESTART if handle is None else handle
    body = build_object_rpc_bits(h, pawn_netguid)
    if not must_be_mapped:
        return body
    return build_must_be_mapped_prefix([pawn_netguid]) + body


# RepLayout property handles, derived from the Dumper-7 SDK and confirmed on the wire by
# decoding the capture's own property blocks (`_decode_all_blocks.py`, 1056 blocks).
#
# `Pawn` was recorded as 34 until 2026-08-07. That reading was an artefact of decoding the
# block from bit 0 instead of bit 1: every RepLayout block starts with a bDoChecksum bit,
# and skipping it halves the first packed handle exactly the way the RPC field index was
# being halved (fact #12 in docs/M4_Possession_Findings.md). The capture's ch2 updates
# (src 12/13, 214, 355) decode cleanly as handle 17 = Pawn -> NetGUID 9372, 137/137 bits.
PC_REP_HANDLE_PAWN = 17          # APlayerController::Pawn  (AController @16 -> Pawn @17)
PC_REP_HANDLE_PLAYERSTATE = 16   # APlayerController::PlayerState
PAWN_REP_HANDLE_PLAYERSTATE = 17  # APawn::PlayerState  (APawn @16 -> RemoteViewPitch)
PAWN_REP_HANDLE_CONTROLLER = 18  # APawn::Controller
# AWW3PlayerStateBase::PlayerCharacter — reverse bind PS → pawn (Net + OnRep).
# Confirmed by derive_rep_handles + capture ch7 open decode (PS 9362 → 9372).
PS_REP_HANDLE_PLAYERCHARACTER = 22
PC_NETGUID = 9360


def pc_pawn_handle() -> int:
    return int(os.environ.get("WW3_PC_PAWN_HANDLE", str(PC_REP_HANDLE_PAWN)))


def ps_playerchar_handle() -> int:
    return int(os.environ.get("WW3_PS_PLAYERCHAR_HANDLE",
                              str(PS_REP_HANDLE_PLAYERCHARACTER)))


def _object_prop_bits(netguid: int) -> list[int]:
    """An object property's value: UPackageMap::SerializeObject -> packed NetGUID.

    No leading bit. (RPC *parameters* get a 1-bit Send flag from
    `FRepLayout::SendPropertiesForRPC`; replicated properties do not.)
    """
    val = GuidWriter()
    val.write_packed(netguid)
    return _bits_from_writer(val)


def build_pc_set_pawn_bits(pawn_netguid: int = PAWN_NETGUID,
                           handle: int | None = None) -> list[int]:
    """Framed PC actor RepLayout block setting APlayerController::Pawn = pawn_netguid.

    Experiment #3B: the ownership bootstrap already replays src=13 (which carries this
    same property), but that lands *before* the pawn channel finishes opening. Re-sending
    just the Pawn handle immediately before ClientRestart puts the binding in the right
    order without touching the capture-faithful bunches.
    """
    rep = write_rep_properties(
        [(pc_pawn_handle() if handle is None else handle,
          _object_prop_bits(pawn_netguid))])
    framed = GuidWriter()
    write_content_block(framed, rep, has_rep_layout=1)
    return _bits_from_writer(framed)


def build_pc_set_playerstate_bits(playerstate_netguid: int = PS_NETGUID,
                                  handle: int = PC_REP_HANDLE_PLAYERSTATE) -> list[int]:
    """Frame an APlayerController::PlayerState RepLayout assignment.

    The ownership replay contains the controller's ``Pawn`` assignment, but the
    client-side synchronization latch also requires the controller's PlayerState
    pointer to resolve to the local PS actor.  Keep this separate from
    :func:`build_pc_set_pawn_bits` so callers can send both bindings in one
    ordered block immediately before restart.
    """
    rep = write_rep_properties([
        (handle, _object_prop_bits(playerstate_netguid)),
    ])
    framed = GuidWriter()
    write_content_block(framed, rep, has_rep_layout=1)
    return _bits_from_writer(framed)


def build_pawn_bind_props_bits(ps_netguid: int = PS_NETGUID,
                               controller_netguid: int = PC_NETGUID) -> list[int]:
    """Framed pawn actor RepLayout block: APawn::PlayerState + APawn::Controller.

    The capture's own ch3 actor block only ever carries RemoteRole, and the ch3 open has
    no actor block at all, so the client's pawn-side `PlayerState` is never set by
    anything we replay. This is the minimal synthesised block that sets it, using the
    encoding validated against 1056 captured blocks (bDoChecksum bit, ascending packed
    handles, packed NetGUID values, packed-0 terminator).

    Prefer injecting via `WW3_PAWN_SYNTH_IN_OPEN=1` (SerializeNewActor → this block →
    subobjects, matching PC/PS open order). `WW3_PAWN_SYNTH_PROPS=1` keeps the post-open
    follow-up as an A/B control.
    """
    rep = write_rep_properties([
        (PAWN_REP_HANDLE_PLAYERSTATE, _object_prop_bits(ps_netguid)),
        (PAWN_REP_HANDLE_CONTROLLER, _object_prop_bits(controller_netguid)),
    ])
    framed = GuidWriter()
    write_content_block(framed, rep, has_rep_layout=1)
    return _bits_from_writer(framed)


def build_ps_set_playerchar_bits(pawn_netguid: int = PAWN_NETGUID,
                                 handle: int | None = None) -> list[int]:
    """Framed PS actor RepLayout: AWW3PlayerStateBase::PlayerCharacter = pawn_netguid.

    Capture ch7 open (src 20–21) already carries PlayerCharacter→9372, but that lands
    *before* the pawn channel opens — NetGUID 9372 is not mapped yet. Live A/B showed
    pawn→PS synth (handles 17/18) ACK-safe yet checklist `PlayerState` stays false, so
    the sync latch is likely the reverse bind (or its OnRep) once the pawn exists.

    Send on ch7 after pawn open / before ClientRestart. Off by default (`WW3_PS_SET_PLAYERCHAR`).
    """
    h = ps_playerchar_handle() if handle is None else handle
    rep = write_rep_properties([(h, _object_prop_bits(pawn_netguid))])
    framed = GuidWriter()
    write_content_block(framed, rep, has_rep_layout=1)
    return _bits_from_writer(framed)


def parse_actor_rpc_fields(bits: list[int], value_max: int | None = None
                           ) -> list[tuple[int, list[int]]]:
    """Return [(handle, param_bits), ...] for every field in every actor RPC block.

    A single content block can carry several fields back to back; the chain ends when the
    block payload is exhausted, so a block that does not consume exactly is a decode
    failure and is dropped rather than reported as a bogus handle. ``value_max`` selects
    the owning class's ClassNetCache bound (PlayerController defaults to 315; the captured
    AWW3DominationPlayerState uses 82).
    """
    forced = forced_handle_bits()
    vmax = handle_value_max() if value_max is None else int(value_max)
    out: list[tuple[int, list[int]]] = []
    try:
        blocks = read_content_blocks(Bits(bits))
    except Exception:
        return out
    for bl in blocks:
        if bl.get("hasRepLayout") or not bl.get("isActor"):
            continue
        pb = bl.get("payload") or []
        if not pb:
            continue
        r = Bits(pb)
        fields: list[tuple[int, list[int]]] = []
        try:
            while r.left() > 0:
                if forced is None:
                    h = read_int_wrapped(r, vmax)
                else:
                    if r.left() < forced:
                        raise EOFError
                    h = r.read(forced)
                n = r.packed()
                if n > r.left():
                    raise EOFError
                fields.append((h, [r.bit() for _ in range(n)]))
        except EOFError:
            continue
        out.extend(fields)
    return out


def parse_object_param(param_bits: list[int]) -> int | None:
    """Decode a single-`UObject*` RPC payload -> NetGUID (0 = null), None if malformed.

    Mirrors `build_object_param_bits`: Send bit, then the packed NetGUID. Send=0 means
    the parameter was left at its default, i.e. a null object.
    """
    if not rpc_send_bit():
        r = Bits(param_bits)
        try:
            return r.packed()
        except EOFError:
            return None
    if not param_bits:
        return None
    r = Bits(param_bits)
    if not r.bit():
        return 0 if r.left() == 0 else None
    try:
        guid = r.packed()
    except EOFError:
        return None
    return guid if r.left() == 0 else None


def parse_actor_rpc_handles(bits: list[int]) -> list[tuple[int, list[int]]]:
    """Back-compat view: [(handle, [packed values decoded from the parameter bits])].

    The leading `SendPropertiesForRPC` bit is consumed first so `vals[0]` is the first
    real argument (a NetGUID for object parameters).
    """
    out: list[tuple[int, list[int]]] = []
    send_bit = rpc_send_bit()
    for h, param in parse_actor_rpc_fields(bits):
        r = Bits(param)
        vals: list[int] = []
        if send_bit and param:
            if not r.bit():
                out.append((h, [0]))
                continue
        try:
            while r.left() >= 8 and len(vals) < 4:
                vals.append(r.packed())
        except EOFError:
            pass
        out.append((h, vals))
    return out


def is_ack_possession_null(bits: list[int]) -> bool:
    """True if bunch contains ServerAcknowledgePossession(None).

    With the Send bit, a null object is a 1-bit payload of 0 -- an *empty* payload still
    means some other, zero-argument RPC, not Ack(null).
    """
    for h, param in parse_actor_rpc_fields(bits):
        if h == RPC_SERVER_ACK_POSSESSION and param and parse_object_param(param) == 0:
            return True
    return False


def is_ack_possession_pawn(bits: list[int], pawn: int = PAWN_NETGUID) -> bool:
    for h, param in parse_actor_rpc_fields(bits):
        if h == RPC_SERVER_ACK_POSSESSION and parse_object_param(param) == pawn:
            return True
    return False


def is_check_possession(bits: list[int]) -> bool:
    for h, _vals in parse_actor_rpc_handles(bits):
        if h in (RPC_SERVER_CHECK_POSSESSION, RPC_SERVER_CHECK_POSSESSION_RELIABLE):
            return True
    return False


# ---------------------------------------------------------------------------
# Deploy-eligibility writes.
#
# Turn 12 measured the real reason the DEPLOY button reads NOT READY: the live
# client thinks the local player is already alive.  `AWW3Character::CurrentHealth`
# reads 100 and `AWW3PlayerState::PlayingState` reads 2, with `bIsSpectator` 0.
# WW3 does not let a living player deploy, so no spawn tile is selectable and the
# client never sends h287 Server_RequestRespawnAtCapturePoint.
#
# The cause is structural rather than a protocol bug: `real_replay_stream.json`
# was captured from the middle of a live match, when the real player had long
# since deployed, so our client inherits "alive" the moment we replay the pawn.
#
# Handles and widths come from the build's own RepLayout dump
# (Dumper-7 `RepLayout/replication_seed.json`), which is the size oracle the
# project requires before synthesising any property write:
#
#     WW3Character.CurrentHealth   h60  type=byte                        -> 8 bits
#     WW3PlayerState.PlayingState  h52  type=enum EWW3PlayingState max=5 -> 3 bits
#
# UE serialises a byte property as 8 bits and an enum property with
# SerializeInt(Max), i.e. ceil(log2(Max)) bits for Max=5 -> 3.
CHAR_REP_HANDLE_CURRENT_HEALTH = 60
PS_REP_HANDLE_PLAYING_STATE = 52
PS_PLAYING_STATE_MAX = 5


def _byte_prop_bits(value: int) -> list[int]:
    """A byte property's value: 8 bits, LSB first.  No leading Send flag."""
    w = GuidWriter()
    w.write_bits(int(value) & 0xFF, 8)
    return _bits_from_writer(w)


def _enum_prop_bits(value: int, max_value: int) -> list[int]:
    """An enum property: FBitWriter::SerializeInt(Value, Max).

    `GuidWriter.write_int_max` is already the mirror of the reader we validated
    against captured blocks, so use it rather than re-deriving a width.
    """
    w = GuidWriter()
    w.write_int_max(int(value), int(max_value))
    return _bits_from_writer(w)


def build_char_health_bits(health: int = 0,
                           handle: int = CHAR_REP_HANDLE_CURRENT_HEALTH) -> list[int]:
    """Framed pawn actor RepLayout block: AWW3Character::CurrentHealth = health."""
    rep = write_rep_properties([(handle, _byte_prop_bits(health))])
    framed = GuidWriter()
    write_content_block(framed, rep, has_rep_layout=1)
    return _bits_from_writer(framed)


def build_ps_playing_state_bits(state: int,
                                handle: int = PS_REP_HANDLE_PLAYING_STATE) -> list[int]:
    """Framed PlayerState actor RepLayout block: PlayingState = state."""
    rep = write_rep_properties([(handle, _enum_prop_bits(state, PS_PLAYING_STATE_MAX))])
    framed = GuidWriter()
    write_content_block(framed, rep, has_rep_layout=1)
    return _bits_from_writer(framed)
