# WW3 private-server mock — Windows workflow

Windows replacement for the old Linux `launch_ww3_mock.sh`. The mock servers
themselves (`../mockserver/*.py`) are unchanged and cross-platform; only the
orchestration (hosts file, process launch, traffic redirect) is Windows-native.

## Prereqs (already installed on this machine)
- Python 3.12 (`%LOCALAPPDATA%\Programs\Python\Python312\python.exe`)
- pip packages: `websockets`, `cryptography`, `pydivert`
- Game at `E:\SteamLibrary\steamapps\common\World War 3` (build 1796 / v241002)

## The strategy
1. **Redirect backend hostnames via the Windows hosts file** -> `127.0.0.1`
   (meta.prod, api.public, xmpp.prod). FXID login (`id.fx.gl`) and EAC/EOS are
   left **live** so the launcher can mint a real token and the protected game starts.
2. The **Hub** is a raw IP the master server hands back. Our mock master controls
   that response, so we return `127.0.0.1` for the Hub — no IP redirect needed.
3. If the client ignores the hosts file (the c-ares bypass seen on Linux), fall
   back to `ww3_redirect.py` (WinDivert DNAT) on the real resolved IPs.

## Step 0 — baseline run (do this first)
Confirms the *current* build's command line, which backends it hits, and whether
the hosts file is honored on Windows.

1. Open an **elevated PowerShell**, `cd F:\Dev_Work\GameDev\WW3\windows`.
2. Launch WW3 normally from Steam. Let it stall (servers are down).
3. Analyze what happened:
   ```powershell
   .\analyze_log.ps1
   ```
   Note the `-Region=` host, any `Could not resolve host` lines, and the `ws://` Hub URL.

## Step 1 — run with mocks
From the **elevated PowerShell**:
```powershell
.\ww3_mock.ps1 up        # write hosts entries + start the 4 mock servers
```
Launch WW3 from Steam, then in another elevated window:
```powershell
.\ww3_mock.ps1 watch     # live-tail game + mock logs
```
After the attempt:
```powershell
.\analyze_log.ps1        # did meta.prod hit 127.0.0.1? did the Hub connect?
.\ww3_mock.ps1 down      # stop mocks, restore hosts
```

## Step 2 — if hostnames are NOT redirected (hosts ignored)
Get the real resolved IPs from the baseline `analyze_log.ps1` output (or
`Resolve-DnsName meta.prod.ww3.fxtools.gl`), then in a second elevated window:
```powershell
python ww3_redirect.py 89.167.40.140:443 213.183.62.234:8705   # example IPs
```
Leave it running alongside `ww3_mock.ps1 up`.

## Files
| file | purpose |
|------|---------|
| `ww3_mock.ps1`    | orchestrator: hosts + start/stop mocks + status/watch |
| `ww3_redirect.py` | WinDivert DNAT fallback (raw IPs -> 127.0.0.1) |
| `analyze_log.ps1` | extract auth sequence / stall point from a WW3.log |
| `logs\`           | per-mock stdout/stderr + pid files |

## Known open questions (resolve empirically)
- Does the Windows client honor the hosts file? (Linux c-ares did not.)
- Exact master-server auth **response** shape that carries the Hub address +
  Hub token — capture it from the first mock run and bake it into `rest_server.py`.
- Whether build 1796 changed any RPC contexts/methods vs the June log.
