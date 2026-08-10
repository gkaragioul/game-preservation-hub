# RECOMPILELABS OPERATOR FIELD MANUAL — VOLUME II

**Binary Protocol Reconstruction and Live-System Iteration**

---

**Classification:** PRIVATE INTERNAL TRAINING DOCUMENT
**Prepared for:** Repository Owner, Founder & Technical Producer, RecompileLabs
**Primary worked case:** World War 3 (Steam App 674020), Unreal Engine 4.21 — Stage 2, match-server reconstruction
**Companion volume:** Volume I — Legacy Game Recovery and Backend Continuity (Stage 1)
**Revision:** 1.0

---

## Classification Notice

This is an internal training document. Volume I taught how to run a recovery investigation against a *service* — request/response systems where the questions are readable and the answers can be learned by observation. Volume II teaches the harder discipline: reconstructing an **undocumented binary protocol** and iterating against a **live system that cannot tell you what is wrong**.

The same redaction rules apply throughout:

- Specific credential, certificate, token, key, and endpoint values → **[REDACTED]**
- Personal identifiers captured during observation → **[SANITIZED]**
- The exact mechanics of sensitive substitutions → **[INTERNAL IMPLEMENTATION DETAIL]**
- Anything whose reuse would require permission from a rights-holder → **[RIGHTS-HOLDER AUTHORIZATION REQUIRED]**

> **⚠ WARNING**
> This volume teaches evidence discipline and diagnostic method. Bit layouts shown are illustrative of *reasoning*, not a transferable recipe. If you find yourself wanting a section to hand you bytes to copy, stop and route that need to an authorized specialist under the escalation rules in Volume I, Module 1.

---

## Intended Audience

Operators who have completed Volume I and can already run a service-chain investigation. Volume II assumes you can capture traffic, classify evidence, and identify the current wall. It adds the capability to work where **there is no text on the wire and no error message when you are wrong**.

---

## Scope

**In scope:** binary format reconstruction, verification by exact reproduction, live-system iteration loops, reading failure signals from timing and behaviour, the replay/simulation boundary, and knowing when a line of investigation is exhausted.

**Out of scope:** anti-cheat circumvention, credential forging mechanics, redistribution of protected assets, and any concrete implementation detail whose reuse would require rights-holder authorization.

---

## Learning Outcomes

On completion, an operator can:

1. Reconstruct an undocumented binary format from traffic recordings using inference plus exact-reproduction proof
2. State and apply the **round-trip standard** as the only acceptable evidence of understanding
3. Design a live-iteration loop that isolates one variable per test against a system that returns no diagnostics
4. Read **timing and behaviour** as primary diagnostic data
5. Distinguish **replay** from **simulation**, and predict which problems each can solve
6. Recognise a **plateau** and correctly classify it as "needs different knowledge" rather than "needs more data"
7. Detect and correct their own premature conclusions on contact with new evidence

---

## Competency-Level System

| Level | Description |
|---|---|
| **L1 — Observer** | Can capture and classify binary traffic; recognises structure but cannot yet prove it |
| **L2 — Reconstructor** | Can recover field layouts and prove them by exact reproduction |
| **L3 — Iterator** | Can run disciplined live-system loops and diagnose from behaviour alone |
| **L4 — Boundary Setter** | Can identify plateaus, classify remaining work, and state limits without overclaiming |

---

# MODULE 1 — WHEN THE WIRE HAS NO WORDS

## 1.1 The change of problem

Volume I dealt with systems that answer questions. Binary game protocols do not answer questions — they **assert state**, continuously, in a packed format with no field names, no delimiters, and no version information.

Three properties define the work:

1. **No self-description.** There is nothing on the wire telling you where a field starts or what it means.
2. **No tolerance.** One bit wrong shifts every subsequent field. There is no "mostly correct."
3. **No diagnostics.** A wrong guess produces silence or a disconnection, never an explanation.

## 1.2 Why "it decodes plausibly" is not evidence

The most dangerous failure mode in this work is a decoder that produces *sensible-looking* output from a *wrong* model. Field widths that are slightly wrong still yield numbers. Numbers still look like data. Confidence rises while accuracy does not.

In the worked case, an entire class of messages had been decoding into implausible values for a long period. The operator had explained this away as "a part of the format not yet reversed." The evidence of the defect was present in the recordings the whole time; the interpretation was wrong.

> **RULE 1.1 — Plausibility is not proof.**
> A decode is evidence only when it is confirmed by reproduction (Module 2) or by an external constraint (a known value, an exact total, a cross-sample consistency check).

## 1.3 Establishing feasibility before committing

Before any reconstruction effort, establish that the target is *readable at all*. In the worked case this was settled with an entropy measurement: the traffic measured 4.8–5.9 bits per byte, where encryption would show ~8.0 and compression ~7.5. The data was plaintext and uncompressed — no protection had to be touched, only understanding acquired.

This is a five-minute test that determines whether a project is weeks or impossible. Run it first, always.

## 1.4 KNOWLEDGE CHECK 1.1

For each, state whether the work is viable and what test you would run first:

1. Traffic measures ~7.9 bits/byte, constant across all activity
2. Traffic measures ~5.0 bits/byte and contains visible repeated byte runs
3. Traffic measures ~7.6 bits/byte but the vendor's engine is open-source
4. Traffic is readable, but the only recordings available start mid-session

*Model answers: (1) encrypted — not viable without authorization; stop. (2) viable; begin structure recovery. (3) likely compressed — identify the compressor from the engine source before concluding. (4) viable but incomplete; the session start must be captured before the connection layer can be reconstructed.*

---

# MODULE 2 — THE ROUND-TRIP STANDARD

## 2.1 The only acceptable proof

> **RULE 2.1 — Reproduce, or you have not understood.**
> A format is understood when your code, given the original inputs, reproduces the original bytes **exactly**. Not equivalently. Not plausibly. Identically.

This standard is severe, and that is the point. It converts "I think this field is 10 bits" from an opinion into a testable claim. When reproduction fails, the diff tells you precisely where your model diverges from reality.

## 2.2 How it works in practice

The loop is:

1. Parse an original message with your current model
2. Re-serialise it from the parsed fields
3. Compare to the original, bit by bit
4. The first differing bit is the boundary of your understanding

Applied to the worked case, this produced statements of a quality that opinion cannot match:

- The handshake reproduced the original **byte for byte**, cross-validated across seven independent recordings
- The generated object-export block reproduced the original **bit for bit — all 3,257 bits**
- The welcome message reproduced at **exactly the original length**, which is how a missing fourth field was detected

## 2.3 What partial reproduction tells you

A near-miss is often more informative than a failure. In the worked case, a re-serialised packet matched the original **except for the final byte**, differing by exactly one bit. That single bit was a message terminator the writer was omitting. A vague model would have produced noise; a precise one produced a one-bit discrepancy that pointed straight at the defect.

## 2.4 Scale as corroboration

Reproduction proves a model on one sample. **Scale** proves it in general. Once the worked case's model was correct, it parsed **1,618 messages** from one recording and **7,378** from another — a different map and a different match — accounting for every bit in every message.

> **RULE 2.2 — Thousands of independent exact parses is the strongest evidence available short of source code.**
> A wrong model does not survive that volume. If yours does, it is right.

## 2.5 EXERCISE 2.1 — Design the proof

You have recovered what you believe is the layout of a status message. Write down, in advance:

1. What you will reproduce
2. What "success" looks like numerically
3. What a one-bit discrepancy would most likely mean
4. What scale test you will run afterwards
5. What result would make you abandon the model

*Assessment: an operator at L2 writes the abandonment criterion before running the test.*

---

# MODULE 3 — THE LIVE-ITERATION LOOP

## 3.1 Why recordings are not sufficient

This is the central lesson of Stage 2 and the one most likely to be resisted.

In the worked case, the decoder was validated against recordings to byte-level accuracy. It still did not work against the live system. **Seven separate defects** were invisible to static analysis and surfaced only under live iteration.

The reason is structural: recordings show you what the system *sent*, never what it *requires*. Optional fields that happened to be absent, ordering constraints that happened to be satisfied, and buffer limits that were never approached are all invisible in a recording and fatal in production.

> **RULE 3.1 — Static validation proves you can read. Only live iteration proves you can speak.**

## 3.2 The loop

1. **One variable per iteration.** Change one thing. Live tests are expensive — often requiring another person's time — so never spend one on two hypotheses.
2. **Instrument before testing.** Log every message in both directions before the first run. The run you fail to record is the run you must repeat.
3. **Record behaviour, not just outcome.** "It failed" is nearly useless. "It failed after 2.68 seconds having acknowledged our message" is a diagnosis.
4. **Predict before running.** Write down what each possible outcome would mean. This prevents fitting a story to whatever happens.
5. **Change one thing, re-run, compare timings.**

## 3.3 Worked sequence (process only)

| Iteration | Observed behaviour | What it isolated |
|---|---|---|
| 1 | Peer repeated its opening message indefinitely | Our acknowledgements were malformed — the peer never considered its message received |
| 2 | Silence; connection healthy, acknowledgements flowing | Our message was *received* but *queued* — a sequencing rule was wrong |
| 3 | Same silence | A second sequencing field, wrong in the same way |
| 4 | Peer disconnected immediately after our reply | Our reply was structurally short — a field was missing |
| 5 | Peer disconnected after 2.68s | Content-level rejection: values wrong, structure right |
| 6 | Peer disconnected after 0.80s | **Progress** — failing earlier means the previous fix landed and the failure moved downstream |
| 7 | Peer never disconnected | Transport fully accepted |

## 3.4 The counter-intuitive signal

Iteration 6 is the teaching moment. **A faster failure was evidence of success.** The peer stopped spending time on a stage it now passed, and reached a later stage that failed sooner.

> **RULE 3.2 — In live iteration, interpret changes in timing, not just changes in outcome.**
> Failing differently is progress. Failing identically is the absence of progress, regardless of how much work went into the change.

## 3.5 EXERCISE 3.1 — Read the timings

A peer disconnects after: run A 5.0s, run B 5.0s, run C 5.0s, run D 3.8s. Between runs you changed, respectively: the volume of data sent (20× more), the ordering of data, and the structural cleanliness of the data.

1. What do runs A–C tell you?
2. What does the constancy imply about the cause?
3. Is run D meaningfully different?
4. What class of hypothesis should you now abandon?

*Model answer: A–C show the failure is independent of data volume, order and cleanliness. A near-constant time strongly implies a **timeout** — the peer is waiting for a condition, not rejecting content. Run D is within noise. Abandon all "we sent the wrong data" hypotheses and search for the awaited condition.*

---

# MODULE 4 — REPLAY VERSUS SIMULATION

## 4.1 The boundary

Volume I, Module 2.3 introduced this distinction. Volume II is where it becomes decisive.

**Replay** re-sends recorded output. It can satisfy any requirement that depends only on *what was said*.

**Simulation** generates output from owned state. It is required for anything that depends on *who is being spoken to* or *what just happened*.

> **RULE 4.1 — Replay can satisfy content requirements. It can never satisfy identity, ownership, or responsiveness requirements.**

## 4.2 The decisive experiment

Replay's highest value is **diagnostic**: it isolates transport from content.

In the worked case, generated output was rejected while **byte-identical recorded output was accepted** — the peer held the connection, consumed the entire stream, and began replying. That single experiment converted an open question ("is anything about our implementation wrong?") into a bounded one ("only our content generation is wrong"), eliminating the entire transport layer from suspicion.

Design this experiment early. It is cheap and it collapses the search space.

## 4.3 Reading replay's ceiling

Replay was then pushed to its limit, and the limit was informative:

- With more data: same failure time
- With structurally sanitised data: same failure time
- Conclusion: the peer was waiting for something **no recording can contain** — in this case, ownership of a session-specific object belonging to a *different* recorded participant

> **RULE 4.2 — When replay plateaus at a constant, you have found a requirement that is structural, not informational.**
> More or better recordings will not help. Identify the requirement and move to simulation.

## 4.4 KNOWLEDGE CHECK 4.1

Which of these can replay satisfy? Justify each.

1. A peer requires a specific greeting format
2. A peer requires the world description it was promised
3. A peer requires an object it is told it owns
4. A peer requires a response to input it just produced
5. A peer requires a credential naming *this* session

*Model answers: (1) yes — content only. (2) yes, if the recording covers it. (3) **no** — ownership is per-session. (4) **no** — responsiveness cannot be recorded. (5) **no** — session-specific identity.*

---

# MODULE 5 — READING PLATEAUS

## 5.1 Two kinds of "stuck"

| Plateau type | Signature | Correct response |
|---|---|---|
| **Data-limited** | Accuracy rises with more samples | Gather more samples |
| **Knowledge-limited** | Accuracy is flat regardless of samples, and failures **concentrate** | Acquire different knowledge |

Confusing these wastes months. The distinguishing test is **failure distribution**.

## 5.2 The concentration test

In the worked case, a statistical model of a data format solved simple cases perfectly (100%) but stalled near 60% on complex ones. Rather than assume a cause, the operator **instrumented where each parse failed**.

The failures were not spread out. **Two or three specific fields accounted for 82–90% of all failures**, and the same fields dominated across otherwise unrelated cases — indicating shared, inherited structure.

That distribution is the signature of **variable-length fields**, which a fixed-length model provably cannot represent. No quantity of additional samples changes that. The remaining work requires *type* knowledge, not more data.

> **RULE 5.1 — Before concluding why a model plateaus, measure where it fails.**
> Concentrated failures indicate a structural limitation. Diffuse failures indicate insufficient data.

## 5.3 Stating a plateau honestly

A plateau is reported with:

1. The measured ceiling (e.g. "simple classes 100%, complex ~60%")
2. The evidence for the cause (failure concentration, shared fields)
3. What would and would not move it ("type knowledge would; more captures would not")
4. Whether it blocks the objective

## 5.4 EXERCISE 5.1

A model reaches 62% and stops. Design the measurement that determines whether to gather more data or acquire different knowledge. State the numeric result that would send you down each path.

---

# MODULE 6 — CORRECTING YOURSELF

## 6.1 Premature conclusions are normal; uncorrected ones are not

In the worked case, the operator concluded that a peer disconnected because "it ran out of data." The reasoning was sound: the disconnection followed shortly after the data stream ended.

The next test — with twenty times more data queued — produced the **same disconnection at the same point**. The conclusion was wrong, and it was corrected in the record.

## 6.2 Why this matters more with AI assistance

AI-assisted investigation generates confident narratives quickly. A plausible explanation arrives fully formed, and the temptation is to accept it because it is coherent. Coherence is not correctness.

> **RULE 6.1 — Every causal claim must carry the test that would falsify it.**
> "It ran out of data" is falsified by supplying more data. If you cannot state the falsifying test, you have a story, not a finding.

## 6.3 The correction protocol

1. State the correction plainly, in the record, where the original claim lives
2. State the evidence that overturned it
3. Do not delete the original — the sequence is itself evidence about method
4. Re-examine anything that was built on the wrong claim

## 6.4 EXERCISE 6.1

Review your three most recent causal claims about a system under investigation. For each, write the single test that would falsify it. Any claim for which you cannot write one is downgraded to a hypothesis in your records.

---

# MODULE 7 — SCOPE, LIMITS AND HANDOVER

## 7.1 Reporting a partial result

Stage 2 produced a genuine partial result: a complete, live-proven connection stack and an unbuilt world simulation. Reporting this well means separating three categories precisely:

| Category | Standard of evidence |
|---|---|
| **Proven live** | Demonstrated against the real system |
| **Validated statically** | Reproduces recordings exactly, not yet exercised live |
| **Not built** | Stated plainly, with the work required |

> **RULE 7.1 — Never let a strong result in one category imply completion in another.**
> "The client completes its entire join sequence against our server" is true and impressive. It does not mean the game is playable, and any report that allows that inference is defective.

## 7.2 Recognising the specialist boundary

An operator's job includes knowing where their competence ends. In the worked case, the boundary is explicit: everything up to and including world replication framing was reconstructed by the operator; **world simulation** — owning actors, establishing ownership, generating live state, answering input — is flagged as warranting a domain specialist.

Naming that boundary early is a professional strength, not an admission. What makes it credible is that everything beneath it is documented, proven, and reproducible.

## 7.3 The handover standard

A handover is complete when a competent stranger can:

1. Reproduce every proven result from the artefacts provided
2. Re-run the diagnostic experiments (including the decisive replay test)
3. Read the corrected record, including abandoned hypotheses
4. Begin the next phase without re-deriving anything

## 7.4 EXERCISE 7.1 — Write the status board

For a project of your own, produce a three-category status board (proven live / validated statically / not built) with the evidence standard for each entry. Have a colleague identify any entry whose wording permits a false inference.

---

# APPENDIX A — THE OPERATOR'S CHECKLIST

**Before reconstruction**
- [ ] Feasibility measured (entropy / protection check)
- [ ] Engine or format family identified
- [ ] Session-start recordings secured, not just mid-session

**During reconstruction**
- [ ] Round-trip reproduction is the acceptance test for every layer
- [ ] Implausible decodes investigated, never explained away
- [ ] Scale check run once a model is believed correct

**During live iteration**
- [ ] Full instrumentation before the first run
- [ ] One variable per iteration
- [ ] Outcomes predicted in advance
- [ ] Timings recorded and compared across runs

**At a plateau**
- [ ] Failure distribution measured before diagnosing cause
- [ ] Data-limited vs knowledge-limited classified
- [ ] Ceiling and its cause stated in the record

**At handover**
- [ ] Three-category status board written
- [ ] Corrections retained in the record
- [ ] Specialist boundary named
- [ ] Stranger-reproducibility verified

---

# APPENDIX B — RULE INDEX

| Rule | Statement |
|---|---|
| 1.1 | Plausibility is not proof |
| 2.1 | Reproduce, or you have not understood |
| 2.2 | Thousands of exact parses is the strongest evidence short of source |
| 3.1 | Static validation proves reading; live iteration proves speaking |
| 3.2 | Interpret changes in timing, not just outcome |
| 4.1 | Replay satisfies content, never identity or responsiveness |
| 4.2 | A constant plateau indicates a structural requirement |
| 5.1 | Measure where a model fails before diagnosing why |
| 6.1 | Every causal claim carries its falsifying test |
| 7.1 | A strong result in one category never implies completion in another |

---

*RecompileLabs Operator Field Manual, Volume II · Private internal training document · Revision 1.0*
