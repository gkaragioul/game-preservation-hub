[CmdletBinding()]
param([switch]$PlanOnly)

$ErrorActionPreference = 'Stop'
$windowsRuntime = Join-Path $PSScriptRoot 'windows_runtime.ps1'
. $windowsRuntime

try {
    $hostStatus = Get-WindowsHostStatus
    Assert-SupportedWindowsHost -Status $hostStatus
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}

$avd = 'SpiralWarrior_API30_X64'
$imagePackage = 'system-images;android-30;google_apis;x86_64'
$packages = @(
    'platform-tools',
    'emulator',
    'platforms;android-30',
    'build-tools;30.0.3',
    $imagePackage
)
$sdkRoot = Join-Path $env:LOCALAPPDATA 'SpiralWarrior\AndroidSdk'
$avdHome = Join-Path $env:LOCALAPPDATA 'SpiralWarrior\Avd'
$archiveUrl = 'https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip'
$plan = [ordered]@{
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
    hostCompatible = $true
    windowsSupported = $true
    avd = $avd
    sdkRoot = $sdkRoot
    avdHome = $avdHome
    packages = $packages
    commandLineTools = $archiveUrl
}

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
        'SpiralWarrior-native-' + [Guid]::NewGuid().ToString('N')
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
        $stdout = if (Test-Path $stdoutPath) {
            [IO.File]::ReadAllText($stdoutPath)
        } else { '' }
        $stderr = if (Test-Path $stderrPath) {
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
                throw "refusing to clean unexpected native capture path: $resolvedCapture"
            }
            Remove-Item -LiteralPath $resolvedCapture -Recurse -Force
        }
    }
}

function Invoke-ReadOnlyNativeProbe {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @()
    )
    $output = @()
    $exitCode = -1
    $previousErrorAction = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = @(
            & $FilePath @Arguments 2>&1 |
                ForEach-Object { [string]$_ }
        )
        $exitCode = $LASTEXITCODE
    } catch {
        $output = @($_.Exception.Message)
    } finally {
        $ErrorActionPreference = $previousErrorAction
    }
    return [pscustomobject]@{
        ExitCode = [int]$exitCode
        Output = ($output -join "`n").Trim()
    }
}


function Test-Java17ReadOnly {
    $candidates = New-Object System.Collections.Generic.List[string]
    if ($env:JAVA_HOME) {
        $candidates.Add((Join-Path $env:JAVA_HOME 'bin\java.exe'))
    }
    $pathJava = Get-Command java.exe -CommandType Application `
        -ErrorAction SilentlyContinue | Select-Object -First 1
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
        $probe = Invoke-ReadOnlyNativeProbe `
            -FilePath $candidate `
            -Arguments @('-version')
        if (($probe.ExitCode -eq 0) -and
            ($probe.Output -match 'version\s+"(?:1\.)?17(?:[._"]|$)')) {
            return $true
        }
    }
    return $false
}


function Get-BootstrapAndroidReadOnlyStatus {
    $adbPath = Join-Path $sdkRoot 'platform-tools\adb.exe'
    $emulatorPath = Join-Path $sdkRoot 'emulator\emulator.exe'
    $status = [ordered]@{
        adb = Test-Path -LiteralPath $adbPath -PathType Leaf
        emulator = Test-Path -LiteralPath $emulatorPath -PathType Leaf
        avd = $false
        acceleration = 'emulator missing'
        accelerationCompatible = $false
    }
    if (-not $status.emulator) {
        return [pscustomobject]$status
    }

    $avdProbe = Invoke-ReadOnlyNativeProbe `
        -FilePath $emulatorPath `
        -Arguments @('-list-avds')
    if ($avdProbe.ExitCode -eq 0) {
        $listedAvds = @(
            $avdProbe.Output -split "\r?\n" |
                ForEach-Object { $_.Trim() } |
                Where-Object { $_ }
        )
        $status.avd = $listedAvds -contains $avd
    }

    $accelerationProbe = Invoke-ReadOnlyNativeProbe `
        -FilePath $emulatorPath `
        -Arguments @('-accel-check')
    $status.acceleration = if ($accelerationProbe.Output) {
        $accelerationProbe.Output
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


function Add-BootstrapReadOnlyStatus {
    param([Parameter(Mandatory = $true)]$Target)

    $androidStatus = Get-BootstrapAndroidReadOnlyStatus
    $Target['java17'] = [bool](Test-Java17ReadOnly)
    $Target['curl'] = [bool](
        Get-Command curl.exe -CommandType Application `
            -ErrorAction SilentlyContinue
    )
    $Target['tar'] = [bool](
        Get-Command tar.exe -CommandType Application `
            -ErrorAction SilentlyContinue
    )
    $Target['winget'] = [bool](
        Get-Command winget.exe -CommandType Application `
            -ErrorAction SilentlyContinue
    )
    $Target['adb'] = [bool]$androidStatus.adb
    $Target['emulator'] = [bool]$androidStatus.emulator
    $Target['avdPresent'] = [bool]$androidStatus.avd
    $Target['acceleration'] = [string]$androidStatus.acceleration
    $Target['accelerationCompatible'] =
        [bool]$androidStatus.accelerationCompatible
}


function Get-JavaMajor {
    param([Parameter(Mandatory = $true)][string]$JavaPath)
    try {
        $result = Invoke-NativeChecked `
            -FilePath $JavaPath `
            -Arguments @('-version') `
            -Description "Java version check ($JavaPath)"
    } catch {
        Write-Diagnostic $_.Exception.Message
        return $null
    }
    $versionText = $result.StdOut + "`n" + $result.StdErr
    $match = [regex]::Match($versionText, 'version\s+"(?:1\.)?(?<major>\d+)')
    if (-not $match.Success) {
        Write-Diagnostic "Could not parse Java version from $JavaPath`: $versionText"
        return $null
    }
    return [int]$match.Groups['major'].Value
}

function Resolve-Java17 {
    $candidates = New-Object System.Collections.Generic.List[string]
    if ($env:JAVA_HOME) {
        $candidates.Add((Join-Path $env:JAVA_HOME 'bin\java.exe'))
    }
    $pathJava = Get-Command java.exe -ErrorAction SilentlyContinue
    if ($pathJava) {
        $candidates.Add($pathJava.Source)
    }
    $adoptiumRoot = Join-Path $env:ProgramFiles 'Eclipse Adoptium'
    if (Test-Path $adoptiumRoot) {
        Get-ChildItem -Path $adoptiumRoot -Directory -Filter 'jdk-17*' |
            Sort-Object Name -Descending |
            ForEach-Object {
                $candidates.Add((Join-Path $_.FullName 'bin\java.exe'))
            }
    }
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if ((Test-Path -LiteralPath $candidate) -and
            ((Get-JavaMajor -JavaPath $candidate) -eq 17)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    return $null
}

function Assert-AvdImage {
    param(
        [Parameter(Mandatory = $true)][string]$AvdHome,
        [Parameter(Mandatory = $true)][string]$AvdName,
        [Parameter(Mandatory = $true)][string]$ExpectedImage
    )
    $config = Join-Path $AvdHome "$AvdName.avd\config.ini"
    if (-not (Test-Path -LiteralPath $config)) {
        throw "AVD $AvdName is missing config: $config"
    }
    $line = Get-Content -LiteralPath $config |
        Where-Object { $_ -match '^image\.sysdir\.1\s*=' } |
        Select-Object -First 1
    if (-not $line) {
        throw "AVD config has no image.sysdir.1: $config"
    }
    $actual = (($line -split '=', 2)[1] -replace '\\', '/').TrimEnd('/').Trim()
    $expected = ($ExpectedImage -replace ';', '/').TrimEnd('/')
    if ($actual -ne $expected) {
        throw "AVD $AvdName uses '$actual', expected '$expected' (config: $config)"
    }
}

$sdkManager = Join-Path $sdkRoot 'cmdline-tools\latest\bin\sdkmanager.bat'

if ($PlanOnly) {
    Add-BootstrapReadOnlyStatus -Target $plan
    [Console]::Out.WriteLine(($plan | ConvertTo-Json -Compress))
    exit 0
}

$java17Available = Test-Java17ReadOnly
$wingetAvailable = [bool](
    Get-Command winget.exe -CommandType Application `
        -ErrorAction SilentlyContinue
)
if ((-not $java17Available) -and (-not $wingetAvailable)) {
    Write-Diagnostic 'Java 17 is unavailable and winget.exe was not found'
    exit 1
}
if (-not (Test-Path -LiteralPath $sdkManager -PathType Leaf)) {
    $curlAvailable = [bool](
        Get-Command curl.exe -CommandType Application `
            -ErrorAction SilentlyContinue
    )
    $tarAvailable = [bool](
        Get-Command tar.exe -CommandType Application `
            -ErrorAction SilentlyContinue
    )
    if (-not $curlAvailable) {
        Write-Diagnostic (
            'curl.exe is required before Android provisioning can mutate state'
        )
        exit 1
    }
    if (-not $tarAvailable) {
        Write-Diagnostic (
            'tar.exe is required before Android provisioning can mutate state'
        )
        exit 1
    }
}

$ownedTemp = $null
try {
    $java = Resolve-Java17
    if (-not $java) {
        $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
        if (-not $winget) {
            throw 'Java 17 is unavailable and winget.exe was not found'
        }
        Write-Diagnostic 'Installing Eclipse Temurin Java 17...'
        $install = Invoke-NativeChecked `
            -FilePath $winget.Source `
            -Arguments @(
                'install',
                '--id', 'EclipseAdoptium.Temurin.17.JDK',
                '--exact',
                '--silent',
                '--accept-package-agreements',
                '--accept-source-agreements'
            ) `
            -Description 'Temurin 17 installation'
        if ($install.StdOut.Trim()) { Write-Diagnostic $install.StdOut.Trim() }
        if ($install.StdErr.Trim()) { Write-Diagnostic $install.StdErr.Trim() }
        $java = Resolve-Java17
        if (-not $java) {
            throw 'Temurin installation completed but Java major version 17 is unavailable'
        }
    }
    if ((Get-JavaMajor -JavaPath $java) -ne 17) {
        throw "resolved Java is not major version 17: $java"
    }

    $javaHome = Split-Path (Split-Path $java -Parent) -Parent
    $env:JAVA_HOME = $javaHome
    $env:ANDROID_SDK_ROOT = $sdkRoot
    $env:ANDROID_AVD_HOME = $avdHome
    $env:Path = (
        (Join-Path $javaHome 'bin'),
        (Join-Path $sdkRoot 'platform-tools'),
        (Join-Path $sdkRoot 'emulator'),
        $env:Path
    ) -join ';'
    [void](New-Item -ItemType Directory -Path $sdkRoot -Force)
    [void](New-Item -ItemType Directory -Path $avdHome -Force)

    if (-not (Test-Path -LiteralPath $sdkManager)) {
        $ownedTemp = Join-Path ([IO.Path]::GetTempPath()) (
            'SpiralWarrior-bootstrap-' + [Guid]::NewGuid().ToString('N')
        )
        [void](New-Item -ItemType Directory -Path $ownedTemp)
        $archive = Join-Path $ownedTemp 'commandlinetools.zip'
        $extract = Join-Path $ownedTemp 'extracted'
        Write-Diagnostic "Downloading Android command-line tools from $archiveUrl..."
        $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
        if (-not $curl) {
            throw "curl.exe is required for the bounded Android tools download"
        }
        $download = Invoke-NativeChecked `
            -FilePath $curl.Source `
            -Arguments @(
                '--fail',
                '--location',
                '--silent',
                '--show-error',
                '--max-time', '600',
                '--output', $archive,
                $archiveUrl
            ) `
            -Description 'Android command-line tools download'
        if ($download.StdErr.Trim()) { Write-Diagnostic $download.StdErr.Trim() }
        if ((-not (Test-Path -LiteralPath $archive)) -or
            ((Get-Item -LiteralPath $archive).Length -le 0)) {
            throw "Android command-line tools download produced an empty archive"
        }
        [void](New-Item -ItemType Directory -Path $extract)
        $tar = Get-Command tar.exe -ErrorAction SilentlyContinue
        if (-not $tar) {
            throw "tar.exe is required for Android tools extraction"
        }
        $extraction = Invoke-NativeChecked `
            -FilePath $tar.Source `
            -Arguments @('-xf', $archive, '-C', $extract) `
            -Description 'Android command-line tools extraction'
        if ($extraction.StdErr.Trim()) { Write-Diagnostic $extraction.StdErr.Trim() }
        $extractedTools = Join-Path $extract 'cmdline-tools'
        $extractedManager = Join-Path $extractedTools 'bin\sdkmanager.bat'
        if (-not (Test-Path -LiteralPath $extractedManager)) {
            throw "command-line tools archive has unexpected layout: $extractedManager"
        }
        $toolsParent = Join-Path $sdkRoot 'cmdline-tools'
        [void](New-Item -ItemType Directory -Path $toolsParent -Force)
        $stageName = '.latest-' + [Guid]::NewGuid().ToString('N')
        $stage = Join-Path $toolsParent $stageName
        Move-Item -LiteralPath $extractedTools -Destination $stage
        if (Test-Path -LiteralPath (Join-Path $toolsParent 'latest')) {
            throw "Android command-line tools appeared concurrently at $sdkManager"
        }
        Rename-Item -LiteralPath $stage -NewName 'latest'
        if (-not (Test-Path -LiteralPath $sdkManager)) {
            throw "sdkmanager was not published at $sdkManager"
        }
    }

    Write-Diagnostic 'Accepting Android SDK licenses...'
    $yesLines = @()
    1..200 | ForEach-Object { $yesLines += 'y' }
    $licenses = Invoke-NativeChecked `
        -FilePath $sdkManager `
        -Arguments @("--sdk_root=$sdkRoot", '--licenses') `
        -InputLines $yesLines `
        -Description 'Android SDK license acceptance'
    if ($licenses.StdErr.Trim()) { Write-Diagnostic $licenses.StdErr.Trim() }

    Write-Diagnostic 'Installing required Android SDK packages...'
    $installPackages = Invoke-NativeChecked `
        -FilePath $sdkManager `
        -Arguments (@("--sdk_root=$sdkRoot") + $packages) `
        -Description 'Android SDK package installation'
    if ($installPackages.StdErr.Trim()) { Write-Diagnostic $installPackages.StdErr.Trim() }

    $emulator = Join-Path $sdkRoot 'emulator\emulator.exe'
    $avdManager = Join-Path $sdkRoot 'cmdline-tools\latest\bin\avdmanager.bat'
    if (-not (Test-Path -LiteralPath $emulator)) {
        throw "emulator.exe is missing after SDK installation: $emulator"
    }
    if (-not (Test-Path -LiteralPath $avdManager)) {
        throw "avdmanager.bat is missing after SDK installation: $avdManager"
    }
    $listed = Invoke-NativeChecked `
        -FilePath $emulator `
        -Arguments @('-list-avds') `
        -Description 'AVD listing'
    $avds = @($listed.StdOut -split "\r?\n" | Where-Object { $_.Trim() })
    if ($avds -notcontains $avd) {
        Write-Diagnostic "Creating AVD $avd..."
        $created = Invoke-NativeChecked `
            -FilePath $avdManager `
            -Arguments @(
                'create', 'avd',
                '--force',
                '--name', $avd,
                '--package', $imagePackage,
                '--device', 'pixel_3a'
            ) `
            -InputLines @('no') `
            -Description "AVD creation ($avd)"
        if ($created.StdErr.Trim()) { Write-Diagnostic $created.StdErr.Trim() }
        $listed = Invoke-NativeChecked `
            -FilePath $emulator `
            -Arguments @('-list-avds') `
            -Description 'post-create AVD listing'
        $avds = @($listed.StdOut -split "\r?\n" | Where-Object { $_.Trim() })
        if ($avds -notcontains $avd) {
            throw "emulator did not list newly created AVD $avd"
        }
    }
    Assert-AvdImage -AvdHome $avdHome -AvdName $avd -ExpectedImage $imagePackage

    Add-BootstrapReadOnlyStatus -Target $plan
    $plan['ready'] = $true
    [Console]::Out.WriteLine(($plan | ConvertTo-Json -Compress))
} catch {
    Write-Diagnostic $_.Exception.Message
    exit 1
} finally {
    if ($ownedTemp -and (Test-Path -LiteralPath $ownedTemp)) {
        $resolvedOwnedTemp = (Resolve-Path -LiteralPath $ownedTemp).Path
        $tempPrefix = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
        if (-not $resolvedOwnedTemp.StartsWith(
            $tempPrefix,
            [StringComparison]::OrdinalIgnoreCase
        )) {
            Write-Diagnostic "Refusing to clean unexpected bootstrap path: $resolvedOwnedTemp"
        } else {
            Remove-Item -LiteralPath $resolvedOwnedTemp -Recurse -Force
        }
    }
}
