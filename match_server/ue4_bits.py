#!/usr/bin/env python3
r"""
ue4_bits.py -- UE4 bit-level serialization (FBitWriter / FBitReader equivalents).

UE4 packs bits LSB-first within each byte, and integers little-endian. This is the
foundation for EVERYTHING in the WW3 match server: the StatelessConnect handshake,
the packet header (sequence numbers), bunches, and property replication all ride on
this bit layout. Ground truth: Engine/Source/Runtime/Core .../BitReader.cpp,BitWriter.cpp
(UE 4.21). Validated against the plaintext WW3 match captures.
"""
import struct


class BitWriter:
    def __init__(self):
        self.buf = bytearray()
        self.num = 0                      # number of bits written

    def write_bit(self, bit):
        i = self.num >> 3
        if i >= len(self.buf):
            self.buf.append(0)
        if bit:
            self.buf[i] |= (1 << (self.num & 7))   # LSB-first
        self.num += 1

    def write_bits(self, value, nbits):   # value's low nbits, LSB-first
        for i in range(nbits):
            self.write_bit((value >> i) & 1)

    def serialize_bytes(self, data):      # each byte as 8 bits, LSB-first
        for b in data:
            self.write_bits(b, 8)

    def serialize_int(self, value, value_max):
        """FBitWriter::SerializeInt(Value, Max): writes bits while Mask < Max (LSB-first)."""
        assert value < value_max
        mask = 1
        while mask < value_max:
            self.write_bit(1 if (value & mask) else 0)
            mask <<= 1

    def write_double(self, d):            # 8 bytes, little-endian
        self.serialize_bytes(struct.pack("<d", d))

    def write_float(self, f):             # 4 bytes, little-endian (UE4 `Ar << float`)
        self.serialize_bytes(struct.pack("<f", f))

    def write_int32(self, v):
        self.serialize_bytes(struct.pack("<i", v))

    def write_uint32(self, v):
        self.serialize_bytes(struct.pack("<I", v))

    def write_fstring(self, s):
        """UE4 FString: int32 length (incl. null term, negative => UTF-16), then chars+null."""
        if s == "":
            self.write_int32(0); return
        data = s.encode("ascii") + b"\x00"
        self.write_int32(len(data))
        self.serialize_bytes(data)

    def get_bytes(self):
        return bytes(self.buf)

    def num_bits(self):
        return self.num


class BitReader:
    def __init__(self, data):
        self.data = data
        self.num = len(data) * 8
        self.pos = 0

    def read_bit(self):
        if self.pos >= self.num:
            return 0
        b = (self.data[self.pos >> 3] >> (self.pos & 7)) & 1
        self.pos += 1
        return b

    def read_bits(self, nbits):
        v = 0
        for i in range(nbits):
            v |= self.read_bit() << i
        return v

    def serialize_bytes(self, n):
        return bytes(self.read_bits(8) for _ in range(n))

    def serialize_int(self, value_max):
        """FBitReader::SerializeInt(Max): reconstruct Value bit-by-bit (LSB-first)."""
        value = 0
        mask = 1
        while mask < value_max:
            if self.read_bit():
                value |= mask
            mask <<= 1
        return value

    def read_double(self):
        return struct.unpack("<d", self.serialize_bytes(8))[0]

    def read_float(self):
        return struct.unpack("<f", self.serialize_bytes(4))[0]

    def read_int32(self):
        return struct.unpack("<i", self.serialize_bytes(4))[0]

    def read_uint32(self):
        return struct.unpack("<I", self.serialize_bytes(4))[0]

    def read_fstring(self):
        n = self.read_int32()
        if n == 0:
            return ""
        if n < 0:                          # UTF-16
            raw = self.serialize_bytes(-n * 2)
            return raw.decode("utf-16-le", "replace").rstrip("\x00")
        raw = self.serialize_bytes(n)
        return raw.decode("ascii", "replace").rstrip("\x00")

    def bits_left(self):
        return self.num - self.pos


if __name__ == "__main__":
    # round-trip sanity check
    w = BitWriter()
    w.write_bit(1); w.write_bit(0); w.write_bit(1)
    w.write_double(1234.5); w.serialize_bytes(b"\xde\xad\xbe\xef"); w.write_fstring("127.0.0.1:7871")
    r = BitReader(w.get_bytes())
    assert r.read_bit() == 1 and r.read_bit() == 0 and r.read_bit() == 1
    assert r.read_double() == 1234.5
    assert r.serialize_bytes(4) == b"\xde\xad\xbe\xef"
    assert r.read_fstring() == "127.0.0.1:7871"
    print("[OK] ue4_bits round-trip passes")
