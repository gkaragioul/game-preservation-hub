#!/usr/bin/env python3
"""Emit the full pre-h65 profile-replication chain as STRICT_* spec tuples.

`_strict_timeline.py` shows the working server sends nothing but the profile
conversation between the client's first `Server_OnClientPreloadWeaponsFinished`
(C->S h279, src~354) and its `Server_OnMapOpened` + `Server_PlayerInGameNotify`
(C->S h281 / PS h65, src~1050).  Our replay ships only two of those bunches
(src 204, 321), so the client never sees the list opened, filled and finished.

This scans `real_replay_stream.json` for every ch2 S->C bunch in the window that
carries one of the profile RPC handles and prints ready-to-paste spec tuples
(source, delay_s, bits, sha256) in capture order.

Usage:
    python match_server/_gen_profile_prologue_specs.py
    python match_server/_gen_profile_prologue_specs.py --lo 204 --hi 1031
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from possess_rpc import parse_actor_rpc_fields  # noqa: E402

#: AWW3DominationPlayerController handles that make up the profile conversation.
PROFILE_HANDLES = {
    110: "Client_FinishPlayersProfileData",
    111: "Client_ForceClearCurrentPlayersProfileReplication",
    132: "Client_ReceiveServerStartDate",
    133: "Client_ReplicateProfileFromNextPlayerInList",
    137: "Client_SendLatestServerPerformanceData",
    140: "Client_SendPlayersProfileData",
    146: "Client_SetServerPerformanceIconsStatus",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lo", type=int, default=204)
    ap.add_argument("--hi", type=int, default=1031)
    ap.add_argument("--ch", type=int, default=2)
    ap.add_argument("--step", type=float, default=0.200,
                    help="synthetic inter-bunch delay (capture spacing is the "
                         "live server's ~30 s broadcast cadence, not a protocol "
                         "requirement)")
    args = ap.parse_args()

    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
    rows = []
    for i in range(args.lo, min(args.hi, len(stream) - 1) + 1):
        b = stream[i]
        if b["chIndex"] != args.ch or b.get("bOpen"):
            continue
        bits = [int(c) for c in b["payload"]]
        try:
            fields = parse_actor_rpc_fields(bits)
        except Exception:
            continue
        handles = [int(h) for h, _p in (fields or [])]
        hit = [h for h in handles if h in PROFILE_HANDLES]
        if not hit:
            continue
        digest = hashlib.sha256(b["payload"].encode("ascii")).hexdigest()
        rows.append((i, b["bits"], digest, hit))

    print(f"# {len(rows)} profile bunches in src [{args.lo}, {args.hi}] on ch{args.ch}")
    total = 0
    for n, (src, bits, digest, hit) in enumerate(rows):
        names = "+".join(PROFILE_HANDLES[h] for h in hit)
        print(f'    ({src}, {n * args.step:.3f}, {bits}, "{digest}"),'
              f'  # h{hit} {names}')
        total += bits
    print(f"# total {total} bits ({total // 8} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
