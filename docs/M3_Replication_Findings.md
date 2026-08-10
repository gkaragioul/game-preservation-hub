# M3 — Map load & actor replication: findings + scope

Decoded from `captures/24July26/W3_match_full_2.pcapng` with the M2 codec (`control_channel.py`).
This is where the connection goes from "logged in" to "in the world" — and it's the deep half
of UE4 netcode (actor channels, NetGUID/PackageMap, RepLayout property serialization).

## The join → replication sequence (observed)

```
[12] S->C  NMT_Welcome   level=/Game/Maps/Main/Dunhuang_v3/WW3_Gobi_New_P
                         game =/Game/Blueprints/GameModes/BP_DominationNewbie_GameMode_01_01...C
                         redirect="DOM_N"                         (gameMode 47 = Domination-Newbie)
     ... client LOADS the map locally (seconds; only tiny keepalives flow, pkts [18..~170]) ...
[14] C->S  NMT_Netspeed 100000  + NMT_Join                        (client asks to spawn)
[179] S->C  first HEAVY replication packet (671B, channel 2 OPEN bunch, 3257 bits):
              PlayerController  BP_WW3_DominationPlayerController_01
              HUD               BP_WW3DominationHUD
              PersistentLevel / InGameCustomizationDataManager
[180][181] S->C  level streaming: every Dunhuang sublevel registered as a NetGUID
              (WW3_Dunhuang_Terrain / Foliage / Buildings / Spawns / Gameplay_DOM / ...)
[182] S->C  player pawn  BP_PlayerPawn_01 ; PlayerStrikesManager ; "WW3Server - prod-213.183.62.18"
```

So on **NMT_Join**, the server does `SpawnPlayActor` and starts replicating: the GameMode/HUD,
the **PlayerController** (owned by this client), the streaming levels, then the **player Pawn**.

## M4 ownership bootstrap (capture order)

From `real_replay_stream.json` (Gobi / Domination-Newbie):

| Stream idx | Ch | What |
|---|---|---|
| 0–1 | 2 | PlayerController open (exports + RepLayout) |
| 2–9 | 2 | PC follow-up bunches (large partials) |
| **10–11** | **3** | **`BP_PlayerPawn_01` open — same location as PC** |
| 14–17 | 4–5 | Weapons (Glock) |
| 18+ | 6+ | PlayerStates / bots / world |

Default server path after Join: curated **ownership bootstrap** (`ownership_bootstrap.json`) —
PC → HUD → streaming → **Pawn first** → PC↔Pawn → pawn-ref PC RPCs → local weapons →
**local PlayerState NetGUID 9362** → GameState (+ follow-ups 215/275).
WW3 `Client Synchronization` requires Controller, PlayerState, Inventory/Attachments,
GameState, MapLevels before leaving LOADING MAP. Ambient bots via `WW3_AMBIENT_LIMIT`
(default 120; use `0` while debugging loading). Override with `WW3_BOOTSTRAP=full`.

## Real class paths (what the server must replicate)

| Role | Package / class |
|------|-----------------|
| Level (Welcome) | `/Game/Maps/Main/Dunhuang_v3/WW3_Gobi_New_P` |
| GameMode (Welcome GameName) | `/Game/Blueprints/GameModes/BP_DominationNewbie_GameMode_01_01...C` |
| PlayerController | `/Game/Blueprints/Player/Controllers/BP_WW3_DominationPlayerController_01` |
| Player Pawn | `/Game/Blueprints/Player/BP_PlayerPawn_01` |
| HUD | `/Game/Blueprints/HUD/BP_WW3DominationHUD` |
| Managers | `InGameCustomizationDataManager`, `PlayerStrikesManager` |

Class paths appear as **FStrings** the first time an actor/class is seen — that's UE4's
NetGUID/PackageMap **export**: the server assigns a NetGUID to each object and sends the path
once; afterwards it's referenced by the small integer NetGUID. Confirmed on the wire.

## DECODED (2026-07-24): NetGUID exports + SerializeNewActor

Implemented in `match_server/netguid.py` (decodes the real capture; run it directly).
Actor bunches now parse cleanly since the ChType fix (`ChType=2` = Actor, per-channel
ChSequence restarting at InitOutReliable+1 for each new channel).

**Partial-bunch reassembly:** an actor's initial state spans partial bunches
(`bPartial` + `bPartialInitial` / `bPartialFinal`). Packet [179] channel 2 = 3257 + 1067 bits
→ one 4324-bit message. The NetGUID export block occupies exactly the first partial bunch.

**Bunch with `bHasPackageMapExports=1` starts with ReceiveNetGUIDBunch:**
```
bit   bHasRepLayoutExport      (0 = NetGUID exports; 1 = net field exports)
i32   NumGUIDsInBunch          (= 6 in the observed PlayerController bunch)
N x   InternalLoadObject
```
**InternalLoadObject:**
```
packed NetGUID
if NetGUID == 0: return                      -- terminates the outer recursion
u8 ExportFlags        ONLY inside an export block (or NetGUID == 1, the "default")
      bit0 bHasPath   bit1 bNoLoad   bit2 bHasNetworkChecksum
if bHasPath:
    InternalLoadObject(...)                  -- the OUTER object, recursive
    FString PathName
    if bHasNetworkChecksum: u32
```
Reading the ExportFlags byte *outside* an export block eats 8 bits that aren't there and
desyncs everything downstream — that's the one subtlety.

**NetGUID parity:** ODD = static (path-loadable asset), EVEN = dynamic (runtime-spawned).

The real export tree from the capture (the PlayerController being spawned for our player):

| NetGUID | Path | Outer |
|---|---|---|
| 15 | `/Game/Blueprints/Player/Controllers/BP_WW3_DominationPlayerController_01` | — |
| 13 | `Default__BP_WW3_DominationPlayerController_01_C` (archetype) | 15 |
| 9 | `/Game/Maps/Main/Dunhuang_v3/WW3_Gobi_New_P` | — |
| 7 | `WW3_Gobi_New_P` | 9 |
| 5 | `PersistentLevel` | 7 |
| 9364 / 9366 / 9368 / 9370 | AntiCheatComponent / SquadManagerRequester / WorldPositionMarkersManager / InGameCustomizationDataManager | 9360 (the actor) |

**SerializeNewActor** (immediately after the export block, NOT in export mode):
```
InternalLoadObject -> actor NetGUID          (9360, dynamic)
if dynamic:
    InternalLoadObject -> archetype          (13 = Default__BP_..._C)
    InternalLoadObject -> level              (5  = PersistentLevel)
    bit bSerializeLocation  [+ FVector]      (=1 in the capture)
    bit bSerializeRotation  [+ FRotator]     (=0)
    bit bSerializeScale     [+ FVector]      (=0)
    bit bSerializeVelocity  [+ FVector]      (=0)
```
After that header, ~1031 bits remain = the replicated properties (content blocks / RepLayout).

## DECODED: packed vectors, content blocks, RepLayout stream

Implemented in `match_server/actor_channel.py` (run it directly — self-test over the capture).

**`FVector_NetQuantize10` = `SerializePackedVector<10,24>`:**
```
SerializeInt(Bits, 24)                     -- 5 bits
3 x SerializeInt(comp, 1 << (Bits+2))
value = (comp - (1 << (Bits+1))) / 10
```
Verified: the captured PlayerController spawns at **(-1787.0, -10060.0, -562.5)** — plausible
world centimetres, and the `.5` confirms the ÷10 quantisation.

**Content block** (repeats until the bunch payload is consumed):
```
bit   bHasRepLayout
bit   bIsActor            (1 = the channel's own actor, 0 = a subobject)
if !bIsActor: packed NetGUID + subobject header      <-- [OPEN] tail not pinned
packed NumPayloadBits
<NumPayloadBits bits>
```
Confirmed by **exact** consumption on many complete bunches across many channels, and at
scale: **1618 actor content blocks parsed** from one capture, 1410 carrying RepLayout payloads.

**RepLayout property stream** (the payload when `bHasRepLayout=1`):
```
repeat:  packed Handle ;  if Handle == 0 -> end ;  <property bits>
```
Confirmed by the packed-0 terminator and by **width consistency**: the same handle carries the
same width across different channels of the same class (handle 38 → 57 bits, handle 56 → 49
bits, every observation). Handles whose observed widths differ (e.g. 10 → 3 bits on ch3/ch31
vs 19 on ch22) indicate either multi-property payloads or channels of a *different* class —
which is exactly the signal used to group channels by class.

## MINED: per-class RepLayout property tables

Tool: `match_server/mine_replayout.py` (reproducible; writes `replayout_table.json`).

Pipeline: track each actor channel's lifetime (**open → close**, so a reused channel index
can't pollute another class), learn the channel's class from the archetype in its open
bunch, collect the `bIsActor` RepLayout payloads, then solve each property's bit width —
unknown handles are assumed final (`width = remaining − 8`) and the **minimum** candidate is
taken. Validation re-parses every payload requiring **ascending handles** and **exact
termination** on the packed-0, then prunes handles never exercised by a valid parse.

Over 2 captures: **43 classes, ~397k payloads, 22 classes profiled**.

| Class | Validation | Result |
|---|---|---|
| `HVTMarkerComponent` | **100.0%** | solved — `{10:3, 49:8, 60:382, 65:8}` |
| `MovementComponent` | **98.5%** | solved — `{14:25, 32:73, 41:8, 42:16, 45:32, 46:81, 68:9, 72:18, 82:9, 90:10}` |
| `BP_ProjectileCarpetBombingJdam_01_C` | 82.3% | partial |
| weapon/projectile classes | 51–66% | partial |

**Why the complex classes plateau — measured, not assumed.** Instrumenting *where* parses
fail shows the failures are **concentrated**, not diffuse: 2–3 handles account for **82–90%**
of all failures, and the mode is `NON_ASCENDING` (after consuming the assumed width the next
read isn't a valid handle). The same handles — **54, 32, 98** — dominate failures across
different classes, i.e. shared base-class properties.

That is the signature of **variable-width properties** (dynamic arrays, strings,
conditionally-serialised struct members). No fixed-width table can represent them, so the
remaining ~40% needs per-property **type** knowledge rather than more samples. Simple
fixed-width classes solve completely, which is consistent with this.

## Still to do for M3

Actor channels are the same bunch framing as M2 (already reversed) but the **payload** is the
hard part. To implement, in order:

1. **Actor-channel bunch header** — like the control bunch, but the open bunch serializes the
   channel **ChName = "Actor"** (not the control 5-bit constant). Reverse it from pkt [179]
   (channel 2, bOpen=1) the same way the control ChName was reversed.
2. **NetGUID / PackageMap export** — assign NetGUIDs; serialize the object/class path FString on
   first use, then the packed NetGUID after. (`FNetGUIDCache` / `UPackageMapClient`.)
3. **Actor spawn header** in the open bunch — NetGUID + class NetGUID + initial location/rotation
   (`SerializeNewActor`).
4. **RepLayout property replication** — per class, the replicated properties in RepLayout order
   with the changelist/handle encoding. This is **WW3-class-specific** and the bulk of the work
   (PlayerController, GameState, PlayerState, Pawn each have their own property set).
5. On **NMT_Join**: open the PlayerController channel, replicate it + GameState, then the Pawn (M4).

## Honest status / dependency

M1 (handshake) and M2 (control channel) were validatable **byte-for-byte against the capture**
because the client SENDS those messages — we reproduce and diff. M3 is the opposite: the SERVER
sends replication, and the only proof it's correct is a **real client accepting it and spawning**.
That needs live-client iteration (client pointed at our `server.py` via the M2 handoff). So M3 is:
- **RE-able now** (decode the captured server replication to learn the exact format) — started here.
- **Completable only with a live client** to iterate against — the key practical dependency.

It is also genuinely large (RepLayouts for many WW3 classes) and is the point where a UE4-networking
specialist is warranted. The framing, join trigger, and real class/map values are in place; the
next concrete step is reversing the actor-channel open bunch (ChName "Actor" + SerializeNewActor)
from packet [179].
