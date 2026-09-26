# World War 3 — Offline Preservation Research

**Status: paused.** &nbsp;·&nbsp; **Source: not published** (this page is a public summary)

Research into keeping a **legally purchased** copy of *World War 3* (Steam app **674020**, Unreal Engine 4.21) bootable for **private, offline use** after the official online services shut down on **3 August 2026**.

The game was multiplayer-only. When the servers went away, every purchased copy stopped working. The project reimplemented enough of the backend, and enough of the UE4 match protocol, for an **unmodified retail client** to boot, browse its menus, matchmake, load a real map and reach the in-match deploy screen entirely against local servers.

> **Not affiliated** with The 4 Winds Entertainment, My.Games, Wishlist Games, Epic Games or Valve. World War 3 and all related names and artwork belong to their respective rights holders.
> This page contains **no game client, no game assets, no code, no tools and no captured data**.

![World War 3 gameplay](assets/project-cover.jpg)

*Public gameplay image used only to identify the game. Artwork © its respective rights holders. [Source: World War 3 on Steam](https://store.steampowered.com/app/674020/World_War_3/).*

---

## Why the source is not public

The working code depends on material that must not be published: data recorded from the author's own connection to the live service, local certificates, and tooling that imitates the retired online platform. This page shares the findings only, so that others working on Unreal Engine 4 preservation can use them.

## Where this got to

**Research update (26 September 2026):** [Weapon customization, blueprints, and save-state findings](research-update-2026-09.md). These notes distinguish a reported client test from backend-only checks; they do not change the match-tier status below.

**The menu tier is finished.** A retail client boots fully offline: login, profile, loadouts, challenges, shop, matchmaking.

**The match tier is most of the way through reverse-engineering.** The client connects to a from-scratch UE4.21 match server, loads *Ruins of Gobi*, renders it, shows the live match HUD, acknowledges pawn possession, and reaches the real deploy screen with a working tactical map and equipment-loadout screen. It also **selects a spawn point**: the client emits `Server_SpectatorAttachToCapturePoint`, which was the long-standing blocker.

### The honest caveat

**What exists is a replay harness, not a game server.** The match server largely replays recorded bytes in order. That was the right way to decode the protocol, but it does not generalise:

- it only works on **one map**;
- it supports **one client**;
- **nothing is simulated**: no movement authority, no hit detection, no objective scoring, no match lifecycle, no bots, no vehicles.

| Phase | State |
|---|---|
| Backend mocks / offline menu | ✅ Complete |
| M1 — UE4 StatelessConnect handshake | ✅ Verified against the retail client |
| M2 — NMT control channel (login → welcome → join) | ✅ Verified |
| M3 — replication read-side (NetGUID, actors, RepLayout) | ✅ Decoded and validated |
| M4 — in-match: map load, possession, deploy screen | ✅ Reached |
| Spawn selection (`h305`) | ✅ Client now emits it |
| Deploy → first-person spawn | 🔶 Blocked here |
| Replace replay with simulated state | ⬜ Not started |
| Two or more players, combat, objectives | ⬜ Not started |

---

## What was decoded

These are the findings most likely to help anyone doing UE4.21 protocol work, on this game or another.

**Handshake and framing**
- UE4.21 `StatelessConnect`: bit 0 `bHandshakePacket`, bit 1 flag, bits 2–33 a float32 timestamp (`-1.0` is the ack sentinel), bits 34–193 cookie, bit 194 terminator — 25 bytes.
- Channel sequence numbers derive from the cookie; they do **not** start at zero.
- An ack entry is **24 bits**: `IsAck(1) + AckPacketId(14) + bHasServerFrameTime(1)[+8] + RemoteInKBytesPerSecond(8)`.
- Bunch header: 12-bit `ChSequence` + 3-bit `ChType` (1 = Control, 2 = Actor).
- The real server packs roughly **11.5 bunches per packet**. Sending one bunch per packet floods the client and breaks replay.

**Replication**
- A RepLayout property stream begins with a 1-bit `bDoChecksum` flag, then packed handle/value pairs in ascending order, terminated by a packed `0`. *Forget that bit and every handle decodes as exactly **2×** its true value with one bit left over.*
- Content block: `[bHasRepLayout][bIsActor][packed NumPayloadBits][payload]`; the subobject variant adds a packed NetGUID and a `bStablyNamed` bit.
- Static level actors frequently open **no channel of their own**. They enter the client's PackageMap only as NetGUID→path exports riding on *other* actors' open bunches. This was the cause of the longest-standing bug in the project.

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

`h305` and `h287` take **different objects**: the capture-point *actor*, then that actor's `"First Spawn Zone"` **child**. `h281 Server_OnMapOpened` is the *tactical map*, not the deploy screen; `h310 StartSpectator` is the reliable deploy-screen marker.

**Other modes are cheaper than they look.** Team Deathmatch has a much smaller deploy surface than Domination: `h281 → h290 RequestRespawnAtRandomTDMPoint → h279 → h64 + h280`, with no spectator phase and no capture-point replication.

**Deriving RPC handles.** The ClassNetCache ordering can be reconstructed from an SDK dump. For this build, wire handle = leaf listing index + 130, verified against six independent on-the-wire anchors.

**Ballistics.** The damage-over-range charts made during the research are in [`weapons/`](weapons/).

---

## Legal

This was an independent preservation and interoperability effort on a copy the author bought, after the publisher discontinued the online service that the purchase depended on. It does not redistribute or modify the game, and it is not a way to play the game online or to gain an advantage in any online service.

---

## A note on method

**Measure, don't argue.** Over the final stretch, six confident hypotheses were falsified by the next measurement, including one where the "fix" made things measurably worse. The ones that survived did so because there was an oracle: a memory read, a byte-exact decode, a positive control on a known-good capture. State the oracle before running the experiment, change one variable at a time, and believe the result over the story.

If you are working on UE4 preservation and want to compare notes, open an issue in this hub.
