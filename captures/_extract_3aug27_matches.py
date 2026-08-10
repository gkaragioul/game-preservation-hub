import re
from collections import Counter
from pathlib import Path

f = Path(r'F:\Dev_Work\GameDev\WW3\captures\3Aug27\WW3_rec_meta.prod.ww3.fxtools.gl_2026-08-03_12-29-02.log')
t = f.read_text(encoding='utf-8', errors='replace')
print('meta log size', len(t))

print('\n=== matchSummary contexts ===')
for i, m in enumerate(re.finditer(r'.{0,120}matchSummary.{0,400}', t, re.I)):
    s = re.sub(r'\s+', ' ', m.group(0))
    print(f'[{i}]', s[:450])
    print('---')

# also session log may have hub WS
s = Path(r'F:\Dev_Work\GameDev\WW3\captures\3Aug27\WW3_rec__session_2026-08-03_12-29-02.log')
st = s.read_text(encoding='utf-8', errors='replace')
print('\nsession log size', len(st))
print('matchSummary in session:', len(re.findall('matchSummary', st, re.I)))
print('LobbyReady in session:', len(re.findall('LobbyReady', st, re.I)))
print('LobbyMatch in session:', len(re.findall('LobbyMatch', st, re.I)))

print('\n=== session matchSummary contexts ===')
for i, m in enumerate(re.finditer(r'.{0,120}matchSummary.{0,400}', st, re.I)):
    s2 = re.sub(r'\s+', ' ', m.group(0))
    print(f'[{i}]', s2[:450])
    print('---')
    if i >= 10:
        break

print('\n=== maps near lobbyToken (session) ===')
c = Counter()
for m in re.finditer(r'lobbyToken', st):
    window = st[max(0, m.start()-1000): m.start()+1000]
    for mm in re.findall(r'WW3_[A-Za-z0-9_]+_P', window):
        c[mm] += 1
print(c)

print('\n=== maps near lobbyToken (meta) ===')
c2 = Counter()
for m in re.finditer(r'lobbyToken', t):
    window = t[max(0, m.start()-1000): m.start()+1000]
    for mm in re.findall(r'WW3_[A-Za-z0-9_]+_P', window):
        c2[mm] += 1
print(c2)

print('\n=== HTTP request lines with match/summary/renew ===')
for m in re.finditer(r'(>>>|<<<).{0,20}(GET|POST|PUT|DELETE)[^\n]{0,120}', t):
    line = m.group(0)
    if re.search(r'match|summary|renew|xp|Clear|score', line, re.I):
        print(line[:200])

print('\n=== gamePort + map pairs in session ===')
pairs = Counter()
for m in re.finditer(r'"map"\s*:\s*"(WW3_[^"]+)"', st):
    window = st[max(0, m.start()-300): m.start()+300]
    ports = re.findall(r'"gamePort"\s*:\s*(\d+)', window)
    for p in ports:
        pairs[(m.group(1), p)] += 1
print(pairs.most_common(20))
