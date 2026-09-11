# How to Capture a World War 3 Match

### A 15-minute favor — please do it before **3 August 2026**

**What this is:** World War 3's servers shut down on 3 August 2026, after which the game can't be played or recorded ever again. I'm preserving it, and I need a recording of the network traffic from **one normal online match** — specifically the moment the game *joins* a match. This can only be captured while the servers are still live.

**Is it safe?** Completely. The tool (Wireshark) only *listens* to network traffic, like a screen-recorder for your internet. It **changes nothing** on your PC, touches no game files or settings, and doesn't affect the game or any other program. You can uninstall it right after.

**Time needed:** ~15 minutes. **You just play the game normally while a recorder runs in the background.**

---

## What you need

- The Windows PC you normally play World War 3 on (able to join a normal online match)
- **Wireshark** — free, from **https://www.wireshark.org/download.html** (install with the default options)

---

## Steps

1. **Install Wireshark** (default options are fine; if it asks to install "Npcap," say yes — that's the part that lets it record).

2. **Open Wireshark.** You'll see a list of network connections, each with a small **live activity graph** next to it.

3. **Pick the connection whose graph is moving** — that's your active internet (usually named **"Wi-Fi"** or **"Ethernet"**). If unsure, pick whichever is clearly wiggling.

4. *(Optional, keeps the file smaller)* In the **capture filter** box near the top, type:
   ```
   udp
   ```
   Leave it blank if you'd rather just capture everything — either works.

5. **Start recording:** double-click that connection (or click the blue **shark-fin ▶** button, top-left). You should see rows of packets start scrolling. **Leave it running.**

6. **Now launch World War 3** and go to the main menu.

7. ⚠️ **THE ONE IMPORTANT PART:** with Wireshark **already recording**, click **PLAY** and **join a match** (normal matchmaking). The recording *must already be running before you join* — that's the whole point of this.

8. Once you're in the match and can move around, **just play normally for 2–3 minutes** — walk, run, shoot, anything.

9. Switch back to Wireshark and click the **red square ⏹ (Stop)** button.

10. **File → Save As…** → save it as **`WW3_match_full_1.pcapng`** (keep the `.pcapng` file type).

11. **Please do it 2–3 times** (a fresh match each time): `WW3_match_full_2.pcapng`, `WW3_match_full_3.pcapng`. More recordings = safer.

12. **Send the file(s) to George** (WeTransfer, Google Drive, or any file-share — they can be a few hundred MB).

---

## The single rule that matters

> **Wireshark has to already be recording BEFORE you join the match.**
> If you joined the match first and only started recording after, the file won't be useful — no harm done, just redo it: start Wireshark, *then* hit Play.

---

## Quick FAQ

**Which network connection do I pick?** The one with the moving activity graph. If you can't tell, pick "Wi-Fi" or "Ethernet."

**The file is big (hundreds of MB) — is that OK?** Yes. Send it as-is, or use the `udp` capture filter (step 4) to make it smaller.

**Will this harm my PC, my game, or my other games?** No. Wireshark only *watches* traffic. It installs nothing into the game, changes no settings, and can be uninstalled afterward with no trace.

**Do I need to do anything special in the game?** No — play World War 3 exactly as you normally would, on the real live servers.

**How do I know I did it right?** If Wireshark was recording *before* you joined the match, and you played for a couple of minutes, it's good. That's the only thing that matters.

---

*Thank you — this genuinely can't be recreated after August 3rd.*
