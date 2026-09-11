#!/usr/bin/env python3
"""Full clothing IM decode with SoftClassPtr = FSoftObjectPath NetSerialize."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import derive_rep_handles as D  # noqa: E402
from cam_im_resend import parse_clothing_content_blocks  # noqa: E402
from netguid import PackageMap  # noqa: E402
from repblock import (  # noqa: E402
    REP_BLOCK_PREFIX_BITS,
    read_fstring,
    read_packed,
    read_u,
    value_widths,
)
from _decode_rep_block import layout, read_array  # noqa: E402


def read_soft_object_path(bits, pos):
    """UE4 FSoftObjectPath::NetSerialize — path as FString (empty = 32 zero bits)."""
    got = read_fstring(bits, pos)
    if got is None:
        return None
    return got[0], got[1]


def value_widths_soft(name, typ, bits, pos, enums=None):
    if typ and ("TSoftClassPtr" in typ or "TSoftObjectPtr" in typ or typ in (
        "FSoftObjectPath", "FSoftClassPath",
    )):
        got = read_soft_object_path(bits, pos)
        if got:
            return [(got[1], f"soft {got[0]!r}")]
        return []
    return value_widths(name, typ, bits, pos, enums=enums)


def decode_soft(payload, by_h, types, enums=None):
    pos = REP_BLOCK_PREFIX_BITS
    seq = []
    last = 0
    n = len(payload)
    while True:
        h, hw = read_packed(payload, pos)
        if h is None:
            return {"closed": False, "reason": "eof_handle", "seq": seq, "left": n - pos, "pos": pos}
        pos += hw
        if h == 0:
            return {"closed": (n - pos) == 0, "reason": "terminator", "seq": seq, "left": n - pos, "pos": pos}
        if h <= last:
            return {"closed": False, "reason": f"non_ascending_{h}_after_{last}", "seq": seq, "left": n - pos, "pos": pos}
        name = by_h.get(h)
        if name is None:
            return {"closed": False, "reason": f"unknown_handle_{h}", "seq": seq, "left": n - pos, "pos": pos}
        typ = types.get(name)
        if name.endswith("[]"):
            # patch read_array to use soft widths for soft elems — rare here
            got = read_array(payload, pos, typ, enums)
            if got is None:
                return {"closed": False, "reason": f"bad_array_{h}_{name}", "seq": seq, "left": n - pos, "pos": pos}
            w, note = got
            seq.append((h, name, typ, w, note, pos))
            pos += w
            last = h
            continue
        cands = value_widths_soft(name, typ, payload, pos, enums=enums)
        if not cands:
            # dump next 64 bits for diagnosis
            head = "".join(str(x) for x in payload[pos:pos + 64])
            return {
                "closed": False,
                "reason": f"no_type_for_{h}_{name}({typ})",
                "seq": seq,
                "left": n - pos,
                "pos": pos,
                "head64": head,
            }
        w, note = cands[0]
        if pos + w > n:
            return {"closed": False, "reason": f"overrun_{h}_{name}", "seq": seq, "left": n - pos, "pos": pos}
        seq.append((h, name, typ, w, note, pos))
        pos += w
        last = h


def dump_array_objs(payload, pos, typ, enums):
    """Walk DynamicArray and print element object NetGUIDs."""
    num = read_u(payload, pos, 16)
    pos += 16
    elem = (typ or "")[len("TArray<"):-1] if (typ or "").startswith("TArray<") else None
    out = []
    while True:
        idx, iw = read_packed(payload, pos)
        pos += iw
        if idx == 0:
            break
        cands = value_widths("elem", elem, payload, pos, enums=enums)
        w, note = cands[0]
        out.append((idx, note, payload[pos:pos + w]))
        pos += w
    return out


def main() -> int:
    sdk = Path(str(D.DEFAULT_DUMP)) / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)

    stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
    bits = []
    for i in (212, 213):
        bits.extend(int(c) for c in stream[i]["payload"])
    res = PackageMap().read_export_bunch(bits)
    print("=== clothing exports ===")
    for e in res["exports"]:
        print(f"  guid={e['netguid']} outer={e['outer']} path={e.get('path')}")

    blocks = parse_clothing_content_blocks()
    print("\n=== clothing content ===")
    for b in blocks:
        print(
            f"  sub={b['subNetGUID']} stably={b['stablyNamed']} "
            f"cls={b['classNetGUID']} nbits={b['payloadBits']}"
        )

    # CAM attachment object refs
    cam = next(b for b in blocks if b["subNetGUID"] == 9374)
    bh_cam, ty_cam = layout("UWW3CharacterAttachmentManager", classes, structs)
    # find ReplicatedAttachments[] handle
    for h, name in sorted(bh_cam.items()):
        if "ReplicatedAttachments" in name or "AttachmentIds" in name or "BatchID" in name:
            print(f"  CAM h{h} {name} typ={ty_cam.get(name)}")

    from _decode_rep_block import decode
    rcam = decode(cam["payload"], bh_cam, ty_cam, enums=enums)
    print(f"\nCAM closed={rcam['closed']} props={len(rcam['seq'])}")
    for h, name, typ, w, note, p0 in rcam["seq"]:
        print(f"  h{h} {name} w={w} {note}")
        if "ReplicatedAttachments[]" in name:
            objs = dump_array_objs(cam["payload"], p0, typ, enums)
            for idx, note2, _bits in objs:
                print(f"    elem[{idx}] {note2}")
        if "AttachmentIds[]" in name and "Skins" not in name:
            # dump uint16 ids
            num = read_u(cam["payload"], p0, 16)
            pos = p0 + 16
            ids = []
            while True:
                idx, iw = read_packed(cam["payload"], pos)
                pos += iw
                if idx == 0:
                    break
                v = read_u(cam["payload"], pos, 16)
                ids.append(v)
                pos += 16
            print(f"    ids={ids}")

    im = next(b for b in blocks if b["subNetGUID"] == 9384)
    bh, ty = layout("UWW3InventoryManager", classes, structs)
    print("\n=== IM soft-aware decode ===")
    rim = decode_soft(im["payload"], bh, ty, enums=enums)
    print(f"closed={rim['closed']} reason={rim['reason']} left={rim['left']} pos={rim.get('pos')}")
    if rim.get("head64"):
        print(f"head64={rim['head64']}")
    for h, name, typ, w, note, p0 in rim["seq"]:
        print(f"  h{h} {name} w={w} {note}")

    # Also dump bits at SoftClassPtr position from standard stall
    # After SecondaryWeaponPreloadState — show next 96 bits
    pos = REP_BLOCK_PREFIX_BITS
    last = 0
    pl = im["payload"]
    while True:
        h, hw = read_packed(pl, pos)
        pos += hw
        if h == 0:
            break
        name = bh.get(h)
        typ = ty.get(name or "")
        if name and "PrimaryGadgetClass" in name:
            print(f"\nAt PrimaryGadgetClass pos={pos} next96=" + "".join(str(x) for x in pl[pos:pos + 96]))
            # try FString
            fs = read_fstring(pl, pos)
            print(f"  as FString: {fs}")
            # try bit + FString
            b = read_u(pl, pos, 1)
            fs2 = read_fstring(pl, pos + 1) if b is not None else None
            print(f"  as bit={b} + FString: {fs2}")
            # try packed netguid
            v, vw = read_packed(pl, pos)
            print(f"  as packed: v={v} w={vw}")
            break
        if name and name.endswith("[]"):
            got = read_array(pl, pos, typ, enums)
            if not got:
                break
            pos += got[0]
        else:
            cands = value_widths(name or "", typ, pl, pos, enums=enums)
            if not cands:
                # skip soft for this probe walk using soft
                cands = value_widths_soft(name or "", typ, pl, pos, enums=enums)
            if not cands:
                print(f"stall before soft at h{h} {name}")
                break
            pos += cands[0][0]
        last = h

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
