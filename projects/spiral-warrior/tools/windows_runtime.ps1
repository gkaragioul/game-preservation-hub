function ConvertTo-SpiralWindowsArchitecture {
    param([AllowNull()]$Value)

    $text = ([string]$Value).Trim().ToLowerInvariant()
    switch -Regex ($text) {
        '^(?:amd64|x64|64-bit|64 bit)$' { return 'x64' }
        '^(?:x86|i386|i686|32-bit|32 bit)$' { return 'x86' }
        '^(?:arm64|aarch64)$' { return 'arm64' }
        '^arm$' { return 'arm' }
        '^$' { return 'unknown' }
        default { return $text }
    }
}


function Invoke-SpiralWindowsReadOnlyProbe {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @()
    )

    $output = @()
    $exitCode = -1
    $failure = $null
    $previousErrorAction = $ErrorActionPreference
    try {
        # Native stderr becomes an ErrorRecord under Windows PowerShell 5.1.
        # Merge and capture it so a read-only probe never leaks extra output.
        $ErrorActionPreference = 'Continue'
        $output = @(
            & $FilePath @Arguments 2>&1 |
                ForEach-Object { [string]$_ }
        )
        $exitCode = $LASTEXITCODE
    } catch {
        $failure = $_.Exception.Message
    } finally {
        $ErrorActionPreference = $previousErrorAction
    }

    return [pscustomobject]@{
        exitCode = [int]$exitCode
        output = ($output -join "`n").Trim()
        failure = $failure
    }
}


function Get-WindowsHostStatus {
    $isWindows = [Environment]::OSVersion.Platform -eq `
        [PlatformID]::Win32NT
    $platform = if ($isWindows) { 'windows' } else { 'unknown' }
    if (-not $isWindows) {
        try {
            if ([Runtime.InteropServices.RuntimeInformation]::IsOSPlatform(
                [Runtime.InteropServices.OSPlatform]::Linux
            )) {
                $platform = 'linux'
            } elseif (
                [Runtime.InteropServices.RuntimeInformation]::IsOSPlatform(
                    [Runtime.InteropServices.OSPlatform]::OSX
                )
            ) {
                $platform = 'macos'
            }
        } catch {
            # Older .NET hosts may not expose RuntimeInformation. "unknown"
            # remains safely unsupported.
        }
    }

    $windowsProductName = ''
    $windowsVersion = [Environment]::OSVersion.Version.ToString()
    $windowsBuild = [string][Environment]::OSVersion.Version.Build
    $osArchitecture = if ([Environment]::Is64BitOperatingSystem) {
        'x64'
    } else {
        'x86'
    }
    $virtualizationFirmwareEnabled = $false

    if ($isWindows) {
        try {
            $operatingSystem = Get-CimInstance -ClassName Win32_OperatingSystem `
                -ErrorAction Stop | Select-Object -First 1
            if ($operatingSystem) {
                $windowsProductName = (
                    [string]$operatingSystem.Caption -replace
                    '^Microsoft\s+',
                    ''
                )
                $windowsVersion = [string]$operatingSystem.Version
                $windowsBuild = [string]$operatingSystem.BuildNumber
                $osArchitecture = ConvertTo-SpiralWindowsArchitecture `
                    $operatingSystem.OSArchitecture
            }
        } catch {
            try {
                $currentVersion = Get-ItemProperty -LiteralPath (
                    'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
                ) -ErrorAction Stop
                $windowsProductName = [string]$currentVersion.ProductName
                if ($currentVersion.CurrentBuildNumber) {
                    $windowsBuild = [string]$currentVersion.CurrentBuildNumber
                }
                if ($currentVersion.CurrentVersion) {
                    $windowsVersion = [string]$currentVersion.CurrentVersion
                }
            } catch {
                # Empty or fallback facts make the host fail closed.
            }
        }

        try {
            $processorStatuses = @(
                Get-CimInstance -ClassName Win32_Processor -ErrorAction Stop |
                    ForEach-Object {
                        [bool]$_.VirtualizationFirmwareEnabled
                    }
            )
            $virtualizationFirmwareEnabled = [bool](
                ($processorStatuses.Count -gt 0) -and
                ($processorStatuses -notcontains $false)
            )
        } catch {
            $virtualizationFirmwareEnabled = $false
        }
    }

    $processArchitecture = if ([Environment]::Is64BitProcess) {
        'x64'
    } else {
        'x86'
    }
    $powershellEdition = if ($PSVersionTable.PSEdition) {
        [string]$PSVersionTable.PSEdition
    } else {
        'Desktop'
    }
    $powershellVersion = (
        '{0}.{1}' -f
        $PSVersionTable.PSVersion.Major,
        $PSVersionTable.PSVersion.Minor
    )
    $wslDetected = [bool](
        $env:WSL_DISTRO_NAME -or
        $env:WSL_INTEROP
    )

    return [pscustomobject][ordered]@{
        platform = $platform
        windowsProductName = $windowsProductName
        windowsVersion = $windowsVersion
        windowsBuild = $windowsBuild
        osArchitecture = $osArchitecture
        processArchitecture = $processArchitecture
        powershellEdition = $powershellEdition
        powershellVersion = $powershellVersion
        wslDetected = $wslDetected
        virtualizationFirmwareEnabled = $virtualizationFirmwareEnabled
    }
}


function Get-UnsupportedWindowsHostFields {
    param([Parameter(Mandatory = $true)]$Status)

    $mismatches = New-Object System.Collections.Generic.List[string]
    if ([string]$Status.platform -cne 'windows') {
        $mismatches.Add(
            "platform (expected 'windows', got '$([string]$Status.platform)')"
        )
    }
    if ([string]$Status.windowsProductName -notmatch '^Windows 11(?:\s|$)') {
        $mismatches.Add(
            'windowsProductName (expected Windows 11, got ' +
            "'$([string]$Status.windowsProductName)')"
        )
    }
    if ((ConvertTo-SpiralWindowsArchitecture $Status.osArchitecture) -cne
        'x64') {
        $mismatches.Add(
            "osArchitecture (expected 'x64', got " +
            "'$([string]$Status.osArchitecture)')"
        )
    }
    if ((ConvertTo-SpiralWindowsArchitecture $Status.processArchitecture) -cne
        'x64') {
        $mismatches.Add(
            "processArchitecture (expected 'x64', got " +
            "'$([string]$Status.processArchitecture)')"
        )
    }
    if ([string]$Status.powershellEdition -cne 'Desktop') {
        $mismatches.Add(
            "powershellEdition (expected 'Desktop', got " +
            "'$([string]$Status.powershellEdition)')"
        )
    }
    if ([string]$Status.powershellVersion -notmatch '^5\.1(?:\.|$)') {
        $mismatches.Add(
            "powershellVersion (expected 5.1, got " +
            "'$([string]$Status.powershellVersion)')"
        )
    }
    if ([bool]$Status.wslDetected) {
        $mismatches.Add('wslDetected (expected false, got true)')
    }
    if (-not [bool]$Status.virtualizationFirmwareEnabled) {
        $mismatches.Add(
            'virtualizationFirmwareEnabled (expected true, got false)'
        )
    }
    return @($mismatches)
}


function Test-SupportedWindowsHost {
    param([Parameter(Mandatory = $true)]$Status)

    return @(
        Get-UnsupportedWindowsHostFields -Status $Status
    ).Count -eq 0
}


function Assert-SupportedWindowsHost {
    param([Parameter(Mandatory = $true)]$Status)

    $mismatches = @(
        Get-UnsupportedWindowsHostFields -Status $Status
    )
    if ($mismatches.Count -gt 0) {
        throw (
            'Unsupported Windows runtime: ' +
            ($mismatches -join '; ') +
            '. Use Windows 11 x64 with 64-bit Windows PowerShell 5.1, ' +
            'firmware virtualization enabled, and no WSL host.'
        )
    }
}


function Get-PythonRuntimeStatus {
    param([Parameter(Mandatory = $true)][string]$PythonPath)

    $status = [ordered]@{
        exists = $false
        compatible = $false
        path = $PythonPath
        implementation = $null
        version = $null
        architecture = $null
        zlibCompileVersion = $null
        zlibRuntimeVersion = $null
    }
    if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
        return [pscustomobject]$status
    }

    $status.exists = $true
    try {
        $status.path = (Resolve-Path -LiteralPath $PythonPath `
            -ErrorAction Stop).Path
    } catch {
        return [pscustomobject]$status
    }

    # Single quotes survive Windows PowerShell 5.1's native-command argument
    # serialization; embedded double quotes would be consumed by cmdline
    # parsing before CPython receives the -c argument.
    $probeCode = (
        "import json,platform,struct,sys,zlib;" +
        "print(json.dumps({" +
        "'implementation':sys.implementation.name," +
        "'version':platform.python_version()," +
        "'pointerBits':struct.calcsize('P')*8," +
        "'zlibCompileVersion':zlib.ZLIB_VERSION," +
        "'zlibRuntimeVersion':zlib.ZLIB_RUNTIME_VERSION" +
        "},separators=(',',':')))"
    )
    $probe = Invoke-SpiralWindowsReadOnlyProbe `
        -FilePath $status.path `
        -Arguments @('-I', '-S', '-c', $probeCode)
    if ($probe.exitCode -ne 0) {
        return [pscustomobject]$status
    }

    $facts = $null
    foreach ($line in @($probe.output -split "\r?\n")) {
        if (-not $line.Trim().StartsWith('{')) {
            continue
        }
        try {
            $facts = $line | ConvertFrom-Json -ErrorAction Stop
            break
        } catch {
            $facts = $null
        }
    }
    if (-not $facts) {
        return [pscustomobject]$status
    }

    $status.implementation = [string]$facts.implementation
    $status.version = [string]$facts.version
    $status.architecture = if ([int]$facts.pointerBits -eq 64) {
        'x64'
    } elseif ([int]$facts.pointerBits -eq 32) {
        'x86'
    } else {
        'unknown'
    }
    $status.zlibCompileVersion = [string]$facts.zlibCompileVersion
    $status.zlibRuntimeVersion = [string]$facts.zlibRuntimeVersion

    $parsedVersion = $null
    try {
        $parsedVersion = [version]$status.version
    } catch {
        $parsedVersion = $null
    }
    $status.compatible = [bool](
        ($status.implementation -ceq 'cpython') -and
        ($null -ne $parsedVersion) -and
        ($parsedVersion -ge [version]'3.12.0') -and
        ($parsedVersion -lt [version]'3.13.0') -and
        ($status.architecture -ceq 'x64') -and
        ($status.zlibCompileVersion -ceq '1.3.1') -and
        ($status.zlibRuntimeVersion -ceq '1.3.1')
    )
    return [pscustomobject]$status
}


function Get-OpenSslRuntimeStatus {
    $status = [ordered]@{
        available = $false
        path = $null
        version = $null
    }
    $candidates = New-Object System.Collections.Generic.List[string]
    if ($env:SPIRAL_OPENSSL) {
        $candidates.Add([string]$env:SPIRAL_OPENSSL)
    }
    $pathOpenSsl = Get-Command -Name openssl.exe -CommandType Application `
        -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pathOpenSsl) {
        $candidates.Add([string]$pathOpenSsl.Source)
    }
    if ($env:ProgramFiles) {
        $candidates.Add(
            (Join-Path $env:ProgramFiles 'Git\usr\bin\openssl.exe')
        )
        $candidates.Add(
            (Join-Path $env:ProgramFiles 'Git\mingw64\bin\openssl.exe')
        )
    }

    $visited = @{}
    foreach ($candidate in $candidates) {
        if (-not $candidate) {
            continue
        }
        try {
            $resolved = (Resolve-Path -LiteralPath $candidate `
                -ErrorAction Stop).Path
        } catch {
            continue
        }
        if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
            continue
        }
        $key = $resolved.ToLowerInvariant()
        if ($visited.ContainsKey($key)) {
            continue
        }
        $visited[$key] = $true

        $probe = Invoke-SpiralWindowsReadOnlyProbe `
            -FilePath $resolved `
            -Arguments @('version')
        if (($probe.exitCode -ne 0) -or (-not $probe.output)) {
            continue
        }
        $status.available = $true
        $status.path = $resolved
        $status.version = ($probe.output -split "\r?\n")[0].Trim()
        break
    }
    return [pscustomobject]$status
}


function Get-SpiralWindowsFileSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    $stream = $null
    $algorithm = $null
    try {
        $stream = [IO.File]::Open(
            $Path,
            [IO.FileMode]::Open,
            [IO.FileAccess]::Read,
            [IO.FileShare]::Read
        )
        $algorithm = [Security.Cryptography.SHA256]::Create()
        return (
            [BitConverter]::ToString($algorithm.ComputeHash($stream)).
                Replace('-', '')
        )
    } catch {
        return $null
    } finally {
        if ($algorithm) {
            $algorithm.Dispose()
        }
        if ($stream) {
            $stream.Dispose()
        }
    }
}


function Get-ArtifactRouteStatus {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet('cn', 'en')]
        [string]$Edition,
        [Parameter(Mandatory = $true)]
        [string]$Root
    )

    if (-not [IO.Path]::IsPathRooted($Root)) {
        throw "artifact root must be absolute: $Root"
    }
    $normalizedRoot = [IO.Path]::GetFullPath($Root)
    $signerPath = Join-Path $normalizedRoot 'build\debug.keystore'
    # The rebuild route starts at the immutable published archive. A locally
    # rebuilt intermediate previously supplied a corrupted data/PartSuit table.
    $sourceApkPath = Join-Path $normalizedRoot 'cn_9game.apk'
    $apkPath = if ($Edition -ceq 'cn') {
        Join-Path $normalizedRoot (
            'patched\LuoXuanWarrior_cn_partsuit_userca_debug.apk'
        )
    } else {
        Join-Path $normalizedRoot 'patched\SpiralWarrior_fullres_debug.apk'
    }

    $sourceApkPresent = [bool](
        ($Edition -ceq 'cn') -and
        (Test-Path -LiteralPath $sourceApkPath -PathType Leaf)
    )
    $apkPresent = Test-Path -LiteralPath $apkPath -PathType Leaf
    $signerPresent = Test-Path -LiteralPath $signerPath -PathType Leaf
    $sourceApkSha256 = if ($sourceApkPresent) {
        Get-SpiralWindowsFileSha256 -Path $sourceApkPath
    } else {
        $null
    }
    $apkSha256 = if ($apkPresent) {
        Get-SpiralWindowsFileSha256 -Path $apkPath
    } else {
        $null
    }
    $signerSha256 = if ($signerPresent) {
        Get-SpiralWindowsFileSha256 -Path $signerPath
    } else {
        $null
    }

    $expectedApkSha256 = if ($Edition -ceq 'cn') {
        '341795584ABCBD0997F1E396F56C3DE7E90FF889768866EAC4F04FE442415414'
    } else {
        '9C8769E51B535A7F909C935B38C2B2A4F27E4B44C711DBF8410011BF736888AD'
    }
    $artifactRoute = 'missing'
    $artifactReady = $false
    if ($apkSha256 -ceq $expectedApkSha256) {
        $artifactRoute = 'runtime-apk'
        $artifactReady = $true
    } elseif (
        ($Edition -ceq 'cn') -and
        ($sourceApkSha256 -ceq
            '4E02FBC9ADF4E31051140194B55B8004C1272C74D76293208D6B1809C77358D5') -and
        ($signerSha256 -ceq
            '7AE2671C9D4B3A35D1197CD7CA4C417ACC2398A39DA2E59E25B7DF65098C266B')
    ) {
        $artifactRoute = 'rebuild-inputs'
        $artifactReady = $true
    }

    return [pscustomobject][ordered]@{
        artifactRoute = $artifactRoute
        artifactReady = [bool]$artifactReady
        sourceApkPresent = [bool]$sourceApkPresent
        apkPresent = [bool]$apkPresent
        signerPresent = [bool]$signerPresent
        sourceApkPath = if ($Edition -ceq 'cn') {
            $sourceApkPath
        } else {
            $null
        }
        apkPath = $apkPath
        signerPath = $signerPath
        sourceApkSha256 = $sourceApkSha256
        apkSha256 = $apkSha256
        signerSha256 = $signerSha256
    }
}
