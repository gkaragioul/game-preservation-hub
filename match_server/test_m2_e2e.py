#!/usr/bin/env python3
r"""
test_m2_e2e.py -- end-to-end M1+M2 pipeline test (no sockets).

Drives MatchServer through a full join with our OWN code on both sides:
  InitialConnect -> Challenge -> (client echoes) -> Ack        (M1 handshake)
  NMT_Hello -> NMT_Challenge -> NMT_Login(+minted lobbyToken) -> NMT_Welcome   (M2)
and asserts the server reaches LOGGED_IN and emits a well-formed NMT_Welcome that
re-parses back to the token's map. Also feeds the REAL captured NMT_Login packet to
confirm the server parses/extracts a live client's token.
"""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "match_analysis"))
from server import MatchServer, Conn
import control_channel as cc
from lobby_token import mint
from pcap_tools import parse_pcap

CLIENT = ("203.0.113.9", 55000)
KEY = f"{CLIENT[0]}:{CLIENT[1]}"

class MockSock:
    def __init__(self): self.sent = []
    def sendto(self, data, addr): self.sent.append((data, addr))
    def pop(self): return self.sent.pop(0)[0] if self.sent else None
    def pop_bunch(self):
        """Skip ack-only packets (the server sends acks in their own packet, like the real
        one) and return the first packet that actually carries a bunch."""
        while self.sent:
            d = self.sent.pop(0)[0]
            p = cc.read_packet(d)
            if not p.get("is_handshake") and p.get("bunches"):
                return d, p
        return None, None

def build_hello(netver=0x8ace8fc5):
    w = cc.CWriter()
    w.write_bits(cc.NMT_Hello, 8); w.write_bits(1, 8); w.write_uint32(netver); w.write_fstring("")
    return w

def build_login(response, url, token):
    w = cc.CWriter()
    w.write_bits(cc.NMT_Login, 8)
    w.write_fstring(response); w.write_fstring(url)
    w.write_fstring("76561198000000001")   # stand-in UniqueId (find_lobby_token scans past it)
    w.write_fstring(token)
    return w

def client_packet(seq, bunch, acks=()):
    return cc.write_packet(seq, list(acks), [bunch])

def run():
    srv = MatchServer(7871); s = MockSock()

    # --- M1 handshake ---
    INITIAL = bytes.fromhex("01000000000000000000000000000000000000000000000004")
    srv.handle(s, INITIAL, CLIENT)
    challenge = s.pop(); assert challenge and len(challenge) == 25, "server must send ConnectChallenge"
    srv.handle(s, challenge, CLIENT)                 # client echoes the challenge verbatim
    ack = s.pop(); assert ack, "server must send ChallengeAck"
    assert srv.conns[KEY].state == "CONNECTED", srv.conns[KEY].state
    print("[e2e] M1 handshake: InitialConnect -> Challenge -> Response(echo) -> Ack  OK")

    conn = srv.conns[KEY]; cseq = 100
    # --- M2: NMT_Hello -> NMT_Challenge ---
    srv.handle(s, client_packet(cseq, cc.make_control_bunch(build_hello(), 1, bOpen=1, direction_s2c=False)), CLIENT); cseq += 1
    chal_pkt, p = s.pop_bunch(); assert chal_pkt, "server must reply to Hello"
    nmt = p["bunches"][0]["nmt"]
    assert nmt == cc.NMT_Challenge, f"expected NMT_Challenge, got {cc.NMT_NAMES.get(nmt)}"
    chal = cc.parse_challenge(p["bunches"][0]["reader"])["challenge"]
    print(f"[e2e] M2 Hello -> server NMT_Challenge '{chal}'  OK")

    # --- M2: NMT_Login (with a token WE mint, our secret) -> NMT_Welcome ---
    now = int(time.time())
    claims = {"type":"LobbyToken","lobbyId":70121,"playerId":100002,"serverGroup":"default",
              "team":{"id":1},"isServerAssigned":True,
              "server":{"serverId":17659577,"matchId":"17659577-x","address":"127.0.0.1",
                        "gamePort":7871,"queryPort":27115,"serverGroup":"default",
                        "map":"WW3_Gobi_New_P","gameMode":47},
              "iat":now,"exp":now+3600}
    token = mint(claims)
    url = "/Game/Maps/Main/Hub/WW3_Hub_P?Name=Player?BuildIdOverride=51?EosProductUserId=deadbeef"
    srv.handle(s, client_packet(cseq, cc.make_control_bunch(build_login(chal, url, token), 2, direction_s2c=False)), CLIENT)
    welc_pkt, p = s.pop_bunch(); assert welc_pkt, "server must reply to Login"
    wb = p["bunches"][0]
    assert wb["nmt"] == cc.NMT_Welcome, f"expected NMT_Welcome, got {cc.NMT_NAMES.get(wb['nmt'])}"
    r = wb["reader"]; r.read_bits(8)
    level = r.read_fstring(); game = r.read_fstring()
    assert srv.conns[KEY].state == "LOGGED_IN", srv.conns[KEY].state
    assert "WW3_Gobi_New_P" in level, level
    print(f"[e2e] M2 Login(valid token) -> server NMT_Welcome(level={level}, game={game})  OK")
    print("[e2e] *** FULL M1+M2 PIPELINE PASSED: client reaches LOGGED_IN ***")

    # --- feed the REAL captured NMT_Login: server must parse it + extract the live token ---
    cap = parse_pcap(os.path.join(os.path.dirname(__file__),"..","captures","24July26","W3_match_full_2.pcapng"))
    sip,sport="213.183.62.18",7868
    flow=[("C->S" if dst==sip else "S->C",pl) for ts,src,sp,dst,dp,pl in cap
          if (dst==sip and dp==sport) or (src==sip and sp==sport)]
    real_login = flow[7][1]
    p = cc.read_packet(real_login); b = p["bunches"][0]
    tok = cc.find_lobby_token(b)
    assert b["nmt"] == cc.NMT_Login and tok and tok.startswith("eyJ"), "must parse real login + token"
    print(f"[e2e] REAL captured NMT_Login parsed: token extracted ({len(tok)} chars), "
          f"validates-against-our-secret={False} (studio-signed, expected)")

if __name__ == "__main__":
    run()
