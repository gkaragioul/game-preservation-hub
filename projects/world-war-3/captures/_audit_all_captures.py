"""Comprehensive audit of F:\\Dev_Work\\GameDev\\WW3\\captures"""
import struct, os, zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(r'F:\Dev_Work\GameDev\WW3\captures')

def parse_pcap(path):
    """Return list of (ts_sec_float, pkt_bytes, linktype) for classic pcap."""
    with open(path, 'rb') as f:
        data = f.read()
    if len(data) < 24:
        return [], None
    magic = data[:4]
    if magic == b'\xd4\xc3\xb2\xa1':
        le = True
    elif magic == b'\xa1\xb2\xc3\xd4':
        le = False
    else:
        return None, None  # not classic pcap
    end = '<' if le else '>'
    _, _, _, _, _, snaplen, linktype = struct.unpack(end + 'IHHIIII', data[:24])
    off = 24
    pkts = []
    while off + 16 <= len(data):
        ts_sec, ts_usec, caplen, origlen = struct.unpack(end + 'IIII', data[off:off+16])
        off += 16
        if off + caplen > len(data):
            break
        pkt = data[off:off+caplen]
        off += caplen
        pkts.append((ts_sec + ts_usec / 1_000_000.0, pkt))
    return pkts, linktype

def parse_pcapng(path):
    with open(path, 'rb') as f:
        data = f.read()
    if data[:4] != b'\x0a\x0d\x0d\x0a':
        return None, None
    off = 0
    pkts = []
    linktypes = {}  # iface_id -> linktype
    ts_resol = {}   # iface_id -> divisor
    default_resol = 1_000_000
    while off + 12 <= len(data):
        block_type, block_len = struct.unpack('<II', data[off:off+8])
        if block_len < 12 or off + block_len > len(data):
            break
        block = data[off:off+block_len]
        if block_type == 0x00000001:  # IDB
            linktype = struct.unpack('<H', block[8:10])[0]
            # iface id = order of IDBs
            iface_id = len(linktypes)
            linktypes[iface_id] = linktype
            # options for tsresol
            opts = block[16:-4]
            resol = default_resol
            i = 0
            while i + 4 <= len(opts):
                ocode, olen = struct.unpack('<HH', opts[i:i+4])
                if ocode == 0 and olen == 0:
                    break
                oval = opts[i+4:i+4+olen]
                if ocode == 9 and oval:
                    val = oval[0]
                    if val & 0x80:
                        resol = 2 ** (val & 0x7f)
                    else:
                        resol = 10 ** (val & 0x7f)
                pad = (4 - olen % 4) % 4
                i += 4 + olen + pad
            ts_resol[iface_id] = resol
        elif block_type == 0x00000006:  # EPB
            if len(block) >= 32:
                iface_id, ts_high, ts_low, caplen = struct.unpack('<IIII', block[8:24])
                resol = ts_resol.get(iface_id, default_resol)
                ts = ((ts_high << 32) | ts_low) / float(resol)
                pkt = block[28:28+caplen]
                pkts.append((ts, pkt, linktypes.get(iface_id, 1)))
        elif block_type == 0x00000003:  # SPB (simple packet)
            if len(block) >= 16:
                origlen = struct.unpack('<I', block[8:12])[0]
                # no timestamp
                pkt = block[12:12+min(origlen, block_len-16)]
                pkts.append((None, pkt, linktypes.get(0, 1)))
        off += block_len
    # normalize to (ts, pkt) with first linktype
    out = []
    for item in pkts:
        if len(item) == 3:
            ts, pkt, lt = item
            out.append((ts, pkt, lt))
        else:
            out.append((item[0], item[1], 1))
    lt = linktypes.get(0, 1) if linktypes else 1
    return out, lt

def l3_offset(pkt, linktype):
    """Return offset to IP header, or None."""
    if linktype == 1:  # Ethernet
        if len(pkt) < 14:
            return None
        ethertype = struct.unpack('>H', pkt[12:14])[0]
        if ethertype == 0x0800:
            return 14
        if ethertype == 0x8100 and len(pkt) >= 18:  # VLAN
            ethertype = struct.unpack('>H', pkt[16:18])[0]
            if ethertype == 0x0800:
                return 18
        return None
    if linktype == 101:  # Raw IP
        return 0
    if linktype == 113:  # Linux cooked
        if len(pkt) < 16:
            return None
        ethertype = struct.unpack('>H', pkt[14:16])[0]
        if ethertype == 0x0800:
            return 16
        return None
    if linktype == 12:  # Raw IP (some)
        return 0
    # Unknown: try ethernet then raw
    if len(pkt) >= 14 and struct.unpack('>H', pkt[12:14])[0] == 0x0800:
        return 14
    if len(pkt) >= 1 and (pkt[0] >> 4) == 4:
        return 0
    return None

def classify(pkt, linktype):
    off = l3_offset(pkt, linktype)
    if off is None or len(pkt) < off + 20:
        return None
    if (pkt[off] >> 4) != 4:
        return None
    ihl = (pkt[off] & 0x0F) * 4
    proto = pkt[off + 9]
    l4 = off + ihl
    if proto == 17 and len(pkt) >= l4 + 4:  # UDP
        sport, dport = struct.unpack('>HH', pkt[l4:l4+4])
        return ('UDP', sport, dport, pkt[off+16:off+20])  # dst IP
    if proto == 6 and len(pkt) >= l4 + 4:  # TCP
        sport, dport = struct.unpack('>HH', pkt[l4:l4+4])
        return ('TCP', sport, dport, pkt[off+16:off+20])
    return (f'P{proto}', 0, 0, b'')

NOISE_UDP = {53, 123, 137, 138, 139, 1900, 5353, 5355, 67, 68, 443, 80, 3478, 19302}

def analyze_file(path):
    size = path.stat().st_size
    suffix = path.suffix.lower()
    if suffix == '.pcapng':
        pkts, lt = parse_pcapng(path)
        if pkts is None:
            return {'error': 'not pcapng', 'size': size}
    elif suffix == '.pcap':
        pkts, lt = parse_pcap(path)
        if pkts is None:
            return {'error': 'not classic pcap', 'size': size}
        pkts = [(t, p, lt) for t, p in pkts]
    else:
        return {'error': 'not a capture', 'size': size}

    if not pkts:
        return {'error': 'empty', 'size': size, 'pkts': 0}

    times = [t for t, _, _ in pkts if t is not None]
    dur = (max(times) - min(times)) if times else 0
    proto = Counter()
    udp_ports = Counter()
    tcp_ports = Counter()
    game_udp = 0  # UDP on ports that look like UE / match (not noise)
    match_port_hits = 0  # 7860-7900 range from docs
    for ts, pkt, linktype in pkts:
        c = classify(pkt, linktype)
        if not c:
            continue
        kind = c[0]
        proto[kind] += 1
        if kind == 'UDP':
            sport, dport = c[1], c[2]
            udp_ports[sport] += 1
            udp_ports[dport] += 1
            if sport not in NOISE_UDP and dport not in NOISE_UDP:
                game_udp += 1
            if (7860 <= sport <= 7900) or (7860 <= dport <= 7900):
                match_port_hits += 1
        elif kind == 'TCP':
            tcp_ports[c[1]] += 1
            tcp_ports[c[2]] += 1

    # Verdict
    udp_n = proto.get('UDP', 0)
    tcp_n = proto.get('TCP', 0)
    if 'tcp.port' in path.name.lower() and (443 in dict(tcp_ports) or 80 in dict(tcp_ports)):
        verdict = 'JUNK (bad TCP filter)'
    elif game_udp > 500 and dur >= 60:
        verdict = 'USEFUL match UDP'
    elif game_udp > 100:
        verdict = 'THIN but has game UDP'
    elif udp_n < 50 and tcp_n > udp_n:
        verdict = 'JUNK (mostly TCP)'
    elif udp_n < 100:
        verdict = 'THIN / short'
    else:
        verdict = 'UNCLEAR — inspect'

    # Full match heuristic: WW3 TDM ~10-15 min, War ~20+ min; need continuous game UDP
    fullish = dur >= 8 * 60 and game_udp > 2000

    return {
        'size': size,
        'pkts': len(pkts),
        'dur_s': dur,
        'dur_min': dur / 60,
        'linktype': lt,
        'udp': udp_n,
        'tcp': tcp_n,
        'game_udp': game_udp,
        'match_port_hits': match_port_hits,
        'top_udp': udp_ports.most_common(6),
        'top_tcp': tcp_ports.most_common(4),
        'verdict': verdict,
        'fullish': fullish,
    }

def map_guess(name):
    n = name.lower()
    tags = []
    for k, label in [
        ('moscow', 'Moscow'), ('moskow', 'Moscow'), ('senate', 'Senate'),
        ('shibuya', 'Shibuya'), ('berlin', 'Berlin'), ('warsaw', 'Warsaw'),
        ('warszawa', 'Warsaw'), ('istanbul', 'Istanbul'), ('instanbul', 'Istanbul'),
        ('landmark', 'Landmark'), ('smolensk', 'Smolensk'), ('dmz', 'DMZ'),
        ('tokyo', 'Tokyo'), ('stronghold', 'Stronghold'), ('stolong', 'Stronghold'),
        ('polar', 'Polyarny'), ('поля', 'Polyarny'),
        ('tdm', 'TDM'), ('war_', 'Warzone'), ('warzone', 'Warzone'),
        ('tacops', 'TacOps'), ('lobby', 'Lobby'),
    ]:
        if k in n:
            tags.append(label)
    return tags

print('=' * 100)
print('FULL AUDIT:', ROOT)
print('=' * 100)

# 1) Tree summary
by_folder = defaultdict(list)
all_files = []
for p in sorted(ROOT.rglob('*')):
    if p.is_file() and not p.name.startswith('_'):
        all_files.append(p)
        by_folder[str(p.parent.relative_to(ROOT))].append(p)

print('\n### FOLDER INVENTORY')
for folder, files in sorted(by_folder.items()):
    total = sum(f.stat().st_size for f in files)
    print(f'\n[{folder}]  {len(files)} files, {total/1e6:.1f} MB')
    for f in files:
        print(f'  {f.name:55s} {f.stat().st_size/1e6:8.2f} MB')

# 2) Analyze every pcap/pcapng
print('\n\n### CAPTURE QUALITY (pcap/pcapng)')
print(f'{"file":55s} {"min":>7s} {"pkts":>8s} {"UDP":>7s} {"gameUDP":>8s} {"verdict"}')
print('-' * 110)

results = []
for p in all_files:
    if p.suffix.lower() not in ('.pcap', '.pcapng'):
        continue
    rel = str(p.relative_to(ROOT))
    try:
        r = analyze_file(p)
    except Exception as e:
        r = {'error': str(e), 'size': p.stat().st_size}
    r['rel'] = rel
    r['name'] = p.name
    r['tags'] = map_guess(p.name)
    results.append(r)
    if 'error' in r and r.get('pkts') is None:
        print(f'{rel[:55]:55s}  ERROR: {r["error"]}')
        continue
    print(f'{rel[:55]:55s} {r.get("dur_min",0):7.1f} {r.get("pkts",0):8d} {r.get("udp",0):7d} {r.get("game_udp",0):8d}  {r.get("verdict","?")}')

# 3) Map coverage from USEFUL files
print('\n\n### MAP / MODE COVERAGE (only USEFUL or THIN-with-UDP captures)')
useful = [r for r in results if r.get('verdict', '').startswith(('USEFUL', 'THIN'))]
by_tag = defaultdict(list)
for r in useful:
    for t in r['tags']:
        by_tag[t].append(r['name'])

known_maps = [
    'Shibuya', 'Berlin', 'Warsaw', 'Moscow', 'Senate', 'Istanbul',
    'Landmark', 'Smolensk', 'DMZ', 'Tokyo', 'Stronghold', 'Polyarny',
]
print('\nMap tags found in useful captures:')
for m in known_maps:
    files = by_tag.get(m, [])
    status = 'YES' if files else 'NO '
    print(f'  [{status}] {m:12s}  {", ".join(files[:4]) if files else "(none)"}')

# 4) Full-match candidates
print('\n\n### "FULL MATCH" CANDIDATES (duration >= 8 min AND substantial game UDP)')
fulls = [r for r in results if r.get('fullish')]
if not fulls:
    print('  (none matched the heuristic)')
else:
    for r in sorted(fulls, key=lambda x: -x.get('dur_min', 0)):
        print(f'  {r["rel"]}')
        print(f'      {r["dur_min"]:.1f} min, {r["game_udp"]} game-UDP pkts, {r["verdict"]}')

# 5) Specific check: Moscow Senate
print('\n\n### MOSCOW SENATE SPECIFIC')
for r in results:
    if 'senate' in r['name'].lower() or ('moscow' in r['name'].lower() and 'tdm' in r['name'].lower()):
        print(f'  FILE: {r["rel"]}')
        for k in ('dur_min', 'pkts', 'udp', 'tcp', 'game_udp', 'match_port_hits', 'top_udp', 'top_tcp', 'verdict', 'fullish', 'linktype'):
            print(f'    {k}: {r.get(k)}')

# 6) Zips
print('\n\n### ZIP ARCHIVES')
for p in all_files:
    if p.suffix.lower() == '.zip':
        try:
            with zipfile.ZipFile(p) as z:
                names = z.namelist()[:8]
            print(f'  {p.relative_to(ROOT)}  ({len(z.namelist())} entries) e.g. {names}')
        except Exception as e:
            print(f'  {p.relative_to(ROOT)}  ERROR {e}')

print('\n\nDONE.')
