# WW3-Recorder-Stop.ps1 - double-click to stop the recorder, restore the hosts
# file, and copy the captured logs to the Desktop. Self-elevates.
$p = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell -Verb RunAs -ArgumentList @(
        '-NoExit','-ExecutionPolicy','Bypass','-File',"`"$PSScriptRoot\ww3_record.ps1`"",'down')
    return
}
& "$PSScriptRoot\ww3_record.ps1" down
