# Spiral Warrior / 螺旋勇士 — Offline Preservation Toolkit

**Status:** Paused, seeking collaborators &nbsp;|&nbsp; **Version:** v0.3 &nbsp;|&nbsp; **License:** MIT

A local preservation lab for **Spiral Warrior / 螺旋勇士**, a Cocos Creator
mobile game whose official services are no longer reachable. The project
reimplements enough backend and game protocol for a copy of the client you
already own to boot, authenticate, reach the lobby, and **play the prologue
Adventure chapter through to its boss** — entirely against local services, with
no production endpoint contacted after launch.

**This repository contains no game client, no game assets, no decrypted source
and no keys.** See [NOTICE](NOTICE).

---

## Why this is public

The original author has stopped work here. Everything that is known is written
down — including the parts that are wrong, and how they were caught — so that
someone else can carry it further. If this is the kind of thing you enjoy,
[CONTRIBUTING.md](CONTRIBUTING.md) is a map of where the seams are.

---

## Project progress

| Phase | Status |
| --- | --- |
| Windows host doctor, SDK/AVD bootstrap, launcher | ✅ Complete |
| Offline edge proxy — deny-by-default, no fabricated success | ✅ Complete |
| Runtime artifact derived reproducibly from your own copy | ✅ Verified |
| Area discovery (`/area/listV2`) accepted by the client | ✅ Verified |
| Logic token (`/auth/es`) and WebSocket login | ✅ Verified |
| Lobby renders with a local account | ✅ Verified |
| Adventure: enter map, node graph, battles, rewards | ✅ Verified |
| Postbattle chip claim, restart-proven save | ✅ Verified |
| Every prologue node kind: story, select, reward, boss | ✅ Verified |
| **Prologue chapter cleared 8/8, boss defeated** | ✅ Verified |
| Chapter progression persisted (`RogueLikeRecord`) | 🔶 Implemented, partly live-verified |
| Exploration % and first-clear chest (`ChapterRecords`) | ⬜ Not started |
| Tournament mode (锦标赛) | ⬜ Not started |
| Chapters beyond the prologue | ⬜ Not started |
| International build (`com.oversea.spinarena`) | ⬜ Reference only |

**365 tests.** A clean checkout — with none of the external inputs present —
runs 350 of them; the other 15 are gated behind a `preservation_artifact`
marker because they need a locally supplied client.

---

## Key findings

The interesting part of this project is not the server, it is what the client
turned out to actually do. A few of the contracts that were modelled wrongly
first, each of which silently refused a real request:

- **`RogueLikeMap.Version` is a timestamp**, not a counter — seconds since
  `2018-01-01T00:00:00+08:00`. Sending `1` made the client abandon every run
  about two seconds after the map loaded.

- **A node's event type is never sent.** `setEvent` reads it from the shipped
  `data/RogueLike` table, so the gateway needs the same mapping to tell a
  battle from a shop from the boss. Keying on event *ids* instead stranded a
  run after the first battle.

- **A declared export list is not echoed back.** Where an event has a fixed
  `ExportIdArray`, the client fills it in locally and sends an *empty* list;
  the server is expected to look it up. Demanding the ids back refused every
  real request.

- **The rolled export count is per event, not per kind.** A battle rolls
  three; the boss rolls four. One hardcoded count refused the boss outright.

- **A repair station heals before it sends.** `setChijiItem` calls
  `dealHp(ExportNum / 100, index, true)`, which halves the ratio for a
  defeated top and rounds up, so the confirm carries the *healed* value. The
  server must recompute and compare, not apply its own.

- **`BattleOverSelect` (net 183 op 3) is dead code** in build 1.0.348. The
  real postbattle claim rides on the trigger, net 184.

- **A won run's only completion signal is `TriggerAllNode`.** `doEndMap` — the
  client's own end-of-map path — runs on a loss only.

`docs/BLOCKERS.md` carries the full account with the evidence for each, and
`docs/REVERSE_ENGINEERING_NOTES.md` the static findings.

---

## How to contribute

Priority areas, in rough order of value:

1. **Tournament mode (锦标赛)** — the other main mode; partial scaffolding exists.
2. **Chapters beyond the prologue** — the extraction tooling already takes `--chapter`.
3. **Exploration and first-clear rewards** — needs `ChapterRecords` modelled.
4. **The paid revive** — `RL_MiscOpr_Diamond`, refused at the parser today.
5. **The unanswered net IDs** — 144, 146, 159, 217, 288.
6. **The international build** — its Cocos resource path still needs work.

Full detail, plus the house rules on evidence and testing, in
[CONTRIBUTING.md](CONTRIBUTING.md).

---

## Scope

**Included**

- Local gateway: discovery, auth, WebSocket game protocol, profile persistence
- Offline edge proxy that intercepts retired hosts and denies everything else
- Windows launcher, host doctor, and Android SDK/AVD bootstrap
- Analysis and extraction tooling (Cocos `.jsc`, data tables, endpoint scans)
- Protocol documentation, findings, and an evidence index

**Explicitly not included**

- Game client, APK/XAPK, assets, installers, or any patched build
- Decrypted, decompiled or otherwise recovered proprietary source
- Cryptographic keys, signing keystores, or private keys
- Packet captures, credentials, session tokens, or other players' data
- Screenshots of the client

---

## Repository structure

```
server/          FastAPI gateway: discovery, /auth/es, /ws, profile store
  app/protocol/    Frame codec, protobuf builders, recovered data tables
  app/routes/      HTTP and WebSocket endpoints
  tests/           365 tests; 15 gated behind preservation_artifact
tools/           Analysis and derivation: Cocos .jsc, table extraction,
                 endpoint scanning, the offline edge proxy, SDK bootstrap
dist/            launcher.ps1 — the single supported entry point
docs/            Status, blockers, protocol notes, API draft, plans
patches/         Host redirection helpers
research/        Evidence index (the captures stay on the host)
```

---

## Requirements

The accepted operator platform is **64-bit Windows 11** under a **64-bit
Windows PowerShell 5.1 Desktop** process. `dist\launcher.ps1` is the only
supported entry point; there is no supported Linux, macOS, WSL or PowerShell 7
launcher.

You also need:

- 64-bit CPython `>=3.12,<3.13`
- Java 17 (Eclipse Adoptium), for deriving the local runtime artifact
- Firmware virtualization enabled, with a working `emulator -accel-check`
- **Your own copy of the client**, and its script-bundle key in
  `SPIRAL_BUNDLE_KEY`. Neither is provided here. Expected hashes are listed in
  `CHECKSUMS.sha256` so you can verify what you supply.

## Running it

Check the host first — `-Doctor` is read-only and mutates nothing:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File dist\launcher.ps1 -Edition cn -Doctor
```

Then:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File dist\launcher.ps1 -Edition cn -Capture
```

That starts the local gateway and proxy edge, boots the AVD, installs the
locally derived artifact, launches the game and records logcat. In the client:
tick the consent box, pick 海之国1服, and press 进入游戏.

---

## How it fits together

```text
emulator ──HTTP proxy──> edge :8888     intercepts retired hosts, denies the rest
         └──────────────> gateway 10.0.2.2:23101
                              /area/listV2   exact areaRet protobuf
                              /auth/es       JWT-shaped logic token
                              /ws            big-endian framed game protocol
```

Saves live beneath `SPIRAL_SAVE_DIR` when set, and are written atomically.

---

## Legal

This is interoperability and preservation research on software that can no
longer be played as sold.

**Legitimate use:** running a private, offline copy of a game you lawfully
obtained; studying the protocol; contributing fixes back here.

**Not permitted, and not supported here:** redistributing the client or its
assets, circumventing any purchase or entitlement check, or operating a public
service using proprietary content.

The MIT licence in [LICENSE](LICENSE) covers **this project's own code and
documentation only** — not the game, its assets, or its trademarks. Attribution
and the full content boundary are in [NOTICE](NOTICE).

If you are a rights holder and believe anything here exceeds interoperability
and fair use, please open an issue — we will act on well-founded requests
promptly.
