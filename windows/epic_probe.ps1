<#
    epic_probe.ps1 - test whether Epic's EOS SDK will trust a cert from OUR CA
    (i.e. can we MITM the EOS Auth TokenGrant to make offline login work forever).

        .\epic_probe.ps1 up     # install our CA, redirect api.epicgames.dev, run the probe
        .\epic_probe.ps1 down   # stop probe, REMOVE our CA, restore hosts

    After 'up', launch the game (Steam or offline) and WATCH THE PROBE WINDOW:
      "[OK CERT ACCEPTED]"  -> EOS trusts our CA, MITM feasible, forever-offline on
      "[X handshake rejected]" -> EOS pins its cert; MITM route closed.

    NOTE: this frees port 443 by stopping the game mocks, so the game won't reach
    the menu during the probe -- we only need EOS's early call to api.epicgames.dev.
    ALWAYS run 'down' after -- it removes the trusted-root cert from your system.
#>
param([Parameter(Position=0)][ValidateSet('up','down')][string]$Action='up')
$ErrorActionPreference='Stop'
$MockDir='F:\Dev_Work\GameDev\WW3\mockserver'
$CA="$MockDir\epic_ca\rootCA.pem"
$HostsFile="$env:WINDIR\System32\drivers\etc\hosts"
$MarkA='# === WW3 EPIC PROBE redirects (auto) ==='
$MarkB='# === end WW3 EPIC PROBE redirects ==='
$EpicHosts=@('api.epicgames.dev')   # the EOS SDK API gateway
$CAName='WW3 Local Root CA'

function Assert-Admin { $p=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent()); if(-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Run from an ELEVATED PowerShell.'} }
function Find-Python { foreach($c in @("$env:LOCALAPPDATA\Programs\Python\Python312\python.exe")){if(Test-Path $c){return $c}}; (Get-Command python.exe|?{$_.Source -notlike '*WindowsApps*'}|Select -First 1).Source }
function Write-HostsLines([string[]]$lines){ try{(Get-Item $HostsFile -Force).Attributes='Archive'}catch{}; $t=($lines -join "`r`n")+"`r`n"; for($i=0;$i -lt 8;$i++){try{[System.IO.File]::WriteAllText($HostsFile,$t,[System.Text.Encoding]::ASCII);return $true}catch{Start-Sleep -Milliseconds 400}}; return $false }
function Hosts-Filtered { $o=New-Object System.Collections.Generic.List[string];$skip=$false; foreach($l in [System.IO.File]::ReadAllLines($HostsFile)){if($l.Trim()-eq $MarkA){$skip=$true;continue};if($l.Trim()-eq $MarkB){$skip=$false;continue};if(-not $skip){$o.Add($l)}}; return $o }

switch($Action){
 'up'{
    Assert-Admin
    Write-Host '[*] stopping game mocks to free port 443...' -ForegroundColor Cyan
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -EA SilentlyContinue | ?{$_.CommandLine -match 'rest_server\.py|hub_server\.py|xmpp_server\.py|epic_probe\.py'} | %{Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue}
    Start-Sleep 1
    Write-Host '[*] installing our CA as a trusted root...' -ForegroundColor Cyan
    certutil -addstore -f Root "$CA" | Out-Null
    Write-Host '[*] redirecting api.epicgames.dev -> 127.0.0.1...' -ForegroundColor Cyan
    $lines=@(Hosts-Filtered)+@($MarkA)+($EpicHosts|%{"127.0.0.1`t$_"})+@($MarkB)
    Write-HostsLines $lines | Out-Null; ipconfig /flushdns | Out-Null
    Write-Host '[*] starting probe on :443 (watch this window)...' -ForegroundColor Green
    Push-Location $MockDir
    try { & (Find-Python) 'epic_probe.py' 443 } finally {
        Pop-Location
        Write-Host "`n[*] probe ended. Run '.\epic_probe.ps1 down' to remove the CA + restore hosts + game mocks." -ForegroundColor Yellow
    }
 }
 'down'{
    Assert-Admin
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -EA SilentlyContinue | ?{$_.CommandLine -match 'epic_probe\.py'} | %{Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue}
    Write-Host '[*] removing our CA from trusted root...' -ForegroundColor Cyan
    certutil -delstore Root "$CAName" | Out-Null
    Write-HostsLines (Hosts-Filtered) | Out-Null; ipconfig /flushdns | Out-Null
    Write-Host '[OK] probe stopped, CA removed, hosts restored. (restart game mocks with ww3_mock.ps1 up)' -ForegroundColor Green
 }
}
