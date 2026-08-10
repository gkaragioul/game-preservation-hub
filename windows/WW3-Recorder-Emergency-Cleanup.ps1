# WW3-Recorder-Emergency-Cleanup.ps1
# Double-click if other games break after recording. Self-elevates.
# Removes WW3 recorder hosts redirects + kills record_proxy. Does NOT touch Epic CA
# (the menu recorder never installs one). For leftover Epic CA from OLD offline
# mock testing, see the note at the bottom.
$ErrorActionPreference = 'Stop'
$p = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell -Verb RunAs -ArgumentList @(
        '-NoExit','-ExecutionPolicy','Bypass','-File',"`"$PSCommandPath`"")
    return
}

$HostsFile = "$env:WINDIR\System32\drivers\etc\hosts"
$MarkA = '# === WW3 RECORD redirects (auto) ==='
$MarkB = '# === end WW3 RECORD redirects ==='

Write-Host '[*] Emergency cleanup — WW3 menu recorder leftovers' -ForegroundColor Cyan

# Kill recorder
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -EA SilentlyContinue |
    Where-Object { $_.CommandLine -match 'record_proxy' } |
    ForEach-Object {
        Write-Host "  killing proxy PID $($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue
    }
Get-NetTCPConnection -LocalPort 443,9009 -State Listen -EA SilentlyContinue |
    ForEach-Object {
        try {
            $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($_.OwningProcess)" -EA SilentlyContinue
            if ($proc.CommandLine -match 'record_proxy' -or $_.LocalPort -eq 443) {
                Write-Host "  killing listener PID $($_.OwningProcess) on port $($_.LocalPort)"
                Stop-Process -Id $_.OwningProcess -Force -EA SilentlyContinue
            }
        } catch {}
    }

# Strip WW3 RECORD hosts block
$lines = @()
try { $lines = [System.IO.File]::ReadAllLines($HostsFile) } catch { $lines = @() }
$out = New-Object System.Collections.Generic.List[string]
$skip = $false
foreach ($l in $lines) {
    if ($l.Trim() -eq $MarkA) { $skip = $true; continue }
    if ($l.Trim() -eq $MarkB) { $skip = $false; continue }
    if (-not $skip) { $out.Add($l) }
}
# Also strip any leftover WW3 pin / 127.0.0.1 redirects to our hosts
$filtered = foreach ($l in $out) {
    if ($l -match 'meta\.prod\.ww3\.fxtools\.gl|api\.storage\.fxtools\.gl|endpoint\.prod\.wishlist\.server\.fxgam\.es') { continue }
    $l
}
try { (Get-Item $HostsFile -Force).Attributes = 'Archive' } catch {}
$text = (($filtered -join "`r`n") + "`r`n")
[System.IO.File]::WriteAllText($HostsFile, $text, [System.Text.Encoding]::ASCII)
ipconfig /flushdns | Out-Null

Write-Host '[OK] Recorder stopped, WW3 hosts redirects removed, DNS flushed.' -ForegroundColor Green
Write-Host ''
Write-Host 'hosts file now:' -ForegroundColor Cyan
Get-Content $HostsFile
Write-Host ''
Write-Host 'NOTE: This menu recorder does NOT install an Epic/root CA.' -ForegroundColor Yellow
Write-Host 'If Epic/EOS games still fail from OLD offline-mock testing, open' -ForegroundColor Yellow
Write-Host 'certmgr.msc -> Trusted Root Certification Authorities -> Certificates' -ForegroundColor Yellow
Write-Host 'and delete any cert named like "WW3 Local Root CA", then reboot.' -ForegroundColor Yellow
Write-Host ''
Read-Host 'Press Enter to close'
