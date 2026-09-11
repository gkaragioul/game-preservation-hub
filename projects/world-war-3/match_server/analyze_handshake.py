#!/usr/bin/env python3
r"""
analyze_handshake.py <capture.pcap> [server_ip:port]

Decodes the START of a WW3 match connection (the StatelessConnect handshake) from a
FRESH full-match capture -- the one recorded from BEFORE the client joined. Use it to
validate/lock the exact bit layout that stateless_handshake.py assumes.

If no server_ip:port is given, it auto-picks the busiest remote UDP endpoint (the match
server) and analyzes the first packets of that flow -- the handshake, if the capture
started before the join.
"""
import sys, os, collections
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "match_analysis"))
from pcap_tools import parse_pcap
from stateless_handshake import StatelessHandshake

def main(path, want=None):
    pk = parse_pcap(path)
    if not pk:
        print("not a classic pcap (pcapng? re-save as pcap in Wireshark)"); return
    # find the match-server endpoint: busiest remote (non-LAN, non-DNS) UDP peer
    peers = collections.Counter()
    for ts, src, sp, dst, dp, pl in pk:
        for ip, port in ((dst, dp), (src, sp)):
            if not ip.startswith(("192.168.", "10.", "127.", "224.", "239.", "255.")) and port > 1024:
                peers[(ip, port)] += 1
    if want:
        ip, port = want.split(":"); server = (ip, int(port))
    elif peers:
        server = peers.most_common(1)[0][0]
    else:
        print("no external UDP peer found -- is this a match capture?"); return
    sip, sport = server
    print(f"match server endpoint: {sip}:{sport}")
    flow = [(ts, src, sp, dst, dp, pl) for ts, src, sp, dst, dp, pl in pk
            if (dst == sip and dp == sport) or (src == sip and sp == sport)]
    print(f"packets on this flow: {len(flow)} (first packet is {'C->S' if flow[0][3]==sip else 'S->C'})")

    hs = StatelessHandshake()
    print("\n=== first 12 packets decoded as handshake ===")
    for i, (ts, src, sp, dst, dp, pl) in enumerate(flow[:12]):
        d = "C->S" if dst == sip else "S->C"
        info = hs.parse_incoming(pl)
        if info.get("is_handshake"):
            kind = ("InitialConnect" if info["initial"] else
                    "ChallengeAck" if info["is_ack"] else "Challenge/Response")
            extra = f" [{kind}] flag={info['flag']} ts={info['timestamp']:.4f} cookie={info['cookie'][:6].hex()}.."
        else:
            extra = " [game/control packet]"
        print(f"[{i:2}] {d} len={len(pl):4d} first-bit={pl[0]&1}{extra}")
        print(f"     hex: {pl[:28].hex(' ')}")
    print("\nExpected handshake: InitialConnect(ts=0) -> Challenge(ts=elapsed secs) ->")
    print("Response(echo) -> ChallengeAck(ts=-1.0) -> then control/game packets (first-bit=0).")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: analyze_handshake.py <capture.pcap> [server_ip:port]"); sys.exit(1)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
