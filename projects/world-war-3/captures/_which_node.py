import re
from pathlib import Path
from collections import defaultdict, Counter

t = Path(r'F:\Dev_Work\GameDev\WW3\windows\record_logs\meta.prod.ww3.fxtools.gl.log').read_text(encoding='utf-8', errors='replace')
lines = t.splitlines()

by = defaultdict(Counter)
last_ip = None
for l in lines:
    m = re.search(r'=====.*meta\.prod\.ww3\.fxtools\.gl \(([\d\.]+)\)', l)
    if m:
        last_ip = m.group(1)
        continue
    if 'PlayerToken' in l:
        by[last_ip]['SUCCESS'] += 1
    if 'Invalid Token' in l:
        by[last_ip]['INVALID'] += 1

print('per-IP auth outcomes in July23 meta log:')
for ip, c in by.items():
    print('  ', ip, dict(c))

ips = sorted(set(re.findall(r'meta\.prod\.ww3\.fxtools\.gl \(([\d\.]+)\)', t)))
print('distinct upstream IPs seen July23:', ips)
