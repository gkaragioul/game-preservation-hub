<#
  ww3_play_dedicated.ps1 - ONE operator button for Path B dedicated match.

  Assumes mocks already up (`ww3_mock.ps1 forever` elevated once).
  Then: match server + NoEAC game + optional Dumper-7 inject.

  Usage (elevated recommended for inject):
    .\windows\ww3_play_dedicated.ps1
    .\windows\ww3_play_dedicated.ps1 -InjectDumper
    .\windows\ww3_play_dedicated.ps1 -AckAudit -NetLogCmds   # M4 possession diagnosis
    .\windows\ww3_play_dedicated.ps1 -NoGame -AckAudit -PawnExportPrefix   # M4 experiment #1, server only
    # M4 experiments #2 + #3B (ClientRestart is ON unless -NoClientRestart):
    .\windows\ww3_play_dedicated.ps1 -NoGame -AckAudit -PawnExportPrefix `
        -RestartMustMap -RestartAfterPawnMs 1500 -RestartRequireCh3Ack `
        -RestartMbmFallbackSec 8 -PcSetPawn
#>
param(
    [string]$ForceMap = 'WW3_Gobi_New_P',
    [switch]$InjectDumper,
    [switch]$NoGame,
    # M4 observability: watch whether the client acks the pawn-open datagram, and turn up
    # the client's own replication logging (it uploads Warning+ lines to our hub, which
    # records them under match_server/live_log/client_log/).
    [switch]$AckAudit,
    [switch]$NetLogCmds,
    # M4 experiment #1 (agent consult 20260805_191543): pre-register the pawn open's
    # archetype+level NetGUID chain on ch2 before the (untouched) ch3 pawn open.
    [switch]$PawnExportPrefix,
    # M4 experiment #2: single-shot ClientRestart(39), no wire-10 Retry.
    # ON BY DEFAULT. `-ClientRestart` used to be opt-in and defaulted the env var to '0',
    # which silently overrode server.py's own default of '1' — session 20260805_193023 ran
    # the whole export-prefix experiment with possession structurally impossible. Restart is
    # now the default and must be turned off explicitly.
    # Do NOT set WW3_CLIENT_RESTART_HANDLE here — possess_rpc / class_net_cache_ww3.json
    # default to dump-derived handle 39. Old hardcode '9' was a halved packed-int decode.
    [switch]$NoClientRestart,
    # MustBeMapped framing for that Restart, plus a single opposite-framing follow-up shot
    # after N seconds (0 = none) so a silent MustBeMapped run still yields an Ack oracle.
    [switch]$RestartMustMap,
    [int]$RestartMbmFallbackSec = 0,
    # Ordering guarantees: hold the Restart until N ms after the ch3 pawn open, and (with
    # -AckAudit) until the client has ACKed the packet carrying that open.
    [int]$RestartAfterPawnMs = 0,
    [switch]$RestartRequireCh3Ack,
    # M4 experiment #3B: re-state APlayerController::Pawn = 9372 on ch2 immediately before
    # the Restart RPC.
    [switch]$PcSetPawn,
    # M4 diagnostic: preserve the captured weapon attachment catalog instead of
    # applying the offline empty-catalog rewrite. This changes only WAM content.
    [switch]$NativeWamCatalog,
    # M4 diagnostic: withhold all attachment-manager channels until after the
    # initial world/possession gate. This is a server-only sequencing switch.
    [switch]$SkipAttachments,
    # M5 (LOADING MAP): how much of the capture to replay *after* the ownership bootstrap.
    # Default 120 replays the captured foreign PlayerState/GameState follow-up state;
    # pass -AmbientLimit 0 only for a deliberately minimal possession diagnostic.
    # -AmbientChannels owned
    # keeps the extra bunches on channels the bootstrap already opened (2/3/4/5/7/53), i.e.
    # more of the local player's own PlayerState / pawn / weapon state and the capture's own
    # ch2 Client_* RPCs, without introducing actors on channels the client never opened.
    # 'all' | 'owned' | explicit list such as '7,4'. Run 20260807_044918 showed that the
    # full owned set is NOT safe: adding the capture's later ch2 (PlayerController) bunches
    # made the client send CHANNEL CLOSE before it ever Acked possession.
    [int]$AmbientLimit = 120,
    [string]$AmbientChannels = '7,53',
    [switch]$CaptureOrder
)
$ErrorActionPreference = 'Stop'
$W = 'F:\Dev_Work\GameDev\WW3\windows'
$MS = 'F:\Dev_Work\GameDev\WW3\match_server'
$PY = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
$Dump = 'F:\Dev_Work\GameDev\WW3\tools\ue_netdump'

$env:WW3_FORCE_MAP = $ForceMap
$env:WW3_FORCE_LOBBY_MAP = $ForceMap
$env:WW3_PREF_MAP = $ForceMap
if ($ForceMap -match 'Gobi') { $env:WW3_FORCE_LOBBY_MODE = '47' }
$env:WW3_HUB_AUTO_MATCH_S = '5'
$env:WW3_BOOTSTRAP = $(if ($CaptureOrder) { 'capture_order' } else { 'ownership' })
$env:WW3_AMBIENT_LIMIT = "$AmbientLimit"
$env:WW3_AMBIENT_CHANNELS = $AmbientChannels
$env:WW3_STREAMING_PAUSE_MS = '15000'
$env:WW3_WAIT_GAMEPLAY_DOM = '1'
$env:WW3_WAIT_SPAWN_LEVEL_VIS = '1'
$env:WW3_SPAWN_LEVEL_VIS_TIMEOUT_S = '30'
# Clear diagnostic-only client RPC experiments inherited from earlier shells.
# They remain available when explicitly set after launching the server, but a
# normal dedicated-server run must not inject a stale level path/state name.
$env:WW3_CLIENT_STREAM_STATUS_PATH = $(if ($env:WW3_CLIENT_STREAM_STATUS_PATH) { $env:WW3_CLIENT_STREAM_STATUS_PATH } else { '' })
$env:WW3_CLIENT_GOTO_STATE = $(if ($env:WW3_CLIENT_GOTO_STATE) { $env:WW3_CLIENT_GOTO_STATE } else { '' })
$env:WW3_CLIENT_PLAYER_RESPAWNED_MOVEMENT = ''
# Keep the speculative two-parameter callback opt-in until its exact wire shape
# is proven against a live client; malformed RPC property framing causes a
# client-side mismatch and masks the otherwise working possession path.
$env:WW3_BEFORE_SPECTATOR_RETURN = $(if ($env:WW3_BEFORE_SPECTATOR_RETURN -eq '1') { '1' } else { '0' })
$env:WW3_STRIP_EXPORT_CHECKSUM = '0'
$env:WW3_PAWN_NO_SCALE = '0'
$env:WW3_WAM_SOFTCLASS_STUB_4606 = '0'
$env:WW3_WAM_SPAWN_ATTACH = '0'
$env:WW3_WAM_EARLY_EMPTY_PARTS_REINFORCE = '1'
$env:WW3_ISOLATE_EARLY_WPN = '1'
$env:WW3_INV_ATTACH = '1'
$env:WW3_CAM_IM_AFTER_ACK = '1'
$env:WW3_WPN_ATTACH = '1'
$env:WW3_CLOTHING_RESEND = '1'
$env:WW3_CLEAR_SPECTATOR_WAITING = '0'
$env:WW3_CAM_STRIP_CATALOG = '1'
$env:WW3_WAM_STRIP_CATALOG = $(if ($NativeWamCatalog) { '0' } else { '1' })
$env:WW3_WAM_STRIP_CHANNELS = 'inv'
$env:WW3_WAM_SOFTCLASS_CATALOG = '0'
# Native WAM catalogs need their BP_WP_* SoftClass exports present before the
# client runs CreateAttachments.  Without these exports the catalog is valid on
# the wire but leaves native streamable handles pending forever.
$env:WW3_WAM_SOFTCLASS_EXPORT = $(if ($NativeWamCatalog) { '1' } else { '0' })
$env:WW3_WAM_SOFTCLASS_WARM_EXPORT = '1'
$env:WW3_WAM_SOFTCLASS_MODE = 'full'
$env:WW3_SKIP_ATTACHMENTS = $(if ($SkipAttachments) { '1' } else { '0' })
$env:WW3_DEFER_ATTACHMENTS_MS = $(if ($SkipAttachments) { '5000' } else { '0' })
$env:WW3_CLIENT_RESTART = $(if ($NoClientRestart) { '0' } else { '1' })
$env:WW3_CLIENT_RESTART_MUSTMAP = $(if ($RestartMustMap) { '1' } else { '0' })
Remove-Item Env:WW3_CLIENT_RESTART_HANDLE -ErrorAction SilentlyContinue
$env:WW3_CLIENT_RESTART_SEND_RETRY = '0'
# Allow a small number of correctly-gated retries.  A single early shot can be
# lost while UE finishes map streaming; the server now enforces the settle gate,
# so these retries are bounded and materially improve recovery on slow clients.
$env:WW3_CLIENT_RESTART_MAX_SPRAYS = '4'
$env:WW3_CLIENT_RESTART_DELAY_S = '2.0'
$env:WW3_CLIENT_RESTART_AFTER_PAWN_MS = "$RestartAfterPawnMs"
$env:WW3_CLIENT_RESTART_REQUIRE_CH3_ACK = $(if ($RestartRequireCh3Ack) { '1' } else { '0' })
$env:WW3_CLIENT_RESTART_GATE_TIMEOUT_S = '20'
$env:WW3_CLIENT_RESTART_MBM_FALLBACK_S = "$RestartMbmFallbackSec"
$env:WW3_PC_SET_PAWN = $(if ($PcSetPawn) { '1' } else { '0' })
$env:WW3_PS_SET_PLAYERCHAR = '1'
$env:WW3_PAWN_SYNTH_PROPS = '1'
$env:WW3_PAWN_SYNTH_AFTER_ACK_ONLY = '1'
$env:WW3_PS_REBIND = '0'
$env:WW3_POST_ATTACH_RESTART = '1'
# Preserve an explicit A/B override from the caller; default to the native
# post-pawn PC-state replay when no override was supplied.
$env:WW3_POST_PAWN_PC_STATE = $(if ($env:WW3_POST_PAWN_PC_STATE -eq '0') { '0' } else { '1' })
$env:WW3_PAWN_EXPORT_PREFIX = $(if ($PawnExportPrefix) { '1' } else { '0' })
$env:WW3_ACK_AUDIT = '1'
$env:WW3_NET_LOGCMDS = $(if ($NetLogCmds) { '1' } else { '0' })

# Stop previous match on 7871
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
    $_.CommandLine -match 'server\.py.*7871'
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }

$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$logDir = Join-Path $MS 'live_log'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$out = Join-Path $logDir "match_console_$ts.out.txt"
$err = Join-Path $logDir "match_console_$ts.err.txt"
Set-Content (Join-Path $logDir 'CURRENT_CONSOLE.txt') $out

Write-Host "[*] match server UDP 7871 map=$ForceMap bootstrap=$($env:WW3_BOOTSTRAP) ackAudit=$($env:WW3_ACK_AUDIT) pawnExportPrefix=$($env:WW3_PAWN_EXPORT_PREFIX) clientRestart=$($env:WW3_CLIENT_RESTART) mustMap=$($env:WW3_CLIENT_RESTART_MUSTMAP) mbmFallbackS=$($env:WW3_CLIENT_RESTART_MBM_FALLBACK_S) afterPawnMs=$($env:WW3_CLIENT_RESTART_AFTER_PAWN_MS) requireCh3Ack=$($env:WW3_CLIENT_RESTART_REQUIRE_CH3_ACK) pcSetPawn=$($env:WW3_PC_SET_PAWN) ambient=$($env:WW3_AMBIENT_LIMIT)/$($env:WW3_AMBIENT_CHANNELS)" -ForegroundColor Cyan
Write-Host "    (server.py repeats these in its own console log - see the 'possession flags' banner)" -ForegroundColor DarkGray
# Absolute path — Start-Process + relative 'server.py' has bitten us (wrong argv / early exit).
$match = Start-Process -FilePath $PY -ArgumentList @('-u',"$MS\server.py",'7871') `
    -WorkingDirectory $MS -RedirectStandardOutput $out -RedirectStandardError $err -PassThru -WindowStyle Hidden
Start-Sleep 2
if ($match.HasExited) { Get-Content $err -ErrorAction SilentlyContinue; throw 'match server exited' }
Write-Host "[OK] match pid $($match.Id)" -ForegroundColor Green
Write-Host "     log: $out" -ForegroundColor DarkGray

if (-not $NoGame) {
    Write-Host '[*] launching NoEAC game...' -ForegroundColor Cyan
    & powershell -ExecutionPolicy Bypass -File (Join-Path $W 'launch_offline.ps1') direct
    $p = $null
    for ($i = 0; $i -lt 60 -and -not $p; $i++) {
        Start-Sleep 2
        $p = Get-Process WW3-Win64-Shipping -EA SilentlyContinue
    }
    if (-not $p) { throw 'game did not start' }
    Write-Host "[OK] game pid $($p.Id)" -ForegroundColor Green
    # Windows Identify #4 = LG 100Hz (\\.\DISPLAY4 @ ~4480,141) — not MSI at 2560.
    $env:WW3_UI_DISPLAY = '4'
    $env:WW3_UI_MONITOR = '4'
    Start-Sleep 5
    & $PY (Join-Path $MS 'auto_ui.py') place --monitor 4
    Write-Host '     UI locked to DISPLAY4 LG 100Hz; agent drives match (no operator clicks)' -ForegroundColor Yellow

    if ($InjectDumper) {
        Write-Host '[*] waiting 90s for menu/assets before inject...' -ForegroundColor Cyan
        Start-Sleep 90
        & powershell -ExecutionPolicy Bypass -File (Join-Path $Dump 'inject_dumper7.ps1')
    }
}

Write-Host '[*] operator watch commands:' -ForegroundColor Cyan
Write-Host "    Get-Content '$out' -Wait -Tail 40"
Write-Host '    python match_server\scan_sync_status.py'
Write-Host '    python match_server\watch_client_log.py --follow    # client-side UE warnings'
Write-Host 'Success signal in match log: AckPossession(Pawn 9372)'
