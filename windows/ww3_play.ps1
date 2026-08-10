<#
    ww3_play.ps1 - SAFE, self-cleaning WW3 offline session.

    Brings up the forever-offline stack, launches the game, waits for it to close,
    and GUARANTEES teardown (remove hosts redirects + CA, stop mocks) afterwards --
    even on Ctrl-C, an error, or the game crashing. The api.epicgames.dev redirect
    therefore can NEVER be left active after you stop playing, so other EOS games
    (Hunt, etc.) are safe.

        .\ww3_play.ps1                 # menu (eac) session, auto-cleans on exit
        .\ww3_play.ps1 -Launch host -GameMode WW3ReconGameMode -Bots 8   # match-host test

    Run from an ELEVATED PowerShell.
#>
param(
    [ValidateSet('eac','host')][string]$Launch='eac',
    [string]$Map='WW3_DMZ_P',
    [string]$GameMode='',
    [int]$Bots=0
)
$ErrorActionPreference='Stop'
$W='F:\Dev_Work\GameDev\WW3\windows'

function Invoke-Down {
    Write-Host "`n[*] tearing down: removing redirects + CA, stopping mocks..." -ForegroundColor Yellow
    & powershell -ExecutionPolicy Bypass -File "$W\ww3_mock.ps1" down
}

# Belt-and-suspenders: also tear down if this PowerShell is closing for ANY reason.
Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action { & powershell -ExecutionPolicy Bypass -File 'F:\Dev_Work\GameDev\WW3\windows\ww3_mock.ps1' down } | Out-Null

try {
    Write-Host "[*] bringing up forever-offline stack..." -ForegroundColor Cyan
    & powershell -ExecutionPolicy Bypass -File "$W\ww3_mock.ps1" forever

    Write-Host "[*] launching game ($Launch)..." -ForegroundColor Cyan
    if ($Launch -eq 'host') {
        & powershell -ExecutionPolicy Bypass -File "$W\launch_offline.ps1" host -Map $Map -GameMode $GameMode -Bots $Bots
    } else {
        & powershell -ExecutionPolicy Bypass -File "$W\launch_offline.ps1" eac
    }

    # wait for the game process to appear (EAC bootstrap can take ~30s)
    $p = $null
    for ($i=0; $i -lt 40 -and -not $p; $i++) { Start-Sleep 2; $p = Get-Process WW3-Win64-Shipping -EA SilentlyContinue }
    if ($p) {
        Write-Host "`n[OK] game running (pid $($p.Id)). SESSION ACTIVE." -ForegroundColor Green
        Write-Host "     >>> Close the game (or press Ctrl-C here) and everything auto-cleans. <<<" -ForegroundColor Green
        Wait-Process -Id $p.Id            # blocks until the game exits
        Write-Host "[*] game closed." -ForegroundColor Cyan
    } else {
        Write-Host "[!] game did not start within 80s -- tearing down anyway." -ForegroundColor Yellow
    }
}
finally {
    Invoke-Down
    Get-EventSubscriber -SourceIdentifier PowerShell.Exiting -EA SilentlyContinue | Unregister-Event -EA SilentlyContinue
    Write-Host "[OK] session ended, networking fully restored. Safe to play other games." -ForegroundColor Green
}
