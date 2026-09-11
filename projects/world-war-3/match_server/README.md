# WW3 Match Server — Path B (reimplement the UE4.21 netcode server)

The official dedicated server (Steam app 912100 / depot 912101) is **unobtainable** —
partner-only license ("No licenses"), files being deleted from Steam, and the only builds
that ever existed there are 2019–2020 early-access (incompatible with the current client).
So the match server has to be **reimplemented** for the current build. Feasible because the
match traffic is **plaintext / uncompressed** (confirmed) and **UE4.21's engine source is
public**, so we read the exact wire format instead of guessing.

## Milestones

| # | Goal | Status |
|---|------|--------|
| **M1** | StatelessConnect handshake — a WW3 client connects to our UDP server | **✅ LOCKED — bit layout reproduces the real server byte-for-byte, cross-validated on 3 independent captures** |
| **M2** | Control channel — accept `NMT_Hello` / `NMT_Login` + the `lobbyToken` | **✅ DONE — PROVEN AGAINST THE REAL GAME** (live client logged in with its real token) |
| **M3** | Load a map — client drops into an empty world | **map load ✅ DONE** (real client loaded WW3_Gobi_New_P from our NMT_Welcome and sent `NMT_Join`). Actor replication framing decoded — see `docs/M3_Replication_Findings.md` |
| **M4** | Replicate the player pawn — you can move (first playable moment) | **blocked on pawn possession** — Controller/GameState/MapLevels sync true, local PS 9362 + early GameState + weapons sent, but the client never maps pawn NetGUID 9372 / never sends `AckPossession(Pawn)` (always `(null)`), so it never leaves LOADING MAP. Wire bytes, framing and sequencing are ground-truthed correct — see `docs/M4_Possession_Findings.md` for what's been ruled out and what's still open. |
| M5+ | Other players / bots / vehicles / combat | ambient drip after ownership (in progress) |

## Files

- `ue4_bits.py` — UE4 `FBitReader`/`FBitWriter` (LSB-first bit packing) incl. float32.
  Foundation for the handshake, packet headers, bunches, and property replication.
- `stateless_handshake.py` — M1 handshake (server side). Cookie = HMAC-SHA1 with **our own**
  secret (no studio key). Self-test **round-trips the real captured packets byte-for-byte**.
- `control_channel.py` — **M2 legacy UE4 packet + bunch codec** (reader + writer). Self-test
  round-trips the real Hello/Challenge/Login packets **byte-for-byte** and extracts the
  lobbyToken via proper bunch parsing.
- `lobby_token.py` — mint/validate the `lobbyToken` (HS256, our secret — same as the hub).
- `server.py` — UDP server + state machine: M1 handshake → M2 NMT (`Hello→Challenge`,
  `Login→validate token→Welcome`). Run: `python server.py 7871`.
- `test_m2_e2e.py` — drives the **full M1+M2 pipeline** with our code on both sides; asserts
  the server reaches LOGGED_IN and parses the real captured NMT_Login.
- `analyze_handshake.py` — decodes the connect handshake from a fresh capture.

## M1 — LOCKED (the handshake bit layout)

The fresh full-match captures (`captures/24July26/W3_match_full_{1,2,3}.pcapng`, recorded
from **before** the client joined) gave the real handshake bytes. Decoded + reproduced
byte-for-byte. The layout (25-byte UDP packets):

```
bit   0        bHandshakePacket        1 for every handshake packet
bit   1        flag (SecretId)         varies 0/1 per connection — cosmetic to us
bits  2..33    Timestamp  float32      InitialConnect=0.0, Challenge=elapsed secs, Ack=-1.0
bits 34..193   Cookie                  20 bytes (HMAC-SHA1); we use OUR OWN secret
bit 194        terminator              UE4 end-of-packet 1-bit marker
```

Sequence: `InitialConnect(ts=0)` → `ConnectChallenge(ts=elapsed)` → client echoes it
**verbatim** as `ChallengeResponse` → server `ChallengeAck(ts=-1.0)` → client starts
sending control/game packets. Because the client pure-echoes and we own the secret,
validation is trivial and needs no studio key.

Verify anytime: `python stateless_handshake.py` (round-trips the REAL captured packets)
and `python analyze_handshake.py ../captures/24July26/W3_match_full_2.pcapng`.

A WW3 client pointed here via the M2 matchmaking handoff (hub returns `127.0.0.1:7871`)
should now complete the handshake against `server.py`.

## M2 — control channel (DECODED — see `docs/M2_ControlChannel_Findings.md`)

Decoded from the same captures. **Packet framing is legacy UE4** (not FNetPacketNotify):
`bit0 bHandshakePacket=0` + `bits1..14 PacketId` (14-bit sequence, +1 per packet per direction)
+ ack/bunch stream + terminator. Control-message order: client **NMT_Hello** → server
**NMT_Challenge** → client **NMT_Login** → server **NMT_Welcome/map**.

The **NMT_Login** (the join) carries three fields, all pulled off the wire:
1. URL FString: `<map>?Name=<name>?BuildIdOverride=51?EosProductUserId=<puid>`
2. UniqueId (SteamID)
3. **lobbyToken** — a separate trailing FString (HS256 JWT), structure matches our M1 spec /
   M2 mint field-for-field. We mint AND validate it with our own secret (`ww3-local-private`).

## M2 — control channel (BUILT + validated)

`control_channel.py` implements the legacy UE4 packet + bunch codec (reader **and** writer),
validated by round-tripping the real captured Hello/Challenge/Login packets **byte-for-byte**.
`server.py` drives the NMT state machine on top of it: `NMT_Hello → NMT_Challenge`,
`NMT_Login → validate lobbyToken (HS256, our secret) → NMT_Welcome`, with packet sequencing
and acks. `test_m2_e2e.py` runs the whole M1+M2 join and the server reaches **LOGGED_IN**.

Legacy packet framing (locked): `bit0 bHandshakePacket=0` + `14-bit PacketId` +
`ack section (while bit: 14-bit AckId)` + bunch(es) + **two** terminator bits (inner
UNetConnection + outer PacketHandler). Bunch header: bControl/bOpen/bClose, bReliable,
ChIndex(packed), 3 flags, ChSequence(10b if reliable), ChName(5-bit const per direction),
BunchDataBits(13b), payload. Control-message payload = NMT type byte + fields.

### Live-client verification (2026-07-24) — M1+M2 PROVEN

Run `windows\ww3_matchtest.ps1` (elevated): brings up the mocks + this server on UDP 7871 +
the game, auto-tears-down, and logs every datagram to `live_log/session_*.jsonl`.

The real WW3 client completed the whole path against this server:
`handshake → NMT_Hello → NMT_Challenge → NMT_Login (real lobbyToken, validated) → NMT_Welcome
→ client LOADED the map → NMT_Netspeed 100000 → NMT_Join`.

**Five bugs, each findable only with a live client** (all fixed):
1. **Ack entry is 24 bits**, not 15: `IsAck(1)+AckId(14)+bHasServerFrameTime(1)[+8]+RemoteInKBytesPerSecond(8)`.
2. **Sequences come from the handshake cookie**, not 0 (`sequences_from_cookie`) — otherwise the
   client buffers our bunches as out-of-order forever (silent hang).
3. **MAX_CHSEQUENCE = 4096** (12-bit ChSequence) followed by a **3-bit ChType** (1=Control, 2=Actor).
4. **WW3's NMT_Welcome takes FOUR FStrings**, not three (the 4th is empty) — sending three made
   the client close the channel.
5. **Close bunches carry a 2-bit close reason** after `bClose`.

The server also runs a ~200ms keepalive because the real server sends continuously even when idle.

## M4 — possession diagnosis: read the CLIENT's side

Every server-side theory for "the client never maps pawn NetGUID 9372" has now been
ground-truthed against the original pcap and refuted (`docs/M4_Possession_Findings.md`).
What was missing was any view of what the *client* thinks. Two channels now exist:

**1. The client's own UE log (no crash needed).** The client uploads its log lines to the
backend over the hub websocket (`context=debug, method=log`), including Warning/Error —
which is the level at which UE prints `SerializeNewActor failed to find/spawn actor`,
`Queued bunches for longer than...`, `Corrupt partial bunch`, `Network checksum mismatch`.
`hub_server.py` used to discard these; it now writes them to
`match_server/live_log/client_log/client_<ts>.log` plus a `_net.log` sidecar.

| env (hub) | default | effect |
|---|---|---|
| `WW3_CLIENT_LOG_CAPTURE` | `1` | record the client's uploaded log lines |
| `WW3_CLIENT_LOG_DIR` | `match_server/live_log/client_log` | where to write them |
| `WW3_CLIENT_LOG_NET` | `0` | also ask the client (via `logsConfig`) to raise verbosity on `LogNet*`/`LogSpawn`. Off by default: unmeasured log volume |

Read it with `python match_server/watch_client_log.py [--follow] [--all]`.
The same categories can be turned up at launch with
`.\windows\ww3_play_dedicated.ps1 -NetLogCmds` (appends to the client's `-LogCmds`).

**2. Ack audit (`WW3_ACK_AUDIT=1`, default off).** UE4 acks at the packet layer, but
deliberately *skips* the ack when `UChannel::ReceivedNextBunch` returns `bOutSkipAck`
during partial-bunch reassembly. So whether the client acks the datagram carrying the
ch3 pawn open splits the remaining search space in half:

- **ACKED** → the bytes reached the channel layer intact; the pawn dies later, in
  `SerializeNewActor` / archetype resolution / queued bunches. Look in the client log.
- **NOT ACKED** → the client threw the bunch away during reassembly. That is a framing
  problem that bit-comparing against the pcap cannot see, because it depends on the
  client's live per-channel partial state rather than on the bytes alone.

The audit only watches packets carrying ch3/ch4/ch5 bunches, reads acks we already
receive, and never resends anything — zero wire change.
`WW3_ACK_AUDIT_VERDICT_S` (default 3.0) is how long to wait before calling it unacked.

## M4 — experiment #1: `WW3_PAWN_EXPORT_PREFIX` (pre-registered archetype+level GUIDs)

Two-agent consult (`live_log/agent_runs/LATEST_SYNTHESIS.md`, run `20260805_191543`)
proposed sending the pawn open's `MustBeMapped` export GUIDs *before* the ch3 open.
Reconciled against `docs/M4_Possession_Findings.md` fact #1 (`bHasMustBeMappedGUIDs`
is genuinely `0` on the real wire for the pawn open, ground-truthed against the raw
pcap) — that flag on the open bunch itself is **not** touched. What's actually new is
a **separate** bunch: `pawn_export_prefix.py` slices the pawn open's own PackageMap
export table (`_dump_pawn_export_paths.py`) down to just its first two top-level,
*static* entries — archetype (`NetGUID 21`, outer chain `23`) and spawn level
(`NetGUID 5`, outer chain `9→7→5`) — and re-emits them, byte-identical, as a
standalone `bHasPackageMapExports=1` bunch on the already-open PC channel (ch2)
immediately before the (byte-for-byte untouched) ch3 pawn open. The six dynamic
subobject exports (outer=9372, the pawn itself) are deliberately excluded — they
can't resolve before the pawn actor exists.

| env | default | effect |
|---|---|---|
| `WW3_PAWN_EXPORT_PREFIX` | `0` | `1` inserts the ch2 export-prefix bunch right before the pawn ch3 open in `ownership_bootstrap.json` |
| `WW3_PAWN_EXPORT_PREFIX_N` | `2` | how many top-level export entries to pre-send (2 = archetype+level only) |
| `WW3_PAWN_EXPORT_PREFIX_CH` | `2` | carrier channel (must already be open by the time the pawn is queued — ch2/PC is) |

Success signal: `ServerAcknowledgePossession(Pawn 9372)` + C→S traffic on ch3/ch4/ch5.
Rollback: `WW3_PAWN_EXPORT_PREFIX=0` (or unset) — no other behavior changes.
Unit tests: `python match_server/test_pawn_export_prefix.py`.

## M4 — experiment #2: single-shot `ClientRestart(39)`

`WW3_CLIENT_RESTART=1` (server default) sends `ClientRestart` (wire handle 39 only —
never the neighbour handles 38/`ClientReset` or 41/`ClientReturnToMainMenu`) once the pawn
channel has opened, capped by `WW3_CLIENT_RESTART_MAX_SPRAYS`.
**No Retry is ever sent unless `WW3_CLIENT_RESTART_SEND_RETRY=1`** — the old
always-Retry behavior sprayed the Retry handle and got the client kicked to the lobby.

> **Handles changed on 2026-08-06.** They used to be 9/10 (and
> `ServerAcknowledgePossession` 34); the real values are 39/40 and 64. The old numbers
> came from decoding a *fixed-width* 8-bit field handle as `SerializeIntPacked`, which
> halves it, and the crafted RPC was also missing its `NumPayloadBits` field entirely —
> so no `ClientRestart` we ever sent could dispatch. See
> `match_server/live_log/HANDLE_DERIVE.md` and `docs/M4_Possession_Findings.md` #12–13.
> The table now comes from `class_net_cache_ww3.json`, regenerated from the Dumper-7 dump
> by `python match_server/derive_net_handles.py --json match_server/class_net_cache_ww3.json`.

| env | default | effect |
|---|---|---|
| `WW3_CLIENT_RESTART` | `1` | `0` disables the RPC entirely (and now logs that it did) |
| `WW3_RPC_HANDLE_BITS` | from cache doc (`8`) | width of the ClassNetCache field handle; only needed if a client class pushes `MaxIndex` past 255 |
| `WW3_CLIENT_RESTART_MUSTMAP` | `0` | `1` sets `bHasMustBeMappedGUIDs` + the GUID prefix so the client queues the RPC until 9372 maps |
| `WW3_CLIENT_RESTART_MBM_FALLBACK_S` | `0` | `>0` sends **one** follow-up shot with the opposite `MustMap` framing after N s, so a silent MustBeMapped run still yields an Ack oracle. Forces the non-MustBeMapped shot to go first (see below) and overrides `_MUSTMAP` for the ordering. |

An unresolvable MustBeMapped bunch parks in `UActorChannel::QueuedBunches` and every
*later* reliable bunch on that channel queues behind it. Live session `20260805_194518`
sent MustBeMapped first and its executable follow-up 8 s later drew no reply at all, on a
connection that then carried 10894 more C→S bunches. Whenever both framings are wanted,
the executable one must be sent first — the server now enforces that.
| `WW3_CLIENT_RESTART_AFTER_PAWN_MS` | `0` | hold the RPC until N ms after the ch3 pawn open was sent |
| `WW3_CLIENT_RESTART_REQUIRE_CH3_ACK` | `0` | with `WW3_ACK_AUDIT=1`, hold the RPC until the client ACKs the packet carrying the ch3 open |
| `WW3_CLIENT_RESTART_GATE_TIMEOUT_S` | `20` | escape hatch: after this long since the pawn open, the gates above stop blocking |
| `WW3_CLIENT_RESTART_SEND_RETRY` | `0` | `1` also sends wire-10 `ClientRetryClientRestart` (known lobby kick — leave off) |
| `WW3_CLIENT_RESTART_MAX_SPRAYS` | `4` | total Restart bunches for the connection (`1` = true single shot; use `2` with the MBM fallback) |

### Why the flags are now echoed into the server's own log

The launcher prints its banner to the PowerShell host, but the server's stdout is
redirected to `live_log/match_console_<ts>.out.txt`. Session `20260805_193023` was
launched with `WW3_CLIENT_RESTART=0` and analysed as though Restart had been attempted
and failed (see `live_log/EXPORT_PREFIX_LIVE.md`). Two changes stop that recurring:

- `server.py` prints a `=== possession flags ===` banner at startup listing every
  possession-relevant env var, its value, and whether it came from the env or a default.
- Every path that declines to send a Restart logs
  `*** M4: ClientRestart NOT sent - <why> ***` once per distinct cause, so an empty log
  can no longer be mistaken for "we tried and the client ignored it".

## M4 — experiment #3B: `WW3_PC_SET_PAWN` (re-state `PlayerController::Pawn`)

`WW3_PC_SET_PAWN=1` (default `0`) sends a PC actor RepLayout block on ch2 setting
`APlayerController::Pawn = NetGUID 9372` immediately before the `ClientRestart` RPC.
The encoding is not invented — `possess_rpc.build_pc_set_pawn_bits()` reproduces the
capture's own bytes (`real_replay_stream` src=13: packed handle `34`, one `0` bit, packed
NetGUID), asserted bit-for-bit by `test_possess_rpc.py::test_pc_set_pawn_matches_capture_bits`.
The bootstrap already replays src=13, but that lands *before* ch3 opens; this restates
the binding with the pawn channel open and directly ahead of the Restart.
`WW3_PC_PAWN_HANDLE` overrides the property handle if it is ever recalibrated.

The other half of experiment #3 (re-encoding the pawn open's own `Owner`/`PlayerState`)
is **not** implemented: the pawn's `Owner` is not in the open bunch at all (findings
fact #2), and `real_replay_stream.json` only contains 6 ch3 specs — every actor RepLayout
in them uses handle `10`, with no object-ref-shaped values — so `BP_PlayerPawn_01_C`'s
Owner/PlayerState handles are unknown. Guessing a handle would corrupt the channel.
Deriving them needs a full re-scan of ch3 across the original pcap.

Combined run (server only, game/client already up on the hub):

```powershell
.\windows\ww3_play_dedicated.ps1 -NoGame -AckAudit -PawnExportPrefix `
    -RestartMustMap -RestartAfterPawnMs 1500 -RestartRequireCh3Ack `
    -RestartMbmFallbackSec 8 -PcSetPawn
```

`ClientRestart` is on by default now; `-NoClientRestart` turns it off.
Unit tests: `python match_server/test_restart_gating.py`.

## Wiring to the rest of the stack

- `mockserver/hub_server.py` (M2 already built) hands a client a lobby → a server address
  (`WW3_MATCH_ADDR`/`WW3_MATCH_PORT`, default `127.0.0.1:7871`) → a minted `lobbyToken`.
  Point those at this server and the client will try to connect here.
- Once M1–M2 land, the client presents the `lobbyToken` in its `NMT_Login` URL; our server
  validates it (HS256, our secret) and admits the player.

## Reality check

This is a large, specialist-grade build; M1–M4 are the achievable near-term milestones,
full matches are a long tail that may warrant a UE4-networking specialist. But every
milestone is a real, testable step, and the foundation here is correct and reusable.
