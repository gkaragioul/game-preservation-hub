import json, re
from pathlib import Path

rm = json.load(open(r'F:\Dev_Work\GameDev\WW3\mockserver\replay_map.json', encoding='utf-8'))
http = rm.get('http', {})
print('=== replay_map shop/season related keys ===')
for k in sorted(http):
    if re.search(r'shop|season|battle|pass|purchase|buy|claim|wallet|bpass', k, re.I):
        raw = json.dumps(http[k], ensure_ascii=False)
        print(f'  {k}  ({len(raw)} chars)')

# peek season and shop structure briefly
for key in ['GET /shop/getShopItems', 'GET /season/getSeason']:
    if key not in http:
        continue
    body = http[key]
    if isinstance(body, dict) and 'body' in body:
        body = body['body']
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except Exception:
            pass
    text = json.dumps(body, ensure_ascii=False)
    print(f'\n=== {key} top-level ===')
    if isinstance(body, dict):
        print('  keys:', list(body.keys())[:30])
    print('  sample:', text[:400].replace('\n', ' '))

# search logs for buy/claim
print('\n=== buy/claim/purchase paths in logs ===')
paths = set()
for d in [Path(r'F:\Dev_Work\GameDev\WW3\captures'), Path(r'F:\Dev_Work\GameDev\WW3\windows\record_logs'), Path(r'F:\Dev_Work\GameDev\WW3\LOGS')]:
    if not d.exists():
        continue
    for f in d.rglob('*'):
        if f.suffix.lower() not in ('.log', '.jsonl'):
            continue
        try:
            t = f.read_text(encoding='utf-8', errors='replace')
        except Exception:
            continue
        for m in re.finditer(r'(GET|POST|PUT|DELETE)\s+(/[^\s"\']*)', t):
            p = (m.group(1) + ' ' + m.group(2)).split('?')[0]
            if re.search(r'shop|season|buy|claim|purchase|wallet|bpass|battle', p, re.I):
                paths.add(p)
for p in sorted(paths):
    print(' ', p)
