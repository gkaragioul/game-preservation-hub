#!/usr/bin/env python3
"""Find the actual S->C datagram(s) we sent this live session that carried the pawn
open bunch (chIndex==3, bOpen==1), and dump full packet decode (seq, acks, ALL bunches
in that datagram) to check for packetization issues (bad ack count, multiple bunches
sharing a datagram in a way that could desync the receiver, wrong terminator, etc.)."""
import json
import sys
import binascii

sys.path.insert(0, "match_server")
import control_channel as cc

path = sys.argv[1]

with open(path, encoding="utf-8", errors="replace") as f:
    for line_no, line in enumerate(f):
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("dir") != "S->C":
            continue
        try:
            data = binascii.unhexlify(d["hex"])
        except Exception:
            continue
        try:
            p = cc.read_packet(data)
        except Exception as e:
            continue
        if p.get("is_handshake"):
            continue
        for b in p.get("bunches", []):
            if b["chIndex"] == 3 and b.get("bOpen"):
                print(f"=== line={line_no} t={d['t']} datagram_len={len(data)} ===")
                print(f"seq={p['seq']} acks={p['acks']} truncated={p.get('truncated')}")
                print(f"n_bunches_in_packet={len(p['bunches'])}")
                for bi, bb in enumerate(p["bunches"]):
                    print(f"  bunch[{bi}] ch={bb['chIndex']} bOpen={bb.get('bOpen')} "
                          f"bClose={bb.get('bClose')} bReliable={bb['bReliable']} "
                          f"chSeq={bb.get('chSeq')} bPartial={bb['bPartial']} "
                          f"partialInit={bb.get('bPartialInitial')} partialFinal={bb.get('bPartialFinal')} "
                          f"exports={bb['bHasPackageMapExports']} mbm={bb['bHasMustBeMappedGUIDs']} "
                          f"bits={bb['bunchDataBits']} truncated={bb.get('truncated')}")
                print(f"hex={d['hex']}")
                print()
