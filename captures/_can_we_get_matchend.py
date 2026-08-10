"""Investigate: can we get match-end from existing captures / is it capturable?"""
import struct, re, json
from pathlib import Path
from collections import Counter, defaultdict

# --- helpers ---
def parse_pcapng_udp_payloads(path, want_ports=None):
    """Yield (ts, sport, dport, payload) for UDP packets."""
    data = Path(path).read_bytes()
    if data[:4] != b'\x0a\x0d\x0d\x0a':
        return
    off = 0
    linktypes = {}
    ts_resol = {}
    iface = 0
    while off + 12 <= len(data):
        bt, bl = struct.unpack('<II', data[off:off+8])
        if bl < 12 or off + bl > len(data):
            break
        block = data[off:off+bl]
        if bt == 1:
            lt = struct.unpack('<H', block[8:10])[0]
            iid = iface; iface += 1
            linktypes[iid] = lt
            resol = 1_000_000
            opts = block[16:-4]; i = 0
            while i + 4 <= len(opts):
                oc, ol = struct.unpack('<HH', opts[i:i+4])
                if oc == 0 and ol == 0: break
                if oc == 9 and ol >= 1:
                    v = opts[i+4]
                    resol = (2**(v&0x7f)) if (v&0x80) else (10**(v&0x7f))
                i += 4 + ol + ((4-ol%4)%4)
            ts_resol[iid] = resol
        elif bt == 6 and len(block) >= 32:
            iid, th, tl, caplen = struct.unpack('<IIII', block[8:24])
            resol = ts_resol.get(iid, 1_000_000)
            ts = ((th << 32) | tl) / float(resol)
            pkt = block[28:28+caplen]
            lt = linktypes.get(iid, 1)
            # ethernet ipv4 udp
            if lt == 1 and len(pkt) >= 42 and struct.unpack('>H', pkt[12:14])[0] == 0x0800 and pkt[23] == 17:
                ihl = (pkt[14] & 0x0F) * 4
                l4 = 14 + ihl
                sp, dp = struct.unpack('>HH', pkt[l4:l4+4])
                if want_ports and sp not in want_ports and dp not in want_ports:
                    pass
                else:
                    yield ts, sp, dp, pkt[l4+8:]
        off += bl

print('='*80)
print('1) SEARCH FULL MATCH PCAPS for end-of-match strings in UDP')
print('='*80)

NEEDLES = [
    b'scoreboard', b'Scoreboard', b'SCOREBOARD',
    b'matchSummary', b'MatchSummary',
    b'matchResult', b'MatchResult',
    b'endOfMatch', b'EndOfMatch', b'MatchEnd',
    b'Victory', b'Defeat', b'Winner',
    b'Experience', b'experience', b'LevelUp',
    b'WW3_', b'TDM_M', b'WAR_M',
]

files = [
    r'F:\Dev_Work\GameDev\WW3\captures\3Aug27\war_smolensk.pcapng',
    r'F:\Dev_Work\GameDev\WW3\captures\26July26\war_moscow.pcapng',
    r'F:\Dev_Work\GameDev\WW3\captures\24July26\W3_match_full_3.pcapng',
    r'F:\Dev_Work\GameDev\WW3\captures\31July26\SHIBUYA.pcapng',
    r'F:\Dev_Work\GameDev\WW3\captures\26July26\tdm_Warszawa.pcapng',
]

for fpath in files:
    p = Path(fpath)
    if not p.exists():
        print('missing', fpath); continue
    print(f'\n--- {p.name} ---')
    times = []
    hits = Counter()
    ww3 = Counter()
    # also track traffic in last 60s vs first 60s for volume drop (match end signal)
    all_ts = []
    last_payloads = []
    for ts, sp, dp, payload in parse_pcapng_udp_payloads(p):
        # only game-ish ports
        if not ((7860 <= sp <= 7900) or (7860 <= dp <= 7900) or (27000 <= sp <= 28000) or (27000 <= dp <= 28000)):
            # still scan all UDP for strings in case
            pass
        all_ts.append(ts)
        for n in NEEDLES:
            if n in payload:
                hits[n.decode('ascii','replace')] += 1
        for m in re.findall(rb'WW3_[A-Za-z0-9_]+_P', payload):
            ww3[m.decode()] += 1
        last_payloads.append((ts, payload))
        if len(last_payloads) > 5000:
            last_payloads = last_payloads[-5000:]

    if not all_ts:
        print('  no UDP parsed'); continue
    dur = max(all_ts) - min(all_ts)
    t0, t1 = min(all_ts), max(all_ts)
    early = sum(1 for t in all_ts if t < t0 + 60)
    late = sum(1 for t in all_ts if t > t1 - 60)
    print(f'  duration {dur/60:.1f} min, pkts {len(all_ts)}, early60s={early}, late60s={late}')
    print(f'  string hits: {dict(hits)}')
    print(f'  map ids: {dict(ww3)}')
    # scan last 90 seconds of payloads for printable strings of interest
    late_hits = Counter()
    late_strs = []
    for ts, payload in last_payloads:
        if ts < t1 - 90:
            continue
        for n in NEEDLES:
            if n in payload:
                late_hits[n.decode('ascii','replace')] += 1
        # extract readable ascii runs
        for m in re.findall(rb'[\x20-\x7e]{6,}', payload):
            s = m.decode('ascii')
            if re.search(r'(?i)score|match|xp|exp|level|victor|defeat|result|summary|end', s):
                late_strs.append(s[:120])
    print(f'  last-90s needle hits: {dict(late_hits)}')
    print(f'  last-90s interesting strings ({len(late_strs)}):')
    for s in late_strs[:15]:
        print('   ', s)

print('\n' + '='*80)
print('2) HUB: what happens AFTER LobbyMatchStarted (leave/end)?')
print('='*80)

hub_files = list(Path(r'F:\Dev_Work\GameDev\WW3').rglob('*hub*.log'))
hub_files += list(Path(r'F:\Dev_Work\GameDev\WW3').rglob('*_session*.log'))
seen_types = Counter()
post_match_examples = []
for f in hub_files:
    if f.stat().st_size > 50_000_000: continue
    try:
        t = f.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    if 'LobbyMatchStarted' not in t:
        continue
    print(f'\n  file: {f}')
    # find types after LobbyMatchStarted
    for m in re.finditer(r'LobbyMatchStarted', t):
        window = t[m.start(): m.start()+8000]
        types = re.findall(r'"type"\s*:\s*"([^"]+)"', window)
        print(f'    after LobbyMatchStarted, types seen: {types[:20]}')
        for tp in types:
            seen_types[tp] += 1
        # also method names
        methods = re.findall(r'"method"\s*:\s*"([^"]+)"', window)
        if methods:
            print(f'    methods: {methods[:15]}')

print('\n  aggregate types after match start:', dict(seen_types))

print('\n' + '='*80)
print('3) AUG3 SESSION: was menu recorder running DURING matches that granted XP?')
print('='*80)

meta = Path(r'F:\Dev_Work\GameDev\WW3\captures\3Aug27\WW3_rec_meta.prod.ww3.fxtools.gl_2026-08-03_12-29-02.log')
t = meta.read_text(encoding='utf-8', errors='replace')
# Extract timestamps of profileNew XP values and surrounding request timeline
print('Timeline of key events:')
# lines with timestamps like [12:29:02] or full datetime
# Our recorder format varies - look for ===== or [HH:MM:SS]
events = []
for m in re.finditer(r'\[(\d{2}:\d{2}:\d{2})\]\s*>>> (GET|POST|PUT) ([^\s]+)', t):
    events.append((m.group(1), m.group(2), m.group(3).split('?')[0], m.start()))
# Also XP at profileNew
for m in re.finditer(r'>>> GET (/profileNew/[^\s]+)', t):
    window = t[m.start():m.start()+4000]
    xp = re.search(r'"playerSeasonExperience"\s*:\s*([0-9.]+)', window)
    # find nearest timestamp before
    before = t[max(0,m.start()-500):m.start()]
    ts = re.findall(r'\[(\d{2}:\d{2}:\d{2})\]', before)
    events.append((ts[-1] if ts else '??', 'XP', xp.group(1) if xp else '?', m.start()))

# print sorted unique interesting
interesting = [e for e in events if any(x in e[2] for x in ['profileNew','playerData','gameSession','renewToken','shop','challenge']) or e[1]=='XP']
# dedupe nearby
print(f'  total HTTP events logged: {len(events)}')
print('  profile/XP related:')
for e in events:
    if e[1]=='XP' or 'profileNew' in str(e[2]) or 'playerData' in str(e[2]) or 'gameSession' in str(e[2]):
        print(f'    {e[0]}  {e[1]} {e[2]}')

# Gaps between profileNew pulls = time in match?
prof = [(e[0], float(e[2]) if e[1]=='XP' and e[2]!='?' else None, e[3]) for e in events if e[1]=='XP']
print('\n  XP observations:')
prev = None
for ts, xp, pos in prof:
    print(f'    time={ts} XP={xp}')
    prev = xp

print('\n' + '='*80)
print('4) Is DedicatedServer/matchSummary only server-side? Check docs + any capture')
print('='*80)
doc = Path(r'F:\Dev_Work\GameDev\WW3\docs\WW3_Preservation_Handoff.md')
if doc.exists():
    txt = doc.read_text(encoding='utf-8', errors='replace')
    for m in re.finditer(r'.{0,80}matchSummary.{0,120}', txt, re.I):
        print(' DOC:', re.sub(r'\s+',' ', m.group(0))[:200])
# any POST to DedicatedServer anywhere?
found_ds = False
for root in [Path(r'F:\Dev_Work\GameDev\WW3\captures'), Path(r'F:\Dev_Work\GameDev\WW3\LOGS'), Path(r'F:\Dev_Work\GameDev\WW3\windows\record_logs')]:
    for f in root.rglob('*.log'):
        try:
            tt = f.read_text(encoding='utf-8', errors='replace')
        except Exception:
            continue
        if 'DedicatedServer' in tt or 'ClearMatch' in tt:
            print(f' FOUND DedicatedServer/ClearMatch in {f}')
            for m in re.finditer(r'.{0,40}(DedicatedServer|ClearMatch).{0,80}', tt):
                print('  ', re.sub(r'\s+',' ', m.group(0))[:150])
                found_ds = True
                break
if not found_ds:
    print('  No DedicatedServer/* or ClearMatch in any client capture logs.')

print('\nDONE')
