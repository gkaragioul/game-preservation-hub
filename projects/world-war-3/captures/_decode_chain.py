import re, glob, os, base64, json
from datetime import datetime, timezone

def dec(seg):
    seg += '=' * ((4 - len(seg) % 4) % 4)
    return base64.urlsafe_b64decode(seg.replace('-', '+').replace('_', '/'))

def full(tok):
    h = json.loads(dec(tok.split('.')[0]))
    p = json.loads(dec(tok.split('.')[1]))
    return h, p

base = r'C:\Users\georg\AppData\Local\World War 3 Launcher\Default\Local Storage\leveldb'
toks = set()
for f in glob.glob(os.path.join(base, '*')):
    if os.path.isdir(f): continue
    try: data = open(f, 'rb').read()
    except: continue
    txt = data.decode('latin-1', 'replace')
    for m in re.findall(r'eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{4,}', txt):
        toks.add(m)

now = datetime.now(timezone.utc).timestamp()
by_iss = {}
for t in toks:
    try:
        h, p = full(t)
    except: continue
    iss = p.get('iss', '?')
    by_iss.setdefault(iss, [])
    by_iss[iss].append((h, p, t))

for iss, items in by_iss.items():
    print(f'\n===== issuer: {iss}  ({len(items)} tokens) =====')
    # show one freshest example fully
    items.sort(key=lambda x: x[1].get('iat', 0), reverse=True)
    h, p, t = items[0]
    print('  header:', h)
    print('  payload:', json.dumps(p, indent=2)[:900])
    exp = p.get('exp')
    if exp:
        yr = datetime.fromtimestamp(exp, timezone.utc).year
        print(f'  exp year: {yr}  expired={exp < now}')

# find refreshToken value and its context
print('\n===== refreshToken key context =====')
for f in glob.glob(os.path.join(base, '*')):
    if os.path.isdir(f): continue
    try: data = open(f, 'rb').read()
    except: continue
    txt = data.decode('latin-1', 'replace')
    for m in re.finditer(r'refreshToken', txt):
        s = max(0, m.start()-10); e = min(len(txt), m.start()+120)
        frag = re.sub(r'[^\x20-\x7e]', '.', txt[s:e])
        print('  ...', frag)
        break
