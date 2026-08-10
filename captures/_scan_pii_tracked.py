import re, subprocess
from pathlib import Path
from collections import defaultdict

files = subprocess.check_output(['git', 'ls-files'], text=True).splitlines()
hits = defaultdict(list)
patterns = {
    'steamid': re.compile(r'7656119\d{10}'),
    'jwt': re.compile(r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'),
    'george': re.compile(r'georgekgaming|GeorgeKGaming|gkaragioul|Karagioule', re.I),
    'playername': re.compile(r'"playerName"\s*:\s*"([^"]+)"'),
    'playerid': re.compile(r'"playerId"\s*:\s*\d+'),
    'fxid_165822': re.compile(r'165822'),
    'hw_guid': re.compile(r'\{[0-9a-fA-F-]{36}\}'),
}

for line in files:
    p = Path(line)
    if not p.is_file():
        continue
    if p.suffix.lower() in ('.png', '.pdf', '.jpg', '.jpeg', '.gif'):
        continue
    try:
        data = p.read_bytes()
    except Exception:
        continue
    if b'\x00' in data[:1024] and p.suffix.lower() not in ('.json', '.jsonl', '.md', '.py', '.txt', '.html', '.xml', '.ini', '.ps1'):
        continue
    t = data.decode('utf-8', errors='ignore')
    for name, pat in patterns.items():
        found = pat.findall(t)
        if found:
            hits[str(p)].append((name, len(found), found[:3]))

for f, items in sorted(hits.items()):
    print(f)
    for name, n, sample in items:
        print(f'  {name}: {n}  sample={sample!r}')
