# Project Status

Last updated: 2026-08-02

> **On the evidence cited below.** Screenshots and captures under
> `research/` are deliberately not published: they are frames of the client
> and belong to the rights holder. The file names are kept so a preservation
> host can check each claim against its own recordings. See `NOTICE`.

## Direction

A **Chinese-primary local/offline revival** for one accepted Windows host. The
English/international build stays a reference selection, not a completion gate.

```text
中文     -> Chinese 9game build, package com.dianhun.lxys.aligames
English  -> International/global build, package com.oversea.spinarena
```

## Accepted operator platform

64-bit Windows 11 under a 64-bit Windows PowerShell 5.1 Desktop process.
`dist\launcher.ps1` is the sole supported entry point. There is no supported
Linux, macOS, WSL or PowerShell 7 launcher.

Verified on this host: Windows 11 Pro build 26200, x64, PowerShell 5.1 Desktop,
CPython 3.12.10 with zlib 1.3.1, WHPX usable, AVD `SpiralWarrior_API30_X64`.

## Live acceptance run — 2026-07-30

A single session from `dist\launcher.ps1 -Edition cn -Capture` reached the
lobby, completed an Adventure battle, and reloaded the result after restart.

| Step | Evidence |
| --- | --- |
| Boot without the protobuf crash | 0 `invalid wire type` in `research/launch_logcat/20260730-025933-551-cn-windows-local.log` |
| Area discovery accepted | client shows 海之国1服 green/推荐; `http 接收(56):CMgBEgJvax...` |
| Logic token issued | `GET /auth/es?account=100000001&...` → 200 |
| WebSocket bootstrap | journal `recv 1111` → `send 1, 2, 5, 129` |
| Lobby rendered with the local account | `research/screenshots/20260730-065000-cn-lobby-reached.png` |
| Adventure entered, key spent | `recv 181` → `send 5, 1, 180`; `roguelike_keys` 1 → 0 |
| Story node and event branch | `recv 182` loc 10003 event 110000, then 110005; `recv 184` trigger |
| Battle node entered | `recv 182` loc 20004 event 110001 |
| Battle fought and won | `research/screenshots/20260730-072800-cn-battle-victory.png` (VICTORY 1:2) |
| Result validated and persisted | `recv 184` → `send 5, 1, 180`; `battle_wins 1`, tops `0/0/4060`, rewards granted |
| Restart reloads the run | gateway pid 20656 → 20036 plus app restart; `research/screenshots/20260730-074200-cn-restart-restored-run.png` |
| RogueLike misc operations served | `recv 183` (GiveUpMap) → `send 5, 180`; client rendered its own end-of-run summary |
| **Postbattle chip claim** | 选择增强模组 shown (`research/screenshots/20260730-104600-cn-chip-selection.png`); `recv 184` loc 20002 → `send 5, 180`; `pending_battle_reward` True→False, `event_buffs {4226: 1}`, node 20002 status 2→3 |
| **Restart after the claim** | gateway pid 22116 → 4000 plus app restart; save digest `41ca88b4...` identical; map redraws the completed node, tops `0/0/2591`, BUFF counter 1 (`research/screenshots/20260730-105900-cn-restart-after-claim.png`) |

The saved profile digest was identical before and after the restart, and the
client redrew the same node states and top HP.

## Chapter cleared end to end — 2026-08-02

The prologue chapter 最初课程 was completed in a single live run: every node
kind on the map was entered and resolved, the chapter boss was defeated, and
the map finished 8/8.

| Step | Evidence |
| --- | --- |
| Run started, ceiling recorded | `recv 181` -> tops `(3095, 4071, 4560)` stored as both hp and max_hp |
| Starter chip branch | `recv 182` loc 10003 event 110019 carrying **no** exports; gateway supplies the declared list; claim -> `event_buffs {4223: 1}` |
| Battle 20004 | `recv 182` event 110001 exports `[100003, 100001, 100002]`; won; chip `4222` claimed |
| Battle 30002 | `recv 182` event 110017; won; chip `4205` claimed |
| Repair 30001 - revive | `recv 184` event 110002, top 2 marked `[1]` at hp **815** = `ceil(4071 x 0.2)` |
| Repair 40004 - heal | `recv 184` event 110002, top 2 marked `[1]` at hp **2444** = `815 + ceil(4071 x 0.4)` |
| **Boss 50003 defeated** | `recv 182` event 110018 with its four declared exports; `recv 184` -> `send 5, 1, 180`; node status 3, `battle_wins 3`, no pending claim (`research/screenshots/20260801-boss-victory.png`) |
| Chapter cleared | 通关成功, 探索 7/8, 战胜 3 (`research/screenshots/20260801-chapter-cleared.png`) |
| Restart reloads the post-boss run | emulator and client restarted, gateway pid 48652; save digest `1d2eb4d1...` identical before and after |
| Reward chest 40005 | `recv 184` event 110003, exports permuted; items `2028x2, 2004x2, 1227894833x500` granted and shown by the client |
| Map complete | every node grey, 8/8 (`research/screenshots/20260802-chapter-complete-map.png`) |

## What exists

- Launcher and runtime contract
  - `dist/launcher.ps1` — `-Doctor`, `-Capture`, `-RestartGateway`, `-SkipInstall`
  - `tools/windows_runtime.ps1` — read-only host/Python/OpenSSL/artifact status
  - `tools/bootstrap_android.ps1` — repeatable JDK/SDK/API-30/AVD install
- Local services
  - FastAPI gateway on `10.0.2.2:23101` (discovery, `/auth/es`, `/ws`, profile)
  - Explicit proxy edge on `8888` with offline deny-by-default
- Artifact derivation
  - `tools/build_cn_userca_apk.py` — reproducible runtime APK from `cn_9game.apk`
  - `tools/cn_client_patch.py` — source-anchored offline patches
  - `tools/cocos_jsc.py` — deterministic Cocos `.jsc` unpack/repack
- Research outputs under `research/` (see `research/runtime/README.md`)

## Derived artifact contract

```text
source   cn_9game.apk                          4e02fbc9...c77358d5
runtime  patched/LuoXuanWarrior_cn_partsuit_userca_debug.apk
                                               34179558...42415414
```

The runtime APK differs from the immutable source in exactly two members:

```text
res/xml/lebian_network_security_config.xml     be19b194...7107cec4
assets/assets/main/index.jsc                   0770fe5f...ec050880
```

## Test status

**352 tests, all passing** (`server\.venv_win\Scripts\python.exe -m pytest server\tests -q`).

Run the suite with the live stack stopped. Several launcher tests bind the
real service ports and share `research\runtime\launcher-state.json`, so they
fail intermittently while a launcher session is running.

### Clean-checkout verification — 2026-08-02

A fresh `git clone` with none of the external preservation inputs present was
provisioned only from committed files:

```powershell
py -3.12 -m venv server\.venv_win
server\.venv_win\Scripts\python.exe -m pip install -r server\requirements-win-py312.lock
server\.venv_win\Scripts\python.exe -m pip install -e server
server\.venv_win\Scripts\python.exe -m pytest tests -q -m "not preservation_artifact"
```

Result: **337 passed, 15 deselected**. The 15 deselected are the
`preservation_artifact` tests that need the untracked APK, extracted tree and
Android toolchain.

The working tree carries no preservation input - the largest tracked file at
HEAD is a 206 KB plan document - but the *history* still contains the large
objects committed before the boundary was repaired, so a fresh clone
transfers about 3.4 GB. Rewriting that history is a separate, destructive
decision and has not been taken.

## What remains

- `RL_MiscOpr_Diamond` (7), the paid revive offered after a lost battle, is
  refused at the parser: the client sends only `OprType` and no
  `RogueLikeVersion`. Declining the revive is the supported path.
- Net IDs 144, 146, 159, 217 and 288 are journalled but unanswered. None of
  them blocks anything observed so far.
- Only the prologue chapter (`BelongChapter == -1`) is modelled. The committed
  event and export tables cover that chapter; later chapters need the same
  extraction.
- The English/international edition remains reference-only.
- Public distribution of patched APKs or assets is out of scope without
  rights-holder permission.

## Next command

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File dist\launcher.ps1 -Edition cn -Capture
```
