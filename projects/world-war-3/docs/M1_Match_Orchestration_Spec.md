# WW3 Match Orchestration — M1 Specification

**Phase M1 of the private-server multiplayer roadmap.** Reconstructs the contract by which the WW3 client is matched to a server, admitted to it, and placed on a team — derived entirely from client-side captures (`windows/record_logs/hub.log`, `captures/match/*.pcap`, and the captured `/sharedData/getGameModesParameters`). No server-side traffic exists (the studio's infrastructure was never on our wire); everything here is the **client half** of the contract, which is what a private server must satisfy.

Evidence classification is noted throughout: **[OBSERVED]** = directly in captures, **[INFERRED]** = strongly supported, **[GAP]** = not captured, must be resolved in M2/M3.

---

## 1. The match lifecycle (end to end)

```
   CLIENT                         HUB (WebSocket JSON-RPC :8700)          MATCH SERVER (UDP)
     │                                    │                                    │
     │  1. lobby.findLobbyForParty ─────► │                                    │
     │     (gameModes, maps, serverGroup) │  creates/joins a lobby             │
     │  ◄─ RpcResponse {lobby}            │                                    │
     │                                    │                                    │
     │  ◄─ LobbyChange (players added,    │  lobby fills with players,         │
     │     teamId/squadId assigned)  ─────┤  assigns teams (0/1), squads       │
     │                                    │                                    │
     │  ◄─ LobbyReadyStateChange ─────────┤  server allocated; issues          │
     │     { server{addr,port,matchId},   │  a signed lobbyToken per player    │
     │       lobby{teams,players},        │                                    │
     │       lobbyToken (HS256 JWT) }     │                                    │
     │                                    │                                    │
     │  ◄─ LobbyMatchStarted              │                                    │
     │                                    │                                    │
     │  2. UE4 netcode connect ───────────┼──────────────────────────────────►│
     │     to server address:gamePort,    │        presents lobbyToken         │
     │     presenting the lobbyToken      │        server validates (HS256),   │
     │                                    │        admits player to team       │
     │  ◄──────── replicated gameplay ────┼───────────────────────────────────┤
```

Two transports: **matchmaking** happens over the Hub WebSocket (JSON-RPC, plaintext — fully reconstructed); the **match itself** is UE4 `UNetConnection` over UDP (plaintext/uncompressed — separately confirmed decodable).

---

## 2. Matchmaking request  **[OBSERVED]**

Client → Hub. Two variants seen: `lobby.findLobbyForParty` (public matchmaking) and `lobby.findCustomLobbyForParty` (custom). Identical arg shape:

```json
{ "type": "RpcRequest", "context": "lobby", "method": "findCustomLobbyForParty", "id": 9,
  "args": [{
    "gameModes": [47],
    "maps": ["WW3_Gobi_New_P"],
    "serverGroup": "default",
    "playerId": 100001,
    "partyMembers": [100001],
    "clientRevision": 2481
  }]}
```

- `gameModes` — array of **numeric** mode ids (see §6). `maps` — desired map package name(s).
- `serverGroup` — server pool selector (`"default"` observed).
- `partyMembers` — playerIds queuing together.
- `clientRevision` — build number (2481); the server can gate on this.

**Response** (`RpcResponse`, same `id`) returns the initial `lobby` object the client was placed in.

Other matchmaking RPCs observed: `lobby.cancelMatchmaking`, `lobby.removePlayerFromLobby`.

---

## 3. Lobby object + team model  **[OBSERVED]**

The lobby is pushed to the client as it fills. Full shape:

```json
{ "id": 66943, "playersLimit": 16, "gameMode": 47, "map": "WW3_Gobi_New_P",
  "players": [
    { "playerId": 100001, "playerName": "OfflinePlayer", "level": 14, "status": 4,
      "xmppAccount": {"username": "prod-100001"},
      "bannerAttachmentsIds": [6382,7953,7224], "teamId": 0, "squadId": null }
  ],
  "teams": [
    { "id": 0, "size": 8, "players": [100001], "squads": [], "supportsSquads": false, "nextSquadId": 1 },
    { "id": 1, "size": 8, "players": [],       "squads": [], "supportsSquads": false, "nextSquadId": 9 }
  ],
  "state": 3, "gameStartTimestamp": 1784765580721, "version": 3,
  "serverGroup": "default", "supportsSquads": false }
```

- **Two teams**, ids `0` and `1`, `size` 8 each → 16-player cap (`playersLimit`). Squads are a sub-grouping (`squadId`), disabled for this mode (`supportsSquads:false`).
- Players carry `playerId`, `playerName`, `level`, `teamId`, `squadId`, and `xmppAccount.username` = `prod-<playerId>` (the presence identity).
- `state` is an enum; `3` = Ready (see §5). `version` increments on every change (optimistic-concurrency).

**Lobby lifecycle push events** (server → client): `LobbyChange` (delta of players added/removed, each with resolved `teamId`/`squadId`), `LobbyReadyStateChange`, `LobbyMatchStarted`, `LobbyClosed`, `LobbyLeft`, `LobbyAbandoned`.

`LobbyChange` delta example:
```json
{ "type": "LobbyChange", "target": { "id": 67034,
    "players": { "added": [ { "playerId": 100001, "teamId": 0, "squadId": null, ... } ], "removed": [] },
    "version": 2 } }
```

---

## 4. The server handoff  **[OBSERVED]**

When a server is allocated, the `server` object appears (inside `LobbyReadyStateChange.target.server` and inside the lobbyToken):

```json
{ "serverId": 286109716,
  "matchId": "286109716-1784765433111",
  "address": "213.183.62.18",
  "gamePort": 7871,
  "queryPort": 27115,
  "serverGroup": "default",
  "gameMode": 47,
  "map": "WW3_Gobi_New_P" }
```

- `address` + `gamePort` = where the client opens its UE4 connection (UDP). `queryPort` = a separate query/stats port.
- `matchId` = `<serverId>-<epochMillis>`. Unique per match; the server and every client agree on it.

---

## 5. The lobbyToken — the admission credential  **[OBSERVED, decoded]**

The single most important artifact. Delivered in `LobbyReadyStateChange.lobbyToken`. It is a **JSON Web Token**:

- **Header:** `{"alg":"HS256","typ":"JWT"}` — HMAC-SHA256, a **shared-secret** signature. The client cannot verify it (only the backend and the match server share the secret) — so, exactly like every other token in this project, **it is forgeable by anyone who controls both the issuer and the verifier** (which, for a private server, we do).
- **Payload:**

```json
{ "type": "LobbyToken",
  "lobbyId": 66943,
  "playerId": 100001,
  "serverGroup": "default",
  "team": { "id": 0 },
  "isServerAssigned": false,
  "server": { "serverId": 286109716, "matchId": "286109716-1784765433111",
              "address": "213.183.62.18", "gamePort": 7871, "queryPort": 27115,
              "serverGroup": "default", "gameMode": 47, "map": "WW3_Gobi_New_P" },
  "iat": 1784765469, "exp": 1784769069 }
```

The token binds **a player** (`playerId`) to **a team** (`team.id`) on **a specific match** (`server.matchId`), with a ~1-hour expiry (`exp - iat` = 3600s). This is what the client presents to the match server; the server validates the signature and reads `playerId`/`team`/`matchId` to admit the player onto the correct team.

**Implication for private servers:** we mint our own lobbyTokens (HS256, our secret) and hand both the hub-issued token to the client and the same secret to the server. No studio secret required.

---

## 6. Game-mode resolution  **[PARTIAL]**

`gameMode` is a **numeric id** (`47` here, on Gobi). The captured `GET /sharedData/getGameModesParameters` holds the parameter set the client uses, but a clean `id → name` table was not directly extractable from it, and `47` did not map to one of the C++ mode classes by number. **[GAP]** — M2 must establish the `numeric gameMode ↔ AWW3*GameMode class ↔ ruleset` mapping (candidates from the binary: `WW3TeamDeathmatch`, `WW3Domination`, `WW3Recon`, `WW3GunGame`, `WW3HVT`, `WW3Breakthrough`/`Break`, `WW3Transmission`, `WW3Vehicles`, `WW3KIA`, `WW3Fubar`). This mapping is what `UWW3GameModeConfigReader` builds when the Hub initializes.

---

## 7. The join handshake (client → match server)  **[INFERRED + GAP]**

The client opens a UE4 `UNetConnection` to `address:gamePort` (UDP). From the match pcaps: the connection begins with the `StatelessConnect` handshake (bit-packed; the repeating cookie is visible), followed by the control channel `NMT_Hello`/`NMT_Login` in which UE4 sends the **login URL with options**. The lobbyToken is presented here (standard UE4 pattern: `?option=value` in the login URL, or an `NMT_Login` payload). **[GAP]** — the exact option name/encoding is bit-packed and requires the UE4 bunch/control-channel parser to extract byte-exactly. **[INFERRED]** — the server reads the presented lobbyToken, validates HS256, and admits the player; the `matchId` in the token must equal the server's own `matchId`.

Resolving this precisely is a small, well-scoped netcode task (parse the control channel of the first ~10 client packets in `Match_tacops_DMZ_still.pcap`).

---

## 8. Known vs. gap — what M2/M3 must resolve

| Piece | Status | Source |
|---|---|---|
| Matchmaking request/response shape | **OBSERVED** | hub.log |
| Lobby object, teams, squads, players | **OBSERVED** | hub.log |
| Lobby lifecycle events | **OBSERVED** | hub.log |
| Server handoff (address/ports/matchId) | **OBSERVED** | hub.log |
| lobbyToken (admission credential, HS256) | **OBSERVED, decoded, forgeable** | hub.log |
| Numeric gameMode → class/ruleset | **GAP** | needs getGameModesParameters + binary RE |
| Exact join-URL option carrying the token | **GAP** | needs netcode parse of match pcap |
| How the **server** is told to host (server↔backend) | **GAP** | never captured — reconstruct from binary / infer from token |
| The shared HS256 secret | **N/A** | we mint our own; issuer == verifier == us |

---

## 9. Reconstruction plan (feeds M2–M4)

**M2 — backend match layer.** Extend the hub mock to:
1. Answer `findLobbyForParty` / `findCustomLobbyForParty` → return a lobby.
2. Emit the lobby lifecycle (`LobbyChange` → `LobbyReadyStateChange` → `LobbyMatchStarted`), assigning teams. Bots or a second client fill the roster.
3. In `LobbyReadyStateChange`, return a `server` handoff pointing at **our local match server** (`127.0.0.1:<gamePort>`) and a **freshly minted lobbyToken** (HS256, our secret, correct `playerId`/`team`/`matchId`).
4. Resolve the `gameMode` mapping and serve the matching ruleset via `getGameModesParameters` / the config the server reads.

**M3 — the match server.** A WW3 instance that hosts `map?game=<class>` for `matchId`, connected to our backend so `UWW3GameModeConfigReader` builds the rules, validates presented lobbyTokens against our secret, and admits players to teams. (This is where the earlier command-line-host crashes get resolved: the rules manager and identity that were null are now supplied through the flow.)

**M4 — clients join.** A client matchmakes through the menu → our hub returns the local handoff + token → the client connects to our match server → **private-server multiplayer.**

---

*M1 status: the client-side contract is fully reconstructed. Two well-scoped gaps remain (the gameMode→ruleset table and the exact join-URL option), plus the server-orchestration reconstruction — all addressable in M2/M3 without any further live captures.*
