# Restart hub with control HTTP :8701 + optional auto-match. No UI/KBM.
$ErrorActionPreference = 'Stop'
$Mock = 'F:\Dev_Work\GameDev\WW3\mockserver'
$LogDir = 'F:\Dev_Work\GameDev\WW3\windows\mock_logs'
$Py = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Get-CimInstance Win32_Process -Filter "Name='python.exe'" -EA SilentlyContinue |
  Where-Object { $_.CommandLine -match 'hub_server\.py' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }

Start-Sleep 1
$env:WW3_HUB_CONTROL_PORT = '8701'
# Auto-match seconds after client reconnect (0 = wait for Quick Play / findLobby).
$env:WW3_HUB_AUTO_MATCH_S = '0'
$env:WW3_FORCE_LOBBY_MAP = 'WW3_Gobi_New_P'
$env:WW3_FORCE_LOBBY_MODE = '47'

$p = Start-Process -FilePath $Py -ArgumentList @('hub_server.py','8700') `
  -WorkingDirectory $Mock -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput (Join-Path $LogDir 'hub.out.log') `
  -RedirectStandardError (Join-Path $LogDir 'hub.err.log')
$p.Id | Set-Content (Join-Path $LogDir 'hub.pid')
Start-Sleep 2
"hub_pid=$($p.Id) exited=$($p.HasExited)"
Get-NetTCPConnection -State Listen -LocalPort 8700,8701 -EA SilentlyContinue |
  Select-Object LocalPort,OwningProcess | Format-Table -AutoSize
