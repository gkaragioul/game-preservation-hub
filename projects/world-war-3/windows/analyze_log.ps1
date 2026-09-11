<#
    analyze_log.ps1 - pull the important facts out of a WW3.log run, AND copy the
    raw log + this analysis to the Desktop every time (so they're easy to grab/paste).

    .\analyze_log.ps1                 # analyze the live game log
    .\analyze_log.ps1 -Path some.log  # analyze a specific log
#>
param([string]$Path = "$env:LOCALAPPDATA\WW3\Saved\Logs\WW3.log")

if (-not (Test-Path $Path)) { Write-Host "Log not found: $Path" -ForegroundColor Red; exit 1 }

# Drop copies directly on the Desktop (literally the Desktop, no subfolder).
$dropDir  = [Environment]::GetFolderPath('Desktop')
$stamp    = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
$rawCopy  = Join-Path $dropDir "WW3_$stamp.log"
$report   = Join-Path $dropDir "WW3_analysis_$stamp.txt"

Copy-Item -Path $Path -Destination $rawCopy -Force

$log = Get-Content $Path
$lines = New-Object System.Collections.Generic.List[string]
function Emit($text, $color = 'Gray') { Write-Host $text -ForegroundColor $color; $lines.Add($text) }

Emit "=== $Path  ($($log.Count) lines, $((Get-Item $Path).LastWriteTime)) ===" 'Cyan'
Emit ''

function Section($title, $pattern, [int]$max = 12) {
    Emit "--- $title ---" 'Yellow'
    $hits = $log | Select-String -Pattern $pattern | Select-Object -First $max
    if ($hits) { $hits | ForEach-Object { Emit ("  " + $_.Line.Trim()) } } else { Emit "  (none)" }
    Emit ''
}

Section 'Command line'            'LogInit: Command Line:'                                                     2
Section 'FXID / EOS auth'         'ConnectLoginFXID|Connect Login with FXID|EOS.*Auth|HTTP 401|Unauthorized'  10
Section 'DNS / redirect failures' 'Could not resolve host|Couldn.t resolve|libcurl error'                     12
Section 'Backend hosts contacted' 'https?://[a-z0-9.-]+\.(fxtools\.gl|fx\.gl|my\.games|ipify\.org)'           15
Section 'Master server'           'SetIsConnectedToMasterServer|MasterServerConnectionStatus|Authoriz'        10
Section 'Hub WebSocket'           'ws://|wss://|FLwsWebSocket.*Connect|WebSocket is not connected'            12
Section 'RPC traffic'             'RpcRequest|RpcResponse'                                                     10
Section 'XMPP'                    'xmpp|Xmpp|jabber'                                                           8
Section 'Errors / fatal'          'LogWW3.*Error|Fatal|Authorization|AUTHORIZATION'                           12

Emit "--- last 8 lines (where it stalled) ---" 'Yellow'
$log | Select-Object -Last 8 | ForEach-Object { Emit ("  " + $_.Trim()) }

$lines | Set-Content -Path $report -Encoding UTF8
Write-Host ''
Write-Host "[OK] copied to Desktop:" -ForegroundColor Green
Write-Host "     $rawCopy"  -ForegroundColor Green
Write-Host "     $report"   -ForegroundColor Green
