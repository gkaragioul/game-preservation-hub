#!/usr/bin/env python3
"""Locate NetGUID 9404 and InventoryManager follow-up bunches on ch3."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from actor_channel import Bits, read_content_blocks, read_new_actor  # noqa: E402
from netguid import PackageMap  # noqa: E402

STREAM = HERE / "real_replay_stream.json"


def groups(stream, ch_filter=None):
    pending: dict[int, list[int]] = defaultdict(list)
    for i, sp in enumerate(stream):
        ch = sp["chIndex"]
        if ch_filter is not None and ch != ch_filter:
            continue
        if not sp.get("bPartial"):
            yield ch, [i]
            continue
        if sp.get("bPartialInitial"):
            pending[ch] = [i]
        elif pending.get(ch):
            pending[ch].append(i)
        if sp.get("bPartialFinal") and pending.get(ch):
            yield ch, pending.pop(ch)


def main() -> int:
    stream = json.loads(STREAM.read_text(encoding="utf-8"))

    print("=== first sightings of GUID 9404 / 9384 content ===")
    seen_export = set()
    for ch, idxs in groups(stream):
        specs = [stream[i] for i in idxs]
        bits: list[int] = []
        for sp in specs:
            bits.extend(int(c) for c in sp["payload"])
        pos = 0
        pm = PackageMap()
        try:
            if specs[0].get("bHasPackageMapExports"):
                res = pm.read_export_bunch(bits)
                pos = res["reader"].pos
                for e in res["exports"]:
                    gid = e.get("netguid")
                    if gid in (9404, 9384, 9374) and gid not in seen_export:
                        seen_export.add(gid)
                        print(
                            f"  EXPORT first src={idxs[0]} ch={ch} guid={gid} "
                            f"outer={e.get('outer')} path={e.get('path')}"
                        )
            if specs[0].get("bOpen"):
                gr_pos = pos
                # may fail if incomplete; ignore
                try:
                    from netguid import GuidReader

                    gr = GuidReader(bits, pos)
                    read_new_actor(gr, pm)
                    pos = gr.pos
                except Exception:
                    pass
            blocks = read_content_blocks(Bits(bits, pos), total_bits=len(bits))
        except Exception:
            continue
        for b in blocks:
            sub = b.get("subNetGUID")
            if sub in (9404, 9384, 9374) and b.get("payloadBits"):
                print(
                    f"  CONTENT src={idxs[0]} ch={ch} sub={sub} "
                    f"hasRep={b.get('hasRepLayout')} bits={b.get('payloadBits')} "
                    f"isActor={b.get('isActor')} bad={b.get('bad')}"
                )

    # Decode clothing bunch more carefully: remaining bits after block1
    print("\n=== clothing bunch deep dive src 212/213 ===")
    bits2: list[int] = []
    for i in (212, 213):
        bits2.extend(int(c) for c in stream[i]["payload"])
    pm2 = PackageMap()
    res2 = pm2.read_export_bunch(bits2)
    r2 = res2["reader"]
    print(f"exports={res2['num']} pos={r2.pos}/{len(bits2)}")
    # Walk content blocks manually with leftover dump
    from actor_channel import Bits as B

    reader = B(bits2, r2.pos)
    # peek: keep reading until we can't
    blocks = read_content_blocks(reader, total_bits=len(bits2))
    consumed = reader.pos if hasattr(reader, "pos") else None
    # Bits may track pos
    print(f"blocks={len(blocks)} reader.pos={getattr(reader, 'pos', '?')} total={len(bits2)}")
    for bi, b in enumerate(blocks):
        print(
            f"  [{bi}] isActor={b.get('isActor')} hasRep={b.get('hasRepLayout')} "
            f"sub={b.get('subNetGUID')} payloadBits={b.get('payloadBits')} bad={b.get('bad')}"
        )
    # How many bits after export before end?
    # Re-implement walk to get exact end pos
    pos = r2.pos
    for bi in range(10):
        if pos >= len(bits2):
            break
        # content block header: hasRepLayout, bIsActor
        if pos + 2 > len(bits2):
            print(f"  leftover header truncated at {pos}, left={len(bits2)-pos}")
            break
        has_rep = bits2[pos]
        is_actor = bits2[pos + 1]
        pos += 2
        sub = None
        if not is_actor:
            # packed netguid
            from repblock import read_packed

            sub, sw = read_packed(bits2, pos)
            if sub is None:
                print(f"  bad subguid at {pos}")
                break
            pos += sw
            # stably named bit
            if pos >= len(bits2):
                break
            stably = bits2[pos]
            pos += 1
        from repblock import read_packed

        nbits, nw = read_packed(bits2, pos)
        if nbits is None:
            print(f"  bad nbits at {pos} isActor={is_actor} hasRep={has_rep} sub={sub}")
            print(f"  remaining bits head64: {''.join(str(x) for x in bits2[pos:pos+64])}")
            print(f"  left={len(bits2)-pos}")
            break
        pos += nw
        print(
            f"  walk[{bi}] hasRep={has_rep} isActor={is_actor} sub={sub} "
            f"nbits={nbits} stably={stably if not is_actor else '-'} "
            f"payload_start={pos} end={pos+nbits}"
        )
        if pos + nbits > len(bits2):
            print(f"  OVERFLOW payload would end at {pos+nbits} > {len(bits2)}")
            print(f"  leftover after header: {len(bits2)-pos}")
            break
        pos += nbits
    print(f"  final pos={pos} left={len(bits2)-pos}")
    if pos < len(bits2):
        rem = bits2[pos:]
        print(f"  rem head128: {''.join(str(x) for x in rem[:128])}")
        # try ClassNetCache field chain: SerializeInt(index, Max+1) + packed len + payload
        # For UWW3CharacterAttachmentManager / pawn - try scoring MaxIndex
        print("  scoring custom-delta MaxIndex on rem...")
        best = []
        for vmax in range(1, 64):
            p = 0
            fields = 0
            ok = True
            while p < len(rem):
                # SerializeInt wrapped: read bits while (written+mask)<vmax
                # Approximate: use same as possess_rpc
                from possess_rpc import read_int_wrapped

                try:
                    idx, iw = read_int_wrapped(rem, p, vmax)
                except Exception:
                    ok = False
                    break
                p += iw
                if idx == 0:
                    break
                n, nw = read_packed(rem, p)
                if n is None or p + nw + n > len(rem):
                    ok = False
                    break
                p += nw + n
                fields += 1
                if fields > 64:
                    ok = False
                    break
            if ok and p == len(rem):
                best.append((vmax, fields))
        print(f"  exact-consume MaxIndex candidates: {best[:20]}")

    # Weapon channel opens in bootstrap range
    print("\n=== ch4/ch5 opens early (src < 300) ===")
    for ch, idxs in groups(stream):
        if ch not in (4, 5):
            continue
        if idxs[0] > 300:
            continue
        sp0 = stream[idxs[0]]
        if not sp0.get("bOpen"):
            continue
        bits = []
        for i in idxs:
            bits.extend(int(c) for c in stream[i]["payload"])
        pm = PackageMap()
        pos = 0
        paths = []
        if sp0.get("bHasPackageMapExports"):
            res = pm.read_export_bunch(bits)
            pos = res["reader"].pos
            paths = [(e["netguid"], e.get("path"), e.get("outer")) for e in res["exports"][:12]]
        try:
            from netguid import GuidReader

            gr = GuidReader(bits, pos)
            info = read_new_actor(gr, pm)
            arch = info.get("archetypePath")
            guid = info.get("netguid")
        except Exception as ex:
            arch, guid = f"err:{ex}", None
        print(f"  src={idxs[0]} ch={ch} actor={guid} arch={arch}")
        for p in paths[:8]:
            print(f"    export {p}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
