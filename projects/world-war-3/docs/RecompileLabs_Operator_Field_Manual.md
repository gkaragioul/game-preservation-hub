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
- B. The stand-in binding a stale player ID (prod-<stale-id>) the client could not reconcile with its own (prod-<current-id>). **← CORRECT**
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

*Scenario:* You task an agent to bring up the three stand-in services and confirm the client reaches the menu. It returns: "All services healthy. Main menu reached. Stage 1 complete." You open the run log and see the identity and meta calls returned 200, the hub connected, but the presence (XMPP) stream shows repeated `stream reset` entries and a `bound JID prod-<stale-id>` line while the client announces `prod-<current-id>`.

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
