import re, json
from pathlib import Path

f = Path(r'F:\Dev_Work\GameDev\WW3\captures\3Aug27\WW3_rec_meta.prod.ww3.fxtools.gl_2026-08-03_12-29-02.log')
t = f.read_text(encoding='utf-8', errors='replace')

# Find matchSummary and dump the following ~1500 chars
print('=== matchSummary blocks ===')
for i, m in enumerate(re.finditer(r'"matchSummary"\s*:\s*\{', t)):
    chunk = t[m.start(): m.start()+2000]
    # pretty-ish collapse whitespace but keep structure readable
    print(f'\n--- block {i} ---')
    print(chunk[:1800])
    print('...')

# Also search endpoint / hub for dedicated server match summary HTTP
for name in [
    'WW3_rec_endpoint.prod.wishlist.server.fxgam.es_2026-08-03_12-29-02.log',
    'WW3_rec__session_2026-08-03_12-29-02.log',
]:
    p = Path(r'F:\Dev_Work\GameDev\WW3\captures\3Aug27') / name
    tt = p.read_text(encoding='utf-8', errors='replace')
    print(f'\n=== paths in {name} mentioning match/Dedicated/summary ===')
    for m in re.finditer(r'(GET|POST|PUT|DELETE)\s+/[^\s"]+', tt):
        line = m.group(0)
        if re.search(r'match|summary|Dedicated|xp|score|Clear', line, re.I):
            print(' ', line)

# Confirm Smolensk / Senate appear as selected maps in custom lobby configs (S2 field)
print('\n=== "S2" map votes/selections counts ===')
for key in ['S2', 'S1', 'map', 'maps']:
    pass
c = __import__('collections').Counter(re.findall(r'"S2"\s*:\s*"(WW3_[^"]+)"', t))
print('S2 selections:', c)
c1 = __import__('collections').Counter(re.findall(r'"S1"\s*:\s*"(WW3_[^"]+)"', t))
print('S1 selections:', c1)

# Look for actual played map in LobbyChange / server handoff style objects
print('\n=== address/gamePort/map co-occurrence samples ===')
for pat in [r'"address"\s*:\s*"[^"]+".{0,300}', r'"serverId"\s*:\s*\d+.{0,300}']:
    shown = 0
    for m in re.finditer(pat, t):
        s = re.sub(r'\s+', ' ', m.group(0))
        if 'WW3_' in s or 'gamePort' in s:
            print(s[:300])
            shown += 1
        if shown >= 5:
            break
