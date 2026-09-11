#!/usr/bin/env python3
r"""
netguid.py -- UE4 PackageMap / NetGUID codec (M3 foundation).

Every replicated object is referenced on the wire by a NetGUID. The first time the server
mentions an object it EXPORTS it: the NetGUID plus the object's path (and its outer's path,
recursively). Afterwards it's just the small packed NetGUID. This is the layer that has to
work before any actor can be spawned on the client.

Reverse-engineered from captures/24July26/W3_match_full_2.pcapng, packet [179] -- the first
actor bunch of a real match (the PlayerController). Structure confirmed against the real bytes:

  Actor bunch with bHasPackageMapExports=1 begins with ReceiveNetGUIDBunch:
      bit   bHasRepLayoutExport        (0 = a NetGUID export block; 1 = net field exports)
      i32   NumGUIDsInBunch
      NumGUIDsInBunch x InternalLoadObject(...)

  InternalLoadObject:
      packed NetGUID                   (FNetworkGUID via SerializeIntPacked)
      if NetGUID == 0: return          (invalid/none -- terminates the outer recursion)
      u8    ExportFlags                (read because we're inside an export bunch)
              bit0 bHasPath
              bit1 bNoLoad
              bit2 bHasNetworkChecksum
      if bHasPath:
          InternalLoadObject(...)      <-- the OUTER object, recursive
          FString PathName             (this object's name/path relative to its outer)
          if bHasNetworkChecksum: u32 NetworkChecksum

NetGUID parity (UE4): ODD = static (path-loadable asset), EVEN = dynamic (runtime-spawned
actor). Confirmed in the capture: the asset/package GUIDs are 5,7,9,13,15 (odd) while the
spawned PlayerController and its components are 9360,9364,9366,... (even).
"""
from ue4_bits import BitReader, BitWriter

# FExportFlags bits
EF_HAS_PATH         = 0x01
EF_NO_LOAD          = 0x02
EF_HAS_NET_CHECKSUM = 0x04


class GuidReader:
    """Bit reader over a (possibly reassembled) bunch payload given as a list of bits."""
    def __init__(self, bits, pos=0):
        self.bits = bits; self.pos = pos
    def bit(self):
        v = self.bits[self.pos]; self.pos += 1; return v
    def read(self, k):
        v = 0
        for i in range(k):
            v |= self.bit() << i
        return v
    def packed(self):
        """FBitReader::SerializeIntPacked -- 7 bits per byte, bit0 = continuation."""
        v = 0; cnt = 0; more = 1
        while more:
            b = self.read(8); more = b & 1; v += (b >> 1) << (7 * cnt); cnt += 1
        return v
    def rint(self, maxv):
        """FBitReader::SerializeInt(Max) -- LSB-first while mask < Max."""
        v = 0; m = 1
        while m < maxv:
            if self.bit(): v |= m
            m <<= 1
        return v
    def left(self):
        return len(self.bits) - self.pos
    def i32(self):
        v = self.read(32)
        return v - 0x100000000 if v >= 0x80000000 else v
    def fstring(self):
        n = self.i32()
        if n == 0: return ""
        if n < 0:
            raw = bytes(self.read(8) for _ in range(-n * 2))
            return raw.decode("utf-16-le", "replace").rstrip("\x00")
        raw = bytes(self.read(8) for _ in range(n))
        return raw.decode("ascii", "replace").rstrip("\x00")


class GuidWriter(BitWriter):
    def write_int_max(self, value, maxv):
        """FBitWriter::SerializeInt(Value, Max) -- mirror of GuidReader.rint."""
        mask = 1
        while mask < maxv:
            self.write_bit(1 if (value & mask) else 0)
            mask <<= 1
    def write_packed(self, value):
        while True:
            b = value & 0x7f; value >>= 7
            self.write_bits(((b << 1) | (1 if value else 0)) & 0xff, 8)
            if not value: break
    def write_fstring(self, s):
        if s == "":
            self.write_int32(0); return
        data = s.encode("ascii") + b"\x00"
        self.write_int32(len(data)); self.serialize_bytes(data)


class PackageMap:
    """Tracks NetGUID <-> object path, and codes the export blocks."""
    def __init__(self):
        self.guid_to_path = {}      # netguid -> full path string
        self.path_to_guid = {}
        self.next_static = 2        # even = static (path-loadable)
        self.next_dynamic = 1       # odd  = dynamic (runtime-spawned)

    # ---------- reading ----------
    def load_object(self, r, depth=0, out=None, exporting=True):
        """InternalLoadObject. Returns (netguid, path_or_None).

        `exporting` mirrors UE4's bIsExportingNetGUIDBunch: the ExportFlags byte is present
        only inside a NetGUID export block (or when the GUID is the default, 1). Reading it
        outside an export block eats 8 bits that aren't there and desyncs everything after.
        """
        gid = r.packed()
        if gid == 0:
            return 0, None                      # invalid -> ends the outer recursion
        if not (exporting or gid == 1):
            if out is not None:
                out.append({"netguid": gid, "flags": None, "outer": None,
                            "path": self.guid_to_path.get(gid), "checksum": None, "depth": depth})
            return gid, self.guid_to_path.get(gid)
        flags = r.read(8)
        path = None; outer_gid = None; checksum = None
        if flags & EF_HAS_PATH:
            outer_gid, _ = self.load_object(r, depth + 1, out, exporting)
            path = r.fstring()
            if flags & EF_HAS_NET_CHECKSUM:
                checksum = r.read(32)
            self.guid_to_path[gid] = path
            self.path_to_guid.setdefault(path, gid)
        if out is not None:
            out.append({"netguid": gid, "flags": flags, "outer": outer_gid,
                        "path": path, "checksum": checksum, "depth": depth})
        return gid, path

    def read_export_bunch(self, bits, pos=0):
        """ReceiveNetGUIDBunch. Returns (exports, reader_positioned_after_the_block)."""
        r = GuidReader(bits, pos)
        has_rep_layout = r.bit()
        if has_rep_layout:
            return {"repLayoutExport": True, "exports": [], "reader": r}
        num = r.i32()
        exports = []
        for _ in range(num):
            self.load_object(r, 0, exports)
        return {"repLayoutExport": False, "num": num, "exports": exports, "reader": r}

    # ---------- writing ----------
    def assign_static(self, path):
        if path in self.path_to_guid: return self.path_to_guid[path]
        gid = self.next_static; self.next_static += 2
        self.path_to_guid[path] = gid; self.guid_to_path[gid] = path
        return gid

    def assign_dynamic(self):
        gid = self.next_dynamic; self.next_dynamic += 2
        return gid

    def write_object(self, w, gid, path=None, outer_gid=0, outer_path=None, checksum=None):
        """InternalWriteObject: mirror of load_object (one level of outer)."""
        w.write_packed(gid)
        if gid == 0: return
        flags = 0
        if path is not None:
            flags |= EF_HAS_PATH
            if checksum is not None: flags |= EF_HAS_NET_CHECKSUM
        w.write_bits(flags, 8)
        if flags & EF_HAS_PATH:
            if outer_gid:
                self.write_object(w, outer_gid, outer_path)
            else:
                w.write_packed(0)                # no outer
            w.write_fstring(path)
            if checksum is not None: w.write_int32(checksum)


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "match_analysis"))
    from pcap_tools import parse_pcap
    import control_channel as cc

    pk = parse_pcap(os.path.join(os.path.dirname(__file__), "..", "captures", "24July26",
                                 "W3_match_full_2.pcapng"))
    sip, sport = "213.183.62.18", 7868
    flow = [("C->S" if dst == sip else "S->C", pl) for ts, src, sp, dst, dp, pl in pk
            if (dst == sip and dp == sport) or (src == sip and sp == sport)]
    p = cc.read_packet(flow[179][1]); b0, b1 = p["bunches"][0], p["bunches"][1]
    def bb(pl, b):
        return [(pl[(b["payloadStart"] + i) >> 3] >> ((b["payloadStart"] + i) & 7)) & 1
                for i in range(b["payloadBits"])]
    bits = bb(flow[179][1], b0) + bb(flow[179][1], b1)

    pm = PackageMap()
    res = pm.read_export_bunch(bits)
    print(f"[netguid] NetGUID export block: {res['num']} exports "
          f"(repLayoutExport={res['repLayoutExport']})")
    for e in res["exports"]:
        ind = "  " + "    " * e["depth"]
        cs = f" checksum=0x{e['checksum']:08x}" if e["checksum"] is not None else ""
        print(f"{ind}NetGUID {e['netguid']:<5} flags=0x{e['flags']:02x} outer={e['outer']}{cs}")
        if e["path"]: print(f"{ind}  path: {e['path']}")
    print(f"[netguid] reader stopped at bit {res['reader'].pos} of {len(bits)} "
          f"({len(bits)-res['reader'].pos} bits remain = the actor payload)")
    assert res["num"] == 6 and len(res["exports"]) >= 6, "expected 6 exports"
    print("[OK] NetGUID export block decoded from the real capture")
