# OPERATION PRESERVATION

## WORLD WAR 3 — STAGE 1

**Mapping and replacing the service dependencies required to preserve access to a multiplayer-only game's main menu before server shutdown.**

**Status:** STAGE 1 — PROOF OF LIFE ACHIEVED

In this document, "proof of life" means one specific, narrowly defined result: the game reaches a stable, fully populated main menu inside the documented local environment, with a locally supplied profile state loaded. It does **not** mean the game is fully preserved, and it does **not** imply playable matches. Stage 1 stops at the menu.

**Compiled by:** Repository Owner, RecompileLabs
**Date:** 23 July 2026

> **Disclaimer:** This is an independent technical preservation investigation. It is not affiliated with, endorsed by or sponsored by the game's publisher, developer, Epic Games or any other rights holder or service provider.

*[INSERT COVER TREATMENT — sanitized title plate]*
Caption: Cover plate for the public case study. What it proves: identifies scope, status and authorship of the Stage 1 investigation. Stage 1 / 23 July 2026. Evidence type: SANITIZED DIAGRAM.

---

## 1. Executive Summary

World War 3 is a multiplayer-only title built on Unreal Engine 4.21. Its official servers are scheduled to shut down on 3 August 2026. Like most online-dependent games, the installed client cannot normally complete startup on its own: a chain of remote services handles identity, profile and progression, the menu/hub, and presence before the player ever reaches an interactive menu. When those services go offline, the locally installed software can become inaccessible even though the game files remain on disk.

Stage 1 of Operation Preservation set out to answer one question: **can the startup service chain that gates the main menu be understood, reproduced and stabilised in a controlled local environment?**

The method was evidence-first. A passive recorder observed legitimate client-to-server sessions while the official infrastructure was still available. Those sessions were timestamped and organised, a live dashboard displayed the client-to-server activity, and sensitive personal material was redacted. From that record, the team mapped the order of services, the categories of messages exchanged, and the responses the client expected. Local stand-in services were then created in an isolated environment, the client was routed to them, and a synthetic local profile was supplied. The result is a documented local proof-of-life environment in which the game reaches a stable main menu with a locally supplied profile state.

Stage 1 does **not** deliver playable matches. The match server — the live battlefield simulation — is a separate and substantially larger problem, addressed as Stage 2, which remains an active research question.

### RESULT PANEL

| Result | Status |
| --- | --- |
| Main menu reached | Yes |
| Profile state loaded | Yes (synthetic, local) |
| Menu services stable | Yes (in current tests) |
| Publisher backend required during the demonstrated local boot | No |
| Playable match server | Not yet |
| Stage 2 (match server) | Remains an active research question |

This is a documented Stage 1 proof of life. It is **not** a "fully preserved game."

---

## 2. The Preservation Problem

A single-player game from twenty years ago will usually still run: the executable and its assets are self-contained. A multiplayer-only game is different. The executable remains, but its core functionality depends on remote services that the player does not own and cannot keep running.

In this case the dependency is deep and early. Login, profile retrieval, progression, inventory, the menu/hub service and presence are all server-controlled and all sit on the path between launching the game and reaching an interactive menu. If those services stop responding, startup does not complete.

The consequence is specific to online-dependent titles: shutdown can make purchased, locally installed software inaccessible even when all the local assets are still present on the drive. The game is not deleted — it simply can no longer get past its own front door.

> **Plain-language sidebar:** Think of the game as a building where the front door, the reception desk and the lift all require a phone call to a remote office to operate. The building still stands after that office closes, but nobody can get inside. Stage 1 is about understanding those phone calls well enough to keep the lobby reachable.

This case study is limited to World War 3 and the specific build and environment tested. It makes no broad legal claims and no general claims about the industry.

---

## 3. The Service Chain

Before anything can be reproduced, the dependency chain has to be mapped: which services the client contacts, in what order, and what each one contributes to reaching the menu.

*[INSERT SERVICE-CHAIN DIAGRAM]*
Caption: Sanitized architecture of the startup service chain, from client to match layer, with the Stage 1 / Stage 2 boundary marked. What it proves: identifies the backend dependencies that gate the main menu versus those that belong to gameplay. Stage 1 / 23 July 2026. Evidence type: SANITIZED DIAGRAM.

The chain, at a sanitized level, is:

**GAME CLIENT → IDENTITY → PROFILE / META → HUB / MENU → PRESENCE → MATCH LAYER**

- **STAGE 1 scope:** Identity, Profile/Meta, Hub/Menu and Presence — everything required to reach and hold the main menu.
- **STAGE 2 scope:** the Match layer — the live battlefield simulation. Out of scope for Stage 1.

Each layer is described below with a technical view and a plain-language view.

### Identity

**Technical view:** The identity layer establishes who the client is and issues the session credentials that later services expect the client to carry. It also includes a third-party identity dependency associated with the platform's online-services layer.

**Plain-language view:** This is the reception desk. It checks you in and hands you a pass that the rest of the building recognises. Nothing else works until this step succeeds.

### Profile / Meta

**Technical view:** The profile/meta layer returns the player's account state — level, inventory, unlocks, loadouts and related progression and season data — that the menu and customisation interfaces need in order to populate.

**Plain-language view:** This is the filing cabinet. It holds your record — what you have, what you have unlocked, how far you have progressed — and the menu reads from it to build the screens you see.

### Hub / Menu

**Technical view:** The hub/menu layer is the live service that drives the interactive menu and menu-side session state. It is a persistent connection rather than a one-off request.

**Plain-language view:** This is the switchboard that keeps the menu "live" — the part that stays on the line while you are browsing menus, rather than answering once and hanging up.

### Presence

**Technical view:** The presence layer manages online status, social state and related background connectivity that the menu maintains after it loads.

**Plain-language view:** This is the "who's online" system. It runs quietly in the background once you reach the menu, and if it misbehaves the menu shows connection warnings.

### Match Layer (Stage 2)

**Technical view:** The match layer is a live, stateful simulation of the battlefield. It is architecturally distinct from the startup services and is not addressed in Stage 1.

**Plain-language view:** This is the actual game — the battlefield where matches happen. Stage 1 never enters it. That is a separate project.

---

## 4. Phase 1 — Observation ("Capturing the Live Service Flow")

Stage 1 began while the official infrastructure was still available. The team used a passive recorder to observe legitimate client-to-server sessions: the recorder captured the messages exchanged during normal, authorised use of the game, timestamped and organised them, and presented the activity on a live dashboard. Sensitive personal material was redacted during capture.

This observation phase produced the raw evidence for everything that followed. It helped identify the order in which services were contacted, the categories of messages exchanged, and the responses the client expected before it would proceed to the next step.

Security-sensitive implementation details are intentionally omitted from the public version. This section describes what was observed, not how to intercept traffic, and contains no tokens, keys, credentials or reusable interception instructions.

*[INSERT SANITIZED RECORDER SCREENSHOT]*
Caption: The passive recorder, with personal identifiers redacted. What it proves: that legitimate sessions were observed and organised into a structured record. Stage 1 / captured while infrastructure was available, 2026. Evidence type: LIVE CAPTURE.

*[INSERT DASHBOARD SCREENSHOT]*
Caption: The live dashboard showing client-to-server activity in real time. What it proves: that the service flow was monitored and categorised as it happened. Stage 1 / 2026. Evidence type: LIVE CAPTURE.

*[INSERT SERVICE-MESSAGE TIMELINE]*
Caption: A timestamped ordering of the observed service messages. What it proves: the sequence and dependency order of the startup services. Stage 1 / 2026. Evidence type: ILLUSTRATIVE FLOW.

*[INSERT GAMEPLAY-BESIDE-CAPTURE SCREENSHOT]*
Caption: Gameplay shown alongside the corresponding captured activity. What it proves: that observed traffic corresponds to real, authorised in-game actions. Stage 1 / 2026. Evidence type: LIVE CAPTURE.

### Observed categories

The recorded sessions covered the following categories:

- Authentication
- Profile retrieval
- Progression
- Inventory
- Loadouts
- Season data
- Menu-service messages
- Matchmaking search
- Lobby state
- Match-start transition
- Match-server handoff

The last three categories were observed but belong to the Stage 2 problem; they are documented here as evidence, not reproduced in the Stage 1 environment.

---

## 5. Phase 2 — Service Mapping ("Turning Traffic into an Architecture")

The organised recordings were then turned into an architecture: each observed service category was assigned a role, a description of what the client expected from it, its importance to reaching the menu, and its current public status. No private endpoint internals are included.

| Service Category | Role | What the Client Expected | Stage 1 Importance | Current Public Status |
| --- | --- | --- | --- | --- |
| Identity | Establishes who the client is and issues session credentials; includes a third-party identity dependency | A successful check-in and valid session credentials to carry forward | Critical — nothing proceeds without it | Reproduced at a high level in the isolated environment; sensitive detail withheld |
| Profile / Meta | Returns account state: level, inventory, unlocks, loadouts, progression, season data | A populated profile record to build the menu from | Critical — the menu cannot populate without it | Reproduced with a synthetic local profile |
| Hub / Menu | Drives the live interactive menu and menu-side session state | A persistent live connection that stays responsive | Critical — the menu depends on it remaining connected | Reproduced and stabilised in current tests |
| Presence | Manages online status and background social connectivity | A stable background connection with consistent identity | Important — instability produces menu connection warnings | Reproduced and stabilised after hardening |
| Match | Live, stateful battlefield simulation | A full gameplay simulation, not a canned response | Out of scope for Stage 1 | Observed and measured only; Stage 2 research question |

---

## 6. Phase 3 — Local Stand-In Environment ("Building a Controlled Local Proof of Life")

With the architecture mapped, the team created local stand-in services inside an isolated environment. The recorded behaviour informed the responses those services returned. The client was routed to the isolated environment rather than to any live infrastructure, and a synthetic local identity and profile were supplied.

The objective was narrow and specific: determine whether the game could move through its startup sequence and reach the menu **without** the publisher backend being available. This was a feasibility test of the Stage 1 dependency chain, not a distribution effort.

For the third-party identity dependency: a locally controlled replacement was introduced for a third-party identity dependency within the isolated test environment. Details of how that replacement was constructed remain internal and are subject to authorisation and specialist review.

**Security-sensitive implementation details are intentionally omitted from the public version.** This section does not describe forging, signing or validating third-party credentials, public-key substitution, or certificate weaknesses, and it is not a private-server implementation guide.

> **Plain-language sidebar:** The team stood up its own local versions of the services the game normally calls, told the game to talk to those local versions instead, and gave it a made-up local profile. Then they watched to see whether the game would walk itself to the menu. It did.

---

## 7. Phase 4 — Profile and Menu State ("Restoring the Menu Experience")

The profile/meta layer is what controls a player's level, inventory, unlocks and loadouts. Because the menu builds itself from that data, the local environment had to supply a coherent profile before the menu could fully populate.

The environment supplied a **synthetic test profile**. With it in place, the menu, customisation and progression interfaces loaded and could be navigated. This demonstrates that the team understood how the profile service feeds the menu — it is a demonstration of service understanding, not a claim of ownership over any commercial content.

*[INSERT SANITIZED MENU RECONSTRUCTION]*
Caption: Reconstruction of the menu state produced by the synthetic test profile. What it proves: that the local profile service populated the menu, customisation and progression interfaces. Stage 1 / 23 July 2026. Evidence type: RECONSTRUCTION.

Illustrative fields represented in the reconstruction:

- Maximum test rank
- Unlocked test inventory
- Populated loadouts
- Menu categories available
- Progression interface accessible

**The synthetic profile exists only inside the isolated test environment.** It is a test fixture used to load the interfaces, not a commercial account and not distributable content.

---

## 8. Phase 5 — Stability Hardening ("Reaching the Menu Was Not Enough")

Reaching the menu once is not the same as reaching it reliably. Early in testing, the menu loaded but background connections behaved incorrectly, producing recurring connection warnings. Three separate issues were identified and corrected. The table below describes them in generalised, non-sensitive terms.

| Symptom | Root Cause | Correction | Validated Result |
| --- | --- | --- | --- |
| Recurring menu connection warning from a background channel | Incomplete presence connection handling — the connection was not being fully established and held open | Complete the connection handshake and keep the channel open | Background channel held stable in current tests |
| Menu session timing out and re-connecting on a loop | Missing server-originated heartbeat behaviour — the local service answered but never initiated its own keep-alive | Add the expected server-originated heartbeat behaviour | Session remained connected without timeout in current tests |
| Presence resetting repeatedly | Presence-layer identity mismatch — the local service presented an inconsistent identity that the client could not reconcile | Align the presence identity with what the client declares | Presence remained stable in current tests |

Detailed, reusable specifics of these corrections are withheld. The point here is the operational discipline, not a repair recipe.

> **Operator lesson:** A proof of life becomes meaningful only when the result can be reproduced and remains stable.

*[INSERT VALIDATION LOG EXCERPT]*
Caption: A sanitized excerpt showing the background connections holding steady after hardening. What it proves: that the identified instabilities were corrected and the menu stayed connected across the test run. Stage 1 / 23 July 2026. Evidence type: VALIDATION EVIDENCE.

---

## 9. Stage 1 Validation ("What Works Today")

The following matrix is deliberately conservative. Each capability is rated against what was actually demonstrated in the documented environment, with its evidence and its limitation stated plainly.

| Capability | Stage 1 Status | Evidence | Limitation |
| --- | --- | --- | --- |
| Launch from controlled local environment | VALIDATED | Repeated boots from the isolated environment | Applies to the tested build and environment |
| Complete startup service chain | VALIDATED FOR THE DOCUMENTED BUILD | Startup proceeded through all Stage 1 services locally | Tied to the specific documented build |
| Reach main menu | VALIDATED | Menu reached and navigable | Menu only — no gameplay beyond it |
| Load synthetic profile state | VALIDATED | Menu, customisation and progression interfaces populated | Profile is synthetic and local only |
| Maintain background menu connectivity | VALIDATED IN CURRENT TESTS | Stable across the hardening test runs | "Current tests"; not a permanent guarantee |
| Play actual matches | NOT IMPLEMENTED | — | Requires the Stage 2 match server |
| Support multiple players | NOT IMPLEMENTED | — | Requires match-layer work |
| Replace the match server | NOT IMPLEMENTED | — | Stage 2 research question |
| Production-ready distribution | NOT ASSESSED | — | Out of scope for this investigation |
| Publisher-approved preservation release | NOT AUTHORIZED OR CLAIMED | — | Would require rights-holder review |

The demonstrated environment is designed to remove the observed Stage 1 dependencies for the tested build. It is not claimed to work indefinitely or across other builds, and no permanence is implied.

---

## 10. Stage 2 ("The Match Server Is a Different Problem")

Stage 1 recreated startup and menu-service behaviour — largely a matter of understanding a defined sequence of requests and responses and reproducing the expected replies. A match server is a fundamentally different kind of software. It must run a live, stateful simulation: connection handling, player state, movement, entities, vehicles and combat, all synchronised in real time. That is not a replay of recorded messages; it is an ongoing computation.

To gauge whether Stage 2 is even investigable, gameplay traffic was separately captured and measured across a range of activities. The measured data appeared **structured rather than strongly encrypted**. Unreal Engine 4.21's documented network behaviour serves as a reference point for interpreting that traffic. On that basis, the dossier considers Stage 2 technically investigable.

**Feasibility is not completion.** "Investigable" means the problem is worth studying, not that a match server exists, is easy, or is guaranteed. Nothing in this section should be read as a promise that Stage 2 will succeed.

*[INSERT MATCH-TRAFFIC MEASUREMENT SUMMARY]*
Caption: Sanitized summary of the match-traffic measurements across activities. What it proves: that captured gameplay traffic appeared structured rather than strongly encrypted. Stage 1 measurement / 2026. Evidence type: VALIDATION EVIDENCE.

### Proposed Stage 2 milestones (all future work)

These are research milestones, not delivered features. None of them is implemented today.

1. **Complete a controlled connection handshake** — future work.
2. **Load into an empty map** — future work.
3. **Spawn and control a player** — future work.
4. **Add multiplayer state** — future work.
5. **Add vehicles and combat behaviour** — future work.
6. **Validate synchronisation** — future work.

Each milestone is a substantial engineering task in its own right, and progress on early milestones does not guarantee the later ones.

---

## 11. Commercial Relevance ("What This Case Demonstrates")

Stripped of the specific game, Stage 1 demonstrates a repeatable workflow for facing an online-service shutdown:

- Time-sensitive backend observation while infrastructure is still available
- Service-dependency mapping from that observation
- Evidence preservation, organised and redacted
- Local proof-of-life prototyping in an isolated environment
- Stability validation of the reproduced services
- Risk separation between menu services and match simulation
- Preparing a recovery roadmap before the infrastructure disappears

That workflow has potential applications for clients dealing with legacy or at-risk online titles, including:

- Publisher backend shutdown preparation
- Legacy multiplayer feasibility audits
- Dormant-catalogue investigation
- Service dependency documentation
- Proof-of-life prototyping
- Preservation-build planning
- Technical handoff to specialist engineering teams

These are potential applications demonstrated by a single case. No claim of universal applicability is made; every title, backend and legal context differs, and each would require its own assessment.

---

## 12. Role and Delivery Model ("How the Project Was Led")

Repository Owner operated as the technical producer and investigation lead. The work combined systems analysis, AI-assisted implementation, evidence management and iterative validation.

In practice, that role covered:

- **Investigation direction** — setting the objective (reach a stable menu without the publisher backend) and keeping the work scoped to it.
- **Milestone definition** — defining what each phase had to prove before moving on.
- **Evidence review** — organising and vetting the captured material and the redaction of sensitive data.
- **Agent coordination** — directing AI-assisted implementation work against the defined milestones.
- **Architecture understanding** — building and holding the mental model of the service chain.
- **Testing** — running and re-running the environment to confirm stability.
- **Documentation** — producing the internal dossier and this public case study.
- **Public communication** — framing the result accurately for external audiences.

This is a producer-and-lead description, not a claim of specialist credentials. It does not characterise the author as a senior security engineer, senior reverse engineer, anti-cheat engineer or cryptographer, and it does not claim sole authorship of every component.

**Specialist review is required when projects enter deeper security-sensitive, engine-level or production-delivery phases.**

---

## 13. Limitations

These limitations are load-bearing and should be read as part of every claim above:

- Stage 1 does **not** provide playable matches.
- This is **not** an official release.
- It is **not** endorsed by the rights holder.
- **No** commercial distribution is claimed.
- The result applies only to the tested build and environment.
- Security-sensitive implementation details are intentionally omitted.
- Stage 2 remains a substantial engineering effort with no guaranteed outcome.
- Legal and distribution questions require separate review.
- This case study does **not** grant permission to reproduce the method against unrelated systems.
- Future availability may depend on preserving the local project materials and environment.

---

## 14. Rights and Scope

This investigation was conducted around a legitimately obtained local copy and an isolated test environment. It does not claim ownership of the game, its assets, trademarks or original services. Any distribution, public release or commercial deployment would require appropriate rights-holder review and authorization.

---

## 15. Final Result

**STAGE 1 PROVED THAT THE MENU-LEVEL SERVICE CHAIN COULD BE UNDERSTOOD, REPRODUCED AND STABILIZED IN A CONTROLLED LOCAL ENVIRONMENT.**

That result rests on four concrete outputs: a documented proof of life inside the isolated environment; an architecture map of the startup service chain; captured, organised and redacted evidence from legitimate sessions; and a clear boundary between what has been achieved and what the match-server phase still requires. The menu is reachable and stable; the battlefield is not, and Stage 1 never claimed otherwise.

### Status panel

| Stage | Status |
| --- | --- |
| STAGE 1 | PROOF OF LIFE ACHIEVED |
| STAGE 2 | MATCH-SERVER INVESTIGATION UNDERWAY |

---

**HAVE A GAME FACING SERVER SHUTDOWN OR LEGACY INFRASTRUCTURE RISK?** RecompileLabs provides technical recovery audits, backend sunset assessments and proof-of-life investigations for rights holders and technical partners.

**REQUEST A RECOVERY ASSESSMENT**
