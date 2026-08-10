# World War 3 — Match Recording Checklist

### Please do this before **3 August 2026**

**What this is:** World War 3's servers are switched off on 3 August 2026. After that, the game can never be recorded again. I'm preserving it, and I need recordings of **8 specific matches**.

**Is it safe?** Completely. Wireshark only *listens* to network traffic, like a screen-recorder for your internet. It **changes nothing** on your PC, touches no game files or settings, and doesn't affect the game or any other program. You can uninstall it straight after.

**Time needed:** roughly 10 minutes per match. You just play normally while a recorder runs in the background.

---

## Setup — do this once

1. **Install Wireshark** — free, from **https://www.wireshark.org/download.html**
   Default options are fine. If it asks to install **"Npcap"**, say yes — that's the part that does the recording.

2. **Open Wireshark.** You'll see a list of network connections, each with a small **live activity graph**.

3. **Pick the connection whose graph is moving** — that's your active internet, usually **"Wi-Fi"** or **"Ethernet"**. If unsure, pick whichever is clearly wiggling.

4. *(Optional — makes files smaller)* In the **capture filter** box near the top, type:
   ```
   udp
   ```
   Leaving it blank also works.

---

## For every match — the routine

1. **Start recording first.** Double-click your connection, or click the blue **shark-fin ▶** button. Packets should start scrolling.
2. **Then** go into World War 3 and **join the match** from the list below.
3. **Stay in for at least 60 seconds after you spawn.** You don't need to play well, get kills, or finish the match.
4. Back in Wireshark, click the **red square ⏹ (Stop)**.
5. **File → Save As…** using the filename from the list (keep the `.pcapng` type).
6. Start a fresh recording for the next match.

> ## ⚠️ THE ONE RULE THAT MATTERS
> **Wireshark must already be recording BEFORE you press join.**
> If you joined first and started recording after, the file is unusable. No harm — just redo it.

---

# THE 8 MATCHES

## Team Deathmatch — 5 matches
*(the smaller maps, around 20 players)*

| ☐ | Play this map | Save the file as |
|---|---|---|
| ☐ | **Shibuya** | `TDM_Shibuya.pcapng` |
| ☐ | **Berlin Backyards** | `TDM_BerlinBackyards.pcapng` |
| ☐ | **Warsaw Shopping Mall** | `TDM_WarsawMall.pcapng` |
| ☐ | **Moscow Senate** | `TDM_MoscowSenate.pcapng` |
| ☐ | **Landmark** | `TDM_Landmark.pcapng` |

## Warzone — 3 matches
*(the big maps, around 40 players)*

| ☐ | Play this map | Save the file as |
|---|---|---|
| ☐ | **Berlin** | `WAR_Berlin.pcapng` |
| ☐ | **Moscow** | `WAR_Moscow.pcapng` |
| ☐ | **Smolensk** | `WAR_Smolensk.pcapng` |

---

## If you can't choose the map

The game usually picks the map for you. If you can't select one directly:

- Keep playing that mode and **record every match**
- Name each file after whichever map you actually landed on
- We need each map **once** — if you land on one you've already done, just delete that file and try again

---

## Bonus — only if you actually see them

If any of these modes show up in the menu or in Custom Play, please record **one match of each**. We have none of them:

**Breakthrough · Gun Game · HVT · Recon · Transmission**

Name them like `Breakthrough_Berlin.pcapng`.

---

## Sending the files

Send everything to George via **WeTransfer, Google Drive, or any file-share**. Files can be a few hundred MB each — that's normal and fine.

---

## Quick FAQ

**Which network connection do I pick?** The one with the moving activity graph. If you can't tell, pick "Wi-Fi" or "Ethernet."

**The files are big — is that OK?** Yes. Send as-is, or use the `udp` capture filter to shrink them.

**Will this harm my PC, my game, or other games?** No. Wireshark only *watches* traffic. It installs nothing into the game and can be uninstalled afterwards with no trace.

**Do I need to do anything special in-game?** No — play exactly as you normally would, on the live servers.

**Do I have to finish the matches?** No. 60 seconds after you spawn is enough. You can quit right after.

**How do I know I did it right?** If Wireshark was recording *before* you joined, and you stayed in a minute, it's good. That's the only thing that matters.

---

## Why these exact 8

Each map has a hidden internal name that only ever appears in this network traffic — it isn't in the game files and can't be guessed. Team Deathmatch also uses different internal game code that we've never recorded.

**These 8 recordings complete the set: every map and every mode the game had.** After 3 August, nothing else can be added, ever.

---

*Thank you — this genuinely cannot be recreated after August 3rd.*
