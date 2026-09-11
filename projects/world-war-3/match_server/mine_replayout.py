#!/usr/bin/env python3
r"""
mine_replayout.py -- mine per-class RepLayout property tables from the captures.

Pipeline:
  1. Walk a capture's server->client actor bunches.
  2. Track each actor channel's lifetime (open -> close) and learn the channel's CLASS from
     the archetype in its open bunch (SerializeNewActor). Payloads are attributed only while
     a channel's class is known, so a reused channel index can't pollute another class.
  3. Collect the RepLayout payloads of `bIsActor` content blocks.
  4. Solve each property's bit width: a payload is
         repeat{ packed Handle ; <width[Handle]> bits } ; packed 0
     Unknown handles are assumed final (width = remaining - 8) and the MINIMUM candidate is
     taken, since the minimum corresponds to observations where the handle really was last.
  5. Validate: re-parse every payload requiring ASCENDING handles and EXACT termination on
     the packed-0. Prune handles never exercised by a valid parse, then re-validate.

RESULT (2 captures, 43 classes, ~397k payloads):
  * Simple, fixed-width classes solve completely -- HVTMarkerComponent 100%,
    MovementComponent 98.5%.
  * Complex classes plateau near 60%. That plateau is the signature of VARIABLE-WIDTH
    properties (dynamic arrays, strings, conditionally-serialised struct members): no
    fixed-width table can represent them, so the remainder needs per-property TYPE
    knowledge rather than more samples.

Usage:  python mine_replayout.py [capture.pcapng ...]      -> writes replayout_table.json
"""
import sys, os, json, random, pickle, collections

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "match_analysis"))
from pcap_tools import parse_pcap
import control_channel as cc
from netguid import PackageMap, GuidReader
from actor_channel import Bits, bunch_bits, read_content_blocks, read_new_actor

MIN_PAYLOADS = 200
SAMPLE_CAP   = 20000
SOLVED_AT    = 90.0          # % validation to call a class solved


def collect(cap_path):
    """-> {class_path: [payload_bits, ...]}"""
    pk = parse_pcap(cap_path)
    peers = collections.Counter()
    for ts, src, sp, dst, dp, pl in pk:
        for ip, port in ((dst, dp), (src, sp)):
            if not ip.startswith(("192.168.", "10.", "127.")) and port > 1024:
                peers[(ip, port)] += 1
    if not peers: return {}
    (sip, sport), _ = peers.most_common(1)[0]
    flow = [("C->S" if dst == sip else "S->C", pl) for ts, src, sp, dst, dp, pl in pk
            if (dst == sip and dp == sport) or (src == sip and sp == sport)]
    pm = PackageMap(); ch_class = {}
    out = collections.defaultdict(list)
    for d, pl in flow:
        if d != "S->C" or not pl or (pl[0] & 1) == 1: continue
        try: q = cc.read_packet(pl)
        except Exception: continue
        for b in q.get("bunches", []):
            ch = b["chIndex"]
            if ch == 0: continue
            if b["bClose"]:
                ch_class.pop(ch, None); continue        # channel freed
            bits = bunch_bits(pl, b)
            if b["bOpen"]:
                ch_class.pop(ch, None)                  # a new actor takes this index
                try:
                    r = (pm.read_export_bunch(bits)["reader"] if b.get("bHasPackageMapExports")
                         else GuidReader(bits))
                    ap = read_new_actor(r, pm).get("archetypePath")
                    if ap: ch_class[ch] = ap
                except Exception: pass
                continue
            if b["bPartial"] or b.get("bHasPackageMapExports"): continue
            cls = ch_class.get(ch)
            if not cls: continue
            try: blocks = read_content_blocks(Bits(bits), b["bunchDataBits"])
            except Exception: continue
            for blk in blocks:
                if blk.get("isActor") and blk.get("hasRepLayout") and "payload" in blk:
                    if plausible(blk["payload"]):
                        out[cls].append(blk["payload"])
    return out


def _packed(bits, p):
    v = 0; c = 0; more = 1
    while more:
        if p + 8 > len(bits): return None, p
        x = 0
        for i in range(8): x |= bits[p + i] << i
        p += 8; more = x & 1; v += (x >> 1) << (7 * c); c += 1
    return v, p


MAX_HANDLE = 4096      # RepLayout handles are small property indices; anything larger means
                       # the payload isn't a RepLayout stream (or we mis-sized the bunch),
                       # so the sample is corrupt and must not train the table.

def plausible(bits):
    """Reject a payload whose first handle is impossible -- corrupt samples otherwise
    invent handles like 135548615 and poison the solved table."""
    h, _ = _packed(bits, 0)
    return h is not None and 0 < h <= MAX_HANDLE


def solve(payloads, rounds=8):
    widths = {}
    for _ in range(rounds):
        cand = collections.defaultdict(list)
        for bits in payloads:
            p = 0; prev = 0
            while True:
                h, p2 = _packed(bits, p)
                if h is None or h == 0: break
                if h <= prev: break                      # handles must ascend
                if h in widths:
                    prev = h; p = p2 + widths[h]
                    if p > len(bits): break
                    continue
                w = len(bits) - p2 - 8                   # assume final property
                if w >= 0: cand[h].append(w)
                break
        new = False
        for h, ws in cand.items():
            if h not in widths:
                widths[h] = min(ws); new = True
        if not new: break
    return widths


def validate(payloads, widths):
    ok = 0; used = collections.Counter()
    for bits in payloads:
        p = 0; prev = 0; seq = []; good = True
        while True:
            h, p2 = _packed(bits, p)
            if h is None: good = False; break
            if h == 0: good = (p2 == len(bits)); break   # must end EXACTLY
            if h <= prev or h > MAX_HANDLE or h not in widths: good = False; break
            prev = h; seq.append(h); p = p2 + widths[h]
            if p > len(bits): good = False; break
        if good:
            ok += 1
            for h in seq: used[h] += 1
    return ok, used


def mine(caps):
    random.seed(0)
    payloads = collections.defaultdict(list)
    for c in caps:
        print(f"[mine] {os.path.basename(c)}")
        for k, v in collect(c).items(): payloads[k].extend(v)
    table = {}; rows = []
    for cls, pls in sorted(payloads.items(), key=lambda x: -len(x[1])):
        if len(pls) < MIN_PAYLOADS: continue
        sample = pls if len(pls) <= SAMPLE_CAP else random.sample(pls, SAMPLE_CAP)
        w = solve(sample)
        _, used = validate(sample, w)
        w = {h: v for h, v in w.items() if used[h] > 0}      # prune unexercised handles
        ok, _ = validate(sample, w)
        rate = 100.0 * ok / len(sample)
        rows.append((rate, cls, len(pls), len(w)))
        table[cls] = {"validation_pct": round(rate, 1), "samples": len(pls),
                      "solved": rate >= SOLVED_AT,
                      "widths": {str(h): w[h] for h in sorted(w)}}
    rows.sort(reverse=True)
    return table, rows


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    caps = sys.argv[1:] or [
        os.path.join(here, "..", "captures", "24July26", "W3_match_full_2.pcapng"),
        os.path.join(here, "..", "captures", "24July26", "WW3_TacOps_Tokyo_Full_3.pcapng"),
    ]
    table, rows = mine(caps)
    print("\n=== per-class RepLayout validation ===")
    for rate, cls, n, nh in rows[:18]:
        print(f"  {rate:5.1f}%  samples={n:<7} handles={nh:<4} {cls[:44]}"
              f"{'   <-- SOLVED' if rate >= SOLVED_AT else ''}")
    out = os.path.join(here, "replayout_table.json")
    json.dump(table, open(out, "w"), indent=1)
    solved = [c for c, v in table.items() if v["solved"]]
    print(f"\n[mine] {len(table)} classes profiled, {len(solved)} solved >= {SOLVED_AT}%")
    for c in solved:
        print(f"    {c}: {table[c]['widths']}")
    print(f"[mine] wrote {out}")
