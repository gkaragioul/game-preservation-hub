#!/usr/bin/env python3
"""Locate ch4 WAM by sliding decode; locate ch5 WAM block header for in-place strip."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from actor_channel import read_new_actor, write_subobject_content_block
from cam_im_resend import (
    STREAM,
    _bits_from_writer,
    build_wam_stripped_catalog_payload,
)
from netguid import GuidReader, GuidWriter, PackageMap
from _decode_rep_block import decode, layout
import derive_rep_handles as D
from repblock import read_u, read_packed


def decode_wam(payload, bh, ty, enums):
    r = decode(payload, bh, ty, enums=enums)
    if not (r.get("closed") and r.get("left") == 0):
        return None
    by = {x[1]: x for x in r["seq"]}
    if "ReplicatedBatch.AttachmentIds[]" not in by:
        return None
    p = by["ReplicatedBatch.AttachmentIds[]"][5]
    n = read_u(payload, p, 16)
    p2 = p + 16
    ids = []
    for _ in range(n):
        _idx, iw = read_packed(payload, p2)
        p2 += iw
        ids.append(read_u(payload, p2, 16))
        p2 += 16
    return ids


def find_wam_payloads(bits, bh, ty, enums, lengths=(457, 505, 217, 252)):
    found = []
    # step by 1 near 4606 hits, else coarser
    hits_4606 = [
        pos
        for pos in range(0, max(0, len(bits) - 15))
        if sum(bits[pos + i] << i for i in range(16)) == 4606
    ]
    starts = set()
    for h in hits_4606:
        for off in range(0, 250):
            starts.add(max(0, h - off))
    for start in sorted(starts):
        for plen in lengths:
            if start + plen > len(bits):
                continue
            ids = decode_wam(bits[start : start + plen], bh, ty, enums)
            if ids is not None:
                found.append((start, plen, ids))
                break
    # dedupe
    uniq = []
    seen = set()
    for f in found:
        if f[0] not in seen:
            uniq.append(f)
            seen.add(f[0])
    return uniq


def find_block_header_for_payload(bits, payload_start, sub_netguid):
    """Scan backwards for content-block header that yields this payload start."""
    for hdr in range(max(0, payload_start - 80), payload_start):
        p = hdr
        if p + 2 > len(bits):
            continue
        has_rep = bits[p]
        is_actor = bits[p + 1]
        p += 2
        if is_actor:
            continue
        sub, sw = read_packed(bits, p)
        if sub is None:
            continue
        p += sw
        if p >= len(bits):
            continue
        stably = bits[p]
        p += 1
        if stably == 0:
            cls, cw = read_packed(bits, p)
            if cls is None:
                continue
            p += cw
        nbits, nw = read_packed(bits, p)
        if nbits is None:
            continue
        p += nw
        if p == payload_start and sub == sub_netguid:
            return {
                "hdr": hdr,
                "payload_start": p,
                "nbits": nbits,
                "nbits_pos": p - nw,
                "nbits_width": nw,
                "has_rep": has_rep,
                "stably": stably,
            }
    return None


def inplace_replace_payload(bits, hdr_info, new_payload):
    """Replace payload and rewrite packed NumBits; keep trailing bits after old payload."""
    old_start = hdr_info["payload_start"]
    old_n = hdr_info["nbits"]
    old_end = old_start + old_n
    # rebuild: bits[:nbits_pos] + packed(new_n) + new_payload + bits[old_end:]
    w = GuidWriter()
    for b in bits[: hdr_info["nbits_pos"]]:
        w.write_bit(b)
    w.write_packed(len(new_payload))
    for b in new_payload:
        w.write_bit(b)
    for b in bits[old_end:]:
        w.write_bit(b)
    return _bits_from_writer(w)


def main():
    stream = json.loads(STREAM.read_text(encoding="utf-8"))
    sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)
    bh, ty = layout("UWW3WeaponAttachmentManager", classes, structs)

    for label, src in [("ch4 FINAL", 15), ("ch5 FINAL", 17), ("ch86 FINAL", 258)]:
        bits = [int(c) for c in stream[src]["payload"]]
        print(f"\n=== {label} src={src} bits={len(bits)} ===")
        found = find_wam_payloads(bits, bh, ty, enums)
        for start, plen, ids in found:
            print(f"  payload@{start} len={plen} ids={ids} has4606={4606 in ids}")
            # guess sub by scanning headers — try common subs
            for sub in (7956, 8314, 9418, 9426, 8608):
                hi = find_block_header_for_payload(bits, start, sub)
                if hi:
                    print(f"    header for sub={sub}: {hi}")
                    stripped = build_wam_stripped_catalog_payload(batch_id=1)
                    out = inplace_replace_payload(bits, hi, stripped)
                    # verify
                    new_start = None
                    # re-find
                    found2 = find_wam_payloads(out, bh, ty, enums, lengths=(len(stripped), 457, 505))
                    print(f"    after inplace {len(bits)}->{len(out)} remaining_wams={found2}")


if __name__ == "__main__":
    main()
