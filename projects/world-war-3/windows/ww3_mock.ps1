<#
    ww3_mock.ps1 - SERVE mode: run the private-server mocks and point the game at them.

    Unlike record mode (ww3_record.ps1), the mocks here SERVE the captured data
    (replay_map.json) instead of forwarding to the real servers -- this is the
    private-server boot attempt.

    Phases:
      up    (Phase A) : redirect meta / storage / gateway -> local mocks; hub stays REAL.
                        Validates the HTTP tier with the real hub as a crutch.
      full  (Phase B) : also redirect xmpp.prod (the hub shares that IP) to try to
                        catch the Hub on our local hub_server too.
      down            : stop mocks, restore hosts.
      status | watch  : inspect / live-tail.

    Run from an ELEVATED PowerShell. Keep real login (id.wishlistgames) + EAC LIVE.
    After 'up'/'full', launch WW3 via Steam and watch the mock logs.
#>
param([Parameter(Position=0)][ValidateSet('up','full','forever','down','status','watch')][string]$Action='status')
$ErrorActionPreference = 'Stop'

$MockDir   = 'F:\Dev_Work\GameDev\WW3\mockserver'
$LogDir    = 'F:\Dev_Work\GameDev\WW3\windows\mock_logs'
$HostsFile = "$env:WINDIR\System32\drivers\etc\hosts"
$MarkA     = '# === WW3 MOCK redirects (auto) ==='
$MarkB     = '# === end WW3 MOCK redirects ==='

# Game-client endpoints to redirect to our mocks (libcurl, no cert check).
$HostsA = @('meta.prod.ww3.fxtools.gl','api.storage.fxtools.gl','endpoint.prod.wishlist.server.fxgam.es')
$HostsB = $HostsA + @('xmpp.prod.ww3.fxtools.gl')   # + hub-catch attempt via xmpp host
$HostsF = $HostsB + @('api.epicgames.dev')          # + Epic EOS-Auth (forged by the faker) = forever-offline

# Our root CA -- must be a Windows Trusted Root so the EOS SDK accepts our epic_cert.
$CA     = "$MockDir\epic_ca\rootCA.pem"
$CAName = 'WW3 Local Root CA'

# Mock processes: name, script, args.
$Servers = @(
    @{ Name='https'; Script='rest_server.py'; Args=@('443','1') },
    @{ Name='http';  Script='rest_server.py'; Args=@('80','0')  },
    @{ Name='hub';   Script='hub_server.py';  Args=@('8700')    },
    @{ Name='xmpp';  Script='xmpp_server.py'; Args=@()          }
)

function Find-Python {
    foreach ($c in @("$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
                     "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe")) { if (Test-Path $c) { return $c } }
    $g = Get-Command python.exe -ErrorAction SilentlyContinue | Where-Object { $_.Source -notlike '*WindowsApps*' } | Select-Object -First 1
    if ($g) { return $g.Source }; throw 'Python not found.'
}
function Assert-Admin {
    $p = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run from an ELEVATED PowerShell.' }
}
function Write-HostsLines([string[]]$lines) {
    try { (Get-Item $HostsFile -Force).Attributes = 'Archive' } catch {}
    $text = ($lines -join "`r`n") + "`r`n"
    for ($i=0; $i -lt 8; $i++) { try { [System.IO.File]::WriteAllText($HostsFile,$text,[System.Text.Encoding]::ASCII); return $true } catch { Start-Sleep -Milliseconds 400 } }
    return $false
}
function Hosts-Filtered {
    $out = New-Object System.Collections.Generic.List[string]; $skip=$false
    foreach ($l in ([System.IO.File]::ReadAllLines($HostsFile))) {
        if ($l.Trim() -eq $MarkA) { $skip=$true; continue }
        if ($l.Trim() -eq $MarkB) { $skip=$false; continue }
        if (-not $skip) { $out.Add($l) }
    }
    return $out
}
function Hosts-Set([string[]]$redirect) {
    $lines = @(Hosts-Filtered)
    if ($redirect) { $lines += @($MarkA) + ($redirect | ForEach-Object { "127.0.0.1`t$_" }) + @($MarkB) }
    if (Write-HostsLines $lines) { ipconfig /flushdns | Out-Null; return $true }
    return $false
}
function Stop-Mocks {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'rest_server\.py|hub_server\.py|xmpp_server\.py' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}
function Install-CA {
    if (-not (Test-Path $CA)) { Write-Host "  ! CA missing: $CA" -ForegroundColor Yellow; return }
    certutil -addstore -f Root "$CA" | Out-Null
    Write-Host "[+] CA installed as Trusted Root ($CAName) -- EOS SDK will accept our Epic cert." -ForegroundColor Green
}
function Remove-CA {
    certutil -delstore Root "$CAName" 2>$null | Out-Null
    Write-Host "[+] CA removed from Trusted Root." -ForegroundColor Green
}
function Start-Mocks {
    $py = Find-Python
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    foreach ($s in $Servers) {
        $p = Start-Process $py -ArgumentList (@($s.Script)+$s.Args) -WorkingDirectory $MockDir -WindowStyle Hidden -PassThru `
             -RedirectStandardOutput (Join-Path $LogDir "$($s.Name).out.log") -RedirectStandardError (Join-Path $LogDir "$($s.Name).err.log")
        $p.Id | Set-Content (Join-Path $LogDir "$($s.Name).pid")
        Write-Host ("[+] {0,-6} pid={1}  ({2} {3})" -f $s.Name,$p.Id,$s.Script,($s.Args -join ' '))
    }
    Start-Sleep -Seconds 2
}
function Boot($redirect,$label) {
    Assert-Admin; Stop-Mocks
    if (-not (Hosts-Set $redirect)) { Write-Host '  ! hosts locked (antivirus?) - retry or disable tamper protection.' -ForegroundColor Yellow }
    Start-Mocks
    Write-Host "`n[OK] $label up. Redirected -> 127.0.0.1:" -ForegroundColor Green
    $redirect | ForEach-Object { Write-Host "     $_" }
    Write-Host "     Login (id.wishlistgames) + EAC left LIVE. Launch WW3 via Steam." -ForegroundColor Green
    Write-Host "     Watch:  .\ww3_mock.ps1 watch   |   Stop:  .\ww3_mock.ps1 down" -ForegroundColor Green
}

switch ($Action) {
    'up'   { Boot $HostsA 'Phase A (HTTP mocks, hub REAL)' }
    'full' { Boot $HostsB 'Phase B (HTTP + hub-catch via xmpp host)' }
    'forever' {
        Assert-Admin; Install-CA
        Boot $HostsF 'FOREVER-OFFLINE (mocks + Epic EOS-Auth forged, no real Epic)'
        Write-Host "     Epic api.epicgames.dev -> FORGED (10y tokens). Launch:  .\launch_offline.ps1 eac" -ForegroundColor Green
        Write-Host "     Use a SYNTHETIC token now:  copy fxid_offline_token.txt.synthetic.bak over the token file." -ForegroundColor Green
    }
    'down' {
        Assert-Admin; Stop-Mocks; Hosts-Set @() | Out-Null; Remove-CA
        Write-Host '[OK] mocks stopped, hosts restored, CA removed.' -ForegroundColor Green
    }
    'status' {
        Write-Host '=== listening (want 80,443,5222,8700) ===' -ForegroundColor Cyan
        Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in 80,443,5222,8700 } |
            Select-Object LocalAddress,LocalPort | Sort-Object LocalPort -Unique | Format-Table -AutoSize
        Write-Host '=== active MOCK redirects ===' -ForegroundColor Cyan
        Select-String -Path $HostsFile -Pattern ($HostsB -join '|') -ErrorAction SilentlyContinue | ForEach-Object { "  $($_.Line.Trim())" }
    }
    'watch' {
        $files = Get-ChildItem $LogDir -Filter '*.log' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
        $gl = "$env:LOCALAPPDATA\WW3\Saved\Logs\WW3.log"; if (Test-Path $gl) { $files += $gl }
        if ($files) { Get-Content -Path $files -Tail 4 -Wait } else { Write-Host 'No logs yet.' }
    }
}
