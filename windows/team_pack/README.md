# World War 3 — Menu Capture Pack (for teammates)

**Deadline: before 3 August 2026** (servers shut down after that)

George cannot log into WW3 on his PC right now. If **you** can get into the main menu, please run this pack and capture a few menu screens. It takes about **15–20 minutes**.

This is **not** Wireshark. The menu uses encrypted HTTPS, so we need this small recorder tool.

---

## Will this mess up my PC?

**Short answer: No — if you always run Stop when finished.**

| This pack does | This pack does **not** |
|---|---|
| Temporarily redirect 3 WW3 server names while recording | Install a fake Epic / root certificate |
| Need admin once (to edit the hosts file) | Redirect `api.epicgames.dev` |
| Restore those redirects when you click **Stop** | Permanently change Steam or other games |

The “Epic games won’t connect” problem some of us hit weeks ago came from a **different offline-mock tool**, not this pack.

**If anything feels wrong after recording:**

1. Double-click `windows\WW3-Recorder-Stop.ps1`
2. If that fails, double-click `windows\WW3-Recorder-Emergency-Cleanup.ps1`
3. Only if Epic games still fail from *old* testing: open `certmgr.msc` → Trusted Root Certification Authorities → delete a cert named like **WW3 Local Root CA** → reboot

---

## What you need

1. **Windows PC** with World War 3 on **Steam**
2. You must be able to **log in and reach the main menu**
3. **Python 3.11 or 3.12**  
   - Download: https://www.python.org/downloads/  
   - During install, tick **“Add python.exe to PATH”**
4. This zip, unzipped anywhere (Desktop is fine)  
   Keep the folder structure:

   ```
   WW3_Menu_Recorder_For_Team\
     README.md          ← you are here
     windows\
       WW3-Recorder-Start.ps1
       WW3-Recorder-Stop.ps1
       WW3-Recorder-Emergency-Cleanup.ps1
       ww3_record.ps1
     mockserver\
       record_proxy.py
       mock_cert.pem
       mock_key.pem
   ```

---

## Critical rule (read this)

**Log into the game menu FIRST. Start the recorder AFTER.**

If you start the recorder before login, auth often breaks (`Invalid Token` / empty token).  
That is expected with this tool — use the order below.

---

## Step-by-step

### Step 1 — Close WW3

Close the game and the WW3 launcher completely.

### Step 2 — Log in normally (recorder OFF)

1. Open **Steam**
2. Click **Play** on World War 3
3. Wait until you are fully in the **main menu** (not stuck on AUTHORIZATION)

Do **not** run any recorder script yet.

### Step 3 — Start the recorder

1. Open the unzipped folder
2. Double-click **`windows\WW3-Recorder-Start.ps1`**
3. Windows will ask for **Administrator** permission → click **Yes**
4. A PowerShell window opens. It will say something like **LOGIN FIRST** / press Enter when you are in the menu
5. Because you are already in the menu, press **Enter**
6. Leave that PowerShell window **open**. A dashboard page may open in your browser (`http://127.0.0.1:9009`) — that is optional; you can ignore it.

### Step 4 — Open the menu screens

In the game, open each screen slowly. Stay on each one for a few seconds so it can load:

| Done? | Screen |
|:---:|---|
| ☐ | **Challenges** — Daily, Weekly, Season tabs |
| ☐ | **Leaderboards / Scores** ← most important |
| ☐ | **Notifications** (bell / inbox) |
| ☐ | **Career / Statistics / Profile** |
| ☐ | **Shop** — browse every tab, **do not buy anything** ← most important |
| ☐ | **Battle Pass / Season progression** |
| ☐ | **Friends list** |
| ☐ | **Loadout / Customisation** — open a few weapons |
| ☐ | **Settings** |

**Optional but very useful:** play **one match all the way to the end** (final scoreboard + XP screen) with the recorder still running.

### Step 5 — Quit the game

Close World War 3 normally.

### Step 6 — Stop the recorder (always)

Double-click **`windows\WW3-Recorder-Stop.ps1`**  
→ Yes to admin if asked.

This:

- Stops the recorder  
- Restores your hosts / network  
- Copies log files to your **Desktop** named like `WW3_rec_....log`

**Do not skip this step.**

### Step 7 — Send the logs to George

Send all new Desktop files starting with **`WW3_rec_`**  
(or zip the whole `windows\record_logs\` folder if you see one).

WeTransfer / Google Drive / Discord — whatever is easiest. A few MB to tens of MB is normal.

---

## Quick checklist

1. ☐ Python installed (with PATH)  
2. ☐ Logged into WW3 **menu** first  
3. ☐ Ran **Start** → pressed Enter  
4. ☐ Opened Leaderboards + Shop (+ others)  
5. ☐ Ran **Stop**  
6. ☐ Sent `WW3_rec_*.log` files  

---

## Troubleshooting

| Problem | What to do |
|---|---|
| “Python not found” | Reinstall Python 3.12 and tick Add to PATH, then reopen the Start script |
| Login fails after I started the recorder | Run **Stop**, fully quit WW3, log in again **without** the recorder, then Start only after the menu |
| Other games / network feel broken | Run **Stop**, then **Emergency-Cleanup** |
| Admin prompt denied | The tool cannot work without admin (it must edit the hosts file briefly) |
| PowerShell says script is blocked | Right-click the `.ps1` → Properties → Unblock (if shown), or run Start again after: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Nothing useful in the logs | You must open the screens **after** pressing Enter on Start; opening them only before Start is not captured |

---

## What this is for (background)

We are preserving WW3 before the servers die. Match traffic is captured with Wireshark (separate job). Menu traffic (shop, leaderboards, etc.) needs this recorder.

Thank you — this is one of the last pieces we can still grab live.
