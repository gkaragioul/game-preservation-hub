## MODULE 7 — AI AGENT CONTROL: "THE AGENT WORKS FOR THE INVESTIGATION"

An AI coding agent is a fast, tireless, and confidently wrong junior contractor. It will produce plausible code, plausible explanations, and plausible success reports at a speed no human can match. That speed is exactly why it is dangerous inside a preservation investigation, where the whole enterprise depends on knowing precisely which claim is *evidenced* and which is *guessed*. An unsupervised agent erases that distinction faster than you can rebuild it.

This module teaches you to run the agent, rather than letting the agent run you. The governing principle is simple and non-negotiable: **the agent works for the investigation; the investigation does not work for the agent.** Every rule below exists to keep the agent inside a bounded, reversible, evidence-first loop.

### 7.1 The control doctrine

**SYSTEM VIEW.** Treat the agent as an untrusted worker executing inside a change-controlled environment. It may read, analyze, and propose freely. It may *modify state* only through a gated protocol: declared file list → declared expected result → declared rollback → approval → single bounded change → single agreed test → stop. Scope is a contract, not a suggestion. Every write is preceded by a checkpoint and followed by a comparison against last-known-good. The agent's narrative output is treated as a hypothesis stream, never as a system-of-record; the system-of-record is your evidence register and your own reproduction.

**OPERATOR VIEW.** Imagine hiring a very fast handyman who sometimes fixes the wrong pipe, sometimes tells you he fixed it when he only looked at it, and occasionally re-plumbs the whole house because he "was in there anyway." You would not hand him the keys and leave. You would say: "Show me the leak first. Tell me exactly which pipe you'll touch. Tell me how to undo it. Do that one thing. Then stop and show me." That is the entire method. You are not being difficult — you are keeping the house standing.

### 7.2 The twelve control rules

Each rule is stated as a directive to you, the operator, with the reason it exists.

| # | Rule | Why it exists |
|---|------|--------------|
| 1 | **Never instruct the agent to "fix everything."** Bound every task to one wall, one hypothesis, one experiment. | "Fix everything" is an open licence to change unbounded state. You lose the ability to attribute cause. |
| 2 | **Never accept a root-cause statement without evidence.** Demand the exact log line, file path, and timestamp. | Agents pattern-match to *likely* causes. Likely is not confirmed. |
| 3 | **Never allow unrelated redesign during a bounded experiment.** | A refactor smuggled into a diagnosis destroys the experiment's validity and your rollback. |
| 4 | **Require a file list before any modification.** | If you don't know what will change, you cannot review, checkpoint, or roll back. |
| 5 | **Require a rollback plan before approval.** | An irreversible change is a bet you cannot unwind. Reversibility is the price of admission. |
| 6 | **Require the expected result, stated before the change.** | A prediction made *before* the test is falsifiable. A rationalization made *after* is not. |
| 7 | **Require a single agreed smoke test.** | One defined pass/fail signal prevents the agent from redefining success mid-run. |
| 8 | **Require the agent to STOP after the test.** | Momentum is the enemy. Stopping returns judgement to you before the next change compounds. |
| 9 | **Require project-state updates.** The wall record, experiment log, and evidence register must be updated. | An undocumented result is a lost result. Tomorrow's you and every specialist depend on it. |
| 10 | **Require explicit uncertainty.** The agent must label confidence and name what it does not know. | Hidden uncertainty is how a guess becomes a "fact" three steps later. |
| 11 | **Require separation of observed evidence vs interpretation.** | Evidence is durable; interpretation is disposable. Mixing them poisons the record. |
| 12 | **Do not let the agent silently change scope.** Any scope change is a new, explicit decision by you. | Silent scope creep is the single most common way investigations lose their footing. |

> **⚠ STOP CONDITION**
> If the agent begins editing files you did not list, touches components outside the approved experiment, or reports success without having run the agreed smoke test — halt immediately. Roll back to the last known-good checkpoint. Do not "let it finish." A run that has already broken the contract cannot be trusted to end well.

### 7.3 Worked example — the WW3 presence disconnection

During Stage 1 stability work, the menu was reachable but a "lost connection with the communication service" pop-up kept returning. The wrong way to hand this to an agent: *"The connection keeps dropping, please fix the presence system."* That invites a rewrite of three background channels at once, with no way to tell which change mattered.

The controlled way:

- [ ] **Bound it.** "Identify the earliest confirmed cause of the presence stream tearing down. Do not modify files."
- [ ] **Demand evidence.** The agent returns the exact observation: the presence bind returned a stale player identifier `[SANITIZED-OLD-ID]` while the client identified itself as `[SANITIZED-CURRENT-ID]`, and the stream was torn down on a fixed interval.
- [ ] **One hypothesis, one experiment.** "Test whether echoing the client's own declared identity, rather than the stale one, holds the stream open. List the one file. State expected result. State rollback."
- [ ] **Approve, run, stop.** Single change; single smoke test (launch, sit at menu, watch for the pop-up across the known failure interval); record result; stop.

The actual fix combined a corrected bound identity with a server-initiated heartbeat, but each was isolated, predicted, tested, and logged *separately*. That is the difference between "the pop-up went away" and "we know exactly why the pop-up went away, and we can prove it repeats."

### 7.4 The five control prompts

These are copy-ready. Use them verbatim. They encode the doctrine so you do not have to re-argue it every session.

```
PROMPT 1 — ANALYZE WITHOUT PATCHING

Do not modify any files. Identify the earliest confirmed failure preventing
the current milestone. Separate your response into: 1. Direct evidence
2. Inference 3. Unverified hypotheses 4. Missing evidence 5. Smallest
experiment capable of disproving the leading hypothesis. Quote the exact log
lines, file paths and timestamps supporting your conclusion. Do not redesign
unrelated systems.
```

```
PROMPT 2 — PROPOSE A BOUNDED EXPERIMENT

Propose one bounded experiment only. State: the current wall; the hypothesis
being tested; files that would change; expected result; failure
interpretation; rollback procedure; smoke-test command; risks; conditions
under which we must stop. Do not implement anything yet.
```

```
PROMPT 3 — IMPLEMENT THE APPROVED EXPERIMENT

Implement only the approved bounded experiment. Before changing anything:
create or identify a checkpoint; list the exact files; confirm the expected
result; confirm the rollback procedure. After implementation: run only the
agreed smoke test; compare with the last known working state; record the
exact result; identify any regression; update the wall record; stop.
```

```
PROMPT 4 — CHALLENGE YOUR OWN CONCLUSION

Attempt to disprove your current conclusion. List: alternative explanations;
evidence that contradicts the preferred hypothesis; accidental environmental
factors; caching or stale-session risks; one test that would expose a false
positive.
```

```
PROMPT 5 — HANDOFF TO A SPECIALIST

Prepare a specialist handoff. Include: objective; current milestone;
confirmed architecture; current wall; evidence; failed approaches;
reproduction steps; relevant files; logs; risks; specific question for the
specialist; definition of done.
```

**How the five prompts chain.** Prompt 1 forces analysis without state change. Prompt 2 converts the leading hypothesis into a single reversible experiment. Prompt 3 executes exactly that experiment and stops. Prompt 4 is your defence against a false positive — run it *before* you believe a success. Prompt 5 is the exit ramp when the problem exceeds what the agent should attempt (see Module 10). You will often loop 1→2→3→4 several times before either resolving the wall or escalating via 5.

### 7.5 Agent failure modes

Learn to recognize these on sight. Each is a specific way an agent quietly corrupts an investigation.

| Failure mode | What it looks like | Countermeasure |
|--------------|--------------------|----------------|
| **Confident fabrication** | Detailed, plausible claims with no source; invented function names or log text. | Demand the exact quote, path, timestamp. If it can't be quoted, it didn't happen. |
| **Fixing the wrong layer** | Patching a symptom two layers above the real cause. | Require the *earliest* confirmed failure, not the most visible one. |
| **Broad refactors** | "While I was in there, I cleaned up…" | Rule 3. Reject any diff beyond the approved file list. |
| **Hiding uncertainty** | Assertive prose that conceals a guess. | Rule 10. Require explicit confidence labels and an "unknowns" list. |
| **Citing files that don't exist** | References to paths that were never in the repo. | Verify every cited path yourself before acting on it. |
| **Claiming success from exit codes alone** | "Build passed, so it works." | Exit code 0 means it compiled/ran, not that the milestone was met. Require runtime evidence. |
| **Skipping runtime validation** | No launch, no observed behavior — only static reasoning. | The agreed smoke test is mandatory. No test, no success. |
| **Introducing regressions** | The target improves; something previously working breaks. | Always compare against last-known-good, not just against the failure. |
| **Changing multiple variables** | Several edits in one run, so cause is unattributable. | One variable per experiment. Full stop. |
| **Rewriting working components** | Replacing a stable module "for consistency." | Working code is evidence. Do not disturb it inside an experiment. |
| **Using stale evidence** | Reasoning from an old log or a previous machine state. | Timestamp all evidence; re-capture if in doubt. |
| **Treating cached sessions as successful offline operation** | A "success" that actually rode a cached credential or a warm session. | Validate from a clean state (Module 8, Level D). A cached pass is not an offline pass. |

> **⚠ WARNING**
> The last failure mode is the one that will fool *you*, not just the agent. In a backend-replacement effort, a launch that "worked offline" may in fact have succeeded because a token or session from an earlier online run was still cached. You have proven nothing about forever-offline operation until you have cleared every cache and reproduced from cold. Treat any offline success that has not survived a clean-state reproduction as unconfirmed.

### 7.6 Agent-review checklist

Run this against every agent deliverable before you accept it.

- [ ] Every root-cause claim is backed by a quoted log line, file path, and timestamp
- [ ] Direct evidence is clearly separated from inference and from hypothesis
- [ ] Uncertainty and unknowns are stated explicitly, with confidence levels
- [ ] The change touched only the approved file list — no unrelated edits
- [ ] Scope was not silently expanded; any scope change was an explicit, approved decision
- [ ] A checkpoint existed before the change and a rollback procedure was confirmed
- [ ] The expected result was stated *before* the change was made
- [ ] Only the single agreed smoke test was run, and its exact result was recorded
- [ ] Success rests on runtime evidence, not on an exit code alone
- [ ] The result was compared against last-known-good; no regression was introduced
- [ ] All cited file paths were verified to exist
- [ ] Cached-session / stale-evidence risk was considered and ruled out
- [ ] The wall record, experiment log, and evidence register were updated
- [ ] The agent stopped after the test rather than continuing into new changes

---

## MODULE 8 — VALIDATION: "A MILESTONE IS NOT REAL UNTIL IT REPEATS"

The most expensive mistake in a preservation project is believing a milestone was reached when it was only *witnessed once*. A single success can be an accident of state — a warm cache, a lucky ordering, a leftover session, an environment variable set three days ago and forgotten. Validation is the discipline of promoting a witnessed event into a *known property of the system*. The rule is blunt: **a milestone is not real until it repeats.**

### 8.1 The five validation levels

Every claimed result sits at one of these levels. State the level explicitly whenever you record a result. Higher is stronger; each level subsumes the ones below it.

| Level | Name | Meaning | What it proves |
|-------|------|---------|----------------|
| **A** | **Visual indication** | You saw it happen once — a screenshot, a glimpse of the menu. | Something worked, once, under unknown conditions. |
| **B** | **Single reproduction** | You deliberately reproduced it once, following a known procedure. | It is not pure chance; a procedure exists. |
| **C** | **Repeatable reproduction** | It reproduces reliably across multiple attempts in the same session. | It is stable within a warm environment. |
| **D** | **Clean-state reproduction** | It reproduces from a cold start — process restarted, machine rebooted, caches and stale sessions cleared. | It does not secretly depend on leftover state. |
| **E** | **Handoff reproduction** | Someone else, or a fresh environment, reproduces it from your written procedure alone. | The result belongs to the *documentation*, not to you or your machine. |

> **⚠ WARNING**
> A successful screenshot is **evidence, not validation**. Level A is where investigations fool themselves. The menu appeared — but did it appear because your backend replacement works, or because a cached credential from a previous online launch was still valid? You cannot tell from the screenshot. Level A is a prompt to keep going, never a place to stop.

### 8.2 Why clean-state is the real bar for offline preservation

**SYSTEM VIEW.** For a project whose entire thesis is "runs forever with no live backend," the load-bearing level is **D**. Levels A–C can all be satisfied while the system still quietly depends on a cached token, a warm socket, an environment carried over from an online session, or a hosts-file entry you forgot you set. Only a clean-state reproduction — caches cleared, sessions invalidated, process and machine cold — exercises the claim you are actually making. Level E then proves the claim survives leaving your head and your hardware.

**OPERATOR VIEW.** It is the difference between "my car started this morning" and "my car will start on a cold morning, with a fresh battery, when someone else turns the key using my written instructions." The first is a happy coincidence. The second is a car you can rely on and hand to someone else. For a game you intend to preserve *forever*, only the second kind of proof is worth anything.

### 8.3 Case study — the WW3 stability work

**SYSTEM VIEW.** After the menu was first reached, the "lost connection" pop-up recurred on a fixed interval. The initial "menu reached" claim was effectively Level A — witnessed, but not durable. Hardening moved it up the ladder: the presence stream was held open by correcting a stale bound identity and echoing the client's declared identity; the hub channel was kept alive with a server-initiated heartbeat on a fixed cadence; the Epic presence socket was held with a completed handshake instead of a mis-answered request. Each fix was then re-validated: it had to hold across the *entire* known failure interval (Level C), then across a full process restart and machine reboot (Level D), before "stable menu" was recorded as real.

**OPERATOR VIEW.** The first time the menu loaded, it looked like victory — but a nagging pop-up kept returning like a smoke alarm chirping every few minutes. The team didn't declare success when the menu *appeared*; they declared it when the menu could sit there quietly, untouched, through restarts and reboots, with no alarm. That is the moment "we reached the menu" became "we have a stable menu."

### 8.4 Validation checklist — "main menu reached"

Do not record the milestone as real until every box is checked. Note the highest validation level you have actually achieved next to the claim.

- [ ] The game launches from the intended build (the private preserved copy, not an incidental install)
- [ ] All intended local stand-in services are running before launch
- [ ] There is no accidental dependency on the live publisher backend (verified, not assumed)
- [ ] Name-routing / hosts behavior directs the intended addresses to the local environment
- [ ] The required profile state loads (identity, progression, inventory as intended)
- [ ] The menu is stable — it stays reachable and interactive, not just momentarily visible
- [ ] All background services (hub, presence, identity) are connected and holding
- [ ] No recurring fatal dialog or disconnection pop-up appears across the known failure interval
- [ ] The logs match the intended architecture — every external call is answered locally, none escape
- [ ] Success repeats after a full process restart (services and game cold-started)
- [ ] Success repeats after a full machine reboot
- [ ] Cached credentials and stale sessions are accounted for and cleared — the pass is not riding leftover state
- [ ] The startup procedure is documented well enough to repeat without memory
- [ ] The shutdown procedure is documented
- [ ] The rollback procedure to last-known-good is documented
- [ ] All sensitive material in captured logs and screenshots is redacted before the evidence is filed

### 8.5 Exercise

**Question.** An operator sends you a screenshot of the fully-loaded WW3 menu with the caption "Stage 1 done — offline works." What validation level is this, and what four questions do you ask before you accept the claim?

**Model answer.** This is **Level A (visual indication)** only. The four questions:
1. Was the machine cleanly started, or could a cached token/session from a prior online launch have carried the login? (Tests for Level D.)
2. Does it reproduce if you restart every service and the game right now? (Tests A→C.)
3. Do the logs show *every* identity/profile/hub/presence call answered locally, with none reaching the live backend? (Tests the actual offline claim, not just the visual.)
4. Can I reproduce it on a different machine from your written startup steps alone? (Tests for Level E.) Until at least Level D is met, "offline works" is unproven — the screenshot is evidence that something worked once, not that the system is offline-durable.

---

## MODULE 9 — REPRODUCIBILITY AND PROJECT STATE

An investigation that lives only in your head is worth nothing the moment you step away from it — and it is unsellable, because a client is buying a *documented capability*, not a story about one. This module defines the minimum set of durable records that make a preservation project reproducible, auditable, and handoff-ready. The goal is that any competent person, or any specialist you engage, can pick up the project cold and know exactly what is true, what is unknown, and what to do next.

### 9.1 The required records

**SYSTEM VIEW.** These records form the project's system-of-record. They are updated as a *side effect of every experiment*, not written up at the end. If a result is not in the records, it does not exist.

**OPERATOR VIEW.** Think of it as the flight recorder and the logbook of the project. When something works, you write down exactly how, so you can do it again. When something fails, you write down why, so nobody wastes a week rediscovering it. When a stranger has to take over, they read the logbook, not your mind.

| Record | Purpose |
|--------|---------|
| **Source-of-truth status file** | The single authoritative statement of where the project stands right now — current milestone, validation level, what is proven. Everything else supports this. |
| **Current wall** | The precise, evidenced description of the *one* thing currently blocking the next milestone. Prevents the project from drifting between vague problems. |
| **Architecture map** | The confirmed service chain and how components relate — what calls what, in what order. The shared mental model everyone works from. |
| **Endpoint / service inventory** | Every service and endpoint the client contacts, its role, and whether it is captured, stubbed, or outstanding. The coverage ledger. |
| **Experiment log** | A dated, append-only record of every bounded experiment: hypothesis, change, expected vs actual result, outcome. The project's memory. |
| **Known-good checkpoint** | A pointer to the last state that reproducibly worked, so any experiment can be rolled back to solid ground. |
| **Change log** | What changed, when, and why — distinct from experiments; captures configuration and environment changes too. |
| **Test procedure** | The exact steps to bring the system up and run the agreed smoke tests. Turns validation from memory into a script. |
| **Unresolved risk register** | Every known risk — technical, legal, security, scope — with status and owner. Nothing important is allowed to be merely "known in someone's head." |
| **Credential / secret handling record** | How keys, tokens, certificates, and personal identifiers are stored, redacted, and kept out of the evidence and disclosure paths. |
| **Public-disclosure boundary** | The explicit line between what may be published and what must stay internal (see Module 12). Prevents accidental over-disclosure. |
| **Specialist handoff pack** | A ready-to-send bundle for escalation (see Module 10) — objective, architecture, wall, evidence, question, definition of done. |
| **Client-facing status summary** | A plain-language, appropriately-redacted statement of progress for the client, derived from the source-of-truth file. |

### 9.2 Recommended directory layout

```
project-root/
├── docs/
│   ├── architecture.md        # confirmed service chain & component map
│   ├── current_wall.md         # the single current blocker, with evidence
│   ├── service_inventory.md    # every endpoint/service + coverage status
│   ├── evidence_register.md     # index of captured evidence, timestamped
│   ├── experiment_log.md        # append-only log of bounded experiments
│   ├── validation_matrix.md     # each milestone × validation level (A–E)
│   ├── risk_register.md         # technical/legal/security/scope risks
│   ├── public_disclosure.md     # what may be published vs kept internal
│   ├── specialist_handoff.md    # ready-to-send escalation pack
│   └── client_status.md         # plain-language client-facing summary
├── evidence/
│   ├── logs/                    # captured & runtime logs (redacted)
│   ├── screenshots/             # visual evidence (redacted)
│   ├── videos/                  # recorded sessions
│   ├── captures/                # protocol/packet captures (sanitized)
│   └── diagrams/                # architecture & flow diagrams
├── checkpoints/
│   ├── known_good/              # last reproducibly-working states
│   └── failed_experiments/      # preserved failures, so they aren't repeated
├── scripts/                     # bring-up, launch, teardown automation
├── tests/                       # smoke tests & validation procedures
└── tools/                       # investigation tooling
```

> **⚠ WARNING**
> This exact layout is a strong default, **not a universal law**. A project with no packet-level work needs no `captures/`; a solo internal effort may fold `client_status.md` away; a heavily legal engagement may expand the disclosure and risk records into several files. Adapt the structure to the project — but do not drop the *functions*. Every record in 9.1 must live somewhere, even if the folder tree differs.

### 9.3 The discipline that makes it work

- [ ] The source-of-truth status file is updated at the end of every working session
- [ ] The current-wall file names exactly one blocker, with evidence — never a vague list
- [ ] Every experiment lands in the experiment log the same day, pass or fail
- [ ] The validation matrix records the honest level (A–E) for each milestone, never inflated
- [ ] Failed experiments are preserved, not deleted — a documented dead end is a saved week
- [ ] Secrets and personal identifiers never enter the evidence or disclosure paths unredacted
- [ ] The known-good checkpoint always points at a state you have actually reproduced

---

## MODULE 10 — SPECIALIST ESCALATION

An AI agent and a capable generalist operator can carry a preservation project a long way — capture, analysis, stand-in services, validation, documentation. But there is a class of problem where continuing to iterate with an agent is not just inefficient, it is *irresponsible*: the risk of a wrong answer is high, the cost of a subtle error is severe, or the domain demands verified human expertise. This module teaches you to recognize that boundary and cross it deliberately.

### 10.1 When to stop iterating and escalate

**SYSTEM VIEW.** Escalation is triggered when the problem enters a domain where (a) errors are silent and high-consequence, (b) correctness requires specialist verification you cannot self-supply, or (c) the work carries legal, security, or distribution risk that an operator is not positioned to accept. The following are hard triggers — meeting *any one* means you prepare a specialist handoff (Prompt 5) rather than another experiment.

**OPERATOR VIEW.** There is a moment in any repair when the right move is to put the tool down and call someone who does this for a living — not because you failed, but because being brave past this line is how people get hurt or get sued. Recognizing that moment is a skill, and it is a mark of competence, not weakness.

**Escalation triggers:**

- Cryptographic verification questions (whether a signature scheme genuinely holds, how verification actually behaves)
- Anti-cheat or other security-sensitive behavior
- High-risk binary patching
- Kernel-level components or drivers
- Advanced C/C++ memory-corruption territory
- Engine-level network protocol implementation
- Low-level rendering reconstruction
- Legal uncertainty of any kind
- Rights-holder authorization requirements
- Repeated failure with no *new* evidence between attempts
- Unbounded scope growth that will not converge
- Any production security or privacy risk
- Code intended to be distributed commercially
- Any claim that requires independent verification before you would stake your name on it

> **⚠ STOP CONDITION**
> The moment a task touches cryptographic soundness, anti-cheat circumvention, kernel-level code, memory-corruption exploitation, or any question of legality or rights-holder authorization — stop iterating with the agent and escalate. These are not "try one more prompt" problems. A confident-but-wrong agent answer in any of these domains can be actively harmful, legally exposing, or both. The exact implementation of sensitive components stays internal and is subject to authorization and specialist review.

### 10.2 Repeated-failure and scope-growth triggers

Two triggers deserve special emphasis because they creep up quietly rather than announcing themselves:

- **Repeated failure without new evidence.** If three experiments in a row have failed and none produced *new* evidence, you are no longer investigating — you are guessing. More agent iterations will not help. Escalate with everything you have tried.
- **Unbounded scope growth.** If the scope needed to reach the next milestone keeps expanding every time you look at it, the problem is larger than the current approach can contain. A specialist can often re-frame it into something bounded — which is exactly the value you are buying.

### 10.3 Specialist-selection table

Match the problem to the role. "Materials to prepare" is what you assemble *before* the conversation so the specialist's expensive time is spent judging, not gathering.

| Problem | Required specialist | Materials to prepare | Question to ask | Expected output |
|---------|--------------------|-----------------------|-----------------|-----------------|
| Memory corruption, unsafe native code, crashes in native modules | **C/C++ engineer** | Crash logs, stack traces, the relevant source or module, reproduction steps | "Is this defect real and what is the safe, minimal correction?" | A verified root cause and a bounded, reviewed fix or a clear "do not proceed." |
| Understanding an unknown binary or format without source | **Reverse engineer** | The binary/artifact, sanitized captures, what is known vs guessed | "What does this component actually do, and how confident can we be?" | A structural explanation with stated confidence, and the limits of what can be inferred. |
| Server/protocol replacement behavior, network correctness | **Backend / network engineer** | Architecture map, endpoint inventory, sanitized captures, current wall | "Does our stand-in behave correctly, and where will it break?" | Confirmation or correction of the design, plus failure-mode analysis. |
| Engine-level netcode / connection handshakes | **Unreal Engine networking specialist** | Sanitized packet captures, engine version reference, observed handshake behavior | "Is this handshake/replication reconstruction correct for this engine version?" | A verified reading of the protocol behavior and the realistic effort to implement it. |
| Rendering reconstruction, low-level graphics | **Graphics engineer** | Captures, engine version, observed rendering behavior | "Is this reconstruction feasible and what does it actually require?" | A feasibility judgement and a scoped path or a documented dead end. |
| Reproducible builds, packaging, offline launch reliability | **Build / release engineer** | Build scripts, environment description, launch procedure, failure logs | "How do we make bring-up reproducible and clean-state reliable?" | A hardened, documented, repeatable build-and-launch procedure. |
| Security or privacy exposure in the approach | **Security reviewer** | Architecture, secret-handling record, disclosure boundary, threat surface | "What are the security and privacy risks, and what must change?" | A risk assessment with required mitigations before proceeding. |
| Legality, rights, distribution, disclosure limits | **IP / legal counsel** | Ownership status, access method, intended use, distribution model, disclosure plan | "What is and is not permissible here, in this jurisdiction and context?" | Qualified legal guidance and defined boundaries — [RIGHTS-HOLDER AUTHORIZATION REQUIRED] where applicable. |
| Whether a claimed result truly holds up | **QA engineer** | Test procedure, validation matrix, reproduction steps, evidence | "Does this milestone reproduce independently at the claimed level?" | An independent validation result (Level D/E) or a list of what fails. |

### 10.4 Exercise

**Question.** Your agent reports, with high confidence, that a token-verification scheme "definitely accepts our locally-served key, so the approach is sound and ready to ship in a client deliverable." Two escalation triggers fire here. Name them and state your next action.

**Model answer.** The triggers are (1) **cryptographic verification** — a claim about whether a signature/verification scheme genuinely holds is exactly the kind of high-consequence, silent-error domain that requires a specialist, and (2) **code intended to be distributed commercially** — "ship in a client deliverable" raises the stakes above operator-acceptable risk. The next action is *not* another agent prompt asserting confidence. It is to run Prompt 4 (challenge the conclusion) to surface false-positive risks, then prepare a Prompt 5 specialist handoff to a security reviewer and, given the crypto question, a specialist qualified to verify the scheme — with sanitized materials only, and the exact implementation kept internal pending review and authorization.

---

## MODULE 11 — CLIENT ENGAGEMENT PROCESS

Preservation done as a paid engagement is not a hobby with an invoice attached. It is a commercial process with authorization gates, defined deliverables, and explicit stop conditions. This module defines the ten-step process RecompileLabs uses to take a client from first contact to a validated, handed-over result — or to an honest, early "no."

### 11.1 The ten-step process

```
INTAKE
  └─> AUTHORIZATION REVIEW        ── gate: no authorization, no work
        └─> ASSET INVENTORY
              └─> RECOVERY AUDIT
                    └─> CURRENT-WALL DEFINITION
                          └─> PROOF-OF-LIFE SPRINT
                                └─> CONTINUATION DECISION   ── gate: go / no-go
                                      └─> SPECIALIST DELIVERY
                                            └─> VALIDATION
                                                  └─> HANDOVER
```

1. **Intake** — capture what the client wants, what they have, and what they are permitted to do. Structured, not conversational (see 11.2).
2. **Authorization review** — establish, in writing, the rights and authorization basis before any technical work. A hard gate. Personal ownership is not, by itself, authorization for every method (see Module 12).
3. **Asset inventory** — enumerate exactly what material exists: source, builds, binaries, server material, captures, credentials.
4. **Recovery audit** — assess feasibility and produce the audit report (see 11.3). This is the first billable deliverable and can stand alone.
5. **Current-wall definition** — name the single most important blocker to the first meaningful milestone, with evidence.
6. **Proof-of-life sprint** — a bounded effort to reach one concrete, demonstrable result (e.g., a stable menu), using the Module 7 control loop throughout.
7. **Continuation decision** — a genuine go/no-go gate. The honest option to stop here, with value already delivered, must be real.
8. **Specialist delivery** — engage the specialists identified in the audit (Module 10) for the domains that require them.
9. **Validation** — prove the result at the agreed validation level (Module 8), independently where the claim warrants it.
10. **Handover** — deliver the documented, reproducible artifact and its records so the client owns a capability, not a demo.

> **⚠ STOP CONDITION**
> Authorization review is a gate, not a checkbox. If the client cannot establish a defensible authorization basis for the work requested, the process stops at step 2 — regardless of budget or enthusiasm. "They own a copy" answers one narrow question and not the others. When in doubt, the correct output of step 2 is a referral to qualified counsel, not a technical plan.

### 11.2 Intake checklist

Complete before any feasibility work begins.

- [ ] Rights-holder status — who holds the rights, and what is the client's relationship to them
- [ ] Source availability — is original source code available?
- [ ] Build availability — is a buildable project or usable build available?
- [ ] Server material — does any original server-side material exist?
- [ ] Binary availability — what compiled binaries exist?
- [ ] Original platform — what platform did it originally target?
- [ ] Target platform — what platform must the result run on?
- [ ] Shutdown deadline — is there a hard date driving urgency?
- [ ] Commercial objective — what is the client actually trying to achieve?
- [ ] Acceptable prototype result — what minimum result would count as success?
- [ ] Disclosure permissions — what may be shown, published, or marketed?
- [ ] Budget — what funding envelope exists?
- [ ] Risk tolerance — technical, legal, and reputational

### 11.3 Recovery audit output template

The recovery audit is a standalone deliverable. Use these exact headings so every audit is comparable and complete.

```markdown
# Recovery Audit — <Project>

## EXECUTIVE SUMMARY
One page: is this feasible, at what risk, to what result, and what it will take.

## CURRENT STATE
What runs today, what does not, and what the shutdown/deadline changes.

## AVAILABLE MATERIAL
Source, builds, binaries, server material, captures — with gaps named.

## SYSTEM ARCHITECTURE
The confirmed (or best-understood) service chain and component map.

## CONFIRMED DEPENDENCIES
Every external dependency the software requires to function.

## CURRENT WALLS
The specific blockers to the first meaningful milestone, evidenced.

## RECOVERY OPTIONS
The viable technical paths, with trade-offs — not a single forced answer.

## RISK REGISTER
Technical, legal, security, and scope risks, each with severity and status.

## PROOF-OF-LIFE TARGET
The one concrete, demonstrable milestone the first sprint will aim for.

## RECOMMENDED SPECIALISTS
Which specialist roles the work will require, and for which walls.

## ESTIMATED PHASES
The phased plan from proof-of-life to the client's objective.

## BUDGET BANDS
Cost ranges per phase — bands, not false precision.

## STOP CONDITIONS
The explicit conditions under which the engagement should halt.

## NEXT DECISION
The single decision the client must make to proceed.
```

### 11.4 Where WW3 fits

The WW3 Stage 1 work is a clean illustration of steps 3–9 for an *internal, single-owned-copy* case: asset inventory (owned copy, captured traffic, no original source or server), recovery audit (feasible to reach a menu; match play a separate, larger question), current-wall definition (each service in turn, then the anti-cheat login, then stability), a proof-of-life sprint that reached a stable, fully-populated menu, and validation hardened to clean-state reproduction. It also shows the honest continuation decision: Stage 1 is a complete, valuable result *on its own*, and Stage 2 (playable matches) is a separate go/no-go — not an assumed continuation.

---

## MODULE 12 — AUTHORIZATION, DISCLOSURE AND SAFETY

This module governs everything above it. Technical capability is not permission, and a working method is not a safe method. The single most important sentence in this manual is this: **personal ownership of a copy does not automatically make every technical method legally safe.**

### 12.1 Ownership is not a licence for every method

Legal rights around software preservation vary — sometimes dramatically — by **jurisdiction, contract, access method, distribution model, and intended use**. Owning a copy answers one narrow question. It does not, by itself, tell you whether a particular technique is permitted, whether a contract you agreed to restricts it, whether the access method you used matters, or whether your intended use (private vs distributed, personal vs commercial) changes the answer.

> **⚠ STOP CONDITION**
> This manual does not give legal advice, and neither should you. Where legal permissibility is uncertain — which is often — the correct action is to obtain qualified legal counsel for the specific facts. Do not substitute an operator's confidence, an agent's assertion, or a forum post for that. "I own it, so I can do anything to it" is not a legal opinion; it is a way to end up on the wrong side of one.

### 12.2 Mandatory pre-investigation gate

No technical work begins until every box is genuinely satisfiable. This gate protects the client, the operator, third parties, and RecompileLabs.

- [ ] The software copy was legitimately obtained
- [ ] Ownership / authorization status is documented, not assumed
- [ ] The scope of work is explicitly defined and bounded
- [ ] Live third-party infrastructure will not be disrupted by the work
- [ ] Personal-data handling is defined — what is captured, how it is redacted, how it is stored
- [ ] Secrets (keys, tokens, certificates, credentials) are protected and kept out of evidence/disclosure paths
- [ ] Public vs private disclosure boundaries are defined before anything is captured
- [ ] Distribution restrictions are understood — who may receive what, if anyone
- [ ] Rights-holder review requirements are identified where they apply
- [ ] Security-sensitive work is routed to specialist review (Module 10)
- [ ] Legal review has been requested wherever it is necessary
- [ ] No public claim will exceed the evidence that supports it

> **⚠ WARNING**
> "Live third-party infrastructure will not be disrupted" is not a formality. A passive recorder that observes your own legitimate traffic while servers are live is a fundamentally different act from anything that loads, probes, or interferes with someone else's live systems. Keep the work isolated to a local environment that talks only to itself. If a technique would touch, stress, or deceive infrastructure you do not control, it does not belong in this project.

### 12.3 Disclosure categories

Every piece of project material is assigned exactly one category. When in doubt, assign the more restrictive one.

| Category | Meaning |
|----------|---------|
| **PUBLIC** | May be shared openly. Teaches process, evidence, and judgement; contains no reusable circumvention, no secrets, no personal data. |
| **CLIENT-CONFIDENTIAL** | Shared only with the client under the engagement. Project specifics not intended for the public. |
| **INTERNAL** | RecompileLabs-only working material — experiment logs, raw notes, working detail not meant to leave the team. |
| **SENSITIVE** | Requires special handling — anything touching security-relevant detail, credentials handling, personal identifiers, or specialist-review-pending implementation. Restricted even internally, on a need-to-know basis. |
| **PROHIBITED** | Must never be produced or shared in any deliverable — reusable exploit/bypass recipes, forged-credential or cert-substitution instructions, anti-cheat-circumvention methods, exposed keys/certs/tokens, or personal identifiers. If content falls here, it is not redacted-and-shipped; it is not written. |

### 12.4 Historical description vs public instruction

The original Stage 1 dossier is written as a triumphant internal narrative. Some of its language — describing impersonating a backend, forging credentials, or getting past an anti-cheat login — may be **acceptable as an internal, historical description of what was done on a single owned copy in an isolated environment**. That same language is **not** suitable as *public instruction* and **not** suitable as *marketing*.

**SYSTEM VIEW.** The distinction is between *recording that an event occurred* and *publishing a reusable method*. An internal record may state that a local replacement was introduced for a third-party identity dependency within the isolated test environment, and that a synthetic local profile reached a fully-populated menu. It does not publish the implementation. A public or marketing artifact must go further still: it teaches the *reasoning and discipline* — capture, evidence, validation, escalation — and deliberately withholds anything that functions as a circumvention recipe. The exact implementation of sensitive components stays internal, subject to authorization and specialist review [INTERNAL IMPLEMENTATION DETAIL] [RIGHTS-HOLDER AUTHORIZATION REQUIRED].

**OPERATOR VIEW.** It is one thing to write in your own logbook, "we got past the guard by doing X on our own machine." It is another to print a poster that says "here is how anyone gets past this guard." The first can be a legitimate private record. The second is instruction — and, as marketing, it is a claim you almost certainly cannot stand behind and a temptation you should not offer. When you turn any of this into something public-facing, you strip it down to method and judgement, and you keep the recipe in the vault.

> **⚠ WARNING**
> Never let a public claim outrun the evidence. Stage 1 reaches a *stable menu* — it does not deliver playable matches, and no public statement should imply otherwise. Marketing that overstates the result is both a credibility risk and, potentially, a legal one. The evidence sets the ceiling on the claim, every time.

### 12.5 Exercise

**Question.** A draft blog post reads: "We fully revived World War 3 offline — here's the exact method for forging the login so you can do it too." Identify three separate problems and give the corrected framing.

**Model answer.** Three problems: (1) **Overclaim** — "fully revived" implies playable matches; Stage 1 reaches only a stable menu, so the claim exceeds the evidence. (2) **Prohibited content** — "the exact method for forging the login" is a reusable circumvention recipe; that belongs to the PROHIBITED category and must not be published in any form. (3) **Instruction framing** — "so you can do it too" converts a historical description of work on a single owned copy into public instruction, which is not permissible. Corrected framing: describe, at the level of process and judgement, that a locally controlled replacement was introduced for a third-party identity dependency within an isolated test environment, that a synthetic local profile reached a fully-populated menu, and that the exact implementation stays internal and subject to authorization and specialist review. State plainly that the result is a stable menu, not playable matches, and teach the *discipline* rather than the recipe.
