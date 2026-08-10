"""Prove whether Moskow TDM captures are Moscow Senate."""
import json, struct, re
from pathlib import Path
from collections import Counter

# --- 1) API logic test ---
rm = json.load(open(r'F:\Dev_Work\GameDev\WW3\mockserver\replay_map.json', encoding='utf-8'))
body = rm['http']['GET /sharedData/maps/getAll']
if isinstance(body, dict) and 'body' in body:
    body = body['body']
if isinstance(body, str):
    body = json.loads(body)

def walk(o):
    if isinstance(o, list) and o and isinstance(o[0], dict) and 'name' in o[0]:
        return o
    if isinstance(o, dict):
        for v in o.values():
            r = walk(v)
            if r is not None:
                return r
    if isinstance(o, list):
        for x in o:
            r = walk(x)
            if r is not None:
                return r
    return None

maps = walk(body)
print('=== API: Moscow maps ===')
for m in maps:
    gms = [g.get('gameMode') for g in m.get('gamemodes', [])]
    if 'Moscow' in m['name']:
        print(f"  {m['name']} -> {gms}")

print('\n=== API: all TDM maps ===')
tdm = []
for m in maps:
    gms = [g.get('gameMode') for g in m.get('gamemodes', [])]
    if any(g and 'TDM' in str(g) for g in gms):
        tdm.append(m['name'])
        print(f"  {m['name']}")
print(f'\nConclusion from API: only Moscow TDM map = {[x for x in tdm if "Moscow" in x]}')

# --- 2) Search pcap payloads for map name strings ---
NEEDLES = [
    b'WW3_Moscow_Senate_P',
    b'WW3_Moscow_P',
    b'Moscow_Senate',
    b'MoscowSenate',
    b'WW3_Shibuya_P',
    b'WW3_Berlin_Backyards',
    b'WW3_Warsaw_Shopping',
    b'TDM_M',
    b'WAR_M',
    b'Senate',
]

def iter_pcapng_payloads(path):
    data = Path(path).read_bytes()
    off = 0
    while off + 12 <= len(data):
        bt, bl = struct.unpack('<II', data[off:off + 8])
        if bl < 12 or off + bl > len(data):
            break
        if bt == 6 and bl >= 32:
            caplen = struct.unpack('<I', data[off + 20:off + 24])[0]
            pkt = data[off + 28:off + 28 + caplen]
            # ethernet + ipv4 + udp -> payload
            if len(pkt) >= 42 and struct.unpack('>H', pkt[12:14])[0] == 0x0800 and pkt[23] == 17:
                ihl = (pkt[14] & 0x0F) * 4
                l4 = 14 + ihl
                payload = pkt[l4 + 8:]  # skip UDP header
                yield payload
            elif len(pkt) >= 28 and (pkt[0] >> 4) == 4 and pkt[9] == 17:
                ihl = (pkt[0] & 0x0F) * 4
                payload = pkt[ihl + 8:]
                yield payload
        off += bl

def scan_file(path):
    print(f'\n=== scanning {Path(path).name} for map strings ===')
    hits = Counter()
    # also collect any WW3_*_P strings found
    ww3 = Counter()
    n = 0
    for payload in iter_pcapng_payloads(path):
        n += 1
        for needle in NEEDLES:
            if needle in payload:
                hits[needle.decode('ascii', 'replace')] += 1
        for m in re.findall(rb'WW3_[A-Za-z0-9_]+_P', payload):
            ww3[m.decode()] += 1
    print(f'  packets scanned: {n}')
    print(f'  needle hits: {dict(hits)}')
    print(f'  WW3_*_P strings in UDP payloads: {dict(ww3)}')
    return hits, ww3

files = [
    r'F:\Dev_Work\GameDev\WW3\captures\3Aug27\Moskow TDM2.pcapng',
    r'F:\Dev_Work\GameDev\WW3\captures\31July26\moskow TDM.pcapng',
    r'F:\Dev_Work\GameDev\WW3\captures\3Aug27\war_smolensk.pcapng',  # control: should show Smolensk if strings leak
]

for f in files:
    if Path(f).exists():
        scan_file(f)
    else:
        print('missing', f)

print('\n=== VERDICT LOGIC ===')
print('If a capture is Moscow + TDM, API says the only possible map is WW3_Moscow_Senate_P.')
print('If UDP payloads contain WW3_Moscow_Senate_P, that is hard proof.')
print('If they contain WW3_Moscow_P, that would be Warzone Moscow (not Senate).')
