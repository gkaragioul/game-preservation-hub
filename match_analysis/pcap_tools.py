#!/usr/bin/env python3
r"""
pcap_tools.py -- minimal pure-Python pcap reader + analysis helpers for the WW3
match-server reverse engineering (no scapy/tshark needed).

The WW3 match protocol is stock UE4.21 netcode on UDP :7868, PLAINTEXT and
UNCOMPRESSED (confirmed: entropy 4.5-5.9 bits/byte across all activity captures;
AES would be ~8.0, Oodle ~7.5-7.9). So we can decode the wire format directly.

Usage:
    from pcap_tools import parse_pcap, entropy, MATCH_PORT
    pkts = parse_pcap("captures/match/Match_tacops_DMZ_still.pcap")
    for ts, src, sport, dst, dport, payload in pkts: ...
"""
import struct, math, collections

MATCH_PORT = 7868

def _decode_eth_udp(raw, ts):
    """Ethernet+IPv4+UDP frame -> (ts, src, sport, dst, dport, payload) or None."""
    if len(raw) < 42 or raw[12:14] != b"\x08\x00" or raw[23] != 17:   # IPv4 + UDP only
        return None
    ihl = (raw[14] & 0x0f) * 4
    ip = raw[14:]
    src = ".".join(map(str, ip[12:16])); dst = ".".join(map(str, ip[16:20]))
    udp = ip[ihl:]
    sport, dport = struct.unpack(">HH", udp[:4])
    ulen = struct.unpack(">H", udp[4:6])[0]
    return (ts, src, sport, dst, dport, udp[8:8+(ulen-8)])


def parse_pcap(path):
    """Return [(ts, src_ip, sport, dst_ip, dport, payload_bytes), ...] for UDP packets.
    Handles classic .pcap (both byte orders) AND .pcapng. Returns None for unknown."""
    d = open(path, "rb").read()
    magic = d[:4]
    if magic == b"\x0a\x0d\x0d\x0a":                      # pcapng Section Header Block
        return _parse_pcapng(d)
    if magic not in (b"\xa1\xb2\xc3\xd4", b"\xd4\xc3\xb2\xa1"):
        return None
    end = "<" if magic == b"\xd4\xc3\xb2\xa1" else ">"
    off, out = 24, []
    while off + 16 <= len(d):
        ts_s, ts_u, incl, orig = struct.unpack(end + "IIII", d[off:off+16]); off += 16
        raw = d[off:off+incl]; off += incl
        p = _decode_eth_udp(raw, ts_s + ts_u/1e6)
        if p:
            out.append(p)
    return out


def _idb_tsresol_divisor(body, end):
    """Timestamp divisor declared by one Interface Description Block.

    pcapng option 9 (`if_tsresol`) is a single byte: with the high bit clear the
    resolution is 10^-value seconds, with it set it is 2^-(value & 0x7f).  The
    default when the option is absent is 6, i.e. microseconds.

    This matters: several of this project's captures declare 9 (nanoseconds) --
    all five in captures/26July26/ and captures/24July26/W3_match_full_2.pcapng --
    so a hardcoded /1e6 makes their timestamps come out 1000x too large, and any
    duration or delta computed from them is silently wrong by the same factor.
    """
    o = 8                                       # linktype(2) + reserved(2) + snaplen(4)
    res = 6                                     # default: microseconds
    while o + 4 <= len(body):
        code, ln = struct.unpack(end + "HH", body[o:o+4])
        if code == 0:                           # opt_endofopt
            break
        if code == 9 and ln >= 1:
            res = body[o+4]
        o += 4 + ((ln + 3) // 4) * 4            # options are padded to 4 bytes
    if res & 0x80:
        return float(2 ** (res & 0x7F))
    return float(10 ** res)


def _parse_pcapng(d):
    """Minimal pcapng reader: walks blocks, decodes Enhanced Packet Blocks (type 6).
    Assumes Ethernet link-type (the WW3 captures are). Both byte orders.

    Timestamp resolution is read per interface from each IDB's `if_tsresol`
    rather than assumed, and an EPB's interface ID (its first 4 bytes) selects
    the right one when a file describes more than one interface.
    """
    end = "<" if d[8:12] == b"\x4d\x3c\x2b\x1a" else ">"   # byte-order magic in the SHB
    off, out = 0, []
    divisors = []                                          # one per IDB, in file order
    n = len(d)
    while off + 12 <= n:
        btype, blen = struct.unpack(end + "II", d[off:off+8])
        if blen < 12 or off + blen > n:
            break
        body = d[off+8:off+blen-4]
        if btype == 1:                                    # Interface Description Block
            divisors.append(_idb_tsresol_divisor(body, end))
        elif btype == 6 and len(body) >= 20:              # Enhanced Packet Block
            iface, th, tl, cap = struct.unpack(end + "IIII", body[:16])
            # Fall back to microseconds only if the file never described the
            # interface -- never silently mis-scale a declared resolution.
            div = divisors[iface] if iface < len(divisors) else 1e6
            ts = ((th << 32) | tl) / div
            p = _decode_eth_udp(body[20:20+cap], ts)
            if p:
                out.append(p)
        off += blen
    return out

def match_flow(pkts):
    """Split into (client->server, server->client) on the match port."""
    c2s = [p for p in pkts if p[4] == MATCH_PORT]
    s2c = [p for p in pkts if p[2] == MATCH_PORT]
    return c2s, s2c

def entropy(b):
    if not b: return 0.0
    c = collections.Counter(b); n = len(b)
    return -sum((v/n) * math.log2(v/n) for v in c.values())

def read_seq(payload):
    """UE4 packs a 14-bit packet sequence LSB-first at the start of each packet.
    Rough extraction of the low sequence byte for flow-tracking (byte 0 low bits)."""
    return payload[0] if payload else None

if __name__ == "__main__":
    import sys, glob, os
    files = sys.argv[1:] or glob.glob("../captures/match/*.pcap")
    for f in files:
        pk = parse_pcap(f)
        if not pk:
            print(f"{f}: (not classic pcap)"); continue
        c2s, s2c = match_flow(pk)
        ents = [entropy(p[5]) for p in pk if len(p[5]) >= 64 and (p[2]==MATCH_PORT or p[4]==MATCH_PORT)]
        me = sum(ents)/len(ents) if ents else 0
        print(f"{os.path.basename(f):44} C->S={len(c2s):5d} S->C={len(s2c):5d} mean-entropy={me:.2f}")
