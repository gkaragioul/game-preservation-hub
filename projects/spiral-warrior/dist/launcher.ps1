[CmdletBinding()]
param(
    [ValidateSet('cn', 'en')][string]$Edition = 'cn',
    [switch]$Doctor,
    [switch]$Capture,
    [switch]$SkipInstall,
    [switch]$RestartGateway
)

$ErrorActionPreference = 'Stop'
$windowsRuntime = Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..')).Path `
    'tools\windows_runtime.ps1'
. $windowsRuntime
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root 'server\.venv_win\Scripts\python.exe'
$sdkRoot = Join-Path $env:LOCALAPPDATA 'SpiralWarrior\AndroidSdk'
$avdHome = Join-Path $env:LOCALAPPDATA 'SpiralWarrior\Avd'
$adb = Join-Path $sdkRoot 'platform-tools\adb.exe'
$emulator = Join-Path $sdkRoot 'emulator\emulator.exe'
$aapt2 = Join-Path $sdkRoot 'build-tools\30.0.3\aapt2.exe'
$zipalign = Join-Path $sdkRoot 'build-tools\30.0.3\zipalign.exe'
$apksigner = Join-Path $sdkRoot 'build-tools\30.0.3\apksigner.bat'
$androidPlatform = Join-Path $sdkRoot 'platforms\android-30\android.jar'
$avd = 'SpiralWarrior_API30_X64'
$imagePackage = 'system-images;android-30;google_apis;x86_64'
$serial = 'emulator-5556'
$gatewayPort = 23101
$edgePort = 8888
$gatewayHealth = '{"ok":true,"service":"spiralwarrior-local-server"}'
$edgeHealth = '{"ok":true,"service":"spiral-edge"}'
if ($Edition -eq 'cn') {
    $sourceApk = Join-Path $root 'cn_9game.apk'
    $apk = Join-Path $root 'patched\LuoXuanWarrior_cn_partsuit_userca_debug.apk'
    $package = 'com.dianhun.lxys.aligames'
    $expectedSourceApkSha256 = '4E02FBC9ADF4E31051140194B55B8004C1272C74D76293208D6B1809C77358D5'
    $expectedApkSha256 = '341795584ABCBD0997F1E396F56C3DE7E90FF889768866EAC4F04FE442415414'
} else {
    $sourceApk = $null
    $apk = Join-Path $root 'patched\SpiralWarrior_fullres_debug.apk'
    $package = 'com.oversea.spinarena'
    $expectedSourceApkSha256 = $null
    $expectedApkSha256 = '9C8769E51B535A7F909C935B38C2B2A4F27E4B44C711DBF8410011BF736888AD'
}
$caCertificate = Join-Path $root 'research\local_resource_server\certs\spiral-local-ca.pem'
$runtimeDir = Join-Path $root 'research\runtime'
$statePath = Join-Path $runtimeDir 'launcher-state.json'


function Write-Diagnostic {
    param([Parameter(Mandatory = $true)][string]$Message)
    [Console]::Error.WriteLine($Message)
}


function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @(),
        [string[]]$InputLines = @(),
        [Parameter(Mandatory = $true)][string]$Description
    )
    $captureRoot = Join-Path ([IO.Path]::GetTempPath()) (
        'SpiralWarrior-launcher-native-' + [Guid]::NewGuid().ToString('N')
    )
    [void](New-Item -ItemType Directory -Path $captureRoot)
    $stdoutPath = Join-Path $captureRoot 'stdout.txt'
    $stderrPath = Join-Path $captureRoot 'stderr.txt'
    try {
        $previousErrorAction = $ErrorActionPreference
        try {
            # Windows PowerShell 5.1 otherwise promotes a successful native
            # program's stderr to a terminating NativeCommandError.
            $ErrorActionPreference = 'Continue'
            if ($InputLines.Count -gt 0) {
                $InputLines | & $FilePath @Arguments 1> $stdoutPath 2> $stderrPath
            } else {
                & $FilePath @Arguments 1> $stdoutPath 2> $stderrPath
            }
            $exitCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $previousErrorAction
        }
        $stdout = if (Test-Path -LiteralPath $stdoutPath) {
            [IO.File]::ReadAllText($stdoutPath)
        } else { '' }
        $stderr = if (Test-Path -LiteralPath $stderrPath) {
            [IO.File]::ReadAllText($stderrPath)
        } else { '' }
        if ($exitCode -ne 0) {
            throw (
                "$Description failed with exit code $exitCode.`n" +
                "stdout:`n$stdout`nstderr:`n$stderr"
            )
        }
        return [pscustomobject]@{
            ExitCode = $exitCode
            StdOut = $stdout
            StdErr = $stderr
        }
    } finally {
        if (Test-Path -LiteralPath $captureRoot) {
            $resolvedCapture = (Resolve-Path -LiteralPath $captureRoot).Path
            $tempPrefix = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
            if (-not $resolvedCapture.StartsWith(
                $tempPrefix,
                [StringComparison]::OrdinalIgnoreCase
            )) {
                throw "refusing to clean unexpected capture path: $resolvedCapture"
            }
            Remove-Item -LiteralPath $resolvedCapture -Recurse -Force
        }
    }
}


function Normalize-ProcessCommandLine {
    param([AllowNull()][string]$CommandLine)
    if ($null -eq $CommandLine) { return '' }
    return ([regex]::Replace($CommandLine.Trim(), '\s+', ' '))
}


function Get-ProcessDetails {
    param([Parameter(Mandatory = $true)][int]$ProcessId)
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" `
        -ErrorAction SilentlyContinue
    if (-not $process) {
        return $null
    }
    $creationDate = if ($process.CreationDate -is [DateTime]) {
        $process.CreationDate.ToUniversalTime().ToString('o')
    } else {
        [string]$process.CreationDate
    }
    $creationFileTimeUtc = if ($process.CreationDate -is [DateTime]) {
        [string]$process.CreationDate.ToUniversalTime().ToFileTimeUtc()
    } else {
        ''
    }
    $resolvedExecutable = [string]$process.ExecutablePath
    if ($resolvedExecutable) {
        try {
            $resolvedExecutable = [IO.Path]::GetFullPath($resolvedExecutable)
        } catch {
            # Retain the live WMI value so a later comparison still fails closed.
        }
    }
    $commandLine = [string]$process.CommandLine
    return [pscustomobject]@{
        ProcessId = [int]$process.ProcessId
        ParentProcessId = [int]$process.ParentProcessId
        ExecutablePath = $resolvedExecutable
        CommandLine = $commandLine
        NormalizedCommandLine = Normalize-ProcessCommandLine $commandLine
        CreationDate = $creationDate
        CreationFileTimeUtc = $creationFileTimeUtc
    }
}


function New-ProcessOwnershipRecord {
    param([Parameter(Mandatory = $true)][int]$ProcessId)
    $deadline = [DateTime]::UtcNow.AddSeconds(5)
    $details = $null
    do {
        $details = Get-ProcessDetails -ProcessId $ProcessId
        if ($details) { break }
        Start-Sleep -Milliseconds 50
    } while ([DateTime]::UtcNow -lt $deadline)
    if (-not $details) {
        throw "cannot capture ownership for vanished PID $ProcessId"
    }
    return [pscustomobject]@{
        ProcessId = $details.ProcessId
        ExecutablePath = $details.ExecutablePath
        NormalizedCommandLine = $details.NormalizedCommandLine
        CreationDate = $details.CreationDate
        CreationFileTimeUtc = $details.CreationFileTimeUtc
    }
}


function Start-OwnedPersistentProcess {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @(),
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$StdoutPath,
        [Parameter(Mandatory = $true)][string]$StderrPath,
        [hashtable]$Hooks = @{}
    )
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        throw "restricted-handle process broker is missing: $python"
    }
    $application = Get-Command -Name $FilePath -CommandType Application `
        -ErrorAction Stop | Select-Object -First 1
    $resolvedFilePath = [IO.Path]::GetFullPath([string]$application.Source)
    $resolvedProcessFilePath = $resolvedFilePath
    $virtualEnvironmentLauncher = $null
    $resolvedLauncherPython = (Resolve-Path -LiteralPath $python).Path
    if ($resolvedFilePath -ieq $resolvedLauncherPython) {
        $baseProbe = Invoke-SpiralWindowsReadOnlyProbe `
            -FilePath $resolvedFilePath `
            -Arguments @(
                '-I',
                '-S',
                '-c',
                'import pathlib,sys;print(pathlib.Path(sys._base_executable).resolve())'
            )
        $baseCandidate = (
            $baseProbe.output -split "\r?\n" |
            Select-Object -Last 1
        ).Trim()
        if (($baseProbe.exitCode -ne 0) -or
            (-not [IO.Path]::IsPathRooted($baseCandidate)) -or
            (-not (Test-Path -LiteralPath $baseCandidate -PathType Leaf))) {
            throw 'could not resolve the venv base interpreter'
        }
        $resolvedProcessFilePath = (
            Resolve-Path -LiteralPath $baseCandidate
        ).Path
        if ($resolvedProcessFilePath -ine $resolvedFilePath) {
            $virtualEnvironmentLauncher = $resolvedFilePath
        }
    }
    $resolvedWorkingDirectory = (
        Resolve-Path -LiteralPath $WorkingDirectory -ErrorAction Stop
    ).Path
    $resolvedStdout = [IO.Path]::GetFullPath($StdoutPath)
    $resolvedStderr = [IO.Path]::GetFullPath($StderrPath)
    foreach ($logPath in @($resolvedStdout, $resolvedStderr)) {
        $logDirectory = Split-Path $logPath -Parent
        if (-not (Test-Path -LiteralPath $logDirectory -PathType Container)) {
            [void](New-Item -ItemType Directory -Path $logDirectory -Force)
        }
    }

    # Start-Process sets bInheritHandles when its standard streams are
    # redirected. On Windows that also leaks unrelated inheritable handles,
    # including an automation caller's stdout/stderr pipes, into a retained
    # child. Python's close_fds implementation uses an explicit handle list,
    # so the child receives only its dedicated log handles and a null stdin.
    $brokerSource = @'
import json
import os
from pathlib import Path
import subprocess
import sys
import ctypes
from ctypes import wintypes

spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
child_environment = os.environ.copy()
child_environment.pop("__PYVENV_LAUNCHER__", None)
if spec["virtualEnvironmentLauncher"]:
    child_environment["__PYVENV_LAUNCHER__"] = spec["virtualEnvironmentLauncher"]
child = None
try:
    with open(spec["stdout"], "ab", buffering=0) as stdout_handle:
        with open(spec["stderr"], "ab", buffering=0) as stderr_handle:
            child = subprocess.Popen(
                [spec["processFilePath"], *spec["arguments"]],
                cwd=spec["workingDirectory"],
                env=child_environment,
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=stderr_handle,
                close_fds=True,
                creationflags=flags,
            )
    if spec["faultPoint"] == "AfterPopen":
        raise RuntimeError("injected broker fault after Popen")
    creation = wintypes.FILETIME()
    exit_time = wintypes.FILETIME()
    kernel_time = wintypes.FILETIME()
    user_time = wintypes.FILETIME()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    ]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    process_handle = wintypes.HANDLE(int(child._handle))
    if not kernel32.GetProcessTimes(
        process_handle,
        ctypes.byref(creation),
        ctypes.byref(exit_time),
        ctypes.byref(kernel_time),
        ctypes.byref(user_time),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    image = ctypes.create_unicode_buffer(32768)
    image_size = wintypes.DWORD(len(image))
    if not kernel32.QueryFullProcessImageNameW(
        process_handle, 0, image, ctypes.byref(image_size)
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    creation_filetime = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
    # Win32_Process.CreationDate is exposed by CIM at microsecond precision.
    creation_filetime -= creation_filetime % 10
    identity = {
        "pid": child.pid,
        "creationFileTimeUtc": str(creation_filetime),
        "executablePath": image.value,
    }
    if spec["faultPoint"] == "AfterIdentityCapture":
        raise RuntimeError("injected broker fault after identity capture")
    encoded_identity = json.dumps(identity, separators=(",", ":"))
    Path(spec["resultPath"]).write_text(encoded_identity, encoding="utf-8")
    sys.stdout.write(encoded_identity)
except BaseException:
    if child is not None:
        try:
            if child.poll() is None:
                child.kill()
        finally:
            child.wait()
    raise
'@
    $brokerRoot = Join-Path ([IO.Path]::GetTempPath()) (
        'SpiralWarrior-launcher-broker-' + [Guid]::NewGuid().ToString('N')
    )
    $brokerPath = Join-Path $brokerRoot 'spawn.py'
    $specPath = Join-Path $brokerRoot 'spec.json'
    $resultPath = Join-Path $brokerRoot 'result.json'
    $brokerFaultPoint = if ($Hooks.ContainsKey('BrokerFaultPoint')) {
        [string]$Hooks['BrokerFaultPoint']
    } else {
        ''
    }
    if ($brokerFaultPoint -notin @(
        '',
        'AfterPopen',
        'AfterIdentityCapture'
    )) {
        throw "unknown broker fault point '$brokerFaultPoint'"
    }
    $getProcess = if ($Hooks.ContainsKey('GetProcess')) {
        $Hooks['GetProcess']
    } else {
        $null
    }
    $spawnedPid = 0
    $brokerIdentity = $null
    $ownership = $null
    $ownershipAuthenticated = $false
    try {
        [void](New-Item -ItemType Directory -Path $brokerRoot)
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [IO.File]::WriteAllText($brokerPath, $brokerSource, $utf8NoBom)
        $spec = [ordered]@{
            filePath = $resolvedFilePath
            processFilePath = $resolvedProcessFilePath
            virtualEnvironmentLauncher = $virtualEnvironmentLauncher
            resultPath = $resultPath
            faultPoint = $brokerFaultPoint
            arguments = @($Arguments)
            workingDirectory = $resolvedWorkingDirectory
            stdout = $resolvedStdout
            stderr = $resolvedStderr
        }
        [IO.File]::WriteAllText(
            $specPath,
            ($spec | ConvertTo-Json -Depth 4 -Compress),
            $utf8NoBom
        )
        $brokerResult = Invoke-NativeChecked `
            -FilePath $python `
            -Arguments @($brokerPath, $specPath) `
            -Description "restricted-handle process start ($resolvedFilePath)"
        if (-not (Test-Path -LiteralPath $resultPath -PathType Leaf)) {
            throw 'restricted-handle process broker returned no identity sidecar'
        }
        try {
            $sidecarJson = [IO.File]::ReadAllText($resultPath) |
                ConvertFrom-Json
            $brokerIdentity = [pscustomobject]@{
                ProcessId = [int]$sidecarJson.pid
                CreationFileTimeUtc =
                    [string]$sidecarJson.creationFileTimeUtc
                ExecutablePath = [IO.Path]::GetFullPath(
                    [string]$sidecarJson.executablePath
                )
            }
            $spawnedPid = [int]$brokerIdentity.ProcessId
        } catch {
            throw 'restricted-handle process broker identity sidecar is invalid'
        }
        if ($Hooks.ContainsKey('BeforeBrokerResultParse')) {
            & $Hooks['BeforeBrokerResultParse']
        }
        if (($brokerResult.StdOut -split "\r?\n" |
            Where-Object { $_.Length -gt 0 }).Count -ne 1) {
            throw "restricted-handle process broker returned invalid output"
        }
        try {
            $brokerJson = $brokerResult.StdOut.Trim() | ConvertFrom-Json
            $parsedBrokerPid = [int]$brokerJson.pid
            $spawnedCreationFileTimeUtc = [string]$brokerJson.creationFileTimeUtc
            $spawnedExecutablePath = [IO.Path]::GetFullPath(
                [string]$brokerJson.executablePath
            )
        } catch {
            throw (
                "restricted-handle process broker returned invalid JSON: " +
                $brokerResult.StdOut
            )
        }
        if (($parsedBrokerPid -ne [int]$brokerIdentity.ProcessId) -or
            ($spawnedCreationFileTimeUtc -cne
                [string]$brokerIdentity.CreationFileTimeUtc) -or
            ($spawnedExecutablePath -ine
                [string]$brokerIdentity.ExecutablePath)) {
            throw 'restricted-handle process broker identity outputs disagree'
        }
        if ($spawnedPid -le 0) {
            throw "restricted-handle process broker returned invalid PID $spawnedPid"
        }
        $parsedCreationFileTime = 0L
        if ((-not [long]::TryParse(
            $spawnedCreationFileTimeUtc,
            [ref]$parsedCreationFileTime
        )) -or $parsedCreationFileTime -le 0) {
            throw (
                "restricted-handle process broker returned invalid creation " +
                "identity '$spawnedCreationFileTimeUtc'"
            )
        }
        if ($spawnedExecutablePath -ine $resolvedProcessFilePath) {
            throw (
                "restricted-handle process broker reported unexpected executable: " +
                "'$spawnedExecutablePath', expected '$resolvedProcessFilePath'"
            )
        }
        $ownership = if ($getProcess) {
            & $getProcess $spawnedPid
        } else {
            New-ProcessOwnershipRecord -ProcessId $spawnedPid
        }
        if (-not $ownership) {
            throw "cannot capture ownership for vanished PID $spawnedPid"
        }
        if (($ownership.ProcessId -ne $spawnedPid) -or
            ($ownership.ExecutablePath -ine $spawnedExecutablePath) -or
            ([string]$ownership.CreationFileTimeUtc -cne
                $spawnedCreationFileTimeUtc)) {
            throw (
                "restricted-handle process identity mismatch: " +
                "brokerPid=$spawnedPid livePid=$($ownership.ProcessId) " +
                "brokerExe='$spawnedExecutablePath' " +
                "liveExe='$($ownership.ExecutablePath)' " +
                "brokerCreated='$spawnedCreationFileTimeUtc' " +
                "liveCreated='$($ownership.CreationFileTimeUtc)'"
            )
        }
        $ownershipAuthenticated = $true
        return [pscustomobject]@{
            ProcessId = $spawnedPid
            OwnershipRecord = $ownership
            Records = @($ownership)
            StdoutPath = $resolvedStdout
            StderrPath = $resolvedStderr
        }
    } catch {
        $originalError = $_
        if ($ownershipAuthenticated -and $ownership) {
            Stop-OwnedProcesses -Records @($ownership)
        } elseif ($brokerIdentity -and
            [int]$brokerIdentity.ProcessId -gt 0) {
            try {
                $cleanupLive = if ($getProcess) {
                    & $getProcess ([int]$brokerIdentity.ProcessId)
                } else {
                    Get-ProcessDetails `
                        -ProcessId ([int]$brokerIdentity.ProcessId)
                }
                if ($cleanupLive -and
                    ([int]$cleanupLive.ProcessId -eq
                        [int]$brokerIdentity.ProcessId) -and
                    ([string]$cleanupLive.ExecutablePath -ieq
                        [string]$brokerIdentity.ExecutablePath) -and
                    ([string]$cleanupLive.CreationFileTimeUtc -cne '') -and
                    ([string]$cleanupLive.CreationFileTimeUtc -ceq
                        [string]$brokerIdentity.CreationFileTimeUtc)) {
                    Stop-OwnedProcesses -Records @($cleanupLive)
                } else {
                    Write-Diagnostic (
                        "broker PID $($brokerIdentity.ProcessId) cleanup was " +
                        'skipped because its CIM identity did not authenticate'
                    )
                }
            } catch {
                Write-Diagnostic (
                    "broker PID $($brokerIdentity.ProcessId) cleanup failed: " +
                    $_.Exception.Message
                )
            }
        }
        throw $originalError
    } finally {
        if (Test-Path -LiteralPath $brokerRoot) {
            $resolvedBrokerRoot = (Resolve-Path -LiteralPath $brokerRoot).Path
            $tempPrefix = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
            if (-not $resolvedBrokerRoot.StartsWith(
                $tempPrefix,
                [StringComparison]::OrdinalIgnoreCase
            )) {
                throw "refusing to clean unexpected broker path: $resolvedBrokerRoot"
            }
            Remove-Item -LiteralPath $resolvedBrokerRoot -Recurse -Force
        }
    }
}


function Test-ProcessOwnershipRecord {
    param(
        [Parameter(Mandatory = $true)]$Record,
        [Parameter(Mandatory = $true)]$Live
    )
    $matches = (
        ([int]$Record.ProcessId -eq [int]$Live.ProcessId) -and
        ([string]$Record.ExecutablePath -ieq [string]$Live.ExecutablePath) -and
        ([string]$Record.NormalizedCommandLine -ceq
            [string]$Live.NormalizedCommandLine) -and
        ([string]$Record.CreationDate -ceq [string]$Live.CreationDate)
    )
    if (-not $matches) {
        return $false
    }
    $recordHasFileTime = @(
        $Record.PSObject.Properties.Name |
        Where-Object { $_ -ieq 'CreationFileTimeUtc' }
    ).Count -gt 0
    if ($recordHasFileTime) {
        $recordedFileTime = 0L
        if ((-not [long]::TryParse(
            [string]$Record.CreationFileTimeUtc,
            [ref]$recordedFileTime
        )) -or $recordedFileTime -le 0) {
            return $false
        }
        return (
            [string]$Record.CreationFileTimeUtc -ceq
            [string]$Live.CreationFileTimeUtc
        )
    }
    return $true
}


function Stop-OwnedProcesses {
    param([object[]]$Records)
    $orderedRecords = @($Records)
    [array]::Reverse($orderedRecords)
    foreach ($record in $orderedRecords) {
        if (-not $record -or [int]$record.ProcessId -le 0) { continue }
        $isServiceRecord = @(
            $record.PSObject.Properties.Name |
            Where-Object { $_ -ieq 'Role' }
        ).Count -gt 0
        $hasCreationFileTime = @(
            $record.PSObject.Properties.Name |
            Where-Object { $_ -ieq 'CreationFileTimeUtc' }
        ).Count -gt 0
        $parsedCreationFileTime = 0L
        if ($isServiceRecord -and
            ((-not $hasCreationFileTime) -or
            (-not [long]::TryParse(
                [string]$record.CreationFileTimeUtc,
                [ref]$parsedCreationFileTime
            )) -or
            $parsedCreationFileTime -le 0)) {
            Write-Diagnostic (
                "cleanup skipped service PID $($record.ProcessId): " +
                'creationFileTimeUtc is required'
            )
            continue
        }
        $live = Get-ProcessDetails -ProcessId ([int]$record.ProcessId)
        if (-not $live) { continue }
        if (-not (Test-ProcessOwnershipRecord -Record $record -Live $live)) {
            Write-Diagnostic (
                "cleanup skipped recycled/mismatched PID $($record.ProcessId): " +
                "recordedExe='$($record.ExecutablePath)' " +
                "liveExe='$($live.ExecutablePath)' " +
                "recordedCreated='$($record.CreationDate)' " +
                "liveCreated='$($live.CreationDate)'"
            )
            continue
        }
        Stop-Process -Id ([int]$record.ProcessId) -Force -ErrorAction SilentlyContinue
        try {
            Wait-Process -Id ([int]$record.ProcessId) -Timeout 15 `
                -ErrorAction SilentlyContinue
        } catch {
            Write-Diagnostic "owned PID $($record.ProcessId) did not exit promptly"
        }
    }
}


function Get-TcpListenerOwner {
    param([Parameter(Mandatory = $true)][int]$Port)
    $connections = @(Get-NetTCPConnection -State Listen -LocalPort $Port `
        -ErrorAction SilentlyContinue)
    if ($connections.Count -eq 0) {
        return $null
    }
    $owners = @($connections | Select-Object -ExpandProperty OwningProcess -Unique)
    if ($owners.Count -ne 1) {
        throw "port $Port has multiple listener owners: $($owners -join ', ')"
    }
    $details = Get-ProcessDetails -ProcessId ([int]$owners[0])
    if (-not $details) {
        throw "port $Port is occupied by vanished PID $($owners[0])"
    }
    return $details
}


function Format-Owner {
    param($Owner)
    if (-not $Owner) { return 'no owner' }
    return (
        "PID $($Owner.ProcessId), executable '$($Owner.ExecutablePath)', " +
        "command '$($Owner.CommandLine)'"
    )
}


function Assert-ServicePortContract {
    param(
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ExpectedBody
    )
    $owner = Get-TcpListenerOwner -Port $Port
    if (-not $owner) {
        return $null
    }
    try {
        $response = Invoke-WebRequest -UseBasicParsing `
            -Uri "http://127.0.0.1:$Port$Path" `
            -TimeoutSec 3
        $responseBody = if ($response.Content -is [byte[]]) {
            [Text.Encoding]::UTF8.GetString($response.Content)
        } else {
            [string]$response.Content
        }
        if (($response.StatusCode -ne 200) -or
            ($responseBody -cne $ExpectedBody)) {
            throw (
                "unexpected health response status=$($response.StatusCode) " +
                "body='$responseBody'"
            )
        }
    } catch {
        throw (
            "port $Port is owned by $(Format-Owner $owner) but does not match " +
            "the expected service: $($_.Exception.Message)"
        )
    }
    return $owner
}


function Assert-PortsUnowned {
    param(
        [Parameter(Mandatory = $true)][int[]]$Ports,
        [Parameter(Mandatory = $true)][string]$Purpose
    )
    foreach ($port in $Ports) {
        $owner = Get-TcpListenerOwner -Port $port
        if ($owner) {
            throw (
                "$Purpose cannot use port $port because it is owned by " +
                "$(Format-Owner $owner)"
            )
        }
    }
}


function Wait-ServiceHealth {
    param(
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ExpectedBody,
        [Parameter(Mandatory = $true)][string]$StdoutLog,
        [Parameter(Mandatory = $true)][string]$StderrLog,
        [ValidateRange(1, 300)][int]$TimeoutSeconds = 30
    )
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $lastMismatchedOwner = $null
    $lastContractError = ''
    while ([DateTime]::UtcNow -lt $deadline) {
        $owner = Get-TcpListenerOwner -Port $Port
        if ($owner) {
            try {
                return Assert-ServicePortContract `
                    -Port $Port -Path $Path -ExpectedBody $ExpectedBody
            } catch {
                $lastMismatchedOwner = $owner
                $lastContractError = $_.Exception.Message
                Start-Sleep -Milliseconds 250
                continue
            }
        }
        Start-Sleep -Milliseconds 250
    }
    $ownerDetails = if ($lastMismatchedOwner) {
        " lastOwner=$(Format-Owner $lastMismatchedOwner) " +
        "contractError='$lastContractError'"
    } else {
        ''
    }
    throw (
        "service on port $Port did not become ready; " +
        "stdout=$StdoutLog stderr=$StderrLog$ownerDetails"
    )
}


function Test-Java17 {
    $candidates = @()
    if ($env:JAVA_HOME) {
        $candidates += Join-Path $env:JAVA_HOME 'bin\java.exe'
    }
    $pathJava = Get-Command java.exe -ErrorAction SilentlyContinue
    if ($pathJava) { $candidates += $pathJava.Source }
    $adoptiumRoot = Join-Path $env:ProgramFiles 'Eclipse Adoptium'
    if (Test-Path -LiteralPath $adoptiumRoot) {
        $candidates += Get-ChildItem $adoptiumRoot -Directory -Filter 'jdk-17*' |
            Sort-Object Name -Descending |
            ForEach-Object { Join-Path $_.FullName 'bin\java.exe' }
    }
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate)) { continue }
        try {
            $version = Invoke-NativeChecked -FilePath $candidate `
                -Arguments @('-version') -Description "Java version ($candidate)"
            $text = $version.StdOut + "`n" + $version.StdErr
            $match = [regex]::Match(
                $text,
                'version\s+"(?:1\.)?(?<major>\d+)'
            )
            if ($match.Success -and
                ([int]$match.Groups['major'].Value -eq 17)) {
                return $true
            }
        } catch {
            continue
        }
    }
    return $false
}


function Test-AndroidToolchain {
    foreach ($requiredPath in @(
        $adb,
        $emulator,
        $aapt2,
        $zipalign,
        $apksigner,
        $androidPlatform
    )) {
        if (-not (Test-Path -LiteralPath $requiredPath)) {
            return $false
        }
    }
    $properties = Join-Path $sdkRoot 'build-tools\30.0.3\source.properties'
    if (-not (Test-Path -LiteralPath $properties)) {
        return $false
    }
    return [bool](
        Get-Content -LiteralPath $properties |
        Where-Object { $_.Trim() -eq 'Pkg.Revision=30.0.3' } |
        Select-Object -First 1
    )
}


function Test-AvdContract {
    if (-not (Test-Path -LiteralPath $emulator)) { return $false }
    $config = Join-Path $avdHome "$avd.avd\config.ini"
    if (-not (Test-Path -LiteralPath $config)) { return $false }
    try {
        $listed = Invoke-NativeChecked -FilePath $emulator `
            -Arguments @('-list-avds') -Description 'AVD listing'
    } catch {
        return $false
    }
    if (@($listed.StdOut -split "\r?\n") -notcontains $avd) { return $false }
    return Test-AvdConfigImage `
        -ConfigPath $config -ExpectedImage $imagePackage
}


function Test-AvdConfigImage {
    param(
        [Parameter(Mandatory = $true)][string]$ConfigPath,
        [Parameter(Mandatory = $true)][string]$ExpectedImage
    )
    if (-not (Test-Path -LiteralPath $ConfigPath)) { return $false }
    $line = Get-Content -LiteralPath $ConfigPath |
        Where-Object { $_ -match '^image\.sysdir\.1\s*=' } |
        Select-Object -First 1
    if (-not $line) { return $false }
    $actual = (($line -split '=', 2)[1] -replace '\\', '/').TrimEnd('/')
    $actual = $actual.Trim()
    $expected = ($ExpectedImage -replace ';', '/').TrimEnd('/')
    return $actual -eq $expected
}


function Invoke-Adb {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Description
    )
    return Invoke-NativeChecked -FilePath $adb `
        -Arguments (@('-s', $serial) + $Arguments) `
        -Description $Description
}


function Get-AdbDeviceEntries {
    $devices = Invoke-NativeChecked -FilePath $adb `
        -Arguments @('devices') -Description 'ADB device listing'
    $entries = @()
    foreach ($line in ($devices.StdOut -split "\r?\n")) {
        if ($line -match '^(\S+)\s+(\S+)$' -and
            $matches[1] -ne 'List') {
            $entries += [pscustomobject]@{
                Serial = $matches[1]
                State = $matches[2]
            }
        }
    }
    return @($entries)
}


function Get-AdbSerialState {
    foreach ($entry in @(Get-AdbDeviceEntries)) {
        if ($entry.Serial -eq $serial) {
            return $entry.State
        }
    }
    return $null
}


function Wait-AdbBoot {
    param(
        [Parameter(Mandatory = $true)][int]$TimeoutSeconds,
        [int]$ServerRestartAfterSeconds = 60,
        [Parameter(Mandatory = $true)][int]$EmulatorPid,
        [Parameter(Mandatory = $true)][string]$EmulatorStdout,
        [Parameter(Mandatory = $true)][string]$EmulatorStderr
    )
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $lastReconnect = [DateTime]::MinValue
    $lastState = 'absent'
    $lastReconnectError = ''
    $waitStarted = [DateTime]::UtcNow
    $serverRestarted = $false
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            $deviceEntries = @(Get-AdbDeviceEntries)
            $serialEntry = @(
                $deviceEntries | Where-Object { $_.Serial -eq $serial }
            ) | Select-Object -First 1
            $lastState = if ($serialEntry) { $serialEntry.State } else { $null }
            if ($lastState -eq 'device') {
                $boot = Invoke-Adb -Arguments @(
                    'shell', 'getprop', 'sys.boot_completed'
                ) -Description 'Android boot-complete check'
                if ($boot.StdOut.Trim() -eq '1') {
                    return
                }
            } elseif (($lastState -eq 'offline') -and
                (([DateTime]::UtcNow - $lastReconnect).TotalSeconds -ge 5)) {
                $lastReconnect = [DateTime]::UtcNow
                try {
                    $reconnect = Invoke-Adb -Arguments @('reconnect') `
                        -Description "exact serial reconnect ($serial)"
                    $lastReconnectError = ''
                } catch {
                    $lastReconnectError = $_.Exception.Message
                }
            } elseif ((-not $lastState) -and
                (-not $serverRestarted) -and
                (([DateTime]::UtcNow - $waitStarted).TotalSeconds -ge
                    $ServerRestartAfterSeconds)) {
                if ($deviceEntries.Count -eq 0) {
                    $serverRestarted = $true
                    try {
                        $killServer = Invoke-NativeChecked -FilePath $adb `
                            -Arguments @('kill-server') `
                            -Description 'guarded empty-list ADB server stop'
                        $startServer = Invoke-NativeChecked -FilePath $adb `
                            -Arguments @('start-server') `
                            -Description 'guarded empty-list ADB server start'
                        $lastReconnectError = ''
                    } catch {
                        $lastReconnectError = $_.Exception.Message
                    }
                } else {
                    $lastReconnectError = (
                        "global ADB restart suppressed because other devices exist: " +
                        (($deviceEntries | ForEach-Object {
                            "$($_.Serial):$($_.State)"
                        }) -join ',')
                    )
                }
            }
        } catch {
            # ADB disconnects are expected while root/reboot is in progress.
        }
        Start-Sleep -Seconds 1
    }
    throw (
        "$serial did not boot within $TimeoutSeconds seconds; " +
        "lastState=$lastState reconnectError='$lastReconnectError' " +
        "emulatorPid=$EmulatorPid stdout=$EmulatorStdout stderr=$EmulatorStderr"
    )
}


function Enable-AdbRoot {
    param(
        [Parameter(Mandatory = $true)][int]$EmulatorPid,
        [Parameter(Mandatory = $true)][string]$EmulatorStdout,
        [Parameter(Mandatory = $true)][string]$EmulatorStderr
    )
    $transportClosed = $false
    try {
        $rootResult = Invoke-Adb -Arguments @('root') `
            -Description 'ADB root enablement'
    } catch {
        if ($_.Exception.Message -notmatch
            'unable to connect for root:\s*closed') {
            throw
        }
        $transportClosed = $true
    }
    if ($transportClosed) {
        Wait-AdbBoot -TimeoutSeconds 180 -EmulatorPid $EmulatorPid `
            -EmulatorStdout $EmulatorStdout -EmulatorStderr $EmulatorStderr
        $rootResult = Invoke-Adb -Arguments @('root') `
            -Description 'ADB root retry after closed transport'
    }
    Wait-AdbBoot -TimeoutSeconds 180 -EmulatorPid $EmulatorPid `
        -EmulatorStdout $EmulatorStdout -EmulatorStderr $EmulatorStderr
    $userResult = Invoke-Adb -Arguments @('shell', 'id', '-u') `
        -Description 'ADB root identity'
    if ($userResult.StdOut.Trim() -ne '0') {
        throw "adb root did not produce uid 0: $($userResult.StdOut)"
    }
}


function Assert-EmulatorOwner {
    param([Parameter(Mandatory = $true)]$Owner)
    $executableName = [IO.Path]::GetFileName($Owner.ExecutablePath)
    if (($executableName -notmatch '^(emulator|qemu-system-.+)\.exe$') -or
        ($Owner.CommandLine -notmatch [regex]::Escape($avd))) {
        throw (
            "$serial console port is not owned by the expected AVD: " +
            "$(Format-Owner $Owner)"
        )
    }
}


function Add-ValidatedEmulatorOwnerForCleanup {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [System.Collections.Generic.List[object]]$StartedPids,
        [Parameter(Mandatory = $true)]$Owner
    )
    $ownerPid = [int]$Owner.ProcessId
    if ($ownerPid -le 0) {
        throw "validated emulator owner has an invalid PID: $ownerPid"
    }
    Assert-EmulatorOwner -Owner $Owner
    $normalizedOwnerCommand = [string]$Owner.NormalizedCommandLine
    if (-not $normalizedOwnerCommand) {
        $normalizedOwnerCommand = Normalize-ProcessCommandLine `
            ([string]$Owner.CommandLine)
    }
    if ((-not $Owner.ExecutablePath) -or
        (-not $normalizedOwnerCommand) -or
        (-not $Owner.CreationDate)) {
        throw (
            "validated emulator listener owner is missing ownership identity: " +
            "$(Format-Owner $Owner)"
        )
    }
    $listenerRecord = [pscustomobject]@{
        ProcessId = $ownerPid
        ExecutablePath = [IO.Path]::GetFullPath([string]$Owner.ExecutablePath)
        NormalizedCommandLine = $normalizedOwnerCommand
        CreationDate = [string]$Owner.CreationDate
        CreationFileTimeUtc = [string]$Owner.CreationFileTimeUtc
    }
    $live = Get-ProcessDetails -ProcessId $ownerPid
    if ((-not $live) -or
        (-not (Test-ProcessOwnershipRecord -Record $listenerRecord -Live $live))) {
        throw (
            "emulator listener ownership identity changed before cleanup " +
            "registration; listenerPid=$ownerPid " +
            "listenerCreated='$($listenerRecord.CreationDate)' " +
            "liveCreated='$($live.CreationDate)'"
        )
    }
    $alreadyRecorded = @(
        $StartedPids | Where-Object { [int]$_.ProcessId -eq $ownerPid }
    ).Count -gt 0
    if (-not $alreadyRecorded) {
        [void]$StartedPids.Add($listenerRecord)
    }
}


function Wait-EmulatorOwner {
    param(
        [Parameter(Mandatory = $true)][string]$EmulatorStdout,
        [Parameter(Mandatory = $true)][string]$EmulatorStderr
    )
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    while ([DateTime]::UtcNow -lt $deadline) {
        $owner = Get-TcpListenerOwner -Port 5556
        if ($owner) {
            Assert-EmulatorOwner -Owner $owner
            return $owner
        }
        Start-Sleep -Milliseconds 250
    }
    throw (
        "new emulator did not claim console port 5556 within 30 seconds; " +
        "stdout=$EmulatorStdout stderr=$EmulatorStderr"
    )
}


function Wait-NewEmulatorBoot {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [System.Collections.Generic.List[object]]$StartedPids,
        [Parameter(Mandatory = $true)][int]$TimeoutSeconds,
        [Parameter(Mandatory = $true)][string]$EmulatorStdout,
        [Parameter(Mandatory = $true)][string]$EmulatorStderr
    )
    $owner = Wait-EmulatorOwner `
        -EmulatorStdout $EmulatorStdout -EmulatorStderr $EmulatorStderr
    Assert-EmulatorOwner -Owner $owner
    Add-ValidatedEmulatorOwnerForCleanup `
        -StartedPids $StartedPids -Owner $owner
    Wait-AdbBoot -TimeoutSeconds $TimeoutSeconds `
        -EmulatorPid $owner.ProcessId `
        -EmulatorStdout $EmulatorStdout -EmulatorStderr $EmulatorStderr
    return $owner
}


function Assert-PathWithin {
    param(
        [Parameter(Mandatory = $true)][string]$Candidate,
        [Parameter(Mandatory = $true)][string]$Parent
    )
    $candidatePath = [IO.Path]::GetFullPath($Candidate)
    $parentPath = [IO.Path]::GetFullPath($Parent).TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    ) + [IO.Path]::DirectorySeparatorChar
    if (-not $candidatePath.StartsWith(
        $parentPath,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "path '$candidatePath' escapes guarded parent '$parentPath'"
    }
}


function Get-LockRecordedPids {
    param([Parameter(Mandatory = $true)][string]$LockPath)
    $pidFiles = @()
    if (-not (Test-Path -LiteralPath $LockPath)) { return @() }
    $item = Get-Item -LiteralPath $LockPath -Force
    if ($item.PSIsContainer) {
        $pidFiles = @(Get-ChildItem -LiteralPath $LockPath -Force -File |
            Where-Object { $_.Name -match '(?i)pid' })
    } else {
        $pidFiles = @($item)
    }
    $recorded = @()
    foreach ($pidFile in $pidFiles) {
        $text = Get-Content -Raw -LiteralPath $pidFile.FullName `
            -ErrorAction SilentlyContinue
        foreach ($match in [regex]::Matches([string]$text, '\b\d+\b')) {
            $recorded += [int]$match.Value
        }
    }
    return @($recorded | Select-Object -Unique)
}


function Assert-EmulatorRecoverySafe {
    $entries = @(Get-AdbDeviceEntries)
    if ($entries.Count -ne 0) {
        throw (
            'emulator recovery suppressed because ADB devices exist: ' +
            (($entries | ForEach-Object {
                "$($_.Serial):$($_.State)"
            }) -join ',')
        )
    }
    Assert-PortsUnowned -Ports @(5556, 5557) -Purpose 'emulator recovery'
    $liveAvdProcesses = @(
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            ($_.Name -match '^(?:emulator|qemu-system-.+)\.exe$') -and
            ([string]$_.CommandLine -match [regex]::Escape($avd))
        }
    )
    if ($liveAvdProcesses.Count -gt 0) {
        throw (
            'emulator recovery suppressed because exact-AVD processes remain: ' +
            (($liveAvdProcesses | ForEach-Object {
                "PID $($_.ProcessId) '$($_.CommandLine)'"
            }) -join '; ')
        )
    }
    $avdDirectory = Join-Path $avdHome "$avd.avd"
    foreach ($lockName in @('hardware-qemu.ini.lock', 'multiinstance.lock')) {
        $lockPath = Join-Path $avdDirectory $lockName
        Assert-PathWithin -Candidate $lockPath -Parent $avdHome
        foreach ($recordedPid in @(Get-LockRecordedPids -LockPath $lockPath)) {
            if (Get-ProcessDetails -ProcessId $recordedPid) {
                throw (
                    "emulator recovery suppressed because $lockPath records " +
                    "live PID $recordedPid"
                )
            }
        }
    }
}


function Wait-EmulatorRecoverySafe {
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    $lastError = ''
    do {
        try {
            Assert-EmulatorRecoverySafe
            return
        } catch {
            $lastError = $_.Exception.Message
        }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "emulator recovery preconditions were not met: $lastError"
}


function Test-DirtyDefaultBootSnapshot {
    param([Parameter(Mandatory = $true)][string]$SnapshotPath)
    if (-not (Test-Path -LiteralPath $SnapshotPath -PathType Container)) {
        return $false
    }
    $ram = Join-Path $SnapshotPath 'ram.img'
    $metadata = Join-Path $SnapshotPath 'snapshot.pb'
    return (
        (Test-Path -LiteralPath $ram -PathType Leaf) -and
        (-not (Test-Path -LiteralPath $metadata -PathType Leaf))
    )
}


function Move-StaleAvdStateToQuarantine {
    $avdDirectory = Join-Path $avdHome "$avd.avd"
    Assert-PathWithin -Candidate $avdDirectory -Parent $avdHome
    $stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')
    $quarantineRoot = Join-Path $avdHome 'quarantine'
    Assert-PathWithin -Candidate $quarantineRoot -Parent $avdHome
    $quarantine = Join-Path $quarantineRoot "$stamp-boot-timeout"
    [void](New-Item -ItemType Directory -Path $quarantine -Force)
    foreach ($lockName in @('hardware-qemu.ini.lock', 'multiinstance.lock')) {
        $source = Join-Path $avdDirectory $lockName
        if (Test-Path -LiteralPath $source) {
            Assert-PathWithin -Candidate $source -Parent $avdDirectory
            Move-Item -LiteralPath $source -Destination (
                Join-Path $quarantine $lockName
            )
        }
    }
    $snapshot = Join-Path $avdDirectory 'snapshots\default_boot'
    if (Test-DirtyDefaultBootSnapshot -SnapshotPath $snapshot) {
        Assert-PathWithin -Candidate $snapshot -Parent $avdDirectory
        Move-Item -LiteralPath $snapshot -Destination (
            Join-Path $quarantine 'default_boot'
        )
    }
    return $quarantine
}


function Move-ExactAvdToQuarantine {
    $avdDirectory = Join-Path $avdHome "$avd.avd"
    $avdIni = Join-Path $avdHome "$avd.ini"
    Assert-PathWithin -Candidate $avdDirectory -Parent $avdHome
    Assert-PathWithin -Candidate $avdIni -Parent $avdHome
    $stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')
    $quarantineRoot = Join-Path $avdHome 'quarantine'
    $quarantine = Join-Path $quarantineRoot "$stamp-avd-recreate"
    [void](New-Item -ItemType Directory -Path $quarantine -Force)
    if (Test-Path -LiteralPath $avdDirectory) {
        Move-Item -LiteralPath $avdDirectory -Destination (
            Join-Path $quarantine "$avd.avd"
        )
    }
    if (Test-Path -LiteralPath $avdIni) {
        Move-Item -LiteralPath $avdIni -Destination (
            Join-Path $quarantine "$avd.ini"
        )
    }
    return $quarantine
}


function Invoke-BootstrapAndRequireReady {
    $bootstrap = Join-Path $root 'tools\bootstrap_android.ps1'
    $bootstrapResult = Invoke-NativeChecked `
        -FilePath 'powershell.exe' `
        -Arguments @(
            '-NoProfile',
            '-ExecutionPolicy', 'Bypass',
            '-File', $bootstrap
        ) `
        -Description 'Android bootstrap'
    if ($bootstrapResult.StdErr.Trim()) {
        Write-Diagnostic $bootstrapResult.StdErr.Trim()
    }
    try {
        $bootstrapJson = $bootstrapResult.StdOut.Trim() | ConvertFrom-Json
    } catch {
        throw "Android bootstrap did not return valid JSON: $($bootstrapResult.StdOut)"
    }
    if (-not $bootstrapJson.ready) {
        throw 'Android bootstrap did not report ready=true'
    }
    if (-not (Test-AndroidToolchain) -or -not (Test-AvdContract)) {
        throw 'Android bootstrap returned success without satisfying its contract'
    }
    return $bootstrapJson
}


function Start-OwnedEmulatorAttempt {
    param(
        [string[]]$ExtraArguments = @(),
        [Parameter(Mandatory = $true)][string]$EmulatorStdout,
        [Parameter(Mandatory = $true)][string]$EmulatorStderr
    )
    Assert-PortsUnowned -Ports @(5556, 5557) -Purpose $serial
    $arguments = @(
        '-avd', $avd,
        '-port', '5556',
        '-netdelay', 'none',
        '-netspeed', 'full',
        '-no-boot-anim',
        '-gpu', 'swiftshader_indirect'
    ) + $ExtraArguments + @('-no-snapshot')
    $records = New-Object System.Collections.Generic.List[object]
    $wrapper = Start-OwnedPersistentProcess `
        -FilePath $emulator `
        -Arguments $arguments `
        -WorkingDirectory (Split-Path $emulator -Parent) `
        -StdoutPath $EmulatorStdout `
        -StderrPath $EmulatorStderr
    foreach ($record in @($wrapper.Records)) {
        [void]$records.Add($record)
    }
    try {
        $owner = Wait-NewEmulatorBoot `
            -StartedPids $records -TimeoutSeconds 300 `
            -EmulatorStdout $EmulatorStdout -EmulatorStderr $EmulatorStderr
        return [pscustomobject]@{
            Owner = $owner
            Records = $records.ToArray()
            WrapperPid = $wrapper.ProcessId
        }
    } catch {
        Stop-OwnedProcesses -Records $records.ToArray()
        throw
    }
}


function Get-RemoteCaStatus {
    param(
        [Parameter(Mandatory = $true)][string]$RemotePath,
        [Parameter(Mandatory = $true)][string]$ExpectedDigest
    )
    try {
        $digestResult = Invoke-Adb -Arguments @(
            'shell', 'toybox', 'sha256sum', $RemotePath
        ) -Description "remote CA digest ($RemotePath)"
        $statResult = Invoke-Adb -Arguments @(
            'shell', 'stat', '-c', '%U:%G:%a', $RemotePath
        ) -Description "remote CA ownership ($RemotePath)"
        $contextResult = Invoke-Adb -Arguments @(
            'shell', 'ls', '-lZ', $RemotePath
        ) -Description "remote CA SELinux context ($RemotePath)"
    } catch {
        return [pscustomobject]@{
            Valid = $false
            Details = $_.Exception.Message
        }
    }
    $digestMatch = [regex]::Match(
        $digestResult.StdOut.ToLowerInvariant(),
        '\b[0-9a-f]{64}\b'
    )
    $digest = if ($digestMatch.Success) { $digestMatch.Value } else { '' }
    $ownership = $statResult.StdOut.Trim()
    $context = $contextResult.StdOut.Trim()
    $validContext = $context -match (
        'u:object_r:misc_user_data_file:s0'
    )
    return [pscustomobject]@{
        Valid = (
            ($digest -eq $ExpectedDigest) -and
            ($ownership -eq 'root:root:644') -and
            $validContext
        )
        Details = (
            "digest=$digest ownership=$ownership context='$context'"
        )
    }
}


function Get-InstalledBaseApkStatus {
    param(
        [Parameter(Mandatory = $true)][string]$PackageName,
        [Parameter(Mandatory = $true)][string]$ExpectedDigest
    )
    try {
        $pathResult = Invoke-Adb -Arguments @(
            'shell', 'pm', 'path', $PackageName
        ) -Description "installed package path ($PackageName)"
    } catch {
        return [pscustomobject]@{
            Exists = $false
            Exact = $false
            BasePath = $null
            Digest = $null
            Details = $_.Exception.Message
        }
    }
    $basePaths = @(
        $pathResult.StdOut -split "\r?\n" |
        Where-Object { $_ -match '^package:' } |
        ForEach-Object { $_.Substring('package:'.Length).Trim() }
    )
    if ($basePaths.Count -eq 0) {
        return [pscustomobject]@{
            Exists = $false
            Exact = $false
            BasePath = $null
            Digest = $null
            Details = $pathResult.StdOut.Trim()
        }
    }
    if ($basePaths.Count -ne 1) {
        throw (
            "package $PackageName must expose exactly one base APK, got " +
            "$($basePaths.Count): $($pathResult.StdOut)"
        )
    }
    $digestResult = Invoke-Adb -Arguments @(
        'shell', 'toybox', 'sha256sum', $basePaths[0]
    ) -Description "installed package digest ($PackageName)"
    $digestMatch = [regex]::Match(
        $digestResult.StdOut.ToLowerInvariant(),
        '\b[0-9a-f]{64}\b'
    )
    $digest = if ($digestMatch.Success) { $digestMatch.Value } else { '' }
    return [pscustomobject]@{
        Exists = $true
        Exact = ($digest -ceq $ExpectedDigest.ToLowerInvariant())
        BasePath = $basePaths[0]
        Digest = $digest
        Details = $digestResult.StdOut.Trim()
    }
}


function Ensure-ApkInstalled {
    param(
        [Parameter(Mandatory = $true)][string]$ApkPath,
        [Parameter(Mandatory = $true)][string]$PackageName,
        [Parameter(Mandatory = $true)][string]$ExpectedDigest,
        [switch]$SkipInstallation
    )
    $installed = Get-InstalledBaseApkStatus `
        -PackageName $PackageName -ExpectedDigest $ExpectedDigest
    if ($installed.Exact) {
        return $installed
    }
    if ($SkipInstallation) {
        $state = if ($installed.Exists) {
            "installed digest '$($installed.Digest)'"
        } else {
            'package absent'
        }
        throw (
            "-SkipInstall requires exact installed package $PackageName; $state, " +
            "expected $($ExpectedDigest.ToLowerInvariant())"
        )
    }
    try {
        $installResult = Invoke-Adb -Arguments @('install', '-r', $ApkPath) `
            -Description "APK install ($PackageName)"
    } catch {
        if ($_.Exception.Message -notmatch 'INSTALL_FAILED_UPDATE_INCOMPATIBLE') {
            throw
        }
        $uninstallResult = Invoke-Adb -Arguments @('uninstall', $PackageName) `
            -Description "incompatible package uninstall ($PackageName)"
        $installResult = Invoke-Adb -Arguments @('install', '-r', $ApkPath) `
            -Description "APK install retry ($PackageName)"
    }
    $installed = Get-InstalledBaseApkStatus `
        -PackageName $PackageName -ExpectedDigest $ExpectedDigest
    if (-not $installed.Exact) {
        throw (
            "installed base APK mismatch for $PackageName`: " +
            "expected $($ExpectedDigest.ToLowerInvariant()), " +
            "got '$($installed.Digest)' at '$($installed.BasePath)'"
        )
    }
    return $installed
}


function Invoke-PackageLaunchGate {
    param(
        [Parameter(Mandatory = $true)][string]$PackageName,
        [Parameter(Mandatory = $true)][string]$CompatibilityDiagnostics
    )
    try {
        $monkeyResult = Invoke-Adb -Arguments @(
            'shell', 'monkey', '-p', $PackageName, '1'
        ) -Description "package launch ($PackageName)"
    } catch {
        throw (
            "package launch failed; $CompatibilityDiagnostics`n" +
            $_.Exception.Message
        )
    }

    $packagePid = $null
    $escapedPackageName = [regex]::Escape($PackageName)
    $packageProcessPattern = (
        '(?m)^\S+\s+(?<pid>\d+)\s+.*\s' + $escapedPackageName + '$'
    )
    $launchDeadline = [DateTime]::UtcNow.AddSeconds(30)
    while ([DateTime]::UtcNow -lt $launchDeadline) {
        try {
            $pidResult = Invoke-Adb -Arguments @(
                'shell', 'pidof', $PackageName
            ) -Description "package PID ($PackageName)"
            if ($pidResult.StdOut.Trim() -match '^\d+(?:\s+\d+)*$') {
                $packagePid = ($pidResult.StdOut.Trim() -split '\s+')[0]
                break
            }
        } catch {
            try {
                $psResult = Invoke-Adb -Arguments @('shell', 'ps', '-A') `
                    -Description 'Android process listing'
                $match = [regex]::Match(
                    $psResult.StdOut,
                    $packageProcessPattern
                )
                if ($match.Success) {
                    $packagePid = $match.Groups['pid'].Value
                    break
                }
            } catch {
                # Continue polling until the bounded deadline.
            }
        }
        Start-Sleep -Milliseconds 500
    }
    if (-not $packagePid) {
        throw (
            "package $PackageName did not remain live; " +
            $CompatibilityDiagnostics
        )
    }

    Start-Sleep -Seconds 5
    $earlyLogcat = Invoke-Adb -Arguments @('logcat', '-d', '-v', 'time') `
        -Description 'early package logcat'
    if ($earlyLogcat.StdOut -match (
        "UnsatisfiedLinkError|dlopen failed|couldn't find.*lib|Fatal signal"
    )) {
        throw (
            "native compatibility failure after launch; " +
            "$CompatibilityDiagnostics`n$($earlyLogcat.StdOut)"
        )
    }

    try {
        $finalPidResult = Invoke-Adb -Arguments @(
            'shell', 'pidof', $PackageName
        ) -Description "post-window package PID ($PackageName)"
        $finalPidText = $finalPidResult.StdOut.Trim()
    } catch {
        throw (
            "package $PackageName did not remain live after compatibility " +
            "window; expectedPid=$packagePid $CompatibilityDiagnostics`n" +
            $_.Exception.Message
        )
    }
    $finalPids = if ($finalPidText -match '^\d+(?:\s+\d+)*$') {
        @($finalPidText -split '\s+')
    } else {
        @()
    }
    if ($finalPids -notcontains [string]$packagePid) {
        throw (
            "package $PackageName did not remain live after compatibility " +
            "window; expectedPid=$packagePid observed='$finalPidText' " +
            $CompatibilityDiagnostics
        )
    }
    return [string]$packagePid
}


function Test-ObjectProperty {
    param(
        [AllowNull()]$InputObject,
        [Parameter(Mandatory = $true)][string]$Name
    )
    if ($null -eq $InputObject) {
        return $false
    }
    if ($InputObject -is [Collections.IDictionary]) {
        foreach ($key in @($InputObject.Keys)) {
            if ([string]$key -ieq $Name) {
                return $true
            }
        }
        return $false
    }
    return @(
        $InputObject.PSObject.Properties.Name |
        Where-Object { $_ -ieq $Name }
    ).Count -gt 0
}


function Test-PositiveFileTime {
    param([AllowNull()]$Value)
    $parsed = 0L
    return (
        [long]::TryParse([string]$Value, [ref]$parsed) -and
        $parsed -gt 0
    )
}


function Test-OrderedStringArray {
    param(
        [AllowNull()]$Actual,
        [Parameter(Mandatory = $true)][string[]]$Expected
    )
    $actualValues = @($Actual | ForEach-Object { [string]$_ })
    if ($actualValues.Count -ne $Expected.Count) {
        return $false
    }
    for ($index = 0; $index -lt $Expected.Count; $index++) {
        if ($actualValues[$index] -cne $Expected[$index]) {
            return $false
        }
    }
    return $true
}


function Test-CompleteServiceStateRecord {
    param([AllowNull()]$Record)
    if ($null -eq $Record) {
        return $false
    }
    foreach ($name in @(
        'role',
        'port',
        'healthPath',
        'expectedHealthBody',
        'processId',
        'executablePath',
        'normalizedCommandLine',
        'creationDate',
        'creationFileTimeUtc',
        'launchFilePath',
        'arguments',
        'workingDirectory',
        'stdout',
        'stderr'
    )) {
        if (-not (Test-ObjectProperty -InputObject $Record -Name $name)) {
            return $false
        }
    }
    if (([string]$Record.role -cne 'gateway') -and
        ([string]$Record.role -cne 'edge')) {
        return $false
    }
    if (([int]$Record.port -le 0) -or
        ([int]$Record.processId -le 0) -or
        (-not [string]$Record.healthPath) -or
        (-not [string]$Record.expectedHealthBody) -or
        (-not [string]$Record.executablePath) -or
        (-not [string]$Record.normalizedCommandLine) -or
        (-not [string]$Record.creationDate) -or
        (-not (Test-PositiveFileTime $Record.creationFileTimeUtc)) -or
        (-not [string]$Record.launchFilePath) -or
        (-not [string]$Record.workingDirectory) -or
        (-not [string]$Record.stdout) -or
        (-not [string]$Record.stderr)) {
        return $false
    }
    foreach ($pathValue in @(
        $Record.executablePath,
        $Record.launchFilePath,
        $Record.workingDirectory,
        $Record.stdout,
        $Record.stderr
    )) {
        if (-not [IO.Path]::IsPathRooted([string]$pathValue)) {
            return $false
        }
    }
    return $true
}


function Test-CompleteLogcatState {
    param(
        [Parameter(Mandatory = $true)]$State,
        [switch]$AllowMissingCreationFileTime
    )
    foreach ($name in @(
        'logcatPid',
        'adbPath',
        'executablePath',
        'normalizedCommandLine',
        'creationDate',
        'serial',
        'arguments',
        'stdout',
        'stderr'
    )) {
        if (-not (Test-ObjectProperty -InputObject $State -Name $name)) {
            return $false
        }
    }
    if (([int]$State.logcatPid -le 0) -or
        (-not [IO.Path]::IsPathRooted([string]$State.adbPath)) -or
        (-not [IO.Path]::IsPathRooted([string]$State.executablePath)) -or
        (-not [string]$State.normalizedCommandLine) -or
        (-not [string]$State.creationDate) -or
        ([string]$State.serial -cne 'emulator-5556') -or
        (-not [IO.Path]::IsPathRooted([string]$State.stdout)) -or
        (-not [IO.Path]::IsPathRooted([string]$State.stderr)) -or
        (-not (Test-OrderedStringArray `
            -Actual $State.arguments `
            -Expected @('-s', 'emulator-5556', 'logcat', '-v', 'time')))) {
        return $false
    }
    $hasFileTime = Test-ObjectProperty `
        -InputObject $State -Name 'creationFileTimeUtc'
    if ($hasFileTime) {
        return Test-PositiveFileTime $State.creationFileTimeUtc
    }
    return [bool]$AllowMissingCreationFileTime
}


function New-EmptyLauncherState {
    return [ordered]@{
        schemaVersion = 2
        gateway = $null
        edge = $null
    }
}


function Read-LauncherState {
    param(
        [Parameter(Mandatory = $true)][string]$StatePath,
        [switch]$PersistMigration
    )
    if (-not (Test-Path -LiteralPath $StatePath -PathType Leaf)) {
        return [pscustomobject](New-EmptyLauncherState)
    }
    try {
        $state = Get-Content -Raw -LiteralPath $StatePath | ConvertFrom-Json
    } catch {
        throw "launcher state is invalid JSON: $StatePath"
    }
    if (-not (Test-ObjectProperty -InputObject $state -Name 'schemaVersion')) {
        throw "launcher state has no schemaVersion: $StatePath"
    }
    if ([int]$state.schemaVersion -eq 1) {
        if (-not (Test-CompleteLogcatState `
            -State $state -AllowMissingCreationFileTime)) {
            throw "launcher schema-1 logcat state is incomplete: $StatePath"
        }
        $state.schemaVersion = 2
        $state | Add-Member -NotePropertyName gateway `
            -NotePropertyValue $null -Force
        $state | Add-Member -NotePropertyName edge `
            -NotePropertyValue $null -Force
        if ($PersistMigration) {
            Write-AtomicState -StatePath $StatePath -State $state
        }
        return $state
    }
    if ([int]$state.schemaVersion -ne 2) {
        throw (
            "unsupported launcher state schema '$($state.schemaVersion)': " +
            $StatePath
        )
    }
    foreach ($role in @('gateway', 'edge')) {
        if (-not (Test-ObjectProperty -InputObject $state -Name $role)) {
            throw "launcher schema-2 state has no $role property: $StatePath"
        }
        if (($null -ne $state.$role) -and
            (-not (Test-CompleteServiceStateRecord -Record $state.$role))) {
            throw "launcher schema-2 $role record is incomplete: $StatePath"
        }
    }
    $logcatFields = @(
        'logcatPid',
        'adbPath',
        'executablePath',
        'normalizedCommandLine',
        'creationDate',
        'creationFileTimeUtc',
        'serial',
        'arguments',
        'stdout',
        'stderr'
    )
    $presentLogcatFields = @(
        $logcatFields |
        Where-Object {
            Test-ObjectProperty -InputObject $state -Name $_
        }
    )
    if ($presentLogcatFields.Count -gt 0) {
        $allLogcatFieldsAreNull = (
            $presentLogcatFields.Count -eq $logcatFields.Count
        )
        if ($allLogcatFieldsAreNull) {
            foreach ($name in $logcatFields) {
                if ($null -ne $state.$name) {
                    $allLogcatFieldsAreNull = $false
                    break
                }
            }
        }
        if ((-not $allLogcatFieldsAreNull) -and
            (-not (Test-CompleteLogcatState `
                -State $state -AllowMissingCreationFileTime))) {
            throw "launcher schema-2 logcat record is incomplete: $StatePath"
        }
    }
    return $state
}


function New-ServiceStateRecord {
    param(
        [Parameter(Mandatory = $true)]$Specification,
        [Parameter(Mandatory = $true)]$OwnershipRecord,
        [Parameter(Mandatory = $true)][string]$StdoutPath,
        [Parameter(Mandatory = $true)][string]$StderrPath
    )
    if (-not (Test-PositiveFileTime $OwnershipRecord.CreationFileTimeUtc)) {
        throw 'service ownership requires creationFileTimeUtc'
    }
    $record = [ordered]@{
        role = [string]$Specification.role
        port = [int]$Specification.port
        healthPath = [string]$Specification.healthPath
        expectedHealthBody = [string]$Specification.expectedHealthBody
        processId = [int]$OwnershipRecord.ProcessId
        executablePath = [IO.Path]::GetFullPath(
            [string]$OwnershipRecord.ExecutablePath
        )
        normalizedCommandLine =
            [string]$OwnershipRecord.NormalizedCommandLine
        creationDate = [string]$OwnershipRecord.CreationDate
        creationFileTimeUtc =
            [string]$OwnershipRecord.CreationFileTimeUtc
        launchFilePath = [IO.Path]::GetFullPath(
            [string]$Specification.launchFilePath
        )
        arguments = @(
            $Specification.arguments |
            ForEach-Object { [string]$_ }
        )
        workingDirectory = [IO.Path]::GetFullPath(
            [string]$Specification.workingDirectory
        )
        stdout = [IO.Path]::GetFullPath($StdoutPath)
        stderr = [IO.Path]::GetFullPath($StderrPath)
    }
    if (-not (Test-CompleteServiceStateRecord -Record $record)) {
        throw 'refusing to create an incomplete service ownership record'
    }
    return [pscustomobject]$record
}


function Test-ServiceStateRecordMatches {
    param(
        [AllowNull()]$Record,
        [Parameter(Mandatory = $true)]$Live,
        [Parameter(Mandatory = $true)]$Specification,
        [switch]$RequireExistingLogs
    )
    if (-not (Test-CompleteServiceStateRecord -Record $Record)) {
        return $false
    }
    $identityRecord = [pscustomobject]@{
        ProcessId = [int]$Record.processId
        ExecutablePath = [string]$Record.executablePath
        NormalizedCommandLine = [string]$Record.normalizedCommandLine
        CreationDate = [string]$Record.creationDate
        CreationFileTimeUtc = [string]$Record.creationFileTimeUtc
    }
    if (-not (Test-ProcessOwnershipRecord `
        -Record $identityRecord -Live $Live)) {
        return $false
    }
    if (([string]$Record.role -cne [string]$Specification.role) -or
        ([int]$Record.port -ne [int]$Specification.port) -or
        ([string]$Record.healthPath -cne
            [string]$Specification.healthPath) -or
        ([string]$Record.expectedHealthBody -cne
            [string]$Specification.expectedHealthBody) -or
        ([string]$Record.launchFilePath -ine
            [string]$Specification.launchFilePath) -or
        ([string]$Record.workingDirectory -ine
            [string]$Specification.workingDirectory) -or
        (-not (Test-OrderedStringArray `
            -Actual $Record.arguments `
            -Expected @(
                $Specification.arguments |
                ForEach-Object { [string]$_ }
            )))) {
        return $false
    }
    if ($RequireExistingLogs -and
        ((-not (Test-Path -LiteralPath $Record.stdout -PathType Leaf)) -or
        (-not (Test-Path -LiteralPath $Record.stderr -PathType Leaf)))) {
        return $false
    }
    return $true
}


function Set-LauncherServiceState {
    param(
        [Parameter(Mandatory = $true)][string]$StatePath,
        [Parameter(Mandatory = $true)]$State,
        [ValidateSet('gateway', 'edge')][string]$Role,
        [AllowNull()]$Record
    )
    $State.$Role = $Record
    Write-AtomicState -StatePath $StatePath -State $State
}


function Resolve-ServiceReuse {
    param(
        [Parameter(Mandatory = $true)][string]$StatePath,
        [Parameter(Mandatory = $true)]$Specification
    )
    $state = Read-LauncherState -StatePath $StatePath -PersistMigration
    $live = Assert-ServicePortContract `
        -Port ([int]$Specification.port) `
        -Path ([string]$Specification.healthPath) `
        -ExpectedBody ([string]$Specification.expectedHealthBody)
    if (-not $live) {
        return [ordered]@{
            processId = $null
            owned = $false
            stdout = $null
            stderr = $null
        }
    }
    $role = [string]$Specification.role
    $record = $state.$role
    if ($record -and
        (Test-ServiceStateRecordMatches `
            -Record $record `
            -Live $live `
            -Specification $Specification `
            -RequireExistingLogs)) {
        return [ordered]@{
            processId = [int]$live.ProcessId
            owned = $true
            stdout = [string]$record.stdout
            stderr = [string]$record.stderr
        }
    }
    if ($record) {
        Set-LauncherServiceState `
            -StatePath $StatePath -State $state -Role $role -Record $null
    }
    return [ordered]@{
        processId = [int]$live.ProcessId
        owned = $false
        stdout = $null
        stderr = $null
    }
}


function Get-ServiceLaunchPython {
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        throw "service virtual environment launcher is missing: '$python'"
    }
    return (Resolve-Path -LiteralPath $python).Path
}


function Get-GatewayServiceSpecification {
    $servicePython = Get-ServiceLaunchPython
    return [pscustomobject][ordered]@{
        role = 'gateway'
        port = $gatewayPort
        healthPath = '/health'
        expectedHealthBody = $gatewayHealth
        launchFilePath = $servicePython
        arguments = @(
            '-m', 'uvicorn', 'app.main:app',
            '--host', '0.0.0.0',
            '--port', [string]$gatewayPort
        )
        workingDirectory = (Join-Path $root 'server')
    }
}


function Get-EdgeServiceSpecification {
    $servicePython = Get-ServiceLaunchPython
    return [pscustomobject][ordered]@{
        role = 'edge'
        port = $edgePort
        healthPath = '/__health'
        expectedHealthBody = $edgeHealth
        launchFilePath = $servicePython
        arguments = @((Join-Path $root 'tools\serve_lbres_proxy.py'))
        workingDirectory = $root
    }
}


function Resolve-OrStartOwnedService {
    param(
        [Parameter(Mandatory = $true)][string]$StatePath,
        [Parameter(Mandatory = $true)]$Specification,
        [Parameter(Mandatory = $true)][string]$StdoutPath,
        [Parameter(Mandatory = $true)][string]$StderrPath,
        [hashtable]$EnvironmentOverrides = @{}
    )
    $existing = Get-TcpListenerOwner -Port ([int]$Specification.port)
    if ($existing) {
        return Resolve-ServiceReuse `
            -StatePath $StatePath -Specification $Specification
    }
    $previousEnvironment = @{}
    foreach ($name in @($EnvironmentOverrides.Keys)) {
        $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable(
            [string]$name,
            'Process'
        )
        [Environment]::SetEnvironmentVariable(
            [string]$name,
            [string]$EnvironmentOverrides[$name],
            'Process'
        )
    }
    $started = $null
    try {
        try {
            $started = Start-OwnedPersistentProcess `
                -FilePath ([string]$Specification.launchFilePath) `
                -Arguments @($Specification.arguments) `
                -WorkingDirectory ([string]$Specification.workingDirectory) `
                -StdoutPath $StdoutPath `
                -StderrPath $StderrPath
        } finally {
            foreach ($name in @($EnvironmentOverrides.Keys)) {
                [Environment]::SetEnvironmentVariable(
                    [string]$name,
                    $previousEnvironment[$name],
                    'Process'
                )
            }
        }
        $live = Wait-ServiceHealth `
            -Port ([int]$Specification.port) `
            -Path ([string]$Specification.healthPath) `
            -ExpectedBody ([string]$Specification.expectedHealthBody) `
            -StdoutLog $StdoutPath `
            -StderrLog $StderrPath
        if (-not (Test-ProcessOwnershipRecord `
            -Record $started.OwnershipRecord -Live $live)) {
            throw (
                "started $($Specification.role) listener identity does not " +
                'match the broker-authenticated child'
            )
        }
        $record = New-ServiceStateRecord `
            -Specification $Specification `
            -OwnershipRecord $started.OwnershipRecord `
            -StdoutPath $started.StdoutPath `
            -StderrPath $started.StderrPath
        $state = Read-LauncherState `
            -StatePath $StatePath -PersistMigration
        Set-LauncherServiceState `
            -StatePath $StatePath `
            -State $state `
            -Role ([string]$Specification.role) `
            -Record $record
        return [ordered]@{
            processId = [int]$live.ProcessId
            owned = $true
            stdout = [string]$record.stdout
            stderr = [string]$record.stderr
        }
    } catch {
        if ($started -and $started.OwnershipRecord) {
            Stop-OwnedProcesses -Records @($started.OwnershipRecord)
        }
        throw
    }
}


function Wait-ServiceOwnerExitAndPortFree {
    param(
        [Parameter(Mandatory = $true)][int]$ProcessId,
        [Parameter(Mandatory = $true)][int]$Port,
        [ValidateRange(1, 60)][int]$TimeoutSeconds = 15
    )
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        $live = Get-ProcessDetails -ProcessId $ProcessId
        $listener = Get-TcpListenerOwner -Port $Port
        if ((-not $live) -and (-not $listener)) {
            return
        }
        Start-Sleep -Milliseconds 100
    } while ([DateTime]::UtcNow -lt $deadline)
    $remainingOwner = Get-TcpListenerOwner -Port $Port
    throw (
        "owned service PID $ProcessId did not leave port $Port; " +
        "listener=$(Format-Owner $remainingOwner)"
    )
}


function Test-CompleteIdentityMatch {
    param(
        [AllowNull()]$Before,
        [AllowNull()]$After
    )
    if (($null -eq $Before) -or ($null -eq $After)) {
        return $false
    }
    return Test-ProcessOwnershipRecord -Record $Before -Live $After
}


function Get-SafeReadOnlyEdgeObservation {
    param(
        [Parameter(Mandatory = $true)][scriptblock]$ObservePort,
        [Parameter(Mandatory = $true)][int]$Port
    )
    try {
        $observed = & $ObservePort $Port
    } catch {
        return $null
    }
    if (-not $observed) {
        return $null
    }
    foreach ($name in @(
        'ProcessId',
        'ExecutablePath',
        'NormalizedCommandLine',
        'CreationDate',
        'CreationFileTimeUtc'
    )) {
        if (-not (Test-ObjectProperty -InputObject $observed -Name $name)) {
            return $null
        }
    }
    if (([int]$observed.ProcessId -le 0) -or
        (-not [IO.Path]::IsPathRooted(
            [string]$observed.ExecutablePath
        )) -or
        (-not [string]$observed.NormalizedCommandLine) -or
        (-not [string]$observed.CreationDate) -or
        (-not (Test-PositiveFileTime $observed.CreationFileTimeUtc))) {
        return $null
    }
    return $observed
}


function Invoke-RestartGatewayTransaction {
    param(
        [Parameter(Mandatory = $true)][string]$StatePath,
        [Parameter(Mandatory = $true)]$Specification,
        [Parameter(Mandatory = $true)][string]$RuntimeDirectory,
        [Parameter(Mandatory = $true)][int]$EdgePort,
        [hashtable]$Hooks = @{}
    )
    if ([string]$Specification.role -cne 'gateway') {
        throw 'RestartGateway requires the hard-coded gateway specification'
    }
    $usingHooks = $Hooks.Count -gt 0
    $observePort = if ($Hooks.ContainsKey('ObservePort')) {
        $Hooks['ObservePort']
    } else {
        { param($observedPort) Get-TcpListenerOwner -Port $observedPort }
    }
    $getProcess = if ($Hooks.ContainsKey('GetProcess')) {
        $Hooks['GetProcess']
    } else {
        { param($observedPid) Get-ProcessDetails -ProcessId $observedPid }
    }
    $stopOwned = if ($Hooks.ContainsKey('StopOwned')) {
        $Hooks['StopOwned']
    } else {
        { param($records) Stop-OwnedProcesses -Records @($records) }
    }
    $waitGone = if ($Hooks.ContainsKey('WaitGone')) {
        $Hooks['WaitGone']
    } else {
        {
            param($observedPid, $observedPort)
            Wait-ServiceOwnerExitAndPortFree `
                -ProcessId $observedPid -Port $observedPort
        }
    }
    $startService = if ($Hooks.ContainsKey('StartService')) {
        $Hooks['StartService']
    } else {
        {
            param($serviceSpec, $outLog, $errLog)
            Start-OwnedPersistentProcess `
                -FilePath ([string]$serviceSpec.launchFilePath) `
                -Arguments @($serviceSpec.arguments) `
                -WorkingDirectory ([string]$serviceSpec.workingDirectory) `
                -StdoutPath $outLog `
                -StderrPath $errLog
        }
    }
    $waitHealth = if ($Hooks.ContainsKey('WaitHealth')) {
        $Hooks['WaitHealth']
    } else {
        {
            param($serviceSpec, $outLog, $errLog)
            Wait-ServiceHealth `
                -Port ([int]$serviceSpec.port) `
                -Path ([string]$serviceSpec.healthPath) `
                -ExpectedBody ([string]$serviceSpec.expectedHealthBody) `
                -StdoutLog $outLog `
                -StderrLog $errLog
        }
    }

    $state = Read-LauncherState -StatePath $StatePath -PersistMigration
    if (-not $state.gateway) {
        throw 'RestartGateway requires an owned schema-2 gateway record'
    }
    $edgeBefore = Get-SafeReadOnlyEdgeObservation `
        -ObservePort $observePort -Port $EdgePort
    $gatewayObserved = if ($usingHooks) {
        & $observePort ([int]$Specification.port)
    } else {
        Assert-ServicePortContract `
            -Port ([int]$Specification.port) `
            -Path ([string]$Specification.healthPath) `
            -ExpectedBody ([string]$Specification.expectedHealthBody)
    }
    if (-not $gatewayObserved) {
        throw 'the recorded gateway listener is absent'
    }
    if (-not (Test-ServiceStateRecordMatches `
        -Record $state.gateway `
        -Live $gatewayObserved `
        -Specification $Specification `
        -RequireExistingLogs)) {
        throw 'the live gateway does not match its complete schema-2 record'
    }
    $previousGatewayPid = [int]$state.gateway.processId
    $signalBoundaryLive = & $getProcess $previousGatewayPid
    if ((-not $signalBoundaryLive) -or
        (-not (Test-ServiceStateRecordMatches `
            -Record $state.gateway `
            -Live $signalBoundaryLive `
            -Specification $Specification `
            -RequireExistingLogs))) {
        throw (
            'gateway identity changed at the signal boundary; ' +
            'the process was left untouched'
        )
    }

    & $stopOwned @($state.gateway)
    & $waitGone $previousGatewayPid ([int]$Specification.port)
    Set-LauncherServiceState `
        -StatePath $StatePath -State $state -Role gateway -Record $null

    if (-not (Test-Path -LiteralPath $RuntimeDirectory -PathType Container)) {
        [void](New-Item -ItemType Directory -Path $RuntimeDirectory -Force)
    }
    $stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss-fff')
    $gatewayLog = Join-Path $RuntimeDirectory `
        "$stamp-gateway.stdout.log"
    $gatewayErrorLog = Join-Path $RuntimeDirectory `
        "$stamp-gateway.stderr.log"
    $started = $null
    try {
        $started = & $startService `
            $Specification $gatewayLog $gatewayErrorLog
        if (-not $started -or -not $started.OwnershipRecord) {
            throw 'gateway replacement did not return authenticated ownership'
        }
        $newLive = & $waitHealth `
            $Specification $gatewayLog $gatewayErrorLog
        if ((-not $newLive) -or
            (-not (Test-ProcessOwnershipRecord `
                -Record $started.OwnershipRecord -Live $newLive))) {
            throw (
                'replacement gateway listener does not match the ' +
                'broker-authenticated child'
            )
        }
        $newRecord = New-ServiceStateRecord `
            -Specification $Specification `
            -OwnershipRecord $started.OwnershipRecord `
            -StdoutPath $gatewayLog `
            -StderrPath $gatewayErrorLog
        Set-LauncherServiceState `
            -StatePath $StatePath `
            -State $state `
            -Role gateway `
            -Record $newRecord
    } catch {
        if ($started -and $started.OwnershipRecord) {
            & $stopOwned @($started.OwnershipRecord)
        }
        throw
    }

    $edgeAfter = Get-SafeReadOnlyEdgeObservation `
        -ObservePort $observePort -Port $EdgePort
    $edgeRetained = Test-CompleteIdentityMatch `
        -Before $edgeBefore -After $edgeAfter
    return [ordered]@{
        gatewayRestarted = $true
        previousGatewayPid = $previousGatewayPid
        gatewayPid = [int]$newRecord.processId
        gatewayOwned = $true
        gatewayLog = [string]$newRecord.stdout
        gatewayErrorLog = [string]$newRecord.stderr
        edgeIdentityRetained = [bool]$edgeRetained
        edgePid = if ($edgeRetained) {
            [int]$edgeBefore.ProcessId
        } else {
            $null
        }
    }
}


function Test-RecordedLogcatStillOwned {
    <#
        Return the live process only when the recorded logcat is still the
        process we started. A bare PID lookup is not enough: a missing
        logcatPid casts to 0, which Windows resolves to the System Idle
        Process, and a recycled PID belongs to somebody else entirely. Both
        would otherwise be reported as a live owner and permanently refuse to
        replace the state.
    #>
    param([Parameter(Mandatory = $true)][string]$StatePath)
    if (-not (Test-Path -LiteralPath $StatePath)) {
        return $null
    }
    try {
        $state = Get-Content -Raw -LiteralPath $StatePath | ConvertFrom-Json
    } catch {
        return $null
    }
    if (-not (Test-ObjectProperty -InputObject $state -Name 'logcatPid')) {
        return $null
    }
    $recordedPid = 0
    try {
        $recordedPid = [int]$state.logcatPid
    } catch {
        return $null
    }
    if ($recordedPid -le 0) {
        return $null
    }
    $live = Get-ProcessDetails -ProcessId $recordedPid
    if (-not $live) {
        return $null
    }
    $record = [pscustomobject]@{
        ProcessId = $recordedPid
        ExecutablePath = [string]$state.executablePath
        NormalizedCommandLine = [string]$state.normalizedCommandLine
        CreationDate = [string]$state.creationDate
    }
    if (Test-ObjectProperty -InputObject $state -Name 'creationFileTimeUtc') {
        $record | Add-Member -NotePropertyName CreationFileTimeUtc `
            -NotePropertyValue ([string]$state.creationFileTimeUtc)
    }
    if (-not (Test-ProcessOwnershipRecord -Record $record -Live $live)) {
        return $null
    }
    return $live
}


function Stop-RecordedLogcat {
    param([Parameter(Mandatory = $true)][string]$StatePath)
    if (-not (Test-Path -LiteralPath $StatePath)) {
        return $false
    }
    try {
        $state = Get-Content -Raw -LiteralPath $StatePath | ConvertFrom-Json
    } catch {
        return $false
    }
    if ((@((1, 2)) -notcontains [int]$state.schemaVersion) -or
        (-not $state.logcatPid) -or
        (-not [IO.Path]::IsPathRooted([string]$state.adbPath)) -or
        (-not [IO.Path]::IsPathRooted([string]$state.executablePath)) -or
        (-not $state.normalizedCommandLine) -or
        (-not $state.creationDate) -or
        ($state.serial -ne 'emulator-5556')) {
        return $false
    }
    $expectedArguments = @('-s', 'emulator-5556', 'logcat', '-v', 'time')
    $recordedArguments = @($state.arguments | ForEach-Object { [string]$_ })
    if (($recordedArguments.Count -ne $expectedArguments.Count) -or
        ((Compare-Object $recordedArguments $expectedArguments -SyncWindow 0).Count -ne 0)) {
        return $false
    }
    $live = Get-ProcessDetails -ProcessId ([int]$state.logcatPid)
    if (-not $live) {
        return $false
    }
    try {
        $expectedExecutable = [IO.Path]::GetFullPath([string]$state.adbPath)
        $liveExecutable = [IO.Path]::GetFullPath([string]$live.ExecutablePath)
    } catch {
        return $false
    }
    if (($liveExecutable -ine $expectedExecutable) -or
        ($liveExecutable -ine [string]$state.executablePath) -or
        ($live.CommandLine -notmatch [regex]::Escape('emulator-5556')) -or
        ($live.CommandLine -notmatch '\blogcat\b') -or
        ($live.CommandLine -notmatch '(?:^|\s)-v(?:\s+)time(?:\s|$)')) {
        return $false
    }
    $record = [pscustomobject]@{
        ProcessId = [int]$state.logcatPid
        ExecutablePath = [string]$state.executablePath
        NormalizedCommandLine = [string]$state.normalizedCommandLine
        CreationDate = [string]$state.creationDate
    }
    if (Test-ObjectProperty `
        -InputObject $state -Name 'creationFileTimeUtc') {
        $record | Add-Member -NotePropertyName CreationFileTimeUtc `
            -NotePropertyValue ([string]$state.creationFileTimeUtc)
    }
    if (-not (Test-ProcessOwnershipRecord -Record $record -Live $live)) {
        return $false
    }
    Stop-OwnedProcesses -Records @($record)
    return -not [bool](Get-ProcessDetails -ProcessId ([int]$state.logcatPid))
}


function Write-AtomicState {
    param(
        [Parameter(Mandatory = $true)][string]$StatePath,
        [Parameter(Mandatory = $true)]$State
    )
    $directory = Split-Path $StatePath -Parent
    [void](New-Item -ItemType Directory -Path $directory -Force)
    $temporary = Join-Path $directory (
        '.' + [IO.Path]::GetFileName($StatePath) + '.' +
        [Guid]::NewGuid().ToString('N') + '.tmp'
    )
    $backup = $temporary + '.replace-backup'
    try {
        [IO.File]::WriteAllText(
            $temporary,
            ($State | ConvertTo-Json -Depth 16 -Compress),
            (New-Object Text.UTF8Encoding($false))
        )
        if (Test-Path -LiteralPath $StatePath) {
            [IO.File]::Replace($temporary, $StatePath, $backup)
        } else {
            [IO.File]::Move($temporary, $StatePath)
        }
    } finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force
        }
        if (Test-Path -LiteralPath $backup) {
            Remove-Item -LiteralPath $backup -Force
        }
    }
}


function Get-RepositoryLauncherMutexName {
    param([Parameter(Mandatory = $true)][string]$RepositoryRoot)
    $canonicalRoot = (
        Resolve-Path -LiteralPath $RepositoryRoot -ErrorAction Stop
    ).Path
    $canonicalRoot = (
        [IO.Path]::GetFullPath($canonicalRoot)
    ).TrimEnd('\', '/').ToUpperInvariant()
    $sha256 = [Security.Cryptography.SHA256]::Create()
    try {
        $digestBytes = $sha256.ComputeHash(
            [Text.Encoding]::UTF8.GetBytes($canonicalRoot)
        )
    } finally {
        $sha256.Dispose()
    }
    $digest = -join @(
        $digestBytes | ForEach-Object { $_.ToString('x2') }
    )
    return "Local\SpiralWarriorLauncher-$digest"
}


function Get-LauncherMutexNameForMode {
    param(
        [ValidateSet(
            'Normal',
            'Capture',
            'RestartGateway',
            'Doctor'
        )][string]$Mode,
        [Parameter(Mandatory = $true)][string]$RepositoryRoot
    )
    if ($Mode -eq 'Doctor') {
        return $null
    }
    return Get-RepositoryLauncherMutexName -RepositoryRoot $RepositoryRoot
}


function Enter-RepositoryLauncherMutex {
    param(
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [ValidateRange(1, 60000)][int]$TimeoutMilliseconds = 5000
    )
    $name = Get-RepositoryLauncherMutexName -RepositoryRoot $RepositoryRoot
    $mutex = New-Object Threading.Mutex($false, $name)
    $acquired = $false
    try {
        try {
            $acquired = $mutex.WaitOne($TimeoutMilliseconds)
        } catch [Threading.AbandonedMutexException] {
            $acquired = $true
            Write-Diagnostic (
                "launcher mutex '$name' was abandoned; ownership recovered"
            )
        }
        if (-not $acquired) {
            throw (
                "launcher mutex timeout after $TimeoutMilliseconds ms: $name"
            )
        }
        return [pscustomobject]@{
            Name = $name
            Mutex = $mutex
            Acquired = $true
        }
    } catch {
        if (-not $acquired) {
            $mutex.Dispose()
        }
        throw
    }
}


function Exit-RepositoryLauncherMutex {
    param([AllowNull()]$Token)
    if (-not $Token) {
        return
    }
    try {
        if ($Token.Acquired) {
            $Token.Mutex.ReleaseMutex()
        }
    } finally {
        $Token.Mutex.Dispose()
    }
}


function Invoke-WithLauncherMutex {
    param(
        [ValidateSet(
            'Normal',
            'Capture',
            'RestartGateway',
            'Doctor'
        )][string]$Mode,
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)][scriptblock]$Operation,
        [ValidateRange(1, 60000)][int]$TimeoutMilliseconds = 5000
    )
    if ($Mode -eq 'Doctor') {
        return (& $Operation)
    }
    $token = $null
    try {
        $token = Enter-RepositoryLauncherMutex `
            -RepositoryRoot $RepositoryRoot `
            -TimeoutMilliseconds $TimeoutMilliseconds
        return (& $Operation)
    } finally {
        Exit-RepositoryLauncherMutex -Token $token
    }
}


function Invoke-ReadOnlyNativeProbe {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @()
    )
    if (-not (Test-Path -LiteralPath $FilePath -PathType Leaf)) {
        return [pscustomobject]@{
            ExitCode = $null
            StdOut = ''
            StdErr = ''
        }
    }
    $previousErrorAction = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $captured = @(& $FilePath @Arguments 2>&1)
        $exitCode = $LASTEXITCODE
    } catch {
        return [pscustomobject]@{
            ExitCode = $null
            StdOut = ''
            StdErr = $_.Exception.Message
        }
    } finally {
        $ErrorActionPreference = $previousErrorAction
    }
    $lines = @($captured | ForEach-Object { [string]$_ })
    return [pscustomobject]@{
        ExitCode = $exitCode
        StdOut = ($lines -join "`n")
        StdErr = ''
    }
}


function Test-Java17ReadOnly {
    $candidates = New-Object System.Collections.Generic.List[string]
    if ($env:JAVA_HOME) {
        $candidates.Add((Join-Path $env:JAVA_HOME 'bin\java.exe'))
    }
    $pathJava = Get-Command java.exe -ErrorAction SilentlyContinue
    if ($pathJava) {
        $candidates.Add([string]$pathJava.Source)
    }
    $adoptiumRoot = Join-Path $env:ProgramFiles 'Eclipse Adoptium'
    if (Test-Path -LiteralPath $adoptiumRoot -PathType Container) {
        Get-ChildItem -LiteralPath $adoptiumRoot -Directory -Filter 'jdk-17*' |
            Sort-Object Name -Descending |
            ForEach-Object {
                $candidates.Add((Join-Path $_.FullName 'bin\java.exe'))
            }
    }
    foreach ($candidate in @($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            continue
        }
        $probe = Invoke-ReadOnlyNativeProbe -FilePath $candidate `
            -Arguments @('-version')
        if (($probe.ExitCode -eq 0) -and
            ($probe.StdOut -match 'version\s+"(?:1\.)?17(?:[._"]|$)')) {
            return $true
        }
    }
    return $false
}


function Get-EmulatorAccelerationStatus {
    $status = [ordered]@{
        avd = $false
        acceleration = 'emulator missing'
        accelerationCompatible = $false
    }
    if (-not (Test-Path -LiteralPath $emulator -PathType Leaf)) {
        return [pscustomobject]$status
    }
    $avdProbe = Invoke-ReadOnlyNativeProbe -FilePath $emulator `
        -Arguments @('-list-avds')
    if ($avdProbe.ExitCode -eq 0) {
        $listedAvds = @(
            $avdProbe.StdOut -split "\r?\n" |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ }
        )
        $status.avd = $listedAvds -contains $avd
    }
    $accelerationProbe = Invoke-ReadOnlyNativeProbe -FilePath $emulator `
        -Arguments @('-accel-check')
    $status.acceleration = if ($accelerationProbe.StdOut) {
        $accelerationProbe.StdOut
    } elseif ($accelerationProbe.StdErr) {
        $accelerationProbe.StdErr
    } else {
        "emulator acceleration probe exit=$($accelerationProbe.ExitCode)"
    }
    $status.accelerationCompatible = [bool](
        ($accelerationProbe.ExitCode -eq 0) -and
        ($status.acceleration -match
            '(?i)(?:installed\s+and\s+usable|is\s+usable|accel:\s*0)')
    )
    return [pscustomobject]$status
}


function Assert-NormalLaunchPreflight {
    param(
        [Parameter(Mandatory = $true)]$HostStatus,
        [Parameter(Mandatory = $true)]$PythonStatus,
        [Parameter(Mandatory = $true)]$ArtifactStatus,
        [Parameter(Mandatory = $true)]$OpenSslStatus
    )
    Assert-SupportedWindowsHost -Status $HostStatus
    if (-not [bool]$PythonStatus.compatible) {
        throw (
            'python runtime is incompatible; require 64-bit CPython ' +
            '>=3.12,<3.13 with compile/runtime zlib exactly 1.3.1'
        )
    }
    if (-not [bool]$ArtifactStatus.artifactReady) {
        throw (
            "artifact route is unavailable for edition $Edition; require " +
            'the exact pinned runtime APK or exact rebuild inputs'
        )
    }
    if (-not [bool]$OpenSslStatus.available) {
        throw (
            'openssl runtime is unavailable; set SPIRAL_OPENSSL to an exact ' +
            'openssl.exe or install Git for Windows'
        )
    }
}


function Assert-RestartGatewayPreflight {
    param(
        [Parameter(Mandatory = $true)]$HostStatus,
        [Parameter(Mandatory = $true)]$PythonStatus
    )
    Assert-SupportedWindowsHost -Status $HostStatus
    if (-not [bool]$PythonStatus.compatible) {
        throw (
            'python runtime is incompatible for RestartGateway; require ' +
            '64-bit CPython >=3.12,<3.13 with zlib exactly 1.3.1'
        )
    }
}


function Get-DoctorResult {
    $hostStatus = Get-WindowsHostStatus
    $pythonStatus = Get-PythonRuntimeStatus -PythonPath $python
    $openSslStatus = Get-OpenSslRuntimeStatus
    $artifactStatus = Get-ArtifactRouteStatus -Edition $Edition -Root $root
    $emulatorStatus = Get-EmulatorAccelerationStatus
    $java17Present = Test-Java17ReadOnly
    $curlPresent = [bool](Get-Command curl.exe -ErrorAction SilentlyContinue)
    $tarPresent = [bool](Get-Command tar.exe -ErrorAction SilentlyContinue)
    $wingetPresent = [bool](Get-Command winget.exe -ErrorAction SilentlyContinue)
    $adbPresent = Test-Path -LiteralPath $adb -PathType Leaf
    $emulatorPresent = Test-Path -LiteralPath $emulator -PathType Leaf
    $hostCompatible = Test-SupportedWindowsHost -Status $hostStatus
    $preflightReady = [bool](
        $hostCompatible -and
        [bool]$pythonStatus.compatible -and
        [bool]$artifactStatus.artifactReady -and
        [bool]$openSslStatus.available
    )
    $androidReady = [bool](
        $java17Present -and
        $adbPresent -and
        $emulatorPresent -and
        [bool]$emulatorStatus.avd -and
        [bool]$emulatorStatus.accelerationCompatible -and
        (Test-AndroidToolchain)
    )
    return [ordered]@{
        edition = $Edition
        edgePort = $edgePort
        gatewayPort = $gatewayPort
        package = $package
        apk = $apk
        sourceApk = $sourceApk
        sourceApkSha256 = if ($expectedSourceApkSha256) {
            $expectedSourceApkSha256.ToLowerInvariant()
        } else {
            $null
        }
        apkSha256 = $expectedApkSha256.ToLowerInvariant()
        serial = $serial
        caCertificate = $caCertificate
        platform = [string]$hostStatus.platform
        windowsProductName = [string]$hostStatus.windowsProductName
        windowsVersion = [string]$hostStatus.windowsVersion
        windowsBuild = [string]$hostStatus.windowsBuild
        osArchitecture = [string]$hostStatus.osArchitecture
        processArchitecture = [string]$hostStatus.processArchitecture
        powershellEdition = [string]$hostStatus.powershellEdition
        powershellVersion = [string]$hostStatus.powershellVersion
        wslDetected = [bool]$hostStatus.wslDetected
        virtualizationFirmwareEnabled =
            [bool]$hostStatus.virtualizationFirmwareEnabled
        hostCompatible = $hostCompatible
        python = [bool]$pythonStatus.exists
        pythonCompatible = [bool]$pythonStatus.compatible
        pythonVersion = [string]$pythonStatus.version
        pythonArchitecture = [string]$pythonStatus.architecture
        zlibCompileVersion = [string]$pythonStatus.zlibCompileVersion
        zlibRuntimeVersion = [string]$pythonStatus.zlibRuntimeVersion
        openssl = [bool]$openSslStatus.available
        opensslPath = if ($openSslStatus.path) {
            [string]$openSslStatus.path
        } else {
            $null
        }
        opensslVersion = if ($openSslStatus.version) {
            [string]$openSslStatus.version
        } else {
            $null
        }
        artifactRoute = [string]$artifactStatus.artifactRoute
        artifactReady = [bool]$artifactStatus.artifactReady
        sourceApkPresent = [bool]$artifactStatus.sourceApkPresent
        apkPresent = [bool]$artifactStatus.apkPresent
        signerPresent = [bool]$artifactStatus.signerPresent
        java17 = $java17Present
        curl = $curlPresent
        tar = $tarPresent
        winget = $wingetPresent
        adb = $adbPresent
        emulator = $emulatorPresent
        avd = [bool]$emulatorStatus.avd
        acceleration = [string]$emulatorStatus.acceleration
        accelerationCompatible =
            [bool]$emulatorStatus.accelerationCompatible
        preflightReady = $preflightReady
        androidReady = $androidReady
        launchReady = [bool]($preflightReady -and $androidReady)
    }
}


function Invoke-Launcher {
    param([hashtable]$TestHooks = @{})
    $modeOperation = if ($TestHooks.ContainsKey('ModeOperation')) {
        if ($TestHooks['ModeOperation'] -isnot [scriptblock]) {
            throw 'TestHooks.ModeOperation must be a scriptblock'
        }
        $TestHooks['ModeOperation']
    } else {
        $null
    }
    $modeContext = [pscustomobject][ordered]@{
        RepositoryRoot = $root
        StatePath = $statePath
        RuntimeDirectory = $runtimeDir
    }
    if ($RestartGateway -and ($Doctor -or $Capture -or $SkipInstall)) {
        throw (
            '-RestartGateway is mutually exclusive with -Doctor, -Capture, ' +
            'and -SkipInstall'
        )
    }
    $hostStatus = Get-WindowsHostStatus
    Assert-SupportedWindowsHost -Status $hostStatus
    if ($Doctor) {
        if ($modeOperation) {
            $doctorResult = & $modeOperation 'Doctor' $modeContext
            [Console]::Out.WriteLine((
                $doctorResult | ConvertTo-Json -Depth 8 -Compress
            ))
            return
        }
        $env:ANDROID_SDK_ROOT = $sdkRoot
        $env:ANDROID_AVD_HOME = $avdHome
        [Console]::Out.WriteLine((
            (Get-DoctorResult) | ConvertTo-Json -Depth 8 -Compress
        ))
        return
    }

    $pythonStatus = Get-PythonRuntimeStatus -PythonPath $python
    if ($RestartGateway) {
        Assert-RestartGatewayPreflight `
            -HostStatus $hostStatus -PythonStatus $pythonStatus
        $restartResult = Invoke-WithLauncherMutex `
            -Mode RestartGateway `
            -RepositoryRoot $root `
            -Operation {
                if ($modeOperation) {
                    & $modeOperation 'RestartGateway' $modeContext
                } else {
                    Invoke-RestartGatewayTransaction `
                        -StatePath $statePath `
                        -Specification (Get-GatewayServiceSpecification) `
                        -RuntimeDirectory $runtimeDir `
                        -EdgePort $edgePort
                }
            }
        [Console]::Out.WriteLine((
            $restartResult | ConvertTo-Json -Depth 8 -Compress
        ))
        return
    }
    $artifactStatus = Get-ArtifactRouteStatus -Edition $Edition -Root $root
    $openSslStatus = Get-OpenSslRuntimeStatus
    Assert-NormalLaunchPreflight `
        -HostStatus $hostStatus `
        -PythonStatus $pythonStatus `
        -ArtifactStatus $artifactStatus `
        -OpenSslStatus $openSslStatus

    $launcherMode = if ($Capture) { 'Capture' } else { 'Normal' }
    $launcherMutexToken = Enter-RepositoryLauncherMutex `
        -RepositoryRoot $root
    try {
    if ($modeOperation) {
        $modeResult = & $modeOperation $launcherMode $modeContext
        [Console]::Out.WriteLine((
            $modeResult | ConvertTo-Json -Depth 8 -Compress
        ))
        return
    }
    $env:ANDROID_SDK_ROOT = $sdkRoot
    $env:ANDROID_AVD_HOME = $avdHome
    $startedPids = New-Object System.Collections.Generic.List[object]
    $gatewayPid = $null
    $edgePid = $null
    $emulatorPid = $null
    $logcatPid = $null
    $logcatOwnership = $null
    $logcatPath = $null
    $gatewayOwned = $false
    $edgeOwned = $false
    $stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss-fff')
    [void](New-Item -ItemType Directory -Path $runtimeDir -Force)
    $gatewayLog = Join-Path $runtimeDir "$stamp-gateway.stdout.log"
    $gatewayErrorLog = Join-Path $runtimeDir "$stamp-gateway.stderr.log"
    $edgeLog = Join-Path $runtimeDir "$stamp-edge.stdout.log"
    $edgeErrorLog = Join-Path $runtimeDir "$stamp-edge.stderr.log"
    $emulatorLog = Join-Path $runtimeDir "$stamp-emulator.stdout.log"
    $emulatorErrorLog = Join-Path $runtimeDir "$stamp-emulator.stderr.log"

    try {
        $runtimeReady = (
            (Test-Java17) -and
            (Test-AndroidToolchain) -and
            (Test-AvdContract)
        )
        if (-not $runtimeReady) {
            $bootstrapJson = Invoke-BootstrapAndRequireReady
        }
        if (-not (Test-Path -LiteralPath $python)) {
            throw "local Python environment is missing: $python"
        }
        if (-not (Test-AvdContract)) {
            throw "AVD $avd does not use exact image $imagePackage"
        }
        if (-not (Test-AndroidToolchain)) {
            throw "Android platform 30/build-tools 30.0.3 contract is incomplete"
        }
        $accelerationStatus = Get-EmulatorAccelerationStatus
        if (-not $accelerationStatus.accelerationCompatible) {
            throw (
                'Android emulator acceleration is unavailable or unusable: ' +
                $accelerationStatus.acceleration
            )
        }

        if ($Edition -eq 'cn') {
            $builderResult = Invoke-NativeChecked `
                -FilePath $python `
                -Arguments @(
                    (Join-Path $root 'tools\build_cn_userca_apk.py'),
                    '--source', $sourceApk,
                    '--output', $apk,
                    '--sdk-root', $sdkRoot,
                    '--keystore', (Join-Path $root 'build\debug.keystore')
                ) `
                -Description 'derived CN user-CA APK build'
            if ($builderResult.StdErr.Trim()) {
                Write-Diagnostic $builderResult.StdErr.Trim()
            }
            if (($builderResult.StdOut -split "\r?\n" |
                Where-Object { $_.Length -gt 0 }).Count -ne 1) {
                throw "CN builder did not emit exactly one JSON object"
            }
            try {
                $builder = $builderResult.StdOut.Trim() | ConvertFrom-Json
            } catch {
                throw "CN builder returned invalid JSON: $($builderResult.StdOut)"
            }
            if ((-not $builder.ready) -or
                ([string]$builder.sourceSha256 -cne
                    $expectedSourceApkSha256.ToLowerInvariant()) -or
                ([string]$builder.outputSha256 -cne
                    $expectedApkSha256.ToLowerInvariant()) -or
                ([string]$builder.compiledMemberSha256 -cne
                    'be19b1947c55c92325d53643a5a4aaed16f4b241dd7a7c9a522d25287107cec4') -or
                ([string]$builder.signerSha256 -cne
                    '7ae2aa16d63e204b4a6ebe2aec06f49e57e13a9c8107cd6c68db37d9d86f0233') -or
                ([string]$builder.package -cne $package)) {
                throw "CN builder output does not match the pinned contract"
            }
        }

        $caResult = Invoke-NativeChecked `
            -FilePath $python `
            -Arguments @(
                (Join-Path $root 'tools\serve_lbres_proxy.py'),
                '--prepare-ca'
            ) `
            -Description 'local CA preparation'
        if (($caResult.StdOut -split "\r?\n" |
            Where-Object { $_.Length -gt 0 }).Count -ne 1) {
            throw "CA preparation did not emit exactly one JSON object"
        }
        try {
            $ca = $caResult.StdOut.Trim() | ConvertFrom-Json
        } catch {
            throw "CA preparation returned invalid JSON: $($caResult.StdOut)"
        }
        if ((-not [IO.Path]::IsPathRooted([string]$ca.certificate)) -or
            ([string]$ca.fingerprint -cnotmatch '^[0-9a-f]{64}$') -or
            ([string]$ca.androidHash -cnotmatch '^[0-9a-f]{8}$')) {
            throw "CA preparation returned invalid metadata"
        }

        $gatewayService = Resolve-OrStartOwnedService `
            -StatePath $statePath `
            -Specification (Get-GatewayServiceSpecification) `
            -StdoutPath $gatewayLog `
            -StderrPath $gatewayErrorLog
        $gatewayPid = $gatewayService.processId
        $gatewayOwned = [bool]$gatewayService.owned
        $gatewayLog = $gatewayService.stdout
        $gatewayErrorLog = $gatewayService.stderr

        $edgeService = Resolve-OrStartOwnedService `
            -StatePath $statePath `
            -Specification (Get-EdgeServiceSpecification) `
            -StdoutPath $edgeLog `
            -StderrPath $edgeErrorLog `
            -EnvironmentOverrides @{ OFFLINE_MODE = '1' }
        $edgePid = $edgeService.processId
        $edgeOwned = [bool]$edgeService.owned
        $edgeLog = $edgeService.stdout
        $edgeErrorLog = $edgeService.stderr

        $startServer = Invoke-NativeChecked -FilePath $adb `
            -Arguments @('start-server') -Description 'ADB server startup'
        $serialState = Get-AdbSerialState
        $newEmulatorStarted = $false
        if ($serialState) {
            if ($serialState -ne 'device') {
                throw "$serial is present in unsafe state '$serialState'; it will not be killed"
            }
            $avdNameResult = Invoke-Adb -Arguments @('emu', 'avd', 'name') `
                -Description 'running emulator AVD identity'
            $runningAvd = @(
                $avdNameResult.StdOut -split "\r?\n" |
                Where-Object { $_.Trim() -and $_.Trim() -ne 'OK' }
            )[0].Trim()
            if ($runningAvd -ne $avd) {
                throw "$serial runs AVD '$runningAvd', expected '$avd'"
            }
            $emulatorOwner = Get-TcpListenerOwner -Port 5556
            if (-not $emulatorOwner) {
                throw "$serial is a device but console port 5556 has no listener"
            }
            Assert-EmulatorOwner -Owner $emulatorOwner
            $emulatorPid = $emulatorOwner.ProcessId
        } else {
            $newEmulatorStarted = $true
            $attempt = $null
            try {
                $attempt = Start-OwnedEmulatorAttempt `
                    -EmulatorStdout $emulatorLog -EmulatorStderr $emulatorErrorLog
            } catch {
                $initialBootError = $_
                if ($initialBootError.Exception.Message -notmatch
                    'did not (?:boot|claim console port)') {
                    throw
                }
                Wait-EmulatorRecoverySafe
                $staleQuarantine = Move-StaleAvdStateToQuarantine
                Write-Diagnostic (
                    "initial AVD boot timed out; stale state quarantined at " +
                    $staleQuarantine
                )
                $coldLog = $emulatorLog -replace '\.stdout\.log$',
                    '-recovery-cold.stdout.log'
                $coldError = $emulatorErrorLog -replace '\.stderr\.log$',
                    '-recovery-cold.stderr.log'
                try {
                    $attempt = Start-OwnedEmulatorAttempt `
                        -EmulatorStdout $coldLog -EmulatorStderr $coldError
                    $emulatorLog = $coldLog
                    $emulatorErrorLog = $coldError
                } catch {
                    Wait-EmulatorRecoverySafe
                    $wipeLog = $emulatorLog -replace '\.stdout\.log$',
                        '-recovery-wipe.stdout.log'
                    $wipeError = $emulatorErrorLog -replace '\.stderr\.log$',
                        '-recovery-wipe.stderr.log'
                    try {
                        $attempt = Start-OwnedEmulatorAttempt `
                            -ExtraArguments @('-wipe-data') `
                            -EmulatorStdout $wipeLog -EmulatorStderr $wipeError
                        $emulatorLog = $wipeLog
                        $emulatorErrorLog = $wipeError
                    } catch {
                        Wait-EmulatorRecoverySafe
                        $avdQuarantine = Move-ExactAvdToQuarantine
                        Write-Diagnostic (
                            "cold and wipe-data boots failed; exact generated " +
                            "AVD quarantined at $avdQuarantine"
                        )
                        $bootstrapJson = Invoke-BootstrapAndRequireReady
                        $recreatedLog = $emulatorLog -replace '\.stdout\.log$',
                            '-recreated.stdout.log'
                        $recreatedError = $emulatorErrorLog -replace
                            '\.stderr\.log$', '-recreated.stderr.log'
                        $attempt = Start-OwnedEmulatorAttempt `
                            -EmulatorStdout $recreatedLog `
                            -EmulatorStderr $recreatedError
                        $emulatorLog = $recreatedLog
                        $emulatorErrorLog = $recreatedError
                    }
                }
            }
            foreach ($record in @($attempt.Records)) {
                [void]$startedPids.Add($record)
            }
            $emulatorOwner = $attempt.Owner
            $emulatorPid = $emulatorOwner.ProcessId
        }
        if (-not $newEmulatorStarted) {
            Wait-AdbBoot -TimeoutSeconds 300 -EmulatorPid $emulatorPid `
                -EmulatorStdout $emulatorLog -EmulatorStderr $emulatorErrorLog
        }

        $abiResult = Invoke-Adb -Arguments @(
            'shell', 'getprop', 'ro.product.cpu.abi'
        ) -Description 'emulator primary ABI'
        $abi = $abiResult.StdOut.Trim()
        $abiListResult = Invoke-Adb -Arguments @(
            'shell', 'getprop', 'ro.product.cpu.abilist'
        ) -Description 'emulator ABI list'
        $allProps = Invoke-Adb -Arguments @('shell', 'getprop') `
            -Description 'emulator properties'
        $isaProperties = @(
            $allProps.StdOut -split "\r?\n" |
            Where-Object { $_ -match '\[ro\.dalvik\.vm\.isa\.' }
        ) -join "`n"
        $compatibilityDiagnostics = (
            "abi=$abi; abilist=$($abiListResult.StdOut.Trim()); " +
            "dalvikIsa=$isaProperties"
        )
        if ($abi -ne 'x86_64') {
            throw "emulator primary ABI is '$abi', expected x86_64; $compatibilityDiagnostics"
        }
        if (-not (Test-AvdContract)) {
            throw "running AVD image contract changed; expected $imagePackage"
        }

        $hostCaDigest = (
            Get-FileHash -LiteralPath ([string]$ca.certificate) -Algorithm SHA256
        ).Hash.ToLowerInvariant()
        $caDirectory = '/data/misc/user/0/cacerts-added'
        $caRemotePath = "$caDirectory/$($ca.androidHash).0"
        if ($caRemotePath -cnotmatch
            '^/data/misc/user/0/cacerts-added/[0-9a-f]{8}\.0$') {
            throw "refusing unexpected user CA destination: $caRemotePath"
        }
        Enable-AdbRoot -EmulatorPid $emulatorPid `
            -EmulatorStdout $emulatorLog -EmulatorStderr $emulatorErrorLog
        $mkdirCa = Invoke-Adb -Arguments @(
            'shell', 'mkdir', '-p', $caDirectory
        ) -Description 'user CA directory creation'
        $directoryMode = Invoke-Adb -Arguments @(
            'shell', 'chmod', '0755', $caDirectory
        ) -Description 'user CA directory mode'
        $directoryContext = Invoke-Adb -Arguments @(
            'shell', 'restorecon', '-RF', $caDirectory
        ) -Description 'user CA directory SELinux restore'
        $remoteCa = Get-RemoteCaStatus `
            -RemotePath $caRemotePath -ExpectedDigest $hostCaDigest
        if (-not $remoteCa.Valid) {
            $temporaryCa = "/data/local/tmp/$($ca.androidHash).0"
            $pushResult = Invoke-Adb -Arguments @(
                'push', ([string]$ca.certificate), $temporaryCa
            ) -Description 'local CA upload'
            $temporaryDigest = Invoke-Adb -Arguments @(
                'shell', 'toybox', 'sha256sum', $temporaryCa
            ) -Description 'uploaded CA digest'
            if ($temporaryDigest.StdOut.ToLowerInvariant() -notmatch
                [regex]::Escape($hostCaDigest)) {
                throw "uploaded CA digest does not match host certificate"
            }
            $copyResult = Invoke-Adb -Arguments @(
                'shell', 'cp', $temporaryCa, $caRemotePath
            ) -Description 'user CA copy'
            $ownerResult = Invoke-Adb -Arguments @(
                'shell', 'chown', 'root:root', $caRemotePath
            ) -Description 'user CA ownership'
            $modeResult = Invoke-Adb -Arguments @(
                'shell', 'chmod', '0644', $caRemotePath
            ) -Description 'user CA mode'
            $restoreResult = Invoke-Adb -Arguments @(
                'shell', 'restorecon', '-F', $caRemotePath
            ) -Description 'user CA SELinux restore'
            $remoteCa = Get-RemoteCaStatus `
                -RemotePath $caRemotePath -ExpectedDigest $hostCaDigest
            if (-not $remoteCa.Valid) {
                throw "user CA verification failed before reboot: $($remoteCa.Details)"
            }
            $rebootResult = Invoke-Adb -Arguments @('reboot') `
                -Description 'user CA installation reboot'
            Wait-AdbBoot -TimeoutSeconds 300 -EmulatorPid $emulatorPid `
                -EmulatorStdout $emulatorLog -EmulatorStderr $emulatorErrorLog
            Enable-AdbRoot -EmulatorPid $emulatorPid `
                -EmulatorStdout $emulatorLog -EmulatorStderr $emulatorErrorLog
            $remoteCa = Get-RemoteCaStatus `
                -RemotePath $caRemotePath -ExpectedDigest $hostCaDigest
            if (-not $remoteCa.Valid) {
                throw "user CA verification failed after reboot: $($remoteCa.Details)"
            }
            $mounts = Invoke-Adb -Arguments @('shell', 'mount') `
                -Description 'post-user-CA mount verification'
            if (($mounts.StdOut + "`n" + $mounts.StdErr) -match
                '(?i)\boverlay(?:fs)?\b') {
                throw "overlay mount detected after user CA provisioning"
            }
        }

        $setProxy = Invoke-Adb -Arguments @(
            'shell', 'settings', 'put', 'global', 'http_proxy', '10.0.2.2:8888'
        ) -Description 'Android proxy configuration'
        $getProxy = Invoke-Adb -Arguments @(
            'shell', 'settings', 'get', 'global', 'http_proxy'
        ) -Description 'Android proxy verification'
        if ($getProxy.StdOut.Trim() -ne '10.0.2.2:8888') {
            throw "Android proxy is '$($getProxy.StdOut.Trim())', expected 10.0.2.2:8888"
        }

        if (-not (Test-Path -LiteralPath $apk)) {
            throw "selected APK does not exist: $apk"
        }
        $actualApkSha256 = (
            Get-FileHash -LiteralPath $apk -Algorithm SHA256
        ).Hash.ToUpperInvariant()
        if ($actualApkSha256 -ne $expectedApkSha256) {
            throw (
                "APK SHA-256 mismatch for $apk`: expected $expectedApkSha256, " +
                "got $actualApkSha256"
            )
        }
        try {
            $installedApk = Ensure-ApkInstalled `
                -ApkPath $apk -PackageName $package `
                -ExpectedDigest $expectedApkSha256 `
                -SkipInstallation:$SkipInstall
        } catch {
            throw (
                "APK install/reuse failed; $compatibilityDiagnostics`n" +
                $_.Exception.Message
            )
        }

        $clearLogcat = Invoke-Adb -Arguments @('logcat', '-c') `
            -Description 'logcat clear'
        if ($Capture) {
            if (Test-Path -LiteralPath $statePath) {
                $stopped = Stop-RecordedLogcat -StatePath $statePath
                if (-not $stopped) {
                    $oldLive = Test-RecordedLogcatStillOwned -StatePath $statePath
                    if ($oldLive) {
                        throw (
                            "refusing to replace launcher state for unverified live " +
                            "process $(Format-Owner $oldLive)"
                        )
                    }
                }
            }
            $captureDir = Join-Path $root 'research\launch_logcat'
            [void](New-Item -ItemType Directory -Path $captureDir -Force)
            $logcatPath = Join-Path $captureDir (
                "$stamp-$Edition-windows-local.log"
            )
            $logcatErrorPath = Join-Path $captureDir (
                "$stamp-$Edition-windows-local.stderr.log"
            )
            $logcatArguments = @('-s', $serial, 'logcat', '-v', 'time')
            $logcatProcess = Start-OwnedPersistentProcess `
                -FilePath $adb `
                -Arguments $logcatArguments `
                -WorkingDirectory $root `
                -StdoutPath $logcatPath `
                -StderrPath $logcatErrorPath
            $logcatPid = $logcatProcess.ProcessId
            $logcatOwnership = $logcatProcess.OwnershipRecord
            foreach ($record in @($logcatProcess.Records)) {
                [void]$startedPids.Add($record)
            }
            $state = Read-LauncherState `
                -StatePath $statePath -PersistMigration
            $logcatValues = [ordered]@{
                schemaVersion = 2
                logcatPid = $logcatPid
                adbPath = (Resolve-Path -LiteralPath $adb).Path
                executablePath = $logcatOwnership.ExecutablePath
                normalizedCommandLine = $logcatOwnership.NormalizedCommandLine
                creationDate = $logcatOwnership.CreationDate
                creationFileTimeUtc =
                    $logcatOwnership.CreationFileTimeUtc
                serial = $serial
                arguments = $logcatArguments
                stdout = [IO.Path]::GetFullPath($logcatPath)
                stderr = [IO.Path]::GetFullPath($logcatErrorPath)
            }
            foreach ($name in @($logcatValues.Keys)) {
                $state | Add-Member -NotePropertyName $name `
                    -NotePropertyValue $logcatValues[$name] -Force
            }
            Write-AtomicState -StatePath $statePath -State $state
            [void]$startedPids.Remove($logcatOwnership)
        }

        $packagePid = Invoke-PackageLaunchGate `
            -PackageName $package `
            -CompatibilityDiagnostics $compatibilityDiagnostics

        $result = [ordered]@{
            gatewayPid = $gatewayPid
            edgePid = $edgePid
            emulatorPid = $emulatorPid
            gatewayOwned = $gatewayOwned
            edgeOwned = $edgeOwned
            gatewayLog = $gatewayLog
            gatewayErrorLog = $gatewayErrorLog
            edgeLog = $edgeLog
            edgeErrorLog = $edgeErrorLog
            logcat = $logcatPath
            logcatPid = $logcatPid
            package = $package
            apk = $apk
            serial = $serial
            apkSha256 = $expectedApkSha256.ToLowerInvariant()
            sourceApk = $sourceApk
            sourceApkSha256 = if ($expectedSourceApkSha256) {
                $expectedSourceApkSha256.ToLowerInvariant()
            } else {
                $null
            }
            caFingerprint = [string]$ca.fingerprint
            caRemotePath = $caRemotePath
        }
        [Console]::Out.WriteLine(($result | ConvertTo-Json -Compress))
    } catch {
        $originalError = $_
        Write-Diagnostic ("launcher failed: " + $originalError.Exception.Message)
        try {
            Stop-OwnedProcesses -Records $startedPids.ToArray()
        } catch {
            Write-Diagnostic ("launcher cleanup failed: " + $_.Exception.Message)
        }
        throw $originalError
    }
    } finally {
        Exit-RepositoryLauncherMutex -Token $launcherMutexToken
    }
}


if ($MyInvocation.InvocationName -ne '.') {
    try {
        Invoke-Launcher
        exit 0
    } catch {
        Write-Diagnostic $_.Exception.Message
        exit 1
    }
}
