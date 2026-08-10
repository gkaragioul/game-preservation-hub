# Runtime evidence index

Large captures stay out of Git. This index records what each retained run
proves so the claims in `docs/STATUS.md` can be checked against the files on
the preservation host.

## 2026-07-30 — live acceptance

Launcher state and service logs are timestamped `20260730-*` in this
directory. The client log is under `research/launch_logcat/`.

| File | Proves |
| --- | --- |
| `research/launch_logcat/20260730-025933-551-cn-windows-local.log` | Boot with the corrected artifact: 0 `invalid wire type`, area response accepted, `DHSDK.onLogin` reaching `/auth/es` |
| `20260730-025933-551-gateway.stdout.log` | `GET /auth/es?account=100000001&...` → 200 |
| `20260730-040305-263-gateway.stderr.log` | Gateway restarted as a new process, then accepted the post-restart WebSocket login |
| `server/app/saves/runtime/logic-frames.jsonl` | Frame journal: `recv 1111` → `send 1,2,5,129`; `recv 181/182/184` Adventure sequence; unknown IDs journalled, never answered |
| `server/app/saves/runtime/local.json` | Persisted run: `battle_wins 1`, nodes `{3:3, 10003:3, 20004:2}`, tops `0/0/4060`, battle rewards |

## 2026-08-02 — chapter cleared end to end

Launcher state and service logs are timestamped `20260801-*` and `20260802-*`.

| File | Proves |
| --- | --- |
| `server/app/saves/runtime/logic-frames.jsonl` | The whole chapter: `recv 182/184` for the starter chip (110019, no exports), both battles (110001, 110017), both repair stations (110002, marked top with `hp`/`buffs`), the boss (110018 with four exports), and the reward chest (110003) |
| `server/app/saves/runtime/local.json` | Post-clear run: every node status 3, `battle_wins 3`, items `2028:2, 2004:2, 1227894833:500` |
| `20260801-195706-153-gateway.stderr.log` | Gateway restarted as a new process, then accepted the post-boss WebSocket login with an unchanged save digest |

## Screenshots

| File | Shows |
| --- | --- |
| `20260730-065000-cn-lobby-reached.png` | Lobby with the local account (Local Warrior, level, currency) |
| `20260730-070200-adventure-map.png` | Adventure map, three tops at full HP |
| `20260730-072800-cn-battle-victory.png` | VICTORY 1:2 with the exact reward set the gateway granted |
| `20260730-074200-cn-restart-restored-run.png` | After gateway + app restart: same node states, tops `0/3095, 0/4071, 4060/4560` |
| `20260730-104600-cn-chip-selection.png` | The postbattle chip selection (选择增强模组) the client presents once the map version is a real timestamp |
| `20260730-105100-cn-chip-claimed.png` | Map after the claim: node completed, module counted |
| `20260730-105900-cn-restart-after-claim.png` | After gateway + app restart: completed node, tops `0/0/2591`, BUFF counter 1 |
| `20260801-boss-run-map.png` | The run's map before the push: route start -> battle -> battle -> repair -> BOSS |
| `20260801-boss-victory.png` | VICTORY 1:0 against 高阶陀螺手 (recommended power 5829) |
| `20260801-chapter-cleared.png` | 通关成功 — 探索 7/8, 战胜 3 |
| `20260802-chapter-complete-map.png` | Every node grey: 8/8, including the reward chest claimed after a restart |

## Reading the frame journal

Each line records direction, net ID and whether the ID is modelled. A
`"known": false` entry is a message the gateway does not implement; it is
logged and left unanswered rather than given a fabricated success.

A node request also records what it carried: `location_exports`, and for a
trigger its `trigger_path` and per-top `hp`/`buffs`. The gateway answers an
unacceptable request by closing the socket, so those fields are the only way
to tell a permutation from a wrong count — or, as with the starter-chip
branch, from no exports at all.
