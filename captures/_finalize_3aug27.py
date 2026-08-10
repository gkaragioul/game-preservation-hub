from pathlib import Path
import re
from collections import Counter

t = Path(r'F:\Dev_Work\GameDev\WW3\captures\3Aug27\WW3_rec_meta.prod.ww3.fxtools.gl_2026-08-03_12-29-02.log').read_text(encoding='utf-8', errors='replace')

print('sample Senate contexts:')
for i, m in enumerate(re.finditer(r'.{0,50}WW3_Moscow_Senate_P.{0,50}', t)):
    print(re.sub(r'\s+', ' ', m.group(0)))
    if i >= 5:
        break

print('\nsample Smolensk contexts:')
for i, m in enumerate(re.finditer(r'.{0,50}WW3_Smolensk_P.{0,50}', t)):
    print(re.sub(r'\s+', ' ', m.group(0)))
    if i >= 5:
        break

def paths_around(needle, limit=80):
    c = Counter()
    for idx in [m.start() for m in re.finditer(needle, t)][:limit]:
        window = t[max(0, idx - 2500):idx]
        ms = list(re.finditer(r'>>> (GET|POST|PUT) ([^\s]+)', window))
        if ms:
            c[ms[-1].group(0)] += 1
    return c

print('\npaths around Smolensk:', paths_around('WW3_Smolensk_P'))
print('paths around Senate:', paths_around('WW3_Moscow_Senate_P'))

exps = [float(x) for x in re.findall(r'"playerSeasonExperience"\s*:\s*([0-9.]+)', t)]
levels = [int(x) for x in re.findall(r'"playerSeasonLevel"\s*:\s*(\d+)', t)]
print('\nXP unique sorted:', sorted(set(round(x, 2) for x in exps)))
print('levels seen:', sorted(set(levels)))
if exps:
    print('XP min/max:', min(exps), max(exps))

# Also check war_smolensk for destination IPs on port 7869
import struct
from pathlib import Path as P

def dst_ips_on_port(path, port=7869, limit_pkts=None):
    data = P(path).read_bytes()
    off = 0
    ips = Counter()
    n = 0
    while off + 12 <= len(data):
        bt, bl = struct.unpack('<II', data[off:off+8])
        if bl < 12 or off + bl > len(data):
            break
        if bt == 6 and bl >= 32:
            caplen = struct.unpack('<I', data[off+20:off+24])[0]
            pkt = data[off+28:off+28+caplen]
            if len(pkt) >= 34 and struct.unpack('>H', pkt[12:14])[0] == 0x0800:
                ihl = (pkt[14] & 0x0F) * 4
                if pkt[23] == 17:
                    l4 = 14 + ihl
                    if len(pkt) >= l4 + 4:
                        sp, dp = struct.unpack('>HH', pkt[l4:l4+4])
                        if sp == port or dp == port:
                            dst = '.'.join(str(b) for b in pkt[30:34])
                            src = '.'.join(str(b) for b in pkt[26:30])
                            ips[(src, sp, dst, dp)] += 1
            n += 1
        off += bl
    return ips

print('\n=== war_smolensk.pcapng UDP flows on 7869 ===')
flows = dst_ips_on_port(r'F:\Dev_Work\GameDev\WW3\captures\3Aug27\war_smolensk.pcapng')
for k, v in flows.most_common(10):
    print(v, k)
