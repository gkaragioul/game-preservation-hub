# M4 — pawn possession blocker: ground-truth findings (2026-08-05)

Goal: get the client past `LOADING MAP` by making it map the pawn's NetGUID (9372) and
send `ServerAcknowledgePossession(Pawn 9372)` instead of `(null)`.

> ## RESOLVED — 2026-08-07 04:09
>
> `ServerAcknowledgePossession(Pawn 9372)` received live
> (`match_server/live_log/session_20260807_040606.jsonl`, ch2 handle 64, 17-bit payload).
> `ServerSetSpectatorLocation` stopped dead at 791 while `ServerUpdateCamera` ran on to
> 10 011, so the client not only possessed the pawn but **kept** it.
>
> The pawn NetGUID was never the problem, and neither was `bHasMustBeMappedGUIDs` (the
> successful run used `mustMap=False`). `ClientRestart` was mis-encoded in two independent
> ways, so `ClientRestart_Implementation` had never once executed:
>
> 1. **Field handle width.** UE 4.21 writes it with `SerializeInt(index, MaxIndex+1)`,
>    which spends bits only while `(WrittenSoFar + Mask) < ValueMax` — a *value-dependent*
>    width. At `ValueMax = 315` handle 39 needs **9** bits; we wrote a flat 8. Every handle
>    a client sends is >= 64 and needs only 8, so the fixed-8 model measured 100% correct
>    on C→S traffic while silently corrupting every S→C `ClientRestart`.
> 2. **Missing Send bit.** `FRepLayout::SendPropertiesForRPC` prefixes each non-out
>    parameter with a bit; an object argument is `1` + packed NetGUID, not a bare NetGUID.
>
> This supersedes fact #6 (pawn-side GUID mapping) and fact #10 (`ClientRestart` produced
> no client reaction) as *causes* — both were downstream of the framing. Fact #10's
> `Ack(null)` was separately shown by `live_log/HANDLE_DERIVE.md` to have been a decode
> artefact. Full derivation in `match_server/live_log/NEXT_EXPERIMENT.md`; live verdict in
> `LIVE_STATUS.md`; regression tests in `match_server/test_possess_rpc.py`.
>
> **Still open:** the UI remains on `LOADING MAP` and `ch3` C→S is empty, so possession is
> no longer the blocker — GameState / level-streaming / pawn-movement setup is. See
> `NEXT_EXPERIMENT.md`.

This note records what was **proven** (with hard evidence, not guesses) in this session,
so future sessions don't re-walk the same dead ends. Tooling added for this investigation
lives in `match_server/_ground_truth_*.py`, `_dump_pawn_export_paths.py`,
`_live_c2s_scan.py`, `_live_pawn_packet_check.py` — all read-only, safe to re-run anytime.

## Method: ground-truth against the ORIGINAL pcap, not just "trust the JSON"

Everything the server replays comes from `real_replay_stream.json`, which was extracted
from `captures/24July26/W3_match_full_2.pcapng` by a one-off script that no longer exists
in the repo. Instead of trusting that extraction blindly, this session re-parsed the raw
pcap directly (`match_analysis/pcap_tools.py` + `control_channel.read_packet`) and
byte-matched specific bunches back to their real datagrams. This closes the "maybe the
JSON extraction lost something" gap that no prior session had ruled out.

## Confirmed facts (new, ground-truthed this session)

1. **`bHasMustBeMappedGUIDs` is genuinely 0 on the real wire** for the pawn open (src 10),
   partial-final (src 11), RepLayout nudges (src 181/192) and clothing export (src 212/213)
   — checked against the actual pcap packets (171, 238/239, 242/243), not inferred.
   `real_replay_stream.json` never captured this field at all (key absent, not just
   defaulted); `build_replay_bunch()` was silently hardcoding 0 regardless. **Fixed** in
   this session (thread `spec.get("bHasMustBeMappedGUIDs", 0)` through) — pure plumbing
   correctness, zero behaviour change today since ground truth is 0 anyway.

2. **The pawn's own `isActor=True` RepLayout block is NOT part of the open bunch** — this
   is normal, not a bug. Reassembling every ch3 bunch across the *entire* real match
   (8565 groups) shows the pawn's own actor-property block first arrives ~67 packets
   *after* the open bunch, as a tiny separate 29-bit update. Our ownership bootstrap
   already includes this exact update (`src=181`/`192`, both 29 bits, `chIndex=3`,
   `bOpen=0`) in the right relative position (after the open, before the clothing/
   InventoryManager export). **Theory "we never send the pawn's own RepLayout" is
   refuted.**

3. **The `212/213` "pawn clothing" bunch's 3rd content block failing to parse
   (`bad: True`) is a decoder limitation, not a wire-format bug.** The identical bytes
   exist in the original capture at pcap packet 242/243 and were accepted by the real
   client (the match played out fine in the original recording). **Theory "clothing
   bunch corrupts the client" is refuted.**

4. **Channel-sequence framing is correct.** `next_chan_seq()` is per-channel (own dict
   entry per `chIndex`), all channels correctly share the same `InitOutReliable` base
   from the handshake cookie, and the pawn channel's first reliable bunch gets
   `ChSequence == init_reliable + 1` exactly as UE4 requires. Checked directly against
   the raw bytes we sent in the currently-live session (`_live_pawn_packet_check.py`),
   not just the intended values — packetization/batching of multiple bunches into one
   datagram also looks correct (ack section, terminators, wraparound at 4096 on ch2 all
   behave as expected).

5. **`WW3_STRIP_EXPORT_CHECKSUM=1` was already tried live** (sessions
   `match_console_20260805_173643/173952`) — checksums were confirmed stripped
   (3201→2849 bits) but the result was still `ServerAcknowledgePossession(null)`.
   **Theory "checksum validation rejects the CDO" is refuted by live test**, not just
   by reasoning.

6. **Both `ClientRestart` MustBeMapped settings were already tried live** (see
   `possess_rpc.py`/`server.py` comments + `session_20260805_153843`/`164147`):
   `must_be_mapped=True` → RPC queued forever, no Ack at all; `must_be_mapped=False`
   (current default) → immediate `Ack(null)`. Both consistent with the same underlying
   cause: **GUID 9372 never gets registered in the client's PackageMap, independent of
   how the `ClientRestart` RPC itself is framed.** The RPC framing is a dead end; the
   real bug is upstream, in why the pawn actor's own channel never fully "takes" on the
   client.

7. **The pawn archetype path is legitimate and known-good.**
   `/Game/Blueprints/Player/BP_PlayerPawn_01` (CDO `Default__BP_PlayerPawn_01_C`) is the
   same class name observed spawning successfully in real matches
   (`analysis/crashes/.../WW3.log`: `"Spawning genkaisyuuraku into BP_PlayerPawn_01_C_0"`,
   2026-07-09, and again in the 24 July capture). **Theory "archetype asset was
   renamed/moved since the capture" is refuted.**

8. **Confirmed live, right now, with a real connected client** (session
   `20260805_181405.jsonl`, 112k C→S datagrams decoded): PC(ch2)=69128 and PS(ch7)=4746
   C→S bunches, **ch3/ch4/ch5 (pawn/weapons) = 0**, matching the reported symptom exactly.
   The connection is healthy (huge steady ch2 traffic) — the client is not hung/crashed,
   it simply never uses the pawn/weapon channels.

9. The `Client Synchronization` debug checklist (`PlayerState`/`InventoryManager`/etc.)
   printed by the game is **not a strict gate** — a genuine working-match crash log
   (`UE4CC-Windows-FBE1EB12469BDEE70E1456911D269857_0000/WW3.log`) shows `PlayerState:
   false` persisting for multiple ticks *while* `InventoryManager`/`WeaponsAttachments`
   independently flip to `true` and the match continues normally. Don't over-index on
   this specific debug string as the LOADING MAP gate condition.

10. **`ClientRestart` on wire handle 9 produces no observable client behaviour at all**
    (live sessions `20260805_194518` and `20260805_195051`, decoded from the session
    JSONL rather than grepped — the console prints `AckPossession(null)` only once per
    connection, so log-line counting cannot answer this). In the second run the RPC was
    sent with `MustBeMapped=0`, so it had to execute on arrival, 1.7 s after the ch3 pawn
    open, which the client had ACKed 15 ms earlier:

    ```
    t=127.913  C->S ServerCheckClientPossession        (client's own)
    t=128.357  C->S ServerAcknowledgePossession(null)  (client's own, BEFORE the RPC)
    t=130.018  S->C ClientRestart(9)
               <nothing, ever>   ch2 C->S = 16163 more bunches, session ran to t=509s
    ```

    `APlayerController::ClientRestart_Implementation` has only two exits: with a resolved
    pawn it calls `AcknowledgePossession(Pawn)`; with a NULL pawn it calls
    `ServerCheckClientPossessionReliable()` and returns. **Neither** was observed. That is
    a stronger statement than fact #6 (which framed the problem as "GUID 9372 never maps"):
    the RPC appears not to run. The leading explanation is that **wire handle 9 is not
    `ClientRestart` in this build's PlayerController ClassNetCache** — that index came from
    string-table ordering calibrated against `ServerAcknowledgePossession=34` and has never
    been confirmed by a dump. Until it is (or until a control test with a provably-resolved
    Pawn argument, e.g. PlayerState `9362`, gets a reaction), every possession experiment
    is resting on an unverified assumption. See
    `match_server/live_log/NEXT_EXPERIMENT.md`.

11. **A MustBeMapped bunch whose GUID never resolves head-of-line blocks the channel.**
    Session `20260805_194518` sent `ClientRestart(MustBeMapped 9372)` first and an
    executable follow-up 8 s later on the same reliable ch2 — the follow-up drew no reply,
    because the queued bunch blocks everything behind it in
    `UActorChannel::ProcessQueuedBunches`. Any future A/B of the two framings must send the
    executable one first; `server.py` now enforces this whenever
    `WW3_CLIENT_RESTART_MBM_FALLBACK_S > 0`.

12. **`ClientRestart` was both mis-numbered *and* mis-framed — it could never have run.**
    (2026-08-06, offline, derived from the Dumper-7 dump of the live build; full write-up
    in `match_server/live_log/HANDLE_DERIVE.md`.) Two separate defects:

    * **Numbering.** `ClientRestart` is wire handle **39**, not 9;
      `ServerAcknowledgePossession` is **64**, not 34. The old table was the real one
      halved, because the decoder read the handle as `SerializeIntPacked` when UE 4.21
      writes it as `WriteIntWrapped(FieldNetIndex, ClassCache->GetMaxIndex()+1)` — a
      fixed-width field, 8 bits on this build. A packed byte `2h` decodes to `h`.
    * **Framing.** The field header is
      `handle | SerializeIntPacked(NumPayloadBits) | payload`. We wrote the handle
      followed immediately by the raw NetGUID and **no length field**, so the client read
      our NetGUID bytes as `NumPayloadBits`, got a payload larger than the bunch, and
      abandoned the field chain without erroring the connection.

    Together these explain fact #10 exactly — silence, on a connection that stays healthy.
    The derivation reproduces **8/8** independent wire anchors with zero error, and the
    corrected framing consumes **105 070/105 070** live C→S blocks exactly (the packed
    model manages 50%). One anchor is confirmed semantically: handle 79's payload decodes
    to `/Game/Maps/Main/Dunhuang_v3/WW3_Dunhuang_Gameplay_New_DOM`, i.e. it really is
    `ServerUpdateLevelVisibility(FName PackageName, bool)`.

13. **The client was never sending `ServerAcknowledgePossession(null)`.** With the fixed
    decoder, handle 64 does not appear *at all* in the stuck session. The line every
    session reported as `Ack(null)` was byte 68 —
    `ServerCheckClientPossessionReliable`, a **zero-argument** RPC whose `NumPayloadBits`
    field (0) was being misread as "argument = 0". What the stuck client actually sends is
    `ServerSetSpectatorLocation` (73) and `ServerUpdateCamera` (78), ~52 500 times each:
    a pawn-less PC sitting in spectator/inactive state. This retires the "why does it ack
    null" line of inquiry entirely — there is no null ack, only an absent possession.

    Consequently facts #6 and #10 need re-reading: **neither** actually tested whether
    GUID 9372 resolves, because no correctly-formed `ClientRestart` was ever delivered.
    The pawn-side theories they were used to refute or support are all back to untested.

## What's still unknown

> **Superseded in part by facts #12–13.** The paragraph below was written when
> `ClientRestart` was believed to be reaching the client. It wasn't. The first task is no
> longer to invent new pawn-side theories but to re-run the experiment with the corrected
> handle (39) and framing, and see which branch of `ClientRestart_Implementation` fires.

With wire bytes, framing, sequencing, checksums and archetype identity all verified
correct/ground-truthed, the remaining explanation is something the passive
network+memory-scan approach can't observe directly, e.g.:
- A client-side precondition for accepting a *dynamic* actor open bunch on a fresh
  channel that isn't purely about bytes (world/streaming state, GameState ordering,
  or something set up over many more bunches than our 30-bunch curated bootstrap sends).
- Something specific to how our dedicated server's connection/session setup differs from
  the captured *listen server* (the capture never sent `ClientRestart` at all — that RPC
  is a necessary invention on our side, not something we can cross-check against a
  capture).

Shipping doesn't write `Saved/Logs` (confirmed — no log files exist under the game's
`Saved/` tree while running), so `scan_sync_status.py`'s live memory scan is the only
client-side signal available, and it only exposes historical log-buffer text, not current
values or PackageMap internals. Getting further likely needs either a debug/development
client build, or attaching a debugger to read `UNetConnection::PackageMap`'s GUID cache
directly to see whether GUID 9372 is even attempted.

## Next attack: stop guessing, read the CLIENT (2026-08-05, later session)

Everything above is server-side reasoning about bytes we send. The reason we kept
running out of theories is that we had **no view of what the client does with them**.
Two client-side channels turned out to already exist and to have been thrown away:

### 1. The client uploads its own UE log to our hub — and we were deleting it

The game runs with `-log -FORCELOGFLUSH -LogCmds=...` and writes **no** file (confirmed
again: the only thing under `E:\...\WW3\Saved\` is a 143-byte `Engine.ini`). But
`analysis/crashes/.../UE4CC-Windows-F39397A045569DF3F76EF58081DD9057_0000/WW3.log`
(a crash forced during *today's* stuck session) shows what it does instead: it batches
its log lines and sends them to the backend over the hub websocket as

```json
{"type":"RpcRequest","context":"debug","method":"log",
 "args":[{"logs":[{"timestamp":"…","msg":"LogTemp: Warning: …"}],"topic":"live.client.global.errors"}]}
```

`LogTemp: Warning`, `LogConsoleManager: Warning` and the `ConnectionTimeout` **Error**
all arrive this way, so the uploader is not restricted to the two categories in the
hub's `logsConfig` — it forwards Warning-and-above generally. That is exactly the
severity UE4 uses for the messages that would answer this whole investigation:

```
LogNet:            Warning: UActorChannel::ProcessBunch: SerializeNewActor failed to find/spawn actor
LogNet:            Warning: UActorChannel::ProcessQueuedBunches: Queued bunches for longer than…
LogNetPackageMap:  Warning: InternalLoadObject: Unable to resolve object from path
LogNetPackageMap:  Error:   Network checksum mismatch
LogNetPartialBunch:Warning: Corrupt partial bunch. Initial partial bunches are expected to be byte-aligned
```

`mockserver/hub_server.py` had a single line — `if not (ctx == "debug" and meth == "log")
# keep debug spam quiet` — that dropped every one of these on the floor. It now records
them (see `WW3_CLIENT_LOG_CAPTURE` in `match_server/README.md`). **No crash, no debugger,
no memory scan needed** — the client has been telling us the answer over an open
websocket the entire time.

The same crash log also proves `-LogCmds=` is honoured by this Shipping build, so the
networking categories can be turned up at launch (`-NetLogCmds`) for detail below Warning.

### 2. We never checked whether the client acks the pawn-open datagram

UE4 acks at the packet layer in `UNetConnection::ReceivedPacket`, but deliberately
**skips** the ack when `UChannel::ReceivedNextBunch` returns `bOutSkipAck` — the
partial-bunch reassembly paths that refuse a bunch without erroring the connection.
`read_packet()` has always parsed the client's ack list; `server.py` never looked at it.
`WW3_ACK_AUDIT=1` now watches the packets carrying ch3/ch4/ch5 bunches. On loopback there
is no real packet loss, so this cleanly splits the remaining search space:

- pawn-open packet **ACKED** → the bytes reached the channel layer intact, and the pawn
  dies later (SerializeNewActor / archetype resolution / queued bunches). Everything
  ground-truthed above stands, and the client log says which.
- pawn-open packet **NOT ACKED** → the client discarded the bunch during reassembly.
  That is a framing fault that bit-comparing against the pcap **cannot** detect, because
  it depends on the client's live per-channel partial state, not on the bytes alone —
  a genuine gap in fact #4 above, which only checked what we *sent*.

## Change made this session

- `match_server/server.py`: `build_replay_bunch()` and `replay_real_spawn()` now thread
  `bHasMustBeMappedGUIDs` from the bunch spec instead of hardcoding 0. No default-behavior
  change (ground-truthed as 0 for everything we currently replay); this only matters if
  `real_replay_stream.json` is ever re-extracted with the real bit, or for hand-crafted
  specs that set it explicitly.
- `match_server/test_m4_spawn.py`: added
  `test_replay_bunch_threads_must_be_mapped_guids` covering default/explicit-0/explicit-1.
- New read-only ground-truth tools (safe to rerun): `_ground_truth_mbm.py`,
  `_ground_truth_pawn_ch3.py`, `_dump_pawn_export_paths.py`, `_live_c2s_scan.py`,
  `_live_pawn_packet_check.py`.

## Changes made in the follow-up session (observability)

- `mockserver/hub_server.py`: records the client's uploaded UE log to
  `match_server/live_log/client_log/client_<ts>.log` (+ `_net.log` sidecar of
  possession/replication lines, also echoed to the hub console as `[CLIENTLOG-NET]`).
  `WW3_CLIENT_LOG_CAPTURE=0` disables. `WW3_CLIENT_LOG_NET=1` (default off) additionally
  asks the client to raise `LogNet*`/`LogSpawn` verbosity through `logsConfig`.
- `match_server/server.py`: `WW3_ACK_AUDIT=1` (default off) watches whether the client
  acks the datagrams carrying ch3/ch4/ch5 bunches. Read-only over acks we already
  receive; no retransmission, no wire change.
- `match_server/watch_client_log.py`: reads/tails the capture and highlights the lines
  that would settle the question.
- `windows/launch_offline.ps1` + `ww3_play_dedicated.ps1`: `-NetLogCmds` appends the
  networking categories to the client's `-LogCmds` and `[Core.Log]`; `-AckAudit` sets
  `WW3_ACK_AUDIT=1`. Both off by default.

### How to run the experiment

1. Restart the hub so the log capture is live (this is the one step that needs it —
   the client reconnects its menu websocket):
   `python mockserver/hub_server.py` (or however the mock stack is normally brought up).
2. Restart the match server with the audit:
   `.\windows\ww3_play_dedicated.ps1 -AckAudit -NoGame`
   (add `-NetLogCmds` and drop `-NoGame` if you also want to relaunch the client with
   verbose networking categories).
3. Start a match (`curl http://127.0.0.1:8701/match`, or matchmake in-game).
4. Watch both sides:
   - `Get-Content (Get-Content match_server\live_log\CURRENT_CONSOLE.txt) -Wait -Tail 40`
     → `[ack-audit] packet N ACKED/NOT ACKED (ch3 OPEN … src=10)`
   - `python match_server\watch_client_log.py --follow`
     → the client's own reason for refusing the pawn.

## RepLayout property blocks: the `bDoChecksum` bit (session of 2026-08-07)

Every attempt to decode actor property blocks — the ch7 483-bit PlayerState open, the
ch2 PlayerController block, the ch3 pawn update — failed the same way: the first handle
looked plausible, then widths drifted and the block never landed on its handle-0
terminator. The cause is a single bit.

`FRepLayout::SendProperties` opens the block with a checksum flag:

```cpp
#ifdef ENABLE_PROPERTY_CHECKSUMS
    Writer.WriteBit( bDoChecksum ? 1 : 0 );
#endif
```

`ENABLE_PROPERTY_CHECKSUMS` is `#define`d unconditionally near the top of
`RepLayout.cpp` — it is not gated on `UE_BUILD_SHIPPING` — so the bit is present in
retail bunches, always 0 because `net.DoPropertyChecksum` defaults off.
`FRepLayout::ReceiveProperties` reads it before the first handle.

Reading from bit 0 swallows that zero into the first `SerializeIntPacked`, and because
`SerializeIntPacked` is little-endian-7-bits-per-byte with a continuation bit, a leading
0 bit **doubles** any handle below 64: the bits for `packed(2h)` and `0 ++ packed(h)`
are identical. So:

| Read from bit 0 | Actually |
|---|---|
| ch7 handle 26 (`EnableTimeAutonomousFightingRobots`) | handle **13** = `AActor::Owner` |
| ch2 handle 10 | handle **5** = `AActor::RemoteRole` |
| `APlayerController::Pawn` = 34 | handle **17** |

This is the *same* halving artefact as fact #12 (`ClientRestart` looking like function
index 9 instead of 39), reached from a different direction. Two independent
"impossible" numbers, one bit.

The `Pawn == 34` anchor had been treated as ground truth and every model was scored
against it, so the search was being steered away from the correct answer. It is retired;
`derive_rep_handles.py` had 17 all along.

### What decodes now

With the bit honoured, plus enum widths from `CeilLogTwo(GetMaxEnumValue())` rather than
8, and `FRootMotionSourceGroup` treated as atomic (it has a native `NetSerialize`):

- **626/626** `ABP_WW3DominationPlayerState_C` blocks exact-consume, including the 483-bit
  ch7 open that this line of work started on.
- **1056/1436** actor property blocks in the whole capture exact-consume; a further 373
  reach a clean handle-0 terminator with a data-bearing tail, which is the custom-delta /
  ClassNetCache chain from `FObjectReplicator::ReceivedBunch`, not RepLayout. Only 7 are
  genuine model failures. 99.5% of RepLayout sections decode.
- Values are semantically right, which matters more than the bit count: `Score = 721.0`,
  player names, Steam IDs, `CurrentGameModeName = 'DOM_N'`, `PS.Owner = 9360`,
  `PS.PlayerCharacter = 9372`.

Decoder lives in `match_server/repblock.py`; `_decode_all_blocks.py` re-runs the
capture-wide score. Any older script that reads a block from bit 0 has been deleted
(`_decode_ch7_open.py`, `_fit_rep_model.py`).

### Bearing on the LOADING MAP checklist

`PlayerState: false` is a **character-local** `LogWW3ClientSynchronization` flag
(`Client Synchronization [ROLE_AutonomousProxy][name]`), with matching
`OnSynchronized:` events on `LogWW3Player`. It is **not** "PC has a PlayerState"
(the header already resolves the name) and **Controller: true** tracks possession
(`GetController()`), which is why Ack(Pawn) alone clears Controller.

`APawn::PlayerState` is handle 17 and `APawn::Controller` is handle 18 on
`ABP_PlayerPawn_01_C`; WW3's Net reverse bind is `AWW3PlayerStateBase::PlayerCharacter`
handle 22 (RepNotify). Capture ch7 open already sets `PlayerCharacter=9372`, but
that lands before the pawn maps. Engine `APlayerState::PawnPrivate` is **not** Net.

Live A/B (2026-08-07):

| Flag | Where | Ack(Pawn 9372) | `PlayerState` checklist |
|------|-------|----------------|-------------------------|
| `WW3_PAWN_SYNTH_PROPS=1` | post-open ch3 bunch before Restart | OK | stays **false** |
| `WW3_PAWN_SYNTH_IN_OPEN=1` | injected into ch3 open (src 11) before SUBs — same order as PC/PS opens | OK | stays **false** |
| `WW3_PS_SET_PLAYERCHAR=1` | post-pawn ch7: PlayerCharacter(22)→9372 before Restart | OK | stays **false** |

Neither direction of the PS↔pawn object bind flips the sync gate; LOADING MAP stays
up. InventoryManager / attachments were the next latch.

### InventoryManager / attachments (2026-08-07)

`InventoryManager` is an `InstancedReference` component (no `Net` on the pointer) —
it replicates as a **stably-named subobject** on the pawn channel (NetGUID **9384**),
not as a pawn RepLayout handle. `CharacterAttachmentManager` is **9374**.

Capture clothing (src 212–213) exact-consumes only when `bStablyNamed=0` content
blocks carry a packed **class NetGUID** before `NumPayloadBits`:

- dynamic hat `9404` / chest `9406`
- then CAM `9374` (705-bit `ReplicatedBatch`, CLOSED decode)
- then IM `9384` (1978-bit preload/inventory; refs weapons **9410/9412**, repair
  **9408**, MSP **9402**)

Those weapon actors open on **ch86/87/88/85** (src 257–262 / 205–206) — outside the
old ownership bootstrap. `WW3_INV_ATTACH=1` adds those opens and re-sends the CAM+IM
payloads as stably-named ch3 blocks before ClientRestart.

Live A/B (2026-08-07 06:34): **Ack(Pawn 9372) OK**, no CHANNEL CLOSE, but
`InventoryManager` / `CharacterAttachments` / `WeaponsAttachments` / `PlayerState`
all stay **false** and LOADING MAP stays up. Opening the referenced actors +
re-sending the clothing CAM/IM tails is ACK-safe and insufficient alone.

### Resend-after-ACK + WAM (2026-08-07 06:53)

Capture fact stronger than “missing WAM batches”: local weapon **opens already
carry** WeaponAttachmentManager RepLayout — ch86 sub **9418** = 505 bits, ch87 sub
**9426** = 457 bits. Later ch86/87 bunches are ammo/FireType, not more WAM.

Shipped flags:

| Flag | Role |
|------|------|
| `WW3_CAM_IM_AFTER_ACK=1` | Hold CAM/IM (and WPN_ATTACH) until clothing + ch85/86/87 ACKED (or timeout) |
| `WW3_WPN_ATTACH=1` | Resend WAM 9418@ch86 + 9426@ch87 after the same gate |
| (drain) | Never batch ch85–88 with ch3/4/5 — MSP+nudges in one datagram skip-acked live |

Live A/B: Restart fires first; CAM/IM held ~2s then `gate=acks`; WAM resend fires;
**Ack(Pawn 9372) OK**; **no NOT ACKED**; checklist still **all four false**; LOADING
uncleared. Timing / WAM resend alone is not the LOADING gate.

### SoftClassPtr + OnSynchronized predicate (2026-08-07)

IM SoftClassPtr is **not** a wire abort. With `FSoftObjectPath` = FString
(`repblock.value_widths`), clothing IM 1978-bit exact-consumes:

- PrimaryGadgetClass → `BP_EquipmentPackInventory_01_C`
- SecondaryGadgetClass → `BP_SemtexC4Inventory_01_C`

Root checklist predicate (working crash `FBE1EB12…`):
`OnSynchronized: Character Attachments` → CharacterAttachments; per-weapon
`OnAttachmentManagerSynchronized` → WeaponsAttachments; InventoryManager flips
in the same tick as WeaponsAttachments. PlayerState can stay false in a live match.

CAM `ReplicatedBatch.ReplicatedAttachments[]` = **9404 + 9406** (hat/chest). CAM/IM-only
resend cannot create those stably=0 dynamics. Shipped
`WW3_CLOTHING_RESEND=1`: after the ACK gate, re-play full clothing src 212–213
(exports + hat/chest + CAM + IM). See `NEXT_EXPERIMENT.md` / `LIVE_STATUS.md`.

### Catalog SoftClass wait → CharacterAttachments (2026-08-07 07:19)

Capture CAM (705-bit, closed) carries more than the two hat/chest NetGUIDs:

| Field | Capture |
|-------|---------|
| `AttachmentIds[]` | 11 uint16s: 1242, 1251, 1260, 1261, 1337, 1386, 2114, 2382, 4425, 6875, 9072 |
| `ReplicatedAttachments[]` | **only** NetGUID 9404 + 9406 |
| `DirectReplicatedSkinsIds.Parts` | 5 skin IDs + 5 ItemTypes |

`OnRep_ReplicatedBatch` resolves the 9 non-channel AttachmentIds (and skins) via
`UWW3ItemDatabase` → `TSoftClassPtr` async load (`MainSkinLoadedClass` /
`PartSkinsLoadedClasses` / mesh SoftClass delegates). Offline those loads never
complete, so `OnSynchronized: Character Attachments` never fires — even when
9404/9406 are mapped and clothing FULL resend is ACK-safe.

Shipped `WW3_CAM_STRIP_CATALOG=1`: after the clothing/CAM-IM ACK gate, send a
CAM-only stably-named block with BatchID=2, empty `AttachmentIds`, empty skins
Parts, still `ReplicatedAttachments=[9404,9406]` (`cam_im_resend.py`).

Live rematch `match_console_20260807_071337`:

| Measure | Result |
|---------|--------|
| Ack(Pawn 9372) | **OK** |
| CAM STRIP | **YES** (276 bits) |
| CharacterAttachments | **true** (heap) |
| IM / WAM / PS | still **false** |
| LOADING MAP | **not** cleared |

Next gate is per-weapon `OnAttachmentManagerSynchronized` (WAM SoftClass /
catalog), which flips InventoryManager + WeaponsAttachments together in the
working crash order.

### WAM catalog SoftClass strip (2026-08-07 07:30)

Capture WAM payloads (ch86 sub **9418** = 505 bits, ch87 sub **9426** = 457 bits)
are SoftClass-only catalogs — **no** `ReplicatedAttachments[]` on the wire:

| Field | Secondary 9418 | Primary 9426 |
|-------|----------------|--------------|
| `AttachmentIds[]` | 9: 101, 151, 304, 4585, 4600, 4606, 4638, 7851, 565 | 8: 295, 143, 526, 346, 432, 108, 39, 7847 |
| `ReplicatedAttachments[]` | none | none |
| `DirectReplicatedSkinsIds.MainId` | 9246 | (not sent) |
| skins Parts | 3×65535 | 3×65535 |

Shipped `WW3_WAM_STRIP_CATALOG=1`: empty WAM AttachmentIds / skins / MainId
(BatchID=2 pattern) in two places (`cam_im_resend.py` / `server.py`):

1. **Open FINALs** (src 258/260) rewritten at send time — BatchID=1 empty catalog
   (805→517 / 757→517 bits) so SoftClass should never arm from the open RepLayout.
2. **Post-ACK** WAM-only blocks on ch86/87 — BatchID=2, 252 bits framed each.

Keeps `WW3_CAM_STRIP_CATALOG=1`.

Live rematch `match_console_20260807_074114` (open strip; prior `072335` was
post-ACK-only):

| Measure | Result |
|---------|--------|
| Ack(Pawn 9372) | **OK** |
| CAM STRIP | **YES** (276 bits) |
| WAM open strip | **YES** (805→517 / 757→517) |
| WAM post-ACK strip | **YES** (252 bits ×2, `open_strip=2/2`) |
| CharacterAttachments | **true** |
| WeaponsAttachments / IM / PS | still **false** |
| LOADING MAP | **not** cleared |

Heap still shows mid-flight `OnAttachmentManagerSynchronized() : 5 - BP_WP_Rail_086…, 4606`
(capture secondary catalog id) even after empty opens. Empty open RepLayout on
ch86/87 alone is necessary but not sufficient — SoftClass was armed earlier.

### SoftClass 4606 armed by early ch4/ch5 Glocks (2026-08-07 08:14)

Ownership bootstrap `(2,17)` opens local Glocks on **ch4/ch5** (src 14–17)
*before* INV_ATTACH ch86/87. Those FINALs carry WAM SoftClass catalogs including
id **4606** (`BP_WP_Rail_086`):

| Channel | Actor | WAM | AttachmentIds |
|---------|-------|-----|---------------|
| ch4 | Glock 8308 | **8314** | 8 ids incl. **4606** |
| ch5 | Glock 7950 | **7956** | 8 ids incl. **4606** |
| ch86 | Glock 9412 | 9418 | 9 ids incl. 4606 (already stripped in open) |
| ch87 | HK417 9410 | 9426 | 8 ids (no 4606) |

Shipped in `cam_im_resend.py` / `server.py` under `WW3_WAM_STRIP_CATALOG=1`:

1. **Open FINALs** src **15/17/258/260** — in-place empty catalog (BatchID=1).
   ch4/ch5 use payload splice (NewActor reader is 3 bits short of content start).
2. **Post-ACK** BatchID=2 empty catalog on ch4/5/86/87 with **keep dynamic**
   `ReplicatedAttachments` = 8312/7954/9416/9424 (stably=0 att after each WAM;
   CAM-style resolvable channel object).

Live rematch `match_console_20260807_081409`:

| Measure | Result |
|---------|--------|
| Ack(Pawn 9372) | **OK** |
| Open strip | **4/4** (1302→1062 / 1287→1047 / 805→517 / 757→517) |
| Post-ACK strip | **276** bits ×4 (`keep dynamic att`) |
| SoftClass 4606 pending | **cleared** (heap hits=0) |
| CharacterAttachments | **false** this rematch (was true under CAM_STRIP alone on earlier run) |
| WeaponsAttachments / IM / PS | still **false** |
| LOADING MAP | **not** cleared |

### WAM strip: omit MainId + FireType keep was wrong (2026-08-07 08:35)

Root findings after SoftClass 4606 cleared:

1. **MainId=0 was capture-unfaithful.** Capture WAM opens omit `DirectReplicatedSkinsIds.MainId`
   on 3/4 channels (only secondary 9418 sent MainId=9246). Stripped payloads were
   forcing MainId=0, dirtying `OnRep_ReplicatedSkinsIds` / `MainSkinLoadedClass`.
   Shipped: **omit MainId** (and omit Num/ReplicatedAttachments when empty) so open
   strip matches early-Glock handle set: BatchID + empty AttachmentIds + empty skins
   Parts. Open bits now 1302→990 / 1287→975 / 805→445 / 757→445.

2. **`WW3_WAM_KEEP_DYNAMIC` keep GUIDs are FireType, not attachments.** Post-WAM
   stably=0 subs 8312/7954/9416/9424 use class NetGUID **243** =
   `BP_Glock17FireType_01_C` (HK417: 1373) — channel FireType spawns, not
   `UWW3Attachment`. Putting them in `ReplicatedAttachments[]` is the wrong type
   vs CAM's hat/chest keep. Default **off**. Capture WAMs have **no**
   ReplicatedAttachments; SoftClass AttachmentIds create `BP_WP_*` parts online.

3. **Empty catalog never starts weapon sync.** After SoftClass-clear + omit-MainId
   rematches (`082420` no-keep, `083016` keep+no-MainId): heap
   `OnAttachmentManagerSynchronized()` hits=**0** (not mid-flight, not completed).
   No `OnSynchronized: <Weapon> Attachments`. SoftClass 4606 still clear.
   Working crash needs SoftClass-created `BP_WP_*` then per-weapon
   `OnSynchronized: BP_* Attachments` before WeaponsAttachments+IM flip.

4. **CharacterAttachments restored** on rematch `083016` (CAM_STRIP unchanged;
   earlier false was dirty long-lived client / timing, not CAM↔WAM strip
   interaction). SoftClass 4606 stays cleared with ch4/5 open strip.

Live rematch `match_console_20260807_083016` (omit MainId + KEEP_DYNAMIC=1):

| Measure | Result |
|---------|--------|
| Ack(Pawn 9372) | **OK** |
| Open strip | **4/4** (1302→990 / … / 805→445) |
| Post-ACK strip | **252** bits ×4 (keep FireType — ineffective) |
| SoftClass 4606 pending | **cleared** |
| CharacterAttachments | **true** |
| WeaponsAttachments / IM / PS | still **false** |
| OnAttachmentManagerSynchronized | **never fires** (heap) |
| LOADING MAP | **not** cleared |

**Next for WAM:** spawn real `BP_WP_*` channel attachments (package-map export +
stably=0) and keep those NetGUIDs — CAM pattern — or otherwise drive SoftClass
completion offline. Empty catalog alone is insufficient.

### WAM_SPAWN_ATTACH — real BP_WP_* (2026-08-07 09:02)

Capture SoftClass catalogs (no wire `ReplicatedAttachments`) map via crash
`OnAttachmentManagerSynchronized` + live process paths:

| Role | SoftClass id | Class | Package path prefix |
|------|--------------|-------|---------------------|
| Glock mag/rail | 151 / 4606 | `BP_WP_Magazine_108_01` / `BP_WP_Rail_086_01` | `.../Magazine/Magazine_108/`, `.../Rail/Rail_086/` |
| HK417 mag/barrel | 143 / 295 | `BP_WP_Magazine_116_01` / `BP_WP_Barrel_033_01` | `.../Magazine/Magazine_116/`, `.../Barrel/Barrel_033/` |

CAM hat/chest: clothing export of package+class, then stably=0 hasRep content;
CAM strip keeps `ReplicatedAttachments=[9404,9406]`.

Shipped `WW3_WAM_SPAWN_ATTACH=1` (`cam_im_resend.py` / `server.py`): after ACK
gate, export each BP_WP_* class **once** (connection-global NetGUID), stably=0
spawn per WAM channel (dyn 9600–9614), then WAM BatchID=2 strip with those GUIDs
in `ReplicatedAttachments[]`. Open SoftClass strip unchanged. KEEP_DYNAMIC off.

Live rematch `match_console_20260807_085701`:

| Measure | Result |
|---------|--------|
| Ack(Pawn 9372) | **OK** |
| Open strip | **4/4** |
| WAM SPAWN | **YES** (ch5/86 `export=0(reuse)`) |
| WAM post-ACK strip | **276 bits ×4** |
| CHANNEL CLOSE | **YES** immediately after spawn/strip |
| WeaponsAttachments / IM / PS | **false** |
| LOADING MAP | **not** cleared |

Spawn wire is ACK-safe until the BP_WP_* content; client hangs up on ch0. Next:
narrow CLOSE (payload/checksum/channel count).

See `match_server/live_log/NEXT_EXPERIMENT.md` / `LIVE_STATUS.md`.

### WAM_SPAWN_ATTACH bisect — CLOSE = stably=0 content (2026-08-07 09:21)

Bisect knobs (`WW3_WAM_SPAWN_CHANNELS` / `ATT_LIMIT` / `EXPORT` / `CONTENT` /
`STRIP_KEEP` / `PAYLOAD`) + rematches after `085701`:

| Preset | Console | Spawn | CLOSE? |
|--------|---------|-------|--------|
| `export87` — ch87×1, export only, keep=0 | `090731` | spawn=0 bits | **NO** (Ack OK, session stayed up) |
| `spawn87_1` — ch87×1 Mag_116, min payload, keep=0 | `091152` | spawn=92 bits | **YES** right after SPAWN |
| `empty87` — ch87×1, empty payload (hasRep=0), keep=0 | `091417` | spawn=43 bits | **YES** right after SPAWN |
| full ×4 + strip keep (`085701`) | `085701` | spawn=184×4 | **YES** after spawn+strip |

**CLOSE cause:** the post-ACK **stably=0 content block** that creates a dynamic
attachment on a weapon channel — even **one** channel, **one** NetGUID, empty
payload, strip keep off. Package-map **export alone is safe**. Strip keep and
multi-channel volume are **not** required for CLOSE.

Payload / AttachmentBatchID / catalog strip order are not the trigger.
Checksum not needed to explain CLOSE (export path-only already accepted).

**Safe live config (restore CAM path):** `WW3_WAM_SPAWN_ATTACH=0` (or
`WW3_WAM_SPAWN_CONTENT=0`), keep `WW3_CAM_STRIP_CATALOG=1` + WAM open/post-ACK
empty catalog strip. No non-closing stably=0 spawn variant found that can feed
`ReplicatedAttachments[]` yet — export-only does not advance WAM sync.

Armed now: match `092147`, `WW3_WAM_SPAWN_ATTACH=0`. Client may need a fresh
Quick Play after CLOSE-dirty "CONNECTING TO SERVER" hangs.

### Capture Mag/Rail are SoftClass-only — no channel opens (2026-08-07 09:40)

Probed `real_replay_stream.json` (`_probe_wp_capture_opens.py`):

| Question | Answer |
|----------|--------|
| Mag_108 / Rail_086 / Mag_116 / Barrel_033 **exports** anywhere? | **0 hits** across 227 export bunches |
| Actor opens with those archetypes? | **0** (5888 opens parsed) |
| Weapon-open stably=0 subs? | **FireType only** (cls 243 / 1373) — never BP_WP_* |
| CAM hat/chest pattern | clothing src 212–213: export + stably=0 `9404`/`9406` **before** CAM 9374 on **pawn ch3** |
| Timing | early Glocks src 14–17 → clothing 212–213 → INV_ATTACH ch86/87 src 257–260 |

SDK: `UWW3Attachment : public UObject` (not `AActor`) — **cannot** open dedicated
actor channels for Mag/Rail. Capture creates them via SoftClass AttachmentIds
client-side; there are **no** capture-faithful attachment open bunches to replay
on new channels.

### WAM spawn host=pawn + hatclass control (2026-08-07 09:39)

Shipped `WW3_WAM_SPAWN_HOST=pawn|weapon|<ch>` — post-ACK export+stably=0 content
host channel (default weapon). Presets: `pawn87_1` / `pawn87_1_keep` / `pawn_all`.

| Preset | Console | What | CLOSE? |
|--------|---------|------|--------|
| `pawn87_1_keep` Mag_116 on **ch3** | `092817` | host=ch3 shared dyn=9612, spawn=92, keep=1 | **YES** right after SPAWN |
| hatclass on **ch3** (cls 1357 already mapped, export=0) | `093528` | spawn=156 payload=hat keep=0 | **NO** — session stayed up (ch2 drip) |
| safe `SPAWN=0` rematch | `093941` | CAM+WAM strip only | **NO** |

**CLOSE refined:** not “weapon channel” specifically — **BP_WP_\*** instance
creation fails offline on **pawn ch3 too**. Post-ACK stably=0 of an **already-mapped
clothing hat class** on ch3 is fine. Package-map export of BP_WP_* remains safe;
content create is the hang-up. Empty SoftClass catalog still never starts WAM sync.

**Safe live:** `WW3_WAM_SPAWN_ATTACH=0`, `CAM_STRIP=1`, `WAM_STRIP=1`,
`KEEP_DYNAMIC=0`. Match `093941`. Ack OK, CAM strip fires, no CLOSE; WAM still
false (empty catalog). Next: SoftClass/ItemDatabase offline completion or prove
BP_WP_* package load (path/checksum/outer) — not more weapon-ch content injects.

### SoftClass / ItemDatabase offline path (2026-08-07 10:08)

**Why CAM empty works, WAM empty does not:**

| Manager | Empty SoftClass catalog | Completes OnSynchronized? |
|---------|-------------------------|---------------------------|
| CAM | + keep `ReplicatedAttachments=[9404,9406]` | **yes** — channel UObjects |
| WAM | no ReplicatedAttachments (capture SoftClass-only) | **never** — nothing to sync |

Capture Mag/Rail are SoftClass AttachmentIds → `UWW3ItemDatabase` →
`TSoftClassPtr` async → local `UWW3Attachment` NewObject (not actor channels).
Offline SoftClass hangs (CAM stripped those waits; WAM empty clears pending but
never fires Synchronized).

**Shipped** (`cam_im_resend.py` / `server.py`):

| Flag | Behavior |
|------|----------|
| `WW3_WAM_SOFTCLASS_CATALOG=1` | Post-ACK BatchID=2 with **min** SoftClass ids (Glock 151+4606, HK 143+295); opens stay empty |
| `WW3_WAM_SOFTCLASS_EXPORT=1` | Package-map SoftClass BP_WP_* exports on ch3 **before** catalog (no stably=0) |
| `WW3_WAM_KEEP_CLOTHING=1` | Post-ACK WAM keep `ReplicatedAttachments=[9404,9406]` — CAM pattern, no SoftClass |

Live rematch SoftClass `match_console_20260807_095100`:

| Measure | Result |
|---------|--------|
| Ack(Pawn 9372) | **OK** |
| SoftClass EXPORT | **YES** (4 classes, 4193 bits, ch3) |
| SoftClass min catalog | **YES** (228 bits ×4) |
| CHANNEL CLOSE | **NO** |
| SoftClass 4606 mid-flight | **absent** (unlike full-catalog hang) |
| CharacterAttachments | **false** this rematch |
| WeaponsAttachments / IM / PS | **false** |
| LOADING MAP | **not** cleared |

SoftClass min **arms** without CLOSE but does **not** complete offline
(`Deploy: IsAsyncLoading` heap). Empty catalog was necessary-but-insufficient;
export preload alone is not sufficient either.

### KEEP_CLOTHING rematch — clothing GUIDs ≠ WAM sync (2026-08-07 10:16)

Fresh client rematch on match `100645` with
`WW3_WAM_KEEP_CLOTHING=1`, `SPAWN_ATTACH=0`, `CAM_STRIP=1`, SoftClass catalog
**off** (no BP_WP content).

| Measure | Result |
|---------|--------|
| Ack(Pawn 9372) | **OK** |
| CAM STRIP keep 9404+9406 | **276 bits** → CharacterAttachments **true** |
| WAM STRIP keep clothing 9404+9406 | **276 bits ×4** (ch4/5/86/87) |
| CHANNEL CLOSE | **NO** |
| OnAttachmentManagerSynchronized | **never** (heap; lobby preview JSON only) |
| WeaponsAttachments / IM / PS | **false** |
| LOADING MAP | **not** cleared (Ruins of Gobi) |

**Diagnosis:** Capture WAMs complete via SoftClass `AttachmentIds` → local
`UWW3Attachment` NewObject, **not** via `ReplicatedAttachments[]` (capture WAM
opens have none). CAM's keep list is hat/chest channel objects that belong to
CAM; reusing those NetGUIDs on WAM is ACK-safe and type-plausible
(`UWW3Attachment`) but does **not** arm weapon Synchronized. So clothing keep
proves wire shape only — it is not a WAM checklist path.

**Next:** SoftClass offline completion (ItemDatabase / empty-name NewObject /
mesh SoftObject). Keep `SPAWN_ATTACH=0` — Mag stably=0 content CLOSES.

See `match_server/live_log/NEXT_EXPERIMENT.md` / `LIVE_STATUS.md`.

### Mag SoftClass force-complete (2026-08-07 10:40)

**Compare SoftClass min rematch vs full SoftClass hang:**

| Case | Wire SoftClass | Synchronized mid-flight | Mag NewObject | WAM |
|------|----------------|-------------------------|---------------|-----|
| Full SoftClass hang (opens still capture catalog) | 8–9 ids | **yes** — stuck on Rail **4606** | **yes** | hang |
| SoftClass min post-ACK (`095100`) | Mag+Rail; opens empty | **no** | **no** | false |
| Mag SoftClass open+ACK (`103341`) | Mag-only 151/143 | **no** | **no** | false |

Full hang proves Mag SoftClass **can** NewObject offline when SoftClass rides
the **capture open RepLayout**. Rail 4606 is the hang *after* Mag. Mag-only in
our **stripped** SoftClass shape (BatchID + Mag ids + empty skins, omit MainId)
never starts `OnAttachmentManagerSynchronized` — same failure as SoftClass min
post-ACK.

**Shipped** (`cam_im_resend.py` / `server.py` / `_restart_spawn_attach.py`):

| Flag | Behavior |
|------|----------|
| `WW3_WAM_SOFTCLASS_MODE=mag` | Mag-only ids (Glock 151, HK 143); default when catalog on |
| SoftClass on **opens** | When catalog on, open strip carries MODE ids (not empty) |
| SoftClass EXPORT | Mag classes only under `MODE=mag` |
| Preset `softclass_mag` | Catalog+export+mag, SPAWN=0, KEEP_CLOTHING=0 |

Live rematch `match_console_20260807_103341` (fresh client): Ack OK, open Mag
SoftClass 1302→1014 (empty would be →990), EXPORT 2×Mag/2241 bits, post-ACK
204b×4, **no CLOSE**, Synchronized/Mag `*_C_0` heap **absent**, WAM/IM/PS
false, LOADING uncleared.

**Next:** splice Mag-only `AttachmentIds[]` **inside** capture open WAM payload
(preserve skins/MainId/handles) — do not full-strip SoftClass shape.

### Mag SoftClass capture-open splice (2026-08-07 10:53)

**Hypothesis:** Mag NewObject needs SoftClass on the **capture open RepLayout**
(skins/MainId/handles), not our stripped SoftClass rebuild. Splice only
`AttachmentIds[]` → Mag-only; leave skins/MainId alone.

**Shipped** (`cam_im_resend.py` / `server.py`):

| Piece | Behavior |
|-------|----------|
| `splice_wam_payload_attachment_ids` | Replace handle-5 `AttachmentIds[]` value bits only |
| SoftClass open path | Capture WAM payload + Mag/min/full ids (no full strip rebuild) |
| SoftClass off | Unchanged empty open strip |
| Bit check | ch4 `1302→1134` (= AttachmentIds 8→1 shrink; empty was →990) |

Live rematch `match_console_20260807_104536` (client pid 9412):

| Measure | Result |
|---------|--------|
| Ack(Pawn 9372) | **OK** |
| Open Mag splice | **YES** (skins×3 + MainId on 9418 kept) |
| SoftClass EXPORT | **YES** (2×Mag / 2241 bits) |
| CLOSE / Rail 4606 hang | **NO** / **NO** |
| OnAttachmentManagerSynchronized | **never** (heap hits=0) |
| Mag `*_C_0` | **absent** |
| WeaponsAttachments / IM / PS | **false** |
| LOADING MAP | **not** cleared |

**Diagnosis:** Mag-only SoftClass — strip rebuild **or** capture-faithful splice —
never arms Synchronized. Full 8–9 id catalog is what starts mid-flight (then Mag
NewObject, then hang on Rail 4606). Next: bisect Mag + one non-Rail SoftClass id
via the same splice; keep `SPAWN_ATTACH=0`.

### Mag + one non-Rail SoftClass splice (2026-08-07 11:10)

**Hypothesis:** Mag alone never arms Synchronized; Mag + one non-Rail SoftClass
id that exists offline (crash map + process SoftClass paths) might enter
mid-flight without Rail 4606.

Capture WAM AttachmentIds → BP_WP_* (crash FD35FE0D):

| Id | Class | Used |
|----|-------|------|
| 151 / 143 | Mag_108 / Mag_116 | always |
| 101 / 108 | Muzzle_020 / Muzzle_013 | candidate 1 |
| 304 / 295 | Barrel_024 / Barrel_033 | candidate 2 |
| 4606 | Rail_086 | **avoid** |

**Shipped** (`cam_im_resend.py` / `_restart_spawn_attach.py`):

| Mode / preset | AttachmentIds |
|---------------|---------------|
| `mag_muzzle` / `softclass_mag_muzzle` | Glock 151+101, HK 143+108 |
| `mag_barrel` / `softclass_mag_barrel` | Glock 151+304, HK 143+295 |

Same open splice path (skins/MainId kept). No BP_WP_* stably=0.

| Measure | Mag+Muzzle `105752` | Mag+Barrel `110537` |
|---------|---------------------|---------------------|
| Ack(Pawn 9372) | **OK** | **OK** |
| Open splice | **YES** (1302→1158) | **YES** (1302→1158) |
| SoftClass EXPORT | Mag×2 / 2241b | Mag×2+Barrel_033 / 3281b |
| Post-ACK catalog | 228b×4 | 228b×4 |
| CLOSE / Rail 4606 | **NO** / **NO** | **NO** / **NO** |
| OnAttachmentManagerSynchronized | **never** | **never** |
| Mag / part `*_C_0` | **absent** | **absent** |
| WeaponsAttachments / IM / PS | **false** | **false** |
| LOADING MAP | **not** cleared | **not** cleared |

**Diagnosis:** Mag + one non-Rail SoftClass id (Muzzle or Barrel) is still
insufficient to arm Synchronized — same as Mag-only. Full 8–9 id catalog remains
the only known mid-flight arm surface (then hangs on 4606). Next: Mag + **two**
non-Rail ids via the same splice (e.g. Mag+Muzzle+Barrel).

See `match_server/live_log/NEXT_EXPERIMENT.md` / `LIVE_STATUS.md`.

### Mag + two non-Rail SoftClass splice (2026-08-07 11:31)

**Hypothesis:** Mag+1 never arms Synchronized; Mag + two offline non-Rail ids
(Mag+Muzzle+Barrel) might enter mid-flight without Rail 4606.

**Shipped:** `MODE=mag_muzzle_barrel` / preset `softclass_mag_muzzle_barrel`
(Glock `151,101,304` / HK `143,108,295`). SoftClass export registry expanded
for Muzzle/Barrel_024 (+ later norail BodyParts). No BP_WP_* stably=0.

| Measure | Mag+Muzzle+Barrel `111622` |
|---------|----------------------------|
| Ack(Pawn 9372) | **OK** |
| Open splice | **YES** (1302→1182) |
| SoftClass EXPORT | 6 classes / 6401b |
| Post-ACK catalog | 252b×4 |
| CLOSE / Rail 4606 | **NO** / **NO** |
| OnAttachmentManagerSynchronized | **never** |
| Mag / part `*_C_0` | **absent** |
| WeaponsAttachments / IM / PS | **false** |
| LOADING MAP | **not** cleared |

### norail binary-search high (2026-08-07 11:31)

Capture catalogs with SoftClass **4606 removed** (`MODE=norail`): early 7 /
secondary 8 / primary 8.

| Measure | norail EXPORT=1 | norail EXPORT=0 `112745` |
|---------|-----------------|--------------------------|
| Ack | **OK** | **OK** |
| SoftClass EXPORT | 14 classes / 15409b | **off** |
| CHANNEL CLOSE | **YES** (after export) | **NO** |
| Synchronized / Mag `*_C_0` | **never** / **absent** | **never** / **absent** |
| WAM | false | false |
| LOADING | n/a (kicked) | stuck Ruins of Gobi |

**Diagnosis:** Mag+0/1/2 and full-minus-4606 open splices never arm Synchronized.
Count is not the trigger — SoftClass **4606** (or another full-catalog-only
property) appears required for mid-flight arm. SoftClass EXPORT of unproven
package paths can CLOSE the client. Next: Mag+4606 (`min`) with EXPORT=0 to
confirm 4606 arms Sync (expect hang), or non-count probes (order/skins/MainId).

See `match_server/live_log/NEXT_EXPERIMENT.md` / `LIVE_STATUS.md`.

### Mag+4606 / Mag+Muzzle+4606 EXPORT=0 (2026-08-07 11:42)

**Hypothesis:** SoftClass id **4606** presence arms mid-flight Synchronized
(norail never arms; full catalog with 4606 does). Test Mag+4606 then
Mag+Muzzle+4606 with SoftClass EXPORT=0 (no unproven package-map export).

**Shipped:** `MODE=min` / preset `softclass_min` (override EXPORT=0);
`MODE=mag_muzzle_4606` / preset `softclass_mag_muzzle_4606` (Glock
`151,101,4606` / HK `143,108`). No BP_WP_* stably=0. No SoftClass EXPORT.

| Measure | Mag+4606 `113312` | Mag+Muzzle+4606 `113922` |
|---------|-------------------|--------------------------|
| Ack(Pawn 9372) | **OK** | **OK** |
| Open splice | **YES** (1302→1158) | **YES** (1302→1182) |
| SoftClass EXPORT | **off** | **off** |
| Post-ACK catalog | 228b×4 | 252b×3 + primary 228b |
| CLOSE / Rail 4606 hang | **NO** / **NO** | **NO** / **NO** |
| OnAttachmentManagerSynchronized | **never** (pending hits=0) | **never** (pending hits=0) |
| Mag / part `*_C_0` | **absent** | **absent** |
| WeaponsAttachments / IM / PS | **false** | **false** |
| LOADING MAP | **not** cleared | **not** cleared |

**Diagnosis:** 4606 presence with Mag(+Muzzle) is **not sufficient** to arm
Synchronized via open splice. Full catalog remains the only known mid-flight
arm surface. Next: non-count probes (capture id order, skins Parts[], MainId,
BatchID) at EXPORT=0 — Sync never armed, so SoftClass 4606 finish/skip was not
attempted.

See `match_server/live_log/NEXT_EXPERIMENT.md` / `LIVE_STATUS.md`.

### Non-count shape probes — stub4606 + full identical open (2026-08-07 12:10)

**Offline field-for-field diff** (`_diff_wam_softclass_shape.py`):

| Surface | vs capture open |
|---------|-----------------|
| MODE=`full` open splice | **bit-identical** FINAL+payload (skins/MainId/BatchID/order) |
| Mag+N / min / norail splices | skins/MainId/BatchID **kept**; AttachmentIds count+**order** differ (secondary capture is Mag-second `101,151,…`; Mag splices are Mag-first) |
| NumReplicatedAttachments | capture **omits**; Mag/full splices omit too |
| post-ACK SoftClass reinforce | **always differs**: BatchID `1→2`, skins Parts `×3→[]`, MainId `9246→omit` on secondary |

**Shipped:** `MODE=stub4606` (capture order/count with SoftClass **4606→Mag 151**);
`WW3_WAM_SOFTCLASS_OPEN_ONLY=1` (post-ACK empty SoftClass); presets
`softclass_stub4606`, `softclass_stub4606_nopost` (`WPN_ATTACH=0`),
`softclass_full_nopost`. EXPORT=0. No BP_WP_* stably=0.

| Measure | stub4606 + empty post `115051` | stub4606 nopost `115633` | full nopost `120311` |
|---------|--------------------------------|--------------------------|----------------------|
| Open bits | 1302→**1302** (4606→151 only) | 1302→**1302** | 1302→**1302** (**identical FINAL**) |
| SoftClass EXPORT | **off** | **off** | **off** |
| Post-ACK WAM | empty SoftClass 180b×4 | **none** (`WPN_ATTACH=0`) | **none** |
| Ack(Pawn 9372) | **OK** | **OK** | **OK** |
| CLOSE | **NO** | **NO** | **NO** |
| OnAttachmentManagerSynchronized | **never** (pending=0) | **never** (pending=0) | **never** (pending=0; Mag/Rail `*_C_0`=0) |
| WeaponsAttachments | **false** | **false** | **false** |
| Hang on 4606 | **NO** | **NO** | **NO** |

**Diagnosis:** Capture SoftClass **shape** (order/count/skins/MainId/BatchID) with
4606 stubbed does **not** arm Sync. More surprising: MODE=`full` open is
**bit-identical** to capture FINALs yet still never arms Sync / Mag NewObject
under current flags (`CAM_STRIP=1`, SoftClass EXPORT=0, no post-ACK WAM). The
historical mid-flight Sync arm was observed when early Glock opens still carried
native capture catalogs **before** the WAM strip rewrite path existed as the
live send path — that “full catalog arms” result is **not** reproduced by
today’s identical-FINAL SoftClass splice rematch. Sync arm is **not** “4606
presence alone”, **not** “capture skins/MainId alone”, and **not** simply
“full AttachmentIds bits on the open” under current bootstrap.

**Next:** isolate what else the historical Sync-arm session had — e.g.
`WW3_CAM_STRIP_CATALOG=0`, SoftClass BatchID=2 reinforce with **capture skins
kept**, or ambient/follow-up bunches — then SoftClass 4606 finish once Sync
actually arms.

See `match_server/live_log/NEXT_EXPERIMENT.md` / `LIVE_STATUS.md`.

### Sync-arm restore A/B — CAM0 / keep-skins / native (2026-08-07 12:37)

**Hypothesis:** Historical mid-flight Sync (hang on SoftClass 4606) needs either
`CAM_STRIP=0`, SoftClass BatchID=2 reinforce that **keeps** capture skins/MainId
(not empty strip), or truly native opens (`WAM_STRIP=0`) rather than MODE=`full`
splice under strip.

**Shipped:** `WW3_WAM_SOFTCLASS_KEEP_SKINS=1` — post-ACK SoftClass reinforce
splices MODE ids into capture open payload and only bumps BatchID (skins Parts /
MainId kept). Presets `softclass_full_cam0`, `softclass_full_keepskins`,
`softclass_native_open`, `softclass_native_cam0`. SoftClass EXPORT=0. No
BP_WP_* stably=0.

| Measure | full+CAM0 `121606` | keepskins `122223` | native `122648` | native+WPN `123300` |
|---------|--------------------|--------------------|-----------------|---------------------|
| SoftClass open | MODE=`full` identical | MODE=`full` identical | **native** (no rewrite) | native |
| Post-ACK WAM | none | BatchID=2 skins/MainId **kept** (492–540b) | none | capture resend 540/492b |
| CAM strip | **off** | on | on | on |
| Ack(Pawn 9372) | **OK** | **OK** | **OK** | **OK** |
| CLOSE | **NO** | **NO** | **NO** | **NO** |
| OnAttachmentManagerSynchronized | **never** (pending=0) | **never** | **never** | **never** |
| Mag / Rail `*_C_0` | **absent** | **absent** | **absent** | **absent** |
| Hang on 4606 | **NO** | **NO** | **NO** | **NO** |
| WeaponsAttachments | **false** | **false** | **false** | **false** |
| CharacterAttachments | (CAM SoftClass waits) | — | **true** | **true** |
| LOADING MAP | **not** cleared | **not** | **not** | **not** |

**Diagnosis:** None of the candidate flag diffs restored Sync arm. SoftClass
4606 finish/skip was **not** attempted. Historical mid-flight Sync is **not**
explained by CAM strip, empty BatchID=2 skins overwrite, or WAM strip rewrite
vs native open bits under today's client. Next: non-flag causes (ItemDatabase /
SoftClassPtr residency, ambient bunches, crash-era client state).

See `match_server/live_log/NEXT_EXPERIMENT.md` / `LIVE_STATUS.md`.

### Historical Sync-arm wire replay — still silent (2026-08-07 12:55)

**Historical Sync-arm session:** rematch `074114` (heap mid-flight
`OnAttachmentManagerSynchronized() : 5 - BP_WP_Rail_086…, 4606`). Flags then:
`WAM_STRIP=1` but **only INV_ATTACH** ch86/87 rewritten empty (`open_strip=2/2`);
early Glock opens src **15/17** stayed native SoftClass (**1302 / 1287** bits,
incl. id 4606); `INV_ATTACH=1` `CLOTHING_RESEND=1` `CAM_STRIP=1` `ClientRestart`
~t+110ms; SoftClass EXPORT=0; no BP_WP_* stably=0. SoftClass pending later
**cleared** when ch4/ch5 open strip landed (`081409`).

**Diff vs today's silent native / MODE=full rematches:**

| Surface | Hist `074114` | Today `WAM_STRIP=0` / MODE=full | Today `hist074114` `124704` |
|---------|---------------|--------------------------------|------------------------------|
| ch4/ch5 SoftClass open | native 1302/1287 | native / identical 1302/1287 | native 1302/1287 (**not stripped**) |
| ch86/87 open | empty strip | SoftClass native | empty strip (`805→445`) |
| post-ACK WAM | empty ×2 (86/87 only) | none or SoftClass resend | empty ×2 (`open_strip=2/2`) |
| SoftClass EXPORT / BP_WP_* stably=0 | off / no | off / no | off / no |
| Client process | overnight Aug6→7 | pid **9412** since 10:33 | same 9412 |
| Sync pending / Mag `*_C_0` | **mid-flight / yes** | **0 / absent** | **0 / absent** |

**Shipped:** `WW3_WAM_STRIP_CHANNELS=inv|early|all` (`cam_im_resend.py` /
`server.py`) + preset `softclass_hist074114` — INV-only open+post-ACK strip so
early SoftClass catalogs survive (exact `074114` wire).

Live rematch `match_console_20260807_124704`:

| Measure | Result |
|---------|--------|
| Wire vs `074114` | **match** (strip only 258/260; src15=1302 SoftClass) |
| Ack(Pawn 9372) | **OK** |
| CHANNEL CLOSE | **NO** |
| SoftClass pending / Mag·Rail `*_C_0` | **0 / absent** |
| Hang on 4606 | **NO** |
| WeaponsAttachments / IM / PS | **false** |
| CharacterAttachments | **false** this rematch |
| LOADING MAP | **not** cleared |
| SoftClass 4606 finish/skip | **not run** (Sync never armed) |

**Root cause:** Sync arm is **not** gated by SoftClass open bits alone. Bit-
identical / historical SoftClass catalogs ACK on today's client without ever
entering `OnAttachmentManagerSynchronized` or Mag NewObject. The morning Sync
arm lived on the **long-lived Aug-6 client** that SoftClass-armed from early
Glock opens *before* ch4/ch5 empty strip existed; after `081409` cleared
pending, SoftClass was never re-proven on that process, and pid **9412** (fresh
10:33) never arms from SoftClass opens or post-ACK SoftClass. CAM SoftClass
waits still work (CharacterAttachments hangs without `CAM_STRIP`) — weapon
SoftClass→`UWW3Attachment` NewObject is the missing client-side step
(ItemDatabase SoftClassPtr / class residency), not the wire catalog.

**Recipe that restores Sync on today's client:** **none yet.** Closest wire
recipe (`softclass_hist074114` / `WW3_WAM_STRIP_CHANNELS=inv`) matches history
but leaves pending=0. SoftClass 4606 finish/skip remains blocked until Sync
pending>0. Keep SoftClass EXPORT=0 / no BP_WP_* stably=0 until then.

See `match_server/live_log/NEXT_EXPERIMENT.md` / `LIVE_STATUS.md`.

### SoftClass early package-map warm — still silent (2026-08-07 13:15)

**Hypothesis:** Mag/Rail SoftClass packages must be package-map-resident before
early SoftClass OnRep so ItemDatabase SoftClassPtr async can resolve → Mag
NewObject → Sync arm.

**Shipped:** `WW3_WAM_SOFTCLASS_WARM_EXPORT=1` (`cam_im_resend.py` /
`server.py`) + preset `softclass_hist074114_warm`. Mag+Rail SoftClass BP_WP_*
(151/4606/143/295) exported on pawn ch3 **before** ownership early Glock SoftClass
OnRep (src 15/17). Independent of SoftClass catalog rewrite — hist native SoftClass
opens kept. Export-only (no stably=0 content). Drain breaks batches so warm is not
swallowed into the src 11–14 pack. 10-class warm (10801 bits) CHANNEL CLOSEd ch0
(`130535`); Mag+Rail 4-class (4193 bits) is the safe size.

Live rematch `match_console_20260807_131115`:

| Measure | Result |
|---------|--------|
| Warm EXPORT | **YES** (4 classes, 4193 bits, before SoftClass OnRep) |
| Wire vs `074114` | hist INV-only strip (`open_strip=2/2`); SoftClass native on ch4/ch5 |
| Ack(Pawn 9372) | **OK** |
| CHANNEL CLOSE | **NO** |
| SoftClass pending / Mag·Rail `*_C_0` | **0 / absent** |
| Hang on 4606 | **NO** |
| CharacterAttachments | **true** (CAM strip) |
| WeaponsAttachments / IM / PS | **false** |
| LOADING MAP | **not** cleared |
| SoftClass 4606 finish/skip | **not run** (Sync never armed) |

**Root cause:** package already-loaded SoftClass paths are **not** sufficient to
start weapon SoftClass → NewObject. Sync arm still needs ItemDatabase SoftClassPtr
residency / another client-side gate (arsenal / CUSTOMIZE browse next).

**Recipe that restores Sync:** **none yet.** Warm method proven safe but Sync=
NO. Keep no BP_WP_* stably=0; Mag+Rail warm only.

See `match_server/live_log/NEXT_EXPERIMENT.md` / `LIVE_STATUS.md`.

### SoftClassPtr CUSTOMIZE browse — warm OK, rematch hangup (2026-08-07 13:50)

**Hypothesis:** browsing arsenal / CUSTOMIZE forces ItemDatabase SoftClassPtr
async loads so Mag NewObject / Sync can arm on hist SoftClass OnRep.

**Warm method (done):** Relaunch client to main menu (stuck Ruins LOADING ignored
Esc). Brief cursor clicks (Slate ignores PostMessage on tabs): **CUSTOMIZE** →
**EQUIPMENT** → browse Marksman secondary / G36 (+ X show parts). Heap then
contains many `/Game/Blueprints/Weapons/Attachments/.../Magazine_*` SoftClass
paths. Hub gained `GET /clearlobbies` for stuck lobby cleanup.

**Rematch after warm** (`softclass_hist074114` ± `WARM_EXPORT=1`, pid **31768**):

| Measure | Result |
|---------|--------|
| SoftClassPtr UI residency | **YES** (Mag paths in mem) |
| Mag+Rail WARM EXPORT | **YES** when enabled (4 cls / 4193 bits) |
| Ack(Pawn 9372) | **NO** |
| CHANNEL CLOSE | **YES** ch0 reason=0 (before Ack) |
| Sync / Mag `*_C_0` / WAM / 4606 hang | **n/a** (hangup first) |
| LOADING | **aborted** |

Same CLOSE with `WARM_EXPORT=0` after UI browse (`134613`). Contrast: Mag+Rail
warm alone on prior pid **9412** (`131115`) was Ack OK / Sync NO / no CLOSE.

**Root cause (working):** SoftClassPtr residency is achievable via CUSTOMIZE, but
rematch after browse on this fresh client hangs up before Ack — not a Sync arm
yet. Suspect overweight loadout (repeated **WEIGHT LIMIT REACHED** modal during
browse) and/or package-map interaction with already-resident SoftClass paths.

**Recipe that restores Sync:** **none yet.** Next: green loadout as main, then
hist±warm again. Keep no BP_WP_* stably=0.

See `match_server/live_log/NEXT_EXPERIMENT.md` / `LIVE_STATUS.md`.

### Green CLOSE QUARTERS main — CLOSE persists (2026-08-07 14:08)

**Hypothesis:** rematch hangup was overweight after arsenal edits; set
**CLOSE QUARTERS** as main and retry hist±warm without WEIGHT LIMIT / SoftClassPtr
browse.

**Loadout fix (done):** `ProfileSave`
`equipmentLoadouts.mainLoadoutIndex=5` already **CLOSE QUARTERS**. Relaunched
fresh client pid **29116** (shotgun CQ on main menu). No arsenal browse this
run; no WEIGHT LIMIT modal on rematch path.

| Candidate | Console | Warm | Ack | CLOSE | Sync | Mag NO | WAM | 4606 hang | LOADING |
|-----------|---------|------|-----|-------|------|--------|-----|-----------|---------|
| green CQ + `hist074114_warm` | `135858` | 4 cls / 4193 bits | **NO** | **ch0** | **NO** | **NO** | false | **NO** | aborted |
| green CQ + `hist074114` | `140440` | off | **NO** | **ch0** | **NO** | **NO** | false | **NO** | aborted |

Heap checklist after hangup: Controller/LocalClientConfigs true; PlayerState /
InventoryManager / CharacterAttachments / WeaponsAttachments / GameState /
MapLevels false. SoftClass pending / Mag·Rail `*_C_0` probe hits=0.

**Root cause (updated):** green CQ does **not** restore Ack. Fresh clients
(**29116**, and prior UI-warm **31768**) hang up ch0 before Ack on hist±warm,
while older pid **9412** Mag+Rail warm (`131115`) still Ack OK / Sync NO.
Overweight is not the primary gate.

**Recipe that restores Sync:** **none yet.** Next: diff Ack-OK long-lived
**9412** vs fresh hangup clients. Keep no BP_WP_* stably=0.

See `match_server/live_log/NEXT_EXPERIMENT.md` / `LIVE_STATUS.md`.

### Fresh-client CLOSE = PS_REBIND default (2026-08-07 14:13)

**Root cause:** `_restart_spawn_attach.py` dropped Ack-OK possession pins when
prior process env lacked them → defaults `WW3_PS_REBIND=1` + `MAX_SPRAYS=4` →
PS rebind + dual ClientRestart spray → **ch0 CHANNEL CLOSE before Ack**. Warm /
CQ / SoftClassPtr browse / overweight were **not** the gate.

**Fix:** pin Ack-OK BASE in `_restart_spawn_attach.py`
(`PS_REBIND=0` `MAX_SPRAYS=1` `BOOTSTRAP=ownership` `PAWN_EXPORT_PREFIX=1`
`ACK_AUDIT=1` `STREAMING_PAUSE_MS=15000`).

| Candidate | Console | Flags | Ack | CLOSE | CAM | LOADING | WAM |
|-----------|---------|-------|-----|-------|-----|---------|-----|
| Mag+Rail warm (pid **9412**) | `131115` | PS_REBIND=0 | OK | NO | strip | stuck | false |
| green CQ hist±warm (fresh **29116**) | `135858`/`140440` | **PS_REBIND=1** | NO | **ch0** | n/a | aborted | n/a |
| restored Ack-OK (fresh **29116**) | **`141101`** | **PS_REBIND=0** | **OK** | **NO** | **true** | stuck | false |

Never rematch with `PS_REBIND` default.

### SoftClass Sync re-attempt — Mag NewObject on 141101; open STUB_4606 blocks Mag (2026-08-07 14:29)

**Reprobe `141101`:** Mag NewObject **YES** —
`OnAttachmentManagerSynchronized() : 7 - BP_WP_Magazine_108_01_C_0, 8, 151, 0`
(timestamp during Ack-OK rematch). Rail `*_C_0` / `OnSynchronized: Weapons`
absent; WAM false. Same Mag+Rail warm on pid **9412** (`131115`) had Mag hits=0.

| Surface | `131115` / **9412** | `141101` / **29116** |
|---------|---------------------|----------------------|
| Wire Mag+Rail warm + hist SoftClass+4606 | same | same |
| Mag SoftClass class resident | warm | warm + class path |
| Mag `*_C_0` | **NO** | **YES** |
| Rail `*_C_0` / WAM | NO / false | NO / false |

**Diff (later superseded):** Mag SoftClass→instance looked process-dependent.
Deep-diff 15:15: Mag*_C_0 is a **one-shot** — Mag SoftClass **class** warm ≠
instance; fresh **29480** never NewObjects under identical hist+warm.

**Finish/skip 4606 attempt:** shipped `WW3_WAM_SOFTCLASS_STUB_4606=1` + preset
`softclass_hist074114_warm_stub4606` — early SoftClass native under INV strip,
splice SoftClass **4606→151** in-place (no stably=0).

| Measure | `142507` |
|---------|----------|
| Stub applied (ch4/ch5) | **YES** (1302/1287 bits) |
| Ack / CLOSE / PS_REBIND | OK / NO / 0 |
| Mag NewObject | **NO** |
| Hang 4606 / WAM / LOADING | NO / false / stuck |

**Root cause:** SoftClass id **4606** must remain on the early open catalog for
Mag Synchronized to start. Open-stub finish/skip **blocks Mag NewObject**.
Mid-flight finish after `Mag*_C_0` (4606 still present) is the remaining path;
then flip WAM. Keep `PS_REBIND=0`; no BP_WP_* stably=0.

See `match_server/live_log/NEXT_EXPERIMENT.md` / `LIVE_STATUS.md`.

### Mid-flight POST_STUB 4606 — Mag NO; finish without Mag (2026-08-07 14:45)

**Shipped:** `WW3_WAM_SOFTCLASS_POST_STUB_4606=1` (`cam_im_resend.py` /
`server.py`) + preset `softclass_hist074114_warm_poststub4606`. Open SoftClass
keeps 4606 (`STUB_4606=0`). After ACK gate + delay + wait-file (touch after
`Mag*_C_0`), post SoftClass reinforce on early WAMs: mode=`stub` (4606→151,
skins/MainId kept, BatchID=2) or `empty` cancel. No BP_WP_* stably=0.

Live rematch `match_console_20260807_143317` (pid **29116**, Ack-OK BASE):

| Measure | Result |
|---------|--------|
| Warm EXPORT | **YES** (4 cls / 4193 bits) |
| Open STUB_4606 | **0** (native SoftClass+4606 on ch4/ch5) |
| Mag NewObject | **NO** (hits=0 before/after POST_STUB) — regress vs `141101` Mag YES |
| Sync / WAM / IM / PS | **NO** / false / false / false |
| Hang 4606 | **n/a** (Mag never armed) |
| Ack / CLOSE | **OK** / **NO** |
| LOADING | MapLevels **true**; still `Deploy: IsAsyncLoading` |
| SoftClass 4606 finish | **YES** — POST_STUB after Mag-wait timeout: `8314@4:492` + `7956@5:492` (4606→151) |

**Root cause (updated):** finishing SoftClass 4606 mid-flight **without** Mag
NewObject does not flip WeaponsAttachments. POST_STUB shape is fine **if** Mag
arms; Mag arm itself has **no recipe** (see deep-diff 15:15). SoftClass Sync
abandoned without Mag*_C_0.

**Recipe that restores Sync:** **none.** Keep `PS_REBIND=0`; no BP_WP_* stably=0.

See `match_server/live_log/NEXT_EXPERIMENT.md` / `LIVE_STATUS.md`.

### Mag re-arm failed — fresh client + hist+warm (2026-08-07 15:08)

**Diff `141101` vs `143317`:** only `WW3_WAM_SOFTCLASS_POST_STUB_*` flags.
Open SoftClass+4606 + Mag+Rail warm wire match; ch4 ACKED on both. POST_STUB
cannot kill Mag (fires after Mag window). Mag NO on `143317` follows open
`STUB_4606` rematch `142507` on the same process.

**Re-arm attempt:** relaunched NoEAC pid **29480**; hist+warm with
`STUB_4606=0` `POST_STUB=0` `PS_REBIND=0`.

| Console | Mag SoftClass class | Mag*_C_0 | Synchronized | Ack | CLOSE | WAM | POST_STUB |
|---------|---------------------|----------|--------------|-----|-------|-----|-----------|
| `145505` | **YES** (Mag108) | **NO** | **NO** | OK | NO | false | not applied |
| `150342` | — | **NO** | **NO** | OK (all ch ACKED) | NO | false | not applied |

**Root cause (updated):** Mag SoftClass **class** warm ≠ Mag NewObject. Fresh
client + Ack-OK hist+warm does **not** reproduce `141101` Mag*_C_0. Mid-flight
POST_STUB remains gated on Mag detect.

**Recipe that restores Mag / Sync / WAM:** **none yet.** Keep `PS_REBIND=0`;
open `STUB_4606=0`; no BP_WP_* stably=0.

See `match_server/live_log/NEXT_EXPERIMENT.md` / `LIVE_STATUS.md`.

### Mag deep-diff — one-shot Mag*_C_0; SoftClass Sync abandoned (2026-08-07 15:15)

**False-positive check:** `141101` Mag YES is **not** a crash-log ghost.
Probe `…11.12.32:720][573]…Mag*_C_0, 8, 151, 0` is UE **UTC** → local
**14:12:32** inside console `141101` (14:11 start). Exact timestamp/frame is
absent from analysis/AppData crash WW3.logs. Live pid **29480**: Mag SoftClass
**class** resident; `Mag*_C_0`=0; Synchronized=0; `WeaponsAttachments: false`.

**Wire deep-diff** (`141101` Mag YES vs `145505`/`150342`/`131115` Mag NO):
SoftClass warm vs Restart, CAM strip, clothing, INV hist SoftClass+4606, and
channel ACK *order* match. Fast ch3 OPEN ACK (~22ms) also on Mag-NO `131115`
(~32ms) — **not** the Mag gate. Mag SoftClass class warm is **insufficient**.

**Root cause of Mag “regression”:** Mag NewObject is **not** produced by
hist+warm class residency. `141101` Mag*_C_0 was a **one-shot** (unknown
ItemDatabase SoftClassPtr / SoftObject resolve state). STUB-burn on **29116**
is **not** the sole regress — fresh **29480** also Mag NO. `LogWW3Wpn` is
omitted from client_log capture; Mag detect = heap UTF-16 `Mag*_C_0` + rematch
UTC window only.

**Sync without Mag*_C_0:** SoftClass Synchronized **cannot** arm without Mag
NewObject (empty catalog never starts; Mag-only splice modes already Mag NO).
`WAM_SPAWN_ATTACH` / ReplicatedAttachments already **CLOSE** on stably=0
BP_WP_* content; KEEP_CLOTHING wrong type. SoftClass Sync **abandoned** until
a Mag precondition appears; LOADING chase should not wait on
WeaponsAttachments alone (checklist not a strict gate — fact #9).

**Recipe Mag / Sync / WAM:** **none.** Keep `PS_REBIND=0`; open `STUB_4606=0`;
no BP_WP_* stably=0.

See `match_server/live_log/NEXT_EXPERIMENT.md` / `LIVE_STATUS.md`.

### Pivot C — LOADING gate (2026-08-07 15:25)

Evidence-only (no rematch). Live pid **29480** checklist:

`Controller/CharacterAttachments/GameState/LocalClientConfigs/MapLevels = true`;
`PlayerState/InventoryManager/WeaponsAttachments = false`. Ack OK; never
`LoadingMap→InGame`.

| Ruled out as sole LOADING gate | Why |
|--------------------------------|-----|
| Full 8-bit checklist / PS | Fact #9; PS false in working matches |
| CAM alone | Live + `071337` CAM true, stuck |
| MapLevels+GS alone | Live both true, stuck |
| IM+WAM alone | `FBE1EB12` both true, MapLevels false, no InGame |
| Mag SoftClass NewObject | `FD35FE0D` InGame @ 11:14:41; Mag108 Synchronized @ 11:14:56 |
| Missing cooked Mag | Path present in `pakchunk0_s51-WindowsClient.pak` |
| `Deploy: IsAsyncLoading` heap | Format-string in binary, not live wait |

**Model:** InGame needs map/GS half **and** IM+WAM half. Offline has the first;
weapon OnSynchronized is the remaining half. Mag SoftClass is one arm path, not
the leave event.

### SoftClassPtr / StreamableManager dump id 151 (2026-08-07 15:43)

**Tool:** `match_server/_dump_softclass_streamable_151.py` →
`live_log/_softclass_streamable_151_dump.txt` on stuck pid **29480** (no rematch).

| Mag id 151 | Result |
|------------|--------|
| SoftObjectPath `/Game/.../Magazine_108/BP_WP_Magazine_108_01` | **YES** |
| BlueprintGeneratedClass + `Default__…_C` | **YES** (class loadable) |
| `BP_WP_Magazine_108_01_C_0` | **NO** |
| Mag-prox Streamable pending / failed load | **none** |
| Peer SoftClass 4606 / 101 / 143 | same: path+class YES, `*_C_0` NO |
| WAM / IM | **false** / **false** (CAM sample false on this dump) |
| Ack / CLOSE / LOADING | OK / NO / stuck |

**Root (superseded 16:05):** SoftClassPtr path/CDO residency was never the Mag
NewObject blocker. See CreateAttachment gate below.

**Rematch:** none — dump yields no SoftClass wire fix.

### CreateAttachment path — Mag*_C_0 false negative (2026-08-07 16:05)

**Tool:** `match_server/_dump_wam_create_sync_gate.py` + live WAM TArray walk on
stuck pid **29480** (no rematch, `PS_REBIND=0`).

**SDK path (Dumper-7 `UWW3AttachmentManager` / `UWW3WeaponAttachmentManager`):**

`OnRep_ReplicatedBatch` → `CreateAttachmentStructureAndRebuild` /
`CreateAttachments` (GameSingleton `bBlockCreateAttachments` /
`bBlockCreateAttachmentStructureAndRebuild` / init blocks) → ItemDatabase
`ItemClass` SoftClassPtr → `NewObject` (Outer=`OwnerWeapon`) →
`TryAddAttachment` → mesh `BaseMeshTemplate` / `OnAttachmentMeshLoaded*` →
`CheckAttachmentsSynchronized` →
`AWW3InventoryWeapon::OnAttachmentManagerSynchronized`.

**Stuck early WAM (hist SoftClass catalog still applied):**

| Field | Value |
|-------|-------|
| ReplicatedBatch | BatchID=1, AttachmentIds=early8 (151…), NumRepAtt=0 |
| ClientApplied | BatchID=1, same ids |
| AllAttachmentObjects | **8** SoftClass instances |
| Mag 151 | Outer=OwnerWeapon, FName Number=1, BaseMeshComp≠0 |
| MeshDelegates / Temporary | 0 / 0 |
| Mag*_C_0 UTF-16 / Synchronized live | **0** / **0** (fmt only) |

**141101 vs stuck:** Mag SoftClass NewObject on both; `141101` Mag*_C_0 string
was Synchronized **ToString**, not a unique create. Stuck never notifies.

**Root:** CreateAttachment does **not** skip after SoftClass resolve. Gap is
**Synchronized notify** (`CheckAttachmentsSynchronized` / post-mesh pad state)
with SoftClass objs already present.

**Rematch:** none. **Blocked-on:** Synchronized notify after create — not Mag
SoftClass NewObject / Streamable. Do not rematch SoftClass hist+warm alone.

### GameSingleton bBlock* + Pad_298/318 (2026-08-07 ~16:20)

**Tools:** `_dump_gs_sync_blocks_fast.py`, `_tabulate_wam_pads.py`,
`_patch_wam_sync_pads_only.py`, `_patch_wam_clear_partskins.py` (inline),
`_patch_wam_sync_kick.py` → `live_log/_gs_sync_blocks_dump.txt`.

| Probe | Result |
|-------|--------|
| GS `bBlockCheckAttachmentsSynchronized` | **0** |
| GS `bBlockOnWeaponAttachmentsFullySynchronized` | **0** |
| All other attachment `bBlock*` | **0** |
| Stuck Pad_318 | 3× TSharedPtr pending (vs 0 on synced-empty Batch=2) |
| Stuck Parts.AttachmentsIds | `[0xFFFF,0xFFFF,0xFFFF]` (+ Pad_3F0 num=3) |
| pads_only clear Pad_318 + i2B4=2 | Pad_318 stays 0; **b2A5 re-arms**; Sync=0 |
| clear Parts/Pad_3F0 | stays 0; Sync=0 (no Check re-entry) |
| ProcessEvent OnRep off-thread | **AV crash**; client dead |

**Root:** GameSingleton blocks are **not** the gate. SoftClass create done;
`CheckAttachmentsSynchronized` never completes/re-enters while Pad_298
substate `b2A5=2`. Pad clears without **game-thread** OnRep/Check kick do not
fire `OnAttachmentManagerSynchronized`. Off-thread PE is unsafe.

**Rematch next:** SoftClass hist+warm + post-ACK BatchID/Parts-empty reinforce
so OnRep runs in-engine after Mag SoftClass exists. `PS_REBIND=0`; no
BP_WP_* stably=0; open `STUB_4606=0`.
