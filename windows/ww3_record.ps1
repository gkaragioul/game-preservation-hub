<#
    ww3_record.ps1 - RECORDING mode for the WW3 revival.

    Puts the HTTPS recording proxy (mockserver/record_proxy.py) in front of the
    game's backend endpoints so we capture the real, decrypted request/response
    traffic (master auth response, profile, storage) while the servers are LIVE.

    What it redirects (game client = libcurl, ignores certs -> safe to MITM):
        meta.prod.ww3.fxtools.gl          (master / auth - THE key response)
        api.storage.fxtools.gl            (profile / loadout storage)
        endpoint.prod.wishlist.server.fxgam.es  (gateway)

    What it LEAVES LIVE (Chromium/EAC verify certs, or not on 443):
        id.wishlistgames.net  (launcher login)   api.epicgames.dev (EAC)
        xmpp.prod (5222)      vivox / sentry

    Usage (ELEVATED PowerShell):
        .\ww3_record.ps1 up      # resolve real IPs, redirect, start recorder
        .\ww3_record.ps1 status
        .\ww3_record.ps1 down    # stop, restore hosts, copy logs to Desktop

    IMPORTANT (login-first): starting the HTTPS MITM before login breaks
    /authenticate/fxgames (live meta returns Invalid Token through the proxy
    TLS path). Use 'live' — it waits until you are in the menu, THEN redirects.
#>
param([Parameter(Position=0)][ValidateSet('up','down','status','live')][string]$Action='status')
$ErrorActionPreference = 'Stop'

# Portable: works from George PC or a teammate zip (repo root = parent of /windows).
$RootDir   = Split-Path $PSScriptRoot -Parent
$MockDir   = Join-Path $RootDir 'mockserver'
$LogDir    = Join-Path $PSScriptRoot 'record_logs'
$HostsFile = "$env:WINDIR\System32\drivers\etc\hosts"
if (-not (Test-Path (Join-Path $MockDir 'record_proxy.py'))) {
    throw "record_proxy.py not found under $MockDir — keep the windows/ + mockserver/ folders together."
}
$MarkA     = '# === WW3 RECORD redirects (auto) ==='
$MarkB     = '# === end WW3 RECORD redirects ==='

# Game-client 443 endpoints to record (safe to MITM - libcurl bVerifyPeer=false).
$RecordHosts = @(
    'meta.prod.ww3.fxtools.gl',
    'api.storage.fxtools.gl',
    'endpoint.prod.wishlist.server.fxgam.es'
)

function Find-Python {
    foreach ($c in @("$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
                     "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe")) {
        if (Test-Path $c) { return $c }
    }
    $g = Get-Command python.exe -ErrorAction SilentlyContinue |
         Where-Object { $_.Source -notlike '*WindowsApps*' } | Select-Object -First 1
    if ($g) { return $g.Source }
    throw 'Python not found.'
}
function Assert-Admin {
    $p = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Run from an ELEVATED PowerShell (hosts file + port 443 need admin).'
    }
}
# Write the hosts file with retries -- AV / tamper-protection often locks it for
# a split second. Clears the read-only bit first. Returns $true on success.
function Write-HostsLines([string[]]$lines) {
    try { (Get-Item $HostsFile -Force).Attributes = 'Archive' } catch {}
    $text = ($lines -join "`r`n") + "`r`n"
    for ($i = 0; $i -lt 8; $i++) {
        try {
            [System.IO.File]::WriteAllText($HostsFile, $text, [System.Text.Encoding]::ASCII)
            return $true
        } catch {
            Start-Sleep -Milliseconds 400
        }
    }
    return $false
}
function Get-HostsLines {
    for ($i = 0; $i -lt 8; $i++) {
        try { return [System.IO.File]::ReadAllLines($HostsFile) }
        catch { Start-Sleep -Milliseconds 400 }
    }
    return @()
}
function Hosts-Filtered {
    # current hosts lines with our managed block removed
    $out = New-Object System.Collections.Generic.List[string]; $skip = $false
    foreach ($l in (Get-HostsLines)) {
        if ($l.Trim() -eq $MarkA) { $skip = $true; continue }
        if ($l.Trim() -eq $MarkB) { $skip = $false; continue }
        if (-not $skip) { $out.Add($l) }
    }
    return $out
}
function Hosts-Remove {
    if (-not (Write-HostsLines (Hosts-Filtered))) {
        Write-Host "  ! could not restore hosts (locked). Run STOP again, or edit $HostsFile." -ForegroundColor Yellow
    }
}
# Add our redirect block; returns $true if it stuck. Non-fatal on failure.
function Hosts-Add {
    $lines = @(Hosts-Filtered) + @($MarkA) + ($RecordHosts | ForEach-Object { "127.0.0.1`t$_" }) + @($MarkB)
    if (Write-HostsLines $lines) { ipconfig /flushdns | Out-Null; return $true }
    return $false
}
function Resolve-RealIPs {
    # Resolve via public DNS (1.1.1.1) so it ignores our own hosts redirects.
    # Keep ALL A records (array) so the proxy can retry auth on another node.
    $map = [ordered]@{}
    foreach ($h in $RecordHosts) {
        try {
            $addrs = @(Resolve-DnsName -Name $h -Type A -Server 1.1.1.1 -ErrorAction Stop |
                       Where-Object { $_.Type -eq 'A' } | ForEach-Object { $_.IPAddress } |
                       Select-Object -Unique)
            if ($addrs.Count -eq 1) { $map[$h] = $addrs[0] }
            elseif ($addrs.Count -gt 1) { $map[$h] = $addrs }
            if ($addrs.Count -gt 0) { Write-Host ("  {0,-42} -> {1} endpoint(s)" -f $h, $addrs.Count) }
        } catch { Write-Host "  ! resolve failed: $h" -ForegroundColor Red }
    }
    ($map | ConvertTo-Json -Compress) | Set-Content (Join-Path $MockDir 'real_ips.json') -Encoding ASCII
    return $map
}

switch ($Action) {
    'up' {
        Assert-Admin
        Write-Host '[*] resolving real backend IPs (via 1.1.1.1)...' -ForegroundColor Cyan
        $map = Resolve-RealIPs
        if ($map.Count -eq 0) { throw 'No IPs resolved; check internet/DNS.' }
        if (-not (Hosts-Add)) {
            Write-Host "  ! hosts file locked (antivirus?) - HTTPS redirect skipped; Hub/XMPP still captured." -ForegroundColor Yellow
        }
        New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
        # stop any prior proxy, then start
        Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -match 'record_proxy\.py' } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        $py = Find-Python
        $p = Start-Process $py -ArgumentList 'record_proxy.py','443',$LogDir `
            -WorkingDirectory $MockDir -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $LogDir 'proxy.out.log') `
            -RedirectStandardError  (Join-Path $LogDir 'proxy.err.log')
        $p.Id | Set-Content (Join-Path $LogDir 'proxy.pid')
        Start-Sleep -Seconds 2
        Write-Host "`n[OK] recording. Redirected -> 127.0.0.1:443 (proxy pid $($p.Id)):" -ForegroundColor Green
        $RecordHosts | ForEach-Object { Write-Host "     $_" }
        Write-Host "     Login (id.wishlistgames.net) + EAC left LIVE." -ForegroundColor Green
        Write-Host "     Now launch WW3 via Steam and play. Logs -> $LogDir" -ForegroundColor Green
        Write-Host "     When done:  .\ww3_record.ps1 down" -ForegroundColor Green
    }
    'down' {
        Assert-Admin
        $pidFile = Join-Path $LogDir 'proxy.pid'
        if (Test-Path $pidFile) { Stop-Process -Id (Get-Content $pidFile) -Force -ErrorAction SilentlyContinue; Remove-Item $pidFile -Force }
        Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -match 'record_proxy\.py' } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Hosts-Remove
        ipconfig /flushdns | Out-Null
        # copy captured logs to the Desktop
        $drop = [Environment]::GetFolderPath('Desktop')
        $stamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
        $n = 0
        if (Test-Path $LogDir) {
            Get-ChildItem $LogDir -Filter '*.log' | ForEach-Object {
                Copy-Item $_.FullName (Join-Path $drop "WW3_rec_$($_.BaseName)_$stamp.log") -Force; $n++
            }
        }
        if ($n -gt 0) { Write-Host "[OK] recorder stopped, hosts restored. $n log(s) copied to Desktop (WW3_rec_*.log)." -ForegroundColor Green }
        else { Write-Host "[OK] recorder stopped, hosts restored. No logs found to export." -ForegroundColor Yellow }
    }
    'live' {
        # Login-first: do NOT redirect hosts until the user is already in the menu.
        # FXID -> /authenticate/fxgames fails through the proxy TLS path; once the
        # game has a PlayerToken, later menu HTTPS calls record fine via MITM.
        Assert-Admin
        Write-Host '[*] resolving real backend IPs (via 1.1.1.1)...' -ForegroundColor Cyan
        $map = Resolve-RealIPs
        if ($map.Count -eq 0) { throw 'No IPs resolved; check internet/DNS.' }
        Hosts-Remove | Out-Null
        ipconfig /flushdns | Out-Null
        New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
        Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -match 'record_proxy\.py' } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

        Write-Host ""
        Write-Host "  LOGIN FIRST (hosts NOT redirected yet)" -ForegroundColor Yellow
        Write-Host "  1. Steam -> Play WW3  (recorder must stay off for login)" -ForegroundColor Yellow
        Write-Host "  2. Wait until you are IN THE MENU (not the auth error screen)" -ForegroundColor Yellow
        Write-Host "  3. Come back here and press Enter  ->  HTTPS recording starts" -ForegroundColor Yellow
        Write-Host "  4. Then open Leaderboards + Shop (and anything else to capture)" -ForegroundColor Yellow
        Write-Host "  5. When done: Ctrl+C in this window to stop + restore hosts" -ForegroundColor Yellow
        Write-Host ""
        Read-Host 'Press Enter when you are in the WW3 menu'

        if (-not (Hosts-Add)) {
            Write-Host "  ! hosts file locked (antivirus?) - HTTPS redirect skipped; Hub/XMPP still captured." -ForegroundColor Yellow
        }
        Write-Host "[*] opening dashboard http://127.0.0.1:9009 ..." -ForegroundColor Cyan
        Start-Process 'http://127.0.0.1:9009'
        Write-Host "[*] HTTPS recording ON. Use the menu now. Ctrl+C to stop.`n" -ForegroundColor Green
        $py = Find-Python
        Push-Location $MockDir
        try {
            & $py 'record_proxy.py' 443 $LogDir 9009
        } finally {
            Pop-Location
            Write-Host "`n[*] stopping + restoring..." -ForegroundColor Yellow
            Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
                Where-Object { $_.CommandLine -match 'record_proxy\.py' } |
                ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
            Hosts-Remove; ipconfig /flushdns | Out-Null
            $drop = [Environment]::GetFolderPath('Desktop'); $stamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
            $n = 0
            Get-ChildItem $LogDir -Filter '*.log' -ErrorAction SilentlyContinue | ForEach-Object {
                Copy-Item $_.FullName (Join-Path $drop "WW3_rec_$($_.BaseName)_$stamp.log") -Force; $n++
            }
            if ($n -gt 0) { Write-Host "[OK] hosts restored. $n log file(s) copied to Desktop (WW3_rec_*.log)." -ForegroundColor Green }
            else { Write-Host "[OK] hosts restored. No logs captured this run (nothing recorded yet)." -ForegroundColor Yellow }
        }
    }
    'status' {
        Write-Host '=== record proxy listening? ===' -ForegroundColor Cyan
        Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
            Where-Object { $_.LocalPort -eq 443 } | Select-Object LocalAddress,LocalPort,OwningProcess | Format-Table -AutoSize
        Write-Host '=== active RECORD hosts redirects ===' -ForegroundColor Cyan
        Select-String -Path $HostsFile -Pattern ($RecordHosts -join '|') -ErrorAction SilentlyContinue |
            ForEach-Object { "  $($_.Line.Trim())" }
        Write-Host "=== captured logs in $LogDir ===" -ForegroundColor Cyan
        if (Test-Path $LogDir) { Get-ChildItem $LogDir -Filter '*.log' | Select-Object Length,Name | Format-Table -AutoSize }
    }
}
