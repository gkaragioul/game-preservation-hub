# WW3 Workspace Data Inventory
*Thorough sweep of everything in `F:\Dev_Work\GameDev\WW3`, rated by usefulness for the private-server revival. Compiled 2026-07-23.*

## ⭐ Crown jewel — CURRENT live endpoint map (from July 22 captures)
The real backends the client contacts **today** (servers live until 3 Aug 2026). Extracted from TLS SNI in `tcp.port == 443 ...pcap`, `1.pcap`, `Launcher.pcap`. This SUPERSEDES the June `WW3_ENDPOINT_MAP.md` (which listed the retired `id.fx.gl` / `api.public.dev`).

| Service | Host | Port | Role | Changed since June? |
|---|---|---|---|---|
| Identity / login | `id.wishlistgames.net` | 443 | FXID launcher login, mints token | **NEW** (was `id.fx.gl`) |
| Master / meta | `meta.prod.ww3.fxtools.gl` | 443 | authorises session, returns Hub addr+token | same |
| Gateway (?) | `endpoint.prod.wishlist.server.fxgam.es` | 443 | **NEW** — likely master/gateway entry | **NEW** |
| Asset/profile storage | `api.storage.fxtools.gl` | 443 | **NEW** — profile/loadout/asset store | **NEW** |
| Presence | `xmpp.prod.ww3.fxtools.gl` | 5222 | XMPP friends/keepalive | same |
| Hub (menu brain) | `213.183.62.234` (raw IP from master) | 8705 | WebSocket JSON-RPC | (June value) |
| Match/gameplay | `213.183.62.18` (per-match) | 7868 UDP | in-match replication | (DMZ sample) |
| Anti-cheat / EOS | `api.epicgames.dev` | 443 | Epic Online Services + EAC | same |
| Voice | `mt2p.vivox.com`, `mt2p.www.vivox.com` | 443 | Vivox voice chat | same |
| Crash reporting | `sentry.fxgam.es` | 443 | Sentry (ignore for revival) | — |

Port-80 traffic is only OS noise (cert revocation, windowsupdate) — **no game data on 80**.

## 📡 Network captures (`captures/` + root)
The richest raw material. Encrypted payloads (443) need the recording proxy to decrypt; UDP match data is plaintext-ish binary.

| File | Size | What it is | Value |
|---|---|---|---|
| `tcp.port == 443 YuFi 22 July 2026.pcap` | 181 MB | **Live** full HTTPS backend session (Jul 22) | hostnames only until decrypted |
| `captures/Launcher.pcap` | 12 MB | Launcher login flow (id.wishlistgames, epic, xmpp) | login sequence |
| `captures/Direct.pcap` | 697 KB | Direct client connection | handshake |
| `captures/1.txt` | 24 MB | **Decoded** match UDP frames (`213.183.62.18:7868`) | gameplay protocol |
| `captures/Match_tacops_DMZ_still.pcap` | 1.8 MB | Match: standing still | **replication baseline** |
| `captures/Match_tacops_DMZ_walk.pcap` | 2.7 MB | Match: walking | movement delta |
| `captures/Match_tacops_DMZ_rundash.pcap` | 3.4 MB | Match: running/dashing | movement delta |
| `captures/Match_tacops_DMZ_drive.pcap` | 4.4 MB | Match: driving vehicle | vehicle replication |
| `captures/Match_tacops_DMZ_combat_Infantry.pcapng` | 2.5 MB | Match: infantry combat | shots/damage |
| `captures/Match_tacops_DMZ_combat_tank.pcap` | 5.6 MB | Match: tank combat | vehicle+weapon |
| `captures/Match_tacops_DMZ_Capture.pcap` | 799 KB | Match: objective capture | objective events |
| `1.pcap`, `111.pcap` | small | Today's spot captures | confirms current endpoints |

The DMZ set is a **deliberate controlled dataset** — same map, one action isolated per capture (still→walk→run→drive→combat). That's the right method to diff and decode the UDP replication format. Hardest part of the project, but the data to start it exists.

## 🖥️ Mock servers (`mockserver/` = current; root = older dupes)
| File | Port | Status |
|---|---|---|
| `mockserver/hub_server.py` | 8705 | Hub WebSocket JSON-RPC (menu). Answers onlineParameters/notifications/friends + generic. Untested vs client. |
| `mockserver/rest_server.py` | 443/80 | Meta REST, self-signed TLS. Returns friends/time/auth-success. |
| `mockserver/xmpp_server.py` | 5222 | **PROVEN WORKING** — `message*.txt` show real client completing auth/bind/session/ping. |
| root `stub.py`, `stub (1).py`, `stub (2).py` | — | Old copies of the XMPP stub (identical). |
| root `api_server.py`, `https_server.py` | 80/443 | Superseded simple REST mocks. |

## 📜 Client logs & protocol evidence
- `analysis/crashes/Crashes/UE4CC-*/WW3.log` — **June "working-day" full client logs** (6167 lines). The source of the whole reverse-engineered flow: command line, FXID→EOS auth, `SetIsConnectedToMasterServer`, `ws://213.183.62.234:8705/client/<HubJWT>`, RPC message shapes, XMPP handshake. Two crash sets present, each with minidump + CrashContext.xml + WW3.log.
- `analysis/logs/cef3*.log` (12 files) — launcher CEF web logs.
- `message.txt` / `message (1..4).txt` — XMPP mock session logs (proof of working handshake), account `100001`.
- Desktop `WW3_launcher_app.log` — launcher app log from today's real login (account **100001**).

## 🔑 Auth / identity
- `mockserver/fxid_token.txt` — synthetic schema-correct FXID JWT (HS512).
- `mockserver/fxid_live_token.txt` — a captured/real-shaped token (id 100001).
- `mockserver/make_fxid_token.py` — mints schema-correct JWTs.
- `mockserver/check_fxid_schema.py` — validates JWT vs recovered 11-claim FXID schema.
- Real accounts seen: **100001** (current owner, level 11), 100001 & 39422 & 100001 (June-era logs/tokens).

## 🎮 Game-data artifacts
- Weapon ballistics graphs (PNG): `556`, `762(39/51)`, `9x18/9x19 pistol+smg`, `300`, `338`, `408`, `40`, `50ae`, `12g flechette/pump/semiauto` — damage/range curves for ~15 weapons, likely mined from game data or match captures.
- `image.png` (2.6 MB) — screenshot (unexamined visual).
- On live disk: `%LOCALAPPDATA%\WW3\Saved\SaveGames\ProfileSave.txt` — real live profile (playerId 100001, XP, faction, loadouts).

## 📦 Crash/asset archives (root ZIPs — large, redundant with extracted `analysis/`)
- `Crashes-*.zip` ×2 (293 MB each) — crash dumps (contain real FXID tokens — 264 recovered).
- `Match_tacops_DMZ-*.zip` (566 MB) — match capture bundle.
- `Direct-*.zip`, `Launcher-*.zip`, `ip-*.zip`, `Logs-*.zip`, `webcache_4430-*.zip` — raw capture bundles.

## 📄 Reports & tooling
- `WW3_ENDPOINT_MAP.md` — June architecture map (**now partly stale** — update with the table above).
- `WW3_Project_Progress_Report.html` / `.pdf` + `generate_progress_report.py` — narrative status.
- `generate_handover_pdf.py` — handover doc generator.
- `windows/` — the new Windows harness (ww3_mock.ps1, ww3_redirect.py, analyze_log.ps1, README).
- `cert.pem`/`key.pem`, `mockserver/mock_cert.pem`/`mock_key.pem` — self-signed certs (client doesn't verify).

## 🕳️ Key gaps still needed for revival (what the data does NOT yet contain)
1. **Plaintext master auth RESPONSE** — the exact JSON meta returns (Hub address + Hub token + profile bootstrap). Encrypted in the 443 pcap. → needs the **recording proxy** while servers are live.
2. **Full Hub RPC method set** for a real menu session (only the opening calls seen in June log).
3. **Behavior of the two NEW endpoints** — `endpoint.prod.wishlist.server.fxgam.es` and `api.storage.fxtools.gl` (didn't exist in June recon).
4. **UDP match protocol format** — captures exist; decoding not started.

## Recommended priority (given Aug 3 shutdown)
1. **Back up the 58 GB game install** off Steam's folder.
2. **Recording proxy** to capture plaintext for #1–#3 above across several live sessions.
3. Keep the DMZ UDP set safe for later match-server work (#4).
