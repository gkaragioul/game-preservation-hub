#!/usr/bin/env python3
"""Every `UWW3InventoryManager` subobject block in the whole captured stream.

`_im_preload_values.py` decodes the one block at src 212/213 and shows it carries
only `SvReplicatedInventory.ForceReplicationVar` (h22) -- the live client's
`SvReplicatedInventory` is zeroed in exactly the same way, so our replay of that
bunch is faithful and the real inventory must arrive somewhere else.

The `InventoryManager` and `WeaponsAttachments` sync bits are both downstream of
`UWW3InventoryManagerBase::OnRep_ReplicatedInventory`, whose guard requires
`FWW3ReplicatedInventory::IsValid(SvReplicatedInventory)` -- i.e. `BatchID != 0`
(h20) and all five slot states != `None` (h15..h19).  So the question this
answers is: **does the working server ever send h10..h20 for subobject 9384, and
in which bunch?**

`_decode_all_blocks.py` only decodes `isActor` blocks; this walks subobject
blocks, which is where a component like the inventory manager actually lives.

Usage:
    python match_server/_im_stream_scan.py
    python match_server/_im_stream_scan.py --sub 9384 --values
    python match_server/_im_stream_scan.py --handles 10,15,16,17,18,19,20
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import derive_rep_handles as D  # noqa: E402
from _decode_all_blocks import groups  # noqa: E402
from _decode_im_soft import decode_soft  # noqa: E402
from _decode_rep_block import layout  # noqa: E402
from actor_channel import Bits, read_content_blocks, read_new_actor  # noqa: E402
from netguid import GuidReader, PackageMap  # noqa: E402
from repblock import read_u  # noqa: E402

STREAM = os.path.join(HERE, "real_replay_stream.json")
IM_NETGUID = 9384
IM_CLASS = "UWW3InventoryManager"

# FWW3ReplicatedInventory, the struct FWW3ReplicatedInventory::IsValid checks.
SV_HANDLES = list(range(10, 23))
REQUIRED = {20: "BatchID != 0", 15: "PrimaryWeaponSlotState", 16: "SecondaryWeaponSlotState",
            17: "PrimaryGadgetSlotState", 18: "SecondaryGadgetSlotState",
            19: "AdditionalGadgetSlotState"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sub", type=int, default=IM_NETGUID)
    ap.add_argument("--values", action="store_true", help="print every property")
    ap.add_argument("--handles", default="",
                    help="only report blocks carrying at least one of these handles")
    ap.add_argument("--dump", default=os.environ.get("WW3_DUMPER7_DIR", str(D.DEFAULT_DUMP)))
    args = ap.parse_args()

    sdk = Path(args.dump)
    if sdk.name != "SDK":
        sdk = sdk / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)
    by_h, types = layout(IM_CLASS, classes, structs)
    want = {int(x) for x in args.handles.split(",") if x.strip()}

    stream = json.load(open(STREAM))
    found = 0
    sv_seen: dict[int, list[int]] = {}
    for ch, idxs in groups(stream):
        specs = [stream[i] for i in idxs]
        bits: list[int] = []
        for sp in specs:
            bits.extend(int(c) for c in sp["payload"])
        pm = PackageMap()
        pos = 0
        try:
            if specs[0].get("bHasPackageMapExports"):
                pos = pm.read_export_bunch(bits)["reader"].pos
            if specs[0].get("bOpen"):
                gr = GuidReader(bits, pos)
                hdr = read_new_actor(gr, pm)
                pos = gr.pos
                if hdr.get("incomplete"):
                    continue
            blocks = read_content_blocks(Bits(bits, pos), total_bits=len(bits))
        except Exception:
            continue

        for b in blocks:
            if b.get("isActor") or b.get("bad"):
                continue
            if b.get("subNetGUID") != args.sub or not b.get("hasRepLayout"):
                continue
            payload = b["payload"]
            res = decode_soft(payload, by_h, types, enums=enums)
            handles = [h for h, *_rest in res["seq"]]
            if want and not want.intersection(handles):
                continue
            found += 1
            sv = [h for h in handles if h in SV_HANDLES]
            for h in sv:
                sv_seen.setdefault(h, []).append(idxs[0])
            print(f"\nch{ch} srcs={idxs} sub={args.sub} bits={len(payload)} "
                  f"closed={res['closed']} reason={res['reason']} left={res['left']}")
            print(f"  handles: {handles}")
            if sv:
                print(f"  *** SvReplicatedInventory handles present: {sv} ***")
            if args.values:
                for h, name, typ, w, note, p in res["seq"]:
                    if note and note.startswith("soft"):
                        val = note
                    elif w <= 32:
                        val = str(read_u(payload, p, w))
                    else:
                        val = note or f"<{w} bits>"
                    print(f"    h{h:<3} {name:<56} w={w:<5} value={val}")

    print(f"\n=== {found} block(s) for subobject {args.sub} in the whole stream ===")
    print("SvReplicatedInventory handles ever sent by the working server:")
    for h in SV_HANDLES:
        srcs = sv_seen.get(h)
        tag = REQUIRED.get(h)
        mark = f"   <- required: {tag}" if tag else ""
        print(f"  h{h:<3} {by_h.get(h, '?'):<52} "
              f"{'srcs ' + str(srcs) if srcs else 'NEVER SENT'}{mark}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
