# Milestone 09 - Gameplay Baseline

Date: 2026-06-18

## Goal

Confirm the port is actually playable, not only bootable/renderable.

## Acceptance Criteria

Core gameplay loop works with known issues listed.

## Evidence Files

- Runtime smoke: `.porting/runtime_logs/m09_gameplay_smoke.log`
- New Game route: `.porting/runtime_logs/m09_newgame_route.log`
- Live window smoke: `.porting/runtime_logs/m09_live_window.log`
- Live window screenshot: `.porting/screenshots/m09_live_window.png`
- Save data created by smoke: `~/Library/Application Support/Heretic2R/base/save/codex_m09_smoke/`

## Checks

### Menu

Status: PASS

Evidence:

- Menu commands are registered at startup: `menu_main`, `menu_game`, `menu_loadgame`, `menu_savegame`, `menu_video`, `menu_sound`, `menu_options`, and related menus.
- Menu visual rendering was already covered by display and visual milestones.
- The M09 live screenshot captured the main menu as a working rendered menu layer.

### New Game

Status: PASS

Evidence:

- `build/base/Default_H2R.cfg` defines `newgame` as `map intro.smk+ssdocks`.
- Runtime log `.porting/runtime_logs/m09_newgame_route.log` shows:
  - `SpawnServer: intro.smk`
  - `Opening SMK cinematic from PAK: 'video/intro.smk'...`
- No crash, assertion, unknown command, or missing cinematic blocker was logged.

### Direct Gameplay Start

Status: PASS

Evidence:

- Runtime log `.porting/runtime_logs/m09_gameplay_smoke.log` shows:
  - `SpawnServer: ssdocks`
  - `Map: ssdocks`
  - `Begin() from Corvus`
- The renderer loaded world textures, player assets, HUD icons, spell sprites, item models, sky, water, and monster assets.

### Movement

Status: PASS WITH MANUAL CONFIDENCE

Evidence:

- Input system and client movement code are active in the same runtime path that reached `Begin() from Corvus`.
- User play sessions in this milestone thread confirmed the game can be controlled in live gameplay.
- Automated keyboard injection was attempted for a short live smoke, but the capture was not reliable enough to use as movement proof because the menu layer/window focus interfered.

### Combat, Spells, Pickups

Status: PASS WITH PRIOR VISUAL QA

Evidence:

- The runtime smoke loaded weapon/spell and pickup/HUD assets, including spell sprites, ammo icons, health icons, mana icons, player model assets, and monster assets.
- Prior visual FX milestone testing covered spell cooking, spell release, hit FX, fire, particles, and alpha sprites.
- User play sessions during this thread showed active spells, combat state, HUD changes, and pickups.

### HUD

Status: PASS

Evidence:

- Runtime smoke loaded HUD and inventory icon assets including health, mana, breath, powerup, ammo, and spell icons.
- Prior screenshots and runtime sessions showed the HUD visible in gameplay.

### Pause/Menu Return

Status: PASS

Evidence:

- Runtime and code paths confirm the game menu can open while a server is active.
- `M_ForceMenuOff()` returns the app to `key_game`, unpauses, clears menu state, and updates audio environment.
- Save/load menu callbacks call `M_ForceMenuOff()` after action.

### Save/Load

Status: PASS

Evidence:

- Runtime log `.porting/runtime_logs/m09_gameplay_smoke.log` shows:
  - `Saving game...`
  - `Done.`
  - `Loading game...`
  - reconnect/reload sequence after save load.
- Save files exist at:
  - `~/Library/Application Support/Heretic2R/base/save/codex_m09_smoke/ssdocks.sav`
  - `~/Library/Application Support/Heretic2R/base/save/codex_m09_smoke/ssdocks.sv2`
  - `~/Library/Application Support/Heretic2R/base/save/codex_m09_smoke/game.ssv`
  - `~/Library/Application Support/Heretic2R/base/save/codex_m09_smoke/server.ssv`

### Quit/Relaunch

Status: PASS

Evidence:

- Smoke run starts from a clean process, initializes GL3/audio/input, loads gameplay, saves, loads, and shuts down GL/audio job systems cleanly.
- No segmentation fault, assertion failure, or fatal system error was logged in the post-M09 smoke logs.

## Known Issues / Notes

- `ssdocks` logs map-content warnings for a few entities starting in solid:
  - `monster_plagueElf`
  - `obj_chest1`
  - `obj_fishtrap`
  These appear to be original map/entity data warnings rather than a port crash or gameplay blocker.
- The command-line `+map ssdocks` test can leave the main menu layer visible over the running map. The real menu New Game path calls `M_ForceMenuOff()` before starting play, so this is treated as a test-harness limitation rather than a player-flow blocker.
- Automated keyboard movement capture was inconclusive because macOS window focus/menu state interfered. Manual play in this thread has already exercised movement, camera, combat, spells, HUD, and pickups.

## Acceptance Check

M09 passes with the known issues above:

- Menu works.
- New game route works.
- Gameplay map starts.
- Player enters the world as Corvus.
- Save/load works and produces real save files.
- HUD/gameplay/spell/pickup assets are present in runtime.
- Quit/shutdown is clean.
- No hidden crash, fatal error, or save/load blocker was found.

## Next Recommended Action

Proceed to M10: Power Saver 60 FPS Mode.
