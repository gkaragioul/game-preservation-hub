$ErrorActionPreference = "Continue"
$Mock = "F:\Dev_Work\GameDev\WW3\mockserver"
$LogDir = "F:\Dev_Work\GameDev\WW3\windows\mock_logs"
$Py = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$log = Join-Path $LogDir "hub_bounce_elev.txt"
"start $(Get-Date -Format o)" | Set-Content $log

# Kill anything listening on 8700/8701
Get-NetTCPConnection -State Listen -LocalPort 8700,8701 -EA SilentlyContinue | ForEach-Object {
  "killing listener pid=$($_.OwningProcess) port=$($_.LocalPort)" | Tee-Object $log -Append
  Stop-Process -Id $_.OwningProcess -Force -EA SilentlyContinue
}
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -EA SilentlyContinue |
  Where-Object { $_.CommandLine -match "hub_server\.py" } |
  ForEach-Object {
    "killing hub cmdline pid=$($_.ProcessId)" | Tee-Object $log -Append
    Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue
  }
Start-Sleep 2

$env:WW3_HUB_CONTROL_PORT = "8701"
$env:WW3_CLIENT_LOG_CAPTURE = "1"
$env:WW3_FORCE_LOBBY_MAP = "WW3_Gobi_New_P"
$env:WW3_FORCE_LOBBY_MODE = "47"
$env:WW3_HUB_AUTO_MATCH_S = "0"

$p = Start-Process -FilePath $Py -ArgumentList @("hub_server.py","8700") `
  -WorkingDirectory $Mock -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput (Join-Path $LogDir "hub.out.log") `
  -RedirectStandardError (Join-Path $LogDir "hub.err.log")
$p.Id | Set-Content (Join-Path $LogDir "hub.pid")
"hub_pid=$($p.Id) exited=$($p.HasExited)" | Tee-Object $log -Append
Start-Sleep 2
Get-NetTCPConnection -State Listen -LocalPort 8700,8701 -EA SilentlyContinue |
  ForEach-Object { "listen port=$($_.LocalPort) pid=$($_.OwningProcess)" | Tee-Object $log -Append }
