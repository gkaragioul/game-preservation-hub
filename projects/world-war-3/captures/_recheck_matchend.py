"""Exhaustive search: do we already have match-end scoreboard/XP HTTPS?"""
import re
from pathlib import Path
from collections import defaultdict, Counter

ROOTS = [
    Path(r'F:\Dev_Work\GameDev\WW3\captures'),
    Path(r'F:\Dev_Work\GameDev\WW3\windows\record_logs'),
    Path(r'F:\Dev_Work\GameDev\WW3\LOGS'),
]

# Patterns that would indicate real match-end protocol
NEEDLES = [
    r'matchSummary',
    r'MatchSummary',
    r'ClearMatch',
    r'clearMatch',
    r'/xp\b',
    r'addExperience',
    r'grantExperience',
    r'playerSeasonExperience',
    r'scoreboard',
    r'Scoreboard',
    r'endOfMatch',
    r'EndOfMatch',
    r'matchResult',
    r'MatchResult',
    r'DedicatedServer/match',
    r'/server/match',
    r'postMatch',
    r'PostMatch',
    r'matchRewards',
    r'MatchRewards',
    r'levelUp',
    r'LevelUp',
    r'lobbyToken',
    r'LobbyMatchStarted',
    r'LobbyMatchEnded',
    r'MatchEnded',
    r'matchEnded',
]

http_hits = defaultdict(list)  # path -> [files]
text_hits = defaultdict(Counter)  # needle -> file -> count
interesting_paths = Counter()

files_scanned = 0
for root in ROOTS:
    if not root.exists():
        continue
    for f in root.rglob('*'):
        if not f.is_file():
            continue
        if f.suffix.lower() not in ('.log', '.jsonl', '.txt'):
            continue
        if f.stat().st_size > 80_000_000:
            continue
        try:
            t = f.read_text(encoding='utf-8', errors='replace')
        except Exception:
            continue
        files_scanned += 1
        rel = str(f)

        for needle in NEEDLES:
            cnt = len(re.findall(needle, t))
            if cnt:
                text_hits[needle][rel] += cnt

        for m in re.finditer(r'(>>>|<<<)\s*(GET|POST|PUT|DELETE)\s+([^\s]+)', t):
            direction, method, path = m.group(1), m.group(2), m.group(3).split('?')[0]
            key = f'{method} {path}'
            interesting_paths[key] += 1
            if re.search(r'match|summary|xp|score|reward|experience|clear|end|level', key, re.I):
                http_hits[key].append(rel)

print(f'Files scanned: {files_scanned}\n')

print('=== A) TEXT NEEDLE HITS (across all logs) ===')
for needle in NEEDLES:
    files = text_hits.get(needle, {})
    total = sum(files.values())
    if total == 0:
        continue
    print(f'\n{needle}: {total} hits in {len(files)} files')
    for path, cnt in sorted(files.items(), key=lambda x: -x[1])[:5]:
        short = path.replace(r'F:\Dev_Work\GameDev\WW3\\', '')
        print(f'  {cnt:5d}  {short}')

print('\n=== B) HTTP PATHS that look match/xp/score related ===')
if not http_hits:
    print('  (none)')
else:
    for path, files in sorted(http_hits.items()):
        uniq = sorted(set(files))
        print(f'\n  {path}  ({len(files)} times, {len(uniq)} files)')
        for u in uniq[:4]:
            print(f'    {u.replace(r"F:\\Dev_Work\\GameDev\\WW3\\", "")}')

print('\n=== C) Classify matchSummary occurrences ===')
# Is matchSummary an HTTP endpoint or a JSON field inside playerData?
for root in ROOTS:
    if not root.exists():
        continue
    for f in root.rglob('*'):
        if f.suffix.lower() not in ('.log', '.jsonl'):
            continue
        try:
            t = f.read_text(encoding='utf-8', errors='replace')
        except Exception:
            continue
        if 'matchSummary' not in t:
            continue
        # find contexts: is it after >>> POST something?
        for m in re.finditer(r'matchSummary', t):
            window_before = t[max(0, m.start()-1500):m.start()]
            window_after = t[m.start():m.start()+200]
            reqs = list(re.finditer(r'>>> (GET|POST|PUT|DELETE) ([^\s]+)', window_before))
            last_req = reqs[-1].group(0) if reqs else 'NO_HTTP_REQ_FOUND'
            # only print unique classifications
            break
        # count by preceding request
        by_req = Counter()
        for m in re.finditer(r'matchSummary', t):
            window_before = t[max(0, m.start()-2000):m.start()]
            reqs = list(re.finditer(r'>>> (GET|POST|PUT|DELETE) ([^\s]+)', window_before))
            last_req = reqs[-1].group(0) if reqs else '(embedded, no preceding >>>)'
            by_req[last_req] += 1
        if by_req:
            print(f'\n  {f.name}:')
            for k, v in by_req.most_common():
                print(f'    {v:3d}x after {k}')

print('\n=== D) XP field changes evidence (playerSeasonExperience unique values per file) ===')
for root in [Path(r'F:\Dev_Work\GameDev\WW3\captures\3Aug27')]:
    for f in root.glob('*meta*12-29-02*'):
        t = f.read_text(encoding='utf-8', errors='replace')
        exps = [float(x) for x in re.findall(r'"playerSeasonExperience"\s*:\s*([0-9.]+)', t)]
        print(f'  {f.name}: unique XP = {sorted(set(round(x,2) for x in exps))}')

print('\n=== E) BOTTOM LINE CHECKLIST ===')
print('''
HAVE already:
  - playerSeasonExperience rising inside GET /playerData (or similar profile pulls)
  - matchSummary JSON *field* inside those profile responses (often zeros)
  - long UDP match captures

STILL NEED if missing:
  - a dedicated match-end HTTP request (POST/PUT to something like matchSummary/ClearMatch/rewards)
  - OR hub RPC explicitly ending match with scoreboard payload
''')
