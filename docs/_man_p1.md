# RECOMPILELABS OPERATOR FIELD MANUAL

**A Systems-Led Curriculum for Legacy Game Recovery, Backend Continuity and AI-Assisted Technical Investigation**

---

**Classification:** PRIVATE INTERNAL TRAINING DOCUMENT
**Prepared for:** Repository Owner, Founder & Technical Producer, RecompileLabs
**Primary worked case:** World War 3 (Steam App 674020), Unreal Engine 4.21, multiplayer-only — Stage 1 backend continuity
**Revision:** 1.0

---

## Classification Notice

This is an internal training document. It is written to teach a repeatable working method — how to run a technical recovery investigation, how to structure evidence, and how to direct AI-assisted engineering without losing control of the truth. It is not a marketing document, not a legal opinion, and not a public disclosure.

Nothing in this manual is a set of step-by-step instructions for defeating a protection, forging a credential, substituting a key, or circumventing an anti-cheat system. Where the World War 3 (WW3) Stage 1 work touched sensitive components, this manual describes **what kind of problem was solved and how the investigation was reasoned**, and marks the concrete implementation as internal and out of scope:

- Specific credential, certificate, token, key, and endpoint values → **[REDACTED]**
- Personal identifiers captured during observation → **[SANITIZED]**
- The exact mechanics of sensitive substitutions → **[INTERNAL IMPLEMENTATION DETAIL]**
- Anything whose reuse would require permission from a rights-holder → **[RIGHTS-HOLDER AUTHORIZATION REQUIRED]**

Read the manual for judgment, not for recipes. If a passage seems to be leaving out "how exactly," that omission is deliberate and correct.

> **⚠ WARNING**
> This manual teaches process, evidence discipline, and decision-making. It deliberately does **not** teach reusable circumvention. If you ever find yourself wanting a section to give you the exact bytes, keys, or bypass steps to copy — stop, and route that need to an authorized specialist under the escalation rules in Module 1. The value of RecompileLabs is the disciplined method, not any single trick.

---

## Intended Audience

The primary reader is **Repository Owner**, founder and technical producer of RecompileLabs. The manual is written specifically for the way this reader works:

- **Understands systems architecturally.** You can reason about how a client, a set of backend services, tokens, and network protocols fit together, and you can hold the whole chain in your head.
- **Operates AI coding agents.** You direct AI-assisted engineering to do the reading, searching, drafting, and much of the implementation. You do not personally hand-write every line.
- **Coordinates specialists.** When a problem needs deep C/C++, binary work, cryptographic review, or engine-level engineering, you bring in a person qualified to own it.
- **Owns the investigation, the evidence, the decisions, and the delivery.** The technical judgment — what the current wall is, what counts as proof, what to claim publicly — is yours and stays yours.

You are **not** a traditional software engineer, and you are **not** expected to become one. You are also not the person who should personally implement every sensitive component. Your job is to convert technical uncertainty into structured, evidence-backed decisions, and to keep the whole effort honest and reproducible. This manual is built around that job.

A secondary audience — future RecompileLabs operators and collaborating specialists — can read the same material to understand the house method and the vocabulary everyone is expected to share.

---

## Scope

**In scope:**

- The role of the technical recovery operator, and how it differs from adjacent roles.
- The universal service chain that online games depend on to boot and reach a menu.
- How to open a new investigation through legitimate observation instead of guessing.
- A shared evidence taxonomy and the discipline of labelling every major claim.
- The "current wall" method for advancing one confirmed blocker at a time.
- The maturity ladder from observing traffic, to replaying it, to genuinely emulating behaviour — and how to tell where you actually are.

**Out of scope (covered in later parts of the curriculum, or intentionally never covered):**

- Reusable circumvention techniques of any kind.
- Deep implementation of sensitive components (identity substitution internals, cryptographic signing procedures, anti-cheat handling).
- Legal determinations. This manual assumes an authorized, single-owned-copy, isolated-environment context and does not rule on any other situation.
- Stage 2 (live match/battlefield simulation), which is a much larger, unfinished effort discussed here only as a feasibility contrast.

---

## What This Manual Does

- Defines the **technical recovery operator** as a distinct role with distinct accountability.
- Gives you a **transferable mental model** of online-game architecture so any new title becomes legible quickly.
- Teaches you to **discover before you build** — to map a system through legitimate observation rather than assumption.
- Installs an **evidence taxonomy** so that "we saw it," "we infer it," and "we suspect it" never get quietly merged into "it's true."
- Teaches the **current-wall discipline** so effort is always spent on the earliest confirmed blocker.
- Teaches the **observe → replay → emulate** maturity ladder so you never mistake a convincing demo for a finished service.
- Gives you the tools to **direct AI agents and specialists** while keeping ownership of the truth.

Every module uses WW3 Stage 1 as the primary worked case, but teaches the reasoning so it transfers to any legacy online title.

---

## What This Manual Does NOT Do

- It does not teach you how to defeat a protection, forge a credential, substitute a certificate or key, sign tokens, or circumvent anti-cheat. Those are marked **[INTERNAL IMPLEMENTATION DETAIL]** / **[RIGHTS-HOLDER AUTHORIZATION REQUIRED]** and belong to authorized specialists.
- It does not turn you into an implementation engineer. It makes you a better director of engineering.
- It does not give legal advice or claim that any activity is lawful, endorsed, or sanctioned. It assumes you have already established an authorized, owned-copy, isolated context, and confines all worked examples to that context.
- It does not claim Stage 2 features exist. Stage 1 reaches a stable menu. It does **not** provide playable matches.
- It does not present hypotheses as facts. Where the WW3 work reached a judgment rather than a proof, the manual says so.

---

## Prerequisite Knowledge

You should be comfortable with the following before starting. None of these require you to be a programmer.

| You should be able to… | Why it matters |
|---|---|
| Read a system as a set of components that talk to each other | Every module treats the game as a chain of services |
| Understand "client" vs "server" as roles | The whole recovery method is about who answers whom |
| Grasp that programs communicate over named protocols (web requests, sockets, chat, real-time UDP) | Module 2 maps each layer to a protocol type |
| Read a log or terminal transcript and follow a sequence of events | Reconnaissance and wall records are built from logs |
| Distinguish "I saw this" from "I think this" from "I guess this" | Module 4 formalises exactly this |
| Direct an AI coding agent with a clear task and check its output | The operator role depends on this |
| Recognise when a problem is beyond you and needs a specialist | Module 1 makes this a formal responsibility |

You do **not** need to know any programming language, any cryptography, or any reverse-engineering technique. Where those appear, you need only enough to *judge* a specialist's or an agent's work — not to perform it.

---

## Learning Outcomes

On completing the full curriculum, the operator will be able to demonstrate the following fourteen competencies. Part 1 (this file) establishes the first several and lays the foundation for the rest.

1. **Understand a target system architecturally** — hold the full client-to-match chain as a mental model.
2. **Discover dependency flow** — determine, by legitimate observation, which service the client calls, in what order, and what each expects back.
3. **Identify the earliest confirmed wall** — locate the first real blocker to the next milestone, not the most interesting bug.
4. **Separate evidence, inference, and hypothesis** — keep the three categories distinct in every report.
5. **Direct AI agents without surrendering control** — use agents for reach and speed while keeping ownership of the conclusions.
6. **Approve bounded experiments** — authorise the smallest test that can disprove a hypothesis, with a rollback plan.
7. **Validate milestone reality and reproducibility** — confirm that a claimed result is real, repeatable, and not a one-time fluke.
8. **Detect hallucinated or weak engineering explanations** — recognise when an agent or specialist is confidently wrong or hand-waving.
9. **Know when replay suffices versus when real emulation is required** — tell the difference between serving fixed responses and simulating behaviour.
10. **Recognise specialist escalation** — know the signals that a problem must go to a qualified human.
11. **Maintain documentation and reproducibility** — keep records so any result can be reconstructed and audited.
12. **Communicate accurately** with engineers, clients, and communities — say exactly what is true, no more.
13. **Avoid exaggerating progress** — never let a menu boot be described as a working game.
14. **Operate within authorization, disclosure, and rights boundaries** — keep every action inside an authorized, isolated, owned-copy scope.

---

## How To Use This Manual

- **Read the modules in order the first time.** Each builds vocabulary the next one reuses.
- **Treat every defined term as load-bearing.** A term is explained once, in bold, and then reused precisely. When you see it again, it means exactly what it meant before.
- **Do the exercises.** They are not decoration. The model answers show the *reasoning*, which is the point — not the answer itself.
- **Use the templates as living documents.** The Reconnaissance Worksheet (Module 3) and the Wall Record (Module 5) are meant to be copied and filled in for real work, not just read.
- **Obey the STOP CONDITIONS.** A blockquote beginning **⚠ STOP CONDITION** marks a point where you must halt and route to a specialist, an authorization check, or a decision — not push forward.
- **When in doubt about a claim, downgrade it.** The evidence taxonomy in Module 4 is a ratchet toward honesty. It is always safe to label something as weaker than you hope; it is never safe to label it stronger than you can prove.

---

## Competency-Level System

RecompileLabs classifies operator capability into five levels. The levels describe *what a person can reliably do on their own*, not how much they know in the abstract.

| Level | Title | Can reliably… |
|---|---|---|
| **LEVEL 0** | OBSERVER | Describe what happened, but cannot yet structure an investigation. Can watch a boot, read a log, and narrate events — without a method to turn that into progress. |
| **LEVEL 1** | OPERATOR | Collect evidence, maintain state, and follow an established process. Can run the recon worksheet, keep a wall record, and execute a defined procedure faithfully. |
| **LEVEL 2** | INVESTIGATION LEAD | Identify walls, control bounded experiments, and challenge agent conclusions. Can decide what the current blocker is, design the disproving test, and push back on a confident-but-wrong explanation. |
| **LEVEL 3** | TECHNICAL PRODUCER | Scope client engagements, coordinate specialists, and convert evidence into recovery plans. Can turn a pile of observations into a costed, sequenced plan and run the people who execute it. |
| **LEVEL 4** | PRACTICE LEAD | Create repeatable methods, oversee multiple investigations, and maintain quality across them. Can build the process others follow and hold the bar across many projects at once. |

**This manual moves the reader from Level 0 toward Level 3.** It builds the observer into an operator, the operator into an investigation lead, and equips the investigation lead with the producer-level judgment needed to scope work, coordinate specialists, and convert evidence into a recovery plan. Level 4 — building the practice itself — is a matter of applying this method across many engagements over time, and is beyond the scope of the manual.

---

# MODULE 1 — THE TECHNICAL RECOVERY OPERATOR

## 1.1 What the role is

> **The operator turns technical uncertainty into structured investigation, evidence, decisions and executable recovery plans.**

That single sentence is the whole job. A legacy online game about to lose its servers is a fog of unknowns: nobody has the source, nobody has the server code, and the clock is running. The operator is the person who walks into that fog and comes out with a *structured* picture — a map of what the system does, a stack of labelled evidence, a set of decisions about what to attempt, and a plan that other people (specialists and AI agents) can execute.

The operator does not have to be the best engineer in the room. The operator has to be the person who keeps the investigation honest, ordered, and moving.

**SYSTEM VIEW.** The operator is the control loop around an otherwise unstructured engineering effort. Inputs are raw observations (logs, captures, process trees, agent output, specialist findings). The operator's function is to classify each input by evidential weight, maintain the investigation's state (current wall, open hypotheses, validated results), authorise bounded state transitions (experiments), and emit two outputs: an auditable evidence record and a sequenced recovery plan. The operator is accountable for the integrity of the loop, not for the internals of any single component inside it.

**OPERATOR VIEW.** Think of yourself as the investigator running a case, not the forensic technician at the bench. The technicians (specialists) and the research assistants (AI agents) do the detailed work. You decide which lead to chase next, you refuse to write down a guess as a fact, and you are the one who has to stand behind the final report and say "this is exactly what we know, and here's how anyone can check it." If the case falls apart, it falls apart on *your* discipline, not on someone else's soldering.

## 1.2 Why the role exists

Legacy game recovery has a structural gap. The work needs:

- Deep, occasional bursts of specialist engineering (binary, protocol, crypto, engine).
- Fast, broad, tireless assistance (search, log analysis, drafting, patch proposals) — which AI agents now provide.
- And, crucially, **someone who owns the truth**: who decides what the current problem actually is, what counts as proof, and what may be claimed.

Neither a pure programmer nor a pure project manager fills that gap. The programmer tends to dive into the most interesting implementation problem; the project manager tends to track tasks without being able to judge technical reality. The operator sits exactly between architecture literacy and delivery accountability. The role exists because AI-assisted engineering made broad execution cheap and abundant — which made *judgment and evidence discipline* the scarce, decisive skill.

## 1.3 How it differs from adjacent roles

| The operator is NOT a… | Because… | The operator instead… |
|---|---|---|
| **Programmer** | A programmer's deliverable is working code; their instinct is to build. | Owns the *question* and the *evidence*; may direct code to be written, but does not measure success in lines shipped. |
| **Project manager** | A PM tracks tasks and dates but cannot adjudicate technical reality. | Judges whether a claimed result is real and reproducible, and sets the technical direction. |
| **Reverse engineer** | A reverse engineer's craft is extracting how a binary or protocol works internally. | Consumes reverse-engineering findings as *inputs*, and knows when to commission them — but is not defined by performing them. |
| **Security researcher** | A security researcher hunts for weaknesses to disclose or exploit. | Is doing preservation and continuity in an authorized, isolated context; deliberately avoids producing reusable circumvention and routes sensitive findings to authorized specialists. |
| **Game producer** | A game producer ships a product and manages a studio's creative delivery. | Runs an *investigation* into an existing artifact, and delivers evidence and a recovery plan, not a game. |

The distinction from the security researcher matters most for RecompileLabs' identity. The operator uses observation and analysis, but the *product* is a preserved, owned artifact and an honest record — never a transferable attack. Sensitive discoveries are noted as internal and escalated, not published as techniques.

## 1.4 What accountability stays with the operator

These never leave the operator, no matter who does the hands-on work:

- The **investigation question** — what we are actually trying to answer right now.
- The **scope boundaries** — what is in and out, including the authorization/rights envelope.
- The **evidence structure** — every major claim carries its taxonomy label.
- The **current-wall definition** — what the one blocker is at this moment.
- **Experiment approval** — no bounded change runs without operator sign-off.
- **Status reporting** — the operator is the source of the honest status.
- **Reproducibility** — results must be reconstructable, and the operator owns that.
- **Specialist escalation** — the operator decides when a problem must go to a qualified human.
- **Client communication** — what is said to a client or community is the operator's responsibility.
- **Claims discipline** — the operator is the last line against exaggeration.

## 1.5 What must be delegated

Some work must go to a qualified specialist. The operator's job is to *recognise* these, not to attempt them:

- Deep C/C++ implementation.
- Binary instrumentation and analysis.
- Protocol implementation at production quality.
- Advanced graphics / rendering engineering.
- Cryptographic review.
- Complex network emulation.
- Engine-level runtime changes.
- Formal security assessment.

> **⚠ STOP CONDITION**
> If a task requires cryptographic implementation, binary instrumentation, engine-level runtime modification, or anything whose failure could be unsafe or whose reuse could constitute circumvention — **stop and escalate to an authorized specialist.** The operator may scope and direct such work; the operator must not improvise it, and an AI agent's willingness to produce it is not a substitute for specialist review.

## 1.6 What must never be falsely claimed

The operator is the guardian against three specific lies, all of which are tempting and all of which are fatal to credibility:

1. **That a menu boot is a working game.** Reaching a stable main menu is a real, bounded achievement. It is not multiplayer. Never let the two be conflated.
2. **That a feasibility judgment is a completed feature.** "The traffic looked readable, so Stage 2 appears possible" is a judgment. It is not a match server.
3. **That an AI agent's confident explanation is verified truth.** An agent producing a fluent rationale is not evidence. Only evidence is evidence.

## 1.7 The Responsibility Matrix

This matrix is the operational heart of Module 1. Internalise it.

### OPERATOR OWNS

- The investigation question
- Scope boundaries
- Evidence structure
- Current-wall definition
- Experiment approval
- Status reporting
- Reproducibility
- Specialist escalation
- Client communication
- Claims discipline

### SPECIALIST MAY OWN

- Deep C/C++ implementation
- Binary instrumentation
- Protocol implementation
- Advanced graphics engineering
- Cryptographic review
- Complex network emulation
- Engine-level runtime changes
- Formal security assessment

### AI AGENT MAY ASSIST WITH

- Code search
- Log analysis
- Documentation
- Implementation proposals
- Bounded patches
- Automation
- Test harnesses
- Diagrams
- Comparison of evidence
- Report drafting

### AI AGENT MUST NOT BE TREATED AS

- An unquestionable authority
- The owner of project truth
- A substitute for evidence
- A substitute for legal authorization
- A substitute for specialist review when risk is high

**SYSTEM VIEW.** The matrix is a separation-of-concerns contract. "Operator owns" is the non-delegable control plane. "Specialist may own" is the high-assurance implementation plane, gated by escalation. "AI agent may assist" is the high-throughput execution plane, gated by operator verification. "Must not be treated as" enumerates the failure modes where the execution plane is mistaken for the control plane — the single most common way these projects go wrong.

**OPERATOR VIEW.** Three sets of hands, one head. The head (you) decides and owns. The skilled hands (specialists) do the dangerous, precise jobs. The many fast hands (AI agents) do the bulk of the fetching, drafting, and building — but they never get to decide what's true, never stand in for real proof, and never replace a specialist when the stakes are high. The last box is the list of ways people accidentally let the fast hands run the show. Don't.

## 1.8 EXERCISE 1.1 — Classify ten responsibilities

For each item below, classify it as **Operator** (owned by the operator), **Specialist** (must be delegated to a qualified human), **AI-Assisted** (an agent may do the bulk of it under operator direction), or **Shared** (meaningfully split — an agent or specialist does the work but the operator retains ownership of the decision or the truth).

1. Deciding which failing service is the current wall.
2. Writing a cryptographic signing routine for a sensitive identity component.
3. Searching a large capture set for every request the client makes before the menu.
4. Deciding whether a claimed "stable boot" is real and reproducible.
5. Drafting the first version of the investigation report.
6. Performing binary instrumentation to see which library a call comes from.
7. Deciding what to tell a client community about current progress.
8. Proposing three candidate fixes for an unstable background connection.
9. Deciding whether the project is authorized and in scope before any work starts.
10. Comparing "walking" versus "standing" captures to isolate which bytes change.

### Model answer

| # | Responsibility | Classification | Reasoning |
|---|---|---|---|
| 1 | Identify the current wall | **Operator** | Wall definition is non-delegable. An agent can surface candidates, but choosing *the* current blocker is the operator's judgment. |
| 2 | Cryptographic signing for a sensitive component | **Specialist** | Cryptographic implementation is a STOP CONDITION. It requires a qualified human and specialist review; an agent's code is not sufficient assurance. |
| 3 | Search captures for pre-menu requests | **AI-Assisted** | Broad search across large data is exactly what agents are for. The operator directs and checks; the agent does the sweep. |
| 4 | Validate a claimed stable boot | **Operator** | Deciding whether a result is real and reproducible is claims discipline and validation — squarely operator-owned. |
| 5 | Draft the report | **Shared** | The agent may write the first draft, but the operator owns every claim's truth and taxonomy label. Drafting is assisted; ownership is not. |
| 6 | Binary instrumentation | **Specialist** | Binary instrumentation is on the delegation list. Commission it; do not improvise it. |
| 7 | Communicate progress to a community | **Operator** | Client/community communication and claims discipline are non-delegable. |
| 8 | Propose candidate fixes | **AI-Assisted** | Proposing options is ideal agent work. Note: *choosing* and *approving* the experiment (Module 5) remains operator-owned. |
| 9 | Confirm authorization and scope | **Operator** | Scope boundaries and the authorization envelope are foundational operator responsibilities; nothing starts until the operator confirms them. |
| 10 | Compare walking vs standing captures | **AI-Assisted** | Structured comparison of evidence is on the agent-assist list. The operator interprets the result; the agent does the diffing. |

Note the recurring pattern: whenever an item is about *deciding what is true, what is in scope, or what may be claimed*, it lands on the operator. Whenever it is about *volume of reading/searching/drafting*, it lands on the agent. Whenever it is *precise, dangerous, or reuse-sensitive implementation*, it lands on the specialist. When work and ownership split across those, it is **Shared** — and the operator keeps the ownership half.

---

# MODULE 2 — THE UNIVERSAL SERVICE CHAIN

Every online game that requires a live backend depends on the same *shape* of architecture, even when the names and protocols differ. Learn the shape once, and every new title becomes legible fast.

```
CLIENT
  → IDENTITY / AUTHENTICATION
    → PROFILE / META
      → HUB / MENU CONTROL
        → PRESENCE / SOCIAL
          → MATCHMAKING / LOBBY
            → MATCH SERVER
```

Each layer generally must succeed before the next begins. That ordering is the operator's single most useful fact: **the earliest failing layer is where your attention belongs, because nothing downstream can even be reached until it passes.** (This is the seed of the current-wall discipline in Module 5.)

WW3 Stage 1 addressed the dependencies needed to *boot and reach the menu*: identity, profile, hub, and presence. Matchmaking/lobby handoff was observed, and the match server itself is Stage 2 — a qualitatively different problem, covered at the end of this module.

## 2.1 The layers

### CLIENT

**Responsibility.** The game executable on the user's machine. It initiates every conversation, carries credentials between services, and renders the result. It is the one component you generally cannot rewrite — it defines what every other layer must satisfy.

**SYSTEM VIEW.** The client is a fixed protocol consumer. It emits requests in a defined order, carries opaque credentials (it typically does not itself validate signatures — it transports them), and gates its own state transitions on receiving expected responses. Its behaviour is the specification the backend must meet.

**OPERATOR VIEW.** The client is the customer you must satisfy exactly. You don't get to change what it wants; you have to learn what it wants and give it precisely that. Everything upstream is about keeping this one demanding customer happy.

---

### IDENTITY / AUTHENTICATION

**Responsibility.** Establishes *who the player is* and issues a credential the client carries onward (commonly a signed token). Everything downstream trusts that credential.

**Common protocols.** HTTP/REST, often issuing signed tokens.

**Typical client expectation.** Submit a login, receive back a token and an identity, proceed only on success.

**Stateless vs stateful.** Largely **stateless** at the request level — a login exchange can be answered without holding long-lived session state — though the *token* it issues carries state forward.

**What failure looks like.** The client stops at or before the first screen; a rejected login halts the whole boot. In WW3 the equivalent hard wall was an identity/anti-cheat check that, when it received an unacceptable login, refused and the client crashed.

**Evidence sources.** Launch logs, the first outbound requests, the request/response bodies of the login exchange, timestamps of the earliest failures.

**Recorded replay sufficient?** For a *bootable, isolated, owned-copy* menu goal, replaying a valid-shaped identity response can be sufficient to get past the gate — because the client transports rather than deeply validates. The sensitive specifics of how an identity dependency was satisfied are **[INTERNAL IMPLEMENTATION DETAIL]**.

**When behavioral emulation is required.** If identity must interact with a live third party or change per-session in ways a fixed response cannot satisfy, replay is not enough and real behavioural handling is needed.

**Specialist expertise.** Cryptographic review; any handling of a third-party identity dependency. In WW3, a **locally controlled replacement was introduced for a third-party identity dependency within the isolated test environment**; the exact implementation stays internal, subject to authorization and specialist review. **[RIGHTS-HOLDER AUTHORIZATION REQUIRED]**

---

### PROFILE / META

**Responsibility.** Serves the player's persistent state: level, progression, inventory, loadouts, currency, unlocks, season/battle-pass data. The "filing cabinet."

**Common protocols.** HTTP/REST returning structured data (often large payloads).

**Typical client expectation.** After identity, fetch the profile and unlock trees; populate the menu from them.

**Stateless vs stateful.** Mostly **stateful** in concept (it represents durable player data), but at the request level it often behaves as a set of retrievable documents — which is why fixed recordings can populate a menu.

**What failure looks like.** The client authenticates but the menu is empty, partial, or hangs waiting for profile data.

**Evidence sources.** Captured profile, inventory, progression, and season responses; their sizes and structure; the order in which the client requests them.

**Recorded replay sufficient?** Yes, for reaching a populated menu in an isolated environment. In WW3, a locally-supplied synthetic profile served from this layer reached a fully-populated menu. (No live account was required for the isolated result.)

**When behavioral emulation is required.** If the menu allows actions that *mutate* profile state and expect consistency across a session, static documents are not enough — the layer must track and update state.

**Specialist expertise.** Usually none beyond ordinary service work — this is often the most tractable layer.

---

### HUB / MENU CONTROL

**Responsibility.** The live "switchboard" behind the menu — the always-on control channel that runs menu state, lobby coordination, and real-time notifications. Unlike the request/response layers above, it is a persistent connection.

**Common protocols.** WebSocket (a long-lived, two-way channel).

**Typical client expectation.** Open a persistent connection and keep it alive; send and receive menu-service messages continuously.

**Stateless vs stateful.** **Stateful and long-lived.** The connection itself is the state. It expects continuous liveness signalling.

**What failure looks like.** The menu loads but shows "lost connection" errors, or repeatedly disconnects and reconnects because the connection is not being kept alive correctly.

**Evidence sources.** The WebSocket handshake, the stream of menu-service messages, and — critically — the *timing* of keep-alive/heartbeat traffic.

**Recorded replay sufficient?** Partially. You can replay the shape of messages, but a persistent connection cannot be satisfied by a fixed recording alone — it requires ongoing, correctly-timed liveness behaviour. WW3 stability work in this layer fixed keep-alive/heartbeat behaviour so the connection held.

**When behavioral emulation is required.** Always, at least minimally — because "stay alive and answer on time" is behaviour, not a document.

**Specialist expertise.** Complex network emulation if the message semantics are intricate.

---

### PRESENCE / SOCIAL

**Responsibility.** Who is online, friends, chat, status. The social overlay on the menu.

**Common protocols.** XMPP-style presence (a chat/presence protocol), typically over a persistent connection.

**Typical client expectation.** Establish a presence session under a consistent identity, then exchange status and social messages.

**Stateless vs stateful.** **Stateful.** It binds an identity and holds a session; identity consistency across the session matters.

**What failure looks like.** Recurring "communication service" disconnects; the social layer resetting in a loop. In WW3, a presence/identity mismatch (the service asserting an identity that did not match what the client declared) caused repeated resets until reconciled; stability work corrected it.

**Evidence sources.** The presence session bind, the identity asserted versus the identity the client declares, disconnect timing, keep-alive behaviour.

**Recorded replay sufficient?** No, not alone — like the hub, it is a live session and needs correct, consistent behaviour (especially identity consistency and keep-alive).

**When behavioral emulation is required.** Whenever identity consistency or liveness must be maintained across the session — which is the normal case.

**Specialist expertise.** Complex network emulation; protocol implementation if the presence dialect is non-trivial.

---

### MATCHMAKING / LOBBY

**Responsibility.** Finds or forms a match, holds lobby state, and hands the client off to a match server.

**Common protocols.** Often HTTP/REST and/or the hub channel for search and lobby state, culminating in a handoff.

**Typical client expectation.** Request matchmaking, receive lobby state, then receive a match-start handoff pointing at a match server.

**Stateless vs stateful.** **Stateful** — a lobby is a shared, evolving state.

**What failure looks like.** The player can sit at the menu but "Play" never resolves into a match; the search spins or the handoff never arrives.

**Evidence sources.** Matchmaking search traffic, lobby state messages, and the match-start handoff — all of which were *observed* in WW3.

**Recorded replay sufficient?** For *observing and understanding the handoff*, replay of the captured flow is informative. For actually *delivering* a match, no — because what it hands off to (the match server) is a live simulation, not a document.

**When behavioral emulation is required.** As soon as the goal is a real match rather than reaching the menu.

**Specialist expertise.** Complex network emulation; overlaps with the match-server problem.

---

### MATCH SERVER

**Responsibility.** The live battlefield simulation — the authoritative game world, updated many times per second, synchronising every player, projectile, and vehicle.

**Common protocols.** Real-time UDP netcode (for WW3, the reference is stock Unreal Engine 4.21 networking).

**Typical client expectation.** Complete a real-time connection handshake, then exchange a continuous stream of world-state updates.

**Stateless vs stateful.** **Deeply stateful and continuous** — it *is* the running simulation.

**What failure looks like.** The client cannot connect into a world, or connects into an empty/frozen one, because there is no simulation on the other end.

**Evidence sources.** Captured match traffic segmented by activity (standing, walking, running, driving, combat); the engine's public netcode as the reference for structure.

**Recorded replay sufficient?** **No.** This is the decisive distinction of the whole module. You cannot replay a simulation. A recording of a match is a fixed transcript of one past game; it cannot respond to *your* movements. A match server must *generate* new, correct state in real time.

**When behavioral emulation is required.** Always. This layer is behavioural emulation by definition — it is Stage 2 and is **not done**.

**Specialist expertise.** Advanced network emulation, engine-level knowledge, and sustained engineering. This is a much larger effort than all of Stage 1 combined.

> **⚠ WARNING**
> Reaching a populated, stable menu through replay of fixed responses does **not** mean a match server exists or is close. The menu layers can largely be satisfied by serving back what was observed. The match server cannot — it must simulate. Never let "we reached the menu" imply "we can play." They are different *kinds* of problem, not different sizes of the same problem.

## 2.2 Layer summary table

| LAYER | WW3 ROLE | OBSERVED PROTOCOL / INTERFACE | CLIENT DEPENDENCY | STAGE 1 STATUS | TRANSFERABLE LESSON |
|---|---|---|---|---|---|
| Identity / Auth | Establish player identity; issue carried credential | HTTP/REST (token-issuing) | Must pass before anything else | Addressed (isolated env); sensitive parts **[INTERNAL IMPLEMENTATION DETAIL]** | The earliest gate; identity failures halt the entire boot |
| Profile / Meta | Serve progression, inventory, loadouts, season data | HTTP/REST (structured payloads) | Populates the menu | Addressed — synthetic profile reached full menu | Persistent-but-retrievable data is often replay-friendly |
| Hub / Menu Control | Live menu/lobby switchboard | WebSocket (persistent) | Keeps the menu alive | Addressed; keep-alive/heartbeat stabilised | A live connection needs *behaviour* (liveness), not just messages |
| Presence / Social | Friends, status, chat | XMPP-style presence (persistent) | Consistent social session | Addressed; identity-consistency & disconnect issues fixed | Identity consistency across a session is a real failure mode |
| Matchmaking / Lobby | Search, lobby state, match handoff | HTTP/REST + hub; handoff | Observed | Observed, not delivered | Understanding the handoff ≠ delivering a match |
| Match Server | Live battlefield simulation | Real-time UDP (UE4.21 netcode reference) | The actual game | **Stage 2 — not done** | You cannot replay a simulation; this is a different kind of problem |

*All endpoint specifics are generic/sanitised. Protocol types are the generic families the architecture uses, not target-specific addresses.*

## 2.3 The critical distinction: replay vs simulation

The menu layers (identity, profile, hub, presence) are dominated by **replaying fixed responses** and maintaining a couple of live connections. That is why Stage 1 could reach a stable menu.

The match server is **live simulation**: it must compute new world state in response to inputs it has never seen. No amount of replaying past matches produces that. This is why Stage 1 (menu) and Stage 2 (matches) are separated in every RecompileLabs communication, and why the operator must never let one imply the other.

## 2.4 KNOWLEDGE CHECK 2.1 — Diagnose the failing layer

You are handed the boot log of an unknown online game. Identify which architectural layer is *probably* failing, and why.

**Sample boot log (sketch):**

```
[00.11] client start
[00.42] auth/login            → OK   (identity established, token received)
[00.55] profile/get           → OK   (progression, inventory loaded)
[00.58] menu: begin populate
[01.03] menu: populated       (level, loadouts, unlocks visible)
[01.04] hub: opening persistent channel
[01.06] hub: connected
[01.10] hub: keep-alive expected
[01.51] hub: no keep-alive sent for 40s → server closed channel
[01.51] UI: "Lost connection to the communication service"
[01.52] hub: reconnecting…
[01.55] hub: connected
[02.35] hub: no keep-alive sent for 40s → server closed channel
[02.35] UI: "Lost connection to the communication service"
```

### Model answer

**Failing layer: Hub / Menu Control (the persistent WebSocket switchboard).**

**Reasoning.** Identity and profile both return OK and the menu fully populates — so those layers are healthy; the problem is downstream of them. The failure is specifically that a *persistent* connection is opened successfully but then dropped on a repeating cycle (connect → ~40s silence → server closes → reconnect). The signature is a **liveness/keep-alive** problem: the connection is not being kept alive with correctly-timed signalling, so the far end times it out. This is exactly the *kind* of failure described for the hub layer — a live connection that needs ongoing behaviour, not just a correct handshake. The presence layer would show a similar looping-disconnect symptom, so a second check is *which* channel the "communication service" message refers to; here the log attributes it to the hub channel and its missing keep-alive, which points at the hub. The fix direction (per the WW3 worked case) is to supply correctly-timed keep-alive/heartbeat behaviour so the connection holds — a *behavioural* fix, confirming that this layer cannot be satisfied by replay alone.

---

# MODULE 3 — RECONNAISSANCE (DISCOVER BEFORE YOU BUILD)

The cardinal error of the inexperienced operator is to start building a stand-in service based on a guess about what the client wants. You will guess wrong, waste effort, and — worse — you will not *know* you guessed wrong. The discipline of this module is simple: **discover the system through legitimate observation first; build only what the evidence demands.**

All observation in this module is of a system you are authorized to run, in an isolated environment, on an owned copy. Reconnaissance here means watching your *own* client talk, in your *own* lab.

> **⚠ STOP CONDITION**
> Before any reconnaissance begins, confirm the authorization envelope: you are observing software you own, in an isolated environment, that you are authorized to run. If you cannot confirm that, **stop** — this is not a technical decision, it is a scope-and-rights decision, and it is owned by the operator (Module 1). Do not intercept, redirect, or analyse traffic that is not yours to observe.

## 3.1 The required questions

A complete reconnaissance answers these before a single stand-in is built:

**Process & load:**
- [ ] What processes start when the game launches?
- [ ] What executables and libraries load?

**Network shape:**
- [ ] What domains does the client resolve?
- [ ] What IP addresses and ports does it contact?
- [ ] Which connections are TCP, UDP, HTTP, WebSocket, or other?

**Sequence:**
- [ ] What happens, in order, *before* the menu appears?
- [ ] What happens when the player presses **Play**?

**Criticality:**
- [ ] Which failure actually stops progression?
- [ ] Which calls are essential versus optional telemetry / noise?

**Persistence & change:**
- [ ] What is cached locally?
- [ ] What changes after a reboot?
- [ ] What changes after a token / credential expires?
- [ ] Which behaviour depends on live infrastructure, and which is entirely client-side?

The last cluster is the highest-leverage. The difference between "this needs a live service" and "this is done locally on the client" determines *how much* you have to build. Much of the art of reaching a menu is discovering that a surprising amount is client-side or cache-able, and that the truly live dependencies are fewer than they first appear.

## 3.2 Evidence sources

Reconnaissance draws on many sources. No single one is sufficient; the picture comes from correlating them by timestamp.

| Source | What it tells you |
|---|---|
| Process trees | What actually runs, and what launches what |
| Application logs | The client's own account of what it tried and what failed |
| Launcher logs | Pre-game steps, updates, and handoffs |
| DNS logs | Which server names the client wants to reach |
| Connection timelines | The order and timing of contacts |
| Packet captures | The actual traffic (of your own, authorized client) |
| Endpoint inventories | The catalogue of distinct services contacted |
| Request/response bodies | Exactly what is asked and answered |
| Filesystem changes | What is written, cached, or read locally |
| Registry changes | Local configuration the client depends on |
| Config files | Declared settings, endpoints, toggles |
| Crash dumps | The precise point and reason a boot dies |
| Screenshots | Visual state at each stage (empty vs populated menu) |
| Video | The lived sequence, timed against the logs |
| Timestamps | The spine that ties every other source together |

**SYSTEM VIEW.** Reconnaissance is the construction of a correlated event timeline across heterogeneous telemetry sources, from which you derive a dependency graph (who calls whom, in what order, gated on what) and a criticality annotation (essential vs optional) per edge. The output is a model precise enough that a stand-in's required behaviour is specified by evidence rather than assumption.

**OPERATOR VIEW.** You are reconstructing the game's launch-day routine like an investigator rebuilding a timeline: who did it call, in what order, what did it need to hear back, and where exactly did it stop when things went wrong. You gather every kind of record you can — its diary (logs), its phone records (DNS/connections), the recordings (captures), the notes it left on the desk (cache/config) — and you line them all up by the clock. When they agree, you have a fact. When they don't, you have a question worth chasing.

## 3.3 The Reconnaissance Worksheet

Copy this template for every new target. Fill it in from evidence, not memory. Leave "UNKNOWN AREAS" honest — an admitted unknown is worth more than a confident guess.

```
============================================================
RECONNAISSANCE WORKSHEET
============================================================
PROJECT:                     ____________________________
TARGET BUILD:                ____________________________
OWNERSHIP / AUTHORIZATION:   ____________________________
   (owned copy? isolated env? authorized to run? Y/N + note)
CURRENT DATE:                ____________________________
SHUTDOWN DEADLINE:           ____________________________

------------------------------------------------------------
KNOWN PROCESSES:
   - __________________________________________________
KNOWN DOMAINS:
   - __________________________________________________
KNOWN PORTS:
   - __________________________________________________
KNOWN PROTOCOLS:  (HTTP/REST · WebSocket · XMPP-style · UDP · other)
   - __________________________________________________

------------------------------------------------------------
BOOT SEQUENCE (in order, before menu):
   1. ________________________________________________
   2. ________________________________________________
   3. ________________________________________________
   ...
FIRST CONFIRMED FAILURE:
   - Layer:   ________________________________________
   - Symptom: ________________________________________
   - Timestamp / log line: ___________________________

------------------------------------------------------------
AVAILABLE LOGS:
   - __________________________________________________
AVAILABLE CAPTURES:
   - __________________________________________________

------------------------------------------------------------
UNKNOWN AREAS (be honest):
   - __________________________________________________
   - __________________________________________________

NEXT OBSERVATION ACTION:
   - __________________________________________________
============================================================
```

## 3.4 Worked example — WW3 service-chain discovery

*(Legitimate local observation of an owned, isolated client only.)*

RecompileLabs opened the WW3 investigation exactly this way. While the official service was still live, a **passive recorder observed the legitimate client↔server traffic** of an owned copy, and a **live dashboard displayed the captured service activity** as it happened. Sensitive personal data was **redacted at capture time**, so the record was safe from the start.

That reconnaissance produced the dependency picture Module 2 describes: identity → profile/meta → hub → presence → matchmaking → match, with the observed flows including login, profile, progression, inventory, loadouts, season data, menu-service messages, matchmaking search, lobby state, and the match-start handoff. Crucially, it also answered the *criticality* questions — which contacts had to succeed to reach the menu, and which were peripheral — which is what made a bounded Stage 1 possible.

A partially-filled worksheet from that work reads (sanitised):

```
PROJECT:                     WW3 Backend Continuity — Stage 1
TARGET BUILD:                WW3 (App 674020), UE4.21, multiplayer-only
OWNERSHIP / AUTHORIZATION:   Owned copy; isolated local env; authorized. Y
SHUTDOWN DEADLINE:           2026-08-03

KNOWN PROTOCOLS:             HTTP/REST (identity, profile) ·
                             WebSocket (hub) · XMPP-style (presence) ·
                             UDP (match — Stage 2)
BOOT SEQUENCE:
   1. identity / login exchange
   2. profile / meta fetch (progression, inventory, loadouts, season)
   3. hub persistent channel opens
   4. presence session establishes
   5. [Play] → matchmaking search → lobby → match handoff  (observed)
FIRST CONFIRMED FAILURE (initial):  identity gate rejects an
                             unacceptable login → client halts
AVAILABLE CAPTURES:          passive recorder logs; live dashboard;
                             PII redacted at capture
UNKNOWN AREAS (early):       exact keep-alive timing on hub/presence;
                             which match bytes carry which state (Stage 2)
NEXT OBSERVATION ACTION:     segment match captures by activity for
                             Stage 2 feasibility (separate effort)
```

> **⚠ WARNING**
> This worked example is about observing *your own, authorized* client in an isolated lab. This manual does **not** teach, and you must not perform, interception or redirection of protected traffic that is not yours to observe. Reconnaissance is a discovery discipline applied to systems you are authorized to run — never a pretext for touching anyone else's traffic.

The reconnaissance is what turned "we have no idea what this game needs" into "we have an ordered, evidence-backed dependency map with the critical path marked." Everything RecompileLabs built afterward was specified by that map. That is the entire point of *discover before you build*.

---

# MODULE 4 — EVIDENCE CLASSIFICATION

An investigation is only as trustworthy as its weakest unlabelled claim. The single most dangerous sentence in technical work is one that *sounds* like a fact but is actually a guess. This module installs the RecompileLabs evidence taxonomy so that never happens silently.

## 4.1 The taxonomy

Every major claim in every RecompileLabs report is labelled with exactly one of these:

| Label | Meaning |
|---|---|
| **OBSERVED** | Directly witnessed in evidence. You can point to the log line, the capture, the screenshot. It happened and you saw it. |
| **INFERRED** | Not directly witnessed, but supported by multiple independent observations that together make it the best explanation. |
| **HYPOTHESIS** | A single candidate explanation, not yet supported by multiple observations. A guess worth testing — and clearly marked as a guess. |
| **IMPLEMENTED** | A change or component has been built. Note: *built* is not *proven to work* — that is VALIDATED. |
| **VALIDATED** | An implemented thing has been confirmed to work, reproducibly, against evidence. |
| **REGRESSION** | Something that previously worked (was VALIDATED) has been observed to fail again. |
| **EXTERNAL DEPENDENCY** | The behaviour depends on something outside your control (a third party, a live service, a rights-held component). |
| **UNKNOWN** | Honestly unresolved. Not guessed, not glossed — flagged as open. |

Three of these deserve special emphasis:

- **IMPLEMENTED ≠ VALIDATED.** "We built the stand-in" and "the stand-in demonstrably works, repeatably" are different claims. Conflating them is how demos get mistaken for deliverables.
- **VALIDATED can become REGRESSION.** A result is validated *as of* a moment and a configuration. If the configuration changes and it breaks, it regressed — say so.
- **UNKNOWN is a first-class label, not a failure.** Marking something UNKNOWN is stronger and more useful than dressing a guess up as an inference.

## 4.2 The decision tree

Use this every time you are about to write a claim that isn't already IMPLEMENTED/VALIDATED/REGRESSION/EXTERNAL/UNKNOWN:

```
                Can I point to direct evidence?
                (a specific log line, capture, screenshot)
                        |
              +---------+---------+
              | YES               | NO
              v                   v
          OBSERVED       Do multiple independent
                         observations support it?
                                  |
                        +---------+---------+
                        | YES               | NO
                        v                   v
                    INFERRED           HYPOTHESIS
```

**SYSTEM VIEW.** The taxonomy is an epistemic type system for claims. Each label encodes evidential provenance and strength; the decision tree is the type-inference rule for the three graded confidence levels. Labelling is mandatory because unlabelled claims default, in the reader's mind, to the strongest interpretation — which is precisely the failure the type system exists to prevent.

**OPERATOR VIEW.** It's a discipline for never letting a hunch wear the costume of a fact. Before you write down anything technical, ask: can I *point* to it? If yes, it's OBSERVED — the gold standard. If not, do several separate clues agree? Then it's INFERRED — solid but not witnessed. If it's just one plausible idea, it's a HYPOTHESIS — say so out loud, and go test it. The labels cost you nothing and protect everything.

## 4.3 Why AI agents collapse these categories

AI agents are fluent. Fluency is exactly the hazard. An agent asked "why is the connection dropping?" will readily produce a confident, well-written explanation — and that explanation, written in the same authoritative tone whether it is OBSERVED or pure HYPOTHESIS, *reads* like a fact. Agents:

- Rarely volunteer the distinction between "the log shows this" and "this is a plausible cause."
- Tend to smooth a HYPOTHESIS into declarative prose ("the heartbeat is missing") rather than tentative prose ("a missing heartbeat is one candidate").
- Will present an INFERRED conclusion and an OBSERVED one in identical register.
- Can produce a fluent rationale for a claim that no evidence supports at all.

This is why the operator (not the agent) owns the evidence structure. When an agent hands you an explanation, your job is to *re-label it*: strip the confident tone, ask "what could you point to?", and downgrade anything that can't survive the decision tree.

## 4.4 The rule

> **Every technical report must label its major claims using this taxonomy.**

No exceptions. A report where the reader cannot tell OBSERVED from HYPOTHESIS is not a RecompileLabs report. The labelling is the product's integrity.

## 4.5 EXERCISE 4.1 — Classify the WW3 examples

Classify each of the following, and give the reasoning.

1. A successful menu boot that you watched happen and captured on video.
2. A suspected heartbeat problem you think might be causing disconnects, before testing.
3. A recurring presence disconnect seen across many boots, each logged.
4. Match traffic that "looks readable" based on measurement.
5. A proposed Stage 2 match server.
6. A one-time launch that succeeded once and hasn't been repeated.
7. A stable launch that succeeds again cleanly after a reboot.

### Model answer

| # | Example | Label | Reasoning |
|---|---|---|---|
| 1 | Menu boot you watched and captured | **OBSERVED** | You can point to direct evidence (video + capture). It was directly witnessed. |
| 2 | Suspected heartbeat problem, untested | **HYPOTHESIS** | A single candidate explanation, not yet supported by multiple observations. Worth testing — and it must be labelled as a guess until tested. |
| 3 | Recurring presence disconnect across many logged boots | **INFERRED** (the *cause*) / **OBSERVED** (the *disconnects*) | The disconnects themselves are OBSERVED — logged repeatedly. The conclusion that they share a common cause is INFERRED from multiple consistent observations. Keep the two claims separately labelled. |
| 4 | Match traffic "looks readable" per measurement | **INFERRED** | The measurement is OBSERVED; the conclusion "this is readable/uncompressed rather than encrypted" is an inference from multiple consistent measurements. It is explicitly *not* proof that Stage 2 works — feasibility, not completion. |
| 5 | Proposed Stage 2 match server | **HYPOTHESIS** (as a plan) — never IMPLEMENTED/VALIDATED | It is a proposal. Nothing is built and nothing is proven. Labelling it anything stronger would be exactly the exaggeration Module 1 forbids. |
| 6 | One-time launch success | **OBSERVED but NOT VALIDATED** | You observed one success. Validation requires *reproducibility*; a single occurrence is not yet validated. Do not report it as "stable." |
| 7 | Stable launch, succeeds again after reboot | **VALIDATED** | An implemented result confirmed to work reproducibly across a state change (reboot). This is the standard a "stable" claim must meet. |

The pair to burn in is #6 and #7: **one success is OBSERVED; repeated success across a reboot is VALIDATED.** "It worked" and "it reliably works" are different claims, and only the second earns the word *stable*.

---

# MODULE 5 — THE CURRENT WALL (ONLY ONE WALL MATTERS AT A TIME)

An investigation drowns when it chases many problems at once. The RecompileLabs method is deliberately narrow:

```
ONE WALL  →  ONE HYPOTHESIS  →  ONE BOUNDED CHANGE  →  ONE SMOKE TEST  →  ONE RECORDED RESULT
```

You take the single current wall. You form one hypothesis about it. You make the smallest change that could disprove that hypothesis. You run one quick test. You record one result — and *then* you decide the next wall. Anything wider than this and you lose the thread of what caused what.

## 5.1 Definition

> **CURRENT WALL: the earliest confirmed failure that prevents the project from advancing to the next agreed milestone.**

Three words carry the weight:

- **Earliest** — not the most interesting, not the most annoying, not the most impressive-to-fix. The *first* one on the path. Because of the service-chain ordering (Module 2), a later failure often *can't even be reached* until the earlier one is cleared, and "fixing" a downstream bug while an upstream gate is closed is wasted motion.
- **Confirmed** — you have OBSERVED it (Module 4), not merely suspect it.
- **To the next agreed milestone** — the wall is defined relative to a specific, agreed target (e.g., "reach a stable menu"), not relative to some distant end state.

**SYSTEM VIEW.** The current wall is the earliest unsatisfied precondition on the critical path to the next milestone. Because the service chain is largely sequential, precedence dominates severity: an upstream blocker strictly gates all downstream progress, so the correct scheduling policy is "earliest confirmed blocker first," regardless of the perceived interest or difficulty of downstream issues.

**OPERATOR VIEW.** Fix the door you're actually standing at, not the fascinating lock three rooms deeper that you can't even reach yet. There is always exactly one door blocking you right now. Find it, prove it's the one, open it, write down what happened, and only then look for the next door. Chasing the exciting bug behind a door you haven't opened is how weeks disappear.

> **⚠ STOP CONDITION**
> If you cannot state the current wall in one sentence as "the earliest *confirmed* failure blocking [named milestone]," you are not ready to act. **Stop and go back to reconnaissance and evidence classification.** Acting without a confirmed, singular wall is how bounded experiments turn into thrashing.

## 5.2 Why earliest, not most interesting

The most interesting bug is a trap. It is interesting precisely because it is deep, subtle, or novel — which usually means it is *downstream*, behind gates that aren't open yet. If you fix it, you often can't even verify the fix (the path to trigger it is blocked), and you certainly haven't advanced the milestone. The earliest confirmed wall, by contrast, is boring and decisive: clearing it is the only move that actually lets the client take its next step.

## 5.3 The Wall Record template

Every wall gets one of these, filled from evidence. This is mandatory. It is the unit of progress.

```
============================================================
WALL RECORD
============================================================
WALL ID:                 ____________________________
DATE:                    ____________________________
MILESTONE TARGET:        ____________________________
LAST KNOWN WORKING STATE:____________________________

------------------------------------------------------------
OBSERVED FAILURE:        ____________________________
EXACT ERROR OR SYMPTOM:  ____________________________
TIMESTAMP:               ____________________________
RELATED LOGS:            ____________________________
RELATED FILES:           ____________________________

------------------------------------------------------------
DIRECT EVIDENCE (OBSERVED):
   - __________________________________________________
INFERENCES (INFERRED):
   - __________________________________________________

------------------------------------------------------------
CURRENT HYPOTHESIS:      ____________________________
ALTERNATIVE HYPOTHESES:  ____________________________
EVIDENCE SUPPORTING:     ____________________________
EVIDENCE AGAINST:        ____________________________

------------------------------------------------------------
SMALLEST DISPROVING EXPERIMENT:
   - __________________________________________________
EXPECTED RESULT:         ____________________________
ROLLBACK PLAN:           ____________________________

------------------------------------------------------------
ACTUAL RESULT:           ____________________________
CLASSIFICATION:          ____________________________
   (OBSERVED / INFERRED / VALIDATED / REGRESSION / ...)
DECISION:                ____________________________
NEXT WALL:               ____________________________
============================================================
```

The **smallest disproving experiment** deserves attention: you want the least change that, if your hypothesis is wrong, will *show* it is wrong. Disproof is faster and more honest than proof. And the **rollback plan** is non-negotiable — every bounded change must be reversible, so a failed experiment costs you a test, not your working state.

## 5.4 Worked examples (process only)

These are the WW3 Stage 1 walls, filled as records. They contain **no** sensitive forgery, key, or bypass detail — only the *shape* of the investigation. Sensitive specifics remain **[INTERNAL IMPLEMENTATION DETAIL]**.

### Wall 1 — Initial login dependency

```
WALL ID:                 W1-IDENTITY
MILESTONE TARGET:        Reach main menu, isolated env
LAST KNOWN WORKING STATE:Client launches; halts at identity gate
OBSERVED FAILURE:        Client stops at/near first screen when the
                         identity exchange is not satisfied
EXACT SYMPTOM:           Login rejected → boot halts   (OBSERVED)
DIRECT EVIDENCE:         Launch log shows identity exchange as the
                         first outbound step and the halt point
INFERENCES:              Nothing downstream is reachable until identity
                         is satisfied (INFERRED from chain ordering)
CURRENT HYPOTHESIS:      A valid-shaped identity response, served
                         locally in the isolated env, lets boot proceed
ALTERNATIVE HYPOTHESES:  The gate also requires a live third-party
                         check (see Wall 4)
SMALLEST DISPROVING EXP.:Serve a valid-shaped identity response locally;
                         observe whether boot advances past the gate
                         [sensitive mechanics: INTERNAL IMPLEMENTATION DETAIL]
EXPECTED RESULT:         Boot advances to the profile-fetch step
ROLLBACK PLAN:           Remove local stand-in; revert to prior config
ACTUAL RESULT:           Boot advanced to profile fetch   (OBSERVED)
CLASSIFICATION:          OBSERVED → later VALIDATED (repeatable)
DECISION:                Identity gate satisfiable in isolated env
NEXT WALL:               W2-PROFILE
```

### Wall 2 — Profile service dependency

```
WALL ID:                 W2-PROFILE
MILESTONE TARGET:        Reach main menu (populated)
LAST KNOWN WORKING STATE:Past identity; menu opens but empty/hanging
OBSERVED FAILURE:        Menu does not populate without profile data
EXACT SYMPTOM:           Empty/partial menu; client awaits profile
                         (OBSERVED)
DIRECT EVIDENCE:         Captured profile/inventory/progression/season
                         responses; client requests them post-identity
CURRENT HYPOTHESIS:      Serving a locally-supplied synthetic profile
                         populates the menu fully
SMALLEST DISPROVING EXP.:Serve the synthetic profile from the local
                         profile/meta stand-in; observe menu state
EXPECTED RESULT:         Fully-populated menu
ROLLBACK PLAN:           Revert to empty stand-in response
ACTUAL RESULT:           Fully-populated menu reached   (OBSERVED)
CLASSIFICATION:          VALIDATED (reproducible)
DECISION:                Profile layer satisfiable by replay in isolation
NEXT WALL:               W3-HUB-HEARTBEAT
```

### Wall 3 — Unstable hub heartbeat

```
WALL ID:                 W3-HUB-HEARTBEAT
MILESTONE TARGET:        Stable menu (no disconnect loop)
LAST KNOWN WORKING STATE:Menu populates, then shows connection-lost loop
OBSERVED FAILURE:        Hub persistent channel dropped on a repeating
                         cycle
EXACT SYMPTOM:           "Lost connection to communication service";
                         reconnect loop (OBSERVED)
DIRECT EVIDENCE:         Connection timeline shows connect → silence →
                         server-side close, repeating
INFERENCES:              Keep-alive/liveness behaviour is not being
                         maintained correctly (INFERRED)
CURRENT HYPOTHESIS:      The stand-in isn't supplying correctly-timed
                         keep-alive, so the far end times it out
ALTERNATIVE HYPOTHESES:  Handshake incomplete; message shape wrong
SMALLEST DISPROVING EXP.:Supply correctly-timed keep-alive behaviour;
                         observe whether the channel holds
EXPECTED RESULT:         Channel stays open; loop stops
ROLLBACK PLAN:           Revert keep-alive change
ACTUAL RESULT:           Channel held steady   (OBSERVED)
CLASSIFICATION:          VALIDATED
DECISION:                Hub stability requires behavioural liveness,
                         not just replayed messages
NEXT WALL:               W4-PRESENCE-IDENTITY
```

### Wall 4 — Presence identity mismatch (XMPP-style)

```
WALL ID:                 W4-PRESENCE-IDENTITY
MILESTONE TARGET:        Stable menu (social layer stable)
LAST KNOWN WORKING STATE:Hub stable; presence still resets periodically
OBSERVED FAILURE:        Presence session resets on a loop
EXACT SYMPTOM:           Recurring communication-service reset
                         (OBSERVED)
DIRECT EVIDENCE:         Presence session asserts an identity that does
                         not match the identity the client declares;
                         session torn down repeatedly
INFERENCES:              The identity inconsistency is what the client
                         cannot reconcile (INFERRED)
CURRENT HYPOTHESIS:      Using a consistent identity that matches the
                         client's own declaration stops the resets
SMALLEST DISPROVING EXP.:Make the presence identity consistent with the
                         client's declared identity; add correct
                         keep-alive; observe stability
EXPECTED RESULT:         Presence session holds; resets stop
ROLLBACK PLAN:           Revert identity/keep-alive change
ACTUAL RESULT:           Presence stable   (OBSERVED)
CLASSIFICATION:          VALIDATED
DECISION:                Identity consistency across a live session is a
                         genuine stability requirement
NEXT WALL:               W5-STAGE2-TRANSITION
```

### Wall 5 — Transition from Stage 1 to match-server investigation

```
WALL ID:                 W5-STAGE2-TRANSITION
MILESTONE TARGET:        Decide feasibility of Stage 2 (playable match)
LAST KNOWN WORKING STATE:Stage 1 complete: stable, populated menu
OBSERVED FAILURE:        No playable match — match server does not exist
                         (this is a scope boundary, not a bug)
EXACT SYMPTOM:           "Play" cannot resolve into a live match; no
                         simulation on the other end (OBSERVED)
DIRECT EVIDENCE:         Match traffic captured and segmented by activity
                         (standing/walking/running/driving/combat)
INFERENCES:              Match traffic appears structured/readable rather
                         than strongly encrypted (INFERRED from
                         measurement); UE4.21 netcode is the reference
CURRENT HYPOTHESIS:      Stage 2 is FEASIBLE but unbuilt — a live
                         simulation, not a replay problem  (HYPOTHESIS
                         as a plan; NOT implemented, NOT validated)
SMALLEST DISPROVING EXP.:(Feasibility analysis only) measure structure
                         of match captures; compare across activities
EXPECTED RESULT:         Determine readable vs encrypted → go/no-go on
                         committing to Stage 2 engineering
ROLLBACK PLAN:           N/A — analysis only, no client change
ACTUAL RESULT:           Traffic appeared readable/structured →
                         feasibility judgment, NOT a completed feature
CLASSIFICATION:          INFERRED (feasibility) — explicitly NOT
                         IMPLEMENTED / NOT VALIDATED
DECISION:                Stage 2 is a much larger, separate, unfinished
                         effort. Menu ≠ match. Do not claim playability.
NEXT WALL:               (Stage 2 scope — out of this milestone)
```

> **⚠ WARNING**
> Wall 5 is where the temptation to exaggerate is strongest. "Feasible" is an INFERRED judgment about readability, not a match server. The correct, honest output of Wall 5 is a *feasibility verdict and a scope boundary* — Stage 1 reaches a stable menu; Stage 2 (playable matches) is a much larger effort that is **not done**.

---

# MODULE 6 — OBSERVE, REPLAY, EMULATE

This module gives you the language to say *exactly how real* a component is. The single most common overclaim in recovery work is treating "we replayed a recording and the menu appeared" as "we built the service." The maturity ladder below makes that impossible to do by accident.

## 6.1 The ten-step progression

```
OBSERVE → RECORD → REPLAY → PARAMETERIZE → MAINTAIN STATE →
EMULATE BEHAVIOR → VALIDATE STABILITY → HARDEN → DOCUMENT → HAND OVER
```

| Step | What it means |
|---|---|
| **OBSERVE** | Watch the real system's legitimate traffic in an authorized, isolated setting. |
| **RECORD** | Capture that traffic faithfully (with sensitive data redacted at capture time). |
| **REPLAY** | Serve the captured responses back to the client. |
| **PARAMETERIZE** | Vary the replayed responses by request inputs, so different requests get appropriately different (still fixed-form) answers. |
| **MAINTAIN STATE** | Track session/player state across requests so responses stay consistent over a session. |
| **EMULATE BEHAVIOR** | Actually *behave* like the service — respond to inputs not seen in the recording, keep live connections alive, enforce the real semantics. |
| **VALIDATE STABILITY** | Confirm the emulation holds up reproducibly, across reboots and over time. |
| **HARDEN** | Make it robust to edge cases, timing, and error conditions. |
| **DOCUMENT** | Record how it works so it can be reconstructed and audited. |
| **HAND OVER** | Package it so another operator or specialist can own it. |

The ladder is also a *diagnosis*: whatever step a component last reached is its honest maturity. A component that has been REPLAYed but never EMULATEd cannot answer a request it never recorded — and you must not claim it can.

## 6.2 Implementation maturity levels

Each component is at exactly one of these. Say which, every time.

| Maturity | Meaning |
|---|---|
| **STATIC RESPONSE** | Returns one fixed answer regardless of the request. The crudest stand-in. |
| **PARAMETERIZED RESPONSE** | Returns different fixed-form answers depending on request inputs, but holds no memory between requests. |
| **STATEFUL MOCK** | Tracks state across a session so answers stay consistent, but does not truly reproduce the service's behaviour. |
| **BEHAVIORAL EMULATOR** | Reproduces the service's actual behaviour — responds correctly to inputs it never recorded, maintains live connections, honours the real semantics. |
| **FUNCTIONAL SERVICE RECONSTRUCTION** | A genuine re-implementation of the service's function, not just its observable surface. |
| **PRODUCTION-READY SERVICE** | Robust, hardened, documented, and fit to run as a dependable service. |

**SYSTEM VIEW.** Maturity measures how far a component generalises beyond its recorded inputs. STATIC and PARAMETERIZED are pure functions of the current request (no memory); STATEFUL adds session memory; BEHAVIORAL adds correct response to unrecorded inputs and live-connection semantics; RECONSTRUCTION re-implements the underlying function; PRODUCTION adds robustness and operability. The key threshold is between STATEFUL MOCK and BEHAVIORAL EMULATOR: below it you can only answer what you have seen; above it you can answer what you have not.

**OPERATOR VIEW.** It's a scale from "a cardboard cut-out" to "a real working stand-in." A cardboard cut-out (static) always says the same thing. A slightly better prop (parameterized) says one of a few pre-written lines depending on what you ask. A stand-in with a memory (stateful) remembers the conversation so far. A genuine impersonator (behavioural emulator) can handle questions nobody scripted — *that's* the big leap. Beyond that is actually rebuilding the thing (reconstruction) and making it rugged enough to rely on (production). The trap is calling a cardboard cut-out a stand-in because, from one angle in good lighting, it looked real.

## 6.3 The core caution

> **⚠ WARNING**
> Reaching the menu through replay does **not** demonstrate that a full multiplayer simulation exists — or is even close. The menu layers can largely be satisfied at STATIC/PARAMETERIZED/STATEFUL maturity plus a little behavioural liveness on the persistent connections. A match server is a live simulation and demands BEHAVIORAL EMULATION (and far beyond). "The menu loads" and "the game is playable" are separated by the widest gap in the whole project. Never let a low-maturity success imply a high-maturity capability.

## 6.4 Component classification (WW3 Stage 1)

Sensitive components are described in sanitised terms; concrete mechanics are **[INTERNAL IMPLEMENTATION DETAIL]**.

| COMPONENT | CURRENT MATURITY | WHAT IT DEMONSTRATES | WHAT IT DOES NOT DEMONSTRATE | NEXT MATURITY STEP |
|---|---|---|---|---|
| **Login / identity layer** | STATEFUL MOCK (isolated env) | The client can pass the identity gate and proceed to boot in an isolated, owned-copy setting | That identity is production-robust, or valid against any live third party | Harden and document; keep sensitive parts under specialist review |
| **Profile / meta layer** | STATEFUL MOCK | A synthetic profile populates a full menu, consistently within a session | That profile mutations behave like the real service over long play | Behavioural emulation of state-changing operations |
| **Hub (menu control)** | BEHAVIORAL EMULATOR (minimal) | A persistent channel stays alive with correct keep-alive timing; menu stays stable | Full hub semantics beyond keeping the menu alive | Broaden behavioural coverage; harden edge cases |
| **Presence / social** | BEHAVIORAL EMULATOR (minimal) | A live presence session holds with consistent identity; social layer stable | Full presence/social feature set | Broaden coverage; harden; document |
| **Third-party identity dependency (sanitised)** | STATEFUL MOCK — sensitive; **[INTERNAL IMPLEMENTATION DETAIL]** | *A locally controlled replacement was introduced for a third-party identity dependency within the isolated test environment*, allowing boot to proceed | Anything reusable; anything valid outside the isolated env; anything about the real third party | **[RIGHTS-HOLDER AUTHORIZATION REQUIRED]** + specialist review before any further maturity |
| **Match layer** | OBSERVE only (Stage 2) | Match traffic was captured and appears structured/readable (feasibility) | Any playable match; any working simulation | BEHAVIORAL EMULATION — a large, separate, unfinished Stage 2 effort |

The shape of this table is the honest summary of Stage 1: the menu-serving components reached STATEFUL MOCK or minimal BEHAVIORAL EMULATION — enough for a stable, populated menu in an isolated environment — while the match layer has only been OBSERVED. Menu maturity is real and bounded. Match maturity does not yet exist.

> **⚠ STOP CONDITION**
> Before advancing the maturity of the sanitised third-party identity dependency, or before doing any Stage 2 match-server engineering, **stop for two checks:** (1) authorization and rights — **[RIGHTS-HOLDER AUTHORIZATION REQUIRED]** — and (2) specialist review, because both cross into high-risk, high-assurance territory (Module 1's STOP CONDITION). Neither an operator's enthusiasm nor an AI agent's willingness substitutes for those two gates.
