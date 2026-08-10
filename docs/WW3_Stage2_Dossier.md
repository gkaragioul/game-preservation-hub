# OPERATION PRESERVATION — STAGE 2

## WORLD WAR 3 — REBUILDING THE MATCH SERVER

**Classification:** Internal technical record
**Subject:** World War 3 (Steam App 674020) · Unreal Engine 4.21 · multiplayer-only
**Stage 1 status:** Complete — game boots and plays offline, no official servers
**Stage 2 status:** Connection stack complete and live-proven; world simulation outstanding
**Shutdown deadline:** 3 August 2026
**Revision:** 1.0 — 25 July 2026

---

## What's inside this dossier

Stage 1 answered *"can the game start without the company's servers?"* The answer was yes: the menu, the profile, the identity system and the anti-cheat handshake were all rebuilt locally, and the game now boots forever-offline with everything unlocked.

Stage 2 asks a much harder question: **can we rebuild the thing that actually runs a match?**

This dossier is the record of that work. It covers what a match server actually is, how we decoded a protocol nobody documented, the seven defects that only a live game could reveal, how far we got, and precisely what stands between here and a playable match.

The short version: **the entire connection stack is finished and proven against the real game.** A real WW3 client now completes its full join sequence against software we wrote — handshake, login, credential validation, map load, and the beginning of world replication — with no official server anywhere in the loop. What remains is not protocol work. It is simulation.

---

## 1. Why the match server is a different problem

Stage 1 was, at heart, **impersonation**. The game asked questions; we learned the answers from recordings and replayed them. A menu is a conversation with predictable turns.

A match server is not a conversation. It is a **simulation with an audience**. It owns the truth about the world — where every player stands, what they are holding, what they just shot — and it broadcasts that truth 30 times a second to every client, in a compressed binary format with no text, no field names, and no documentation.

Three consequences follow, and they define the whole stage:

1. **You cannot fake it from recordings.** A recording knows what happened last Tuesday. It cannot answer what happens when *you* press W.
2. **There is no error message.** When you get a bit wrong, the game does not tell you. It goes quiet, or it hangs up. Diagnosis has to come from behaviour and timing.
3. **The format is exact.** Not "roughly right" — a single bit in the wrong place shifts everything after it and turns the rest of the message into noise.

Stage 1 was archaeology. Stage 2 is engineering.

---

## 2. What we were up against

Before any of this could start, we had to know whether it was possible at all. Two findings made Stage 2 viable:

**The traffic is readable.** Match data measured 4.8–5.9 bits per byte of entropy. Encrypted traffic measures ~8.0; compressed traffic ~7.5. Ours was neither — the match protocol is **plaintext and uncompressed**. Nothing had to be broken; it had to be *understood*.

**The engine is public.** WW3 runs on Unreal Engine 4.21, whose source is publicly available. We were not guessing at a bespoke protocol — we were identifying a known one, then finding where this particular build differs from stock. (It differs in several places, and every one of them cost us a live test to find.)

One door closed hard: the **official dedicated server binary is unobtainable**. It is a separate, licence-restricted Steam application; owning the game does not grant it, its files were deleted by the developers, and the only builds that ever existed are from 2019–2020 and incompatible with the current game. There is no legitimate way to obtain it. That left exactly one route: **write our own**.

---

## 3. Getting a word in — the handshake

Before a client will exchange a single byte of game data, it performs a challenge-response handshake designed to stop spoofed connections.

We reconstructed it from captured traffic down to the individual bit:

| Field | Bits | Notes |
|---|---|---|
| Handshake marker | 0 | always set on handshake packets |
| Flag (secret id) | 1 | rotates per connection |
| **Timestamp** | 2–33 | **32-bit float** — and **−1.0** is the "you're accepted" signal |
| Cookie | 34–193 | 20-byte authentication token |
| Terminator | 194 | → exactly 25 bytes on the wire |

Two discoveries made this work. First, the timestamp is a **float**, not the integer we initially assumed — the giveaway was a value that decoded to exactly −1.0, which turned out to be the server's acceptance sentinel. Second, the client **echoes the server's challenge back verbatim**, which means we validate by regenerating the cookie with *our own* secret. No studio key is needed anywhere.

**Verification standard:** we fed our code the real captured cookie and it produced the real server's challenge packet **byte for byte**, then cross-checked across seven independent captures. That standard — *reproduce the original exactly, or you have not understood it* — was applied to every layer that followed.

---

## 4. Speaking the language — the control channel

Past the handshake sits the negotiation that turns a socket into a game session: hello, challenge, login, welcome.

Reconstructing it meant reverse-engineering three nested layers of framing — how packets carry acknowledgements, how acknowledgements are separated from data, and how data is chopped into "bunches" addressed to channels. Every field width had to be recovered by inference and confirmed by exact reproduction.

The credential the client presents is a **lobby token**: a signed permit issued by the matchmaking system naming the player, their team, the map, the game mode, and the server they were sent to. Because it is signed with a shared secret rather than a private key, **our own backend both issues and validates it** — the same key on both sides, entirely ours.

The moment that proved this layer was the live log line:

```
<- NMT_Login VALID: player=100001 team=0 map=WW3_Gobi_New_P gameMode=47  -> NMT_Welcome
```

That is the real game, presenting its real credential, validated by our server, and accepted back. Shortly after, the client loaded the map and asked to spawn.

---

## 5. The seven defects only a live game could find

This is the most transferable lesson in the whole stage, so it gets its own section.

We had validated our decoder against recorded traffic to the byte. It still did not work. Seven separate defects were invisible to offline analysis and surfaced only by pointing the real game at our server:

| # | Symptom | Actual cause |
|---|---|---|
| 1 | Client repeated its greeting forever | Acknowledgement entries are **24 bits**, not 15 — two extra fields we never knew existed |
| 2 | Silent hang, connection healthy | Sequence numbers are **derived from the handshake cookie**, not started at zero |
| 3 | Silent hang again | Channel sequence is **12-bit**, followed by a 3-bit channel type |
| 4 | Client hung up after our welcome | This build's welcome message has **four** text fields, not the standard three |
| 5 | Garbage in our decoder | Channel-close messages carry a **2-bit reason code** |
| 6 | Spawn rejected | Object exports are **recursive** — the parent must be a full nested record |
| 7 | Client quit mid-world-load | **73% of world updates must be sent "unreliable"**; sending them all reliable overflows the client |

Every one of these was found the same way: change one thing, watch the *behaviour*, read the timing. Defect 2 was the sharpest example — the connection looked perfectly healthy, acknowledgements flowing both ways, but the client had quietly filed our message in a queue waiting for hundreds of earlier messages that would never arrive.

**Why offline analysis missed them:** we had only ever perfectly reproduced packets that happened to contain *no acknowledgements*. Every acknowledgement-bearing packet in the recordings had been decoding into nonsense, and we had misattributed that nonsense to a part of the format we hadn't reversed yet. The recordings contained the evidence; we had rationalised it away. Only the live client refused to accept the rationalisation.

---

## 6. The world on the wire

With the connection open, the client asks to spawn and the server starts describing the world.

Unreal does this through an object dictionary. The first time the server mentions anything — a class, a map, a component — it sends the full text path and assigns it a number. Everything afterwards refers to the number. We reversed this dictionary format, including the recursive parent structure and three separate flag bits, and confirmed it by decoding real world state:

```
15 -> /Game/Blueprints/Player/Controllers/BP_WW3_DominationPlayerController_01
13 -> Default__BP_WW3_DominationPlayerController_01_C   (parent: 15)
 9 -> /Game/Maps/Main/Dunhuang_v3/WW3_Gobi_New_P
 7 -> WW3_Gobi_New_P            (parent: 9)
 5 -> PersistentLevel           (parent: 7)
```

Run across the recordings, the same decoder reconstructs the entire object graph of a live match unaided — player controllers, HUDs, player states, bots, weapons, even individual ammunition types. Spawn positions decode to sensible world coordinates. Actor updates decode into property streams whose fields keep consistent widths across independent channels.

**Scale check:** the decoder parsed **1,618 actor updates** from one recording and **7,378** from another, on a different map, with exact bit-accounting on every one. A wrong model does not survive thousands of independent messages.

---

## 7. Talking back

Reading is half the job. To *be* a server you must produce this format, not just consume it.

We built the writer and held it to the same standard as everything else: our generated object-export block is **bit-identical to the real server's — all 3,257 bits**. Same numbering, same flags, same checksums, same nested structure, same subobjects.

When we sent our own spawn to the live game, the diagnosis came from timing:

| What we sent | Client reaction |
|---|---|
| Our spawn, wrong checksums and flags | hung up after **2.68s** |
| Bit-identical export block | hung up after **0.80s** |
| The real server's bytes, replayed | **never hung up** — 40 seconds, and it started talking back |

That middle row is the useful one. The client failing *faster* was the evidence that our fix had landed and moved the failure downstream.

---

## 8. How far a recording gets you

The third row above is the most striking result in Stage 2. Replaying the real server's captured world data, the client **accepted 1,200+ updates across 90 channels including 136 actor spawns**, held the connection, and began sending its own data back to us.

So we pushed it: 20× more data, then a structural sanitiser that removed every incoherent channel lifecycle. The client kept dying at roughly the same point.

The cause turned out to be **ours, and mundane**: we were sending **one message per packet**. Measuring the real server showed it packs **11.5 messages into every packet** (up to 33) at around 411 bytes. We were generating roughly **eleven times the packet rate** — about 250 datagrams per second where the client expected 30. It was not rejecting our world; it was drowning in datagrams.

Packing them properly produced an immediate, measurable jump:

| Fix | Messages accepted | Connection held |
|---|---|---|
| original | 480 | ~4s |
| correct reliable/unreliable mix | 1,210 | 4.9s |
| **messages packed per packet** | 3,840 | 14.2s |
| **+ corrupt-data guard** | **5,280** | **19.4s** |

Eleven times the world data, five times longer.

Two earlier readings of this same evidence were wrong and are recorded here deliberately. The first — "the client ran out of material" — was disproved by queueing twenty times more data and seeing the identical failure. The second — "it is a fixed timeout waiting for its own player controller" — was disproved by the fact that a two-message replay survived forty seconds, which no fixed timeout would allow. Only measuring the real server's packet pacing settled it.

The lesson is the one in Volume II of the field manual: **a causal claim without a falsifying test is a story, not a finding.**

---

## 9. Status board — what works today

**Proven against the real game, with no official servers involved:**

- The full cryptographic handshake — byte-exact, cross-validated on seven captures
- Login, credential validation, and session acceptance — using the player's real token
- Map load — the client loads Gobi on our instruction
- World replication framing — the client digested 1,200+ updates, 136 actor spawns, 90 channels
- Our object-export generation — bit-identical to the original server

**Built and validated against recordings:**

- Complete decoder for packets, acknowledgements, bunches, channels, object dictionary, spawn records, quantised positions, and property streams
- Property tables mined for 43 classes across ~397,000 samples; simple classes solved to 100%
- Full writer stack, verified by reproducing original messages exactly

**Not built:**

- World simulation — owning actors, establishing controller ownership, generating live property updates, and answering the client's input

**Honest position:** the connection is a solved problem. The world is not.

---

## 9b. Cleaning our own instruments

Chasing the replay failures exposed a defect in our own decoder worth recording, because it had been silently contaminating results.

About **1% of packets** were losing bit-alignment inside the acknowledgement section. When that happens every message after it in the packet is nonsense — we were reading channel numbers in the billions where the real range is 0–255 — and we were faithfully replaying that nonsense to the client and feeding it into our property tables.

We A/B-tested the acknowledgement format against 135,520 real messages and confirmed **our format is correct** (0.99% failure versus 3% and worse for the alternatives). The residual is a variable-length long tail, not a missing field. Rather than chase it, the decoder now **fails closed**: it stops at the first impossible value and flags the packet, emitting **zero corrupt messages** where it previously emitted 1,339.

This also settled an open question honestly. We had attributed the property-table plateau (simple classes 100%, complex ones ~60%) to variable-width fields. With the corruption removed we re-ran the analysis expecting movement — and the plateau **did not move**, with an identical failure distribution concentrated on the same three properties. The original conclusion was therefore confirmed by controlled re-test rather than assumed, and those three specific properties are now named for whoever continues.

---

## 10. The wall, and what is on the other side

Everything now rests on one requirement: **the server must own the world.**

Concretely, the remaining work is:

1. **Ownership** — establish the client's own player controller with the correct authority flags, which is precisely what the four-second timeout is waiting for
2. **Property generation** — emit live world state using the mined tables, including the variable-width types (arrays, text, conditional fields) that a fixed-width model provably cannot express
3. **Input handling** — decode and answer the client's messages; we already log thousands per session
4. **Game rules** — spawn points, teams, scoring: the actual match

This is a substantial engineering project — realistically the largest single piece of Path B — and it is the natural point to bring in Unreal networking expertise. It is not, however, an unknown. Every layer beneath it is mapped, documented, and proven.

---

## 11. What Stage 2 demonstrates

Independent of whether a match is ever played, this stage produced results worth stating plainly:

- An **undocumented binary protocol** was reconstructed to bit-level accuracy from traffic recordings alone, and verified by exact reproduction rather than by assertion
- A **live client was driven through its entire join sequence** by independently written software
- Seven defects invisible to static analysis were found through **disciplined live iteration**, each isolated by changing one variable and reading behaviour
- A **decisive experiment** separated transport from content, converting an open-ended question into a bounded one
- The limits are **stated accurately**, including a corrected earlier conclusion

That combination — reconstruct, verify by reproduction, iterate against reality, and report limits honestly — is the method. The game is the worked example.

---

## 12. Limitations

- **No match is playable.** The client connects, authenticates and loads the map, then times out awaiting world ownership.
- **Replay is a diagnostic, not gameplay.** Recordings cannot respond to input, and cannot transfer ownership.
- **Property coverage is partial.** Simple classes solve completely; complex ones plateau near 60% because variable-width fields need type knowledge, not more samples.
- **One capture source.** All recordings are client-side, from a small number of matches on three maps.
- **Stage 1 is unaffected.** Offline boot and solo play work today and do not depend on any of this.

---

## 13. Rights and scope

This work covers a legally owned copy of the game, operated privately, for the purpose of keeping it playable after the publisher's servers are withdrawn. No copyrighted assets are redistributed. No official server software was obtained or used — the investigation confirmed it is unobtainable and stopped there. No protection was defeated for distribution, and the toolchain is scoped so it cannot affect any other game on the machine.

---

## 14. Final result

Stage 1 kept the game **alive**. It boots, it unlocks, it plays solo — forever, offline, from an owned copy.

Stage 2 established that the multiplayer half is **reachable**. The protocol that nobody documented has been reconstructed and proven against the real game: a real WW3 client now completes its entire join sequence — handshake, login, credential validation, map load, world replication — against software written from scratch, with the publisher's servers already irrelevant.

What is left is not a mystery. It is a build.

---

*Prepared by RecompileLabs · Internal technical record · Stage 2 · Revision 1.0*
