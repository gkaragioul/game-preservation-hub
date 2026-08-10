# WW3-Recorder-Start.ps1 - double-click launcher. Self-elevates, then runs the
# recorder live in a visible window and opens the dashboard.
$p = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell -Verb RunAs -ArgumentList @(
        '-NoExit','-ExecutionPolicy','Bypass','-File',"`"$PSScriptRoot\ww3_record.ps1`"",'live')
    return
}
& "$PSScriptRoot\ww3_record.ps1" live
