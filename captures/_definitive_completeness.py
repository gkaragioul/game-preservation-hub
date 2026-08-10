"""
DEFINITIVE workspace completeness audit.
Only report items the TEAM must still provide (live login required).
Do NOT list things we already have.
"""
import json, re, struct
from pathlib import Path
from collections import defaultdict, Counter

ROOT = Path(r'F:\Dev_Work\GameDev\WW3')
CAP = ROOT / 'captures'

# ───────── load API map catalog ─────────
rm = json.load(open(ROOT / 'mockserver' / 'replay_map.json', encoding='utf-8'))
body = rm['http']['GET /sharedData/maps/getAll']
if isinstance(body, dict) and 'body' in body:
    body = body['body']
if isinstance(body, str):
    body = json.loads(body)

def walk_maps(o):
    if isinstance(o, list) and o and isinstance(o[0], dict) and 'name' in o[0]:
        return o
    if isinstance(o, dict):
        for v in o.values():
            r = walk_maps(v)
            if r is not None:
                return r
    if isinstance(o, list):
        for x in o:
            r = walk_maps(x)
            if r is not None:
                return r
    return None

api_maps = walk_maps(body)
api_by_name = {}
for m in api_maps:
    gms = [g.get('gameMode') for g in m.get('gamemodes', [])]
    api_by_name[m['name']] = gms

# ───────── scan all pcaps for map id strings + quality ─────────
def scan_pcap_maps(path):
    """Return (has_786x_traffic, map_ids Counter, summary_markers Counter, size, dur_est)"""
    data = path.read_bytes()
    size = len(data)
    maps = Counter()
    markers = Counter()
    has_786 = False
    # fast binary scan for strings first
    for m in re.findall(rb'WW3_[A-Za-z0-9_]+_P', data):
        maps[m.decode()] += 1
    for needle in [b'SummaryScreen', b'Scoreboard', b'MatchResult', b'PlayerLevel']:
        c = data.count(needle)
        if c:
            markers[needle.decode()] = c
    # check for 786x in a sample of packets (pcapng)
    if data[:4] == b'\x0a\x0d\x0d\x0a':
        off = 0
        n = 0
        while off + 12 <= len(data) and n < 50000:
            bt, bl = struct.unpack('<II', data[off:off+8])
            if bl < 12 or off + bl > len(data):
                break
            if bt == 6 and bl >= 32:
                caplen = struct.unpack('<I', data[off+20:off+24])[0]
                pkt = data[off+28:off+28+min(caplen, 80)]
                if len(pkt) >= 42 and struct.unpack('>H', pkt[12:14])[0] == 0x0800 and pkt[23] == 17:
                    ihl = (pkt[14] & 0x0F) * 4
                    l4 = 14 + ihl
                    if len(pkt) >= l4 + 4:
                        sp, dp = struct.unpack('>HH', pkt[l4:l4+4])
                        if 7860 <= sp <= 7900 or 7860 <= dp <= 7900:
                            has_786 = True
                            break
                n += 1
            off += bl
    elif data[:4] in (b'\xd4\xc3\xb2\xa1', b'\xa1\xb2\xc3\xd4'):
        # classic - quick check size > 10MB as proxy for useful if named well
        has_786 = size > 20_000_000  # weak
    return has_786, maps, markers, size

print('Scanning all pcap/pcapng under captures (this takes a bit)...')
pcap_results = []
for f in sorted(CAP.rglob('*')):
    if f.suffix.lower() not in ('.pcap', '.pcapng'):
        continue
    if f.stat().st_size < 100_000:
        continue
    try:
        has_786, maps, markers, size = scan_pcap_maps(f)
    except Exception as e:
        print(' ERR', f, e)
        continue
    pcap_results.append({
        'path': str(f.relative_to(CAP)),
        'name': f.name,
        'size': size,
        'has_786': has_786,
        'maps': maps,
        'markers': markers,
    })

# Aggregate: which API maps have hard proof (string in pcap)?
proven = defaultdict(list)  # map_id -> [files]
summary_files = []
for r in pcap_results:
    for mid, cnt in r['maps'].items():
        if mid.startswith('WW3_') and mid.endswith('_P'):
            # skip sublevel noise? keep all, filter later
            proven[mid].append((r['path'], cnt, r['size']))
    if r['markers']:
        summary_files.append((r['path'], dict(r['markers']), r['size']))

print('\n' + '='*70)
print('A) MAP COVERAGE vs API CATALOG')
print('='*70)

# Map API names to human + how we verify
# Sub-maps like WW3_Moscow_63_* are streaming sublevels, not separate playable maps
PLAYABLE = [
    ('WW3_Shibuya_P', 'TDM', 'Shibuya'),
    ('WW3_Berlin_Backyards_02_P', 'TDM', 'Berlin Backyards'),
    ('WW3_Warsaw_Shopping_Mall_P', 'TDM', 'Warsaw Shopping Mall'),
    ('WW3_Moscow_Senate_P', 'TDM', 'Moscow Senate'),
    ('WW3_Landmark_P', 'TDM', 'Landmark'),
    ('WW3_Berlin_P', 'WAR', 'Berlin Warzone'),
    ('WW3_Moscow_P', 'WAR', 'Moscow Warzone'),
    ('WW3_Warsaw_P', 'WAR', 'Warsaw Warzone'),
    ('WW3_Polarnyj_P', 'WAR', 'Polyarny'),
    ('WW3_Smolensk_P', 'WAR', 'Smolensk'),
    ('WW3_DMZ_P', 'WAR/TacOps', 'DMZ'),
    ('WW3_Tokio_P', 'WAR/TacOps', 'Tokyo'),
    ('WW3_Gobi_New_P', 'DOM', 'Gobi Domination'),
]

# Filename heuristics for useful captures without string proof
def filename_suggests(mid, human, mode, fname):
    n = fname.lower()
    checks = {
        'WW3_Shibuya_P': 'shibuya' in n,
        'WW3_Berlin_Backyards_02_P': ('berlin' in n and 'tdm' in n) or 'backyard' in n,
        'WW3_Warsaw_Shopping_Mall_P': ('warsaw' in n or 'warszawa' in n) and ('tdm' in n or 'mall' in n or 'shopping' in n),
        'WW3_Moscow_Senate_P': ('moskow' in n or 'moscow' in n) and 'tdm' in n,
        'WW3_Landmark_P': 'landmark' in n,
        'WW3_Berlin_P': 'berlin' in n and ('war' in n or 'warzone' in n),
        'WW3_Moscow_P': ('moscow' in n or 'moskow' in n) and ('war' in n),
        'WW3_Warsaw_P': ('warsaw' in n or 'warszawa' in n) and ('war' in n),
        'WW3_Polarnyj_P': 'polar' in n or 'поляр' in n,
        'WW3_Smolensk_P': 'smolensk' in n or 'smolenck' in n,
        'WW3_DMZ_P': 'dmz' in n,
        'WW3_Tokio_P': 'tokyo' in n or 'tokio' in n,
        'WW3_Gobi_New_P': 'gobi' in n,
    }
    return checks.get(mid, False)

# Also stronghold / known useful large files
useful_by_name = []
for r in pcap_results:
    if r['size'] > 20_000_000 and (r['has_786'] or r['maps'] or r['size'] > 50_000_000):
        useful_by_name.append(r)

map_status = []
for mid, mode, human in PLAYABLE:
    hard = proven.get(mid, [])
    # filter hard proof to substantial counts or any
    hard_ok = [(p, c, s) for p, c, s in hard if c >= 1 and s > 5_000_000]
    fname_hits = [r for r in pcap_results if filename_suggests(mid, human, mode, r['name']) and r['size'] > 5_000_000]
    # exclude known junk loopback tiny senate
    fname_hits = [r for r in fname_hits if 'TDM_MoscowSenate' not in r['name'] or r['size'] > 10_000_000]

    if mid == 'WW3_Landmark_P':
        status = 'DROP'
        detail = 'Not queueable in live game (API leftover). Team cannot provide.'
    elif hard_ok:
        status = 'HAVE'
        detail = f'packet-proven in {hard_ok[0][0]} (x{hard_ok[0][1]})'
    elif mid == 'WW3_Moscow_Senate_P' and fname_hits:
        status = 'HAVE*'
        detail = f'API: only Moscow TDM map. Filename evidence: {fname_hits[0]["path"]} ({fname_hits[0]["size"]/1e6:.0f}MB). Not packet-proven (UDP/4500 wrap).'
    elif fname_hits:
        status = 'HAVE'
        detail = f'filename+size: {fname_hits[0]["path"]} ({fname_hits[0]["size"]/1e6:.0f}MB)'
    elif mid == 'WW3_Gobi_New_P':
        # check stronghold
        sh = [r for r in pcap_results if 'strong' in r['name'].lower() or 'stolong' in r['name'].lower()]
        if sh:
            status = 'UNCLEAR'
            detail = f'No Gobi-named capture. Stronghold exists ({sh[0]["path"]}) — may be related DOM, unproven.'
        else:
            status = 'MISSING'
            detail = 'No capture'
    else:
        status = 'MISSING'
        detail = 'No useful capture found'

    map_status.append((status, mode, human, mid, detail))
    print(f'  [{status:7}] {mode:10} {human:22} {detail}')

# ───────── menu HTTPS ─────────
print('\n' + '='*70)
print('B) MENU HTTPS (offline replay + all logs)')
print('='*70)

replay_keys = set(rm['http'].keys())
all_paths = set()
for d in [CAP, ROOT/'windows'/'record_logs', ROOT/'LOGS']:
    if not d.exists():
        continue
    for f in d.rglob('*'):
        if f.suffix.lower() not in ('.log', '.jsonl'):
            continue
        try:
            t = f.read_text(encoding='utf-8', errors='replace')
        except Exception:
            continue
        for m in re.finditer(r'\b(GET|POST|PUT|DELETE)\s+(/[^\s"\'\\]*)', t):
            method, path = m.group(1), m.group(2).split('?')[0]
            key = re.sub(r'/\d{5,}', '/{id}', path)
            key = re.sub(r'/7656119\d+', '/{steamid}', key)
            all_paths.add(f'{method} {key}')

menu_items = [
    ('Auth mint', [r'authenticate/fxgames'], 'offline'),
    ('Shop', [r'getShopItems'], 'have'),
    ('Career/Stats', [r'PlayerStatistics', r'/profileNew'], 'have'),
    ('Challenges', [r'/challenges'], 'have'),
    ('Friends', [r'/friends/'], 'have'),
    ('Season/BP', [r'/season/'], 'have'),
    ('Inventory', [r'/inventory/'], 'have'),
    ('Maps list', [r'maps/getAll'], 'have'),
    ('Game modes', [r'getGameModesParameters'], 'have'),
    ('XP after match (profile refresh)', [r'/profileNew'], 'have'),
    ('Leaderboards API', [r'leaderboard', r'/scores', r'getScores', r'ranking'], 'optional'),
    ('Notifications feed', [r'notif'], 'optional'),
]

for name, pats, kind in menu_items:
    in_replay = any(re.search(p, k, re.I) for k in replay_keys for p in pats)
    in_logs = any(re.search(p, k, re.I) for k in all_paths for p in pats)
    if in_replay or in_logs:
        print(f'  [HAVE   ] {name}')
    else:
        print(f'  [MISSING] {name}  ({kind})')

# ───────── match-end ─────────
print('\n' + '='*70)
print('C) MATCH-END')
print('='*70)
print(f'  UDP SummaryScreen/Scoreboard/MatchResult present in {len(summary_files)} captures:')
for p, m, s in sorted(summary_files, key=lambda x: -x[2])[:8]:
    print(f'    {p} ({s/1e6:.0f}MB) {m}')
# XP progression
aug3 = list((CAP/'3Aug27').glob('*meta*12-29-02*'))
if aug3:
    t = aug3[0].read_text(encoding='utf-8', errors='replace')
    exps = sorted(set(round(float(x), 2) for x in re.findall(r'"playerSeasonExperience"\s*:\s*([0-9.]+)', t)))
    print(f'  Client XP refresh after matches: HAVE (Aug3 XP values {exps})')
print('  DedicatedServer/matchSummary from client: NOT CAPTURABLE (server-side only)')

# ───────── FINAL ─────────
print('\n' + '='*70)
print('D) FINAL — WHAT TEAM MUST STILL PROVIDE')
print('='*70)

must = []
nice = []
for status, mode, human, mid, detail in map_status:
    if status == 'MISSING':
        must.append(f'{human} ({mode}) — {detail}')
    elif status == 'UNCLEAR':
        nice.append(f'{human} ({mode}) — {detail}')
    elif status == 'HAVE*':
        nice.append(f'{human} ({mode}) — already likely have; hard proof optional only — {detail}')

# leaderboards
lb = any(re.search(p, k, re.I) for k in all_paths for p in [r'leaderboard', r'getScores'])
if not lb:
    nice.append('Leaderboards API — never seen; may not exist as menu API; low value')

if not must:
    print('\n  *** NOTHING the team MUST provide. ***')
    print('  Core preservation data is complete for live-capturable items.')
else:
    print('\n  MUST:')
    for m in must:
        print(f'   - {m}')

if nice:
    print('\n  OPTIONAL (not required):')
    for m in nice:
        print(f'   - {m}')

print('\n  DO NOT ASK TEAM FOR:')
print('   - Smolensk (HAVE war_smolensk.pcapng, packet-proven)')
print('   - Landmark (not queueable)')
print('   - More random full matches / scoreboard (already in Tokyo Full 3 + others)')
print('   - Match-end HTTPS write (not capturable from client)')
print('   - Shop/Career/Challenges/etc (already in recorder logs + replay_map)')
print('   - Offline menu (works locally)')
