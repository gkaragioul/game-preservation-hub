import json, re

http = json.load(open(r'F:\Dev_Work\GameDev\WW3\mockserver\replay_map.json', encoding='utf-8'))['http']

# 1) god catalog source: progression tree item rewards
prog = http['GET /progression/getProgressionTree']['body']['result']
prog_ids = set()
for ent in prog.get('entities', []):
    for lvl in ent.get('levels', []):
        for it in lvl.get('rewards', {}).get('items', []):
            try:
                prog_ids.add(int(it))
            except (ValueError, TypeError):
                pass

# 2) season / battle pass reward IDs
seas = http['GET /season/getSeason']['body']['result']
season_ids = set()
season_award_ids = set()  # awardId strings like "8453"

def walk(o):
    if isinstance(o, dict):
        # common reward shapes
        if 'awardId' in o:
            try:
                season_award_ids.add(str(o['awardId']))
            except Exception:
                pass
        if 'items' in o and isinstance(o['items'], list):
            for it in o['items']:
                try:
                    season_ids.add(int(it))
                except Exception:
                    pass
        for v in o.values():
            walk(v)
    elif isinstance(o, list):
        for x in o:
            walk(x)

walk(seas)

# also pull numeric awardIds
for a in list(season_award_ids):
    try:
        season_ids.add(int(a))
    except Exception:
        pass

# 3) what inventory currently owns
inv = http['GET /inventory/get']['body']['result']
owned = set()
for bucket in ('player', 'items'):
    for it in inv.get(bucket, []) or []:
        if isinstance(it, dict) and 'id' in it:
            try:
                owned.add(int(it['id']))
            except Exception:
                pass

# 4) shop - broken
shop = http.get('GET /shop/getShopItems', {}).get('body', {})
shop_ok = not (isinstance(shop, dict) and 'error' in shop)

print('Progression-tree item IDs (god source):', len(prog_ids))
print('Season/BP numeric reward IDs found:', len(season_ids))
print('Season awardId strings found:', len(season_award_ids))
print('Currently owned in inventory:', len(owned))
print('Shop catalog usable:', shop_ok)

bp_only = season_ids - prog_ids
prog_only = prog_ids - season_ids
overlap = season_ids & prog_ids
bp_missing_from_inv = season_ids - owned
prog_missing_from_inv = prog_ids - owned

print('\nOverlap progression ∩ season:', len(overlap))
print('In Battle Pass but NOT in progression tree:', len(bp_only))
print('In progression tree but NOT in season scrape:', len(prog_only))
print('BP reward IDs not in current inventory:', len(bp_missing_from_inv))
print('Progression IDs not in current inventory:', len(prog_missing_from_inv))

print('\nSample BP-only IDs (first 30):', sorted(bp_only)[:30])
print('Sample BP awardIds (first 20):', sorted(season_award_ids)[:20])

# season unlock flags currently set?
print('\nSeason top-level keys:', sorted(seas.keys())[:40])
for k in ('currentTier', 'tier', 'level', 'ownedTiers', 'premiumUnlocked', 'isPremium', 'premium', 'battlePass'):
    if k in seas:
        print(f'  seas[{k}] =', seas[k])
if 'supportedBattlePasses' in seas:
    print('  supportedBattlePasses count:', len(seas['supportedBattlePasses']))
    bp0 = seas['supportedBattlePasses'][0] if seas['supportedBattlePasses'] else {}
    if isinstance(bp0, dict):
        print('  first BP keys:', list(bp0.keys())[:25])
