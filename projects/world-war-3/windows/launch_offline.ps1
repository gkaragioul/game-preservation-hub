<#
    launch_offline.ps1 - launch the BACKUP game standalone (no Steam launcher, no
    real login), pointed at our mock backend, with OUR minted FXID token.

    This is the offline-launch experiment. Run the mocks first:
        .\ww3_mock.ps1 up
    Then launch a variant and read the game log:
        .\launch_offline.ps1 eac      # via EAC bootstrap (start_protected_game.exe)
        .\launch_offline.ps1 direct   # game exe directly + -Continent=SECRETMS (EAC bypass)
        .\launch_offline.ps1 log      # just open the newest WW3.log analysis

    The game runs with -log so it writes %LOCALAPPDATA%\WW3\Saved\Logs\WW3.log,
    which we analyze to see exactly where (if) it fails.
    Steam should be RUNNING for now (steam_api64.dll); we test fully-Steamless later.
#>
param(
    [Parameter(Position=0)][ValidateSet('eac','direct','log','grab','host','dedi')][string]$Mode='eac',
    [string]$Map='WW3_DMZ_P',
    [string]$GameMode='WW3ReconGameMode',   # DMZ's native mode; used by host/dedi
    [int]$Bots=0
)

$Game    = 'E:\WW3_Playable_Backup\World War 3'
$ExeDir  = "$Game\WW3\Binaries\Win64"
$TokFile = 'F:\Dev_Work\GameDev\WW3\mockserver\fxid_offline_token.txt'
$GameLog = "$env:LOCALAPPDATA\WW3\Saved\Logs\WW3.log"

if ($Mode -eq 'log') {
    & "$PSScriptRoot\analyze_log.ps1" -Path $GameLog
    return
}

if ($Mode -eq 'grab') {
    # pull the REAL fxid token from a currently-running (Steam-launched) game
    $p = Get-CimInstance Win32_Process -Filter "Name='WW3-Win64-Shipping.exe'" -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $p) { Write-Host "WW3-Win64-Shipping.exe not running. Launch WW3 via Steam first." -ForegroundColor Red; return }
    if ($p.CommandLine -match '--fxid-login-token=([A-Za-z0-9._-]+)') {
        $real = $Matches[1]
        Copy-Item $TokFile "$TokFile.synthetic.bak" -Force -ErrorAction SilentlyContinue
        Set-Content -Path $TokFile -Value $real -NoNewline -Encoding ASCII
        Write-Host "[OK] grabbed REAL token ($($real.Length) chars) -> $TokFile" -ForegroundColor Green
        Write-Host "     (synthetic token backed up to $TokFile.synthetic.bak)" -ForegroundColor Green
        Write-Host "     Now fully quit WW3, then:  .\launch_offline.ps1 eac" -ForegroundColor Green
    } else { Write-Host "no fxid-login-token found on the game command line." -ForegroundColor Red }
    return
}

if (-not (Test-Path $TokFile)) { throw "token file missing: $TokFile" }
$tok = (Get-Content $TokFile -Raw).Trim()

# clear the old game log so we read a fresh boot
if (Test-Path $GameLog) { Remove-Item $GameLog -Force -ErrorAction SilentlyContinue }

# Force Client Synchronization checklist into the log buffer (Shipping often only
# flushes on crash; still worth enabling + memory-scan fallback).
$CfgDir = "$env:LOCALAPPDATA\WW3\Saved\Config\WindowsNoEditor"
New-Item -ItemType Directory -Force -Path $CfgDir | Out-Null
$EngineIni = Join-Path $CfgDir 'Engine.ini'
# M4: WW3_NET_LOGCMDS=1 additionally turns up the replication categories. UE prints the
# reason an actor open bunch is refused (SerializeNewActor failure, queued-bunch timeout,
# corrupt partial bunch, unresolved NetGUID) in these categories, and the client uploads
# Warning+ lines to our hub, which now records them (WW3_CLIENT_LOG_CAPTURE).
$netLog = ($env:WW3_NET_LOGCMDS -eq '1')
$netLogCmds = 'LogNet Verbose,LogNetTraffic Verbose,LogNetPackageMap VeryVerbose,LogNetPartialBunch VeryVerbose,LogNetDormancy Verbose,LogSpawn Verbose,LogPlayerController Verbose'
$syncLogBlock = @"
[Core.Log]
LogWW3ClientSynchronization=VeryVerbose
LogWW3Player=Log
LogStreaming=Warning
"@
if ($netLog) {
    $syncLogBlock += @"

LogNet=Verbose
LogNetTraffic=Verbose
LogNetPackageMap=VeryVerbose
LogNetPartialBunch=VeryVerbose
LogSpawn=Verbose
LogPlayerController=Verbose
"@
}
if (Test-Path $EngineIni) {
    $existing = Get-Content $EngineIni -Raw -ErrorAction SilentlyContinue
    if ($existing -notmatch 'LogWW3ClientSynchronization') {
        Add-Content -Path $EngineIni -Value "`r`n$syncLogBlock" -Encoding ASCII
    }
} else {
    Set-Content -Path $EngineIni -Value $syncLogBlock -Encoding ASCII
}

# the command line the game expects (recovered from working logs) + -log
$common = @(
    '-pref_language','english',
    "--fxid-login-token=$tok",
    '-NoMrac',
    '-Region=meta.prod.ww3.fxtools.gl:443',
    '-FXGamesInit=1',
    '-NoSplash',
    '-NoStartupMovies',
    '-dx11',
    '-log',
    # Force an absolute path so failures before the normal Saved/Logs bootstrap
    # still leave an Unreal log for diagnosis (the old launcher could hang at the
    # Valve frame with no WW3.log at all).
    "-ABSLOG=$GameLog",
    '-FORCELOGFLUSH',
    ('-LogCmds=LogWW3ClientSynchronization VeryVerbose,LogWW3Player Log,LogStreaming Warning' +
     $(if ($netLog) { ',' + $netLogCmds } else { '' }))
)
if ($netLog) { Write-Host "[*] WW3_NET_LOGCMDS=1 -> net replication logging enabled on the client" -ForegroundColor Yellow }

if ($Mode -eq 'dedi') {
    # M3: launch the HEADLESS DEDICATED MATCH SERVER (no EAC wrapper, no GPU via -nullrhi).
    # It authenticates, fetches /events/getWebSocketUrl, connects to our hub as a server,
    # pulls game-mode rules, registers via /server/register, and hosts the map+mode.
    # Boot into the HUB level (WW3_Hub_P), NOT a match map. The hub is where HubManager
    # initializes + connects to the backend -> register -> then it travels to the assigned
    # match. A match map on the cmdline hosts immediately (skips hub-init) and crashes.
    # Keep the server role on the same validated transport baseline as the
    # reimplemented match server.  Without these explicit values a stale
    # shell environment can change packet grouping between runs.
    $env:WW3_WAM_EARLY_EMPTY_PARTS_REINFORCE = '1'
    $env:WW3_ISOLATE_EARLY_WPN = '1'
    $env:WW3_WAM_SOFTCLASS_STUB_4606 = '0'
    $env:WW3_WAM_SPAWN_ATTACH = '0'
    $entry = 'WW3_Hub_P'
    $srvArgs = @($entry,'-server','-nullrhi','-log',
                 'DedicatedServerGroup=default','Port=7871','GameServerQueryPort=27115',
                 '-Region=meta.prod.ww3.fxtools.gl:443','-FXGamesInit=1',"--fxid-login-token=$tok")
    Write-Host "[*] M3: launching HEADLESS dedicated server into hub level $entry (register-and-wait)" -ForegroundColor Cyan
    Write-Host "    args: $($srvArgs -join ' ')" -ForegroundColor DarkGray
    Write-Host "    watch OUR mock log for [M3] getWebSocketUrl / DEDICATED SERVER connected / server/register." -ForegroundColor Cyan
    Start-Process -FilePath "$ExeDir\WW3-Win64-Shipping.exe" -ArgumentList $srvArgs -WorkingDirectory $ExeDir
    return
}

if ($Mode -eq 'host') {
    # EXPERIMENT: host a real match map locally as a listen server.
    $url = $Map + '?listen'
    if ($GameMode) { $url = $Map + '?game=/Script/ShooterGame.' + $GameMode + '?listen' }
    if ($Bots -gt 0) { $url += ('?bots=' + $Bots) }
    Write-Host "[*] HOST experiment -> $url" -ForegroundColor Cyan
    Write-Host "    (listen-server map load; -FORCELOGFLUSH writes WW3.log live so we get diagnostics even on a clean exit)" -ForegroundColor Cyan
    Start-Process -FilePath "$Game\start_protected_game.exe" -ArgumentList (@($url) + $common) -WorkingDirectory $Game
}
elseif ($Mode -eq 'eac') {
    Write-Host "[*] launching via EAC bootstrap (start_protected_game.exe)..." -ForegroundColor Cyan
    # -FORCELOGFLUSH is in $common (needed for M4 sync diagnostics).
    Start-Process -FilePath "$Game\start_protected_game.exe" -ArgumentList $common -WorkingDirectory $Game
}
else {  # direct: bypass EAC wrapper with SECRETMS
    Write-Host "[*] launching game exe directly + -Continent=SECRETMS (EAC bypass)..." -ForegroundColor Cyan
    Start-Process -FilePath "$ExeDir\WW3-Win64-Shipping.exe" -ArgumentList ($common + @('-Continent=SECRETMS')) -WorkingDirectory $ExeDir
}

Write-Host "[*] launched. Watch it; when it stalls or the menu loads, run:" -ForegroundColor Green
Write-Host "      .\launch_offline.ps1 log     (analyzes the game's WW3.log)" -ForegroundColor Green
Write-Host "    Game log: $GameLog" -ForegroundColor Green
