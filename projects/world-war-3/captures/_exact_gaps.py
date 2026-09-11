"""Exact remaining gaps — evidence-based."""
import json, re
from pathlib import Path

paths = set()
roots = [
    Path(r'F:\Dev_Work\GameDev\WW3\captures'),
    Path(r'F:\Dev_Work\GameDev\WW3\windows\record_logs'),
    Path(r'F:\Dev_Work\GameDev\WW3\LOGS'),
]
for d in roots:
    if not d.exists():
        continue
    for f in d.rglob('*'):
        if f.suffix.lower() not in ('.log', '.jsonl'):
            continue
        try:
            t = f.read_text(encoding='utf-8', errors='replace')
        except Exception:
            continue
        for m in re.finditer(r'\b(GET|POST|PUT|DELETE)\s+(/[^\s"\'\\]*)', t):
            method, path = m.group(1), m.group(2).split('?')[0]
            key = re.sub(r'/\d{5,}', '/{id}', path)
            key = re.sub(r'/7656119\d+', '/{steamid}', key)
            paths.add(f'{method} {key}')

print('=== A) MENU / HTTPS — still missing captured traffic ===')
menu = {
    'Leaderboards / Scores API': [r'leaderboard', r'/scores', r'getScores', r'ranking'],
    'Notifications data feed': [r'notif'],
    'Match-end summary / XP write': [r'matchSummary', r'ClearMatch', r'DedicatedServer/match'],
}
for name, pats in menu.items():
    hits = [p for p in paths if any(re.search(pat, p, re.I) for pat in pats)]
    print(f'  MISSING  {name}' if not hits else f'  HAVE     {name}: {hits[:5]}')
print('  NOTE     GET /gameSession/get is captured, but that is NOT a match-end XP write')

# replay map coverage for shop etc
rm = json.load(open(r'F:\Dev_Work\GameDev\WW3\mockserver\replay_map.json', encoding='utf-8'))
http = set(rm.get('http', {}).keys())
print('\n=== B) Offline menu replay — already working (not missing) ===')
for k in sorted(http):
    if any(x in k.lower() for x in ['shop', 'season', 'challenge', 'playerstat', 'friend', 'inventory', 'progression', 'profile', 'auth', 'maps', 'gamemode']):
        print(f'  OK  {k}')

print('\n=== C) MAPS — API catalog vs usable match UDP capture ===')
rows = [
    # (internal, mode, player name, status, detail)
    ('WW3_Shibuya_P', 'TDM', 'Shibuya', 'HAVE', 'useful captures'),
    ('WW3_Berlin_Backyards_02_P', 'TDM', 'Berlin Backyards', 'HAVE', 'useful Berlin TDM captures'),
    ('WW3_Warsaw_Shopping_Mall_P', 'TDM', 'Warsaw Shopping Mall', 'HAVE', 'useful Warsaw TDM captures'),
    ('WW3_Moscow_Senate_P', 'TDM', 'Moscow Senate', 'GAP', 'TDM_MoscowSenate.pcapng is JUNK (loopback). moskow TDM.pcapng is good Moscow TDM but NOT proven to be Senate'),
    ('WW3_Landmark_P', 'TDM', 'Landmark', 'DROP', 'not queueable in live game; API leftover only'),
    ('WW3_Berlin_P', 'WAR', 'Berlin', 'HAVE', 'war_Berlin.pcapng'),
    ('WW3_Moscow_P', 'WAR', 'Moscow', 'HAVE', 'war_moscow.pcapng'),
    ('WW3_Warsaw_P', 'WAR', 'Warsaw', 'HAVE', 'war_Warszawa.pcapng'),
    ('WW3_Polarnyj_P', 'WAR', 'Polyarny', 'HAVE', 'war_Полярный.pcapng'),
    ('WW3_DMZ_P', 'WAR/TacOps', 'DMZ', 'HAVE', 'ww3_tacops_DMZ + zips'),
    ('WW3_Tokio_P', 'WAR/TacOps', 'Tokyo', 'HAVE', 'WW3_TacOps_Tokyo_Full_3'),
    ('WW3_Smolensk_P', 'WAR', 'Smolensk', 'MISSING', 'no capture file anywhere'),
    ('WW3_Gobi_New_P', 'DOM', 'Gobi', 'UNCLEAR', 'no Gobi-named capture; Stronghold captures exist and may be related DOM'),
]
for mid, mode, label, status, detail in rows:
    print(f'  {status:8} [{mode:9}] {label:22}  {detail}')

print('\n=== D) OTHER named captures ===')
print('  JUNK     TDM_Instanbul.pcapng — loopback, unusable')
print('  HAVE     Stronghold (ww3_StolongHold / strongHold_2) — useful UDP')
print('  HAVE     Many full-length matches (8–31 min) — NOT missing')

print('\n=== E) FINAL — ONLY what is still actually missing/actionable ===')
print('''
MUST / STILL MISSING (if teammates can still log in today):
  1. Smolensk Warzone — one usable UDP match capture (Wireshark, filter empty or "udp")
  2. Moscow Senate TDM — only if they can confirm that exact map; existing Senate file is junk
  3. One match recorded ALL THE WAY TO THE END (scoreboard + XP screen) — never captured as HTTPS match-end write

NICE / LOW VALUE (probably skip):
  4. Leaderboards API — client never requested it in your offline browse; may not be a real menu screen
  5. Notifications article feed — panel works, content empty; cosmetic
  6. Gobi Domination — only if they can actually queue it
  7. Any rare mode (Breakthrough/GunGame/HVT/etc.) — bonus only

DROP / NOT MISSING:
  - Landmark — not findable, not queueable
  - Offline menu boot — DONE (you are in it)
  - Shop / Career / Challenges / Friends / Battle Pass / Inventory — HAVE
  - Full match recordings in general — HAVE many
''')
