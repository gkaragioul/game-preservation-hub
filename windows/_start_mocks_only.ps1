# _start_mocks_only.ps1 - restart ONLY the four mock services, with the same log files
# ww3_mock.ps1 uses. Does NOT touch hosts, the CA, or the match server: this is for the
# case where the mock processes died but the network redirects are still in place.
$ErrorActionPreference = 'Stop'
$py  = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
$dir = 'F:\Dev_Work\GameDev\WW3\mockserver'
$log = 'F:\Dev_Work\GameDev\WW3\windows\mock_logs'

# stop any existing mock python processes first (leaves the match server alone)
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'rest_server\.py|hub_server\.py|xmpp_server\.py' } |
    ForEach-Object {
        Write-Host ("  stopping old pid {0}" -f $_.ProcessId)
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
Start-Sleep -Seconds 2

# The hub defaults to Landmark/TDM. The turn-9d pipeline is capture-grounded on
# GOBI + mode 47 (DOM_N) -- the replay stream comes from the Gobi capture, and
# Landmark's package path was never captured. Force Gobi or the client hangs on load.
$env:WW3_FORCE_LOBBY_MAP  = 'WW3_Gobi_New_P'
$env:WW3_FORCE_LOBBY_MODE = '47'
$env:WW3_CLIENT_LOG_CAPTURE = '1'
$env:WW3_CLIENT_LOG_NET = '1'

$specs = @(
    @{ n='https'; s='rest_server.py'; a=@('443','1'); e='https'        },
    @{ n='http';  s='rest_server.py'; a=@('80','0');  e='http'         },
    @{ n='hub';   s='hub_server.py';  a=@('8700');    e='hub_version4' },
    @{ n='xmpp';  s='xmpp_server.py'; a=@();          e='xmpp'         }
)
foreach ($s in $specs) {
    $out = Join-Path $log ($s.e + '.out.log')
    $err = Join-Path $log ($s.e + '.err.log')
    $p = Start-Process -FilePath $py -ArgumentList (@($s.s) + $s.a) `
            -WorkingDirectory $dir -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $out -RedirectStandardError $err
    Write-Host ("  started {0,-6} pid={1}  -> {2}" -f $s.n, $p.Id, $err)
    Start-Sleep -Milliseconds 400
}
Start-Sleep -Seconds 3
Write-Host "`n  listening:"
Get-NetTCPConnection -LocalPort 80,443,8700 -State Listen -ErrorAction SilentlyContinue |
    Select-Object LocalPort, OwningProcess | Format-Table -AutoSize
Get-NetTCPConnection -LocalPort 5222 -State Listen -ErrorAction SilentlyContinue |
    Select-Object LocalPort, OwningProcess | Format-Table -AutoSize
