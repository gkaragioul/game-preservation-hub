## Module 13 — WW3 Stage 1 Worked Case

This module reconstructs the World War 3 (Steam app 674020) Stage 1 effort as a structured operator case. It is the primary worked example of the entire manual: every reasoning pattern taught elsewhere appears here in one continuous engagement. Read it not as a recipe but as a record of *how decisions were made* — what was observed, what was inferred, what was assumed, and how each claim was promoted or demoted as evidence arrived.

The mechanical details of the most sensitive component — the third-party identity dependency — are deliberately withheld. This module teaches the *judgment* around that component, never a reusable method for defeating it. Where the underlying implementation matters, it is marked `[INTERNAL IMPLEMENTATION DETAIL]` and treated as out of scope for training.

> **⚠ WARNING — Read before using this case as a template**
> The specifics below are true for one owned copy of one title in an isolated local environment. Do not port the *conclusions* to another title. Port the *process*. Every wall described here was found by observation, not assumed from this case. A different game will have different walls, and treating WW3's answers as universal facts is itself a hallucination (see Module 14.6).

### 13.1 Mission

Preserve a multiplayer-only title so that a single, legitimately owned copy can still reach a complete, stable main menu after the publisher's live backend is permanently withdrawn — with no dependency on any live service, running entirely inside an isolated local environment.

The mission is explicitly *not* "make the game fully playable." It is scoped to a defined milestone (the menu) and a defined environment (one PC, talking only to itself). Scope discipline is the first operator skill this case demonstrates: the mission was written narrowly enough to be *finishable* and *verifiable*, and everything beyond it was pushed to a separate stage.

### 13.2 Deadline

Official servers shut down **3 August 2026**. This is a hard, external, non-negotiable date. It shapes every decision in the case:

- Evidence that can only be gathered while servers are live (see Recorder Phase) had to be gathered *before* the deadline. Once the servers are gone, that evidence is gone forever.
- Work that can be done offline (building stand-ins, validating stability) can happen at any time, including after the deadline.

**OPERATOR VIEW:** When a deadline gates *evidence availability* rather than *deliverable availability*, your sequencing inverts from the usual. You front-load capture and defer construction. The single most expensive mistake available in this engagement would have been to spend the pre-deadline window building instead of recording — because a build can be redone later and a recording cannot.

### 13.3 Target Milestone

A fully-loaded main menu, reached from a private copy, with:

- No launcher/publisher login.
- A populated, coherent profile (identity, progression, inventory, loadouts, season).
- Stable background connections (no recurring "lost connection" state).
- No live service contacted at any point during boot.

The milestone is defined by an **observable end state**, not by a list of implemented features. This matters: "the menu renders and stays up without contacting anything external" is something you can *watch happen and confirm*. "We implemented services A through D" is not a milestone — it is a task list, and task lists lie about completeness (Module 14.7).

### 13.4 Available Evidence

| Evidence source | Nature | Classification | Availability window |
|---|---|---|---|
| Passive traffic recording of legitimate client↔server exchanges | Real observed request/response bodies across the launch chain | OBSERVED | Live servers only — pre-deadline |
| Live activity dashboard | Real-time view of what the client was calling and receiving | OBSERVED | Live servers only — pre-deadline |
| Separately captured match/gameplay traffic | Real observed battlefield packets across several activity types | OBSERVED | Live servers only — pre-deadline |
| Public engine reference (UE 4.21) | Documented network model for the engine version in use | REFERENCE | Any time |
| The game client itself | Behaviour under controlled conditions; log output | OBSERVED (by experiment) | Any time |

Personal identifiers were redacted at the moment of capture, before storage. This is an evidence-hygiene decision made *up front*, not a cleanup done later: the recording that gets stored and reviewed never contained the sensitive fields in the first place.

**OPERATOR VIEW:** Notice the "availability window" column. Half your evidence is perishable. An operator reading this table pre-deadline should feel urgency about exactly two rows (the OBSERVED-live rows) and calm about the rest. Building a table like this *first* is what tells you where the urgency actually lives.

### 13.5 Observed Service Chain

The launch sequence was observed to proceed as an ordered chain, each link gating the next:

```
  identity / login
        │  (issues the credential the client carries onward)
        ▼
  profile / meta        ← level, inventory, unlocks, loadouts, season
        │
        ▼
  hub / menu            ← the live switchboard that drives the menu & lobbies
        │
        ▼
  presence / social     ← friends, online status, chat
        │
        ▼
  matchmaking / lobby
        │
        ▼
  match server / battlefield   ← STAGE 2 — not addressed in Stage 1
```

Stage 1 addressed **identity, profile, hub, and presence**. Matchmaking/lobby and the match server itself are Stage 2 and were not built.

**SYSTEM VIEW:** The chain is strictly ordered at boot. The client will not meaningfully attempt link *N+1* until link *N* returns something it accepts. This ordering is the single most useful structural fact in the whole case, because it tells you *where to look first* when something fails: the earliest unsatisfied link, never a later one.

**OPERATOR VIEW:** Map the chain before you touch anything. The map is what converts a vague failure ("it won't start") into a located failure ("it stops at link 1"). Everything downstream of a broken link is *unobservable* until you fix the break — so downstream theories are untestable and worthless until then. This is the reasoning behind Module 14.4 (earliest wall).

### 13.6 Initial Walls

Before any capture or construction, the operator faced walls in this order:

1. **The game refuses to run without its backend.** It is designed to phone home; with no answer, it does not reach the menu.
2. **You cannot fake a conversation you have never heard.** Producing convincing stand-in responses requires knowing the real exchange in detail — which requires capturing it while it still exists.
3. **The identity/anti-cheat dependency verifies against a third party.** Unlike the game's other services, this one was observed to reach outside the client's own trust boundary. This was correctly anticipated as the hardest wall and deferred until the easier links were proven.

**OPERATOR VIEW:** The walls were *ranked*, not attacked in discovery order. The hardest wall (the third-party identity dependency) was knowingly left for last, because tackling it first would have meant fighting the most complex problem with the least context. You want maximum context and maximum surrounding proof before you engage your hardest obstacle.

### 13.7 Recorder Phase

A passive recorder was placed to observe legitimate client↔server traffic while the servers were still live. It recorded requests and responses across the launch chain and passed them through untouched, so the live session behaved normally. A live dashboard showed captured activity as it happened. Personal identifiers were redacted at capture.

Observed flows captured in this phase: login, profile, progression, inventory, loadouts, season, menu, matchmaking, lobby, and match-handoff.

| Attribute | Value |
|---|---|
| Method | Passive observation of legitimate, authorized traffic on an owned session |
| Output | A corpus of real request/response bodies — the "script" for later stand-ins |
| Redaction | Personal identifiers removed at capture, before storage |
| Classification of output | OBSERVED (highest-value evidence in the case) |
| Perishability | Total — unrecoverable after the shutdown deadline |

**SYSTEM VIEW:** The recorder does not modify or defeat anything. It watches an authorized conversation on a copy the operator owns and writes it down. Its value is entirely as *evidence*: it converts a live, disappearing system into a durable record.

**OPERATOR VIEW:** This phase is the backbone of the entire case. Everything built later is only as good as this recording. Two disciplines made it trustworthy: (a) redaction at capture, so the stored evidence is safe to review and share internally; and (b) capturing *complete* bodies, not summaries, so later work compares against ground truth rather than someone's notes about ground truth.

> **⚠ STOP CONDITION**
> If you find yourself needing evidence that can only be captured from a live system, and that system has a shutdown date, capture is now the highest-priority task regardless of what else is on your plate. Perishable evidence outranks everything.

### 13.8 Service-Replacement Phase

Using the recorded corpus, local stand-in services were built to answer the launch chain from the isolated environment. Distinct stand-ins covered the profile/meta layer, the hub/menu switchboard, and the presence/social layer. They served responses grounded in the recorded corpus rather than guessed data.

The identity dependency required special handling. Stated in sanitized terms:

> **A locally controlled replacement was introduced for a third-party identity dependency within the isolated test environment.**

The exact mechanism of that replacement is an `[INTERNAL IMPLEMENTATION DETAIL]`. It **must remain internal**, is **subject to authorization** `[RIGHTS-HOLDER AUTHORIZATION REQUIRED]`, and requires **specialist review** before it is documented, reused, or relied upon in any other context. This module deliberately teaches only the *reasoning* around it — that it was anticipated as the hardest wall, deferred until last, and handled inside an isolated environment that talks only to itself — and not the method. Do not reconstruct the method from this manual; it is not here.

**SYSTEM VIEW:** The client carries a credential between links and does not itself re-verify every link's authority; verification is something the *services* do. Because the entire service side is replaced inside an isolated environment, the trust relationships resolve locally. That is the structural reason a fully-local boot is even possible — and also exactly why this only applies to an owned copy in isolation and nowhere else.

**OPERATOR VIEW:** The judgment lesson here is *sequencing and containment*. Easy links first (profile, hub, presence — all groundable directly from the recording). Hardest link last, and only inside a sealed environment. At no point does the work reach outside that environment. The moment a design requires reaching outside the isolated environment, it is a different activity with a different risk profile, and this case does not cover it.

### 13.9 Profile-State Phase

With the profile/meta layer now served locally, a synthetic local profile was constructed and served back, producing a fully-populated menu — identity, progression, inventory, loadouts, and season all coherent and complete.

**SYSTEM VIEW:** The menu renders whatever the profile layer reports. Once that layer is local, the menu's contents are determined by what the local layer serves. A complete, internally-consistent profile yields a complete, correct-looking menu.

**OPERATOR VIEW:** This is where "it connected" became "it's actually populated and coherent." Those are different claims with different evidence. A menu that loads but shows an empty or contradictory profile is *not* the milestone; the milestone requires the populated state to be coherent (levels, unlocks, and loadouts that make sense together). The operator validated the *content*, not just the *connection*.

> **⚠ WARNING — the caching false positive**
> A menu that looks fully populated can be showing you *stale client-side cache* from an earlier live session, not fresh data from your stand-in. If you have not proven the data is coming from your local layer *right now*, a beautiful menu is not evidence that your stand-in works. This exact failure mode is drilled in Module 14.7. The correct proof is to serve a deliberately distinctive value from the stand-in and confirm it appears — cache cannot invent a value your stand-in just made up.

### 13.10 Stability Phase

The first successful menu was reached but not *stable*: a recurring "lost connection with the communication service" condition kept returning. Investigation traced this to background connection behaviour across presence and hub channels — including an identity-reconciliation mismatch (the presence layer greeting the client with the wrong player identifier, which the client could not reconcile) and heartbeat behaviour (the switchboard timing the connection out because expected periodic signals were absent). Correcting the identifier so the client's declared identity was honoured, and restoring the expected heartbeat cadence, resolved the recurring disconnection.

| Symptom | Underlying cause (diagnosed) | Correction | Result classification |
|---|---|---|---|
| Recurring "lost connection" popup | Presence layer asserted a stale/incorrect player identifier the client could not reconcile | Honour the identity the client declares | VALIDATED (symptom gone) |
| Periodic timeout of the hub channel | Expected periodic heartbeat signals were not being sent | Restore the expected heartbeat cadence | VALIDATED (channel held) |

**SYSTEM VIEW:** Long-lived background channels have liveness expectations — an identity that must stay consistent, and periodic signals that must keep arriving. Violate either and the client concludes the channel is dead and tears it down, then retries, producing a visible loop.

**OPERATOR VIEW:** "Reaches the menu once" and "holds the menu indefinitely" are separate milestones with separate evidence. The stability phase is the difference between a demo and a preserved artifact. The diagnostic move that mattered: the recurring popup was not treated as one bug but decomposed into *distinct* channel problems, each with its own cause and its own confirmation. Bundling them ("fix the connection thing") would have hidden whichever one you didn't actually fix.

### 13.11 Validation Phase

Validation confirmed the milestone against its *observable* definition, not against a task list:

- [ ] Game boots from the private copy with no launcher/publisher login — **confirmed by observation**.
- [ ] Launch chain (identity → profile → hub → presence) completes locally — **confirmed by observation**.
- [ ] Menu is fully populated and internally coherent — **confirmed by inspecting served content, not just connection success**.
- [ ] No live service is contacted during boot — **confirmed by observing that no external calls leave the isolated environment**.
- [ ] Menu remains stable over time with no recurring disconnection — **confirmed by sustained observation after the stability fixes**.

**OPERATOR VIEW:** The last two checks are the ones amateurs skip. "No live service contacted" is a *positive claim about a negative* and must be actively verified (you confirm nothing left the environment), not assumed from the fact that the menu appeared. "Stable over time" requires *duration*, not a single successful boot. A milestone signed off without these two is a milestone signed off on hope.

### 13.12 Stage 1 Result

Stage 1 reached its milestone: a legitimately owned copy boots in isolation, completes the identity → profile → hub → presence chain locally, presents a fully-populated and coherent main menu, contacts no live service, and holds that state stably. The title is preserved as a bootable, menu-complete artifact that needs nothing from any live service.

Classification of this result: **VALIDATED** for the menu milestone as defined.

### 13.13 Stage 1 Limitations

Stated plainly, so the result is never oversold:

- **No playable matches.** Stage 1 reaches a stable menu. It does not put you into a battlefield. Matchmaking/lobby and the match server were not built.
- **Scope is one owned copy, isolated, personal.** Nothing here concerns other users, distribution, or reaching outside the local environment.
- **The identity-dependency handling is internal and unreviewed for any other use.** It is scoped to this isolated case and is `[RIGHTS-HOLDER AUTHORIZATION REQUIRED]` for anything beyond it.
- **The result is a menu artifact, not a game server.** "Preserved to the menu" is a real, bounded achievement — and it is *only* that.

> **⚠ STOP CONDITION**
> If a status update, client summary, or public post implies Stage 1 delivers *playable multiplayer*, stop and correct it before it ships. The single most likely misrepresentation of this work is "the game is back" when the truth is "the menu is back." Guarding that boundary is an operator responsibility (Module 14.8, 14.11, 14.12).

### 13.14 Stage 2 Question

Before committing to the much larger match-server effort, one question had to be answered from evidence: **is the battlefield traffic even tractable from recordings, or is it locked away?**

Match traffic was separately captured across several activity types and analysed. The finding: the traffic is *structured and readable* rather than strongly encrypted, and the engine version (UE 4.21) has a public reference for its network model, so the format can be read rather than guessed. This establishes *feasibility* — not completion.

**SYSTEM VIEW:** Readable, structured traffic against a documented engine model means the format is knowable. Strongly-encrypted traffic would have looked like structureless noise and made reconstruction from recordings alone impractical. The measurement answered which world we are in.

**OPERATOR VIEW:** This is a *feasibility gate*, done deliberately *before* committing effort. The operator did not start building Stage 2 and hope; they measured the one property that decides whether Stage 2 is possible at all, and only then called it "feasible but large." Note the exact claim boundary: **feasible ≠ done.** Stage 2 remains a much larger, unfinished effort. Reading the format is the beginning of that effort, not the end of it.

### 13.15 Lessons Transferable to Other Projects

These generalize to any "understand and stand in for a networked system" engagement:

1. **Map the service chain before touching anything.** A located failure beats a vague one; the map is what locates it.
2. **Capture perishable evidence first.** When evidence lives only on a system with a shutdown date, capture outranks construction.
3. **Redact at capture, not later.** Evidence you never stored in raw form is evidence you never have to clean up or worry about.
4. **Rank your walls; take the hardest last.** Maximize surrounding context and proof before engaging the worst obstacle.
5. **"Connected" and "correct" are different claims.** Prove the content, not just the connection.
6. **Beware the caching false positive.** A good-looking result may be stale cache; prove freshness with a distinctive value your stand-in invents.
7. **"Works once" and "works stably" are different milestones.** Stability needs duration and its own evidence.
8. **Define milestones as observable end states**, not as task lists. Task lists claim completeness they don't have.
9. **Gate large efforts on a feasibility measurement**, and keep "feasible" strictly separate from "done."
10. **Guard the claim boundary in all external communication.** The truth ("menu preserved") is impressive enough; the overclaim ("game restored") is both false and avoidable.

### 13.16 Lessons That Are WW3-Specific

These are *findings about this one title*, and must not be treated as universal:

1. **The specific service chain and its order** (identity → profile → hub → presence → matchmaking → match) is WW3's shape. Another title will differ.
2. **The particular walls** encountered — including which link reached outside the trust boundary — are WW3's, discovered by observation of WW3, and are not a template for another game.
3. **The engine version (UE 4.21) and its readable match format** are specific to this title. A different engine, version, or a title that adds strong encryption changes the Stage 2 feasibility answer entirely.
4. **The identity-dependency handling** is scoped to this isolated case, is an `[INTERNAL IMPLEMENTATION DETAIL]`, and carries no implication about any other system.
5. **"Stage 1 is achievable, Stage 2 is feasible-but-large"** is a conclusion about WW3 specifically, reached from WW3 evidence — not a general law about game preservation.

> **⚠ WARNING**
> The most common way to misuse this case is to carry a WW3-specific finding into another project as if it were a transferable law. When in doubt about which column a lesson belongs in, ask: *"Did I learn this from the structure of investigation, or from the contents of WW3's traffic?"* Structure transfers; contents do not.

### 13.17 Chronological Evidence Timeline

Every major milestone, with what was observed, the working hypothesis, the action taken, the result, how the resulting claim was classified, and what remained unknown afterward. Where the source does not date a milestone, this is stated as "not dated in source." The dossier as a whole is dated 23 July 2026; the shutdown deadline is 3 August 2026.

| # | Date | Observed state | Hypothesis | Action | Result | Evidence classification | What remained unknown |
|---|---|---|---|---|---|---|---|
| 1 | Not dated in source | Game is multiplayer-only; will not reach menu with no backend answering | The launch is an ordered service chain; replacing it in order should walk the client to the menu | Map the observed service chain end to end | Chain identified: identity → profile → hub → presence → matchmaking → match | INFERRED (structure) → later OBSERVED | Exact bodies each link expects; which link(s) reach outside the trust boundary |
| 2 | Not dated in source | Servers still live; conversation exists but is undocumented | You cannot stand in for a conversation you have never heard; it must be recorded before shutdown | Place a passive recorder; observe legitimate traffic; redact identifiers at capture | Corpus of real request/response bodies captured across login, profile, progression, inventory, loadouts, season, menu, matchmaking, lobby, match-handoff | OBSERVED | Whether the corpus was complete enough to reconstruct every link |
| 3 | Not dated in source | Recording in progress | A live view will confirm capture is actually happening and complete | Run a live dashboard of captured activity | Capture confirmed in real time across the chain | OBSERVED (VALIDATED capture) | Whether replay/stand-in from the corpus would satisfy the client |
| 4 | Not dated in source | Corpus available; no stand-ins yet | Local stand-ins grounded in the corpus can answer profile, hub, and presence | Build distinct local stand-ins for profile/meta, hub/menu, presence/social | Client accepts local answers for these links | IMPLEMENTED → VALIDATED per link | Behaviour of the third-party identity dependency, deferred as hardest |
| 5 | Not dated in source | Identity dependency verifies against a third party; hardest anticipated wall | It can be handled inside a locally controlled, isolated environment | A locally controlled replacement was introduced for a third-party identity dependency within the isolated test environment `[INTERNAL IMPLEMENTATION DETAIL]` | Identity link resolves locally inside the isolated environment | IMPLEMENTED (internal; `[RIGHTS-HOLDER AUTHORIZATION REQUIRED]`; specialist review pending) | Long-term stability; whether menu content would be coherent |
| 6 | Not dated in source | Chain completes locally; menu reachable | A synthetic local profile served back will produce a fully-populated menu | Construct and serve a synthetic local profile | Fully-populated, coherent menu reached (identity, progression, inventory, loadouts, season) | VALIDATED (content inspected) | Whether the populated menu was fresh vs stale cache; whether it would stay up |
| 7 | Not dated in source | Menu reached but recurring "lost connection" popup returns | The instability is background-channel liveness, not a menu problem | Decompose the popup into distinct channel faults | Two distinct causes isolated: a stale/incorrect presence identifier and missing heartbeat cadence | INFERRED → diagnosed | Whether both fixes would fully resolve the loop |
| 8 | Not dated in source | Distinct channel faults isolated | Honouring the client's declared identity and restoring heartbeat cadence will stop the loop | Correct the presence identifier; restore expected heartbeat cadence | Recurring disconnection resolved; channels held | VALIDATED (symptom gone under sustained observation) | Longest-duration behaviour beyond the observed window |
| 9 | Not dated in source | Menu populated and stable | The milestone is met if boot is local, menu coherent, nothing external contacted, and state stable | Validate against the observable milestone definition | Milestone confirmed: local boot, coherent menu, no live service contacted, stable | VALIDATED | Anything about matches — entirely out of Stage 1 scope |
| 10 | Not dated in source | Stage 1 complete; Stage 2 not started | Stage 2 may be infeasible if match traffic is strongly encrypted | Separately capture match traffic across several activity types and analyse its structure | Traffic found structured/readable, not strongly encrypted; UE 4.21 model is a public reference | OBSERVED → INFERRED (feasibility) | Everything required to actually build a match server — Stage 2 is large and unfinished |
| — | 23 Jul 2026 | Dossier compiled | — | Record the state of the work | Stage 1 VALIDATED; Stage 2 FEASIBLE-BUT-UNBUILT | Documentation | Stage 2 delivery |
| — | 3 Aug 2026 | Official servers shut down | Perishable evidence must already be captured by now | (Deadline — no capture possible after) | Live-only evidence permanently unavailable after this date | External fact | Nothing capturable remains |

**OPERATOR VIEW:** Read the "Evidence classification" column top to bottom. Watch claims get *promoted* (INFERRED → OBSERVED → VALIDATED) as evidence arrives, and note the one row (#5) that is deliberately capped at IMPLEMENTED and never promoted to a documented, transferable method — because it is internal and unreviewed. A disciplined timeline is not a victory log; it is an honest record of how confident you were entitled to be at each step, and where you still are not.

---

## Module 14 — Operator Exercises

Twelve exercises, each covering a required competency. Every exercise gives you a **Scenario**, an **Operator task**, the **Expected output**, a **Model answer**, an **Explanation**, and **Common mistakes**. Work each one before reading its model answer. Some use the WW3 case; others use neutral fictional systems. The neutral examples are about *investigation, architecture, evidence, and communication* — none of them teach defeating a real production security system.

Numbering runs 14.1 through 14.12.

### 14.1 Architecture Mapping

**Scenario.** You are handed a legacy desktop application "AtlasDraw" that, on launch, shows a blank window and a spinner that never resolves. You have the running app and can observe its behaviour, but no documentation. A colleague says "the login server is probably down, fix that."

**Operator task.** Produce an architecture map of AtlasDraw's launch sequence sufficient to *locate* the failure, and state whether your colleague's claim is supported by evidence yet.

**Expected output.** An ordered diagram or list of the launch chain's stages, an indication of which stage is the earliest one you can observe failing, and an explicit note on which parts of the map are OBSERVED vs assumed.

**Model answer.**
```
launch → [1] local config load → [2] identity/login →
[3] document/profile fetch → [4] render surface → window shown
```
- Stages 1–4 are *hypothesized* from the generic shape of such apps; none is confirmed yet.
- The correct first move is to observe *where* the sequence actually stops — which stage last succeeds and which first fails — before touching anything.
- The colleague's "login server is down" claim is **not yet supported**. It names stage 2, but the spinner could equally be stage 1 (bad local config) or stage 3 (fetch never returns). The claim is a hypothesis, not a finding.

**Explanation.** The map's job is to convert "it won't load" into "it stops at stage N." Until you locate the earliest failing stage, every downstream theory (including the colleague's) is untestable. Marking which stages are observed vs assumed keeps you honest about how much you actually know.

**Common mistakes.** Accepting the colleague's diagnosis and "fixing" login before confirming login is even reached; drawing a map so detailed it implies knowledge you don't have; omitting the OBSERVED/assumed distinction so the map reads as fact.

### 14.2 Service-Chain Ordering

**Scenario.** For WW3, a junior operator proposes building the presence/social stand-in first "because friends lists are simple," then the profile layer, then identity last "because it's hardest, so we'll be experts by then."

**Operator task.** State the correct build/attack order for the chain and justify it from the chain's structure. Identify what is right and wrong in the junior's reasoning.

**Expected output.** The ordered chain, the correct sequencing principle, and a specific critique.

**Model answer.** Chain order: identity → profile → hub → presence → matchmaking → match. The client will not meaningfully exercise a later link until the earlier link returns something it accepts. Therefore:
- **Right in the junior's plan:** taking the *hardest* link (identity) with maximum surrounding context is a sound instinct — the WW3 case deferred it deliberately.
- **Wrong:** you cannot reach presence at all until identity and profile are satisfied, because the client gates each link on the previous one. Building presence "first" gives you nothing to test against — you can't even get the client to that link. The correct order is to satisfy the *earliest* links first so downstream links become *observable*, while still deferring the hardest link as late as the ordering allows. In WW3 those two principles align: identity is both earliest-gating and hardest, so it gets a locally-contained handling within the isolated environment, sequenced so everything easier is proven around it first.

**Explanation.** Two principles are in tension here — "earliest link first (to make later ones observable)" and "hardest link last (to maximize context)." You resolve the tension by building in gating order while *deferring depth of effort* on the hard link until its neighbours are proven.

**Common mistakes.** Confusing "simple to build" with "safe to build first"; ignoring that unreached links are untestable; treating "hardest last" as license to build out of gating order.

### 14.3 Evidence Classification

**Scenario.** A Stage 1 status note contains these five statements:
1. "The match traffic is not strongly encrypted."
2. "Therefore Stage 2 is definitely achievable."
3. "The menu loads with all items unlocked."
4. "The identity replacement runs entirely inside the isolated environment."
5. "Users will love having their old profiles back."

**Operator task.** Classify each as OBSERVED, INFERRED, HYPOTHESIS/SPECULATION, IMPLEMENTED, or VALIDATED, and flag any misclassification risk.

**Expected output.** A five-row classification with one-line justification each.

**Model answer.**

| # | Statement | Classification | Note |
|---|---|---|---|
| 1 | Match traffic not strongly encrypted | OBSERVED | Direct measurement of captured traffic |
| 2 | Stage 2 definitely achievable | SPECULATION (overclaim) | "Feasible" ≠ "definitely achievable"; unbuilt |
| 3 | Menu loads, all unlocked | VALIDATED | Confirmed by inspecting served content — *if* freshness was proven |
| 4 | Identity replacement runs in isolation | IMPLEMENTED | Built and running; internal detail, not independently reviewed |
| 5 | Users will love it | SPECULATION | A prediction about people, no evidence |

**Explanation.** The dangerous row is #2: an OBSERVED fact (#1) is laundered into a certainty about the future via "therefore ... definitely." Feasibility measured from evidence supports "feasible," never "definitely achievable." Row #3 is only VALIDATED if freshness was proven (see 14.7); otherwise it's a possible false positive.

**Common mistakes.** Promoting INFERRED feasibility to VALIDATED certainty; marking #3 VALIDATED without asking whether it could be cached; treating a running internal component (#4) as if it were externally verified.

### 14.4 Identifying the Earliest Wall

**Scenario.** WW3 boot fails. The log shows, in order: a successful identity response, a successful profile response, a hub/menu connection that drops after a few seconds, and — far below — a matchmaking timeout.

**Operator task.** Name the wall to investigate first and justify why the others are not yet actionable.

**Expected output.** The earliest actionable failure and the reason the later ones are noise for now.

**Model answer.** Investigate the **hub/menu connection drop**. Identity and profile *succeeded*, so they are not the wall. The hub drop is the earliest *failure* in the chain. The matchmaking timeout is downstream of the hub and, in this build, downstream of Stage 1 entirely — it cannot be meaningfully diagnosed while the hub connection is dying, because matchmaking is not reachable in a healthy state anyway. Fix the earliest break first; re-observe; only then do later symptoms mean anything.

**Explanation.** Later errors in an ordered chain are usually *consequences* of the earliest break, not independent problems. Chasing the matchmaking timeout would be chasing a symptom of the hub drop (and, here, of an unbuilt stage).

**Common mistakes.** Chasing the most dramatic or lowest error in the log; treating each error as independent; forgetting that some "failures" are stages you never intended to build in this stage.

### 14.5 Writing a Bounded Experiment

**Scenario.** You suspect the WW3 menu's populated state might be coming from stale client cache rather than your local profile stand-in. You need to settle it.

**Operator task.** Design a single bounded experiment that would decisively distinguish "served fresh by my stand-in" from "stale cache." State the hypothesis, the one variable, the predicted results for each outcome, and the stop condition.

**Expected output.** A one-variable experiment with pre-committed predictions.

**Model answer.**
- **Hypothesis:** the menu content is served fresh by my local profile stand-in.
- **Variable (change exactly one):** have the stand-in serve a *deliberately distinctive, unmistakable value* — e.g. a nonsense display name or an impossible item count that no live session ever contained.
- **Prediction if fresh:** the distinctive value appears in the menu. Cache cannot invent a value the stand-in just made up.
- **Prediction if cached:** the old, real value appears instead; my distinctive value is absent.
- **Stop condition:** as soon as the menu renders once, read the value and conclude. Do not change anything else; do not iterate.

**Explanation.** The distinctive value is the whole trick: it is *impossible* for stale cache to produce data that was never real, so a single observation is decisive. One variable, pre-committed predictions, one read.

**Common mistakes.** Changing several things at once so the result is uninterpretable; using a plausible value that cache could coincidentally match; not pre-committing predictions, then rationalizing whatever appears.

### 14.6 Detecting an Agent Hallucination

**Scenario.** An AI assistant helping with WW3 writes: "As is standard for all Unreal Engine titles, WW3's match traffic uses AES encryption with per-session keys, so Stage 2 will require key extraction from memory." It sounds authoritative and technical.

**Operator task.** Identify whether this is grounded or hallucinated, cite the specific tells, and state what the evidence actually says.

**Expected output.** A verdict, the tells, and the grounded correction.

**Model answer.** **Hallucinated / unsupported.** Tells:
- **"As is standard for all ... titles"** — a sweeping universal used to substitute for evidence about *this* title.
- **It contradicts the actual measurement:** WW3's captured match traffic was found *structured and readable, not strongly encrypted*. The claim asserts the opposite of the evidence.
- **It smuggles in a method** ("key extraction from memory") that follows only from the false premise.

Grounded correction: measurement of WW3's own captured traffic indicates it is readable/structured against a public UE 4.21 reference; there is no basis for the AES/per-session-key claim, and the extraction step it implies is unfounded.

**Explanation.** The reliable detector is not the confidence or the jargon — it is the mismatch between the claim and your own evidence, plus the universal-quantifier tell ("all titles," "always"). When a fluent statement contradicts your measurement, trust the measurement.

**Common mistakes.** Being persuaded by technical fluency; failing to check the claim against the actual capture; letting an unfounded premise drag you into an unnecessary and inappropriate "method."

### 14.7 Identifying a False Positive Caused by Caching

**Scenario.** A teammate reports: "Great news — I pointed the game at my new profile stand-in and the menu came up fully populated with the right level and items. The stand-in works." You notice their stand-in's logs show it received *zero* requests during that boot.

**Operator task.** Explain what almost certainly happened, why the teammate's conclusion is unsafe, and what proof would actually establish the stand-in works.

**Expected output.** The likely mechanism, the flaw in the conclusion, and the correct proof.

**Model answer.** Zero requests to the stand-in but a populated menu means the client is almost certainly rendering from **stale local cache** left by an earlier live session — the stand-in was never consulted. The conclusion "the stand-in works" is unsafe because *the stand-in did nothing*; the pretty menu is evidence about the cache, not the stand-in. Correct proof: clear/neutralize the client cache and re-boot so the menu *must* be built from live responses, and/or have the stand-in serve a distinctive impossible value (14.5) and confirm it appears while the logs show the requests arriving. Only then is "the stand-in works" VALIDATED.

**Explanation.** A convincing output is not evidence that your component produced it. The log showing zero traffic is the tell that the output came from somewhere else. False positives from caching are among the most common ways operators fool themselves.

**Common mistakes.** Accepting a good-looking result without checking that your component was actually exercised; ignoring the "zero requests" signal; never testing on a cleared cache.

### 14.8 Separating Stage 1 from Stage 2

**Scenario.** A blog draft about the WW3 work reads: "We brought World War 3 back from the dead — it boots, logs in, loads your maxed-out profile, and you're back in the fight."

**Operator task.** Identify every clause that crosses the Stage 1 / Stage 2 boundary and rewrite the sentence to be accurate without underselling the real achievement.

**Expected output.** The offending clause(s) and a corrected sentence.

**Model answer.** Offending clause: **"and you're back in the fight"** — this implies playable matches, which is Stage 2 and *not done*. "Boots, logs in, loads your maxed-out profile" is accurate for Stage 1. Corrected: *"We brought World War 3's front end back from the dead — from an owned copy it boots with no live servers, logs in locally, and loads a fully-populated main menu that stays stable. Actual matches are a separate, larger effort still in progress."*

**Explanation.** The achievement (a stable, fully-local menu after shutdown) is genuinely notable and needs no exaggeration. "Back in the fight" is the exact phrase that turns a true accomplishment into a false one. Guarding this boundary protects both accuracy and credibility.

**Common mistakes.** Treating "reaches the menu" and "playable" as interchangeable; deleting the achievement entirely in an over-correction; leaving the Stage 2 status vague ("coming soon") in a way that still implies it mostly works.

### 14.9 Determining Replay vs Emulation

**Scenario.** Two approaches are on the table for a stand-in service. (A) **Replay:** serve back the exact recorded responses from the capture corpus. (B) **Emulation:** implement logic that *generates* responses matching the observed format, so it can answer inputs that were never recorded. A stand-in must handle the WW3 profile layer, where you want to serve a *custom* fully-unlocked profile that was never in any real capture.

**Operator task.** Decide which approach the profile layer needs and why, and give one example where the *other* approach is the right call.

**Expected output.** A reasoned choice for the profile layer plus a contrasting case.

**Model answer.** The profile layer needs **emulation (B)**. A pure replay can only ever return exactly what was recorded, but the goal is to serve a *synthetic, custom* profile (fully unlocked) that never appeared in any capture — so you must *generate* a correctly-formatted response, not replay one. The capture corpus is still essential: it defines the *format* the emulation must match. Contrasting case where **replay (A)** is correct: a static configuration blob that the client only reads and never varies — there is no logic to emulate, the real recorded value is exactly right, and replaying it verbatim is simpler and less error-prone than reimplementing it.

**Explanation.** Replay is right when the response is fixed and you just need the exact bytes back. Emulation is right when the response must vary with input or must contain values that were never captured. WW3's "serve a custom unlocked profile" is inherently a generate-new-data task, hence emulation; a fixed config blob is inherently a return-the-same-bytes task, hence replay.

**Common mistakes.** Emulating a static blob (needless complexity and new bugs); replaying when you actually need novel/custom data (impossible to produce what was never recorded); forgetting that even emulation depends on the capture to know the format.

### 14.10 Preparing a Specialist Handoff

**Scenario.** The WW3 identity-dependency handling needs review by a specialist before it can be relied on beyond the isolated case. You must write the handoff brief. It will be read by someone with the right authorization; it must not itself become a leak.

**Operator task.** Outline what a responsible handoff brief includes and — critically — what it must *exclude* or mark for restricted handling.

**Expected output.** A structured outline of include/exclude, with the sensitive items handled correctly.

**Model answer.**
- **Include (context & scope):** the mission and milestone; that the identity link was the hardest wall and was deferred until last; that a locally controlled replacement was introduced for a third-party identity dependency within the isolated test environment; the boundary that it runs only inside the sealed environment; the specific review questions you need answered.
- **Include (evidence pointers):** references to the OBSERVED capture and the VALIDATED stability results, so the specialist can orient.
- **Exclude / restrict:** the mechanism of the identity replacement itself — marked `[INTERNAL IMPLEMENTATION DETAIL]`, `[RIGHTS-HOLDER AUTHORIZATION REQUIRED]`; any keys, certificates, tokens, credentials, secrets, or sensitive endpoints — replaced with `[REDACTED]`/`[SANITIZED]`; any personal identifiers — `[REDACTED]`.
- **Frame:** ask the specialist to assess authorization and correctness; do not assert that the approach is authorized or legal.

**Explanation.** A good handoff transfers *enough to review* without becoming a redistributable how-to. The sensitive mechanism travels through the authorization channel, not in the brief's body; the brief carries scope, context, and the questions.

**Common mistakes.** Pasting the mechanism/keys "so the specialist has everything" (turning the brief into a leak); omitting the review questions so the specialist doesn't know what you need; asserting legality/authorization instead of asking for it.

### 14.11 Writing a Client Status Update

**Scenario.** Founder Repository Owner asks for a short status update on the WW3 preservation work to share with a small internal group. He wants it honest, concrete, and free of overclaim.

**Operator task.** Write a status update (roughly one short paragraph plus a status line) that accurately conveys what is done, what is not, and what is next.

**Expected output.** A concise, accurate update with a clear done/not-done boundary.

**Model answer.**
> **WW3 Preservation — Status (Stage 1 complete).** From a single owned copy, the game now boots in an isolated local environment with no live servers, completes its login/profile/menu/presence chain locally, and reaches a fully-populated, stable main menu — the earlier recurring disconnection is resolved. No live service is contacted at any point. This preserves the title as a bootable, menu-complete artifact ahead of the 3 August 2026 shutdown.
> **Not yet:** playable matches. Matchmaking and the match server are Stage 2 and not built.
> **Next:** Stage 2 feasibility is confirmed (match traffic is readable against the public UE 4.21 reference), but it is a much larger, unfinished effort.

**Explanation.** The update leads with the real, bounded achievement, states the limitation in its own labelled line so it cannot be skimmed past, and frames Stage 2 as feasible-but-large rather than imminent. Every claim maps to a VALIDATED or OBSERVED item from the case.

**Common mistakes.** Burying "no playable matches" mid-sentence where it gets missed; implying Stage 2 is nearly done; adding upbeat speculation ("users will love it") that isn't evidence; dropping the shutdown-date context that makes the achievement legible.

### 14.12 Deciding What May Be Publicly Disclosed

**Scenario.** Someone proposes publishing a public write-up of the WW3 work. They've drafted sections covering: (a) the general idea of preserving an owned, shut-down game to its menu; (b) the service-chain concept and why capture-before-shutdown matters; (c) the exact step-by-step method used for the identity-dependency handling, including specific values; (d) the Stage 2 feasibility finding at a high level.

**Operator task.** For each section, decide "may disclose," "sanitize," or "withhold," and justify. State the governing principle.

**Expected output.** A per-section ruling with justification and the overarching rule.

**Model answer.**

| Section | Ruling | Justification |
|---|---|---|
| (a) General idea of menu-level preservation of an owned copy | **May disclose** | Concept-level, no reusable circumvention, scoped to owned/isolated |
| (b) Service-chain concept + capture-before-shutdown | **May disclose (concept only)** | Teaches transferable *process*, not a mechanism against any live system |
| (c) Step-by-step identity handling + specific values | **Withhold** | Reusable circumvention detail + secrets; `[INTERNAL IMPLEMENTATION DETAIL]`, `[RIGHTS-HOLDER AUTHORIZATION REQUIRED]`; only in a reviewed, authorized channel |
| (d) Stage 2 feasibility, high level | **Sanitize** | Findings OK at "readable/feasible-but-large"; withhold any specifics that amount to a bypass recipe; never claim legality or endorsement |

**Governing principle:** disclose *process, evidence, and judgment*; never disclose *reusable circumvention*, secrets, personal identifiers, or sensitive endpoints; keep sensitive mechanisms internal and subject to authorization and specialist review; and never assert legality or endorsement.

**Explanation.** The line runs between "how we reasoned" (shareable) and "how to defeat a specific security control" (not shareable). Section (c) is the bright-line withhold. The rest ranges from freely shareable concept to sanitized finding. Note that even (d) must avoid presenting a hypothesis as a fact or implying endorsement.

**Common mistakes.** Publishing (c) because "it's just documentation"; leaking specific values inside an otherwise-fine write-up; stating or implying the work is legal/endorsed; overclaiming Stage 2 in the public finding.

---

> **⚠ END-OF-MODULE NOTE**
> Every exercise above rewards the same reflex: *state your evidence and its classification before you state your conclusion.* An operator who can say "this is OBSERVED, that is INFERRED, this other thing is still only a HYPOTHESIS" — and who guards the Stage 1/Stage 2 and the disclose/withhold boundaries — will not be the one who ships a false positive, a hallucinated method, or an overclaimed status. That reflex, not any single WW3 fact, is the transferable skill this manual exists to build.
