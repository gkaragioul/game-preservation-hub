# World War 3 — Offline Preservation Toolkit

**Status: paused — looking for collaborators.** &nbsp;·&nbsp; **Version:** `v0.2` &nbsp;·&nbsp; **Licence:** MIT (see `LICENSE`)

Research and tooling to keep a **legally purchased** copy of *World War 3* (Steam app **674020**, Unreal Engine 4.21) bootable for **private, offline use** after the official online services shut down on **3 August 2026**.

The game was multiplayer-only. When the servers went away, every purchased copy stopped working. This project reimplements enough of the backend — and enough of the UE4 match protocol — for an **unmodified retail client** to boot, browse its menus, matchmake, load a real map, and reach the in-match deploy screen entirely against local servers.

> **Not affiliated** with The 4 Winds Entertainment, My.Games, Wishlist Games, Epic Games, or Valve.
> This repository contains **no game client, no game assets, and no cracked binaries.** You need your own legitimate copy.

---

## Where this got to

**The menu tier is finished.** A retail client boots fully offline: login, profile, loadouts, challenges, shop, matchmaking. This part is stable and no longer changes.

**The match tier is most of the way through reverse-engineering.** The client connects to a from-scratch UE4.21 match server, loads *Ruins of Gobi*, renders it, shows the live match HUD, acknowledges pawn possession, and reaches the real deploy screen with a working tactical map and equipment-loadout screen. As of the last session it also **selects a spawn point** — the client emits `Server_SpectatorAttachToCapturePoint`, which was the long-standing blocker.

### The honest caveat

**What exists today is a replay harness, not a game server.**

The match server largely sends *recorded bytes* from one packet capture, SHA-pinned and replayed in order. That was the right way to decode the protocol and it is why the findings below are verifiable — but it does not generalise:

- it only works on **one map**, because the replay stream is from that map;
- it supports **one client**, because the capture had one player's point of view;
- **nothing is simulated** — no movement authority, no hit detection, no objective scoring, no match lifecycle, no bots, no vehicles.

The frozen `06:02` on the match HUD is exactly this: the round timer is a replayed constant that never ticks.

So: near the end of the **protocol reverse-engineering** phase, near the start of the **server implementation** phase. The decoded protocol — and the tooling and oracles around it — is the real asset here.

| Phase | State |
|---|---|
| Backend mocks / offline menu | ✅ Complete |
| M1 — UE4 StatelessConnect handshake | ✅ Verified against the retail client |
| M2 — NMT control channel (login → welcome → join) | ✅ Verified, with a regression test |
| M3 — replication read-side (NetGUID, actors, RepLayout) | ✅ Decoded and validated |
| M4 — in-match: map load, possession, deploy screen | ✅ Reached |
| Spawn selection (`h305`) | ✅ Client now emits it |
| Deploy → first-person spawn | 🔶 **Current blocker** |
| Replace replay with simulated state | ⬜ Not started — the large one |
| Two or more players, combat, objectives | ⬜ Not started |

---

## Why it is paused, and where help is wanted

This was a solo effort and has reached the point where the remaining work is a **different kind of project**: not "decode the wire format" but "write a game server". Progress stalled at the last step of the deploy handshake, and rather than let the findings rot undocumented, everything is written down here.

**Contributions very welcome.** Good places to start, roughly by size:

### 1. Finish the deploy handshake (small, well-specified)

The client sends `h305 Server_SpectatorAttachToCapturePoint` per tick. The server must answer each one **1:1** with `ClientSetViewTarget` + `Client_UpdateSpectatePoint`, echoing back **the capture point the client named**. Right now the server replays a captured `h273` that names the *wrong* capture point, so the client never proceeds to `h287`.

The fix is to parse the NetGUID out of the incoming `h305` and rebuild `h273` around it. The wire layout is known — its 20-bit parameter is `send=1`, packed NetGUID, then `CapturePointType` (2 bits) + `FirstItem` (1 bit) + `SpectateActor` (packed). Helpers for building this already exist in `match_server/possess_rpc.py`.

**Success looks like:** the client sends `h287`, the server answers with the captured transition bundle, and the player spawns into first person. Then measure pawn displacement after one bounded `W` input to confirm movement works end to end.

### 2. Replace replay with generated state (the real work)

The keystone task is **NetGUID allocation plus spawning an actor on demand** — owning the NetGUID space instead of inheriting the capture's numbering, and building `SerializeNewActor` with a chosen class, location and rotation. Everything downstream needs it: respawning, a second player, bots, vehicles, any other map.

After that: a GameState that actually ticks, then movement authority (`ServerMove` → update → replicate back), then a second client — which is the real forcing function, because it exposes every remaining place the server is replaying rather than simulating.

### 3. Other modes are cheaper than they look

Team Deathmatch has a **much smaller** deploy surface than Domination: `h281 → h290 RequestRespawnAtRandomTDMPoint → h279 → h64 + h280`, with no spectator phase and no capture-point replication at all. If you want a spawned, moving player quickly, that path is worth considering.

---

## What was decoded (the useful part)

These are the findings most likely to help anyone doing UE4.21 protocol work, on this game or another.

**Handshake and framing**
- UE4.21 `StatelessConnect`: bit 0 `bHandshakePacket`, bit 1 flag, bits 2–33 a float32 timestamp (`-1.0` is the ack sentinel), bits 34–193 cookie, bit 194 terminator — 25 bytes.
- Channel sequence numbers derive from the cookie, they do **not** start at zero.
- An ack entry is **24 bits**: `IsAck(1) + AckPacketId(14) + bHasServerFrameTime(1)[+8] + RemoteInKBytesPerSecond(8)`.
- Bunch header: 12-bit `ChSequence` + 3-bit `ChType` (1 = Control, 2 = Actor).
- The real server packs roughly **11.5 bunches per packet**. Sending one bunch per packet floods the client and breaks replay.

**Replication**
- A RepLayout property stream begins with a 1-bit `bDoChecksum` flag, then packed handle/value pairs in ascending order, terminated by a packed `0`. *Forget that bit and every handle decodes as exactly **2×** its true value with one bit left over.*
- Content block: `[bHasRepLayout][bIsActor][packed NumPayloadBits][payload]`; the subobject variant adds a packed NetGUID and a `bStablyNamed` bit.
- Static level actors frequently open **no channel of their own** — they enter the client's PackageMap only as NetGUID→path exports riding on *other* actors' open bunches. This was the cause of the longest-standing bug in the project.

**The deploy handshake** (confirmed on four independent captures)

```
C->S  h310 StartSpectator + h305 AttachToCapturePoint(<capture point actor>)   per tick
S->C  h50 ClientSetViewTarget + h273 Client_UpdateSpectatePoint(same point)    strictly 1:1
C->S  h287 RequestRespawnAtCapturePoint(<that point's "First Spawn Zone">)
S->C  h231 Client_OnCapturePointRespawnRequestStatusChanged
C->S  h279 OnClientPreloadWeaponsFinished
S->C  one packet: StopSpectatorBeforeDeploy, StopSpectator, SetViewTarget,
                  ClientRestart, SetViewTarget, SetCameraMode, SetRotation
C->S  h64 AcknowledgePossession + h280 OnMapClosed
```

Note `h305` and `h287` take **different objects**: the capture-point *actor*, then that actor's `"First Spawn Zone"` **child**. Also, `h281 Server_OnMapOpened` is the *tactical map*, not the deploy screen — `h310 StartSpectator` is the reliable deploy-screen marker.

**Deriving RPC handles.** `match_server/derive_net_handles.py` reconstructs the ClassNetCache ordering from an SDK dump. For this build, wire handle = leaf listing index + 130, verified against six independent on-the-wire anchors.

---

## Repository layout

```
mockserver/     Local backend: REST/meta (443, 80), hub + matchmaking (8700), XMPP (5222)
match_server/   The reimplemented UE4.21 match server (UDP 7871) and its analysis tools
match_analysis/ pcap reading and protocol decode helpers
windows/        Orchestration: bring the stack up, launch the client, tear everything down
docs/           Protocol findings (M1/M2/M3), field manuals, capture guides
weapons/        Ballistics charts (research notes)
```

## Running it

Requires Windows, an **elevated** PowerShell, Python 3.12, and your own installed copy of the game.

```powershell
# bring up mocks + hosts redirects + local CA, start the match server, launch the game
powershell -ExecutionPolicy Bypass -File windows\ww3_matchtest.ps1

# ALWAYS tear down afterwards
powershell -ExecutionPolicy Bypass -File windows\ww3_mock.ps1 down
```

> ⚠️ **Always tear down.** The stack installs a local test CA and hosts redirects so the client resolves the studio domains to `127.0.0.1`. If you leave them in place, **other games using the same platform services will fail to connect.** This has already caused one real incident during development.

The match server is driven almost entirely by `WW3_*` environment variables, documented with their defaults at the top of `match_server/server.py`. Each experiment pins its own environment so runs are reproducible.

---

## What is deliberately **not** in this repository

- **The game.** No client, no PAKs, no installers, no assets. Bring your own legitimate copy.
- **Packet captures**, and anything derived byte-for-byte from them — including the replay streams the match server needs. They contain session tokens, IP addresses and **other players' match traffic**, so publishing them would expose people who never consented. See `captures/README.md`.
- **Private keys.** The local mock CA and certificates are generated on your machine.

This means the **menu tier runs from a clean clone, but the match server does not** — it needs capture-derived replay data that is not published. If you are working on the match tier, open an issue and we can discuss sharing that data privately.

---

## Legal

| Intended use | Explicitly not this project |
|---|---|
| You own a legitimate Steam licence | Redistributing game files, PAKs or installers |
| Private, offline play on your own machines | A public "free download" of the game |
| Interoperability and preservation research on your own copy | Circumventing purchase, ownership checks, or anti-cheat for online advantage |
| Local mock backends that you run yourself | Hosting a public service using someone else's content |

This is an independent preservation and interoperability effort, undertaken on a copy the author bought, after the publisher discontinued the online service that the purchase depended on. It reimplements server behaviour observed on the author's own network connection; it does not decompile, redistribute, or modify the game.

See `NOTICE` for trademark attributions and `LICENSE` for the licence covering the code in this repository. The MIT licence applies to **this project's own code and documentation only** — not to World War 3, its assets, or any trademark referenced here.

---

## Contributing

Issues and pull requests are welcome. The most valuable contributions right now are the ones listed under **"Why it is paused"** above.

If you are picking this up cold, a suggested order:

1. Read `docs/M1_Match_Orchestration_Spec.md`, then the M2 and M3 findings.
2. Bring the menu tier up and watch a client boot offline — it works from a clean clone.
3. Read `match_server/README.md` for the match-tier architecture and flag reference.

A note on method, because it mattered more than anything else here: **measure, don't argue.** Over the final stretch, six confident hypotheses were falsified by the next measurement, including one where the "fix" made things measurably worse. The ones that survived did so because there was an oracle — a memory read, a byte-exact decode, a positive control on a known-good capture. State the oracle before running the experiment, change one variable at a time, and believe the result over the story.
