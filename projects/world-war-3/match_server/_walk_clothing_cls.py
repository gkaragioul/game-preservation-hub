#!/usr/bin/env python3
"""Walk clothing bunch with stably=0 + packed class NetGUID before nbits."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

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

sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
classes, structs = D.parse_sdk(sdk)
enums = D.parse_enums(sdk)


def walk(include_class: bool):
    p = pos
    blocks = []
    while p + 3 <= len(bits):
        start = p
        has_rep = bits[p]
        is_actor = bits[p + 1]
        p += 2
        sub = None
        stably = None
        cls = None
        if not is_actor:
            sub, sw = read_packed(bits, p)
            if sub is None:
                return blocks, p, "bad_sub"
            p += sw
            if p >= len(bits):
                return blocks, p, "eof_stably"
            stably = bits[p]
            p += 1
            if include_class and stably == 0:
                cls, cw = read_packed(bits, p)
                if cls is None:
                    return blocks, p, "bad_cls"
                p += cw
        nbits, nw = read_packed(bits, p)
        if nbits is None:
            return blocks, start, "bad_nbits"
        p += nw
        if p + nbits > len(bits):
            return blocks, start, f"overflow nbits={nbits}"
        payload = bits[p : p + nbits]
        p += nbits
        blocks.append(
            {
                "hasRep": has_rep,
                "isActor": is_actor,
                "sub": sub,
                "stably": stably,
                "cls": cls,
                "clsPath": pm.guid_to_path.get(cls) if cls else None,
                "nbits": nbits,
                "payload": payload,
                "start": start,
            }
        )
    return blocks, p, "ok"


for include_class in (False, True):
    blocks, end, status = walk(include_class)
    rem = len(bits) - end
    print(
        f"\n=== include_class={include_class} status={status} "
        f"blocks={len(blocks)} end={end}/{len(bits)} rem={rem} ==="
    )
    for i, b in enumerate(blocks):
        print(
            f"  [{i}] hasRep={b['hasRep']} isActor={b['isActor']} sub={b['sub']} "
            f"stably={b['stably']} cls={b['cls']}({b['clsPath']}) nbits={b['nbits']}"
        )

# With include_class=True, try decoding each hasRep payload
blocks, end, status = walk(True)
print(f"\n=== decode payloads (include_class=True, rem={len(bits)-end}) ===")

# CAM layout for comparison; also try UWW3Attachment / hat class
for b in blocks:
    if not b["hasRep"] or not b["payload"]:
        continue
    pl = b["payload"]
    candidates = [
        "UWW3CharacterAttachmentManager",
        "UWW3AttachmentManager",
        "UWW3Attachment",
        "UActorComponent",
        "ABP_PlayerPawn_01_C",
        "AWW3Character",
    ]
    # find hat BP class
    for cn in classes:
        if "Hat_004" in cn or "KSK_NOJACKET" in cn or cn.endswith("Attachment_C"):
            if "CH_Hat" in cn or "KSK" in cn:
                candidates.append(cn)
    print(f"\n-- sub={b['sub']} cls={b['clsPath']} nbits={len(pl)} --")
    for leaf in candidates:
        if leaf not in classes and not leaf.startswith("A") and not leaf.startswith("U"):
            continue
        if leaf not in classes:
            # try A/U prefix variants already
            continue
        try:
            by_h, types = layout(leaf, classes, structs)
        except Exception:
            continue
        rdec = decode(pl, by_h, types, enums=enums)
        flag = "CLOSED" if rdec["closed"] else rdec["reason"]
        if rdec["closed"] or rdec["reason"] == "terminator" or len(rdec["seq"]) > 0:
            print(
                f"  {leaf}: {flag} left={rdec['left']} props={len(rdec['seq'])}"
            )
            for h, name, typ, w, note, p in rdec["seq"][:8]:
                print(f"    h{h} {name} w={w} {note}")
