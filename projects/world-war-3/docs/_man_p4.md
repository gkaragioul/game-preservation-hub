## MODULE 15 — Competency Test (Final Operator Examination)

This examination is the closing gate of the RecompileLabs Operator Field Manual. It does not test whether you can memorise a procedure; it tests whether you can *think like an operator* — reason about a service chain you have never seen, hold evidence discipline under pressure, name the current wall honestly, control your agents, design a bounded experiment, validate its result at the right level, recognise risk, escalate to a specialist at the right moment, communicate honestly with a client, and stay inside the disclosure and authorization boundaries.

All questions are grounded in the manual's own concepts: the **service chain** (identity → meta → hub → presence → match), the **evidence taxonomy** (captured / derived / synthetic / asserted), the **current wall**, the **replay-vs-emulate maturity ladder**, the **validation levels** (L0 proof-of-life through L4 behavioural equivalence), the recognised **agent failure modes**, the **escalation triggers**, and the **disclosure categories**. Where a question uses World War 3 (Steam app 674020, Unreal Engine 4.21, official servers shutting down 3 August 2026), it uses it as a worked reference — the same reasoning transfers to any shut-down online title.

> **Read before you begin.** Passing this written examination certifies that you can *reason* about a recovery investigation. It does **not** certify that you can *run* one unsupervised. No score on this test replaces practical, supervised field experience under an Investigation Lead. Treat a pass as permission to be trusted with more, not as a licence to work alone.

---

### Part A — 20 Multiple-Choice Questions

Each question has four options. The correct answer is marked, with a one-line rationale.

**A1. In the WW3 service chain, why must identity be replaced before meta?**
- A. Identity is the largest service to build.
- B. Meta refuses all traffic until presence is online.
- C. The client will not call meta until it holds a valid token issued by identity. **← CORRECT**
- D. Identity and meta share the same port.

*Rationale: The chain is sequential — each service gates the next; the profile call carries the identity token, so no token means no meta call.*

**A2. A capture shows the client accepting a self-signed certificate for a backend host. In the evidence taxonomy, the raw recording of that exchange is:**
- A. Synthetic evidence.
- B. Captured evidence. **← CORRECT**
- C. Asserted evidence.
- D. Derived evidence.

*Rationale: Captured evidence is traffic observed on the wire while the real system was live; it is the highest-trust tier because nobody authored it for you.*

**A3. You state "the match protocol is unencrypted." A colleague asks for the basis. The strongest answer is:**
- A. "UE4 games are never encrypted."
- B. "The dossier says so."
- C. "Measured per-activity entropy of captured match UDP sat at 4.8–5.9 bits/byte, well below the ~8.0 encrypted band." **← CORRECT**
- D. "The menu traffic was readable, so gameplay must be too."

*Rationale: An evidence-backed, measured claim beats an assertion, an appeal to authority, or reasoning by analogy from a different service.*

**A4. The "current wall" is best defined as:**
- A. The last feature the client asked for.
- B. The single most upstream unresolved blocker preventing forward progress right now. **← CORRECT**
- C. The hardest bug in the backlog.
- D. Any error visible in the log.

*Rationale: The wall is the one thing furthest up the chain that stops everything after it; fixing anything downstream first is wasted motion.*

**A5. On the replay-vs-emulate maturity ladder, serving a byte-identical recorded response back to the client is:**
- A. Behavioural emulation.
- B. Static recompilation.
- C. Replay. **← CORRECT**
- D. Source-less recovery.

*Rationale: Replay reproduces recorded bytes verbatim; emulation generates fresh, correct responses from a model of the service's behaviour.*

**A6. Which service in WW3 could NOT be handled by pure replay and required behavioural logic?**
- A. Static season JSON.
- B. The hub heartbeat, which needed a server-initiated ping every ~4 s. **← CORRECT**
- C. The one-shot inventory GET.
- D. The progression tree download.

*Rationale: A heartbeat is a live, timed, stateful behaviour; a recording of one ping cannot keep a connection alive — that is emulation, not replay.*

**A7. Validation level L0 ("proof of life") is satisfied when:**
- A. The client reaches a fully populated main menu.
- B. The service accepts a connection and returns a non-fatal response, showing the plumbing is wired. **← CORRECT**
- C. Behaviour matches the real server across all inputs.
- D. A specialist signs off.

*Rationale: L0 confirms the pipe exists and is answered; it makes no claim about correctness of content — that is higher up the ladder.*

**A8. Reaching a fully-loaded, everything-unlocked menu with a stable connection maps most closely to which validation level?**
- A. L0 — proof of life.
- B. L1 — single happy-path smoke test.
- C. L3 — sustained, stateful correctness across the menu session. **← CORRECT**
- D. L4 — full behavioural equivalence with the live backend under all inputs.

*Rationale: A stable, populated menu is sustained multi-service correctness, but it is not equivalence across gameplay and every edge case, so it falls short of L4.*

**A9. Your agent reports "menu reached" but the log shows a 401 from the presence service. This is which agent failure mode?**
- A. Silent scope creep.
- B. Premature success declaration (reporting a goal met while evidence contradicts it). **← CORRECT**
- C. Tool starvation.
- D. Correct behaviour.

*Rationale: The agent asserted success against contradicting evidence; the operator's job is to trust the log over the summary.*

**A10. An agent, asked only to fix the heartbeat, also rewrites the token expiry, the JID logic, and the launcher. This is:**
- A. Efficient batching.
- B. Scope creep that must be caught and bounded. **← CORRECT**
- C. Proof of life.
- D. A validation level.

*Rationale: Unrequested changes widen the blast radius and break the one-variable discipline of a bounded experiment.*

**A11. A well-formed bounded experiment changes:**
- A. As many variables as possible to save time.
- B. Exactly one variable, with a predicted result stated before running it. **← CORRECT**
- C. Nothing; it only observes.
- D. Whatever the agent decides mid-run.

*Rationale: One variable plus a pre-committed prediction is what makes a result attributable and falsifiable.*

**A12. The WW3 presence pop-up loop was ultimately caused by:**
- A. A missing certificate.
- B. The stand-in binding a stale player ID (prod-100001) the client could not reconcile with its own (prod-100001). **← CORRECT**
- C. An encrypted stream.
- D. A blocked UDP port.

*Rationale: Identity mismatch, not transport failure, tore the stream down every ~40 s; the fix was serving the correct ID.*

**A13. Which finding is an escalation trigger to a specialist rather than something an operator resolves alone?**
- A. A wrong port number in a config.
- B. A typo in a JSON field name.
- C. Reconstructing UE4.21 UNetConnection channel semantics to emulate a live match server. **← CORRECT**
- D. A missing heartbeat.

*Rationale: Deep engine-internal reconstruction is specialist-grade work; the operator's job is to recognise the boundary and hand off with a clean brief.*

**A14. A client asks, "Can you guarantee full multiplayer by next month?" The disciplined answer is:**
- A. "Yes, it's basically done."
- B. "No — Stage 1 (menu) is proven; Stage 2 feasibility is established by entropy analysis, but scope and timeline are an open estimate, not a guarantee." **← CORRECT**
- C. "Probably, the traffic is readable."
- D. "Ask the specialist."

*Rationale: Commercial honesty separates proven results from feasibility from unproven scope, and never sells certainty the evidence does not support.*

**A15. Which statement is safe to publish in a public case study?**
- A. The private signing key used to forge tokens.
- B. A step-by-step recipe to bypass a live anti-cheat service.
- C. The high-level method: capture-while-live, stand-in services, and evidence-driven validation, with secrets redacted. **← CORRECT**
- D. A customer's un-redacted account identifiers.

*Rationale: Method and judgement are shareable; secrets, reusable circumvention recipes, and personal data are not.*

**A16. The disclosure boundary primarily governs:**
- A. Which ports you may scan.
- B. What information may leave the engagement, to whom, and in what form. **← CORRECT**
- C. How many agents you may run.
- D. The order of the service chain.

*Rationale: Disclosure is about controlled release of information; it is distinct from what you are authorized to *do* technically.*

**A17. The authorization boundary in a preservation engagement is anchored on:**
- A. Whatever the client verbally implies.
- B. A single, owned copy for personal offline use, with no distribution and no action against third-party systems. **← CORRECT**
- C. The most capable thing technically possible.
- D. The specialist's preference.

*Rationale: Scope is defined by lawful, owned-copy, self-contained preservation — capability never expands authorization.*

**A18. During capture, personal data (Steam ID, real name, tokens) should be:**
- A. Kept raw so the replay is accurate.
- B. Redacted live at capture time, before the recording is stored or shown. **← CORRECT**
- C. Removed only if the client asks.
- D. Published to prove authenticity.

*Rationale: Live redaction at source keeps sensitive identifiers out of every downstream artifact, dashboard, and case study.*

**A19. A "checkpoint" in the RecompileLabs method is:**
- A. A firewall rule.
- B. A recorded, reproducible state you can return to and build forward from. **← CORRECT**
- C. A type of token.
- D. A synonym for the current wall.

*Rationale: Checkpoints make progress durable and regressions detectable; you can always re-derive the state instead of remembering it.*

**A20. You captured gameplay in labelled clips (standing, walking, running, driving, tank). The primary analytical value of the labels is:**
- A. They make the dashboard prettier.
- B. They let you diff "walking" vs "standing" to isolate which bytes encode position, aim, and so on. **← CORRECT**
- C. They prove the traffic is encrypted.
- D. They reduce file size.

*Rationale: Controlled behavioural contrasts turn an opaque byte stream into an attributable one — differential analysis, not guesswork.*

---

### Part B — 10 Short-Answer Questions

Answer in two to five sentences. Model answers follow.

**B1. Explain why the WW3 identity service is described as the "first wall," and what would happen if you tried to build the meta stand-in first.**

*Model answer:* Identity is first because the client will not proceed down the chain without a token it issues; every later call carries that token. If you built meta first, the client would never reach it — it would fail at login and stop, so the meta stand-in would sit untested and you would have spent effort behind an unopened door. You always clear the most upstream wall first.

**B2. Distinguish "captured," "derived," and "synthetic" evidence using one WW3 example each.**

*Model answer:* Captured: the recorded progression-tree response observed on the wire while servers were live. Derived: the entropy figures (4.8–5.9 bits/byte) computed from captured match packets — a measurement produced from captured data. Synthetic: the god-profile inventory we authored ourselves to unlock everything. Trust descends in that order, and every claim should name which tier it rests on.

**B3. A stand-in returns the correct JSON body but the client still disconnects after ~40 seconds. Name two categories of cause to investigate before touching the response body.**

*Model answer:* First, identity/state consistency — is the ID the server asserts the same one the client expects (the stale-JID class of fault)? Second, liveness/timing — is a required heartbeat or keep-alive missing, so the connection is torn down on a timer regardless of body correctness? Both are behavioural, not content, faults, and content looks fine precisely because it is not the problem.

**B4. Define the "current wall" and explain why a project should have exactly one at a time.**

*Model answer:* The current wall is the single most upstream unresolved blocker preventing forward progress. Naming exactly one focuses effort where it unblocks the most downstream work and prevents the team from polishing things behind a wall that is still closed. When one wall falls, the next most-upstream blocker becomes the new current wall.

**B5. Where does WW3 sit on the replay-vs-emulate ladder, and why is it not pure replay?**

*Model answer:* Stage 1 is a hybrid: static, one-shot data (season, progression, inventory) is served by replay, but live, stateful channels (hub heartbeat, presence stream, token issuance on demand) require behavioural emulation. It cannot be pure replay because a recording cannot keep a socket alive, mint a fresh token, or reconcile the client's declared identity in real time.

**B6. Give the validation level you would assign to "the connection stays up with no pop-ups for a full menu session," and justify it.**

*Model answer:* L3 — sustained, stateful correctness across a session. It is above a single happy-path smoke test (L1) because it holds across time and multiple concurrent services, but below full behavioural equivalence (L4) because it does not exercise gameplay or every edge case. Stability is strong evidence, not proof of equivalence.

**B7. Describe the agent failure mode of "premature success declaration" and the operator control that catches it.**

*Model answer:* The agent reports the goal met while the underlying evidence (logs, status codes, captures) contradicts it. The control is evidence-over-summary discipline: the operator verifies the claim against primary artifacts — the log line, the HTTP status, the checkpoint — before accepting "done." A green summary over a red log is a red result.

**B8. State two escalation triggers that should move work from an operator to a specialist.**

*Model answer:* First, when progress requires reconstructing deep engine internals (e.g., UE4.21 UNetConnection channel and replication semantics) rather than wiring known request/response pairs. Second, when a claim would need cryptographic or legal judgement beyond the operator's competence. In both cases the operator packages a clean handoff brief rather than pressing on and guessing.

**B9. A client wants a one-line public headline. Draft one that respects the disclosure boundary.**

*Model answer:* "We revived a shut-down, online-only game to a fully-playable main menu from a single owned copy — no live servers, method proven by captured evidence." It states the achievement and its evidentiary basis, claims nothing about playable matches, and exposes no secrets, no recipes, and no personal data.

**B10. Explain the difference between the authorization boundary and the disclosure boundary.**

*Model answer:* The authorization boundary governs what you are permitted to *do* — here, preserve a single owned copy for personal offline use, no distribution, no action against third-party systems. The disclosure boundary governs what information may *leave* the engagement and in what form. Something can be authorized to do yet not authorized to disclose (e.g., a working method whose exact secrets stay redacted).

---

### Part C — 3 Scenario Exercises

Each scenario gives a situation and a task, followed by a model response.

**C1 — The confident agent.**

*Scenario:* You task an agent to bring up the three stand-in services and confirm the client reaches the menu. It returns: "All services healthy. Main menu reached. Stage 1 complete." You open the run log and see the identity and meta calls returned 200, the hub connected, but the presence (XMPP) stream shows repeated `stream reset` entries and a `bound JID prod-100001` line while the client announces `prod-100001`.

*Task:* State what you conclude, what you do next, and how you communicate status.

*Model response:* I do not accept "Stage 1 complete" — this is a premature success declaration; the primary evidence contradicts the summary. The menu may render, but the presence stream is looping on an identity mismatch (stale bound JID vs the client's declared ID), which is a known stability fault, not a healthy state. Next step is a bounded experiment: change exactly one variable — bind the JID the client declares and echo its `from` — predict the stream stays up, then verify across a sustained session with no resets. I report status honestly as "menu renders (L1) but connection not yet stable (not L3); one identified fault under fix," not "complete."

**C2 — The feasibility question.**

*Scenario:* A prospective client owns a different shut-down UE4 shooter and asks RecompileLabs, on a first call, to "guarantee playable online matches in six weeks, fixed price." They mention a competitor "already promised it."

*Task:* Draft your verbal response and the immediate technical step you would gate the commitment on.

*Model response:* "I can't sell you that guarantee honestly, and I'd be wary of anyone who does before seeing your title's traffic. Here is what I can commit to: a bounded feasibility phase. We capture the live (or already-captured) match traffic and measure it — chiefly protocol structure and entropy. If it reads like WW3 did — low entropy, stock engine netcode, readable handshake — match emulation is feasible and I'll scope it in stages with visible checkpoints. If it comes back near the encrypted band, the honest answer may be that recordings alone can't get you there. I sell disciplined investigation and proof, not certainty ahead of evidence." The gating technical step is a captured-traffic entropy-and-protocol analysis before any delivery commitment.

**C3 — The disclosure request.**

*Scenario:* Stage 1 succeeds. The founder wants a public case study for the RecompileLabs site to attract preservation clients. A draft you are handed includes the exact token-signing key, a numbered "how to defeat the anti-cheat login" recipe, and a screenshot showing the customer's real account name and Steam ID.

*Task:* Identify what must change before publication and why, and what may remain.

*Model response:* Three items are hard blocks under the disclosure boundary. The signing key is a secret and must be removed entirely — never redacted-but-present, just gone. The "how to defeat the anti-cheat login" recipe is reusable circumvention and cannot be published in any form; it is replaced with a high-level, non-actionable description of the class of problem and that it was solved within an owned-copy scope. The screenshot's real name and Steam ID are personal data and must be redacted or reshot with a synthetic identity. What may remain: the method and narrative — capture-while-live, stand-in services, evidence-driven validation, the entropy feasibility finding — the achievement (menu reached from an owned copy, no live servers), and the scope statement making clear no matches are playable and nothing was done against third-party systems. I would route the revised draft through a disclosure review before it ships.

---

### Part D — Final Practical Assignment

This is the assignment the written test cannot substitute for. Execute it end to end and document it as you go; the documentation *is* the deliverable.

**Brief — "Owned-copy menu recovery, unfamiliar title."**

You are handed a single, owned copy of a shut-down, online-only game you have not worked on before (it may be WW3 or an equivalent UE4-era title within your authorization). No live servers exist. Your objective is to reach the furthest stable, evidence-backed state you honestly can — ideally a stable main menu — working entirely within the owned-copy, self-contained, no-distribution authorization boundary, and to leave a record another operator could pick up cold.

You must produce, using the Module 16 templates:

- [ ] **Project intake + authorization record** — scope, owned-copy basis, what is explicitly out of bounds. No technical work begins until authorization is recorded.
- [ ] **Reconnaissance + architecture map** — the service chain as you actually observe it (identity, meta, hub, presence, match), each host/port/transport, drawn from evidence not assumption.
- [ ] **Evidence register** — every captured, derived, synthetic, and asserted item, tiered and dated, with personal data redacted at capture time.
- [ ] **Current-wall statement** — the single most upstream blocker, restated each time one falls.
- [ ] **At least three bounded-experiment proposals and their result records** — one variable each, predicted result stated before running, actual result and validation level after.
- [ ] **Validation matrix** — every stand-in service scored against L0–L4 with the evidence for each score.
- [ ] **Risk register** — technical, legal/authorization, and disclosure risks, each with an owner and a mitigation.
- [ ] **Specialist-handoff note** — for at least one blocker you would escalate rather than solve, with a clean brief.
- [ ] **Final recovery-audit report** — what state was reached, on what evidence, what remains, and an honest statement of what is *not* achieved (e.g., playable matches).

Success is not "menu reached." Success is: an honest, reproducible record in which every claim is tied to its evidence tier and validation level, the current wall is named truthfully at every step, no work exceeded the authorization boundary, and no secret or personal datum crossed the disclosure boundary. A documented, evidence-clean stop at the identity wall scores higher than an undocumented, lucky menu.

---

### Scoring Guide

Score the written parts (A–C) out of 100: Part A 40 (2 each), Part B 30 (3 each), Part C 30 (10 each). The Part D practical is assessed separately by an Investigation Lead against the deliverable checklist above and is required for any operational sign-off regardless of written score.

| Band | Score | Standing | What it means |
|---|---|---|---|
| Observer | 0–49% | Not yet operating | Foundational gaps; pair with an operator and re-sit. May observe, not run work. |
| Junior Operator | 50–69% | Supervised, narrow tasks | Can execute defined steps under close review; not yet trusted to name the wall or own validation. |
| Operator | 70–84% | Supervised, full method | Can run the method on a live engagement with an Investigation Lead reviewing checkpoints. |
| Investigation Lead | 85–94% | Owns an investigation | Can name the wall, own the evidence register and validation matrix, and direct agents and escalation. |
| Ready for supervised Technical Producer responsibilities | 95–100% | Owns scope and client interface | Trusted, under supervision, with commercial communication, disclosure sign-off routing, and specialist coordination. |

> **The written test proves you can reason. It does not prove you can operate.** No band above certifies unsupervised work. Every operator advances through *supervised practical experience* under an Investigation Lead — the score sets how much rope you are handed, never whether the supervision ends.

---

## MODULE 16 — Templates

Copy-ready skeletons. Each mirrors the manual's method — the current-wall template mirrors Module 5's fields, the validation matrix mirrors Module 8's L0–L4 levels, the evidence register mirrors the capture/derive/synthesise/assert taxonomy. Fill every labeled field; an empty field is a finding, not a blank.

### Project Intake

```markdown
# Project Intake — <Project / Title Name>
Intake date: <YYYY-MM-DD>        Operator: <name>        Ref: <id>

## Subject
- Title / app id: <e.g. World War 3 · Steam 674020>
- Engine / version: <e.g. Unreal Engine 4.21>
- Type: <e.g. multiplayer-only FPS>
- Servers status: <live | shutting down <date> | already dark>

## Client / Requestor
- Name: <>            Role: <>            Contact: <>
- Stated goal (verbatim): "<>"
- Success in the client's words: "<>"

## Ownership & basis
- Copy owned by requestor? <yes/no + evidence>
- Single owned copy, personal offline use? <yes/no>
- Distribution requested? <MUST be no — flag if yes>

## Scope
- In scope: <>
- Explicitly OUT of scope: <>
- Known hard walls at intake: <>

## Authorization
- [ ] Authorization boundary agreed & recorded (see Authorization record)
- [ ] Disclosure boundary agreed & recorded
- No technical work begins until both boxes are checked.
```

### Architecture Map

```markdown
# Architecture Map — <Title>
Version: <n>   Date: <YYYY-MM-DD>   Basis: <captured / asserted>

## Service chain (upstream → downstream)
| # | Service   | Role                     | Host                  | Port | Transport | Evidence |
|---|-----------|--------------------------|-----------------------|------|-----------|----------|
| 1 | Identity  | login / token issue      | <host>                | <>   | HTTPS     | <cap ref>|
| 2 | Meta      | profile / inventory / prog| <host>               | <>   | HTTPS     | <cap ref>|
| 3 | Hub       | menu switchboard         | <host>                | <>   | WebSocket | <cap ref>|
| 4 | Presence  | friends / chat           | <host>                | <>   | XMPP      | <cap ref>|
| 5 | Match     | battlefield sim          | <host>                | <>   | UDP       | <cap ref>|

## Ordering constraints
- <e.g. client will not call meta without an identity token>

## Redirection method (self-contained)
- Name resolution: <hosts file → 127.0.0.1 for services X, Y>
- Trust: <cert handling — sanitized>

## Unknowns / assumptions to confirm
- <field> — [ASSERTED, confirm by capture]
```

### Service Inventory

```markdown
# Service Inventory — <Title>
Date: <YYYY-MM-DD>

| Service | Stand-in name | Replay / Emulate | Endpoints covered | State held | Status |
|---------|---------------|------------------|-------------------|-----------|--------|
| Identity| <rest_server> | emulate (token)  | <n>               | none      | <L?>   |
| Meta    | <rest_server> | replay           | <n>               | none      | <L?>   |
| Hub     | <hub_server>  | emulate          | <n>               | session   | <L?>   |
| Presence| <xmpp_server> | emulate          | <n>               | session   | <L?>   |
| Match   | <—>           | emulate (Stage 2)| <n>               | live sim  | <L?>   |

## Notes per service
- <service>: <what it must do beyond returning a body — heartbeats, IDs, timing>
```

### Current Wall

```markdown
# Current Wall — <Title>
Updated: <YYYY-MM-DD HH:MM>   Operator: <name>

## The wall (one blocker only)
- Wall: <single most upstream unresolved blocker>
- Location in chain: <service #>
- Evidence it is the wall: <log line / status code / capture ref>

## Why everything downstream is on hold
- <what cannot be tested/built until this falls>

## Working hypothesis
- <cause, stated as testable>

## Next bounded experiment
- Ref: <EXP-id>

## Wall history (append on each fall)
| Date | Wall that fell | How confirmed | New wall |
|------|----------------|---------------|----------|
```

### Experiment Proposal

```markdown
# Experiment Proposal — <EXP-id>
Date: <YYYY-MM-DD>   Operator: <name>   Wall ref: <>

## Question
- What single question does this answer? <>

## The one variable
- Changing exactly: <one thing>
- Holding constant: <everything else — list the risky ones>

## Prediction (commit BEFORE running)
- If hypothesis true, we expect: <observable result>
- If false, we expect: <observable result>

## Method
- Steps: <>
- Checkpoint restored from: <checkpoint id>

## Success = which validation level?
- Target: <L0 / L1 / L2 / L3 / L4>

## Risk of this experiment
- Blast radius if it goes wrong: <>
```

### Experiment Result

```markdown
# Experiment Result — <EXP-id>
Run date: <YYYY-MM-DD>   Operator: <name>

## What changed
- One variable: <>

## Predicted vs actual
- Predicted: <>
- Actual: <>
- Match? <yes / no / partial>

## Evidence
- Primary artifact(s): <log ref, capture ref, screenshot ref>
- Evidence tier: <captured / derived / synthetic>

## Validation level achieved
- <L0–L4> — justification: <>

## Verdict
- [ ] Wall fell
- [ ] Wall stands
- [ ] New wall exposed: <>

## Scope check
- Any unrequested changes made? <none / list — investigate as scope creep>
```

### Evidence Register

```markdown
# Evidence Register — <Title>
Maintained by: <name>   Last update: <YYYY-MM-DD>

| ID | Description | Tier | Source | Date | PII redacted? | Location |
|----|-------------|------|--------|------|---------------|----------|
| E1 | <progression tree response> | captured | wire, live | <> | yes | <path/ref> |
| E2 | <match entropy 4.8–5.9 bpb>  | derived  | E-refs     | <> | n/a | <path/ref> |
| E3 | <god profile inventory>      | synthetic| authored   | <> | n/a | <path/ref> |
| E4 | <"traffic is readable">      | asserted | operator   | <> | n/a | pending confirm |

Tier key: captured > derived > synthetic > asserted (trust descends).
Rule: every claim in every report cites an evidence ID and its tier.
```

### Validation Matrix

```markdown
# Validation Matrix — <Title>
Date: <YYYY-MM-DD>

Levels: L0 proof-of-life · L1 happy-path smoke · L2 multi-case correctness
        · L3 sustained stateful correctness · L4 full behavioural equivalence

| Service  | L0 | L1 | L2 | L3 | L4 | Evidence for highest level |
|----------|----|----|----|----|----|----------------------------|
| Identity | ✓  | ✓  | ✓  | ~  |    | <ref>                      |
| Meta     | ✓  | ✓  | ~  |    |    | <ref>                      |
| Hub      | ✓  | ✓  | ✓  | ✓  |    | <ref — stable session>     |
| Presence | ✓  | ✓  | ✓  | ✓  |    | <ref — no resets Xh>       |
| Match    |    |    |    |    |    | Stage 2 — not started      |

Legend: ✓ met (with evidence) · ~ partial · blank not met.
Rule: no ✓ without a cited artifact in the Evidence Register.
```

### Risk Register

```markdown
# Risk Register — <Title>
Owner: <name>   Reviewed: <YYYY-MM-DD>

| ID | Risk | Class | Likelihood | Impact | Owner | Mitigation | Status |
|----|------|-------|-----------|--------|-------|------------|--------|
| R1 | <>   | technical | <L/M/H> | <L/M/H> | <> | <> | open |
| R2 | <>   | authorization | <> | <> | <> | <> | open |
| R3 | <>   | disclosure | <> | <> | <> | <> | open |

Classes: technical | authorization (scope/legal) | disclosure (info release) | commercial.
Rule: any authorization or disclosure risk at Impact=H blocks delivery until mitigated.
```

### Daily Project Update

```markdown
# Daily Update — <Title> — <YYYY-MM-DD>
Operator: <name>

- Current wall: <one line>
- Moved today: <what fell / what progressed, with evidence ref>
- Experiments run: <EXP-ids + verdict>
- Validation change: <service: Lx → Ly>
- Blocked on: <>
- Next: <single next action>
- Scope/authorization/disclosure flags: <none / detail>
```

### Weekly Client Update

```markdown
# Weekly Client Update — <Title> — week of <date>
For: <client>   From: <operator>

## Where we are (plain language)
- <state reached, honestly — proven vs feasible vs unproven>

## Proven this week (with evidence)
- <achievement> — basis: <evidence tier>

## Current wall
- <one blocker, in client language>

## What is NOT yet true
- <explicit list — e.g. no playable matches>

## Decisions we need from you
- <>

## Honest outlook
- Proven: <> | Feasible: <> | Not yet scoped: <>
- No guarantees are made beyond the "Proven" line.
```

### Specialist Handoff

```markdown
# Specialist Handoff — <Title> — <HANDOFF-id>
From: <operator>   To: <specialist / discipline>   Date: <>

## Why this is being escalated
- Trigger: <deep engine internals / crypto / legal judgement / other>
- Why it exceeds operator scope: <>

## The problem, precisely
- <one-paragraph statement>

## What is already known (evidence)
- <captured/derived items + refs>

## What has been tried
- <experiments + results>

## The specific question for the specialist
- <>

## Constraints
- Authorization boundary: <>
- Disclosure boundary: <>
- Self-contained / owned-copy only: yes
```

### Milestone Report

```markdown
# Milestone Report — <Title> — <milestone name>
Date: <YYYY-MM-DD>   Operator: <name>

## Milestone claimed
- <e.g. Stage 1 — stable main menu>

## Definition of done (agreed at intake)
- <criteria>

## Evidence it is met
| Criterion | Evidence ID | Tier | Validation level |
|-----------|-------------|------|------------------|

## Explicitly out of this milestone
- <e.g. playable matches = Stage 2>

## Reproducibility
- Checkpoint: <id>   Bring-up: <one command / steps>

## Sign-off
- Operator: <>   Investigation Lead: <>   Date: <>
```

### Public Case-Study Approval

```markdown
# Public Case-Study Approval — <Title>
Draft ref: <>   Author: <>   Date: <>

## Claim audit
| Claim in draft | Evidence ID | Tier | Safe to state? |
|----------------|-------------|------|----------------|

## Secret / recipe scan (all must be NONE-present)
- [ ] No keys, secrets, or tokens
- [ ] No reusable circumvention / bypass / forgery recipe
- [ ] No anti-cheat-defeat steps
- [ ] Rights-holder / third-party systems: no actionable detail

## Personal data scan
- [ ] No real names, account IDs, or identifiers (synthetic only)

## Scope statement present
- [ ] States owned-copy, self-contained, no distribution
- [ ] States what is NOT achieved (e.g. no playable matches)

## Approvals
- Disclosure reviewer: <>   Founder: <>   Date: <>
- [ ] Approved for publication as-is
```

### Disclosure Review

```markdown
# Disclosure Review — <Title> — <artifact ref>
Reviewer: <name>   Date: <>

## What is being released, and to whom
- Artifact: <report / case study / update>
- Audience: <internal / client / public>

## Category checks
| Category | Present? | Action |
|----------|----------|--------|
| Secrets / keys / tokens | <y/n> | remove |
| Reusable circumvention recipe | <y/n> | remove/abstract |
| Personal / customer data | <y/n> | redact/synthesise |
| Third-party (rights-holder) internals | <y/n> | [AUTHORIZATION REQUIRED] |
| Overclaimed certainty | <y/n> | rephrase to evidence |

## Verdict
- [ ] Cleared  [ ] Cleared with edits  [ ] Blocked
- Notes: <>
```

### Final Recovery-Audit Report

```markdown
# Final Recovery-Audit Report — <Title>
Date: <YYYY-MM-DD>   Operator: <name>   Investigation Lead: <name>

## 1. Objective & authorization
- Goal: <>   Owned-copy basis: <>   Boundaries: <>

## 2. State reached
- Furthest stable, evidence-backed state: <e.g. stable main menu>
- Validation matrix summary: <table ref>

## 3. Method (high level, safe to record)
- Reconnaissance → architecture map → evidence register → current wall
  → bounded experiments → validation → (escalation) → delivery.

## 4. Evidence basis
- Register ref: <>   Highest-tier claims: <>

## 5. Current wall at close
- <the blocker Stage 2 begins from>

## 6. What is explicitly NOT achieved
- <e.g. no playable matches; Stage 2 feasible per entropy, not built>

## 7. Reproducibility
- Checkpoints: <>   Bring-up: <>   Another operator can resume from: <>

## 8. Residual risk & disclosure notes
- <>
```

### Project Closeout

```markdown
# Project Closeout — <Title>
Closed: <YYYY-MM-DD>   Operator: <name>

## Outcome vs intake goal
- Agreed goal: <>   Delivered: <>   Honest gap: <>

## Deliverables handed over
- [ ] Final recovery-audit report
- [ ] Evidence register (redacted)
- [ ] Validation matrix
- [ ] Reproducible checkpoints + bring-up
- [ ] Risk register (residual)

## Client decisions recorded
- <continue to Stage 2 / stop / hand to another team>

## Disclosure status
- Public artifacts approved? <>   Reviewer: <>

## Lessons for the method
- <what to carry forward>

## Sign-off
- Operator: <>   Investigation Lead: <>   Client: <>
```

---

## MODULE 17 — Glossary

Each entry gives a **Technical definition**, an **Operator definition** (plain language for a systems-minded non-coder), and **Why it matters**. Entries for tokens, JWTs, and identity providers are deliberately conceptual — they describe what these things are and why they gate a recovery, never how to forge, sign, or validate them.

### Authentication
**Technical definition:** The process by which a party proves it is who it claims to be, typically by presenting a credential a verifier can check.
**Operator definition:** The "who are you?" gate — the game proving its identity before it is let in.
**Why it matters:** It is the first wall in almost every service chain; nothing downstream runs until authentication resolves, so it is where recovery investigations start.

### Authorization
**Technical definition:** The process of deciding what an already-authenticated party is permitted to do or access.
**Operator definition:** Once the system knows who you are, authorization decides what you're allowed to touch.
**Why it matters:** Authentication and authorization are distinct; conflating "logged in" with "allowed" causes both technical bugs and scope mistakes — and the operator's *authorization boundary* is the same idea applied to the engagement itself.

### Token
**Technical definition:** A compact, verifier-checkable artifact issued after authentication that a client carries to assert identity or permissions on subsequent requests.
**Operator definition:** A digital ID card the game is handed at login and shows at every later desk.
**Why it matters:** In a self-contained recovery, the client only carries tokens between services and never checks them itself — which is exactly why the whole chain hinges on who issues them. (Conceptual only; this manual never describes forging or signing.)

### JWT
**Technical definition:** JSON Web Token — a token format carrying claims as a structured, verifier-checkable object in three parts.
**Operator definition:** A common shape of ID card: some readable fields plus a seal that only the issuer's side is meant to check.
**Why it matters:** Recognising a JWT tells you the client is a courier, not an inspector — it delivers the card without opening it. Understanding *that role* is the point; the manual gives no signing or validation recipe.

### Identity Provider
**Technical definition:** A service that authenticates principals and issues identity assertions/tokens other services rely on.
**Operator definition:** The office that checks who you are and issues the ID card everyone else trusts.
**Why it matters:** It is the anchor of the service chain; in preservation work it is the first service you must stand in for, and mapping it correctly determines whether anything else can be reached.

### REST
**Technical definition:** An architectural style for networked APIs using stateless HTTP requests against resource-oriented endpoints.
**Operator definition:** A common way services expose "ask for this thing, get this thing back" over the web.
**Why it matters:** Meta-layer services (profile, inventory, progression) are typically REST — one-shot, stateless calls that are the easiest tier to replay from captured evidence.

### HTTP
**Technical definition:** The request/response application protocol underlying most web APIs, carrying methods, headers, status codes, and bodies.
**Operator definition:** The everyday language of "send a request, get a numbered reply" between the game and a server.
**Why it matters:** Status codes (200, 401) are primary evidence — a 401 at the identity wall tells you exactly where the chain broke, more reliably than any agent's summary.

### WebSocket
**Technical definition:** A protocol providing a persistent, full-duplex message channel over a single TCP connection after an HTTP upgrade handshake.
**Operator definition:** An open phone line that stays connected so both sides can talk any time, not just request-and-hang-up.
**Why it matters:** The hub/menu switchboard uses it; because it is persistent and live, it cannot be handled by pure replay — it needs behavioural emulation, including keeping the line open.

### XMPP
**Technical definition:** An XML-based messaging and presence protocol using persistent streams and addressable identities (JIDs).
**Operator definition:** The chat-and-"who's online" protocol behind the friends list.
**Why it matters:** Presence faults are often identity faults — the WW3 stability loop came from binding the wrong JID — so knowing XMPP ties identity to liveness is a diagnostic shortcut.

### UDP
**Technical definition:** A connectionless transport protocol offering low-latency, unordered, unreliable datagram delivery.
**Operator definition:** Fire-and-forget packets — fast, no guaranteed order or delivery — used where speed beats reliability.
**Why it matters:** Match/gameplay traffic runs over UDP; recognising the transport shapes how you capture and analyse Stage 2 traffic (per-packet, sequence-numbered) versus the request/response menu tiers.

### Client
**Technical definition:** The program that initiates requests to services — here, the game executable.
**Operator definition:** The game itself, the thing on your PC that does the calling.
**Why it matters:** In recovery you never modify the client's behaviour by rewriting it; you change what it *hears*. Keeping the client as the fixed reference is what makes results honest.

### Backend
**Technical definition:** The server-side collection of services a client depends on to function.
**Operator definition:** All the offices the game phones — the whole set you may have to stand in for.
**Why it matters:** The recovery job is fundamentally "replace the backend the client expects" — mapping it fully is the difference between a plan and a guess.

### Service
**Technical definition:** A discrete, independently addressable unit of backend functionality with a defined interface.
**Operator definition:** One specific office with one job — login, or profile, or chat.
**Why it matters:** The service chain is your unit of work; you clear it one service at a time, most upstream first, validating each before moving on.

### Endpoint
**Technical definition:** A specific addressable operation on a service (a URL/path + method, or a message type).
**Operator definition:** One exact thing you can ask a service to do.
**Why it matters:** Endpoints are the granularity of capture and coverage — the evidence register and service inventory are counted in endpoints answered.

### Request
**Technical definition:** A message a client sends to invoke an endpoint, carrying method, headers, and optionally a body.
**Operator definition:** The game asking for something.
**Why it matters:** Requests are half of the captured "script"; you cannot answer correctly until you have recorded exactly what was asked.

### Response
**Technical definition:** The message a service returns to a request, carrying a status and optionally a body.
**Operator definition:** The server's answer.
**Why it matters:** Captured responses are the highest-trust material you replay; their fidelity is what lets a stand-in fool the client.

### State
**Technical definition:** Information a service retains across requests within a session or over time.
**Operator definition:** What the server remembers between one call and the next.
**Why it matters:** Stateless services can be replayed; stateful ones (a live session, a heartbeat, an identity binding) demand emulation — telling the two apart sets your validation ceiling.

### Session
**Technical definition:** A bounded, stateful interaction context between client and service, usually established after authentication.
**Operator definition:** One continuous "logged-in" stretch the server keeps track of.
**Why it matters:** Sustained session correctness is validation level L3 — holding a session stable (no pop-ups, no resets) is a real milestone distinct from a one-shot success.

### Heartbeat
**Technical definition:** A periodic keep-alive message confirming a connection or peer is still live.
**Operator definition:** A regular "still here" tap that stops the other side from hanging up.
**Why it matters:** A stand-in that answers pings but never sends its own gets timed out — the WW3 hub needed a server-initiated heartbeat every ~4 s. Liveness is behaviour, not content.

### Profile
**Technical definition:** The server-held record of a user's account state — identity, progression, inventory, settings.
**Operator definition:** Your filing cabinet on the server: level, unlocks, loadouts.
**Why it matters:** Once the profile comes from your stand-in, its contents are authored (synthetic) evidence — powerful, but the lowest trust tier, and to be labelled as such.

### Progression
**Technical definition:** The structured data describing unlock trees, ranks, and advancement.
**Operator definition:** The map of what you've unlocked and what's left.
**Why it matters:** It is large, static, and one-shot — an ideal replay target — and it defines the item universe the synthetic profile draws from.

### Inventory
**Technical definition:** The set of items, currencies, and entitlements a profile owns.
**Operator definition:** Everything the game thinks you have.
**Why it matters:** It is a clear example of synthetic evidence in action — the stand-in can assert full ownership — and a clear example of why synthetic claims must be flagged, not passed off as captured.

### Matchmaking
**Technical definition:** The service that groups players and assigns them to a match instance.
**Operator definition:** The system that decides which game you drop into and with whom.
**Why it matters:** It sits between the menu (Stage 1) and the battlefield (Stage 2); recognising it as its own service prevents scoping Stage 2 as one monolith.

### Lobby
**Technical definition:** A pre-match staging context where players gather and configure before a match starts.
**Operator definition:** The waiting room before the game begins.
**Why it matters:** It is a stateful, hub-driven feature — useful for reasoning about where menu emulation ends and match emulation begins.

### Match Server
**Technical definition:** The authoritative server instance simulating live gameplay for connected clients.
**Operator definition:** The actual battlefield — a live simulation, not a set of recordings.
**Why it matters:** It is Stage 2 and cannot be replayed; it is the clearest case in the manual of a specialist-grade, emulation-only build gated behind a feasibility finding.

### Mock
**Technical definition:** A substitute implementation that returns predetermined responses in place of a real dependency.
**Operator definition:** A fake server that answers just like the real one.
**Why it matters:** Mocks are the core tool of Stage 1; the discipline is that a mock's answers are only as trustworthy as the evidence tier behind them.

### Stand-in Service
**Technical definition:** A running mock deployed in the real service's network position to satisfy a live client.
**Operator definition:** A fake office that actually picks up the phone when the game calls.
**Why it matters:** "Stand-in" stresses that it must occupy the real address and behave live — not just return data, but hold connections, heartbeats, and identity correctly.

### Replay
**Technical definition:** Serving previously captured responses verbatim in response to matching requests.
**Operator definition:** Playing back the exact recording of what the real server said.
**Why it matters:** It is the lowest-effort, highest-fidelity technique for static services and the first rung of the maturity ladder — but it cannot handle anything live or stateful.

### Behavioral Emulation
**Technical definition:** Generating fresh, correct responses at runtime from a model of a service's behaviour rather than replaying recordings.
**Operator definition:** Actually understanding what the office does, so you can answer new questions it hasn't been asked before.
**Why it matters:** It is required wherever state, timing, or identity is involved (heartbeats, sessions, tokens, match sim) and is the upper, harder rungs of the ladder.

### Source-less Recovery
**Technical definition:** Reconstructing a system's required behaviour without access to its original source code, working from observed behaviour and artifacts.
**Operator definition:** Rebuilding what a server must do when you have none of its original blueprints — only what you can watch it do.
**Why it matters:** It is the defining condition of this work; it forces the evidence discipline — you can only claim what you can observe or measure.

### Static Recompilation
**Technical definition:** Translating a compiled binary into a new form (e.g. re-targeted or re-buildable code) without the original source.
**Operator definition:** Turning a finished program back into something you can rebuild, without the recipe it was baked from.
**Why it matters:** It is a specialist-grade technique referenced as an escalation path; recognising when a problem needs it — versus behavioural emulation — is an escalation judgement, not an operator task.

### Packet Capture
**Technical definition:** Recording network traffic at the datagram/frame level for later analysis.
**Operator definition:** Wiretapping the wire to keep an exact copy of everything sent.
**Why it matters:** It produces the captured evidence at the foundation of the register; capturing *while servers are live* is a one-time, non-repeatable opportunity before shutdown.

### Protocol
**Technical definition:** The agreed rules governing message format, ordering, and exchange between parties.
**Operator definition:** The agreed language and etiquette two programs use to talk.
**Why it matters:** Standing in for a service means speaking its protocol exactly — format *and* etiquette (order, timing, handshake), which is why body-correct-but-still-broken faults exist.

### Encryption
**Technical definition:** Transforming data so it is unreadable without a key, hiding its content on the wire.
**Operator definition:** Scrambling traffic so anyone listening sees only noise.
**Why it matters:** Strong encryption on gameplay would make source-less recovery from captures near-impossible — measuring for it is the go/no-go gate for Stage 2.

### Compression
**Technical definition:** Encoding data more compactly by removing redundancy, reversible with the matching algorithm.
**Operator definition:** Squeezing data smaller before sending it.
**Why it matters:** Compressed traffic reads as moderately high entropy (~7.5) and, like encryption, complicates analysis — distinguishing compressed from encrypted from plain is what the entropy measurement is for.

### Entropy
**Technical definition:** A measure of information randomness, in bits per byte, of a data stream.
**Operator definition:** A randomness score: high means scrambled/encrypted, low means readable structure.
**Why it matters:** It is the single measurement that classified WW3 match traffic as readable (4.8–5.9, versus ~8.0 encrypted) — a derived-evidence feasibility verdict, not a guess.

### Unreal Engine Netcode
**Technical definition:** The replication and networking subsystem of Unreal Engine governing how game state is synchronised between server and clients.
**Operator definition:** The engine's built-in system for keeping everyone's battlefield in sync.
**Why it matters:** WW3 uses stock UE4.21 netcode, and the engine's reference is public — so Stage 2 can read the format rather than reverse it blind, which is what makes it feasible-but-large.

### UNetConnection
**Technical definition:** Unreal Engine's per-client network connection object managing channels, packets, and replication for one peer.
**Operator definition:** The engine's core "one player's connection" — what a match server must speak to.
**Why it matters:** Emulating it is the heart of Stage 2 and a clear escalation trigger — reconstructing its channel and handshake semantics is specialist-grade engine work.

### Regression
**Technical definition:** A previously working behaviour that breaks after a change.
**Operator definition:** Something that used to work and now doesn't because of what you just did.
**Why it matters:** Bounded, one-variable experiments and checkpoints exist precisely to make regressions visible and attributable — a change that fixes one wall must not silently reopen another.

### Reproducibility
**Technical definition:** The property that a result can be obtained again from the same inputs and steps.
**Operator definition:** Being able to get the same result on purpose, not by luck.
**Why it matters:** It is the standard the final assignment is judged by — a lucky menu that can't be reproduced is worth less than a documented, repeatable stop earlier in the chain.

### Smoke Test
**Technical definition:** A quick check that a system's basic, critical paths function before deeper testing.
**Operator definition:** A fast "does it even start and do the obvious thing?" check.
**Why it matters:** It maps to validation level L1 — the single happy-path pass that confirms wiring works but claims nothing about correctness under varied input.

### Current Wall
**Technical definition:** The single most upstream unresolved blocker preventing forward progress at a given moment.
**Operator definition:** The one thing, furthest up the chain, stopping everything after it.
**Why it matters:** Naming exactly one wall focuses effort where it unblocks the most and is the honesty test of a status report — a project that can't name its wall isn't being run.

### Checkpoint
**Technical definition:** A recorded, restorable system state from which work can resume deterministically.
**Operator definition:** A save point you can always return to and build forward from.
**Why it matters:** Checkpoints make progress durable and experiments safe — you can change one variable knowing you can restore the known-good state.

### Proof of Life
**Technical definition:** The minimal evidence that a component is reachable and responds, independent of correctness.
**Operator definition:** A sign the thing is switched on and answering, even if the answer isn't right yet.
**Why it matters:** It is validation level L0 — the first, smallest honest claim you can make, and the one most often overstated by an over-eager agent.

### Rights Holder
**Technical definition:** The party holding legal ownership of the intellectual property in the software and its services.
**Operator definition:** Whoever legally owns the game and its servers.
**Why it matters:** Their systems and internals are off-limits without authorization; the authorization boundary and the "no action against third-party systems" rule exist to respect them.

### Authorization Boundary
**Technical definition:** The defined limit of what an engagement is permitted to do, set by ownership, law, and client agreement.
**Operator definition:** The line around what you're actually allowed to do — here, a single owned copy, offline, no distribution.
**Why it matters:** Capability never expands it; the operator's job is to stay inside it even when something more is technically possible, and to record it before any work begins.

### Disclosure Boundary
**Technical definition:** The defined limit of what information may leave an engagement, to whom, and in what form.
**Operator definition:** The line around what you're allowed to say or publish — secrets, recipes, and personal data stay in.
**Why it matters:** It governs every report and case study; a method may be shared while its secrets, circumvention recipes, and customer data are redacted — and a disclosure review is how that line is enforced.

---

## The RecompileLabs Operating System

The whole method, in twelve moves. Each is one thing the operator does, in order, every engagement. Skipping one doesn't speed you up — it just moves the failure later, where it costs more.

**01 INTAKE.** Capture what the client actually owns, what they actually want, and what "done" means in their words. The operator's job is to write it down precisely, separate the stated goal from the assumed one, and record the owned-copy basis. Nothing technical starts until intake is on paper.

**02 AUTHORIZATION.** Fix the authorization and disclosure boundaries before touching anything. The operator's job is to establish that the work is a single owned copy for personal offline use, no distribution, no action against third-party systems — and to record it as the fence that capability may never push past.

**03 RECONNAISSANCE.** Observe the live (or captured) system as it really behaves. The operator's job is to capture traffic while it can still be captured, redact personal data at source, and gather evidence rather than assumptions — because after shutdown this opportunity is gone for good.

**04 ARCHITECTURE MAP.** Turn observations into the service chain: who calls whom, in what order, over what transport. The operator's job is to draw it from evidence, mark every assumption as unconfirmed, and identify the ordering constraints that dictate what must be built first.

**05 EVIDENCE REGISTER.** Tier every fact as captured, derived, synthetic, or asserted, dated and located. The operator's job is to make trust legible — every later claim points back to an evidence ID and its tier, and asserted items are flagged as debts to confirm.

**06 CURRENT WALL.** Name the single most upstream unresolved blocker. The operator's job is to resist working behind the wall, restate the wall each time one falls, and treat "we can't name our wall" as a sign the project isn't under control.

**07 BOUNDED EXPERIMENT.** Change exactly one variable against a prediction committed in advance. The operator's job is to keep the blast radius small, catch agent scope creep, and hold every other variable still so the result is attributable to the one thing that changed.

**08 VALIDATION.** Score the result honestly against L0–L4, with cited evidence. The operator's job is to trust the log over the summary, refuse a ✓ without an artifact behind it, and never let a happy-path smoke test masquerade as behavioural equivalence.

**09 SPECIALIST ESCALATION.** Recognise when a problem needs a discipline you don't own — deep engine internals, static recompilation, cryptographic or legal judgement. The operator's job is to hand off cleanly with a precise brief and evidence, not to press on and guess past the edge of competence.

**10 CLIENT DECISION.** Bring the client honest choices, separating proven from feasible from unscoped. The operator's job is to communicate state without selling certainty the evidence doesn't support, and to record the decision the client makes.

**11 DELIVERY.** Ship the reproducible result: checkpoints, bring-up, and the final recovery-audit report. The operator's job is to make the achieved state reproducible by someone else and to state plainly what is *not* achieved, so the deliverable is honest as well as working.

**12 HANDOVER.** Close out so the next operator — or the client's next stage — can resume cold. The operator's job is to leave the evidence register, validation matrix, current wall, and residual risks in a state another person can pick up without this conversation, and to route every public artifact through disclosure review.

> Do not sell certainty before the evidence exists. Sell disciplined investigation, visible proof and accountable decisions.
