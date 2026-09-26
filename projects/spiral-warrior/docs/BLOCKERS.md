# Blockers

Last updated: 2026-07-30

## Scope: playable local/offline prototype

Status: **Complete.** A single live session reaches the lobby, runs the
Adventure through a completed battle, claims the postbattle chip, and reloads
that state after a gateway and app restart. See the evidence table in
`docs/STATUS.md`.

## Resolved: the Cocos boot crash (`invalid wire type 7 at offset 1`)

Status: **Root-caused and fixed.**

For several runs the Chinese client aborted at startup with:

```
ERROR: Uncaught Error: invalid wire type 7 at offset 1
s.skipType@assets/main/index.jsc:20239
e.decode@assets/main/index.jsc:247439
anonymous@assets/main/index.jsc:142586   (PartSuitManager.init)
```

An earlier note in this file claimed the shipped APK contained a corrupted
64-byte `data/PartSuit` table and that replacing it had produced "zero protobuf
errors". Both halves were wrong, and the newest capture at the time still
showed the error loop.

What the evidence actually shows:

- `cn_9game.apk` ships `data/PartSuit`
  (`assets/assets/resources/native/b4/b4bc0aa8-8d49-434e-b2fe-722279cdc129.bin`)
  as a **0-byte** file, SHA-256 `e3b0c442...`. An empty protobuf message is a
  valid empty table and `PartSuitArray.decode()` accepts it.
- The locally rebuilt `patched/LuoXuanWarrior_cn_partsuit_debug.apk` replaced
  that member with **64 bytes** of filler, SHA-256 `92d61472...`. Its first
  byte `0x67` decodes as field 12 / wire type 7, which is invalid.
- A CRC sweep of all **28,909** members showed that table was the *only*
  content difference between the immutable archive and that intermediate, so
  the "partsuit patch" introduced the very bug it was named for.
- The derived runtime APK, and therefore every install, inherited it.

Fix: `tools/build_cn_userca_apk.py` now derives the runtime APK directly from
`cn_9game.apk`. `server/tests/test_runtime_apk_provenance.py` holds the
contract: the runtime APK may differ from the immutable archive in exactly two
members, each pinned by digest.

Live result: **0 occurrences** of `invalid wire type` in
`research/launch_logcat/20260730-025933-551-cn-windows-local.log`.

## Resolved: the gateway rejected every real client login

Status: **Root-caused and fixed.**

`first_text_field` accepted a login payload only if it contained exactly one
length-delimited field. The shipped `CS_LoginNode` carries twelve declared
fields; the client always sends eleven of them. Every unit test built a
synthetic single-field payload, so the incorrect contract passed the entire
suite while no real client could ever authenticate.

`parse_login_token` now follows the field/wire-type table taken from the
generated encoder in the decrypted bundle and still refuses undeclared fields,
wrong wire types, duplicates and truncation.

## Resolved: the lobby threw before rendering

Status: **Root-caused and fixed.**

`updatePlayerExp` reads `levelDataManager.getItem(getPlayerLv()).MaxExp`, and
`getPlayerLv()` returns `BaseInfo.PlayerLevel` — field **70**, not the `Level`
counter at field 3. With field 70 absent the lookup returned null and the HUD
threw `Cannot read property 'MaxExp' of null`. `build_base_info` now sends
`PlayerLevel` (70) and `PlayerExp` (72).

## Resolved: the retired account SDK blocked the logic token

Status: **Bypassed by a source-anchored client patch.**

The 9game/DHUnion SDK cannot initialise against local services. Its telemetry
reports `430000::SDK_CLIENT_LOGIN` with `登录失败：未初始化` ("login failed: not
initialised") and the JS bridge receives `DHSDK.onLogin false` with an empty
payload, so the client never calls `/auth/es`.

All four SDK init endpoints were reached and answered over MITM'd HTTPS
(`CONNECT_SSL_OK sdk-config.17m3.com`), so this is the SDK's own dead
initialisation rather than a missing local response.

`tools/cn_client_patch.py` rewrites the failed-login callback into a local
guest login. This is the "dead SDK gate" case the design explicitly allows.

## Resolved: the RogueLike misc operations, and where the claim really lives

Status: **Implemented, tested, and live-verified.**

A detour is recorded here because it cost time: the claim was briefly assumed
to run over net **183** (`ECS_RogueLikeMiscOpr`, `RL_MiscOpr_BattleOverSelect`)
because the client sent net 183 right after a battle. It does not. That send
was `GiveUpMap`, and `BattleOverSelect` is dead code in this build (below).
The claim runs over net **184**, exactly as originally designed.

Source-proven contract, from the generated encoder in the decrypted bundle:

```text
net 183  = ECS_RogueLikeMiscOpr
CS_RogueLikeMiscOpr { 1 RogueLikeVersion int32, 2 MiscOpr, 3 chapterId int32 }
RogueLikeMiscOpr    { 1 OprType int32, 2 param int32 }

RogueLikeMiscOprType        ERogueLikeCode
  1  ExchangeKey              50  ExchangeKeySuccess
  2  GiveUpMap                60  GiveUpMapSuccess
  3  BattleOverSelect         61  BattleOverSelectSuccess
 14  BattleFailed
```

`/ws` now handles three operations and still refuses everything else:

- **BattleOverSelect (3)** claims the chip: validates `param` against the
  20-key EventType-10 pool, applies the pool buff and the healing effect,
  clears the pending reward and answers code 61.
- **GiveUpMap (2)** abandons a run the client cannot resume, answers code 60.
  The key spent on the map is not refunded.
- **ExchangeKey (1)** refills one adventure key and answers code 50. The
  retired service charged from a live price table; the lab grants the key
  rather than inventing a price, because the currency is local-only while the
  code the client checks is the protocol contract.

### `BattleOverSelect` is dead code in this client build

`RogueLike_BattleOverSelect` is **defined and never called** anywhere in
v1.0.348. An exhaustive search over the decrypted bundle finds only the
definition (`main.js:174504`), the enum entry, the result-code entry, and
listeners for the success event — no call site. So the postbattle claim
cannot be driven through net 183 OprType 3 on this build, whatever the
server does.

The reachable chip selection is the `battleChoosePrefab` UI. The map opens it
for a node whose `status === NodeStatus.NodeTrigger`, and `NodeTrigger` is
**2** — exactly the status the gateway writes after a won battle. That UI
then claims through `RogueLike_Trigger_Export_Select` → net **184**, which is
the path `_trigger_frames` already models (status 2 → 3) and which 30 tests
cover. The original design was right; the net-183 handler is extra surface,
not the claim path.

### Resolved: the map version made the client abandon every run

`RogueLikeMap.Version` is a map timestamp, not a counter. The client runs it
through `getRealTime()`, which is `new Date(getDateTime2018() + 1000 *
Version)` with the base fixed at `2018-01-01T00:00:00+08:00`, and
`loadLocalStorage()` abandons the run and resets when that lands before
`minMapVersion` (`1594872e6` ms, 2020-07-16). `checkTimeOver()` reads the same
field plus `getEnterMapKeepHours()` as the 24-hour expiry.

The gateway sent a constant `1`, so every map rendered as 2018 and the client
sent `RL_MiscOpr_GiveUpMap` on its own about two seconds after the map screen
opened, with no user input. `map_version_now()` now assigns real seconds since
that epoch, and the client echoes the value back in every subsequent request.

With that fixed the run survives the battle and the client presents the chip
selection, so **the postbattle claim is live-verified**: see the evidence table
in `docs/STATUS.md`.

### Earlier hypotheses, ruled out

A complete fresh run was played in one session: key refill → enter map →
start node → story node → event branch → trigger → battle node → three
rounds → `recv 184` persisting `battle_wins 1` with `pending_battle_reward`
true. The client sent the win-branch trigger:

```json
{"RogueLikeVersion":1,"TriggerNodeOnce":{"CurNode":{"Location":20002,
 "Event":{"EventId":110001,"LocationExports":[100001,100002,100003]}},
 "TriggerPath":[110001],"NowToyTops":[{"hp":0},{"hp":0},{"hp":3289}],
 "EnergyType":0,"clearNextBattleBuff":1},"chapterId":-1}
```

Then the map scene loaded (`打开界面：RogueLikeUI`) and 1.8 s later, with no
user input, the client sent `RL_MiscOpr_GiveUpMap` and abandoned the run,
logging `roguelike eventType not found`.

Ruled out by source:

- **Run expiry.** `checkTimeOver` treats `RogueLikeMap.Version` as the map
  start time, and a version of 1 would look decades expired — but the whole
  branch is skipped because `chapterId === ROGUELIKE_CHAPTER_PROLOGUE`, and
  that constant is `-1`, our chapter.
- **Losing the battle.** `getRaceEndType()` returns Win when
  `gameEndInfo.length > 1`, and that array gets one entry per round played,
  so a three-round battle reads as a win. The client also took its win branch
  (it sent `Trigger_Export`; the lose branch sends nothing).

The `roguelike eventType not found` line seen alongside it is unrelated and
cosmetic: it is the map icon selector falling through to `node_start` for an
event type it has no sprite for.

## Open: unhandled RogueLike operations

`RL_MiscOpr_Diamond` (7) — the paid revive offered by the 战斗失败 dialog — is
unmodelled, and it is refused at the *parser*: `RogueLike_Diamond` sets only
`MiscOpr.OprType` and leaves `RogueLikeVersion` unset, which
`parse_roguelike_misc_opr` requires. Declining the revive is the supported
path; accepting it closes the socket. Modelling it also needs
`RogueLike_Report_TopStatus`, which follows with `resetHp2Max` and a trigger
carrying **no** event on the node.

Net ID **217** (`ECS_GlobalAllTaskDetail`, sent four times after login) is
unanswered. `process_GlobalAllTaskDetail` only fills a history cache and
removes no loading panel, so it blocks nothing; it is journalled as unknown.

Net IDs **144**, **146**, **159** and **288** are likewise journalled and
unanswered with no observed effect.

## Open: English/international edition

Status: **Reference only.** Unchanged: the international build installs and
launches but its Cocos resource path still needs work. It is not a
playable-MVP completion gate.

## Legal/distribution scope

Status: **Open policy/scope item.**

This workspace is a local research/preservation prototype. Do not distribute
patched APKs or copyrighted assets without permission from the rights holder.

## Resolved: battle nodes are accepted by event type

Status: **Fixed and live-verified for battle nodes. Other node kinds remain
unmodelled.**

`_enter_node_frames` models three node locations only:

```python
request.new_node.location == 3            # start
request.new_node.location == 10003        # story
request.new_node.location in {20002, 20004}   # first battle
```

The prologue map has more: a second battle row, a treasure chest, a
repair/shop node and the BOSS. Clicking any of them is refused, so a run
cannot progress toward 击败BOSS.

### Map structure, from the client's own generator

`createMainPath` builds the main path deterministically, and node ids are
`y * 10000 + x`, which is why the modelled nodes are 3, 10003 and 2000x:

```text
d = 0        pathType Start,  eventType NormalChijiItemEvent   -> id 3
d = 1                         eventType StartEvent             -> id 1000x
d = t-1      pathType Boss,   eventType FinishEvent
(t-1-d) % 3 == 1              eventType SelectEvent
otherwise                     eventType Lv1BattleEvent
```

`ERogueLikeType`: 0 Invalid, 1-4 Lv1..Lv4Battle, 5 FinalBoss, 6 Talk,
7 Select, 8 Reward, 9 Shopping, 10 NormalChijiItem, 11 RareChijiItem,
12 Start, 13 Finish, 14/15 Lv1/Lv2Talk, 16 AfterBossTalk, 17 TalentExp,
18/19 Lv1/Lv2Reward, 20 BattlePassReward, 21 ShopBattle.

A node's `eventType` is not sent by the client; it comes from
`eventData.EventType`, a table lookup on the event id.

### Captured live contract for the next node

Resuming the completed run and clicking the next node produced:

```text
recv 182  roguelike_version 270660814  chapter_id -1  location 30004  event_id 110017
```

That is row y=3, x=4 — a battle node carrying event **110017**, an id the
gateway has never seen (it models 110000 story, 110005/110019 branches,
110001 battle).

### Resolution

The `data/RogueLike` table was decoded. `data/RogueLike` resolves through
`resources/config.json` (path index -> compressed uuid -> `native/<xx>/`), and
`tools/extract_roguelike_events.py` reproduces the mapping. Event **110017 is
a Lv1BattleEvent — the same type as 110001**, only a different id, so the
refusal was purely the hardcoded id and location set.

The prologue is exactly twenty events, committed in
`server/app/protocol/roguelike_events.py`:

```text
110000 Start        110001 Lv1Battle   110002 Select     110003 Reward
110005 Talk         110010-110016 Talk 110017 Lv1Battle  110018 FinalBoss
110019 NormalChijiItem                 110020-110024 AfterBossTalk
```

Entering and resolving a battle now keys on the declared event type and
validates structurally — standing on a completed node, target new, three
distinct exports, and the win offering the exports the node was entered with.

Live: the frame that was refused, `recv 182 location 30004 event 110017`,
now answers `send 5, 180`, the run advances to `nodes {3:3, 10003:3, 20002:3,
30004:1}`, and the client reaches the battle deploy screen.

## Resolved: every node kind on the prologue map

Status: **Fixed and live-verified. The chapter was cleared 8/8 on
2026-08-02.**

Four separate contracts were wrong, each of them refusing a real request and
closing the socket.

### A declared export list is not sent back

`data/RogueLike` gives some events a fixed `ExportIdArray`. `setEvent` fills
those in client side and `getRogueLikeNode` leaves `Event.LocationExports`
empty, so the gateway must look the list up rather than expect an echo. The
starter-chip branch (110019) demanded the three ids back and refused every
real request, stranding the run on the story node.

The declared lists are extracted alongside the event types:

```text
110002 (100018, 100019, 100020)   110016 (100007,)
110019 (100095, 100080, 100090)
```

### A rolled export count is per event, not per kind

`RandomTime` says how many exports the client rolls and sends. A battle rolls
three; **the boss rolls four**. Demanding three of every fightable node
refused event 110018 outright, and the loading panel simply expired.

```text
110001: 3   110003: 3   110017: 3   110018: 4
```

### A Select node names its pick on a top, and heals before sending

`RogueLike_Trigger_Export_Select` clears `Event.LocationExports` and marks the
chosen top with `Buffs = [ExportItemId]`. That id is the only thing naming the
choice, so the gateway resolves it through `data/RogueLikeExport`:

```text
1    RecoverHp  40    4301 ChijiItem 1    4302 ChijiItem 1
```

`setChijiItem` then calls `dealHp(ExportNum / 100, index, true)` *before*
sending, which halves the ratio for a defeated top and rounds up. The gateway
recomputes the same number and refuses a mismatch rather than applying its
own. Live: a defeated 4071 hp top confirmed at **815** — `ceil(4071 * 0.2)` —
and an 815/4071 top healed to **2444**.

### A reward node has no choice

`doTrigger` hands a `RewardEvent` node's whole export list straight back, and
every row is an Item. The gateway grants each one from the table.

### Live evidence — 2026-08-02

| Node | Frame |
| --- | --- |
| story 10003, starter chip | `recv 182` 110019 with **no** exports → gateway supplies `[100095, 100080, 100090]`; claim → `event_buffs {4223: 1}` |
| battle 20004 | `recv 182` 110001 exports `[100003, 100001, 100002]`; win → chip `4222` |
| battle 30002 | `recv 182` 110017; win → chip `4205` |
| repair 30001 | `recv 184` 110002, top 2 marked `[1]` at hp 815 → revived |
| repair 40004 | `recv 184` 110002, top 2 marked `[1]` at hp 2444 → healed |
| **boss 50003** | `recv 182` 110018 exports `[100015, 100017, 100016, 100102]`; `recv 184` → `send 5, 1, 180`; node status **3**, `battle_wins 3`, no pending claim |
| epilogue | AfterBossTalk plays out client side; 通关成功, 探索 7/8 |
| chest 40005 | `recv 184` 110003 exports permuted → items `2028×2, 2004×2, 1227894833×500` |

Screenshots: `research/screenshots/20260801-boss-victory.png`,
`20260801-chapter-cleared.png`, `20260802-chapter-complete-map.png`.

### Diagnosing the next one

The journal now records what a node request actually carried — its exports,
and for a trigger its path and per-top `hp`/`buffs`. A refusal is answered by
closing the socket, so without that the payload had to be guessed and replayed
offline. With it, the starter-chip refusal was a one-line read: the request
carried no exports at all.
