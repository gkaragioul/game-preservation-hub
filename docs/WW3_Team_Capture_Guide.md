# World War 3 — Final Recordings

### Please do these before **3 August 2026**

After that date the servers are switched off and this can never be recorded again.

**Two matches are essential. A bonus item follows if you happen to see it.**

---

## What to record

| ☐ | Play **Team Deathmatch** on | Save the file as |
|---|---|---|
| ☐ | **Moscow Senate** | `TDM_MoscowSenate.pcapng` |
| ☐ | **Landmark** | `TDM_Landmark.pcapng` |

**Please do NOT record Warzone or Domination** — we already have every map for those, and duplicates just cost you time.

---

## ALSO VALUABLE — any *other* game mode

If you see **any game mode other than Team Deathmatch, Warzone or Domination** anywhere — in the normal menu, a playlist, or **Custom Play** — please record **one match of it**.

Look out for anything like:

**Breakthrough · Gun Game · HVT · Recon · Transmission · Fubar · KIA · Search & Destroy**

Name the file after the mode, e.g. `Breakthrough_Berlin.pcapng`, `GunGame_Shibuya.pcapng`.

**Any map is fine — the mode is what matters.** Even one match of one of these is a big win: each game mode uses its own internal code that exists nowhere except live traffic, so once the servers are off it's gone permanently.

If you only ever see Team Deathmatch, Warzone and Domination, that's fine — just do the two matches above.

---

## Setup (once)

1. **Install Wireshark** — free, from **https://www.wireshark.org/download.html**
   Use the default options. If it asks about **"Npcap"**, say **yes** — that's the part that does the recording.

2. **Open Wireshark.** You'll see a list of network connections, each with a small graph next to it.

3. **Pick the connection whose graph is moving** — that's your active internet. Usually called **"Wi-Fi"** or **"Ethernet"**.

---

> ## ⚠️ LEAVE THE FILTER BOX EMPTY
>
> Do **not** type anything into the filter box. No `tcp.port`, no `http`, nothing at all.
>
> The last two recordings we received used `tcp.port == 443`, and they contained **zero**
> usable data — the game's match traffic is **UDP**, and that filter deleted all of it.
>
> **Empty box = correct.**
> If you really want smaller files, the only safe thing to type is the single word `udp`.

---

## For each match

1. **Start recording FIRST** — double-click your connection, or click the blue **shark-fin ▶** button. You should see rows of packets scrolling.

2. **Then** open World War 3 and **join the match**.

3. **Stay in for at least 60 seconds after you spawn.** You don't need kills or a good score.

   **⭐ For ONE of your matches, please stay until the match actually ENDS** — all the way through the final scoreboard and the XP / level-up screen, until you're back at the menu. Keep recording the whole time.

   We have never recorded a match *finishing*, so that one recording is especially valuable. It doesn't matter which match, or whether you win.

4. Go back to Wireshark and click the **red square ⏹ (Stop)**.

5. **File → Save As…** and use the filename from the table above. Keep the `.pcapng` file type.

6. Start a fresh recording for the second match.

---

> ## ⚠️ THE ONE RULE THAT MATTERS
>
> **Wireshark must already be recording BEFORE you press join.**
>
> If you join first and start recording after, the file is useless to us.
> No harm done — just start over: recording first, then join.

---

## If a map won't fill

The game is nearly empty this close to shutdown. That's expected.

- Try **Custom Play** — custom lobbies often start with far fewer players
- Try **peak evening hours**, when the most people are on
- **If a map won't start after 2 or 3 tries, skip it and let George know.** Don't waste your evening in an empty queue.

Even a match that never properly starts is still useful — the important part is the moment you connect.

---

## Sending the files

WeTransfer, Google Drive, or any file-sharing service. Each file will be a few hundred MB — that's completely normal.

---

## Quick FAQ

**Which connection do I pick?** The one with the moving graph. If unsure, pick "Wi-Fi" or "Ethernet".

**Is this safe?** Yes. Wireshark only *listens* to network traffic, like a screen recorder for your internet. It changes nothing on your PC, touches no game files, and can be uninstalled afterwards.

**Do I have to finish the match?** For most, no — 60 seconds after you spawn is enough. But please let **one** match run to the very end (final scoreboard + XP screen) with the recording still running. We've never captured a match finishing.

**The file is huge — is that OK?** Yes, send it as-is.

**How do I know I did it right?** If Wireshark was recording *before* you joined, and you stayed in about a minute, it's good.

---

## Why these

Every map has a hidden internal name that appears **only** in this network traffic — it isn't in the game files and can't be guessed. We have 10 of 13; these two matches complete the set.

The same is true of every **game mode**: each one uses internal code that exists nowhere except live traffic. We have three. Any other mode you can find and record is one more preserved forever.

**Priority: the two matches. Any other game mode is a bonus.**

---

*Thank you. This genuinely cannot be recreated after August 3rd.*
