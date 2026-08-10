#!/usr/bin/env python3
r"""
control_channel.py -- WW3 match-server control channel (M2), UE4.21 LEGACY netcode.

Reverse-engineered byte-for-byte from captures/24July26/W3_match_full_2.pcapng and validated
by round-tripping the real captured packets (see __main__). This is the layer that runs
AFTER the StatelessConnect handshake (stateless_handshake.py, M1):

    client --NMT_Hello-->  server --NMT_Challenge-->  client --NMT_Login(URL+UniqueId+lobbyToken)-->
    server (validate token) --NMT_Welcome(map,gamemode)-->  client loads the map (M3).

WIRE FORMAT (LSB-first bits; see docs/M2_ControlChannel_Findings.md):

Packet:
    bit  bHandshakePacket = 0                 (StatelessConnect prepends; 1 = handshake pkt)
    14   PacketId  (sequence, +1 per pkt/dir)
    ack section: while ReadBit()==1: AckPacketId(14)   -- a 0 bit ends the section
    bunch(es)...
    bit  terminator = 1                        (UE4 end-of-packet marker; then zero-pad to byte)

Bunch header:
    bControl(1); if bControl: bOpen(1) bClose(1)
    bIsReplicationPaused(1)
    bReliable(1)
    ChIndex (SerializeIntPacked)               -- control channel = 0
    bHasPackageMapExports(1) bHasMustBeMappedGUIDs(1) bPartial(1)
    if bReliable: ChSequence = ReadInt(1024)   (10 bits)
    if bPartial:  bPartialInitial(1) bPartialFinal(1)
    if bReliable or bOpen: ChName block        -- 5-bit constant for the control channel:
                                                  C->S = 0b00110 ("01100" LSB), S->C = 0b00111 ("11100" LSB)
    BunchDataBits = ReadInt(MaxPacket*8 = 8192) (13 bits)
    <BunchDataBits bits of payload>

Control message payload = NMT message type (uint8) + message-specific fields (FString = int32
length incl null, then chars; ints little-endian; all bit-packed LSB-first).
"""
import struct
from ue4_bits import BitReader, BitWriter

# --- NMT control message types (UE4) ---
NMT_Hello=0; NMT_Welcome=1; NMT_Upgrade=2; NMT_Challenge=3; NMT_Netspeed=4
NMT_Login=5; NMT_Failure=6; NMT_Join=9; NMT_JoinSplit=10; NMT_PCSwap=15
NMT_NAMES={0:"Hello",1:"Welcome",2:"Upgrade",3:"Challenge",4:"Netspeed",5:"Login",
           6:"Failure",9:"Join",10:"JoinSplit",15:"PCSwap"}

MAX_PACKETID=16384      # 14 bits
MAX_CHSEQUENCE=4096     # 12 bits -- verified: ChType then decodes as Control(1)/Actor(2)
                        # and actor bunches come out with consecutive ChSequence.
MAX_BUNCH_BITS=8192     # ReadInt(MaxPacket*8), MaxPacket=1024
CHTYPE_MAX=8            # ReadInt(CHTYPE_MAX) -> 3 bits
CHTYPE_CONTROL=1
CHTYPE_ACTOR=2
CLOSE_REASON_BITS=2     # present only when bClose=1
MAX_CHANNEL_INDEX=255   # real channel indices are 0..255; higher = we lost bit-alignment


# ---------- bit helpers (LSB-first, matching ue4_bits) ----------
class CReader(BitReader):
    def read_int_max(self, maxv):
        v=0; mask=1
        while mask<maxv:
            if self.read_bit(): v|=mask
            mask<<=1
        return v
    def read_packed(self):
        v=0; cnt=0; more=1
        while more:
            b=self.read_bits(8); more=b&1; v+=(b>>1)<<(7*cnt); cnt+=1
        return v
    def read_fstring(self):
        n=self.read_int32()
        if n==0: return ""
        if n<0:  return self.serialize_bytes(-n*2).decode("utf-16-le","replace").rstrip("\x00")
        return self.serialize_bytes(n).decode("ascii","replace").rstrip("\x00")

class CWriter(BitWriter):
    def write_int_max(self, value, maxv):
        mask=1
        while mask<maxv:
            self.write_bit(1 if (value&mask) else 0)
            mask<<=1
    def write_packed(self, value):
        while True:
            b=value&0x7f; value>>=7
            self.write_bits(((b<<1)|(1 if value else 0))&0xff, 8)
            if not value: break
    def write_fstring(self, s):
        if s=="":
            self.write_int32(0); return
        data=s.encode("ascii")+b"\x00"
        self.write_int32(len(data)); self.serialize_bytes(data)


def _payload_bits(data):
    for i in range(len(data)*8-1,-1,-1):
        if (data[i>>3]>>(i&7))&1: return i
    return 0


# ---------- packet / bunch READER ----------
def read_packet(data):
    """Parse a post-handshake packet -> {seq, acks:[...], bunches:[{...}]}.

    Legacy entry loop: each entry is prefixed by an IsAck bit (1 -> 14-bit AckId,
    0 -> bunch). Stop with 1 bit left (the inner UNetConnection terminator; the outer
    PacketHandler terminator is the highest set bit that bounds `term`)."""
    term=_payload_bits(data)
    r=CReader(data); r.num=term
    hs=r.read_bit()
    if hs: return {"is_handshake":True}
    seq=r.read_bits(14)
    acks=[]; bunches=[]
    while term-r.pos>1:
        if r.read_bit()==1:                          # IsAck
            ack=r.read_bits(14)                      # AckPacketId
            if r.read_bit():                         # bHasServerFrameTime
                r.read_bits(8)                       #   FrameTimeByte
            r.read_bits(8)                           # RemoteInKBytesPerSecond
            acks.append(ack)
        else:
            b=_read_bunch(r, term)
            if b is None: break
            # FAIL-SAFE: a bunch that decodes to an impossible channel index means we lost
            # bit-alignment somewhere in this packet; everything after it is garbage. Stop
            # here and flag it rather than emitting nonsense that callers might replay or
            # mine. ~1% of real packets hit this (a residual long tail in the ack section).
            if b["chIndex"] > MAX_CHANNEL_INDEX:
                return {"is_handshake":False,"seq":seq,"acks":acks,"bunches":bunches,
                        "truncated":True}
            bunches.append(b)
    return {"is_handshake":False,"seq":seq,"acks":acks,"bunches":bunches,"truncated":False}

def _read_bunch(r, term):
    if term-r.pos < 8: return None                  # only the terminator bit left
    b={}
    b["bControl"]=r.read_bit()
    if b["bControl"]:
        b["bOpen"]=r.read_bit(); b["bClose"]=r.read_bit()
    else:
        b["bOpen"]=0; b["bClose"]=0
    # A close bunch carries a 2-bit close reason (verified: only this width makes a real
    # client close-bunch decode to chIndex 0 / reliable / ChType=Control / 0 payload bits).
    b["closeReason"]=r.read_bits(CLOSE_REASON_BITS) if b["bClose"] else 0
    b["bIsReplicationPaused"]=r.read_bit()
    b["bReliable"]=r.read_bit()
    b["chIndex"]=r.read_packed()
    b["bHasPackageMapExports"]=r.read_bit()
    b["bHasMustBeMappedGUIDs"]=r.read_bit()
    b["bPartial"]=r.read_bit()
    b["chSeq"]=r.read_int_max(MAX_CHSEQUENCE) if b["bReliable"] else 0
    if b["bPartial"]:
        b["bPartialInitial"]=r.read_bit(); b["bPartialFinal"]=r.read_bit()
    if b["bReliable"] or b["bOpen"]:
        b["chType"]=r.read_int_max(CHTYPE_MAX)      # 1=Control, 2=Actor
    b["bunchDataBits"]=r.read_int_max(MAX_BUNCH_BITS)
    start=r.pos
    b["payloadStart"]=start
    # Guard against a bunch claiming more bits than the datagram actually holds (malformed,
    # or our own mis-parse). Never let it run off the end -- that used to crash the server.
    avail=len(r.data)*8 - start
    b["truncated"] = b["bunchDataBits"] > avail
    b["payloadBits"]=min(b["bunchDataBits"], max(0, avail))
    payload=CReader(r.data); payload.pos=start; payload.num=start+b["payloadBits"]
    b["reader"]=payload
    # NMT type = first payload byte -- ONLY meaningful on the control channel for a bunch
    # that starts a message (a partial CONTINUATION carries raw payload, not an NMT type).
    b["nmt"]=None
    is_msg_start = (not b["bPartial"]) or b.get("bPartialInitial",0)
    if b["chIndex"]==0 and is_msg_start and b["payloadBits"]>=8:
        mt=CReader(r.data); mt.pos=start; mt.num=start+b["payloadBits"]
        b["nmt"]=mt.read_bits(8)
    r.pos=start+b["bunchDataBits"]
    if r.pos>term: r.pos=term          # clamp so the entry loop always terminates
    return b

# ---------- NMT message parsers ----------
def parse_hello(reader):
    reader.read_bits(8)                              # NMT type
    return {"isLittleEndian":reader.read_bits(8),
            "remoteNetworkVersion":reader.read_uint32(),
            "encryptionToken":reader.read_fstring()}

def parse_challenge(reader):
    reader.read_bits(8)
    return {"challenge":reader.read_fstring()}

def parse_login(reader):
    reader.read_bits(8)                              # NMT type = 5
    client_response=reader.read_fstring()            # response to the challenge
    url=reader.read_fstring()                        # login URL (map + options)
    return {"clientResponse":client_response,"url":url,"_reader":reader}
    # UniqueId + trailing lobbyToken follow; UniqueId serialization is version-specific, so
    # the token is pulled with find_lobby_token() below (robust to the UniqueId layout).

def find_lobby_token(bunch):
    """Pull the trailing lobbyToken FString (a JWT 'eyJ...') out of an NMT_Login bunch."""
    data=bunch["reader"].data; start=bunch["payloadStart"]; end=start+bunch["bunchDataBits"]
    # scan bit alignments for 'eyJ' then read the FString length prefix 32 bits before it
    for base in range(start, end-24):
        if all(((data[(base+k)>>3]>>((base+k)&7))&1)==(( (b'eyJ'[k>>3])>>(k&7))&1) for k in range(24)):
            r=CReader(data); r.pos=base-32; r.num=len(data)*8
            n=r.read_int32()
            if 0<n<4096:
                s=r.serialize_bytes(n).rstrip(b"\x00").decode("ascii","replace")
                if s.startswith("eyJ"): return s
    return None


# ---------- packet / bunch WRITER (mirror of the reader) ----------
def write_packet(seq, acks, bunches):
    """bunches = list of (nbits, bytes) from make_control_bunch. Entry-loop format:
    each ack -> IsAck(1)+14-bit id; each bunch -> IsAck(0)+bunch; then two terminators."""
    w=CWriter()
    w.write_bit(0)                                   # bHandshakePacket=0
    w.write_bits(seq, 14)
    for a in acks:
        w.write_bit(1); w.write_bits(a, 14)          # IsAck=1 + AckPacketId
        w.write_bit(0)                               # bHasServerFrameTime = 0 (no FrameTimeByte)
        w.write_bits(0, 8)                           # RemoteInKBytesPerSecond
    for nbits,data in bunches:
        w.write_bit(0)                               # IsAck=0 -> this entry is a bunch
        for i in range(nbits):
            w.write_bit((data[i>>3]>>(i&7))&1)
    w.write_bit(1)                                   # UNetConnection packet terminator (inner)
    w.write_bit(1)                                   # PacketHandler terminator (outer)
    return w.get_bytes()

def make_control_bunch(nmt_payload_writer, ch_seq, bOpen=0, direction_s2c=True):
    """Build a reliable control-channel (index 0) bunch carrying an NMT message.
    direction_s2c is kept for call-site compatibility; the wire format is symmetric."""
    payload=nmt_payload_writer.get_bytes(); payload_bits=nmt_payload_writer.num
    w=CWriter()
    bControl=1 if bOpen else 0
    w.write_bit(bControl)
    if bControl:
        w.write_bit(bOpen); w.write_bit(0)           # bOpen, bClose=0
    w.write_bit(0)                                   # bIsReplicationPaused
    w.write_bit(1)                                   # bReliable
    w.write_packed(0)                                # chIndex = 0 (control)
    w.write_bit(0); w.write_bit(0); w.write_bit(0)   # bHasPME, bHasMBM, bPartial
    w.write_int_max(ch_seq, MAX_CHSEQUENCE)          # ChSequence (12 bits)
    w.write_int_max(CHTYPE_CONTROL, CHTYPE_MAX)      # ChType = Control
    w.write_int_max(payload_bits, MAX_BUNCH_BITS)
    for i in range(payload_bits):
        w.write_bit((payload[i>>3]>>(i&7))&1)
    return (w.num, w.get_bytes())

def make_bunch(payload_bits, payload_bytes, ch_index, ch_seq, ch_type,
               bOpen=0, bClose=0, bReliable=1, bHasPackageMapExports=0,
               bPartial=0, bPartialInitial=0, bPartialFinal=0,
               bHasMustBeMappedGUIDs=0):
    """Generic bunch writer -- the mirror of _read_bunch. Used for actor channels (M3);
    make_control_bunch() is the channel-0 special case."""
    w=CWriter()
    bControl = 1 if (bOpen or bClose) else 0
    w.write_bit(bControl)
    if bControl:
        w.write_bit(bOpen); w.write_bit(bClose)
    if bClose:
        w.write_bits(0, CLOSE_REASON_BITS)
    w.write_bit(0)                                   # bIsReplicationPaused
    w.write_bit(bReliable)
    w.write_packed(ch_index)
    w.write_bit(bHasPackageMapExports)
    w.write_bit(1 if bHasMustBeMappedGUIDs else 0)
    w.write_bit(bPartial)
    if bReliable:
        w.write_int_max(ch_seq, MAX_CHSEQUENCE)
    if bPartial:
        w.write_bit(bPartialInitial); w.write_bit(bPartialFinal)
    if bReliable or bOpen:
        w.write_int_max(ch_type, CHTYPE_MAX)
    w.write_int_max(payload_bits, MAX_BUNCH_BITS)
    for i in range(payload_bits):
        w.write_bit((payload_bytes[i>>3]>>(i&7))&1)
    return (w.num, w.get_bytes())


def build_challenge_msg(challenge_str):
    w=CWriter(); w.write_bits(NMT_Challenge,8); w.write_fstring(challenge_str); return w

def build_welcome_msg(level_map, game_name, redirect_url="", extra=""):
    """WW3's NMT_Welcome carries FOUR FStrings, not the vanilla three: the real server's
    Welcome bunch is exactly 32 bits longer than type+3 strings, and those 32 bits are an
    empty FString (length 0). Verified on all three full-match captures. Omitting it made
    the client over-read, fail the message, and CLOSE the control channel."""
    w=CWriter(); w.write_bits(NMT_Welcome,8)
    w.write_fstring(level_map); w.write_fstring(game_name)
    w.write_fstring(redirect_url); w.write_fstring(extra)
    return w


if __name__=="__main__":
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__),"..","match_analysis"))
    from pcap_tools import parse_pcap
    pk=parse_pcap(os.path.join(os.path.dirname(__file__),"..","captures","24July26","W3_match_full_2.pcapng"))
    sip,sport="213.183.62.18",7868
    flow=[("C->S" if dst==sip else "S->C",pl) for ts,src,sp,dst,dp,pl in pk
          if (dst==sip and dp==sport) or (src==sip and sp==sport)]

    print("=== READ the real control packets ===")
    for idx,label in [(4,"Hello"),(5,"Challenge"),(7,"Login"),(12,"Welcome?")]:
        d=flow[idx][1]; p=read_packet(d)
        b=p["bunches"][0]
        line=f"[{idx}] {label:9} seq={p['seq']:5} acks={p['acks']} | bunch: bOpen={b['bOpen']} rel={b['bReliable']} chIdx={b['chIndex']} chSeq={b['chSeq']} bits={b['bunchDataBits']} NMT={b.get('nmt')}({NMT_NAMES.get(b.get('nmt'),'?')})"
        print(line)
        if b.get("nmt")==NMT_Hello:
            print("     ",parse_hello(b["reader"]))
        elif b.get("nmt")==NMT_Challenge:
            print("     ",parse_challenge(b["reader"]))
        elif b.get("nmt")==NMT_Login:
            lg=parse_login(b["reader"]); tok=find_lobby_token(b)
            print(f"      url={lg['url']!r}")
            print(f"      lobbyToken={'FOUND ('+str(len(tok))+' chars) '+tok[:40]+'...' if tok else 'NOT FOUND'}")

    print("\n=== ROUND-TRIP: read a packet, re-serialize its bunches, compare bytes ===")
    for idx in (4,5,7):
        d=flow[idx][1]; p=read_packet(d)
        bunches=[]
        for b in p["bunches"]:
            # re-serialize this exact bunch from its parsed fields
            w=CWriter()
            w.write_bit(b["bControl"])
            if b["bControl"]: w.write_bit(b["bOpen"]); w.write_bit(b["bClose"])
            if b["bClose"]: w.write_bits(b["closeReason"], CLOSE_REASON_BITS)
            w.write_bit(b["bIsReplicationPaused"]); w.write_bit(b["bReliable"])
            w.write_packed(b["chIndex"])
            w.write_bit(b["bHasPackageMapExports"]); w.write_bit(b["bHasMustBeMappedGUIDs"]); w.write_bit(b["bPartial"])
            if b["bReliable"]: w.write_int_max(b["chSeq"], MAX_CHSEQUENCE)
            if b["bPartial"]: w.write_bit(b["bPartialInitial"]); w.write_bit(b["bPartialFinal"])
            if b["bReliable"] or b["bOpen"]: w.write_int_max(b["chType"], CHTYPE_MAX)
            w.write_int_max(b["bunchDataBits"], MAX_BUNCH_BITS)
            pr=CReader(b["reader"].data); pr.pos=b["payloadStart"]; pr.num=b["payloadStart"]+b["bunchDataBits"]
            for _ in range(b["bunchDataBits"]): w.write_bit(pr.read_bit())
            bunches.append((w.num, w.get_bytes()))
        rebuilt=write_packet(p["seq"], p["acks"], bunches)
        ok = rebuilt==d
        print(f"[{idx}] round-trip {'MATCH ✓' if ok else 'DIFF'}  ({len(d)}B)")
        if not ok:
            print(f"     orig:    {d.hex(' ')}")
            print(f"     rebuilt: {rebuilt.hex(' ')}")
