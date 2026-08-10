#!/usr/bin/env python3
"""Rewrite NetGUID export blocks to drop NetworkChecksum (EF bit 2).

Live Gobi pawn open is bit-identical to capture, yet the client never maps
NetGUID 9372. Capture archetype guid 21 carries checksum 0x40BC1DD1 — if this
playable build's class checksum differs, the client rejects the spawn silently.
Stripping bHasNetworkChecksum makes the client path-resolve without the check.
"""
from __future__ import annotations

from netguid import GuidReader, GuidWriter, EF_HAS_PATH, EF_HAS_NET_CHECKSUM


def _rewrite_object(r: GuidReader, w: GuidWriter, strip: bool) -> None:
    gid = r.packed()
    w.write_packed(gid)
    if gid == 0:
        return
    flags = r.read(8)
    has_path = bool(flags & EF_HAS_PATH)
    has_cs = bool(flags & EF_HAS_NET_CHECKSUM)
    out_flags = (flags & ~EF_HAS_NET_CHECKSUM) if strip else flags
    w.write_bits(out_flags, 8)
    if not has_path:
        return
    _rewrite_object(r, w, strip)  # outer (or packed 0)
    path = r.fstring()
    w.write_fstring(path)
    if has_cs:
        cs = r.read(32)
        if not strip:
            w.write_bits(cs, 32)


def strip_export_checksums(bits: list[int]) -> list[int]:
    """Return payload bits with all export NetworkChecksum fields removed."""
    if len(bits) < 40:
        return list(bits)
    r = GuidReader(bits)
    w = GuidWriter()
    w.write_bit(r.bit())  # bHasRepLayoutExport
    n = r.i32()
    w.write_int32(n)
    if n < 0 or n > 512:
        return list(bits)
    for _ in range(n):
        _rewrite_object(r, w, strip=True)
    # remainder of bunch (SerializeNewActor + content) unchanged
    for i in range(r.pos, len(bits)):
        w.write_bit(bits[i])
    raw = w.get_bytes()
    return [((raw[i >> 3] >> (i & 7)) & 1) for i in range(w.num)]
