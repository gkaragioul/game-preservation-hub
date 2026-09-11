#!/usr/bin/env python3
"""Decode capture src 1934 -- the deploy->first-person transition bundle."""
import hashlib, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from possess_rpc import parse_actor_rpc_fields

NAMES = {11:"ClientSetRotation",39:"ClientRestart",45:"ClientSetCameraMode",
         50:"ClientSetViewTarget",254:"Client_OnStopSpectatorBeforeDeploy",
         271:"Client_StopSpectator"}

stream = json.loads((HERE/"real_replay_stream.json").read_text(encoding="utf-8"))
for src in (int(a) for a in sys.argv[1:] or ["1934"]):
    b = stream[src]
    print(f"=== src {src} ch{b['chIndex']} bits={b['bits']} bOpen={b.get('bOpen')} "
          f"bReliable={b.get('bReliable')} bPartial={b.get('bPartial')} "
          f"bPartialInitial={b.get('bPartialInitial')} bPartialFinal={b.get('bPartialFinal')}")
    print(f"    sha256={hashlib.sha256(b['payload'].encode('ascii')).hexdigest()}")
    bits = [int(c) for c in b["payload"]]
    fields = parse_actor_rpc_fields(bits)
    for h, p in fields or []:
        def rd(n):  # packed-int reader over param bits
            return p[:n]
        val = 0
        for i, bit in enumerate(p[:32]):
            val |= bit << i
        print(f"    h{h:<4} {NAMES.get(h,'?'):<36} params={len(p):>4} bits  "
              f"first32={val:#010x}  raw={''.join(str(x) for x in p[:64])}")
