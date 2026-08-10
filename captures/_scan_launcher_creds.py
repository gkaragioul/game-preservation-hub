import re, glob, os, base64, json

def dec(seg):
    seg += '=' * ((4 - len(seg) % 4) % 4)
    return base64.urlsafe_b64decode(seg.replace('-', '+').replace('_', '/'))

def scan(base, label):
    print(f'\n===== {label}: {base} =====')
    if not os.path.isdir(base):
        print('  (missing)'); return
    urls = set(); toks = set(); keys = set()
    for f in glob.glob(os.path.join(base, '*')):
        if os.path.isdir(f): continue
        try: data = open(f, 'rb').read()
        except: continue
        txt = data.decode('latin-1', 'replace')
        for m in re.findall(r'https?://[A-Za-z0-9\.\-/_]{6,90}', txt): urls.add(m)
        for m in re.findall(r'eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{4,}', txt): toks.add(m)
        for m in re.findall(r'[A-Za-z_]{3,}(?:Token|token|Auth|auth|fxid|FxId|Session|Player|Account|refresh|Refresh)[A-Za-z_]*', txt): keys.add(m)
    print('  URLs:')
    for u in sorted(urls)[:40]: print('    ', u)
    print(f'  JWTs present: {len(toks)}')
    for t in list(toks)[:12]:
        try:
            p = json.loads(dec(t.split('.')[1]))
            small = {k: p[k] for k in ('sub','id','type','auth_type','is_fx_native','iss','auth_via','exp') if k in p}
            print('    ', small)
        except Exception as e:
            print('    (undecodable)', t[:30])
    print('  cred keys:', sorted(keys)[:50])

scan(r'C:\Users\georg\AppData\Local\World War 3 Launcher\Default\Local Storage\leveldb', 'ACTIVE Local Storage')
scan(r'C:\Users\georg\AppData\Local\World War 3 Launcher\Default\Session Storage', 'ACTIVE Session Storage')
scan(r'C:\Users\georg\AppData\Local\World War 3 Launcher\Default_authbak_20260731_012034\Local Storage\leveldb', 'BACKUP(Jul31) Local Storage')
