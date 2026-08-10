#!/usr/bin/env python3
r"""Decode captured RepLayout property blocks with the bDoChecksum fix.

Supersedes `_decode_ch7_open.py`, which read the payload from bit 0 and so
could never close. Scores exactly the way NEXT_EXPERIMENT.md asked for --
leaf x atomic-struct model, accept only models that end on handle 0 with 0 bits
left -- but now over *all* captured blocks of a class, not just the one ch7
sample.

  python match_server/_decode_rep_block.py                    # PlayerState x13
  python match_server/_decode_rep_block.py --which pc         # PlayerController
  python match_server/_decode_rep_block.py --which pc --verbose
  python match_server/_decode_rep_block.py --score            # brute atomic sets
"""
from __future__ import annotations

import argparse
import itertools
import os
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import derive_rep_handles as D  # noqa: E402
from _ps_blocks import group_opens, load_stream, parse_open  # noqa: E402
from repblock import REP_BLOCK_PREFIX_BITS, read_packed, value_widths  # noqa: E402

AMBIGUOUS = ["FVector", "FRotator", "FRepMovement", "FVector_NetQuantize100",
             "FVector_NetQuantize", "FQuat", "FRepAttachment"]
ALWAYS_ATOMIC = {"FUniqueNetIdRepl", "FGameplayTag", "FGameplayTagContainer"}


def layout(leaf, classes, structs):
    """-> (handle -> cmd name, cmd name -> declared type)."""
    typed = D.build_typed(leaf, classes, structs)
    return ({h: n for h, _c, n, _t in typed},
            {n: t for _h, _c, n, t in typed})


def read_array(payload, pos, typ, enums):
    """Consume one REPCMD_DynamicArray value. -> (width, note) or None."""
    from repblock import read_u

    start = pos
    num = read_u(payload, pos, 16)
    if num is None:
        return None
    pos += 16
    elem = (typ or "")[len("TArray<"):-1] if (typ or "").startswith("TArray<") else None
    seen = 0
    while True:
        idx, iw = read_packed(payload, pos)
        if idx is None:
            return None
        pos += iw
        if idx == 0:
            return pos - start, f"array<{elem}> num={num} sent={seen}"
        if idx > max(num, 1) + 1 or seen > 4096:
            return None
        cands = value_widths(f"elem{idx}", elem, payload, pos, enums=enums)
        if not cands:
            return None
        pos += cands[0][0]
        if pos > len(payload):
            return None
        seen += 1


def decode(payload, by_h, types, enums=None, max_left=0):
    """Walk one property block. -> dict(closed, seq, left, reason)."""
    pos = REP_BLOCK_PREFIX_BITS
    seq = []
    last = 0
    n = len(payload)
    while True:
        h, hw = read_packed(payload, pos)
        if h is None:
            return {"closed": False, "reason": "eof_handle", "seq": seq, "left": n - pos}
        pos += hw
        if h == 0:
            return {"closed": (n - pos) <= max_left, "reason": "terminator",
                    "seq": seq, "left": n - pos}
        if h <= last:
            return {"closed": False, "reason": f"non_ascending_{h}_after_{last}",
                    "seq": seq, "left": n - pos}
        name = by_h.get(h)
        if name is None:
            return {"closed": False, "reason": f"unknown_handle_{h}",
                    "seq": seq, "left": n - pos}
        typ = types.get(name)
        if name.endswith("[]"):
            # REPCMD_DynamicArray: uint16 ArrayNum, then a nested handle stream
            # (element command indices) terminated by its own packed 0.
            got = read_array(payload, pos, typ, enums)
            if got is None:
                return {"closed": False, "reason": f"bad_array_{h}_{name}",
                        "seq": seq, "left": n - pos, "pos": pos}
            w, note = got
            seq.append((h, name, typ, w, note, pos))
            pos += w
            last = h
            continue
        cands = value_widths(name, typ, payload, pos, enums=enums)
        if not cands:
            return {"closed": False, "reason": f"no_type_for_{h}_{name}({typ})",
                    "seq": seq, "left": n - pos, "pos": pos}
        w, note = cands[0]
        if pos + w > n:
            return {"closed": False, "reason": f"overrun_{h}_{name}",
                    "seq": seq, "left": n - pos}
        seq.append((h, name, typ, w, note, pos))
        pos += w
        last = h


def blocks_for(arch_substr, leaf_hint=None):
    """-> [(label, payload)] for every captured open whose archetype matches."""
    stream = load_stream()
    out = []
    for _first, idxs in group_opens(stream):
        try:
            g = parse_open(stream, idxs)
        except Exception:
            continue
        arch = g["header"].get("archetypePath") or ""
        if arch_substr.lower() not in arch.lower():
            continue
        blk = next((b for b in g["blocks"]
                    if b.get("isActor") and b.get("hasRepLayout") and not b.get("bad")), None)
        if blk is None:
            continue
        out.append((f"ch{g['chIndex']}/guid{g['header'].get('netguid')}", blk["payload"]))
    return out


TARGETS = {
    "ps": ("PlayerState", "AWW3DominationPlayerState"),
    "pc": ("DominationPlayerController", "AWW3DominationPlayerController"),
    "pawn": ("PlayerPawn", "AWW3Character"),
    "char": ("WW3DistanceRelevantCharacter", "AWW3DistanceRelevantCharacter"),
}


def run(leaf, samples, classes, structs, enums, verbose=False):
    by_h, types = layout(leaf, classes, structs)
    ok = 0
    for label, payload in samples:
        r = decode(payload, by_h, types, enums=enums)
        if r["closed"]:
            ok += 1
        if verbose:
            print(f"\n--- {label}  bits={len(payload)}  "
                  f"{'CLOSED' if r['closed'] else 'FAIL: ' + r['reason']}  left={r['left']}")
            for h, name, typ, w, note, pos in r["seq"]:
                print(f"   @{pos:<5} h{h:<4} {name:<44} {str(typ):<20} w={w:<5} {note}")
        elif not r["closed"]:
            print(f"   {label}: {r['reason']} (left={r['left']}, "
                  f"{len(r['seq'])} props read)")
    return ok, len(samples)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", default="ps", choices=sorted(TARGETS))
    ap.add_argument("--leaf", default=None)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--score", action="store_true",
                    help="brute-force the ambiguous atomic-struct set")
    ap.add_argument("--dump", default=os.environ.get("WW3_DUMPER7_DIR", str(D.DEFAULT_DUMP)))
    args = ap.parse_args()

    sdk = Path(args.dump)
    if sdk.name != "SDK":
        sdk = sdk / "CppSDK" / "SDK"
    classes, structs = D.parse_sdk(sdk)
    enums = D.parse_enums(sdk)

    arch, default_leaf = TARGETS[args.which]
    leaf = args.leaf or default_leaf
    samples = blocks_for(arch)
    print(f"target={args.which} archetype~{arch!r} leaf={leaf} samples={len(samples)}")
    if not samples:
        print("no samples")
        return 2

    if args.score:
        print("\natomic-struct set -> blocks exact-consumed")
        best = []
        for r in range(len(AMBIGUOUS) + 1):
            for atomic in itertools.combinations(AMBIGUOUS, r):
                D.NET_SERIALIZE_STRUCTS.clear()
                D.NET_SERIALIZE_STRUCTS.update(ALWAYS_ATOMIC)
                D.NET_SERIALIZE_STRUCTS.update(atomic)
                by_h, types = layout(leaf, classes, structs)
                ok = sum(1 for _l, p in samples
                         if decode(p, by_h, types, enums=enums)["closed"])
                best.append((ok, atomic))
        best.sort(key=lambda x: -x[0])
        for ok, atomic in best[:12]:
            tag = ",".join(atomic) or "(none)"
            mark = "   <== EXACT ON ALL" if ok == len(samples) else ""
            print(f"  {ok:>3}/{len(samples)}  {{{tag}}}{mark}")
        return 0

    ok, n = run(leaf, samples, classes, structs, enums, verbose=args.verbose)
    print(f"\nexact-consumed {ok}/{n} blocks")
    return 0 if ok == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
