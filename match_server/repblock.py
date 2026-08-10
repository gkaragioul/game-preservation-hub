#!/usr/bin/env python3
r"""UE 4.21 RepLayout property-block codec.

The one thing every previous derivation attempt got wrong: a property block
does **not** begin with a packed handle. `FRepLayout::SendProperties` writes a
leading `bDoChecksum` bit first --

    #ifdef ENABLE_PROPERTY_CHECKSUMS
        Writer.WriteBit( bDoChecksum ? 1 : 0 );
    #endif

-- and `ENABLE_PROPERTY_CHECKSUMS` is defined unconditionally at the top of
`RepLayout.cpp`, so the bit is on the wire in Shipping too (value 0, because
`net.DoPropertyChecksum` defaults off). Reading the payload from bit 0 shifts
every handle by one bit, which is why no leaf x atomic-struct model could ever
exact-consume a block: the model was never the problem.

Block layout:

    bit  bDoChecksum (0)
    loop:
        SerializeIntPacked  handle        ; 0 terminates
        <property value, width by type>

This module exposes the layout so both the decoder (`_decode_rep_block.py`) and
any future property synth share one implementation.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from actor_channel import Bits  # noqa: E402

#: bits consumed by the leading FRepLayout::SendProperties checksum flag
REP_BLOCK_PREFIX_BITS = 1


def read_u(bits, pos, k):
    if pos + k > len(bits):
        return None
    return sum(bits[pos + i] << i for i in range(k))


def read_packed(bits, pos):
    r = Bits(bits, pos)
    try:
        return r.packed(), r.pos - pos
    except EOFError:
        return None, 0


def read_fstring(bits, pos, maxlen=512):
    """FString: int32 SaveNum then SaveNum ANSI chars (or |SaveNum| UCS2)."""
    n = read_u(bits, pos, 32)
    if n is None:
        return None
    if n == 0:
        return "", 32
    if n & 0x80000000:                       # negative -> UCS2
        cnt = (1 << 32) - n
        if cnt > maxlen:
            return None
        need = 32 + cnt * 16
        if pos + need > len(bits):
            return None
        chars = [read_u(bits, pos + 32 + i * 16, 16) for i in range(cnt)]
        wide = True
    else:
        cnt = n
        if cnt > maxlen:
            return None
        need = 32 + cnt * 8
        if pos + need > len(bits):
            return None
        chars = [read_u(bits, pos + 32 + i * 8, 8) for i in range(cnt)]
        wide = False
    if not chars or chars[-1] != 0:
        return None
    if any(c == 0 for c in chars[:-1]):
        return None
    try:
        text = "".join(chr(c) for c in chars[:-1])
    except ValueError:
        return None
    if not wide and any(c > 127 for c in chars[:-1]):
        return None
    return text, need


def read_unique_net_id(bits, pos):
    """FUniqueNetIdRepl::NetSerialize — 8-bit encoding/size byte then the id string.

    Ground-truthed against 13 captured PlayerState opens: the byte is 0x08 and
    is followed by a plain FString (Steam id for humans, an index for bots).
    """
    enc = read_u(bits, pos, 8)
    if enc is None:
        return None
    if enc == 0:
        return ("", 8)
    got = read_fstring(bits, pos + 8)
    if got is None:
        return None
    return got[0], 8 + got[1]


def read_name(bits, pos):
    """UPackageMap::SerializeName — 1 bit bHardcoded, else FString + int32 Number."""
    b = read_u(bits, pos, 1)
    if b is None:
        return None
    if b:
        # SerializeInt(NameIndex, MAX_NETWORKED_HARDCODED_NAME + 1); width is
        # build-dependent, so callers treat hardcoded names as unresolved.
        return None
    got = read_fstring(bits, pos + 1)
    if got is None:
        return None
    num = read_u(bits, pos + 1 + got[1], 32)
    if num is None:
        return None
    return got[0], 1 + got[1] + 32


def read_rotator_compressed_short(bits, pos):
    """FRotator::NetSerialize -> SerializeCompressedShort: per axis 1 bit + 16 if set."""
    total = 0
    comps = []
    for _ in range(3):
        b = read_u(bits, pos + total, 1)
        if b is None:
            return None
        total += 1
        if b:
            v = read_u(bits, pos + total, 16)
            if v is None:
                return None
            total += 16
            comps.append(v)
        else:
            comps.append(0)
    return comps, total


def read_packed_vector(bits, pos, max_bits):
    """SerializePackedVector<Scale, MaxBits>: SerializeInt(NumBits, MaxBits) then 3
    SerializeInt(1 << (NumBits + 2))."""
    r = Bits(bits, pos)
    try:
        nbits = r.rint(max_bits)
        mx = 1 << (nbits + 2)
        vals = [r.rint(mx) for _ in range(3)]
    except (IndexError, EOFError):
        return None
    if r.pos > len(bits):
        return None
    return vals, r.pos - pos


#: struct types with a native NetSerializer and their wire readers
def struct_width(typ, bits, pos):
    if typ in ("FVector", "FVector2D", "FVector4", "FQuat"):
        n = {"FVector": 3, "FVector2D": 2, "FVector4": 4, "FQuat": 4}[typ]
        return (n * 32, f"{typ} {n}xfloat") if pos + n * 32 <= len(bits) else None
    if typ == "FRotator":
        got = read_rotator_compressed_short(bits, pos)
        return (got[1], f"rot {got[0]}") if got else None
    if typ in ("FIntPoint", "FIntVector"):
        n = 2 if typ == "FIntPoint" else 3
        return (n * 32, typ) if pos + n * 32 <= len(bits) else None
    quant = {"FVector_NetQuantize": 20, "FVector_NetQuantize10": 24,
             "FVector_NetQuantize100": 30, "FVector_NetQuantizeNormal": 16}
    if typ in quant:
        got = read_packed_vector(bits, pos, quant[typ])
        return (got[1], f"{typ} {got[0]}") if got else None
    return None


def ceil_log_two(v: int) -> int:
    """FMath::CeilLogTwo — 0 for v<=1, else the bit count needed for [0, v)."""
    if v <= 1:
        return 0
    return (v - 1).bit_length()


#: fixed-width scalar types
FIXED = {
    "bool": 1,
    "uint8": 8, "int8": 8,
    "uint16": 16, "int16": 16,
    "uint32": 32, "int32": 32, "float": 32,
    "uint64": 64, "int64": 64, "double": 64,
}


def read_soft_object_path(bits, pos):
    """UE4 FSoftObjectPath::NetSerialize — path as FString (empty SaveNum=0 = 32 zero bits).

    Ground-truthed against clothing IM (9384) WeaponsPreloadRequest SoftClassPtrs:
    PrimaryGadgetClass / SecondaryGadgetClass exact-consume as FString asset paths.
    Mis-reading SoftClassPtr as packed NetGUID falsely hits handle 0 (terminator).
    """
    got = read_fstring(bits, pos)
    if got is None:
        return None
    return got[0], got[1]


def value_widths(cmd: str, typ: str | None, bits, pos, enums=None):
    """Ordered candidate (width, note) pairs for one property value at `pos`."""
    base = cmd.split(".")[-1]
    enums = enums or {}
    out: list[tuple[int, str]] = []

    if typ == "FString":
        got = read_fstring(bits, pos)
        if got:
            out.append((got[1], f"str {got[0]!r}"))
        return out
    if typ == "FUniqueNetIdRepl":
        got = read_unique_net_id(bits, pos)
        if got:
            out.append((got[1], f"uid {got[0]!r}"))
        return out
    if typ == "FName":
        got = read_name(bits, pos)
        if got:
            out.append((got[1], f"name {got[0]!r}"))
        return out
    if typ and (
        "TSoftClassPtr" in typ
        or "TSoftObjectPtr" in typ
        or typ in ("FSoftObjectPath", "FSoftClassPath")
    ):
        got = read_soft_object_path(bits, pos)
        if got:
            out.append((got[1], f"soft {got[0]!r}"))
        return out
    got = struct_width(typ, bits, pos) if typ else None
    if got:
        out.append(got)
        return out
    if typ in enums:
        # UByteProperty/UEnumProperty::NetSerializeItem ->
        # Ar.SerializeBits(Data, FMath::CeilLogTwo(Enum->GetMaxEnumValue()))
        w = ceil_log_two(enums[typ])
        out.append((w, f"enum{w} max={enums[typ]}"))
        return out
    if typ in FIXED:
        out.append((FIXED[typ], typ))
        return out
    if typ and (typ.startswith("A") or typ.startswith("U")) and typ not in FIXED:
        v, w = read_packed(bits, pos)                 # object -> packed NetGUID
        if v is not None:
            out.append((w, f"obj netguid={v}"))
        return out
    if typ and typ.startswith("TArray<"):
        return out                                    # handled by the caller
    if base.startswith("b") and len(base) > 1 and base[1].isupper():
        out.append((1, "bool"))
        return out
    return out
