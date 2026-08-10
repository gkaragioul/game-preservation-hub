#!/usr/bin/env python3
r"""Read the wire handles around UniqueId / PlayerNamePrivate in the PS blocks.

`_find_ps_strings.py` located the two FStrings in every captured PlayerState
property block (the unique-id string and the player name), and there is exactly
an 8-bit gap between them in all 13 samples -- i.e. a one-byte packed handle.
Reading that byte gives the wire handle of PlayerNamePrivate directly, with no
SDK flattening model assumed. The delta against `derive_rep_handles.py`'s guess
is then the exact command-count error in the AActor/APlayerState prefix.

  python match_server/_ps_anchor.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _find_ps_strings import scan, try_fstring  # noqa: E402
from _ps_blocks import playerstate_samples  # noqa: E402
from actor_channel import Bits  # noqa: E402


def packed_at(bits: list[int], pos: int):
    r = Bits(bits, pos)
    try:
        return r.packed(), r.pos - pos
    except EOFError:
        return None, 0


def bitstr(bits: list[int], a: int, b: int) -> str:
    return "".join(str(x) for x in bits[a:min(b, len(bits))])


def main() -> int:
    samples = playerstate_samples()
    print(f"{'ch':<6}{'guid':<7}{'bits':<6}{'uidPos':<8}{'uidEnd':<8}"
          f"{'gap':<5}{'H(name)':<9}{'nameEnd':<9}{'H(next)':<9} name")
    for s in samples:
        p = s["payload"]
        found = [f for f in scan(p) if len(f[1]) >= 3]
        if len(found) < 2:
            print(f"ch{s['chIndex']}: <2 strings")
            continue
        (upos, utext, ubits), (npos, ntext, nbits) = found[0], found[1]
        uend = upos + ubits
        gap = npos - uend
        h_name, hw = packed_at(p, uend) if gap > 0 else (None, 0)
        nend = npos + nbits
        h_next, _ = packed_at(p, nend)
        print(f"ch{s['chIndex']:<4}{s['netguid']:<7}{len(p):<6}{upos:<8}{uend:<8}"
              f"{gap:<5}{str(h_name):<9}{nend:<9}{str(h_next):<9} {ntext!r}")

    print("\n=== bits before the unique-id string (handle + FUniqueNetIdRepl prefix) ===")
    for s in samples:
        p = s["payload"]
        found = [f for f in scan(p) if len(f[1]) >= 3]
        if not found:
            continue
        upos = found[0][0]
        print(f"ch{s['chIndex']:<4} guid={s['netguid']:<6} uidPos={upos:<4} "
              f"head={bitstr(p, 0, 8)} pre[{max(0, upos - 40)}:{upos}]="
              f"{bitstr(p, max(0, upos - 40), upos)}")

    print("\n=== full walk attempt from the name handle backwards is not needed; "
          "forward-walk the tail instead ===")
    for s in samples:
        p = s["payload"]
        found = [f for f in scan(p) if len(f[1]) >= 3]
        if len(found) < 2:
            continue
        npos, ntext, nbits = found[1]
        pos = npos + nbits
        seq = []
        last = None
        while pos < len(p):
            h, hw = packed_at(p, pos)
            if h is None:
                break
            seq.append((pos, h, hw))
            break
        print(f"ch{s['chIndex']:<4} afterName pos={npos + nbits:<5} "
              f"next40={bitstr(p, npos + nbits, npos + nbits + 40)} "
              f"packed={seq[0][1] if seq else None}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
