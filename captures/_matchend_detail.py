import re
from pathlib import Path

# What is "Scoreboard" in endpoint logs?
for f in [
    Path(r'F:\Dev_Work\GameDev\WW3\windows\record_logs\endpoint.prod.wishlist.server.fxgam.es.log'),
    Path(r'F:\Dev_Work\GameDev\WW3\LOGS\23July26\WW3_rec_endpoint.prod.wishlist.server.fxgam.es_2026-07-23_03-26-53.log'),
]:
    if not f.exists():
        continue
    t = f.read_text(encoding='utf-8', errors='replace')
    print('===', f.name, 'Scoreboard contexts ===')
    for m in re.finditer(r'.{0,80}Scoreboard.{0,120}', t):
        print(re.sub(r'\s+', ' ', m.group(0))[:250])
        print('---')

# LevelUp contexts in 1August26
f = Path(r'F:\Dev_Work\GameDev\WW3\captures\1August26\meta.prod.ww3.fxtools.gl.log')
t = f.read_text(encoding='utf-8', errors='replace')
print('\n=== LevelUp contexts (1Aug) ===')
for i, m in enumerate(re.finditer(r'.{0,100}LevelUp.{0,200}', t)):
    print(re.sub(r'\s+', ' ', m.group(0))[:300])
    print('---')
    if i >= 4:
        break

# Hub: any match end / leave / summary RPC
for f in [
    Path(r'F:\Dev_Work\GameDev\WW3\windows\record_logs\hub.log'),
    Path(r'F:\Dev_Work\GameDev\WW3\LOGS\23July26\WW3_rec_hub_2026-07-23_03-26-53.log'),
]:
    if not f.exists():
        continue
    t = f.read_text(encoding='utf-8', errors='replace')
    print(f'\n=== hub RPC-ish names in {f.name} ===')
    # collect method-like strings
    methods = set(re.findall(r'"(?:method|type|rpc|name)"\s*:\s*"([^"]+)"', t))
    # also Lobby* CamelCase
    lobbyish = sorted(set(re.findall(r'\b(?:Lobby|Match|Server|Player)[A-Za-z0-9_]{3,}\b', t)))
    print(' lobby/match identifiers:', [x for x in lobbyish if re.search(r'(End|Summary|Score|Reward|Result|Leave|Finish|Complete|XP)', x, re.I)][:40])
    print(' sample methods:', sorted(methods)[:40])

# Aug3: sequence around XP change — what HTTP calls happen between XP values?
f = Path(r'F:\Dev_Work\GameDev\WW3\captures\3Aug27\WW3_rec_meta.prod.ww3.fxtools.gl_2026-08-03_12-29-02.log')
t = f.read_text(encoding='utf-8', errors='replace')
print('\n=== Aug3 timeline: HTTP requests near profileNew with rising XP ===')
# find each profileNew and XP in nearby response
for m in re.finditer(r'>>> GET /profileNew/[^\s]+', t):
    window = t[m.start(): m.start()+5000]
    xp = re.search(r'"playerSeasonExperience"\s*:\s*([0-9.]+)', window)
    lvl = re.search(r'"playerSeasonLevel"\s*:\s*(\d+)', window)
    ms = re.search(r'"matchSummary"\s*:\s*\{[^\}]*\}', window, re.S)
    print(f'  profileNew @ {m.start()}: XP={xp.group(1) if xp else "?"} lvl={lvl.group(1) if lvl else "?"} matchSummary={ms.group(0)[:120] if ms else "no"}')

# All distinct >>> paths in Aug3 meta during that session
print('\n=== ALL distinct request paths in Aug3 meta session ===')
paths = sorted(set(re.findall(r'>>> (GET|POST|PUT|DELETE) ([^\s]+)', t)))
for p in paths:
    print(' ', p[0], p[1])
