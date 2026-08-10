#!/usr/bin/env python3
"""Find how inventory/attachments actually fill after pawn open in capture."""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from actor_channel import Bits, read_content_blocks, read_new_actor  # noqa: E402
from netguid import PackageMap  # noqa: E402

stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))


def groups(ch_filter=None):
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


# Stats on ch3 content after open
print("=== ch3 content-block census (post-open) ===")
kinds = Counter()
examples = defaultdict(list)
for ch, idxs in groups(3):
    if stream[idxs[0]].get("bOpen"):
        continue
    bits: list[int] = []
    for i in idxs:
        bits.extend(int(c) for c in stream[i]["payload"])
    pos = 0
    pm = PackageMap()
    try:
        if stream[idxs[0]].get("bHasPackageMapExports"):
            pos = pm.read_export_bunch(bits)["reader"].pos
        bl = read_content_blocks(Bits(bits, pos), total_bits=len(bits))
    except Exception as ex:
        kinds["parse_fail"] += 1
        continue
    left = len(bits) - Bits(bits, pos).pos if False else None
    # re-read with tracking end
    r = Bits(bits, pos)
    bl = read_content_blocks(r, total_bits=len(bits))
    rem = len(bits) - r.pos
    for b in bl:
        key = (
            f"isActor={int(bool(b.get('isActor')))}"
            f"|hasRep={int(bool(b.get('hasRepLayout')))}"
            f"|sub={b.get('subNetGUID')}"
            f"|bits={b.get('payloadBits')}"
            f"|stably={b.get('stablyNamed')}"
            f"|bad={b.get('bad')}"
        )
        # compress
        k2 = (
            f"isActor={int(bool(b.get('isActor')))} hasRep={int(bool(b.get('hasRepLayout')))} "
            f"sub={b.get('subNetGUID')} stably={b.get('stablyNamed')} "
            f"bitbucket={b.get('payloadBits') if (b.get('payloadBits') or 0) < 50 else 'BIG'}"
            f"{'|bad' if b.get('bad') else ''}"
        )
        kinds[k2] += 1
        if len(examples[k2]) < 3:
            examples[k2].append(idxs[0])
    if rem > 8:
        kinds[f"LEFTOVER~{rem}"] += 1
        if len(examples["LEFTOVER"]) < 5:
            examples["LEFTOVER"].append((idxs[0], rem))

for k, c in kinds.most_common(40):
    print(f"  {c:>5}  {k}  eg={examples.get(k, examples.get('LEFTOVER', []))[:3]}")

# ch4/ch5 content census
for chx in (4, 5):
    print(f"\n=== ch{chx} content census ===")
    kinds = Counter()
    n_bunches = 0
    for ch, idxs in groups(chx):
        n_bunches += 1
        bits = []
        for i in idxs:
            bits.extend(int(c) for c in stream[i]["payload"])
        pos = 0
        pm = PackageMap()
        try:
            if stream[idxs[0]].get("bHasPackageMapExports"):
                pos = pm.read_export_bunch(bits)["reader"].pos
            if stream[idxs[0]].get("bOpen"):
                from netguid import GuidReader

                gr = GuidReader(bits, pos)
                try:
                    read_new_actor(gr, pm)
                    pos = gr.pos
                except Exception:
                    pass
            r = Bits(bits, pos)
            bl = read_content_blocks(r, total_bits=len(bits))
        except Exception:
            kinds["fail"] += 1
            continue
        for b in bl:
            k2 = (
                f"isActor={int(bool(b.get('isActor')))} hasRep={int(bool(b.get('hasRepLayout')))} "
                f"sub={b.get('subNetGUID')} bits="
                f"{b.get('payloadBits') if (b.get('payloadBits') or 0) < 80 else 'BIG'}"
                f"{'|bad' if b.get('bad') else ''}"
            )
            kinds[k2] += 1
    print(f"  bunches={n_bunches}")
    for k, c in kinds.most_common(25):
        print(f"  {c:>5}  {k}")

# Specifically: any block targeting 9384 or 9374 or 8314 anywhere
print("\n=== any content targeting CAM/IM/WAM guids ===")
targets = {9374, 9384, 8314, 7952}  # CAM, IM, WAM ch4, FireType?
# also collect all sub guids seen on ch3/4/5
sub_hist = Counter()
for ch, idxs in groups():
    if ch not in (3, 4, 5):
        continue
    bits = []
    for i in idxs:
        bits.extend(int(c) for c in stream[i]["payload"])
    pos = 0
    pm = PackageMap()
    try:
        if stream[idxs[0]].get("bHasPackageMapExports"):
            pos = pm.read_export_bunch(bits)["reader"].pos
        if stream[idxs[0]].get("bOpen"):
            from netguid import GuidReader

            gr = GuidReader(bits, pos)
            try:
                read_new_actor(gr, pm)
                pos = gr.pos
            except Exception:
                pass
        bl = read_content_blocks(Bits(bits, pos), total_bits=len(bits))
    except Exception:
        continue
    for b in bl:
        sub = b.get("subNetGUID")
        if sub:
            sub_hist[sub] += 1
        if sub in targets or (b.get("payloadBits") and sub and b.get("payloadBits") > 0):
            if sub in targets or (sub and sub >= 9374 and sub <= 9420):
                print(
                    f"  ch{ch} src={idxs[0]} sub={sub} hasRep={b.get('hasRepLayout')} "
                    f"bits={b.get('payloadBits')} stably={b.get('stablyNamed')}"
                )

print("\nsubguid histogram ch3/4/5 top 30:")
for s, c in sub_hist.most_common(30):
    print(f"  {s}: {c}")
