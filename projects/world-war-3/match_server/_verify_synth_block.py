#!/usr/bin/env python3
r"""Round-trip the synthesised property blocks through the validated decoder.

Encoding a block is only safe if the same decoder that exact-consumes 1056 captured
blocks also exact-consumes ours and reads back the values we meant. This also
byte-compares `build_pc_set_pawn_bits()` against the capture's own PC::Pawn block.

  python match_server/_verify_synth_block.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import derive_rep_handles as D  # noqa: E402
from _decode_rep_block import decode, layout  # noqa: E402
from actor_channel import Bits, read_content_blocks  # noqa: E402
from possess_rpc import (PAWN_NETGUID, PC_NETGUID, PS_NETGUID,  # noqa: E402
                         build_pawn_bind_props_bits, build_pc_set_pawn_bits)


def main() -> int:
    sdk = Path(os.environ.get("WW3_DUMPER7_DIR", str(D.DEFAULT_DUMP)))
    if sdk.name != "SDK":
        sdk = sdk / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)

    stream = json.loads(Path(HERE, "real_replay_stream.json").read_text(encoding="utf-8"))
    cap = read_content_blocks(Bits([int(c) for c in stream[13]["payload"]]))[0]

    rc = 0

    print("=== PC::Pawn block vs capture src=13 ===")
    ours = read_content_blocks(Bits(build_pc_set_pawn_bits()))[0]
    same = ours["payload"][:25] == list(cap["payload"][:25])
    print(f"  first 25 payload bits identical to capture: {same}")
    print(f"  ours  : {''.join(str(b) for b in ours['payload'])}")
    print(f"  capture: {''.join(str(b) for b in cap['payload'][:33])} ...")
    rc |= 0 if same else 1

    by_h, types = layout("ABP_WW3_DominationPlayerController_01_C", classes, structs)
    r = decode(ours["payload"], by_h, types, enums=enums)
    print(f"  decode: closed={r['closed']} left={r['left']}")
    for h, name, typ, w, note, p in r["seq"]:
        print(f"     h{h:<4} {name:<24} {note}")
    rc |= 0 if (r["closed"] and r["seq"] and r["seq"][0][4].endswith(str(PAWN_NETGUID))) else 1

    print("\n=== synthesised pawn bind block (APawn::PlayerState + Controller) ===")
    pb = read_content_blocks(Bits(build_pawn_bind_props_bits()))[0]
    by_h, types = layout("ABP_PlayerPawn_01_C", classes, structs)
    r = decode(pb["payload"], by_h, types, enums=enums)
    print(f"  payloadBits={len(pb['payload'])}  closed={r['closed']} left={r['left']}")
    print(f"  bits: {''.join(str(b) for b in pb['payload'])}")
    got = {}
    for h, name, typ, w, note, p in r["seq"]:
        print(f"     h{h:<4} {name:<24} {typ:<16} w={w:<4} {note}")
        got[name] = note
    ok = (r["closed"]
          and got.get("PlayerState", "").endswith(str(PS_NETGUID))
          and got.get("Controller", "").endswith(str(PC_NETGUID)))
    print(f"  round-trip OK: {ok}")
    rc |= 0 if ok else 1

    print("\n=== synthesised PS reverse bind (PlayerCharacter -> 9372) ===")
    from possess_rpc import build_ps_set_playerchar_bits
    psb = read_content_blocks(Bits(build_ps_set_playerchar_bits()))[0]
    by_h, types = layout("ABP_WW3DominationPlayerState_C", classes, structs)
    r = decode(psb["payload"], by_h, types, enums=enums)
    print(f"  payloadBits={len(psb['payload'])}  closed={r['closed']} left={r['left']}")
    got = {}
    for h, name, typ, w, note, p in r["seq"]:
        print(f"     h{h:<4} {name:<24} {typ:<16} w={w:<4} {note}")
        got[name] = note
    ok = (r["closed"]
          and got.get("PlayerCharacter", "").endswith(str(PAWN_NETGUID)))
    print(f"  round-trip OK: {ok}")
    rc |= 0 if ok else 1

    print("\nRESULT:", "PASS" if rc == 0 else "FAIL")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
