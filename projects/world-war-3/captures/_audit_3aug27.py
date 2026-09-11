"""Deep audit of captures/3Aug27 — quality + menu coverage."""
import struct, re, json
from pathlib import Path
from collections import Counter

ROOT = Path(r'F:\Dev_Work\GameDev\WW3\captures\3Aug27')
NOISE_UDP = {53, 123, 137, 138, 139, 1900, 5353, 5355, 67, 68, 443, 80, 3478, 19302, 4500, 6881}

def parse_pcapng(path):
    data = path.read_bytes()
    if data[:4] != b'\x0a\x0d\x0d\x0a':
        return None, None
    off = 0
    pkts = []
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
            iid = iface
            iface += 1
            linktypes[iid] = lt
            resol = 1_000_000
            opts = block[16:-4]
            i = 0
            while i + 4 <= len(opts):
                oc, ol = struct.unpack('<HH', opts[i:i+4])
                if oc == 0 and ol == 0:
                    break
                if oc == 9 and ol >= 1:
                    v = opts[i+4]
                    resol = (2 ** (v & 0x7f)) if (v & 0x80) else (10 ** (v & 0x7f))
                i += 4 + ol + ((4 - ol % 4) % 4)
            ts_resol[iid] = resol
        elif bt == 6 and len(block) >= 32:
            iid, th, tl, caplen = struct.unpack('<IIII', block[8:24])
            resol = ts_resol.get(iid, 1_000_000)
            ts = ((th << 32) | tl) / float(resol)
            pkt = block[28:28+caplen]
            pkts.append((ts, pkt, linktypes.get(iid, 1)))
        off += bl
    return pkts, linktypes

def parse_pcap(path):
    data = path.read_bytes()
    magic = data[:4]
    if magic == b'\xd4\xc3\xb2\xa1':
        le = True
    elif magic == b'\xa1\xb2\xc3\xd4':
        le = False
    else:
        return None, None
    end = '<' if le else '>'
    _, _, _, _, _, _, linktype = struct.unpack(end + 'IHHIIII', data[:24])
    off = 24
    pkts = []
    while off + 16 <= len(data):
        ts_sec, ts_usec, caplen, _ = struct.unpack(end + 'IIII', data[off:off+16])
        off += 16
        if off + caplen > len(data):
            break
        pkt = data[off:off+caplen]
        off += caplen
        pkts.append((ts_sec + ts_usec / 1e6, pkt, linktype))
    return pkts, {0: linktype}

def classify(pkt, lt):
    cands = []
    if lt == 0 and len(pkt) >= 24:
        cands.append(4)  # null/loopback
    if len(pkt) >= 34 and struct.unpack('>H', pkt[12:14])[0] == 0x0800:
        cands.append(14)
    if len(pkt) >= 20 and (pkt[0] >> 4) == 4:
        cands.append(0)
    for off in cands:
        if len(pkt) < off + 20 or (pkt[off] >> 4) != 4:
            continue
        ihl = (pkt[off] & 0x0F) * 4
        proto = pkt[off + 9]
        l4 = off + ihl
        if len(pkt) < l4 + 4:
            continue
        sp, dp = struct.unpack('>HH', pkt[l4:l4+4])
        if proto == 17:
            return 'UDP', sp, dp
        if proto == 6:
            return 'TCP', sp, dp
    return None, 0, 0

def analyze_cap(path):
    if path.suffix.lower() == '.pcapng':
        pkts, lts = parse_pcapng(path)
    else:
        pkts, lts = parse_pcap(path)
    if not pkts:
        return {'error': 'empty/unreadable'}
    times = [t for t, _, _ in pkts if t is not None]
    dur = (max(times) - min(times)) if times else 0
    proto = Counter()
    ports = Counter()
    game_udp = 0
    match_ports = 0
    for ts, pkt, lt in pkts:
        kind, sp, dp = classify(pkt, lt)
        if not kind:
            proto['OTHER'] += 1
            continue
        proto[kind] += 1
        ports[sp] += 1
        ports[dp] += 1
        if kind == 'UDP':
            if sp not in NOISE_UDP and dp not in NOISE_UDP:
                game_udp += 1
            if (7860 <= sp <= 7900) or (7860 <= dp <= 7900) or (27000 <= sp <= 28000) or (27000 <= dp <= 28000):
                match_ports += 1
    # also count UDP excluding only DNS/mDNS etc but including 4500 (common in these captures)
    udp_any = proto.get('UDP', 0)
    if game_udp > 500 and dur >= 60:
        verdict = 'USEFUL match UDP'
    elif udp_any > 1000 and dur >= 60:
        verdict = 'LIKELY useful (UDP heavy)'
    elif proto.get('TCP', 0) > udp_any * 5 and 443 in ports:
        verdict = 'JUNK (TCP 443 filter)'
    elif lts and list(lts.values()) == [0] and proto.get('TCP', 0) > udp_any:
        verdict = 'JUNK (loopback)'
    else:
        verdict = 'THIN / unclear'
    return {
        'pkts': len(pkts),
        'dur_min': dur / 60,
        'udp': proto.get('UDP', 0),
        'tcp': proto.get('TCP', 0),
        'other': proto.get('OTHER', 0),
        'game_udp': game_udp,
        'match_port_hits': match_ports,
        'top_ports': ports.most_common(8),
        'linktypes': lts,
        'verdict': verdict,
    }

print('=' * 90)
print('PCAP QUALITY')
print('=' * 90)
for f in sorted(ROOT.iterdir()):
    if f.suffix.lower() not in ('.pcap', '.pcapng'):
        continue
    print(f'\n--- {f.name} ({f.stat().st_size/1e6:.1f} MB) ---')
    try:
        r = analyze_cap(f)
    except Exception as e:
        print('  ERROR', e)
        continue
    if 'error' in r:
        print(' ', r)
        continue
    for k in ('dur_min', 'pkts', 'udp', 'tcp', 'game_udp', 'match_port_hits', 'linktypes', 'top_ports', 'verdict'):
        print(f'  {k}: {r[k]}')

print('\n' + '=' * 90)
print('MENU RECORDER LOGS — endpoints + gap checklist')
print('=' * 90)

checklist = [
    ('Leaderboards', [r'leaderboard', r'/scores', r'getScores', r'ranking']),
    ('Notifications', [r'notif']),
    ('Match-end / XP', [r'matchSummary', r'ClearMatch', r'DedicatedServer/match', r'/xp']),
    ('Shop', [r'getShopItems', r'/shop/']),
    ('Career/Stats', [r'PlayerStatistics', r'/profileNew', r'/progression']),
    ('Challenges', [r'/challenges']),
    ('Friends', [r'/friends/']),
    ('Season/BP', [r'/season/']),
    ('Inventory', [r'/inventory/']),
    ('Auth', [r'authenticate/fxgames']),
    ('Maps list', [r'maps/getAll']),
    ('Smolensk mention', [r'Smolensk', r'smolensk']),
    ('Moscow Senate mention', [r'Moscow_Senate', r'Senate']),
    ('Landmark mention', [r'Landmark']),
]

# group logs by date stamp in filename
logs = sorted(ROOT.glob('WW3_rec_*.log'))
by_run = {}
for f in logs:
    # extract stamp
    m = re.search(r'(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})', f.name)
    stamp = m.group(1) if m else 'unknown'
    by_run.setdefault(stamp, []).append(f)

for stamp, files in sorted(by_run.items()):
    print(f'\n### run {stamp} ({len(files)} files, {sum(x.stat().st_size for x in files)/1e6:.1f} MB)')
    text = ''
    for f in files:
        try:
            text += f.read_text(encoding='utf-8', errors='replace') + '\n'
        except Exception:
            pass
    # paths
    seen = set()
    for m in re.finditer(r'\b(GET|POST|PUT|DELETE)\s+(/[^\s"\'\\]*)', text):
        method, path = m.group(1), m.group(2).split('?')[0]
        key = re.sub(r'/\d{5,}', '/{id}', path)
        key = re.sub(r'/7656119\d+', '/{steamid}', key)
        seen.add(f'{method} {key}')
    print(f'  distinct HTTP paths: {len(seen)}')
    for name, pats in checklist:
        hits = [p for p in seen if any(re.search(pat, p, re.I) for pat in pats)]
        # also plain text mentions for map names
        if name.endswith('mention'):
            ok = any(re.search(pats[0], text) for pats in [pats]) or any(re.search(p, text, re.I) for p in pats)
            # count
            cnt = sum(len(re.findall(p, text, re.I)) for p in pats)
            print(f'  {"YES" if cnt else "no ":3} {name} (x{cnt})')
        else:
            print(f'  {"YES" if hits else "no ":3} {name}' + (f' -> {hits[:3]}' if hits else ''))
    # PlayerToken / auth success?
    print(f'  PlayerToken mentions: {text.count("PlayerToken")}')
    print(f'  Invalid Token: {text.count("Invalid Token")}')
    print(f'  Missing token: {text.count("Missing token")}')
    # interesting new paths vs known
    interesting = sorted(p for p in seen if not any(x in p for x in ['analytics', 'ww3-content', 'client_events']))
    print('  non-analytics paths:')
    for p in interesting:
        print('   ', p)

print('\nDONE')
