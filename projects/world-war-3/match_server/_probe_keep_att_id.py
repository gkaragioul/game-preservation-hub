#!/usr/bin/env python3
"""Identify keep-dyn attachment class / item id from weapon opens."""
from __future__ import annotations

import json
from pathlib import Path

from cam_im_resend import WAM_KEEP_REPLICATED, WAM_OPEN_FINAL_SRCS, _find_wam_block_header
from netguid import PackageMap
from repblock import read_packed

HERE = Path(__file__).resolve().parent
stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))

OPEN_SRCS = {
    8314: (14, 15),
    7956: (16, 17),
    9418: (257, 258),
    9426: (259, 260),
}


def walk_from(bits, start):
    blocks = []
    p = start
    n = len(bits)
    while p + 3 <= n:
        has_rep = bits[p]
        is_actor = bits[p + 1]
        p0 = p
        p += 2
        sub = stably = cls = None
        if not is_actor:
            sub, sw = read_packed(bits, p)
            if sub is None:
                break
            p += sw
            if p >= n:
                break
            stably = bits[p]
            p += 1
            if stably == 0:
                cls, cw = read_packed(bits, p)
                if cls is None:
                    break
                p += cw
        nbits, nw = read_packed(bits, p)
        if nbits is None or p + nw + nbits > n:
            break
        p += nw
        payload = bits[p : p + nbits]
        p += nbits
        blocks.append({"sub": sub, "stably": stably, "cls": cls, "nbits": nbits, "payload": payload, "has_rep": has_rep})
        if len(blocks) > 12:
            break
    return blocks


def main():
    for wam, srcs in OPEN_SRCS.items():
        keep = WAM_KEEP_REPLICATED[wam]
        bits = []
        for i in srcs:
            bits.extend(int(c) for c in stream[i]["payload"])
        pm = PackageMap()
        er = pm.read_export_bunch(bits)
        # dump exports that might name class for keep
        print(f"\n=== wam={wam} keep={keep} exports={len(getattr(pm, 'guid_to_path', {}) or {})}")
        # PackageMap internals vary — print export paths from reader if available
        if hasattr(pm, "netguids"):
            pass
        final = [int(c) for c in stream[srcs[1]]["payload"]]
        hdr = _find_wam_block_header(final, wam)
        blocks = walk_from(final, hdr["hdr"])
        for b in blocks:
            mark = ""
            if b["sub"] == wam:
                mark = " WAM"
            if b["sub"] == keep:
                mark = " KEEP"
            print(f"  sub={b['sub']} stably={b['stably']} cls={b['cls']} bits={b['nbits']}{mark}")
            if b["sub"] == keep:
                pl = b["payload"]
                print(f"    payload hex-ish first 64 bits: {pl[:64]}")
                # try uint16 scans
                for off in range(0, min(20, len(pl) - 15)):
                    v = sum(pl[off + i] << i for i in range(16))
                    if 1 <= v <= 10000:
                        print(f"    u16@{off}={v}")

        # INIT+FINAL export paths
        bits2 = []
        for i in srcs:
            bits2.extend(int(c) for c in stream[i]["payload"])
        pm2 = PackageMap()
        info = pm2.read_export_bunch(bits2)
        # inspect common attrs
        for attr in ("exports", "paths", "guid_path", "path_cache", "objects"):
            if hasattr(pm2, attr):
                print(f"  pm.{attr}={getattr(pm2, attr)!r}"[:500])
        # Guid map
        if hasattr(pm2, "guid_to_path"):
            for g, path in list(pm2.guid_to_path.items())[:20]:
                print(f"  export {g} -> {path}")
        # Try reading from info
        print(f"  export_info_keys={list(info.keys()) if isinstance(info, dict) else type(info)}")


if __name__ == "__main__":
    main()
