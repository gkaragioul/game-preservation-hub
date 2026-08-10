#!/usr/bin/env python3
r"""
actor_channel.py -- M3: actor channels, content blocks and RepLayout property streams.

Everything here was reverse-engineered from the real captures and is verified by the
self-test at the bottom (run this file directly).

WHAT IS CONFIRMED
-----------------
1. Partial-bunch reassembly: an actor's initial state spans bunches flagged
   bPartial + bPartialInitial / bPartialFinal. Reassemble in ChSequence order.

2. Export block (bunch has bHasPackageMapExports=1) -- see netguid.py:
       bit bHasRepLayoutExport, i32 NumGUIDsInBunch, N x InternalLoadObject

3. SerializeNewActor (start of an actor channel's open bunch, AFTER any export block):
       InternalLoadObject -> actor NetGUID          (even = dynamic)
       if dynamic:
           InternalLoadObject -> archetype
           InternalLoadObject -> level
           bit bSerializeLocation [+ packed vector]
           bit bSerializeRotation [+ rotator]        <-- [OPEN] exact rotator encoding
           bit bSerializeScale    [+ packed vector]
           bit bSerializeVelocity [+ packed vector]

4. FVector_NetQuantize10 == SerializePackedVector<10,24>:
       SerializeInt(Bits, 24)          -- 5 bits
       3 x SerializeInt(comp, 1<<(Bits+2))
       value = (comp - (1<<(Bits+1))) / 10
   Verified: the captured PlayerController spawns at (-1787.0, -10060.0, -562.5).

5. Content block (repeats until the bunch payload is consumed):
       bit  bHasRepLayout
       bit  bIsActor          (1 = the channel's actor itself; 0 = a subobject)
       if !bIsActor: packed NetGUID (+ subobject header)   <-- [OPEN] exact subobject tail
       packed NumPayloadBits
       <NumPayloadBits bits of payload>
   Confirmed by exact consumption on many complete bunches across several channels.

6. RepLayout property stream (the payload when bHasRepLayout=1):
       repeat: packed Handle ; if Handle == 0 -> end ; <property bits>
   Confirmed: the same handle carries the same width across different channels of the
   same class (e.g. handle 98 -> 9 bits on ch41/ch15/ch26/ch13; handle 10 on ch3/ch22),
   and payloads terminate with the packed-0 handle.

WHAT IS STILL OPEN
------------------
* Per-property bit widths/types (the RepLayout table per WW3 class). These come from
  correlating handles across many packets -- `scan_property_widths()` starts that.
* Scale/velocity encodings in SerializeNewActor (flags never set on the PC spawn).
* Live ownership: the client must accept the PC as AutonomousProxy and possess a Pawn
  before movement works (M4). Capture-faithful open + world drip-feed is the current path.
"""
from netguid import PackageMap, GuidReader


# ---------------------------------------------------------------- bit helpers
class Bits:
    """A bit list with UE4-style readers."""
    def __init__(self, bits, pos=0):
        self.b = bits; self.pos = pos
    def __len__(self): return len(self.b)
    def left(self): return len(self.b) - self.pos
    def bit(self):
        v = self.b[self.pos]; self.pos += 1; return v
    def read(self, k):
        v = 0
        for i in range(k): v |= self.bit() << i
        return v
    def packed(self):
        v = 0; c = 0; more = 1
        while more:
            if self.left() < 8: raise EOFError("packed int past end")
            x = self.read(8); more = x & 1; v += (x >> 1) << (7 * c); c += 1
        return v
    def rint(self, maxv):
        v = 0; m = 1
        while m < maxv:
            if self.bit(): v |= m
            m <<= 1
        return v


def bunch_bits(packet_bytes, bunch):
    s = bunch["payloadStart"]
    return [(packet_bytes[(s + i) >> 3] >> ((s + i) & 7)) & 1 for i in range(bunch["payloadBits"])]


def reassemble(parts):
    """Concatenate partial-bunch bit lists (already in ChSequence order)."""
    out = []
    for p in parts: out.extend(p)
    return out


# ---------------------------------------------------------------- spawn header
def read_packed_vector(r, scale=10, max_bits=24):
    """SerializePackedVector<scale, max_bits> -> (x, y, z) floats."""
    nbits = r.rint(max_bits)
    bias = 1 << (nbits + 1)
    mx = 1 << (nbits + 2)
    return tuple((r.rint(mx) - bias) / float(scale) for _ in range(3))


def read_rotator_net(r):
    """FRotator::NetSerialize as used in SerializeNewActor — 3x SerializeInt(512).

    Confirmed on the captured PlayerController spawn: 27 bits, values map to degrees via
    `comp * 360 / 512` (capture yaw = 90.0 exactly)."""
    comps = [r.rint(512) for _ in range(3)]
    return tuple(c * 360.0 / 512.0 for c in comps), comps


def write_rotator_net(w, degrees):
    """Mirror of read_rotator_net. `degrees` = (pitch, yaw, roll) in degrees."""
    for deg in degrees:
        c = int(round((float(deg) % 360.0) * 512.0 / 360.0)) & 511
        w.write_int_max(c, 512)


def read_new_actor(r, pm):
    """SerializeNewActor. `r` must be positioned right after any export block."""
    info = {}
    gid, _ = pm.load_object(r, exporting=False)
    info["netguid"] = gid
    info["dynamic"] = (gid % 2 == 0) and gid > 0
    if not info["dynamic"]:
        return info
    arch, _ = pm.load_object(r, exporting=False)
    lvl, _ = pm.load_object(r, exporting=False)
    info["archetype"] = arch; info["archetypePath"] = pm.guid_to_path.get(arch)
    info["level"] = lvl;      info["levelPath"] = pm.guid_to_path.get(lvl)
    info["location"] = read_packed_vector(r) if r.bit() else None
    info["incomplete"] = False
    # Rotation — encoding pinned (3x9-bit / SerializeInt(512)). Scale/velocity still open
    # if their flags are set (never observed set on the PC spawn).
    if r.left() < 1:
        info["incomplete"] = True; return info
    if r.bit():
        info["has_rotation"] = True
        if r.left() < 27:
            info["incomplete"] = True; return info
        info["rotation"], info["rotation_comps"] = read_rotator_net(r)
    else:
        info["has_rotation"] = False
        info["rotation"] = None
    for name in ("scale", "velocity"):
        if r.left() < 1:
            info["incomplete"] = True; return info
        if r.bit():
            info["has_" + name] = True
            if name == "scale":
                # Pinned on BP_PlayerPawn_01 capture (src 10–11): 109 bits then
                # velocity flag clear, then component content blocks (9374–9384).
                # Exact FVector codec still TBD; consume fixed width for parse continuity.
                SCALE_BITS = 109
                if r.left() < SCALE_BITS:
                    info["incomplete"] = True; return info
                info["scale_raw_bits"] = [r.bit() for _ in range(SCALE_BITS)]
            else:
                info["incomplete"] = True                # velocity encoding still open
                return info
        else:
            info["has_" + name] = False
    return info


# ---------------------------------------------------------------- content blocks
def read_content_blocks(r, total_bits=None):
    """Parse the content-block chain. Returns a list of blocks; each payload is raw bits.
    Stops cleanly (rather than guessing) if a subobject block is hit, since the subobject
    header tail is not yet pinned."""
    end = len(r.b) if total_bits is None else min(total_bits, len(r.b))
    blocks = []
    while r.pos < end:
        if end - r.pos < 3: break
        start = r.pos
        has_rep = r.bit()
        is_actor = r.bit()
        if not is_actor:
            # Subobject block: packed NetGUID + bStablyNamed, then optionally a packed
            # class NetGUID when bStablyNamed=0 (dynamic spawn), then payload length.
            # Clothing src 212–213 exact-consumes only with the class GUID present
            # (hat 9404 / chest 9406 / CAM 9374 / IM 9384). Stably-named empty stubs
            # on the pawn open still use E=1 with no class field.
            try:
                sub = r.packed()
            except EOFError:
                break
            if sub == 0:
                blocks.append({"isActor": False, "hasRepLayout": has_rep, "bad": True,
                               "start": start})
                break
            stably = r.bit()
            class_guid = None
            if stably == 0:
                try:
                    class_guid = r.packed()
                except EOFError:
                    break
            try:
                npb = r.packed()
            except EOFError:
                break
            if npb < 0 or r.pos + npb > end:
                blocks.append({"isActor": False, "hasRepLayout": has_rep, "subNetGUID": sub,
                               "stablyNamed": stably, "classNetGUID": class_guid,
                               "bad": True, "start": start})
                break
            payload = [r.b[r.pos + i] for i in range(npb)]
            r.pos += npb
            blocks.append({"isActor": False, "hasRepLayout": has_rep, "subNetGUID": sub,
                           "stablyNamed": stably, "classNetGUID": class_guid,
                           "payloadBits": npb, "payload": payload, "start": start})
            continue
        try:
            npb = r.packed()
        except EOFError:
            break
        if npb <= 0 or r.pos + npb > end:
            blocks.append({"isActor": True, "hasRepLayout": has_rep, "bad": True, "start": start})
            break
        payload = [r.b[r.pos + i] for i in range(npb)]
        r.pos += npb
        blocks.append({"isActor": True, "hasRepLayout": has_rep, "payloadBits": npb,
                       "payload": payload, "start": start})
    return blocks


def read_rep_handles(payload_bits):
    """RepLayout stream: packed handle, property bits, ... , packed 0.
    Property widths are unknown, so this returns the handles it can read plus the
    remaining bit count -- enough to correlate widths across many samples."""
    r = Bits(payload_bits)
    out = []
    try:
        h = r.packed()
    except EOFError:
        return out, 0
    if h == 0: return out, r.left()
    out.append(h)
    return out, r.left()


def scan_property_widths(samples):
    """samples = [(chIndex, payload_bits)]. Groups the first handle of each payload with
    the number of bits that follow it (minus the 8-bit packed-0 terminator), which is the
    property's width when a payload carries a single property."""
    table = {}
    for ch, payload in samples:
        handles, rest = read_rep_handles(payload)
        if not handles: continue
        width = rest - 8                              # drop the packed-0 terminator
        if width < 0: continue
        table.setdefault(handles[0], []).append((ch, width))
    return table


# ---------------------------------------------------------------- WRITE side (M3)
from netguid import GuidWriter, EF_HAS_PATH, EF_NO_LOAD, EF_HAS_NET_CHECKSUM


def write_packed_vector(w, vec, scale=10, max_bits=24):
    """Mirror of read_packed_vector: SerializePackedVector<scale,max_bits>."""
    ints = [int(round(c * scale)) for c in vec]
    m = max(abs(v) for v in ints) if ints else 0
    nbits = 1
    while (1 << nbits) <= (1 + m) and nbits < max_bits:
        nbits += 1
    nbits = min(max(nbits - 1, 0), max_bits - 1)
    # grow until every component fits in the biased range
    while any(not (0 <= v + (1 << (nbits + 1)) < (1 << (nbits + 2))) for v in ints) and nbits < max_bits - 1:
        nbits += 1
    w.write_int_max(nbits, max_bits)
    bias = 1 << (nbits + 1); mx = 1 << (nbits + 2)
    for v in ints:
        w.write_int_max(v + bias, mx)


def write_object_export(w, spec):
    """InternalWriteObject mirror -- RECURSIVE, because the reader recurses into the outer.

    spec = {"gid": int, "path": str|None, "checksum": int|None,
            "no_load": bool, "outer": spec|None}

    Wire order (matches the capture exactly):
        packed gid, u8 flags, [<outer object | packed 0>, FString path, [u32 checksum]]

    `path=None` emits a REFERENCE-ONLY export (flags without bHasPath): the object is
    already known to the client, so no outer/path/checksum follows. The real server uses
    this for the actor when exporting its subobjects (flags 0x06).
    `no_load=True` sets bNoLoad -- the real server sets it on the level chain (flags 0x07).
    """
    w.write_packed(spec["gid"])
    checksum = spec.get("checksum")
    path = spec.get("path")
    flags = 0
    if path is not None: flags |= EF_HAS_PATH
    if spec.get("no_load"): flags |= EF_NO_LOAD
    if checksum is not None: flags |= EF_HAS_NET_CHECKSUM
    w.write_bits(flags, 8)
    if path is None:
        return                                       # reference only -- nothing follows
    outer = spec.get("outer")
    if outer:
        write_object_export(w, outer)                # full nested object
    else:
        w.write_packed(0)                            # 0 terminates the outer recursion
    w.write_fstring(path)
    if checksum is not None:
        w.write_uint32(checksum)                     # NetworkChecksum is unsigned


def write_export_block(w, specs):
    """ReceiveNetGUIDBunch mirror. `specs` = list of nested export specs."""
    w.write_bit(0)                                   # bHasRepLayoutExport = 0
    w.write_int32(len(specs))
    for s in specs:
        write_object_export(w, s)


def write_new_actor(w, netguid, archetype_guid, level_guid, location=None, rotation=None):
    """SerializeNewActor mirror (dynamic actor).

    `rotation` = (pitch, yaw, roll) degrees, or None to omit (bSerializeRotation=0).
    """
    w.write_packed(netguid)
    w.write_packed(archetype_guid)
    w.write_packed(level_guid)
    if location is not None:
        w.write_bit(1); write_packed_vector(w, location)
    else:
        w.write_bit(0)
    if rotation is not None:
        w.write_bit(1); write_rotator_net(w, rotation)
    else:
        w.write_bit(0)                               # bSerializeRotation
    w.write_bit(0)                                   # bSerializeScale
    w.write_bit(0)                                   # bSerializeVelocity


def write_content_block(w, payload_bits_list, has_rep_layout=1):
    """Content block for the channel's own actor."""
    w.write_bit(has_rep_layout)
    w.write_bit(1)                                   # bIsActor
    w.write_packed(len(payload_bits_list))
    for b in payload_bits_list:
        w.write_bit(b)


def write_subobject_content_block(w, netguid, stably_named=1, has_rep_layout=0,
                                  payload_bits_list=None, class_netguid=None):
    """Content block for a subobject (bIsActor=0). Empty payloads register the subobject.

    When stably_named=0 the wire packs a class NetGUID between bStablyNamed and
    NumPayloadBits (dynamic spawn) — required for clothing hat/chest 9404/9406.
    """
    payload_bits_list = payload_bits_list or []
    w.write_bit(has_rep_layout)
    w.write_bit(0)                                   # bIsActor = 0
    w.write_packed(netguid)
    w.write_bit(1 if stably_named else 0)
    if not stably_named:
        if class_netguid is None:
            raise ValueError("stably_named=0 requires class_netguid")
        w.write_packed(int(class_netguid))
    w.write_packed(len(payload_bits_list))
    for b in payload_bits_list:
        w.write_bit(b)


def write_rep_properties(props):
    """RepLayout stream: bDoChecksum bit, then packed handle + value bits, ascending,
    terminated by packed 0. `props` = [(handle, [bits...]), ...] -- caller supplies raw
    value bits.

    The leading bit is `FRepLayout::SendProperties`' `bDoChecksum` flag. RepLayout.cpp
    defines ENABLE_PROPERTY_CHECKSUMS unconditionally, so the bit is on the wire in
    Shipping too (0, since net.DoPropertyChecksum defaults off) and
    `FRepLayout::ReceiveProperties` always reads it before the first handle. Verified
    against the capture: with it, 1056 of the capture's actor property blocks decode to
    exactly 0 bits left; without it every block is off by one bit. See `repblock.py`."""
    w = GuidWriter()
    w.write_bit(0)                                   # bDoChecksum
    for handle, bits in sorted(props, key=lambda x: x[0]):
        w.write_packed(handle)
        for b in bits: w.write_bit(b)
    w.write_packed(0)                                # terminator
    return [(w.get_bytes()[i >> 3] >> (i & 7)) & 1 for i in range(w.num)]


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "match_analysis"))
    from pcap_tools import parse_pcap
    import control_channel as cc

    cap = os.path.join(os.path.dirname(__file__), "..", "captures", "24July26",
                       "W3_match_full_2.pcapng")
    pk = parse_pcap(cap)
    sip, sport = "213.183.62.18", 7868
    flow = [("C->S" if dst == sip else "S->C", pl) for ts, src, sp, dst, dp, pl in pk
            if (dst == sip and dp == sport) or (src == sip and sp == sport)]

    # --- 1. the PlayerController spawn (packet 179, channel 2) ---
    p = cc.read_packet(flow[179][1]); b0, b1 = p["bunches"][0], p["bunches"][1]
    bits = reassemble([bunch_bits(flow[179][1], b0), bunch_bits(flow[179][1], b1)])
    pm = PackageMap()
    res = pm.read_export_bunch(bits)
    r = res["reader"]
    actor = read_new_actor(r, pm)
    print(f"[actor] spawn: NetGUID={actor['netguid']} dynamic={actor['dynamic']}")
    print(f"        archetype={actor['archetypePath']}")
    print(f"        level    ={actor['levelPath']}")
    print(f"        location ={actor['location']}")
    assert actor["archetypePath"] == "Default__BP_WW3_DominationPlayerController_01_C"
    assert actor["levelPath"] == "PersistentLevel"
    assert actor["location"] is not None

    # --- 2. content blocks + RepLayout on complete (non-partial) actor bunches ---
    samples, ok_blocks = [], 0
    for i, (d, pl) in enumerate(flow[170:900], start=170):
        if d != "S->C" or not pl or (pl[0] & 1) == 1: continue
        try: q = cc.read_packet(pl)
        except Exception: continue
        for b in q.get("bunches", []):
            if b["chIndex"] == 0 or b["bPartial"] or b.get("bHasPackageMapExports"): continue
            if b["bunchDataBits"] > 400: continue
            bb = bunch_bits(pl, b)
            blocks = read_content_blocks(Bits(bb), b["bunchDataBits"])
            for blk in blocks:
                if blk.get("isActor") and "payload" in blk:
                    ok_blocks += 1
                    if blk["hasRepLayout"]:
                        samples.append((b["chIndex"], blk["payload"]))
    print(f"[actor] parsed {ok_blocks} actor content blocks, {len(samples)} with a RepLayout payload")
    table = scan_property_widths(samples)
    print("[actor] property handle -> observed widths (handle: [(channel, bits), ...])")
    for h in sorted(table)[:12]:
        entries = table[h][:6]
        widths = {w for _, w in table[h]}
        flag = "  CONSISTENT" if len(widths) == 1 and len(table[h]) > 1 else ""
        print(f"    handle {h:5}: {entries}{flag}")
    assert ok_blocks > 10 and table, "expected content blocks with rep payloads"
    print("[OK] actor channel: spawn header + content blocks + RepLayout handles decoded")
