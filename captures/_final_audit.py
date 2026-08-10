import os, re, glob, json

ROOT = r'F:\Dev_Work\GameDev\WW3'
LOG_DIRS = [
    os.path.join(ROOT, 'captures'),
    os.path.join(ROOT, 'windows', 'record_logs'),
]

paths_seen = set()
for d in LOG_DIRS:
    for f in glob.glob(os.path.join(d, '**', '*'), recursive=True):
        if not os.path.isfile(f): continue
        if os.path.splitext(f)[1].lower() not in ('.log', '.jsonl', '.txt'): continue
        try:
            txt = open(f, encoding='utf-8', errors='replace').read()
        except Exception:
            continue
        for m in re.finditer(r'\b(GET|POST|PUT|DELETE|PATCH)\s+(/[^\s"\'\\]*)', txt):
            method, path = m.group(1), m.group(2).split('?')[0]
            key = re.sub(r'/\d{5,}', '/{id}', path)
            key = re.sub(r'/7656119\d+', '/{steamid}', key)
            paths_seen.add(f'{method} {key}')

checklist = {
    'Challenges (list)':            [r'/challenges'],
    'Leaderboards / Scores':        [r'leaderboard', r'/scores', r'getScores', r'ranking'],
    'Notifications (data feed)':    [r'notif'],
    'Career / Stats / Profile':     [r'PlayerStatistics', r'/profileNew', r'/progression'],
    'Shop':                         [r'getShopItems', r'/shop/'],
    'Battle Pass / Season':         [r'/season/'],
    'Friends':                      [r'/friends/'],
    'Loadout / Inventory':          [r'/inventory/', r'customConfigs', r'accountConfig'],
    'Match-end summary / XP write': [r'matchSummary', r'ClearMatch', r'match.*summary', r'/xp', r'gameSession'],
    'Auth':                         [r'authenticate/fxgames'],
    'Game modes / maps list':       [r'getGameModesParameters', r'maps/getAll'],
}

print('=== ENDPOINT COVERAGE (across ALL captured logs, all dates, all people) ===\n')
for name, pats in checklist.items():
    hits = [p for p in paths_seen if any(re.search(pat, p, re.I) for pat in pats)]
    status = 'COVERED' if hits else 'MISSING'
    print(f'[{status:7}] {name}')
    for h in sorted(hits)[:5]:
        print('           ', h)

print('\n=== all distinct request paths seen (for reference) ===')
for p in sorted(paths_seen):
    print(' ', p)

print('\n=== map/mode filenames seen across pcap + zip captures ===')
names = set()
for f in glob.glob(os.path.join(ROOT, 'captures', '**', '*'), recursive=True):
    if os.path.isfile(f) and os.path.splitext(f)[1].lower() in ('.pcap', '.pcapng', '.zip'):
        names.add(os.path.basename(f))
for n in sorted(names):
    print(' ', n)

print('\n=== any mention of "Landmark" anywhere in logs/docs ===')
for f in glob.glob(os.path.join(ROOT, '**', '*'), recursive=True):
    if not os.path.isfile(f): continue
    if os.path.splitext(f)[1].lower() not in ('.log', '.jsonl', '.txt', '.md', '.json'): continue
    try:
        txt = open(f, encoding='utf-8', errors='replace').read()
    except Exception:
        continue
    if 'Landmark' in txt or 'landmark' in txt:
        cnt = txt.lower().count('landmark')
        print(f'  {f}  (x{cnt})')
