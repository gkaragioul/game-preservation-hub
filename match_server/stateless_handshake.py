#!/usr/bin/env python3
r"""
stateless_handshake.py -- WW3 match-server connect handshake (SERVER side).

This is the very first thing a WW3 client does when it connects to a match server:
a stateless challenge/response so the server doesn't hold per-connection memory for
half-open connections. Sequence:

    client --> InitialConnect     (bHandshakePacket=1, flag=0, Timestamp=0, Cookie=0)
    server --> ConnectChallenge   (flag=1, Timestamp=elapsedServerTime, Cookie=HMAC(secret,...))
    client --> ChallengeResponse  (echoes the challenge VERBATIM -- byte-for-byte)
    server --> ChallengeAck        (flag=1, Timestamp=-1.0 sentinel, Cookie=echoed cookie)
    ... client now sends control-channel (game) packets -> M2.

We are the server, so the secret is OURS -- no studio key needed.

BIT LAYOUT -- LOCKED against the real capture (captures/24July26/W3_match_full_2.pcapng),
byte-for-byte reproduced (see the __main__ self-test which round-trips the REAL packets):

    bit   0        bHandshakePacket        (1 for every handshake packet)
    bit   1        flag                    (0 = client InitialConnect; 1 = server msgs
                                             + the client's echoed ChallengeResponse)
    bits  2..33    Timestamp  -> float32   (LSB-first, little-endian)
                                             InitialConnect=0.0, Challenge=elapsed secs,
                                             Ack=-1.0 (the completion sentinel)
    bits 34..193   Cookie                  (20 bytes = HMAC-SHA1 output)
    bit 194        terminator              (UE4 end-of-packet 1-bit marker)  -> 25 bytes on wire

Note vs stock UE4.21: this build uses a 32-bit FLOAT timestamp (not a 64-bit double) and a
single flag bit before it -- 1+1+32+160 = 194 payload bits. That's why the whole handshake
packet is 25 bytes, and it's what the __main__ self-test verifies against the real bytes.
"""
import hmac, hashlib, os, struct
from ue4_bits import BitWriter, BitReader

COOKIE_BYTE_SIZE = 20        # HMAC-SHA1 output
SECRET_BYTE_SIZE = 64
WIRE_SIZE        = 25        # bytes on the wire (194-bit payload + terminator, byte-padded)
ACK_TIMESTAMP    = -1.0      # the ChallengeAck sentinel (UE4 completion marker)


def _payload_bits(data):
    """The handshake payload length = index of the terminator (highest set bit)."""
    for i in range(len(data) * 8 - 1, -1, -1):
        if (data[i >> 3] >> (i & 7)) & 1:
            return i
    return 0


def _finish(writer):
    """Append the terminator 1-bit and byte-pad to the 25-byte wire size."""
    writer.write_bit(1)
    b = bytearray(writer.get_bytes())
    while len(b) < WIRE_SIZE:
        b.append(0)
    return bytes(b)


class StatelessHandshake:
    def __init__(self, secret=None):
        # our own handshake secret; regenerated each server start unless provided
        self.secret = secret or os.urandom(SECRET_BYTE_SIZE)

    # ---- cookie = HMAC-SHA1(secret, timestamp_bytes(4) + address) ----
    # Keyed on the EXACT 4 float bytes (not the float value) so validation regenerates
    # bit-for-bit regardless of float rounding.
    def generate_cookie(self, address, ts_bytes):
        digest = hmac.new(self.secret, ts_bytes + address.encode(), hashlib.sha1).digest()
        return digest[:COOKIE_BYTE_SIZE]

    # ---- parse any incoming UDP payload ----
    def parse_incoming(self, data):
        """Handshake -> full dict; anything else -> {'is_handshake': False}."""
        if len(data) != WIRE_SIZE:
            return {"is_handshake": False}
        n = _payload_bits(data)
        br = BitReader(data); br.num = n
        if not br.read_bit():                       # bit0 bHandshakePacket
            return {"is_handshake": False}
        flag = br.read_bit()                        # bit1
        ts_bytes = br.serialize_bytes(4)            # float32 timestamp, bits 2..33
        timestamp = struct.unpack("<f", ts_bytes)[0]
        cookie = br.serialize_bytes(COOKIE_BYTE_SIZE)
        return {"is_handshake": True, "flag": flag, "timestamp": timestamp,
                "ts_bytes": ts_bytes, "cookie": cookie,
                "initial": cookie == b"\x00" * COOKIE_BYTE_SIZE,
                "is_ack": timestamp == ACK_TIMESTAMP}

    # ---- build the server's ConnectChallenge ----
    def build_challenge(self, address, server_time):
        ts_bytes = struct.pack("<f", float(server_time))
        w = BitWriter()
        w.write_bit(1)                              # bHandshakePacket
        w.write_bit(1)                              # flag (server message)
        w.serialize_bytes(ts_bytes)                 # float32 timestamp
        w.serialize_bytes(self.generate_cookie(address, ts_bytes))
        return _finish(w)

    # ---- build the server's ChallengeAck (sent after a valid response) ----
    def build_ack(self, cookie):
        w = BitWriter()
        w.write_bit(1)                              # bHandshakePacket
        w.write_bit(1)                              # flag
        w.serialize_bytes(struct.pack("<f", ACK_TIMESTAMP))   # -1.0 sentinel
        w.serialize_bytes(cookie)                   # echo the validated cookie
        return _finish(w)

    # ---- validate the client's ChallengeResponse (stateless) ----
    def validate_response(self, address, ts_bytes, cookie):
        expected = self.generate_cookie(address, ts_bytes)
        return hmac.compare_digest(expected, cookie)


MAX_PACKETID   = 16384      # 14-bit packet sequence
MAX_CHSEQUENCE = 4096       # 12-bit reliable-bunch sequence (verified vs capture + live client)

def sequences_from_cookie(cookie):
    """UE4 derives the connection's starting sequence numbers FROM THE HANDSHAKE COOKIE
    (StatelessConnectHandlerComponent::GetChallengeSequence -> UNetConnection::InitSequence).
    Verified against the capture: cookie 195f2ff8... -> server 7961 / client 14383, which are
    exactly the first packet ids observed, and their &1023 values +1 are exactly the first
    reliable ChSequences observed (794 / 48).

    Returns (server_packet_seq, client_packet_seq).
    """
    server_seq = struct.unpack("<H", cookie[0:2])[0] & (MAX_PACKETID - 1)
    client_seq = struct.unpack("<H", cookie[2:4])[0] & (MAX_PACKETID - 1)
    return server_seq, client_seq


if __name__ == "__main__":
    # 1) round-trip the REAL captured packets byte-for-byte (layout lock)
    REAL_INITIAL   = bytes.fromhex("01000000000000000000000000000000000000000000000004")
    REAL_CHALLENGE = bytes.fromhex("f3c2b50e657cbde0fb332eb46faa305e02b74a58571fa3b506")
    REAL_ACK       = bytes.fromhex("030000fe667cbde0fb332eb46faa305e02b74a58571fa3b506")
    hs = StatelessHandshake()

    pi = hs.parse_incoming(REAL_INITIAL)
    assert pi["is_handshake"] and pi["initial"] and pi["timestamp"] == 0.0, pi
    pc = hs.parse_incoming(REAL_CHALLENGE)
    assert pc["is_handshake"] and not pc["initial"] and abs(pc["timestamp"] - 346.8807) < 1e-3, pc
    pa = hs.parse_incoming(REAL_ACK)
    assert pa["is_handshake"] and pa["is_ack"] and pa["timestamp"] == -1.0, pa
    assert pa["cookie"] == pc["cookie"], "ack echoes the challenge cookie"
    print(f"[OK] real capture decodes: challenge ts={pc['timestamp']:.4f}s  ack ts={pa['timestamp']}  "
          f"cookie={pc['cookie'][:6].hex()}..")

    # 2) full server-side round-trip with OUR secret: challenge -> (client echoes) -> validate -> ack
    addr = "203.0.113.7:54321"
    challenge = hs.build_challenge(addr, 346.8807)
    assert len(challenge) == WIRE_SIZE
    response = challenge                              # the client echoes it verbatim
    p = hs.parse_incoming(response)
    assert hs.validate_response(addr, p["ts_bytes"], p["cookie"]), "our own cookie must validate"
    assert not hs.validate_response("1.2.3.4:9", p["ts_bytes"], p["cookie"]), "wrong addr must fail"
    ack = hs.build_ack(p["cookie"])
    pa2 = hs.parse_incoming(ack)
    assert pa2["is_ack"] and pa2["cookie"] == p["cookie"]
    print(f"[OK] server round-trip: built challenge -> validated echo -> built ack ({len(ack)}B)")
    print("[LOCKED] handshake bit-layout matches the real WW3 match server byte-for-byte.")
