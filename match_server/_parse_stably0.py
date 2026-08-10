#!/usr/bin/env python3
"""Parse clothing subobject with stably=0 + class NetGUID header."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from actor_channel import Bits  # noqa: E402
from netguid import PackageMap  # noqa: E402
from repblock import read_packed  # noqa: E402
from _decode_rep_block import decode, layout  # noqa: E402
import derive_rep_handles as D  # noqa: E402

stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
bits: list[int] = []
for i in (212, 213):
    bits.extend(int(c) for c in stream[i]["payload"])

pm = PackageMap()
pos = pm.read_export_bunch(bits)["reader"].pos
print("exports:", {g: pm.guid_to_path.get(g) for g in sorted(pm.guid_to_path)})

# block 0 actor
has_rep, is_actor = bits[pos], bits[pos + 1]
pos += 2
nbits, nw = read_packed(bits, pos)
pos += nw + nbits
print(f"actor block done at {pos}, hasRep={has_rep}")

# block 1 subobject
start = pos
has_rep, is_actor = bits[pos], bits[pos + 1]
pos += 2
sub, sw = read_packed(bits, pos)
pos += sw
stably = bits[pos]
pos += 1
print(f"sub={sub} stably={stably} hasRep={has_rep} header@{start}")

# Try: class NetGUID packed (already-mapped static)
cls, cw = read_packed(bits, pos)
print(f"  try class packed={cls} w={cw} path={pm.guid_to_path.get(cls)}")
pos_after_cls = pos + cw

# Also try: full InternalLoadObject with exporting=True style (ExportFlags)
# Seed reader at pos
from netguid import GuidReader

for mode in ("packed_only", "load_exporting", "load_not_exporting"):
    p = pos
    label = mode
    try:
        if mode == "packed_only":
            cls, cw = read_packed(bits, p)
            p2 = p + cw
            note = f"cls={cls} path={pm.guid_to_path.get(cls)}"
        else:
            gr = GuidReader(bits, p)
            pm2 = PackageMap()
            # copy known mappings
            pm2.guid_to_path = dict(pm.guid_to_path)
            gid, path = pm2.load_object(gr, exporting=(mode == "load_exporting"))
            p2 = gr.pos
            note = f"gid={gid} path={path}"
        nbits, nw = read_packed(bits, p2)
        if nbits is None:
            print(f"  {label}: {note} then nbits FAIL")
            continue
        end = p2 + nw + nbits
        ok = end <= len(bits)
        rem = len(bits) - end
        print(
            f"  {label}: {note} nbits={nbits} end={end}/{len(bits)} "
            f"ok={ok} rem={rem}"
        )
        if ok and rem < 64:
            # try consume more blocks until end
            p3 = end
            extra = 0
            while p3 + 3 < len(bits):
                hr, ia = bits[p3], bits[p3 + 1]
                p3 += 2
                if not ia:
                    s2, s2w = read_packed(bits, p3)
                    if s2 is None:
                        break
                    p3 += s2w
                    st2 = bits[p3]
                    p3 += 1
                    if st2 == 0:
                        # class?
                        c2, c2w = read_packed(bits, p3)
                        p3 += c2w
                nb2, nw2 = read_packed(bits, p3)
                if nb2 is None or p3 + nw2 + nb2 > len(bits):
                    break
                p3 += nw2 + nb2
                extra += 1
            print(f"    further blocks≈{extra} final_pos={p3} left={len(bits)-p3}")
    except Exception as ex:
        print(f"  {label}: EXC {ex}")

# Score: after stably, try InternalLoadObject exporting=False with empty map
# (class might be inlined as export)
print("\n=== score class-header models for exact bunch consume ===")
best = []
# model A: no class (current) — already know rem=1639
# model B: packed class guid
# model C: load_object exporting True/False
# model D: bDeleted bit before stably (UE sometimes has this)

def try_walk(header_fn, name):
    p = start + 2  # after hasRep/isActor — wait start already at hasRep
    p = start
    p += 2  # hasRep isActor
    sub_x, sw = read_packed(bits, p)
    p += sw
    # optional deleted bit?
    return header_fn(p, sub_x)

# Simpler manual scores
candidates = []
# after sub+stably at known pos
base = start + 2
sub_x, sw = read_packed(bits, base)
base = base + sw + 1  # +stably

# 1) no extra
for label, skip in [
    ("none", 0),
    ("1bit", 1),
    ("2bit", 2),
]:
    p = base + skip
    nbits, nw = read_packed(bits, p)
    if nbits is not None and p + nw + nbits <= len(bits):
        rem = len(bits) - (p + nw + nbits)
        candidates.append((abs(rem), rem, nbits, label, p))

# packed class
cls, cw = read_packed(bits, base)
if cls is not None:
    p = base + cw
    nbits, nw = read_packed(bits, p)
    if nbits is not None and p + nw + nbits <= len(bits):
        rem = len(bits) - (p + nw + nbits)
        candidates.append((abs(rem), rem, nbits, f"packed_cls={cls}", p))

# load_object variants
for exporting in (True, False):
    try:
        gr = GuidReader(bits, base)
        pm2 = PackageMap()
        pm2.guid_to_path = dict(pm.guid_to_path)
        gid, path = pm2.load_object(gr, exporting=exporting)
        p = gr.pos
        nbits, nw = read_packed(bits, p)
        if nbits is not None and p + nw + nbits <= len(bits):
            rem = len(bits) - (p + nw + nbits)
            candidates.append(
                (abs(rem), rem, nbits, f"load(exp={exporting}) gid={gid} {path}", p)
            )
    except Exception as ex:
        candidates.append((99999, None, None, f"load(exp={exporting}) FAIL {ex}", None))

candidates.sort()
for c in candidates[:15]:
    print(f"  rem={c[1]} nbits={c[2]} model={c[3]}")

# If packed_cls works with rem near 0, decode payload as CAM or Attachment
if candidates and candidates[0][1] == 0:
    print("\nEXACT model found:", candidates[0])
