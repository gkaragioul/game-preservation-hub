# WW3 Backend Architecture & Endpoint Map
*Reverse-engineered from client binary, working-day crash logs (2026-06-12), and packet captures.*

## The connection chain (login → menu)
The client boots and contacts backends **in this order**. Each must succeed to reach the menu.

| # | Layer | Host (real) | Port | Protocol | Purpose |
|---|-------|-------------|------|----------|---------|
| 1 | Identity/launch | `id-dev.fx.gl` | 443 | HTTPS | fxlauncher / account bootstrap |
| 2 | EOS anti-cheat | `epicgames.dev`, `ww3.anticheat.my.games` | 443 | HTTPS | Epic Online Services + EAC handshake |
| 3 | Meta server | `meta.prod.ww3.fxtools.gl` | 443 | HTTPS/REST | friends, invitations, profile bootstrap |
| 4 | Time/config | `api.public.dev.ww3.fxtools.gl` | 443 | HTTPS/REST | DateTimeKeeper + remote config |
| 5 | **Hub (WebSocket)** | `ws://213.183.62.234` | **8705** | **WebSocket (RPC)** | **THE lobby/menu brain — all live data** |
| 6 | XMPP presence | `xmpp.prod.ww3.fxtools.gl` | 5222 | XMPP | online status, friends presence, keepalive |
| 7 | Match server | (per-match IP) | **7868 UDP** | UDP | actual gameplay (positions, shots) |

## KEY FINDINGS

### ✅ NO cert pinning — and no cert verification AT ALL
Client log: `bVerifyPeer = false — Libcurl will NOT verify peer certificate`.
The self-signed cert approach works with **zero binary patching**. This is the easy path.

### ✅ The Hub WebSocket is the real target (not the HTTP stubs)
The menu is driven by a **WebSocket JSON-RPC** protocol on port 8705, NOT plain REST.
The current mocks (api_server/https_server) answer REST but **there is no WebSocket mock yet** — that's the missing piece.

**RPC message shape:**
```json
// Request:  {"type":"RpcRequest","id":<int>,"context":"<ctx>","method":"<m>","args":[...]}
// Response: {"type":"RpcResponse","id":<int>,"result":<value>}
```

**RPC contexts/methods observed (must be mocked):**
| context | method | args | real response shape |
|---------|--------|------|---------------------|
| `friends` | `changeStatus` | `[statusInt]` | `true` |
| `friends` | *(getAll via HTTP)* | — | array of friends |
| `onlineParameters` | `getParameters` | `[]` | `{"type":"OnlineParameters","pingPongInterval":4000,"pingPongTimeout":10000,"logsConfig":[...]}` |
| `notifications` | `getNotifications` | `[{"quantity":10,"targetId":<id>}]` | `{"notifications":{"news":[...]}}` |
| `debug` | `log` | `[{logs:[...]}]` | ack |
| *(lobby)* | — | — | `{"lobby":{"id":...,"playersLimit":40,"gameMode":2,"map":"WW3_Tokio_P","players":[...]}}` |

### ✅ Meta REST endpoints (HTTPS on meta.prod)
- `GET https://meta.prod.ww3.fxtools.gl:443/friends/getAll`
- `GET https://meta.prod.ww3.fxtools.gl:443/friends/getReceivedInvitations`

### ✅ Account identity
- Player id: `100001`, XMPP JID: `prod-100001@xmpp.prod.ww3.fxtools.gl`
- XMPP resource carries session token: `V2:WW3:::<32-hex>`
- XMPP auth mechanism: `DIGEST-MD5` (stub auto-accepts)

### Engine facts
- Unreal Engine **4.21**, libcurl 7.82 / OpenSSL 1.1.1
- Private-server launch flag: `-Continent=SECRETMS` (bypasses EAC wrapper `start_protected_game.exe`)
- Connectivity check: `http://api.ipify.org` (returns your public IP)

## CURRENT BLOCKER (where everyone is stuck)
Client reaches **"AUTHORIZATION IN PROGRESS"** and stalls. Reason:
1. HTTP/HTTPS/XMPP mocks answer ✅
2. But the client then needs the **Hub WebSocket (ws://…:8705)** to connect and answer `onlineParameters.getParameters` + friends/notifications RPC — **no mock exists for this yet**.
3. Without the Hub, `SetIsConnectedToMasterServer` never fully completes → stuck on auth.

## NEXT STEP
Build a **WebSocket mock** (port 8705) that:
- accepts the `ws://.../client/<JWT>` upgrade
- answers `onlineParameters.getParameters` with the real OnlineParameters shape (captured above)
- answers `friends.changeStatus`→`true`, `notifications.getNotifications`→empty list
- replies to every `RpcRequest` with a matching `RpcResponse` id
Plus point `meta.prod.ww3.fxtools.gl` + `api.public.dev.ww3.fxtools.gl` at the HTTPS mock (add to hosts).
