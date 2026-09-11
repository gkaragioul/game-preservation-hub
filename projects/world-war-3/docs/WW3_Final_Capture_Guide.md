# World War 3 — Final Captures

### Everything left to record before **3 August 2026**

After that date the servers are switched off and none of this can ever be recorded again.

There are **two separate jobs**. They use different tools and different people.

| Job | Who | Tool | Time |
|---|---|---|---|
| **PART 1** — 2 match recordings | The team | Wireshark | ~20 min |
| **PART 2** — menu recording | **George only** | The recorder tool | ~20 min |

---
---

# PART 1 — FOR THE TEAM

## What we need: 2 Team Deathmatch matches

| ☐ | Play **Team Deathmatch** on | Save the file as |
|---|---|---|
| ☐ | **Moscow Senate** | `TDM_MoscowSenate.pcapng` |
| ☐ | **Landmark** | `TDM_Landmark.pcapng` |

That's it. Nothing else is needed from the team.

**Do NOT record:** Warzone, Domination, or any other map — we already have those.

---

## Setup (once)

1. **Install Wireshark** — free, from **https://www.wireshark.org/download.html**
   Default options. If it asks about **"Npcap"**, say **yes**.

2. **Open Wireshark.** You'll see a list of connections, each with a small wiggling graph.

3. **Find the connection whose graph is moving** — that's your internet, usually **"Wi-Fi"** or **"Ethernet"**.

> ### ⚠️ LEAVE THE FILTER BOX EMPTY
> Do **not** type anything into the filter box — no `tcp.port`, no `http`, nothing.
> A previous recording used `tcp.port == 443` and captured **zero** usable data, because
> the game's match traffic is **UDP** and that filter threw it all away.
>
> Empty box = correct. If you really want smaller files, the *only* safe thing to type is
> the single word `udp`.

---

## For each match

1. **Start recording FIRST** — double-click your connection (or click the blue **shark-fin ▶**). Packets start scrolling.
2. **Then** open World War 3 and **join the match**.
3. **Stay in for 60 seconds after you spawn.** You don't need kills, a good score, or to finish.
4. Back in Wireshark, click the **red square ⏹ (Stop)**.
5. **File → Save As…** with the filename from the table above. Keep the `.pcapng` type.
6. New recording for the next match.

> ## ⚠️ THE ONE RULE
> **Wireshark must already be recording BEFORE you press join.**
> Join first and the file is worthless. No harm — just start over.

---

## If a map won't fill

The game is nearly empty this close to shutdown.

- Try **Custom Play** — a custom lobby often starts with far fewer players
- Try **peak evening hours**
- **If a map won't start after 2–3 tries, skip it and tell George.** Don't grind an empty queue.

Even a match that never properly starts is useful — the moment you connect is what matters.

---

## Sending files

WeTransfer / Google Drive / any file share. Files are a few hundred MB — that's normal.

---
---

# PART 2 — FOR GEORGE ONLY

## Why this is different

This one is **not** Wireshark. The menu talks to the servers over **encrypted** connections, so Wireshark would only record scrambled bytes. Our recorder tool sits in the middle and captures the readable version.

**This must be done on your machine** — the recorder is only set up there, and it temporarily changes network settings. **Do not ask the team to do this.**

## What we're missing

17 menu functions we never opened while recording: Challenges, Daily/Season challenges, Leaderboards, Notifications, career statistics, and the writes that happen when a match ends.

## Steps

1. **Close World War 3** if it's running.

2. **Double-click** `F:\Dev_Work\GameDev\WW3\windows\WW3-Recorder-Start.ps1`
   It asks for admin — say yes. A window opens and stays open. **Leave it running.**

3. **Launch World War 3 normally through Steam** — online, against the real servers.
   (Do **not** use any of the offline/mock scripts for this.)

4. **Open every one of these screens**, slowly, giving each a few seconds to load:

   | ☐ | Screen |
   |---|---|
   | ☐ | **Challenges** — and each tab: Daily, Weekly, Season |
   | ☐ | **Leaderboards / Scores** |
   | ☐ | **Notifications** (the bell / inbox) |
   | ☐ | **Career / Statistics / Profile** |
   | ☐ | **Shop** — browse every tab. **Do not buy anything** |
   | ☐ | **Battle Pass / Season progression** |
   | ☐ | **Friends list** |
   | ☐ | **Loadout / Customisation** — open a few weapons |
   | ☐ | **Settings** |

5. **If you can, play one match all the way to the end** — through the scoreboard and the XP/level screen. That captures what happens when a match finishes.

6. **Quit the game.**

7. **Double-click** `WW3-Recorder-Stop.ps1`
   It stops recording, restores your network settings, and copies the logs to your Desktop.

> ### ⚠️ IMPORTANT
> Always run the **Stop** script when finished. If you don't, network redirects stay active
> and **other games (Killing Floor, Hunt, anything using Epic) will fail to connect.**
> If that ever happens, running Stop fixes it.

---

## After both parts are done

Nothing else is recoverable from the servers. Everything else is already safely captured:
all three game modes, ten of thirteen maps, vehicles, progression data, the lobby system,
and the complete match connection protocol.

---

*Thank you — none of this can be recreated after August 3rd.*
