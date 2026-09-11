#!/usr/bin/env python3
"""Rewrite a pawn SerializeNewActor payload (scale strip / in-open synth props).

Capture pawn NewActor has a 109-bit scale body. PC/PS opens do not. Live client
accepts ch2/ch7 but never maps ch3 (pawn) — try dropping scale while keeping
exports + content blocks intact.

WW3_PAWN_SYNTH_IN_OPEN: the capture's ch3 open has no isActor RepLayout (only
subobject stubs). PC/PS opens put the actor property block *before* subobjects
(SerializeNewActor → ACTOR_REP → SUBs). Injecting APawn::PlayerState /
::Controller into that slot lets PostNetInit see the bind before latching.
"""
from __future__ import annotations

from actor_channel import (
    Bits,
    read_content_blocks,
    read_new_actor,
    write_packed_vector,
    write_rotator_net,
)
from netguid import PackageMap, GuidWriter


def strip_newactor_scale(bits: list[int]) -> list[int]:
    """bits = SerializeNewActor (+ following content). Returns same with scale cleared."""
    pm = PackageMap()
    r = Bits(bits)
    info = read_new_actor(r, pm)
    if info.get("incomplete"):
        return list(bits)
    if not info.get("has_scale"):
        return list(bits)
    content = bits[r.pos :]
    w = GuidWriter()
    w.write_packed(info["netguid"])
    w.write_packed(info["archetype"])
    w.write_packed(info["level"])
    if info.get("location") is not None:
        w.write_bit(1)
        write_packed_vector(w, info["location"])
    else:
        w.write_bit(0)
    if info.get("has_rotation"):
        w.write_bit(1)
        write_rotator_net(w, info["rotation"])
    else:
        w.write_bit(0)
    w.write_bit(0)  # scale off
    w.write_bit(0)  # velocity off
    for b in content:
        w.write_bit(b)
    raw = w.get_bytes()
    return [((raw[i >> 3] >> (i & 7)) & 1) for i in range(w.num)]


def inject_pawn_open_synth_props(bits: list[int],
                                 prop_block_bits: list[int] | None = None) -> list[int]:
    """Insert an isActor RepLayout content block after SerializeNewActor, before subs.

    `bits` is the pawn open *body* (src 11 partial-final): NewActor + subobject
    content blocks. No export prefix. `prop_block_bits` is a full framed content
    block (hasRepLayout + isActor + packed NumPayloadBits + payload) as produced
    by `possess_rpc.build_pawn_bind_props_bits`. If omitted, that helper is used.

    Idempotent: if the first content block is already an isActor RepLayout, bits
    are returned unchanged.
    """
    if prop_block_bits is None:
        from possess_rpc import build_pawn_bind_props_bits
        prop_block_bits = build_pawn_bind_props_bits()
    pm = PackageMap()
    r = Bits(bits)
    info = read_new_actor(r, pm)
    if info.get("incomplete"):
        return list(bits)
    content_start = r.pos
    existing = read_content_blocks(Bits(bits, content_start))
    if existing and existing[0].get("isActor") and existing[0].get("hasRepLayout"):
        return list(bits)
    return list(bits[:content_start]) + list(prop_block_bits) + list(bits[content_start:])
