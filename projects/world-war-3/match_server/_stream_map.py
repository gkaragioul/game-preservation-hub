#!/usr/bin/env python3
"""Read-only: map real_replay_stream.json by channel, marking what the ownership
bootstrap already sends and what it leaves behind. Used to decide how far past the
curated slice the replay must run to satisfy the client's sync checklist."""
import collections
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
s = json.load(open(os.path.join(HERE, "real_replay_stream.json")))

OWNED_RANGES = [(0, 1), (20, 21), (2, 17), (9, 9), (181, 181), (192, 192),
                (212, 213), (119, 121), (215, 215), (275, 275)]
owned = set()
for a, b in OWNED_RANGES:
    owned.update(range(a, b + 1))

print("total bunches", len(s))
print("keys", sorted(s[0].keys()))
print("channels overall:", dict(sorted(collections.Counter(x["chIndex"] for x in s).items())))
rest = [(i, x) for i, x in enumerate(s) if i not in owned]
print("not-sent count", len(rest))
print("channels not sent:", dict(sorted(collections.Counter(x["chIndex"] for _, x in rest).items())))
print()
print("--- every un-sent bunch on an ownership channel (2/3/4/5/7/53) ---")
for i, x in rest:
    if x["chIndex"] not in (2, 3, 4, 5, 7, 53):
        continue
    print("  i=%4d ch=%3d bits=%6d open=%s part=%s/%s/%s exp=%s"
          % (i, x["chIndex"], x["bits"], x.get("bOpen"), x.get("bPartial"),
             x.get("bPartialInitial"), x.get("bPartialFinal"),
             x.get("bHasPackageMapExports")))
print()
print("--- channel opens in the whole stream ---")
for i, x in enumerate(s):
    if x.get("bOpen"):
        print("  i=%4d ch=%3d bits=%6d exp=%s" % (i, x["chIndex"], x["bits"],
                                                  x.get("bHasPackageMapExports")))
