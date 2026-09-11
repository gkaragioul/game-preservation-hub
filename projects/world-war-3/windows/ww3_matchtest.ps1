<#
    ww3_matchtest.ps1 - LIVE-CLIENT test of our own match server (Path B, M1+M2).

    Brings up the forever-offline stack, starts OUR match server (match_server/server.py)
    on UDP 7871, and launches the game. When you matchmake in-game, the hub hands the
    client off to 127.0.0.1:7871 -- our server -- and we watch it run the real
    StatelessConnect handshake + NMT control channel against our code.

    Everything auto-cleans on exit (hosts redirects, CA, mocks, match server), so other
    EOS games stay safe.

        .\ww3_matchtest.ps1

    Run from an ELEVATED PowerShell.

    WHAT TO EXPECT in the match-server window:
        [match] <- InitialConnect ...        -> sent ConnectChallenge
        [match] *** HANDSHAKE COMPLETE ...   (M1 proven against the REAL client)
        [match]   <- NMT_Hello ...           -> NMT_Challenge
        [match]   <- NMT_Login VALID ...     -> NMT_Welcome        (M2 proven)
        [match]   <- NMT_Join                *** M4 START ***
        [match]       -> REPLAY bunch ...    (PC open, capture-faithful)
        [match]       queued N world bunches (drip-feed)
    Success for this milestone: connection holds while world stream drains; watch for
    client actor-channel traffic (moves). Full possession/movement is still M4 live work.
    Every packet is logged to match_server\live_log\session_*.jsonl for analysis.
#>
param(
    [string]$ForceMap = 'WW3_Gobi_New_P',   # known-good package path read off the wire
    [switch]$ReplaySpawn,                   # explicit: same as default PC open (compat)
    [switch]$ReplayFull,                    # queue entire stream from bunch 0 (no PC pre-send)
    [switch]$GenerateSpawn,                 # build PC open with our writers (bit-identical body)
    [switch]$NoWorldReplay,                 # PC open only — do not drip-feed world stream
    [switch]$NoEac,                         # launch via SECRETMS (no EAC) so we can memory-scan sync flags
    [int]$WorldLimit = 160                  # bunches after PC (GameState ~idx 119; 0 = full stream)
)
$ErrorActionPreference = 'Stop'
$W    = 'F:\Dev_Work\GameDev\WW3\windows'
$MS   = 'F:\Dev_Work\GameDev\WW3\match_server'
$PY   = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"

$matchProc = $null

function Invoke-Down {
    Write-Host "`n[*] tearing down: match server, redirects, CA, mocks..." -ForegroundColor Yellow
    if ($matchProc -and -not $matchProc.HasExited) {
        try { Stop-Process -Id $matchProc.Id -Force -EA SilentlyContinue } catch {}
    }
    & powershell -ExecutionPolicy Bypass -File "$W\ww3_mock.ps1" down
}

Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
    & powershell -ExecutionPolicy Bypass -File 'F:\Dev_Work\GameDev\WW3\windows\ww3_mock.ps1' down
} | Out-Null

try {
    if (-not (Test-Path $PY)) { throw "python not found at $PY" }

    Write-Host '[*] bringing up forever-offline stack...' -ForegroundColor Cyan
    # Align hub lobby map/mode with the match server spawn capture (Gobi / DOM_N by default).
    $env:WW3_PREF_MAP = $ForceMap
    $env:WW3_FORCE_LOBBY_MAP = $ForceMap
    if ($ForceMap -match 'Gobi') {
        $env:WW3_FORCE_LOBBY_MODE = '47'
    } elseif ($ForceMap -match 'Landmark|Shibuya|Senate|Backyards|Shopping') {
        $env:WW3_FORCE_LOBBY_MODE = '10'
    }
    Write-Host "[*] hub forced map=$ForceMap mode=$($env:WW3_FORCE_LOBBY_MODE)" -ForegroundColor Magenta
    & powershell -ExecutionPolicy Bypass -File "$W\ww3_mock.ps1" forever

    Write-Host "[*] starting OUR match server on UDP 7871 (map -> $ForceMap)..." -ForegroundColor Cyan
    $env:WW3_FORCE_MAP = $ForceMap
    if (-not $env:WW3_BOOTSTRAP) { $env:WW3_BOOTSTRAP = 'ownership' }
    # The real listen-server's LoadingMap->InGame edge is carried by the
    # first post-transition world actors (capture channels 113-118).  Keep
    # this narrow and deterministic instead of replaying the noisy full
    # ambient stream.
    if (-not $env:WW3_AMBIENT_LIMIT) { $env:WW3_AMBIENT_LIMIT = '26' }
    if (-not $env:WW3_AMBIENT_START) { $env:WW3_AMBIENT_START = '1935' }
    if (-not $env:WW3_AMBIENT_CHANNELS) { $env:WW3_AMBIENT_CHANNELS = '113,114,115,116,117,118' }
    if (-not $env:WW3_AMBIENT_PREREQS) { $env:WW3_AMBIENT_PREREQS = '400,401,402,403,1918,1919' }
    # Pin the validated early-weapon transport fixes for fresh sessions.  These
    # must not depend on whatever environment a previous Cursor/manual run left
    # behind: isolation prevents ch4/ch5 WAM opens co-bundling with pawn data,
    # and the empty-Parts reinforce lets the client revisit the SoftClass gate.
    $env:WW3_WAM_EARLY_EMPTY_PARTS_REINFORCE = '1'
    $env:WW3_ISOLATE_EARLY_WPN = '1'
    if ($null -eq $env:WW3_INV_ATTACH) { $env:WW3_INV_ATTACH = '1' }
    if ($null -eq $env:WW3_CAM_IM_AFTER_ACK) { $env:WW3_CAM_IM_AFTER_ACK = '1' }
    if ($null -eq $env:WW3_WPN_ATTACH) { $env:WW3_WPN_ATTACH = '1' }
    if ($null -eq $env:WW3_WAM_STRIP_CATALOG) { $env:WW3_WAM_STRIP_CATALOG = '1' }
    $env:WW3_WAM_SOFTCLASS_CATALOG = '0'
    $env:WW3_ACK_AUDIT = '1'
    # Keep the live harness aligned with the dedicated launcher.  The speculative
    # PlayerState reverse-rebind poisons the subsequent captured ch2 transition and
    # makes the client skip the source-8 bunch.
    if (-not $env:WW3_PS_REBIND) { $env:WW3_PS_REBIND = '0' }
    Write-Host "[*] WW3_BOOTSTRAP=$($env:WW3_BOOTSTRAP) WW3_AMBIENT_LIMIT=$($env:WW3_AMBIENT_LIMIT) WW3_STREAMING_PAUSE_MS=$($env:WW3_STREAMING_PAUSE_MS)" -ForegroundColor DarkGray
    if ($ReplayFull) {
        $env:WW3_REPLAY_SPAWN = '1'; $env:WW3_REPLAY_FULL = '1'
        Write-Host '[*] FULL REPLAY: streaming the real server''s entire early replication from bunch 0.' -ForegroundColor Magenta
    } elseif ($GenerateSpawn) {
        $env:WW3_GENERATE_SPAWN = '1'
        Write-Host '[*] GENERATE SPAWN: PC open built by our writers (captured RepLayout bits).' -ForegroundColor Magenta
    } elseif ($ReplaySpawn) {
        $env:WW3_REPLAY_SPAWN = '1'
        Write-Host '[*] REPLAY MODE: captured PC open (same as default).' -ForegroundColor Magenta
    } else {
        Remove-Item Env:\WW3_REPLAY_SPAWN -ErrorAction SilentlyContinue
        Remove-Item Env:\WW3_REPLAY_FULL  -ErrorAction SilentlyContinue
        Remove-Item Env:\WW3_GENERATE_SPAWN -ErrorAction SilentlyContinue
        Write-Host '[*] DEFAULT M4: capture-faithful PC open + OWNERSHIP bootstrap (HUD/stream/pawn/PS/GS).' -ForegroundColor Magenta
    }
    if ($NoWorldReplay) {
        $env:WW3_NO_WORLD_REPLAY = '1'
        Write-Host '[*] WW3_NO_WORLD_REPLAY=1 — PC only.' -ForegroundColor Yellow
    } else {
        Remove-Item Env:\WW3_NO_WORLD_REPLAY -ErrorAction SilentlyContinue
        $env:WW3_WORLD_LIMIT = "$WorldLimit"
        Write-Host "[*] WW3_WORLD_LIMIT=$WorldLimit (pawn is within first ~10 after PC)." -ForegroundColor DarkGray
    }
    # -u = unbuffered stdout, so you see the handshake/login lines LIVE in the window
    $serverLog = Join-Path $MS ("live_log\match_console_live_{0}.out.txt" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
    $matchProc = Start-Process -FilePath $PY -ArgumentList '-u','server.py','7871' `
                    -WorkingDirectory $MS -RedirectStandardOutput $serverLog `
                    -RedirectStandardError ($serverLog + '.err') -PassThru
    Write-Host "     server console: $serverLog" -ForegroundColor DarkGray
    Start-Sleep 2
    if ($matchProc.HasExited) { throw 'match server exited immediately -- check for errors' }
    Write-Host "[OK] match server running (pid $($matchProc.Id)) in its own window." -ForegroundColor Green

    Write-Host '[*] launching game...' -ForegroundColor Cyan
    if ($NoEac) {
        Write-Host '[*] NoEac: direct exe + -Continent=SECRETMS (memory-scanable; EAC off)' -ForegroundColor Magenta
        & powershell -ExecutionPolicy Bypass -File "$W\launch_offline.ps1" direct
    } else {
        & powershell -ExecutionPolicy Bypass -File "$W\launch_offline.ps1" eac
    }

    $p = $null
    for ($i=0; $i -lt 40 -and -not $p; $i++) { Start-Sleep 2; $p = Get-Process WW3-Win64-Shipping -EA SilentlyContinue }
    if ($p) {
        Write-Host "`n[OK] game running (pid $($p.Id)). SESSION ACTIVE." -ForegroundColor Green
        Write-Host '     >>> IN GAME: start matchmaking (Play / Quick Match).            <<<' -ForegroundColor Green
        Write-Host '     >>> Then WATCH THE MATCH-SERVER WINDOW for handshake/login/M4.  <<<' -ForegroundColor Green
        Write-Host '     >>> Expect Gobi; LOADING MAP should clear (PS 9362 bootstrap). <<<' -ForegroundColor Green
        Write-Host '     >>> If still hung: leave it up and tell the agent — we scan   <<<' -ForegroundColor Yellow
        Write-Host '     >>>   python match_server\scan_sync_status.py                 <<<' -ForegroundColor Yellow
        Write-Host '     >>> for live Client Sync flags (MapLevels/Inventory/…).       <<<' -ForegroundColor Yellow
        Write-Host '     >>> Close the game (or Ctrl-C here) to end + auto-clean.         <<<' -ForegroundColor Green
        Wait-Process -Id $p.Id
        Write-Host '[*] game closed.' -ForegroundColor Cyan
    } else {
        Write-Host '[!] game did not start within 80s -- tearing down anyway.' -ForegroundColor Yellow
    }
}
finally {
    Invoke-Down
    Get-EventSubscriber -SourceIdentifier PowerShell.Exiting -EA SilentlyContinue | Unregister-Event -EA SilentlyContinue
    Write-Host '[OK] session ended, networking fully restored. Safe to play other games.' -ForegroundColor Green
    Write-Host "[i] packet log: $MS\live_log\session_*.jsonl" -ForegroundColor Cyan
}
