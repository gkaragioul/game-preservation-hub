"""Extract SummaryScreen context from pcaps that already have it."""
import struct, re
from pathlib import Path

def payloads_near_string(path, needle=b'SummaryScreen', window=200):
    data = Path(path).read_bytes()
    off = 0
    results = []
    while off + 12 <= len(data):
        bt, bl = struct.unpack('<II', data[off:off+8])
        if bl < 12 or off + bl > len(data):
            break
        if bt == 6 and bl >= 32:
            caplen = struct.unpack('<I', data[off+20:off+24])[0]
            pkt = data[off+28:off+28+caplen]
            if len(pkt) >= 42 and struct.unpack('>H', pkt[12:14])[0] == 0x0800 and pkt[23] == 17:
                ihl = (pkt[14] & 0x0F) * 4
                l4 = 14 + ihl
                payload = pkt[l4+8:]
                if needle in payload:
                    # extract ascii around it
                    idx = payload.find(needle)
                    start = max(0, idx - window)
                    end = min(len(payload), idx + len(needle) + window)
                    chunk = payload[start:end]
                    ascii_runs = re.findall(rb'[\x20-\x7e]{4,}', chunk)
                    results.append([r.decode('ascii') for r in ascii_runs])
        off += bl
    return results

for f in [
    r'F:\Dev_Work\GameDev\WW3\captures\26July26\war_moscow.pcapng',
    r'F:\Dev_Work\GameDev\WW3\captures\26July26\tdm_Warszawa.pcapng',
]:
    print('===', Path(f).name, '===')
    hits = payloads_near_string(f)
    print(f'SummaryScreen packets: {len(hits)}')
    for i, runs in enumerate(hits[:5]):
        print(f'  hit {i}: {runs[:30]}')
    print()

# Also search more pcaps quickly for SummaryScreen / PlayerLevel presence
print('=== which full matches already contain SummaryScreen / PlayerLevel? ===')
needles = [b'SummaryScreen', b'PlayerLevel', b'MatchResult', b'scoreboard', b'Scoreboard']
candidates = []
root = Path(r'F:\Dev_Work\GameDev\WW3\captures')
for f in root.rglob('*.pcapng'):
    # skip tiny junk
    if f.stat().st_size < 5_000_000:
        continue
    # quick binary search
    data = f.read_bytes()
    found = {n.decode(): data.count(n) for n in needles if n in data}
    if found:
        print(f'  {f.relative_to(root)}: {found}')
        candidates.append(f.name)

print('\nFiles with SummaryScreen-like markers:', candidates)
