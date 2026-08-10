# World War 3 — Preservation Project · Full Handoff & Continuation Guide

**Purpose:** everything needed to continue this project with a fresh AI/engineer. Written as a technical reference, not marketing. Compiled 24 July 2026.

---

## 0 · TL;DR — where we are right now

- **Stage 1 (boot the game offline to a fully-unlocked menu, no live servers): COMPLETE & stable.**
- **Solo / Training mode: playable offline today.**
- **Stage 2 (multiplayer matches): in progress.**
  - **Path A (use the official dedicated server): DEAD** — the client build can't run as a true dedicated server, and the official server app is license-locked ("No licenses"), being deleted from Steam, and the only builds that existed are 2019–2020 early-access (incompatible with the current build 2481).
  - **Path B (reimplement the UE4.21 match server): STARTED.** Foundation built and tested. **The connect handshake has been captured and partially decoded.**
- **Immediate next step:** lock the exact bit-layout of the `StatelessConnect` handshake from the captured bytes (details in §7), then M2 (control channel) → M3 (load map) → M4 (player pawn).

---

## 1 · The project

**Game:** World War 3 — a multiplayer-only tactical FPS on **Unreal Engine 4.21**, Steam **app 674020**, current build **2481**. Publisher (The 4 Winds Entertainment) is **shutting the servers down 3 August 2026**, after which the retail game is unplayable.

**Goal:** preserve a legitimately-owned copy so it stays playable offline/privately after shutdown — by replacing the publisher's backend with local stand-ins, and (Stage 2) reconstructing the match server.

**Owner's backup of the game:** `E:\WW3_Playable_Backup\World War 3\`
Client exe: `E:\WW3_Playable_Backup\World War 3\WW3\Binaries\Win64\WW3-Win64-Shipping.exe`
Project workspace: `F:\Dev_Work\GameDev\WW3\`

---

## 2 · Architecture — the service chain

The client walks a strict chain each launch; each link must succeed:

```
CLIENT
  → IDENTITY/LOGIN   id.wishlistgames (FXID JWT)
  → META/PROFILE     meta.prod.ww3.fxtools.gl:443   (HTTPS REST, ~25 endpoints)
  → HUB/MENU         WebSocket JSON-RPC :8700        (real 213.183.62.234:8700)
  → PRESENCE         xmpp.prod.ww3.fxtools.gl:5222   (XMPP)
  → EPIC EOS         api.epicgames.dev               (anti-cheat/identity)
  → MATCHMAKING      via the hub → server handoff
  → MATCH SERVER     213.183.62.18:786x  UDP         (UE4 netcode)
```

**Key exploit that makes it all work:** the client's HTTP library uses `bVerifyPeer=false` (accepts any TLS cert for the ww3 hosts). Server names are redirected to `127.0.0.1` via the Windows `hosts` file. Tokens are JWTs the client only *couriers* between services — it never verifies their signatures — so we mint/forge our own.

---

## 3 · Stage 1 — COMPLETE (offline menu)

### What was built (all in `F:\Dev_Work\GameDev\WW3\mockserver\`)
- **`rest_server.py`** — serves meta/profile on :443 + :80 from captured data (`replay_map.json`); mints the FXID→PlayerToken and hub-URL tokens; **also contains the Epic faker and the M3 server-role endpoints** (see §5).
- **`hub_server.py`** — the hub WebSocket on :8700; serves captured RPC + `onlineParameters`; sends a server-initiated `HeartbeatPing` every 4 s; **also contains the M2 matchmaking layer** (see §5).
- **`xmpp_server.py`** — presence on :5222; binds the client's JID as `prod-100001` (the real player id — a stale id caused a reconnect loop, now fixed).
- **`epic_faker.py`** — forges Epic EOS tokens (RS256, our own key under Epic's `kid 2022-06-14T06:17:57...`), serves our JWKS. **WW3-scoped** (see §9 Safety).
- **`god_profile.py`** — rewrites the profile: level 52, all 1,675 items, all loadout slots, max currency.
- **`make_synthetic_token.py`** — mints a 10-year synthetic FXID token (HS512).
- **`replay_map.json`** — the captured protocol map (god-profile applied).

### Orchestration (`F:\Dev_Work\GameDev\WW3\windows\`)
- **`ww3_mock.ps1 forever`** — installs our CA, redirects the ww3 hosts + `api.epicgames.dev`, starts the mocks. **`down`** reverts everything.
- **`launch_offline.ps1 eac`** — launches the backup game offline (via `start_protected_game.exe`) with the synthetic token.
- **`ww3_play.ps1`** — **safe session wrapper**: brings up the stack, launches the game, and *guarantees* teardown on exit/crash/Ctrl-C.

### Result
Boots 100% offline to a fully-unlocked main menu, stable (no reconnect pop-ups), on a synthetic 10-year token, with **zero live servers** contacted. Verified working.

---

## 4 · Stage 2 — Multiplayer: what we learned

### 4a · Feasibility — GREEN
Match traffic is **plaintext & uncompressed** (Shannon entropy 4.8–5.9 bits/byte across all activities; AES would be ~8.0, compression ~7.5). It's stock UE4.21 `UNetConnection`. UE4.21 engine source is public. So the wire format is decodable, not guessed.

### 4b · Solo / Training — WORKS offline
Training mode uses a separate offline path (`UWW3OfflinePlayerProfileManager`) and plays fully offline (real map, full mechanics) from our menu. No server needed.

### 4c · Path A (official dedicated server) — DEAD (thoroughly confirmed)
- **The client can't be a true dedicated server.** Run with `-server -nullrhi` it boots headless and talks to our backend, but on every map it spawns a *local player* (`?Name=Player` in the browse URL) and crashes: `FindPlayerStart: NO PLAYERSTART` → `Assertion: Array index out of bounds` → NaN. It's a "Game" target (has server *code*, listen-server capable) but not a Server-target *build*.
- **The official server binary** is a separate Steam app — **"World War 3 Dedicated Server", app 912100** (depot 912101). It is **not obtainable**: SteamCMD anonymous = "Missing configuration"; owner login = **"No licenses"** (owning the game doesn't grant it; it's partner-only). SteamDB shows the developers **deleting** its encrypted files/manifests, and the only manifests that ever existed are **2019–2020 early-access** builds — incompatible with the current client. **No legitimate path exists.**

### 4d · Path B (reimplement the match server) — STARTED
This is the only remaining route to real matches. Feasible but large/specialist. Foundation is built (§6) and the connect handshake is captured (§7).

---

## 5 · The match-orchestration protocol (reverse-engineered — the M1 spec)

Full spec: `F:\Dev_Work\GameDev\WW3\docs\M1_Match_Orchestration_Spec.md`. Summary of the contract:

**Matchmaking (hub WebSocket, JSON-RPC):**
```
client → RpcRequest lobby.findLobbyForParty | findCustomLobbyForParty
         args: {gameModes:[47], maps:["WW3_DMZ_P"], serverGroup:"default",
                playerId:100001, partyMembers:[100001], clientRevision:2481}
hub → RpcResponse {lobby}
hub → LobbyChange (players added, teamId 0/1, squadId)
hub → LobbyReadyStateChange {target:{server:{...handoff...}}, lobby:{teams,players}, lobbyToken}
hub → LobbyMatchStarted
```
Teams: two teams id 0/1, size 8 each (16-player cap). Players carry `playerId, playerName, level, teamId, squadId, xmppAccount.username="prod-<id>"`.

**Server handoff object:**
```json
{"serverId":286109716,"matchId":"286109716-<epochMs>","address":"213.183.62.18",
 "gamePort":7871,"queryPort":27115,"serverGroup":"default","gameMode":47,"map":"WW3_DMZ_P"}
```

**`lobbyToken` — the admission credential (HS256 JWT, FORGEABLE — we control issuer+verifier):**
```json
{"type":"LobbyToken","lobbyId":66943,"playerId":100001,"serverGroup":"default",
 "team":{"id":0},"isServerAssigned":false,"server":{...handoff...},"iat":...,"exp":iat+3600}
```
The client presents this to the match server on connect; the server validates it and admits the player onto their team.

**M2 — matchmaking layer: BUILT** (in `hub_server.py`, `M2_ENABLED`). Answers `findLobbyForParty`/`findCustomLobbyForParty` → runs the lobby lifecycle → returns a handoff pointing at a **local** server (`WW3_MATCH_ADDR`/`WW3_MATCH_PORT`, default `127.0.0.1:7871`) + a freshly-minted `lobbyToken` (HS256, secret `"ww3-local-private"`). WebSocket integration test passes.

**M3 — dedicated-server-role backend: BUILT** (in `rest_server.py` + `hub_server.py`). The match server (a game instance) talks to the backend over REST + a *separate* hub WebSocket:
- REST: `/events/getWebSocketUrl` → `ws://…/server/<token>`; `POST /server/register`, `/server/update`, `/server/lock`; `/AuthenticateUserTicket/<id>`; `/matchmaking/lobby/getAll`; `/DedicatedServer/matchSummary/<n>`.
- Hub: connections on the `/server/` path are handled by `server_handler`, which serves the game-mode config (from `getGameModesParameters`) to the server's `GameModeConfigReader`. RPC types the server uses: `ServerLobbyChange`, `RemovePlayerOnServerDemand`, `PlayerLogoutFromDedicatedServer`; contexts `server.metrics`, `server.global.errors`.
*(M3 backend is correct and ready — it just has no server to drive, since Path A is dead. Its endpoints will also serve a Path-B server if useful.)*

---

## 6 · Path B foundation — BUILT (`F:\Dev_Work\GameDev\WW3\match_server\`)

| File | What it is | Status |
|---|---|---|
| `ue4_bits.py` | UE4 `FBitReader`/`FBitWriter` — LSB-first bit packing. Foundation for handshake/packet-headers/bunches/replication. | ✅ round-trip test passes |
| `stateless_handshake.py` | UE4.21 `StatelessConnectHandlerComponent` (server side): parse InitialConnect → send ConnectChallenge → validate ChallengeResponse. Cookie = HMAC-SHA1 with **our own** secret. | ✅ round-trips; **bit layout pending capture-lock** |
| `server.py` | UDP match server + connection state machine (HANDSHAKING→CONNECTED). `python server.py 7871`. | ✅ runs |
| `analyze_handshake.py` | Decodes a capture's connect handshake to validate/lock the layout; auto-detects the match-server endpoint. | ✅ tested |
| `README.md` | Path B milestones + wiring notes. | — |

**Milestones:** M1 handshake → M2 control channel (`NMT_Hello`/`NMT_Login` + the `lobbyToken`) → M3 load a map (client into empty world) → M4 replicate the player pawn (first playable) → long tail (others/bots/vehicles/combat).

---

## 7 · The connect handshake — CAPTURED, partially decoded (immediate work)

A fresh full-match capture was recorded **from before the client joined** (this is the one piece that could only be captured while servers were live — done in time). Files in `F:\Dev_Work\GameDev\WW3\captures\24July26\`:
- `W3_match_full_1.pcapng`, `_2.pcapng`, `_3.pcapng` (three full matches, **with the handshake**)
- `ww3_StrongHold*.pcap`, `ww3_tacops_DMZ.pcap`, `Match_tacops_tokyo…zip` (more handshakes to cross-validate)
- `LOBBY-…zip` (matchmaking side — validate M2)

**Decoded so far** (from `W3_match_full_2.pcapng`, match server `213.183.62.18:7868`, flow starts at frame 33,523):
```
[0] C->S 25B  InitialConnect   01 00 00 … 00 04                 (our decoder confirms initial=True ✓)
[1] S->C 25B  ConnectChallenge f3 c2 b5 0e 65 | <20-byte cookie: 7c bd e0 fb … a3 b5 06>
[2] C->S 25B  ChallengeResponse — BYTE-IDENTICAL to [1] (client echoes the challenge verbatim)
[4+] game packets (bit0=0) — connection established
```
Confirmed: handshake packets are 25 bytes; the **first bit is `bHandshakePacket`**; the **cookie is the trailing 20 bytes**; the client **echoes the whole challenge back**. No magic-header prefix.

**What's NOT yet locked:** the exact encoding of the **5-byte header** before the cookie (bytes 0–4 / ~40 bits) — `bHandshakePacket`, `bRestartHandshake`, `SecretId`, and the `Timestamp`. My first-pass assumed a 64-bit double timestamp right after 3 flag bits; that decodes to garbage, so the real layout differs (the header is only ~40 bits, not 3+64). 

**Immediate task for the continuing AI:**
1. `cd match_server; python analyze_handshake.py ../captures/24July26/W3_match_full_2.pcapng`
2. Cross-reference the **all-zero InitialConnect** vs the **real Challenge** across the three captures (the cookie/timestamp vary per connection; the fixed layout is what's constant) to determine the exact header field widths/order.
3. Fix `stateless_handshake.py` (`build_challenge`/`parse_incoming`) until a Challenge decodes to a sane elapsed-seconds timestamp + 20-byte cookie, and our regenerated challenge matches the captured server's format.
4. Reference: UE 4.21 `Engine/Source/Runtime/PacketHandlers/PacketHandler/Private/StatelessConnectHandlerComponent.cpp`. Note UE4.21's timestamp may be sent as fewer than 64 bits, and the packet likely ends with a terminator bit (highest set bit) — account for that when computing bit length.
5. Then point a real client at `server.py` (via the M2 handoff) and confirm it completes the handshake.

---

## 8 · Captured data inventory

- `captures/24July26/*.pcapng|pcap` — **fresh matches WITH the connect handshake** (the key Path-B data). Also a LOBBY capture.
- `captures/match/*.pcap` — earlier match captures, but **mid-session** (no handshake). Useful for gameplay-replication study later.
- `captures/backend/*.pcap` — client↔backend HTTPS/HTTP (SNI/IPs only; encrypted bodies).
- `windows/record_logs/hub.log` (5.4 MB) — full matchmaking→lobby→handoff flow with the real `lobbyToken` (decoded in the M1 spec).
- `mockserver/replay_map.json` — the captured menu/meta/hub protocol (god-profile applied).
- `match_analysis/pcap_tools.py` — pure-Python pcap parser (no scapy/tshark).
- Note: all captures are **client-side only** — the studio's server↔backend traffic was never on our wire.

---

## 9 · Key technical reference

**Ports:** meta 443/80 · hub WS 8700 · xmpp 5222 · Epic 443 (api.epicgames.dev) · match UDP 786x (game 7871, query 27115).
**Player identity:** playerId **100001**, name "OfflinePlayer", xmpp `prod-100001`, fxGamesId 100001, steamId 76561198000000000.
**Local secrets (ours, chosen):** HS256/HS512 JWT secret `"ww3-local-private"`; Epic RS256 key at `mockserver/epic_ca/forge_rsa_key.pem` under `kid 2022-06-14T06:17:57.047928700Z`.
**Epic (EOS) IDs:** ClientId `xyza78913PNJAxLsnw1B5OGzaAYR4zPW` · ProductId `fd268a599d7e49dda99dd002488e9fa2` · DeploymentId `0bf47cddeab54c08b0358c134ec54408` · SandboxId `54ddf5e8d6b3441ea0d56726677dd234`.
**Map package names (from `/sharedData/maps/getAll`):** WW3_DMZ_P, WW3_Berlin_P, WW3_Moscow_P, WW3_Smolensk_P, WW3_Warsaw_P, WW3_Polarnyj_P, WW3_Tokio_P, WW3_Shibuya_P, WW3_Gobi_New_P, WW3_Landmark_P (+ sub-maps). Non-match: `WW3_Hub_P` (hub), `WW3_Menu_P`.
**Game modes (C++ classes):** WW3ReconGameMode, WW3TeamDeathmatchGameMode, WW3DominationGameMode, WW3GunGameGameMode, WW3HVTGameMode, WW3BreakGameMode, WW3TransmissionGameMode, WW3VehiclesGameMode, WW3TutorialGameMode… (`gameMode:47` numeric id → mode mapping still TODO, resolvable via `getGameModesParameters`).
**Paks:** AES-encrypted, key is **obfuscated** in the exe (not extractable by plain scan — specialist RE if ever needed).

### Safety (important — do not skip)
The Epic faker is **WW3-scoped**: it only forges requests carrying WW3's ClientId/Product/Deployment/Sandbox ids; **all other EOS traffic is transparently proxied to real Epic** (so other games like Hunt keep working). This was added after an incident where the un-scoped faker handed *Hunt* the WW3 productUserId and got the user kicked. **Rule: never leave `api.epicgames.dev` redirected without the scoped faker running; always tear down with `ww3_mock.ps1 down` (or use `ww3_play.ps1` which auto-teardowns).** Never handle the user's Steam credentials.

---

## 10 · How to run (current capabilities)

**Offline menu / solo (Stage 1 — works):** from an elevated PowerShell in `F:\Dev_Work\GameDev\WW3\windows\`:
```
.\ww3_play.ps1            # brings up mocks, launches game, auto-cleans on exit
```
Then use the menu; enter Training for offline gameplay.

**Path B handshake work (no game needed):**
```
cd F:\Dev_Work\GameDev\WW3\match_server
python ue4_bits.py                 # foundation self-test
python stateless_handshake.py      # handshake self-test
python analyze_handshake.py ..\captures\24July26\W3_match_full_2.pcapng   # decode the real handshake
python server.py 7871              # run the match server (once M1 is locked)
```

---

## 11 · The path forward (ordered)

1. **Lock M1** — the handshake bit-layout, from the captured bytes (§7). *← you are here.*
2. **M2 control channel** — after handshake, parse the client's `NMT_Hello`/`NMT_Login` (control channel 0, bunches), read the `lobbyToken` from the login URL, admit the player.
3. **M3 load a map** — send the client into an empty world (the client already knows the map from the handoff).
4. **M4 replicate the player pawn** — spawn + replicate movement so the player can move. First playable moment.
5. **Long tail** — other players/bots, weapons, vehicles, combat, hit-reg. This is where a UE4-networking specialist is genuinely warranted.

Reference throughout: the **plaintext captures** in `captures/24July26/` and the **public UE4.21 engine source**. Cross-validate every implemented layer against the real packets.

---

## 12 · Honest scope note

Stage 1 is a complete, real preservation result: the game boots and plays (solo) offline forever from the backup, with the multiplayer backend fully mapped. Stage 2/Path B is a **large, specialist-grade build** — M1–M4 are achievable near-term milestones; full competitive matches are a long road. Nothing here is blocked by the shutdown anymore: the one time-sensitive item (the connect-handshake capture) was secured before Aug 3.
