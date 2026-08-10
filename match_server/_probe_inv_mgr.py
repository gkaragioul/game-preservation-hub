#!/usr/bin/env python3
"""Map InventoryManager / attachment sync in capture (ch3 open + clothing)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import derive_rep_handles as D  # noqa: E402
from _decode_rep_block import decode, layout  # noqa: E402
from actor_channel import Bits, read_content_blocks, read_new_actor  # noqa: E402
from netguid import PackageMap  # noqa: E402


def main() -> int:
    sdk = Path(os.environ.get("WW3_DUMPER7_DIR", str(D.DEFAULT_DUMP)))
    if sdk.name != "SDK":
        sdk = sdk / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)

    for cn in ("UActorComponent", "UWW3InventoryManagerBase", "UWW3InventoryManager"):
        c = classes[cn]
        nets = [p for p in c["props"] if "Net" in p[3]]
        print(f"=== {cn} net={len(nets)} super={c.get('super')}")
        for p in nets:
            print(f"  0x{p[0]:04x} {p[1]:40s} {p[2]}")

    for sn in (
        "FWW3ReplicatedInventory",
        "FWW3CurrentItemRepInfo",
        "FWW3SimProxyEquipInfo",
        "FWW3WeaponsPreloadRequest",
        "FWW3CustomizationConfigOptimized",
        "FWW3EquipmentLoadoutOptimized",
        "FWW3ProfileLoadoutOptimized",
    ):
        s = structs.get(sn)
        if not s:
            print("missing struct", sn)
            continue
        print(f"=== STRUCT {sn} super={s.get('super')}")
        for p in s["props"]:
            print(f"  0x{p[0]:04x} {p[1]:40s} {p[2]}")

    by_h, types = layout("UWW3InventoryManager", classes, structs)
    print("=== InventoryManager RepLayout handles ===")
    for h in sorted(by_h):
        name, typ = by_h[h][0], by_h[h][1] if len(by_h[h]) > 1 else by_h[h]
        # layout returns dict handle -> (name, type) or similar
        print(f"  h{h}: {by_h[h]}  type_entry={types.get(h)}")

    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))

    # --- pawn open ---
    bits: list[int] = []
    for i in (10, 11):
        bits.extend(int(c) for c in stream[i]["payload"])
    pm = PackageMap()
    res = pm.read_export_bunch(bits)
    r = res["reader"]
    print("\n=== pawn open exports ===")
    for e in res["exports"]:
        cs = f" checksum=0x{e['checksum']:08x}" if e.get("checksum") is not None else ""
        print(f"  {e['netguid']} outer={e['outer']} path={e.get('path')}{cs}")
    read_new_actor(r, pm)
    blocks = read_content_blocks(Bits(bits, r.pos))
    print("content blocks:", len(blocks))
    for b in blocks:
        print(
            f"  isActor={b.get('isActor')} hasRep={b.get('hasRepLayout')} "
            f"bits={b.get('payloadBits')} sub={b.get('subNetGUID')} bad={b.get('bad')}"
        )
        if b.get("subNetGUID") == 9384 and b.get("payload"):
            pl = b["payload"]
            print("  IM payload bits:", len(pl), "".join(str(x) for x in pl))
            rdec = decode(pl, by_h, types, enums=enums)
            print(
                f"  decode closed={rdec['closed']} reason={rdec['reason']} "
                f"left={rdec['left']}"
            )
            for h, name, typ, w, note, p in rdec["seq"]:
                print(f"    @{p} h{h} {name} {typ} w={w} {note}")

    # --- clothing ---
    bits2: list[int] = []
    for i in (212, 213):
        bits2.extend(int(c) for c in stream[i]["payload"])
    pm2 = PackageMap()
    res2 = pm2.read_export_bunch(bits2)
    r2 = res2["reader"]
    print("\n=== clothing exports ===")
    for e in res2["exports"]:
        cs = f" checksum=0x{e['checksum']:08x}" if e.get("checksum") is not None else ""
        print(f"  {e['netguid']} outer={e['outer']} path={e.get('path')}{cs}")
    print(f"pos after export {r2.pos}/{len(bits2)}")
    blocks2 = read_content_blocks(Bits(bits2, r2.pos), total_bits=len(bits2))
    print("content blocks:", len(blocks2))
    for bi, b in enumerate(blocks2):
        pl = b.get("payload") or []
        print(
            f"  [{bi}] isActor={b.get('isActor')} hasRep={b.get('hasRepLayout')} "
            f"bits={b.get('payloadBits')} sub={b.get('subNetGUID')} bad={b.get('bad')} "
            f"payload_len={len(pl)}"
        )
        if pl and b.get("hasRepLayout"):
            # try decode as pawn actor if isActor
            if b.get("isActor"):
                leaf = "ABP_PlayerPawn_01_C"
                if leaf not in classes:
                    # find
                    for cand in classes:
                        if "PlayerPawn_01" in cand:
                            leaf = cand
                            break
                bh, ty = layout(leaf, classes, structs)
                rdec = decode(pl, bh, ty, enums=enums)
                print(
                    f"    pawn decode closed={rdec['closed']} reason={rdec['reason']} "
                    f"left={rdec['left']} props={len(rdec['seq'])}"
                )
                for h, name, typ, w, note, p in rdec["seq"][:12]:
                    print(f"      @{p} h{h} {name} {typ} w={w} {note}")
            elif b.get("subNetGUID"):
                # unknown subobject — dump head
                print("    head96:", "".join(str(x) for x in pl[:96]))

    # Scan all ch3 bunches for subobject 9384 / 9404 content after open
    print("\n=== ch3 later blocks touching InventoryManager / unknown subs ===")
    from collections import defaultdict

    pending: dict[int, list[int]] = defaultdict(list)

    def groups():
        for i, sp in enumerate(stream):
            ch = sp["chIndex"]
            if ch != 3:
                continue
            if not sp.get("bPartial"):
                yield [i]
                continue
            if sp.get("bPartialInitial"):
                pending[ch] = [i]
            elif pending.get(ch):
                pending[ch].append(i)
            if sp.get("bPartialFinal") and pending.get(ch):
                yield pending.pop(ch)

    sub_hits = []
    for idxs in groups():
        specs = [stream[i] for i in idxs]
        if specs[0].get("bOpen"):
            continue
        bits3: list[int] = []
        for sp in specs:
            bits3.extend(int(c) for c in sp["payload"])
        pos = 0
        pm3 = PackageMap()
        try:
            if specs[0].get("bHasPackageMapExports"):
                pos = pm3.read_export_bunch(bits3)["reader"].pos
            bl = read_content_blocks(Bits(bits3, pos), total_bits=len(bits3))
        except Exception as ex:
            continue
        for b in bl:
            sub = b.get("subNetGUID")
            if sub in (9384, 9374, 9404) or (
                not b.get("isActor") and b.get("payloadBits") and b.get("payloadBits") > 50
            ):
                sub_hits.append((idxs[0], sub, b.get("hasRepLayout"), b.get("payloadBits"), b.get("bad")))

    print(f"hits: {len(sub_hits)}")
    for h in sub_hits[:40]:
        print(f"  src={h[0]} sub={h[1]} hasRep={h[2]} bits={h[3]} bad={h[4]}")

    # Find when 9404 / attachment managers get exported
    print("\n=== exports mentioning 9404 / Inventory / Attachment paths (first 80) ===")
    n = 0
    for i, sp in enumerate(stream):
        if not sp.get("bHasPackageMapExports"):
            continue
        bits_e = [int(c) for c in sp["payload"]]
        try:
            res_e = PackageMap().read_export_bunch(bits_e)
        except Exception:
            continue
        for e in res_e["exports"]:
            path = str(e.get("path") or "")
            gid = e.get("netguid")
            interesting = gid in (9404, 9384, 9374) or any(
                k in path
                for k in (
                    "Inventor",
                    "CharacterAttachment",
                    "AttachmentManager",
                    "BP_CH_",
                    "WeaponAttachment",
                )
            )
            if not interesting:
                continue
            print(
                f"  src={i} ch={sp['chIndex']} guid={gid} outer={e['outer']} path={path}"
            )
            n += 1
            if n >= 80:
                break
        if n >= 80:
            break

    print("\n=== bootstrap neighborhood src 115-130 ===")
    for i in range(115, 131):
        sp = stream[i]
        print(
            f"  src={i} ch={sp['chIndex']} bits={sp['bits']} "
            f"open={int(bool(sp.get('bOpen')))} exp={int(bool(sp.get('bHasPackageMapExports')))} "
            f"partial={int(bool(sp.get('bPartial')))}"
        )

    # Manual decode of IM 98-bit: try bitfields as 1-bit for bReplicates/bIsActive
    print("\n=== manual IM 98-bit walk (bitfield-aware guess) ===")
    # payload already printed above; re-fetch
    bits_im = None
    bits_re = []
    for i in (10, 11):
        bits_re.extend(int(c) for c in stream[i]["payload"])
    pm_re = PackageMap()
    r_re = pm_re.read_export_bunch(bits_re)["reader"]
    read_new_actor(r_re, pm_re)
    for b in read_content_blocks(Bits(bits_re, r_re.pos)):
        if b.get("subNetGUID") == 9384:
            bits_im = b["payload"]
    if bits_im:
        from repblock import read_packed, REP_BLOCK_PREFIX_BITS

        pos = REP_BLOCK_PREFIX_BITS
        print(f"  checksum bit={bits_im[0]} len={len(bits_im)}")
        # Try interpreting first props as 1-bit bools
        seq = []
        while pos < len(bits_im):
            h, hw = read_packed(bits_im, pos)
            if h is None:
                print(f"  eof at {pos}")
                break
            pos += hw
            if h == 0:
                print(f"  terminator at {pos}, left={len(bits_im)-pos}")
                break
            # guess widths for early handles
            if h in (1, 2, 4):  # bitfields / bool
                w = 1
            elif h == 5:  # ForceItemID uint8
                w = 8
            elif h in (15, 16, 17, 18, 19, 23, 24):  # enums - try 3 or packed
                w = 3
            elif h in (3, 6, 10, 11, 12, 13, 14, 25, 26, 27, 29, 40, 41):
                # object refs - packed netguid often small
                # read remaining as packed
                from repblock import read_packed as rp

                v, vw = rp(bits_im, pos)
                note = f"obj? packed={v}"
                seq.append((h, vw, note))
                pos += vw
                print(f"  h{h} w={vw} {note} pos={pos}")
                continue
            else:
                w = 8
            if pos + w > len(bits_im):
                print(f"  h{h} need {w} overflow at {pos}")
                break
            val_bits = bits_im[pos : pos + w]
            pos += w
            seq.append((h, w, val_bits))
            print(f"  h{h} w={w} bits={''.join(str(x) for x in val_bits)} pos={pos}")
        print(f"  final pos={pos} left={len(bits_im)-pos} seq_len={len(seq)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
