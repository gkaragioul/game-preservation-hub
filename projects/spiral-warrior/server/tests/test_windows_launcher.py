import json
import hashlib
import os
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = ROOT / "tools" / "bootstrap_android.ps1"
LAUNCHER = ROOT / "dist" / "launcher.ps1"
WINDOWS_RUNTIME = ROOT / "tools" / "windows_runtime.ps1"
CN_BUILDER = ROOT / "tools" / "build_cn_userca_apk.py"
POWERSHELL = "powershell.exe"
CN_SOURCE_SHA256 = "4e02fbc9adf4e31051140194b55b8004c1272c74d76293208d6b1809c77358d5"
CN_DERIVED_SHA256 = "341795584abcbd0997f1e396f56c3de7e90ff889768866eac4f04fe442415414"
UNSUPPORTED_HOST_CASES = (
    "windows10",
    "windows11-arm64",
    "windows11-32bit-process",
    "powershell7",
    "wsl",
    "linux",
    "macos",
    "virtualization-disabled",
)
RESTART_MISMATCH_FIELDS = (
    "processId",
    "executablePath",
    "normalizedCommandLine",
    "creationDate",
    "creationFileTimeUtc",
    "role",
    "port",
    "healthPath",
    "expectedHealthBody",
    "launchFilePath",
    "arguments",
    "workingDirectory",
)
NEW_TESTS = (
    "test_windows_host_status_accepts_windows11_x64_powershell51",
    "test_windows_host_status_rejects_each_unsupported_runtime",
    "test_bootstrap_plan_reports_the_windows_only_host_contract",
    "test_launcher_doctor_reports_complete_read_only_preflight",
    "test_launcher_doctor_missing_prerequisites_mutates_nothing",
    "test_normal_launch_preflight_fails_before_any_android_mutation",
    "test_restart_gateway_preflight_does_not_require_artifact_or_openssl",
    "test_service_state_schema1_migrates_logcat_without_adopting_services",
    "test_schema1_logcat_migration_allows_missing_creation_file_time",
    "test_service_state_matching_schema2_reuse_returns_retained_log_paths",
    "test_service_state_healthy_unrecorded_reuse_is_unowned_without_paths",
    "test_service_state_stale_schema2_role_is_cleared_on_healthy_reuse",
    "test_service_state_serializes_nested_records_at_depth_eight",
    "test_stateful_launcher_modes_share_one_repo_scoped_mutex",
    "test_concurrent_stateful_invocations_preserve_records_and_children",
    "test_service_stop_requires_creation_file_time",
    "test_restart_gateway_refuses_mismatched_owned_service",
    "test_restart_gateway_revalidates_identity_at_signal_boundary",
    "test_restart_gateway_observes_unowned_edge_identity_without_adoption",
    "test_restart_gateway_edge_identity_change_emits_no_retained_pid",
    "test_restart_gateway_replaces_only_gateway_and_preserves_state",
    "test_restart_gateway_start_failure_leaves_gateway_unowned",
    "test_corrupt_service_state_never_authorizes_termination",
    "test_restart_gateway_stdout_is_one_json_document",
)


def run_powershell_file(script: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            *arguments,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )


def powershell_json(script: Path, *arguments: str) -> dict:
    completed = run_powershell_file(script, *arguments)
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    assert len(completed.stdout.splitlines()) == 1
    encoded = completed.stdout.strip()
    assert encoded.startswith("{") and encoded.endswith("}")
    assert "\n" not in encoded and "\r" not in encoded
    return json.loads(encoded)


def run_powershell_command(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )


def ps_quote(value: Path | str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def files_are_identical(first: Path, second: Path) -> bool:
    if first.stat().st_size != second.stat().st_size:
        return False
    with first.open("rb") as left, second.open("rb") as right:
        while left_chunk := left.read(1024 * 1024):
            if left_chunk != right.read(len(left_chunk)):
                return False
        return right.read(1) == b""


def _supported_host_status() -> dict:
    return {
        "platform": "windows",
        "windowsProductName": "Windows 11 Pro",
        "windowsVersion": "10.0.26200",
        "windowsBuild": "26200",
        "osArchitecture": "x64",
        "processArchitecture": "x64",
        "powershellEdition": "Desktop",
        "powershellVersion": "5.1",
        "wslDetected": False,
        "virtualizationFirmwareEnabled": True,
    }


def _run_powershell_script(
    command: str,
    *,
    env: dict[str, str] | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env,
    )


def test_windows_host_status_accepts_windows11_x64_powershell51():
    fixture = json.dumps(_supported_host_status(), separators=(",", ":"))
    completed = run_powershell_command(
        "$ErrorActionPreference = 'Stop'; "
        f". {ps_quote(WINDOWS_RUNTIME)}; "
        f"$status = {ps_quote(fixture)} | ConvertFrom-Json; "
        "if (-not (Test-SupportedWindowsHost -Status $status)) { exit 81 }; "
        "Assert-SupportedWindowsHost -Status $status; "
        "$status | ConvertTo-Json -Compress"
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == _supported_host_status()


@pytest.mark.parametrize("unsupported_case", UNSUPPORTED_HOST_CASES)
def test_windows_host_status_rejects_each_unsupported_runtime(
    unsupported_case: str,
):
    status = _supported_host_status()
    mismatched_field = {
        "windows10": "windowsProductName",
        "windows11-arm64": "osArchitecture",
        "windows11-32bit-process": "processArchitecture",
        "powershell7": "powershellEdition",
        "wsl": "wslDetected",
        "linux": "platform",
        "macos": "platform",
        "virtualization-disabled": "virtualizationFirmwareEnabled",
    }[unsupported_case]
    if unsupported_case == "windows10":
        status["windowsProductName"] = "Windows 10 Pro"
        status["windowsBuild"] = "19045"
    elif unsupported_case == "windows11-arm64":
        status["osArchitecture"] = "arm64"
    elif unsupported_case == "windows11-32bit-process":
        status["processArchitecture"] = "x86"
    elif unsupported_case == "powershell7":
        status["powershellEdition"] = "Core"
        status["powershellVersion"] = "7.5"
    elif unsupported_case == "wsl":
        status["wslDetected"] = True
    elif unsupported_case == "linux":
        status["platform"] = "linux"
    elif unsupported_case == "macos":
        status["platform"] = "macos"
    else:
        status["virtualizationFirmwareEnabled"] = False
    fixture = json.dumps(status, separators=(",", ":"))
    completed = run_powershell_command(
        "$ErrorActionPreference = 'Stop'; "
        f". {ps_quote(WINDOWS_RUNTIME)}; "
        f"$status = {ps_quote(fixture)} | ConvertFrom-Json; "
        "if (Test-SupportedWindowsHost -Status $status) { exit 82 }; "
        "try { Assert-SupportedWindowsHost -Status $status; exit 83 } "
        "catch { [Console]::Error.WriteLine($_.Exception.Message); exit 0 }"
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""
    assert mismatched_field.lower() in completed.stderr.lower()


def test_bootstrap_plan_reports_the_windows_only_host_contract(tmp_path: Path):
    isolated_localappdata = tmp_path / "LocalAppData"
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(isolated_localappdata)
    completed = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(BOOTSTRAP),
            "-PlanOnly",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        env=env,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    assert len(completed.stdout.splitlines()) == 1
    plan = json.loads(completed.stdout)
    assert plan["platform"] == "windows"
    assert plan["windowsProductName"].startswith("Windows 11")
    assert plan["osArchitecture"] == "x64"
    assert plan["processArchitecture"] == "x64"
    assert plan["powershellEdition"] == "Desktop"
    assert plan["powershellVersion"] == "5.1"
    assert plan["wslDetected"] is False
    assert plan["virtualizationFirmwareEnabled"] is True
    assert plan["hostCompatible"] is True
    for field in ("java17", "curl", "tar", "winget"):
        assert isinstance(plan[field], bool)
    assert not isolated_localappdata.exists()


def test_launcher_doctor_reports_complete_read_only_preflight():
    before_state = (
        (ROOT / "research" / "runtime" / "launcher-state.json").read_bytes()
        if (ROOT / "research" / "runtime" / "launcher-state.json").exists()
        else None
    )
    completed = run_powershell_file(LAUNCHER, "-Doctor", "-Edition", "cn")
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    assert len(completed.stdout.splitlines()) == 1
    doctor = json.loads(completed.stdout)
    required = {
        "platform",
        "windowsProductName",
        "windowsVersion",
        "windowsBuild",
        "osArchitecture",
        "processArchitecture",
        "powershellEdition",
        "powershellVersion",
        "wslDetected",
        "virtualizationFirmwareEnabled",
        "hostCompatible",
        "python",
        "pythonCompatible",
        "pythonVersion",
        "pythonArchitecture",
        "zlibCompileVersion",
        "zlibRuntimeVersion",
        "openssl",
        "opensslPath",
        "opensslVersion",
        "artifactRoute",
        "artifactReady",
        "sourceApkPresent",
        "apkPresent",
        "signerPresent",
        "java17",
        "curl",
        "tar",
        "winget",
        "adb",
        "emulator",
        "avd",
        "acceleration",
        "accelerationCompatible",
        "preflightReady",
        "androidReady",
        "launchReady",
    }
    assert required <= doctor.keys()
    assert doctor["hostCompatible"] is True
    assert doctor["preflightReady"] == (
        doctor["hostCompatible"]
        and doctor["pythonCompatible"]
        and doctor["artifactReady"]
        and doctor["openssl"]
    )
    assert doctor["launchReady"] == (
        doctor["preflightReady"] and doctor["androidReady"]
    )
    state_path = ROOT / "research" / "runtime" / "launcher-state.json"
    after_state = state_path.read_bytes() if state_path.exists() else None
    assert after_state == before_state


def test_launcher_doctor_missing_prerequisites_mutates_nothing(tmp_path: Path):
    missing_root = tmp_path / "missing-repository"
    command = (
        f". {ps_quote(LAUNCHER)}; "
        f"$root = {ps_quote(missing_root)}; "
        "$python = Join-Path $root 'server\\.venv_win\\Scripts\\python.exe'; "
        "$sdkRoot = Join-Path $root 'AndroidSdk'; "
        "$avdHome = Join-Path $root 'Avd'; "
        "$adb = Join-Path $sdkRoot 'platform-tools\\adb.exe'; "
        "$emulator = Join-Path $sdkRoot 'emulator\\emulator.exe'; "
        "$sourceApk = Join-Path $root 'patched\\source.apk'; "
        "$apk = Join-Path $root 'patched\\runtime.apk'; "
        "$runtimeDir = Join-Path $root 'research\\runtime'; "
        "$statePath = Join-Path $runtimeDir 'launcher-state.json'; "
        "(Get-DoctorResult) | ConvertTo-Json -Depth 8 -Compress"
    )
    completed = run_powershell_command(command)
    assert completed.returncode == 0, completed.stderr
    assert len(completed.stdout.splitlines()) == 1
    doctor = json.loads(completed.stdout)
    assert doctor["pythonCompatible"] is False
    assert doctor["artifactReady"] is False
    assert doctor["androidReady"] is False
    assert doctor["launchReady"] is False
    assert not missing_root.exists()


def test_normal_launch_preflight_fails_before_any_android_mutation(
    tmp_path: Path,
):
    accepted = json.dumps(_supported_host_status(), separators=(",", ":"))
    for mode in ("Normal", "Capture"):
        for failure in ("python", "artifact", "openssl"):
            repository = tmp_path / f"{mode}-{failure}"
            repository.mkdir()
            command = (
                f". {ps_quote(LAUNCHER)}; "
                f"$root = {ps_quote(repository)}; "
                "$Doctor=$false; $RestartGateway=$false; $SkipInstall=$false; "
                f"$Capture=${str(mode == 'Capture').lower()}; "
                "$script:counters = [ordered]@{ "
                "mutex=0; bootstrap=0; android=0; stateRead=0; "
                "stateWrite=0; listener=0; childStart=0; childStop=0; "
                "modeOperation=0 }; "
                f"$script:hostStatus = {ps_quote(accepted)} | ConvertFrom-Json; "
                "$script:pythonStatus = [pscustomobject]@{ compatible=$true }; "
                "$script:artifactStatus = "
                "[pscustomobject]@{ artifactReady=$true }; "
                "$script:opensslStatus = [pscustomobject]@{ available=$true }; "
                + (
                    "$script:pythonStatus.compatible = $false; "
                    if failure == "python"
                    else "$script:artifactStatus.artifactReady = $false; "
                    if failure == "artifact"
                    else "$script:opensslStatus.available = $false; "
                )
                + "function Get-WindowsHostStatus { return $script:hostStatus }; "
                "function Get-PythonRuntimeStatus { "
                "return $script:pythonStatus }; "
                "function Get-ArtifactRouteStatus { "
                "return $script:artifactStatus }; "
                "function Get-OpenSslRuntimeStatus { "
                "return $script:opensslStatus }; "
                "function Enter-RepositoryLauncherMutex { "
                "$script:counters.mutex++; throw 'mutex must not run' }; "
                "function Invoke-BootstrapAndRequireReady { "
                "$script:counters.bootstrap++ }; "
                "function Test-AndroidToolchain { "
                "$script:counters.android++; return $true }; "
                "function Read-LauncherState { $script:counters.stateRead++ }; "
                "function Write-AtomicState { $script:counters.stateWrite++ }; "
                "function Get-TcpListenerOwner { "
                "$script:counters.listener++ }; "
                "function Start-OwnedPersistentProcess { "
                "$script:counters.childStart++ }; "
                "function Stop-OwnedProcesses { $script:counters.childStop++ }; "
                "$hooks = @{ ModeOperation={ param($observedMode,$context) "
                "$script:counters.modeOperation++; "
                "return [ordered]@{ mode=$observedMode } } }; "
                "try { Invoke-Launcher -TestHooks $hooks; exit 84 } "
                "catch { "
                f"if ($_.Exception.Message -notmatch {ps_quote(failure)}) "
                "{ exit 85 }; "
                "$script:counters | ConvertTo-Json -Compress; exit 0 }"
            )
            completed = run_powershell_command(command)
            assert completed.returncode == 0, completed.stderr
            assert json.loads(completed.stdout) == {
                "mutex": 0,
                "bootstrap": 0,
                "android": 0,
                "stateRead": 0,
                "stateWrite": 0,
                "listener": 0,
                "childStart": 0,
                "childStop": 0,
                "modeOperation": 0,
            }


def test_restart_gateway_preflight_does_not_require_artifact_or_openssl(
    tmp_path: Path,
):
    accepted = json.dumps(_supported_host_status(), separators=(",", ":"))
    repository = tmp_path / "restart-repository"
    repository.mkdir()
    command = (
        f". {ps_quote(LAUNCHER)}; "
        f"$root = {ps_quote(repository)}; "
        "$Doctor=$false; $Capture=$false; $SkipInstall=$false; "
        "$RestartGateway=$true; "
        "$script:forbidden=[ordered]@{ artifact=0; openssl=0; android=0 }; "
        f"$script:hostStatus = {ps_quote(accepted)} | ConvertFrom-Json; "
        "$script:pythonStatus = [pscustomobject]@{ compatible=$true }; "
        "function Get-WindowsHostStatus { return $script:hostStatus }; "
        "function Get-PythonRuntimeStatus { return $script:pythonStatus }; "
        "function Get-ArtifactRouteStatus { "
        "$script:forbidden.artifact++; throw 'artifact consulted' }; "
        "function Get-OpenSslRuntimeStatus { "
        "$script:forbidden.openssl++; throw 'openssl consulted' }; "
        "function Test-AndroidToolchain { "
        "$script:forbidden.android++; throw 'android consulted' }; "
        "$hooks = @{ ModeOperation={ param($observedMode,$context) "
        "return [ordered]@{ ready=$true; mode=$observedMode; "
        "repositoryRoot=[string]$context.RepositoryRoot } } }; "
        "Invoke-Launcher -TestHooks $hooks; "
        "[Console]::Out.WriteLine(($script:forbidden | ConvertTo-Json -Compress))"
    )
    completed = run_powershell_command(command)
    assert completed.returncode == 0, completed.stderr
    lines = completed.stdout.splitlines()
    assert len(lines) == 2
    result = json.loads(lines[0])
    assert result == {
        "ready": True,
        "mode": "RestartGateway",
        "repositoryRoot": str(repository),
    }
    assert json.loads(lines[1]) == {
        "artifact": 0,
        "openssl": 0,
        "android": 0,
    }


def test_bootstrap_plan_has_pinned_api_and_avd():
    plan = powershell_json(BOOTSTRAP, "-PlanOnly")
    assert plan["avd"] == "SpiralWarrior_API30_X64"
    assert plan["packages"] == [
        "platform-tools",
        "emulator",
        "platforms;android-30",
        "build-tools;30.0.3",
        "system-images;android-30;google_apis;x86_64",
    ]
    assert plan["commandLineTools"] == (
        "https://dl.google.com/android/repository/"
        "commandlinetools-win-11076708_latest.zip"
    )
    assert plan["sdkRoot"].endswith(r"SpiralWarrior\AndroidSdk")
    assert "ready" not in plan


def test_bootstrap_download_is_bounded_and_native_checked():
    source = BOOTSTRAP.read_text(encoding="utf-8")
    assert "Invoke-WebRequest" not in source
    assert "Expand-Archive" not in source
    assert "curl.exe" in source
    assert "tar.exe" in source
    assert "'--max-time'" in source
    assert "Invoke-NativeChecked" in source


@pytest.mark.preservation_artifact
def test_cn_builder_rejects_wrong_source_without_touching_existing_output(
    tmp_path: Path,
):
    bad_source = tmp_path / "wrong.apk"
    bad_source.write_bytes(b"not the authoritative CN artifact")
    output = tmp_path / "existing.apk"
    sentinel = b"previously-valid-output-sentinel"
    output.write_bytes(sentinel)
    completed = subprocess.run(
        [
            sys.executable,
            str(CN_BUILDER),
            "--source",
            str(bad_source),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode != 0
    assert completed.stdout == ""
    assert "source" in completed.stderr.lower()
    assert "sha-256" in completed.stderr.lower()
    assert output.read_bytes() == sentinel


@pytest.mark.preservation_artifact
def test_cn_builder_two_clean_builds_are_identical_and_preserve_source(
    tmp_path: Path,
):
    source = ROOT / "cn_9game.apk"
    before = file_sha256(source)
    assert before == CN_SOURCE_SHA256
    outputs = [tmp_path / "derived-a.apk", tmp_path / "derived-b.apk"]
    results = []
    for output in outputs:
        completed = subprocess.run(
            [
                sys.executable,
                str(CN_BUILDER),
                "--source",
                str(source),
                "--output",
                str(output),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=180,
        )
        assert completed.returncode == 0, completed.stderr
        assert len(completed.stdout.splitlines()) == 1
        results.append(json.loads(completed.stdout))
        assert file_sha256(output) == CN_DERIVED_SHA256
    assert files_are_identical(outputs[0], outputs[1])
    assert file_sha256(source) == before
    for result in results:
        assert result["ready"] is True
        assert result["sourceSha256"] == CN_SOURCE_SHA256
        assert result["outputSha256"] == CN_DERIVED_SHA256
        assert result["compiledMemberSha256"] == (
            "be19b1947c55c92325d53643a5a4aaed"
            "16f4b241dd7a7c9a522d25287107cec4"
        )
        assert result["package"] == "com.dianhun.lxys.aligames"


@pytest.mark.preservation_artifact
def test_cn_builder_reuses_exact_output_without_source_or_keystore(tmp_path: Path):
    output = tmp_path / "exact-derived.apk"
    initial = subprocess.run(
        [
            sys.executable,
            str(CN_BUILDER),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=180,
    )
    assert initial.returncode == 0, initial.stderr
    before_hash = file_sha256(output)
    before_mtime = output.stat().st_mtime_ns

    reused = subprocess.run(
        [
            sys.executable,
            str(CN_BUILDER),
            "--source",
            str(tmp_path / "absent-source.apk"),
            "--keystore",
            str(tmp_path / "absent-debug.keystore"),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert reused.returncode == 0, reused.stderr
    assert len(reused.stdout.splitlines()) == 1
    result = json.loads(reused.stdout)
    assert result["ready"] is True
    assert result["outputSha256"] == CN_DERIVED_SHA256
    assert file_sha256(output) == before_hash == CN_DERIVED_SHA256
    assert output.stat().st_mtime_ns == before_mtime


def test_launcher_never_uses_writable_system_or_overlay_ca_path():
    source = LAUNCHER.read_text(encoding="utf-8")
    assert "-writable-system" not in source
    assert "/system/etc/security/cacerts" not in source
    assert "adb remount" not in source
    assert "Test-RemountRequiresReboot" not in source
    assert "/data/misc/user/0/cacerts-added" in source
    assert "u:object_r:misc_user_data_file:s0" in source


def test_launcher_disables_snapshot_load_and_save_for_every_boot():
    source = LAUNCHER.read_text(encoding="utf-8")
    assert "'-no-snapshot'" in source
    assert "-no-snapshot-load" not in source


def test_launcher_recovery_is_bounded_and_quarantines_only_exact_avd_state():
    source = LAUNCHER.read_text(encoding="utf-8")
    assert "function Assert-EmulatorRecoverySafe" in source
    assert "function Move-StaleAvdStateToQuarantine" in source
    assert "function Move-ExactAvdToQuarantine" in source
    assert "hardware-qemu.ini.lock" in source
    assert "multiinstance.lock" in source
    assert r"snapshots\default_boot" in source
    assert "'-wipe-data'" in source
    assert "Move-Item -LiteralPath" in source
    assert "quarantine" in source


@pytest.mark.parametrize(
    ("edition", "package", "artifact", "sha256"),
    [
        (
            "cn",
            "com.dianhun.lxys.aligames",
            r"patched\LuoXuanWarrior_cn_partsuit_userca_debug.apk",
            CN_DERIVED_SHA256,
        ),
        (
            "en",
            "com.oversea.spinarena",
            r"patched\SpiralWarrior_fullres_debug.apk",
            "9C8769E51B535A7F909C935B38C2B2A4F27E4B44C711DBF8410011BF736888AD",
        ),
    ],
)
def test_launcher_doctor_reports_exact_contract(
    edition: str, package: str, artifact: str, sha256: str
):
    doctor = powershell_json(LAUNCHER, "-Doctor", "-Edition", edition)
    assert doctor["edition"] == edition
    assert doctor["edgePort"] == 8888
    assert doctor["gatewayPort"] == 23101
    assert doctor["package"] == package
    assert doctor["apk"].endswith(artifact)
    assert doctor["apkSha256"].lower() == sha256.lower()
    if edition == "cn":
        assert doctor["sourceApk"].endswith("cn_9game.apk")
        assert doctor["sourceApkSha256"] == CN_SOURCE_SHA256
    else:
        assert doctor["sourceApk"] is None
        assert doctor["sourceApkSha256"] is None
    assert doctor["serial"] == "emulator-5556"
    assert Path(doctor["caCertificate"]).is_absolute()
    assert "python" in doctor
    assert "adb" in doctor
    assert "emulator" in doctor
    assert "avd" in doctor
    assert "acceleration" in doctor


def test_launcher_binds_deterministic_android_environment_before_doctor():
    command = (
        f". {ps_quote(LAUNCHER)}; "
        "$Doctor = $true; "
        "$env:ANDROID_SDK_ROOT = 'C:\\wrong-sdk'; "
        "$env:ANDROID_AVD_HOME = 'C:\\wrong-avd'; "
        "function Get-DoctorResult { "
        "if ($env:ANDROID_SDK_ROOT -cne $sdkRoot) { "
        "throw 'doctor observed the wrong SDK root' }; "
        "if ($env:ANDROID_AVD_HOME -cne $avdHome) { "
        "throw 'doctor observed the wrong AVD home' }; "
        "return [ordered]@{ ready = $true } "
        "}; "
        "Invoke-Launcher"
    )
    completed = run_powershell_command(command)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {"ready": True}


def test_native_helper_observes_nonzero_exit_under_windows_powershell():
    command = (
        f". {ps_quote(LAUNCHER)}; "
        "try { "
        "Invoke-NativeChecked -FilePath $env:ComSpec "
        "-Arguments @('/d','/c','exit 37') -Description 'sentinel'; "
        "exit 99 "
        "} catch { [Console]::Error.WriteLine($_.Exception.Message); exit 37 }"
    )
    completed = run_powershell_command(command)
    assert completed.returncode == 37
    assert completed.stdout == ""
    assert "sentinel" in completed.stderr
    assert "37" in completed.stderr


def test_native_helper_captures_successful_stderr_under_windows_powershell():
    command = (
        f". {ps_quote(LAUNCHER)}; "
        "$result = Invoke-NativeChecked -FilePath $env:ComSpec "
        "-Arguments @('/d','/c','echo stderr-sentinel 1>&2') "
        "-Description 'successful stderr sentinel'; "
        "if ($result.StdErr -notmatch 'stderr-sentinel') { exit 91 }"
    )
    completed = run_powershell_command(command)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""


def test_persistent_child_does_not_hold_callers_redirected_pipes(tmp_path: Path):
    child_stdout = tmp_path / "child.stdout.log"
    child_stderr = tmp_path / "child.stderr.log"
    child_pid = tmp_path / "child.pid"
    command = (
        f". {ps_quote(LAUNCHER)}; "
        "$owned = Start-OwnedPersistentProcess "
        "-FilePath 'powershell.exe' "
        "-Arguments @('-NoProfile','-Command',"
        "\"[Console]::Out.WriteLine('child-out'); "
        "[Console]::Error.WriteLine('child-err'); "
        "Start-Sleep -Seconds 8\") "
        f"-WorkingDirectory {ps_quote(tmp_path)} "
        f"-StdoutPath {ps_quote(child_stdout)} "
        f"-StderrPath {ps_quote(child_stderr)}; "
        f"[IO.File]::WriteAllText({ps_quote(child_pid)}, "
        "[string]$owned.ProcessId); "
        "[Console]::Out.WriteLine('launcher-returned')"
    )
    started = time.monotonic()
    completed = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=5,
    )
    elapsed = time.monotonic() - started
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "launcher-returned"
    assert completed.stderr == ""
    assert elapsed < 5
    pid = int(child_pid.read_text(encoding="ascii"))
    try:
        live = subprocess.run(
            [
                POWERSHELL,
                "-NoProfile",
                "-Command",
                f"if (Get-Process -Id {pid} -ErrorAction SilentlyContinue) "
                "{ exit 0 } else { exit 1 }",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert live.returncode == 0
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if (
                child_stdout.exists()
                and "child-out" in child_stdout.read_text(errors="replace")
                and child_stderr.exists()
                and "child-err" in child_stderr.read_text(errors="replace")
            ):
                break
            time.sleep(0.05)
        assert "child-out" in child_stdout.read_text(errors="replace")
        assert "child-err" in child_stderr.read_text(errors="replace")
    finally:
        subprocess.run(
            [
                POWERSHELL,
                "-NoProfile",
                "-Command",
                f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )


def test_spawn_identity_rejects_same_executable_pid_substitution(tmp_path: Path):
    unrelated = subprocess.Popen(
        [POWERSHELL, "-NoProfile", "-Command", "Start-Sleep -Seconds 60"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        stdout = tmp_path / "child.stdout.log"
        stderr = tmp_path / "child.stderr.log"
        command = (
            f". {ps_quote(LAUNCHER)}; "
            f"$unrelatedPid = {unrelated.pid}; "
            "$unrelatedPath = (Get-Process -Id $unrelatedPid).Path; "
            "$brokerIdentity = [ordered]@{ "
            "pid = $unrelatedPid; "
            "creationFileTimeUtc = '132537600000000000'; "
            "executablePath = $unrelatedPath "
            "} | ConvertTo-Json -Compress; "
            "function Invoke-NativeChecked { "
            "return [pscustomobject]@{ "
            "ExitCode = 0; StdOut = $brokerIdentity; StdErr = '' "
            "} "
            "}; "
            "$accepted = $false; "
            "try { "
            "Start-OwnedPersistentProcess "
            f"-FilePath {ps_quote(POWERSHELL)} "
            "-Arguments @('-NoProfile','-Command','Start-Sleep -Seconds 60') "
            f"-WorkingDirectory {ps_quote(tmp_path)} "
            f"-StdoutPath {ps_quote(stdout)} "
            f"-StderrPath {ps_quote(stderr)} | Out-Null; "
            "$accepted = $true "
            "} catch { "
            "if ($_.Exception.Message -notmatch 'identity') { "
            "[Console]::Error.WriteLine($_.Exception.Message); exit 92 "
            "} "
            "}; "
            "if ($accepted) { exit 91 }; "
            "if (-not (Get-Process -Id $unrelatedPid "
            "-ErrorAction SilentlyContinue)) { exit 93 }"
        )
        completed = run_powershell_command(command)
        assert completed.returncode == 0, completed.stderr
        assert unrelated.poll() is None
    finally:
        if unrelated.poll() is None:
            unrelated.terminate()
            unrelated.wait(timeout=10)


def test_avd_image_contract_accepts_emulator_rewritten_spacing(tmp_path: Path):
    config = tmp_path / "config.ini"
    config.write_text(
        "avd.name = SpiralWarrior_API30_X64\n"
        r"image.sysdir.1 = system-images\android-30\google_apis\x86_64\\"
        "\n",
        encoding="ascii",
    )
    command = (
        f". {ps_quote(LAUNCHER)}; "
        f"if (-not (Test-AvdConfigImage -ConfigPath {ps_quote(config)} "
        "-ExpectedImage 'system-images;android-30;google_apis;x86_64')) "
        "{ exit 92 }"
    )
    completed = run_powershell_command(command)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""


def test_boot_wait_reconnects_only_the_exact_offline_serial(tmp_path: Path):
    state = tmp_path / "reconnected.txt"
    fake_adb = tmp_path / "adb.cmd"
    fake_adb.write_text(
        "@echo off\r\n"
        "if \"%1\"==\"devices\" (\r\n"
        "  echo List of devices attached\r\n"
        f"  if exist \"{state}\" (echo emulator-5556 device) "
        "else (echo emulator-5556 offline)\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "if \"%1\"==\"-s\" if \"%2\"==\"emulator-5556\" "
        "if \"%3\"==\"reconnect\" (\r\n"
        f"  type nul > \"{state}\"\r\n"
        "  echo reconnecting emulator-5556\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "if \"%1\"==\"-s\" if \"%2\"==\"emulator-5556\" "
        "if \"%3\"==\"shell\" (\r\n"
        "  echo 1\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "exit /b 94\r\n",
        encoding="ascii",
    )
    command = (
        f". {ps_quote(LAUNCHER)}; "
        f"$adb = {ps_quote(fake_adb)}; "
        "Wait-AdbBoot -TimeoutSeconds 4 -EmulatorPid 1 "
        f"-EmulatorStdout {ps_quote(tmp_path / 'emu.out')} "
        f"-EmulatorStderr {ps_quote(tmp_path / 'emu.err')}; "
        f"if (-not (Test-Path {ps_quote(state)})) {{ exit 95 }}"
    )
    completed = run_powershell_command(command)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""


def test_boot_wait_restarts_adb_server_only_when_device_list_is_empty(tmp_path: Path):
    state = tmp_path / "server-restarted.txt"
    fake_adb = tmp_path / "adb.cmd"
    fake_adb.write_text(
        "@echo off\r\n"
        "if \"%1\"==\"devices\" (\r\n"
        "  echo List of devices attached\r\n"
        f"  if exist \"{state}\" echo emulator-5556 device\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "if \"%1\"==\"kill-server\" (\r\n"
        f"  type nul > \"{state}\"\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "if \"%1\"==\"start-server\" exit /b 0\r\n"
        "if \"%1\"==\"-s\" if \"%2\"==\"emulator-5556\" "
        "if \"%3\"==\"shell\" (\r\n"
        "  echo 1\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "exit /b 98\r\n",
        encoding="ascii",
    )
    command = (
        f". {ps_quote(LAUNCHER)}; "
        f"$adb = {ps_quote(fake_adb)}; "
        "Wait-AdbBoot -TimeoutSeconds 9 -ServerRestartAfterSeconds 1 "
        "-EmulatorPid 1 "
        f"-EmulatorStdout {ps_quote(tmp_path / 'emu.out')} "
        f"-EmulatorStderr {ps_quote(tmp_path / 'emu.err')}; "
        f"if (-not (Test-Path {ps_quote(state)})) {{ exit 99 }}"
    )
    completed = run_powershell_command(command)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""


def test_boot_wait_does_not_restart_empty_adb_during_normal_registration_window(
    tmp_path: Path,
):
    touched = tmp_path / "server-touched-too-early.txt"
    fake_adb = tmp_path / "adb.cmd"
    fake_adb.write_text(
        "@echo off\r\n"
        "if \"%1\"==\"devices\" (\r\n"
        "  echo List of devices attached\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "if \"%1\"==\"kill-server\" (\r\n"
        f"  type nul > \"{touched}\"\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "if \"%1\"==\"start-server\" (\r\n"
        f"  type nul > \"{touched}\"\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "exit /b 104\r\n",
        encoding="ascii",
    )
    command = (
        f". {ps_quote(LAUNCHER)}; "
        f"$adb = {ps_quote(fake_adb)}; "
        "Wait-AdbBoot -TimeoutSeconds 7 -EmulatorPid 1 "
        f"-EmulatorStdout {ps_quote(tmp_path / 'emu.out')} "
        f"-EmulatorStderr {ps_quote(tmp_path / 'emu.err')}"
    )
    completed = run_powershell_command(command)
    assert completed.returncode != 0
    assert not touched.exists()


def test_boot_wait_never_restarts_adb_server_with_another_device(tmp_path: Path):
    touched = tmp_path / "global-server-touched.txt"
    fake_adb = tmp_path / "adb.cmd"
    fake_adb.write_text(
        "@echo off\r\n"
        "if \"%1\"==\"devices\" (\r\n"
        "  echo List of devices attached\r\n"
        "  echo physical-sentinel device\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "if \"%1\"==\"kill-server\" (\r\n"
        f"  type nul > \"{touched}\"\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "if \"%1\"==\"start-server\" (\r\n"
        f"  type nul > \"{touched}\"\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "exit /b 100\r\n",
        encoding="ascii",
    )
    command = (
        f". {ps_quote(LAUNCHER)}; "
        f"$adb = {ps_quote(fake_adb)}; "
        "Wait-AdbBoot -TimeoutSeconds 7 -ServerRestartAfterSeconds 1 "
        "-EmulatorPid 1 "
        f"-EmulatorStdout {ps_quote(tmp_path / 'emu.out')} "
        f"-EmulatorStderr {ps_quote(tmp_path / 'emu.err')}"
    )
    completed = run_powershell_command(command)
    assert completed.returncode != 0
    assert not touched.exists()


def test_adb_root_recovers_from_transport_closed_and_proves_uid_zero(tmp_path: Path):
    rooted = tmp_path / "rooted.txt"
    fake_adb = tmp_path / "adb.cmd"
    fake_adb.write_text(
        "@echo off\r\n"
        "if \"%1\"==\"devices\" (\r\n"
        "  echo List of devices attached\r\n"
        "  echo emulator-5556 device\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "if \"%1\"==\"-s\" if \"%2\"==\"emulator-5556\" "
        "if \"%3\"==\"root\" (\r\n"
        f"  if exist \"{rooted}\" (echo adbd is already running as root& exit /b 0)\r\n"
        f"  type nul > \"{rooted}\"\r\n"
        "  echo adb: unable to connect for root: closed 1>&2\r\n"
        "  exit /b 1\r\n"
        ")\r\n"
        "if \"%1\"==\"-s\" if \"%2\"==\"emulator-5556\" "
        "if \"%3\"==\"shell\" if \"%4\"==\"getprop\" (\r\n"
        "  echo 1\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "if \"%1\"==\"-s\" if \"%2\"==\"emulator-5556\" "
        "if \"%3\"==\"shell\" if \"%4\"==\"id\" (\r\n"
        "  echo 0\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "exit /b 102\r\n",
        encoding="ascii",
    )
    command = (
        f". {ps_quote(LAUNCHER)}; "
        f"$adb = {ps_quote(fake_adb)}; "
        "Enable-AdbRoot -EmulatorPid 1 "
        f"-EmulatorStdout {ps_quote(tmp_path / 'emu.out')} "
        f"-EmulatorStderr {ps_quote(tmp_path / 'emu.err')}; "
        f"if (-not (Test-Path {ps_quote(rooted)})) {{ exit 103 }}"
    )
    completed = run_powershell_command(command)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""


def test_remote_ca_status_accepts_only_user_store_context(tmp_path: Path):
    expected_digest = "c" * 64
    fake_adb = tmp_path / "adb.cmd"
    fake_adb.write_text(
        "@echo off\r\n"
        "if \"%4\"==\"toybox\" if \"%5\"==\"sha256sum\" (\r\n"
        f"  echo {expected_digest}  %6\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "if \"%4\"==\"stat\" (\r\n"
        "  echo root:root:644\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "if \"%4\"==\"ls\" (\r\n"
        "  echo -rw-r--r-- 1 root root "
        "u:object_r:misc_user_data_file:s0 2025 sentinel.0\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "exit /b 87\r\n",
        encoding="ascii",
    )
    remote = "/data/misc/user/0/cacerts-added/0123abcd.0"
    command = (
        f". {ps_quote(LAUNCHER)}; "
        f"$adb = {ps_quote(fake_adb)}; "
        f"$status = Get-RemoteCaStatus -RemotePath '{remote}' "
        f"-ExpectedDigest '{expected_digest}'; "
        "if (-not $status.Valid) { "
        "[Console]::Error.WriteLine($status.Details); exit 89 }"
    )
    completed = run_powershell_command(command)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""


@pytest.mark.parametrize(
    ("installed_state", "skip_install", "expected_installs", "succeeds"),
    [
        ("exact", False, 0, True),
        ("absent", False, 1, True),
        ("mismatch", False, 1, True),
        ("absent", True, 0, False),
        ("mismatch", True, 0, False),
    ],
)
def test_apk_install_reuses_only_exact_remote_hash(
    tmp_path: Path,
    installed_state: str,
    skip_install: bool,
    expected_installs: int,
    succeeds: bool,
):
    expected_digest = "a" * 64
    state = tmp_path / "installed-state.txt"
    if installed_state != "absent":
        state.write_text(installed_state + "\n", encoding="ascii")
    calls = tmp_path / "adb-calls.txt"
    fake_adb = tmp_path / "adb.cmd"
    fake_adb.write_text(
        "@echo off\r\n"
        f"echo %*>>\"{calls}\"\r\n"
        "if \"%1\"==\"-s\" if \"%2\"==\"emulator-5556\" "
        "if \"%3\"==\"shell\" if \"%4\"==\"pm\" if \"%5\"==\"path\" (\r\n"
        f"  if not exist \"{state}\" exit /b 1\r\n"
        "  echo package:/data/app/sentinel/base.apk\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "if \"%1\"==\"-s\" if \"%2\"==\"emulator-5556\" "
        "if \"%3\"==\"shell\" if \"%4\"==\"toybox\" "
        "if \"%5\"==\"sha256sum\" (\r\n"
        f"  findstr /x exact \"{state}\" >nul\r\n"
        f"  if not errorlevel 1 (echo {expected_digest}  %6& exit /b 0)\r\n"
        f"  echo {'b' * 64}  %6\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "if \"%1\"==\"-s\" if \"%2\"==\"emulator-5556\" "
        "if \"%3\"==\"install\" (\r\n"
        f"  >\"{state}\" echo exact\r\n"
        "  echo Success\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "exit /b 86\r\n",
        encoding="ascii",
    )
    apk = tmp_path / "selected.apk"
    apk.write_bytes(b"selected artifact sentinel")
    command = (
        f". {ps_quote(LAUNCHER)}; "
        f"$adb = {ps_quote(fake_adb)}; "
        "Ensure-ApkInstalled "
        f"-ApkPath {ps_quote(apk)} "
        "-PackageName 'com.example.sentinel' "
        f"-ExpectedDigest '{expected_digest}' "
        f"-SkipInstallation:${str(skip_install).lower()} | Out-Null"
    )
    completed = run_powershell_command(command)
    assert (completed.returncode == 0) is succeeds, completed.stderr
    logged = calls.read_text(encoding="ascii").splitlines()
    installs = [line for line in logged if " install " in f" {line} "]
    assert len(installs) == expected_installs


def test_package_exit_during_native_scan_window_fails_launch_gate():
    command = (
        f". {ps_quote(LAUNCHER)}; "
        "$script:pidCalls = 0; "
        "function Invoke-Adb { "
        "param([string[]]$Arguments, [string]$Description); "
        "$joined = $Arguments -join ' '; "
        "if ($joined -eq 'shell monkey -p com.example.sentinel 1') { "
        "return [pscustomobject]@{ StdOut = ''; StdErr = ''; ExitCode = 0 } "
        "}; "
        "if ($joined -eq 'shell pidof com.example.sentinel') { "
        "$script:pidCalls += 1; "
        "$value = if ($script:pidCalls -eq 1) { '4242' } else { '' }; "
        "return [pscustomobject]@{ StdOut = $value; StdErr = ''; ExitCode = 0 } "
        "}; "
        "if ($joined -eq 'logcat -d -v time') { "
        "return [pscustomobject]@{ StdOut = ''; StdErr = ''; ExitCode = 0 } "
        "}; "
        "throw \"unexpected fake ADB call: $joined\" "
        "}; "
        "$accepted = $false; "
        "try { "
        "Invoke-PackageLaunchGate "
        "-PackageName 'com.example.sentinel' "
        "-CompatibilityDiagnostics 'compatibility-sentinel' | Out-Null; "
        "$accepted = $true "
        "} catch { "
        "if ($_.Exception.Message -notmatch "
        "'did not remain live after compatibility window') { "
        "[Console]::Error.WriteLine($_.Exception.Message); exit 92 "
        "} "
        "}; "
        "if ($accepted) { exit 91 }; "
        "if ($script:pidCalls -ne 2) { exit 93 }; "
        "exit 0"
    )
    completed = run_powershell_command(command)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""


def _start_fake_qemu(tmp_path: Path) -> subprocess.Popen[bytes]:
    powershell_path = shutil.which(POWERSHELL)
    assert powershell_path
    fake_qemu = tmp_path / "qemu-system-x86_64.exe"
    shutil.copy2(powershell_path, fake_qemu)
    return subprocess.Popen(
        [
            fake_qemu,
            "-NoProfile",
            "-Command",
            "$null='SpiralWarrior_API30_X64'; Start-Sleep -Seconds 60",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def test_validated_qemu_owner_is_recorded_after_wrapper_exit(tmp_path: Path):
    qemu = _start_fake_qemu(tmp_path)
    try:
        command = (
            f". {ps_quote(LAUNCHER)}; "
            "$started = New-Object System.Collections.Generic.List[object]; "
            f"$owner = Get-ProcessDetails -ProcessId {qemu.pid}; "
            "Add-ValidatedEmulatorOwnerForCleanup "
            "-StartedPids $started -Owner $owner; "
            "if ($started.Count -ne 1) { exit 96 }; "
            f"if ($started[0].ProcessId -ne {qemu.pid}) {{ exit 97 }}; "
            "if (-not $started[0].CreationDate) { exit 98 }"
        )
        completed = run_powershell_command(command)
        assert completed.returncode == 0, completed.stderr
        assert completed.stdout == ""
    finally:
        qemu.terminate()
        qemu.wait(timeout=10)


def test_qemu_handoff_rejects_listener_snapshot_substitution(tmp_path: Path):
    qemu = _start_fake_qemu(tmp_path)
    try:
        command = (
            f". {ps_quote(LAUNCHER)}; "
            "$started = New-Object System.Collections.Generic.List[object]; "
            f"$owner = Get-ProcessDetails -ProcessId {qemu.pid}; "
            "$owner.CreationDate = 'simulated-listener-pid-reuse'; "
            "$accepted = $false; "
            "try { "
            "Add-ValidatedEmulatorOwnerForCleanup "
            "-StartedPids $started -Owner $owner; "
            "$accepted = $true "
            "} catch { }; "
            "if ($accepted) { exit 91 }; "
            "if ($started.Count -ne 0) { exit 92 }; "
            f"if (-not (Get-Process -Id {qemu.pid} "
            "-ErrorAction SilentlyContinue)) { exit 93 }"
        )
        completed = run_powershell_command(command)
        assert completed.returncode == 0, completed.stderr
        assert qemu.poll() is None
    finally:
        if qemu.poll() is None:
            qemu.terminate()
            qemu.wait(timeout=10)


def test_cleanup_revalidates_creation_time_before_stopping_owned_pid():
    sleeper = subprocess.Popen(
        [POWERSHELL, "-NoProfile", "-Command", "Start-Sleep -Seconds 60"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        mismatch = run_powershell_command(
            f". {ps_quote(LAUNCHER)}; "
            f"$record = New-ProcessOwnershipRecord -ProcessId {sleeper.pid}; "
            "$record.CreationDate = 'simulated-pid-reuse'; "
            "Stop-OwnedProcesses -Records @($record); "
            f"if (-not (Get-Process -Id {sleeper.pid} -ErrorAction SilentlyContinue)) "
            "{ exit 88 }"
        )
        assert mismatch.returncode == 0, mismatch.stderr
        assert sleeper.poll() is None

        matching = run_powershell_command(
            f". {ps_quote(LAUNCHER)}; "
            f"$record = New-ProcessOwnershipRecord -ProcessId {sleeper.pid}; "
            "Stop-OwnedProcesses -Records @($record)"
        )
        assert matching.returncode == 0, matching.stderr
        sleeper.wait(timeout=10)
    finally:
        if sleeper.poll() is None:
            sleeper.terminate()
            sleeper.wait(timeout=10)


def test_qemu_owner_is_recorded_before_boot_wait_can_timeout():
    source = LAUNCHER.read_text(encoding="utf-8")
    start = source.index("function Wait-NewEmulatorBoot")
    end = source.index("\nfunction ", start + 10)
    helper = source[start:end]
    record = helper.index("Add-ValidatedEmulatorOwnerForCleanup")
    wait = helper.index("Wait-AdbBoot")
    assert record < wait


def _wait_for_port_file(path: Path, process: subprocess.Popen[str]) -> int:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(process.stderr.read())
        if path.exists():
            return int(path.read_text(encoding="ascii"))
        time.sleep(0.05)
    raise AssertionError("health server did not publish its port")


def _netstat_listener_pid(port: int) -> int:
    completed = subprocess.run(
        ["netstat.exe", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    suffix = f":{port}"
    for line in completed.stdout.splitlines():
        fields = line.split()
        if (
            len(fields) == 5
            and fields[0].upper() == "TCP"
            and fields[1].endswith(suffix)
            and fields[3].upper() == "LISTENING"
        ):
            return int(fields[4])
    raise AssertionError(f"netstat did not report listener port {port}")


def _stop_test_processes_with_marker(marker: str) -> None:
    completed = run_powershell_command(
        "$currentPid = $PID; "
        f"$marker = {ps_quote(marker)}; "
        "$matches = @(Get-CimInstance Win32_Process | Where-Object { "
        "([int]$_.ProcessId -ne [int]$currentPid) -and "
        "([string]$_.CommandLine).Contains($marker) }); "
        "foreach ($match in $matches) { "
        "Stop-Process -Id ([int]$match.ProcessId) -Force "
        "-ErrorAction SilentlyContinue }"
    )
    assert completed.returncode == 0, completed.stderr


def _test_process_ids_with_marker(marker: str) -> list[int]:
    completed = run_powershell_command(
        "$currentPid = $PID; "
        f"$marker = {ps_quote(marker)}; "
        "$matches = @(Get-CimInstance Win32_Process | Where-Object { "
        "([int]$_.ProcessId -ne [int]$currentPid) -and "
        "([string]$_.CommandLine).Contains($marker) }); "
        "[ordered]@{ pids=@($matches | ForEach-Object { "
        "[int]$_.ProcessId }) } | ConvertTo-Json -Compress"
    )
    assert completed.returncode == 0, completed.stderr
    return [int(value) for value in json.loads(completed.stdout)["pids"]]


def _netstat_listener_pid_or_none(port: int) -> int | None:
    try:
        return _netstat_listener_pid(port)
    except AssertionError:
        return None


def test_service_spec_uses_venv_launcher_with_required_dependencies():
    completed = run_powershell_command(
        f". {ps_quote(LAUNCHER)}; "
        "$spec = Get-GatewayServiceSpecification; "
        "$expected = (Resolve-Path -LiteralPath "
        "(Join-Path $root 'server\\.venv_win\\Scripts\\python.exe')).Path; "
        "$probe = Invoke-SpiralWindowsReadOnlyProbe "
        "-FilePath ([string]$spec.launchFilePath) "
        "-Arguments @('-I','-c','import fastapi,uvicorn'); "
        "[ordered]@{ launchFilePath=[string]$spec.launchFilePath; "
        "expected=$expected; importExitCode=[int]$probe.exitCode } "
        "| ConvertTo-Json -Compress"
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["launchFilePath"].lower() == payload["expected"].lower()
    assert payload["importExitCode"] == 0


def test_start_owned_process_authenticates_venv_child_base_image(
    tmp_path: Path,
):
    marker = f"task8a-venv-child-{uuid.uuid4().hex}"
    stdout_path = tmp_path / "child.stdout.log"
    stderr_path = tmp_path / "child.stderr.log"
    child_code = "import fastapi,uvicorn,time;time.sleep(30)"
    command = (
        f". {ps_quote(LAUNCHER)}; "
        "$venv = (Resolve-Path -LiteralPath "
        "(Join-Path $root 'server\\.venv_win\\Scripts\\python.exe')).Path; "
        "$baseProbe = Invoke-SpiralWindowsReadOnlyProbe -FilePath $venv "
        "-Arguments @('-I','-S','-c',"
        "'import pathlib,sys;print(pathlib.Path(sys._base_executable).resolve())'); "
        "$base = ($baseProbe.output -split '\\r?\\n' | "
        "Select-Object -Last 1).Trim(); "
        "$started = $null; "
        "try { "
        "$started = Start-OwnedPersistentProcess -FilePath $venv "
        f"-Arguments @('-c',{ps_quote(child_code)},{ps_quote(marker)}) "
        f"-WorkingDirectory {ps_quote(tmp_path)} "
        f"-StdoutPath {ps_quote(stdout_path)} "
        f"-StderrPath {ps_quote(stderr_path)}; "
        "$live = Get-ProcessDetails -ProcessId ([int]$started.ProcessId); "
        "[ordered]@{ processId=[int]$started.ProcessId; "
        "launchFilePath=$venv; baseExecutable=$base; "
        "ownedExecutable=[string]$started.OwnershipRecord.ExecutablePath; "
        "liveExecutable=[string]$live.ExecutablePath; "
        "creationFileTimeUtc=[string]$started.OwnershipRecord.CreationFileTimeUtc "
        "} | ConvertTo-Json -Compress "
        "} finally { "
        "if ($started -and $started.OwnershipRecord) { "
        "Stop-OwnedProcesses -Records @($started.OwnershipRecord) } }"
    )
    try:
        completed = run_powershell_command(command)
        assert completed.returncode == 0, completed.stderr
        payload = json.loads(completed.stdout)
        assert payload["processId"] > 0
        assert (
            payload["ownedExecutable"].lower()
            == payload["baseExecutable"].lower()
            == payload["liveExecutable"].lower()
        )
        assert (
            payload["ownedExecutable"].lower()
            != payload["launchFilePath"].lower()
        )
        assert int(payload["creationFileTimeUtc"]) > 0
    finally:
        _stop_test_processes_with_marker(marker)


@pytest.mark.parametrize(
    ("fault_setup", "expected_error"),
    (
        (
            "$hooks = @{ BrokerFaultPoint='AfterPopen' }; ",
            "injected broker fault after Popen",
        ),
        (
            "$hooks = @{ BrokerFaultPoint='AfterIdentityCapture' }; ",
            "injected broker fault after identity capture",
        ),
        (
            "$hooks = @{ BeforeBrokerResultParse={ "
            "throw 'injected parent parse fault' } }; ",
            "injected parent parse fault",
        ),
        (
            "$script:cimCalls=0; $hooks = @{ GetProcess={ "
            "param($observedPid) $script:cimCalls++; "
            "if ($script:cimCalls -eq 1) { "
            "throw 'injected first CIM fault' }; "
            "Get-ProcessDetails -ProcessId $observedPid } }; ",
            "injected first CIM fault",
        ),
    ),
    ids=(
        "after-popen",
        "after-identity-capture",
        "before-parent-parse",
        "first-cim-lookup",
    ),
)
def test_broker_faults_leave_no_child_listener_or_state(
    tmp_path: Path,
    fault_setup: str,
    expected_error: str,
):
    marker = f"task8a-broker-fault-{uuid.uuid4().hex}"
    port_probe = socket.socket()
    port_probe.bind(("127.0.0.1", 0))
    port = int(port_probe.getsockname()[1])
    port_probe.close()
    state_path = tmp_path / "launcher-state.json"
    sentinel_state = b'{"schemaVersion":2,"gateway":null,"edge":null}'
    state_path.write_bytes(sentinel_state)
    stdout_path = tmp_path / "fault.stdout.log"
    stderr_path = tmp_path / "fault.stderr.log"
    child_code = (
        "import socket,time;"
        "s=socket.socket();"
        "s.bind(('127.0.0.1',int(__import__('sys').argv[1])));"
        "s.listen();"
        "time.sleep(30)"
    )
    command = (
        f". {ps_quote(LAUNCHER)}; "
        "$venv = (Resolve-Path -LiteralPath "
        "(Join-Path $root 'server\\.venv_win\\Scripts\\python.exe')).Path; "
        + fault_setup
        + "try { "
        "Start-OwnedPersistentProcess -FilePath $venv "
        f"-Arguments @('-c',{ps_quote(child_code)},{port},{ps_quote(marker)}) "
        f"-WorkingDirectory {ps_quote(tmp_path)} "
        f"-StdoutPath {ps_quote(stdout_path)} "
        f"-StderrPath {ps_quote(stderr_path)} -Hooks $hooks; "
        "exit 91 "
        "} catch { "
        "[Console]::Error.WriteLine($_.Exception.Message); exit 7 }"
    )
    try:
        completed = run_powershell_command(command)
        assert completed.returncode == 7
        assert completed.stdout == ""
        assert expected_error in completed.stderr
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if (
                not _test_process_ids_with_marker(marker)
                and _netstat_listener_pid_or_none(port) is None
            ):
                break
            time.sleep(0.05)
        assert _test_process_ids_with_marker(marker) == []
        assert _netstat_listener_pid_or_none(port) is None
        assert state_path.read_bytes() == sentinel_state
    finally:
        _stop_test_processes_with_marker(marker)


def test_occupied_service_port_reuses_only_exact_health(tmp_path: Path):
    port_file = tmp_path / "port.txt"
    server_code = (
        "import http.server,pathlib,sys;"
        "body=b'{\"ok\":true,\"service\":\"spiral-edge\"}';"
        "H=type('H',(http.server.BaseHTTPRequestHandler,),{"
        "'do_GET':lambda s:(s.send_response(200),s.send_header('Content-Length',str(len(body))),"
        "s.end_headers(),s.wfile.write(body)),"
        "'log_message':lambda *a:None});"
        "srv=http.server.ThreadingHTTPServer(('127.0.0.1',0),H);"
        "pathlib.Path(sys.argv[1]).write_text(str(srv.server_port));"
        "srv.serve_forever()"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", server_code, str(port_file)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        port = _wait_for_port_file(port_file, process)
        ok = run_powershell_command(
            f". {ps_quote(LAUNCHER)}; "
            f"$owner = Assert-ServicePortContract -Port {port} -Path '/__health' "
            "-ExpectedBody '{\"ok\":true,\"service\":\"spiral-edge\"}'; "
            "$owner.ProcessId"
        )
        assert ok.returncode == 0, ok.stderr
        owner_pid = int(ok.stdout.strip())
        assert owner_pid > 0
        assert process.poll() is None

        mismatch = run_powershell_command(
            f". {ps_quote(LAUNCHER)}; "
            f"Assert-ServicePortContract -Port {port} -Path '/__health' "
            "-ExpectedBody '{\"ok\":true,\"service\":\"wrong\"}'"
        )
        assert mismatch.returncode != 0
        assert str(owner_pid) in mismatch.stderr
        assert process.poll() is None
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_service_start_race_reports_mismatched_listener_owner(tmp_path: Path):
    port_file = tmp_path / "port.txt"
    server_code = (
        "import http.server,pathlib,sys;"
        "body=b'{\"ok\":true,\"service\":\"foreign\"}';"
        "H=type('H',(http.server.BaseHTTPRequestHandler,),{"
        "'do_GET':lambda s:(s.send_response(200),"
        "s.send_header('Content-Length',str(len(body))),"
        "s.end_headers(),s.wfile.write(body)),"
        "'log_message':lambda *a:None});"
        "srv=http.server.ThreadingHTTPServer(('127.0.0.1',0),H);"
        "pathlib.Path(sys.argv[1]).write_text(str(srv.server_port));"
        "srv.serve_forever()"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", server_code, str(port_file)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        port = _wait_for_port_file(port_file, process)
        listener_pid = _netstat_listener_pid(port)
        completed = run_powershell_command(
            f". {ps_quote(LAUNCHER)}; "
            f"Wait-ServiceHealth -Port {port} -Path '/health' "
            "-ExpectedBody '{\"ok\":true,\"service\":\"expected\"}' "
            "-StdoutLog 'gateway.stdout.log' "
            "-StderrLog 'gateway.stderr.log' -TimeoutSeconds 1"
        )
        assert completed.returncode != 0
        assert str(listener_pid) in completed.stderr
        assert "python" in completed.stderr.lower()
        assert process.poll() is None
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_absent_serial_port_guard_reports_owner_without_stopping_it(tmp_path: Path):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    listener.listen()
    command = (
        f". {ps_quote(LAUNCHER)}; "
        f"Assert-PortsUnowned -Ports @({port}) -Purpose 'emulator sentinel'"
    )
    try:
        completed = run_powershell_command(command)
        assert completed.returncode != 0
        assert str(os.getpid()) in completed.stderr
        assert str(port) in completed.stderr
        listener.getsockname()
    finally:
        listener.close()


def test_launcher_state_mismatch_never_authorizes_termination(tmp_path: Path):
    sleeper = subprocess.Popen(
        [POWERSHELL, "-NoProfile", "-Command", "Start-Sleep -Seconds 60"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    state = tmp_path / "launcher-state.json"
    state.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "logcatPid": sleeper.pid,
                "adbPath": r"C:\definitely-not-the-live-process.exe",
                "serial": "emulator-5556",
                "arguments": [
                    "-s",
                    "emulator-5556",
                    "logcat",
                    "-v",
                    "time",
                ],
                "stdout": str((tmp_path / "capture.log").resolve()),
                "stderr": str((tmp_path / "capture.err.log").resolve()),
            }
        ),
        encoding="utf-8",
    )
    try:
        completed = run_powershell_command(
            f". {ps_quote(LAUNCHER)}; "
            f"$stopped = Stop-RecordedLogcat -StatePath {ps_quote(state)}; "
            "if ($stopped) { exit 90 }"
        )
        assert completed.returncode == 0, completed.stderr
        assert sleeper.poll() is None
    finally:
        sleeper.terminate()
        sleeper.wait(timeout=10)


def test_launcher_state_atomically_replaces_existing_file(tmp_path: Path):
    state = tmp_path / "launcher-state.json"
    state.write_text('{"schemaVersion":0}', encoding="utf-8")
    command = (
        f". {ps_quote(LAUNCHER)}; "
        "$next = [ordered]@{ schemaVersion = 1; sentinel = 'replacement' }; "
        f"Write-AtomicState -StatePath {ps_quote(state)} -State $next; "
        f"$actual = Get-Content -Raw -LiteralPath {ps_quote(state)} "
        "| ConvertFrom-Json; "
        "if ($actual.schemaVersion -ne 1 -or "
        "$actual.sentinel -ne 'replacement') { exit 85 }"
    )
    completed = run_powershell_command(command)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""
    leftovers = [
        path
        for path in tmp_path.iterdir()
        if path.name != "launcher-state.json"
    ]
    assert leftovers == []


def _start_health_server(
    tmp_path: Path,
    body: str = '{"ok":true,"service":"spiralwarrior-local-server"}',
    port: int = 0,
) -> tuple[subprocess.Popen[str], int]:
    port_file = tmp_path / f"health-{time.monotonic_ns()}.port"
    server_code = (
        "import http.server,pathlib,sys;"
        "body=sys.argv[2].encode();"
        "H=type('H',(http.server.BaseHTTPRequestHandler,),{"
        "'do_GET':lambda s:(s.send_response(200),"
        "s.send_header('Content-Length',str(len(body))),"
        "s.end_headers(),s.wfile.write(body)),"
        "'log_message':lambda *a:None});"
        "srv=http.server.ThreadingHTTPServer(('127.0.0.1',int(sys.argv[3])),H);"
        "pathlib.Path(sys.argv[1]).write_text(str(srv.server_port));"
        "srv.serve_forever()"
    )
    process = subprocess.Popen(
        [
            getattr(sys, "_base_executable", sys.executable),
            "-c",
            server_code,
            str(port_file),
            body,
            str(port),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    return process, _wait_for_port_file(port_file, process)


def _service_spec_ps(
    *,
    role: str,
    port: int,
    working_directory: Path,
    health_body: str = '{"ok":true,"service":"spiralwarrior-local-server"}',
) -> str:
    return (
        "[pscustomobject]@{"
        f"role={ps_quote(role)};"
        f"port={port};"
        "healthPath='/health';"
        f"expectedHealthBody={ps_quote(health_body)};"
        f"launchFilePath={ps_quote(Path(sys.executable).resolve())};"
        "arguments=@('-c','fake-owned-health-service');"
        f"workingDirectory={ps_quote(working_directory.resolve())}"
        "}"
    )


def _schema1_logcat_state(tmp_path: Path, *, include_file_time: bool) -> dict:
    state = {
        "schemaVersion": 1,
        "logcatPid": 4242,
        "adbPath": str((tmp_path / "adb.exe").resolve()),
        "executablePath": str((tmp_path / "adb.exe").resolve()),
        "normalizedCommandLine": (
            f'"{(tmp_path / "adb.exe").resolve()}" '
            "-s emulator-5556 logcat -v time"
        ),
        "creationDate": "2026-07-25T00:00:00.0000000Z",
        "serial": "emulator-5556",
        "arguments": ["-s", "emulator-5556", "logcat", "-v", "time"],
        "stdout": str((tmp_path / "capture.log").resolve()),
        "stderr": str((tmp_path / "capture.stderr.log").resolve()),
    }
    if include_file_time:
        state["creationFileTimeUtc"] = "134294112000000000"
    return state


def test_service_state_schema1_migrates_logcat_without_adopting_services(
    tmp_path: Path,
):
    process, _port = _start_health_server(tmp_path)
    state_path = tmp_path / "launcher-state.json"
    original = _schema1_logcat_state(tmp_path, include_file_time=True)
    state_path.write_text(json.dumps(original), encoding="utf-8")
    try:
        completed = run_powershell_command(
            f". {ps_quote(LAUNCHER)}; "
            f"$state = Read-LauncherState -StatePath {ps_quote(state_path)} "
            "-PersistMigration; "
            "$state | ConvertTo-Json -Depth 16 -Compress"
        )
        assert completed.returncode == 0, completed.stderr
        migrated = json.loads(completed.stdout)
        assert migrated["schemaVersion"] == 2
        assert migrated["gateway"] is None
        assert migrated["edge"] is None
        for key, value in original.items():
            if key != "schemaVersion":
                assert migrated[key] == value
        assert json.loads(state_path.read_text(encoding="utf-8")) == migrated
        assert process.poll() is None
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_schema1_logcat_migration_allows_missing_creation_file_time(
    tmp_path: Path,
):
    state_path = tmp_path / "launcher-state.json"
    original = _schema1_logcat_state(tmp_path, include_file_time=False)
    state_path.write_text(json.dumps(original), encoding="utf-8")
    completed = run_powershell_command(
        f". {ps_quote(LAUNCHER)}; "
        f"$state = Read-LauncherState -StatePath {ps_quote(state_path)} "
        "-PersistMigration; "
        "$state | ConvertTo-Json -Depth 16 -Compress"
    )
    assert completed.returncode == 0, completed.stderr
    migrated = json.loads(completed.stdout)
    assert migrated["schemaVersion"] == 2
    assert "creationFileTimeUtc" not in migrated
    assert migrated["gateway"] is None
    assert migrated["edge"] is None


def test_service_state_matching_schema2_reuse_returns_retained_log_paths(
    tmp_path: Path,
):
    process, port = _start_health_server(tmp_path)
    state_path = tmp_path / "launcher-state.json"
    stdout_path = tmp_path / "retained-gateway.stdout.log"
    stderr_path = tmp_path / "retained-gateway.stderr.log"
    stdout_path.write_text("owned stdout", encoding="utf-8")
    stderr_path.write_text("owned stderr", encoding="utf-8")
    spec = _service_spec_ps(role="gateway", port=port, working_directory=tmp_path)
    listener_pid = _netstat_listener_pid(port)
    try:
        command = (
            f". {ps_quote(LAUNCHER)}; "
            f"$spec = {spec}; "
            f"$live = Get-ProcessDetails -ProcessId {listener_pid}; "
            "$record = New-ServiceStateRecord -Specification $spec "
            "-OwnershipRecord $live "
            f"-StdoutPath {ps_quote(stdout_path)} "
            f"-StderrPath {ps_quote(stderr_path)}; "
            "$state = [ordered]@{ schemaVersion=2; gateway=$record; edge=$null }; "
            f"Write-AtomicState -StatePath {ps_quote(state_path)} -State $state; "
            f"$result = Resolve-ServiceReuse -StatePath {ps_quote(state_path)} "
            "-Specification $spec; "
            "$result | ConvertTo-Json -Depth 16 -Compress"
        )
        completed = run_powershell_command(command)
        assert completed.returncode == 0, completed.stderr
        result = json.loads(completed.stdout)
        assert result["owned"] is True
        assert result["processId"] == listener_pid
        assert Path(result["stdout"]) == stdout_path.resolve()
        assert Path(result["stderr"]) == stderr_path.resolve()
        assert process.poll() is None
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_service_state_healthy_unrecorded_reuse_is_unowned_without_paths(
    tmp_path: Path,
):
    process, port = _start_health_server(tmp_path)
    state_path = tmp_path / "launcher-state.json"
    state_path.write_text(
        json.dumps({"schemaVersion": 2, "gateway": None, "edge": None}),
        encoding="utf-8",
    )
    spec = _service_spec_ps(role="gateway", port=port, working_directory=tmp_path)
    listener_pid = _netstat_listener_pid(port)
    try:
        completed = run_powershell_command(
            f". {ps_quote(LAUNCHER)}; "
            f"$spec = {spec}; "
            f"$result = Resolve-ServiceReuse -StatePath {ps_quote(state_path)} "
            "-Specification $spec; "
            "$result | ConvertTo-Json -Depth 16 -Compress"
        )
        assert completed.returncode == 0, completed.stderr
        result = json.loads(completed.stdout)
        assert result == {
            "processId": listener_pid,
            "owned": False,
            "stdout": None,
            "stderr": None,
        }
        persisted = json.loads(state_path.read_text(encoding="utf-8"))
        assert persisted["gateway"] is None
        assert persisted["edge"] is None
        assert process.poll() is None
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_service_state_stale_schema2_role_is_cleared_on_healthy_reuse(
    tmp_path: Path,
):
    process, port = _start_health_server(tmp_path)
    state_path = tmp_path / "launcher-state.json"
    gateway_stdout = tmp_path / "gateway.stdout.log"
    gateway_stderr = tmp_path / "gateway.stderr.log"
    edge_stdout = tmp_path / "edge.stdout.log"
    edge_stderr = tmp_path / "edge.stderr.log"
    for path in (gateway_stdout, gateway_stderr, edge_stdout, edge_stderr):
        path.write_text(path.name, encoding="utf-8")
    gateway_spec = _service_spec_ps(
        role="gateway", port=port, working_directory=tmp_path
    )
    edge_spec = _service_spec_ps(role="edge", port=port + 1, working_directory=tmp_path)
    listener_pid = _netstat_listener_pid(port)
    command = (
        f". {ps_quote(LAUNCHER)}; "
        f"$gatewaySpec = {gateway_spec}; "
        f"$edgeSpec = {edge_spec}; "
        f"$live = Get-ProcessDetails -ProcessId {listener_pid}; "
        "$stale = New-ServiceStateRecord -Specification $gatewaySpec "
        "-OwnershipRecord $live "
        f"-StdoutPath {ps_quote(gateway_stdout)} "
        f"-StderrPath {ps_quote(gateway_stderr)}; "
        "$stale.role = 'edge'; "
        "$edgeRecord = New-ServiceStateRecord -Specification $edgeSpec "
        "-OwnershipRecord $live "
        f"-StdoutPath {ps_quote(edge_stdout)} "
        f"-StderrPath {ps_quote(edge_stderr)}; "
        "$edgeRecord | Add-Member -NotePropertyName metadata "
        "-NotePropertyValue ([pscustomobject]@{ "
        "nested=@([pscustomobject]@{ values=@(1,2,3) }) }); "
        "$state = [ordered]@{ "
        "schemaVersion=2; gateway=$stale; edge=$edgeRecord; "
        "logcatPid=4242; adbPath='C:\\fixture\\adb.exe'; "
        "executablePath='C:\\fixture\\adb.exe'; "
        "normalizedCommandLine='\"C:\\fixture\\adb.exe\" -s emulator-5556 logcat -v time'; "
        "creationDate='2026-07-25T00:00:00.0000000Z'; "
        "creationFileTimeUtc='134294112000000000'; "
        "serial='emulator-5556'; "
        "arguments=@('-s','emulator-5556','logcat','-v','time'); "
        "stdout='C:\\fixture\\capture.log'; stderr='C:\\fixture\\capture.err.log'; "
        "sentinel=[pscustomobject]@{ arrays=@(@(1,2),@(3,4)) } }; "
        f"Write-AtomicState -StatePath {ps_quote(state_path)} -State $state; "
        f"$before = Read-LauncherState -StatePath {ps_quote(state_path)}; "
        f"$result = Resolve-ServiceReuse -StatePath {ps_quote(state_path)} "
        "-Specification $gatewaySpec; "
        f"$after = Read-LauncherState -StatePath {ps_quote(state_path)}; "
        "[ordered]@{ result=$result; before=$before; after=$after } "
        "| ConvertTo-Json -Depth 16 -Compress"
    )
    try:
        completed = run_powershell_command(command)
        assert completed.returncode == 0, completed.stderr
        payload = json.loads(completed.stdout)
        assert payload["result"]["owned"] is False
        assert payload["result"]["stdout"] is None
        assert payload["result"]["stderr"] is None
        assert payload["after"]["gateway"] is None
        assert payload["after"]["edge"] == payload["before"]["edge"]
        for key in (
            "logcatPid",
            "adbPath",
            "executablePath",
            "normalizedCommandLine",
            "creationDate",
            "creationFileTimeUtc",
            "serial",
            "arguments",
            "stdout",
            "stderr",
            "sentinel",
        ):
            assert payload["after"][key] == payload["before"][key]
        assert process.poll() is None
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_service_state_serializes_nested_records_at_depth_eight(tmp_path: Path):
    state_path = tmp_path / "launcher-state.json"
    nested = {
        "level1": {
            "level2": [
                {
                    "level3": {
                        "level4": [
                            {
                                "level5": {
                                    "level6": [
                                        {
                                            "level7": {
                                                "level8": ["sentinel", 8, True]
                                            }
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
            ]
        }
    }
    encoded = json.dumps(nested, separators=(",", ":"))
    completed = run_powershell_command(
        f". {ps_quote(LAUNCHER)}; "
        f"$nested = {ps_quote(encoded)} | ConvertFrom-Json; "
        "$state = [ordered]@{ schemaVersion=2; gateway=$null; edge=$null; "
        "nested=$nested }; "
        f"Write-AtomicState -StatePath {ps_quote(state_path)} -State $state"
    )
    assert completed.returncode == 0, completed.stderr
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["nested"] == nested


def test_stateful_launcher_modes_share_one_repo_scoped_mutex(tmp_path: Path):
    repository = tmp_path / "actual-mode-repository"
    repository.mkdir()
    accepted = json.dumps(_supported_host_status(), separators=(",", ":"))
    state_path = repository / "launcher-state.json"
    runtime_directory = repository / "runtime"
    for mode in ("Normal", "Capture", "RestartGateway", "Doctor"):
        flags = {
            "Normal": "$Doctor=$false; $Capture=$false; $RestartGateway=$false; ",
            "Capture": "$Doctor=$false; $Capture=$true; $RestartGateway=$false; ",
            "RestartGateway": (
                "$Doctor=$false; $Capture=$false; $RestartGateway=$true; "
            ),
            "Doctor": "$Doctor=$true; $Capture=$false; $RestartGateway=$false; ",
        }[mode]
        command = (
            f". {ps_quote(LAUNCHER)}; "
            f"$root = {ps_quote(repository)}; "
            f"$statePath = {ps_quote(state_path)}; "
            f"$runtimeDir = {ps_quote(runtime_directory)}; "
            + flags
            + "$SkipInstall=$false; "
            "$script:counters=[ordered]@{ modeOperation=0; doctorBody=0; "
            "bootstrap=0; stateRead=0; stateWrite=0; "
            "serviceStart=0; serviceStop=0 }; "
            f"$script:hostStatus={ps_quote(accepted)} | ConvertFrom-Json; "
            "$script:pythonStatus=[pscustomobject]@{ compatible=$true }; "
            "$script:artifactStatus=[pscustomobject]@{ artifactReady=$true }; "
            "$script:opensslStatus=[pscustomobject]@{ available=$true }; "
            "function Get-WindowsHostStatus { return $script:hostStatus }; "
            "function Get-PythonRuntimeStatus { return $script:pythonStatus }; "
            "function Get-ArtifactRouteStatus { "
            "return $script:artifactStatus }; "
            "function Get-OpenSslRuntimeStatus { "
            "return $script:opensslStatus }; "
            "function Get-DoctorResult { $script:counters.doctorBody++; "
            "throw 'real Doctor body reached' }; "
            "function Invoke-BootstrapAndRequireReady { "
            "$script:counters.bootstrap++; throw 'real normal body reached' }; "
            "function Test-Java17 { return $false }; "
            "function Read-LauncherState { $script:counters.stateRead++; "
            "throw 'real state read reached' }; "
            "function Write-AtomicState { $script:counters.stateWrite++; "
            "throw 'real state write reached' }; "
            "function Start-OwnedPersistentProcess { "
            "$script:counters.serviceStart++; throw 'real service start reached' }; "
            "function Stop-OwnedProcesses { $script:counters.serviceStop++; "
            "throw 'real service stop reached' }; "
            "$hooks=@{ ModeOperation={ param($observedMode,$context) "
            "$script:counters.modeOperation++; "
            "return [ordered]@{ mode=$observedMode; "
            "repositoryRoot=[string]$context.RepositoryRoot; "
            "statePath=[string]$context.StatePath; "
            "runtimeDirectory=[string]$context.RuntimeDirectory } } }; "
            "Invoke-Launcher -TestHooks $hooks; "
            "[Console]::Out.WriteLine(($script:counters | "
            "ConvertTo-Json -Compress))"
        )
        completed = run_powershell_command(command)
        assert completed.returncode == 0, completed.stderr
        lines = completed.stdout.splitlines()
        assert len(lines) == 2
        result = json.loads(lines[0])
        assert result == {
            "mode": mode,
            "repositoryRoot": str(repository),
            "statePath": str(state_path),
            "runtimeDirectory": str(runtime_directory),
        }
        assert json.loads(lines[1]) == {
            "modeOperation": 1,
            "doctorBody": 0,
            "bootstrap": 0,
            "stateRead": 0,
            "stateWrite": 0,
            "serviceStart": 0,
            "serviceStop": 0,
        }


def test_concurrent_stateful_invocations_preserve_records_and_children(
    tmp_path: Path,
):
    repository = tmp_path / "actual-concurrent-repository"
    repository.mkdir()
    acquired = tmp_path / "winner-acquired"
    release = tmp_path / "release-winner"
    state_path = tmp_path / "launcher-state.json"
    runtime_directory = tmp_path / "runtime"
    sentinel_state = b'{"schemaVersion":2,"gateway":null,"edge":null}'
    state_path.write_bytes(sentinel_state)
    child_prefix = f"task8a-mode-winner-{uuid.uuid4().hex}"
    accepted = json.dumps(_supported_host_status(), separators=(",", ":"))
    base_python = str(Path(getattr(sys, "_base_executable", sys.executable)).resolve())
    child_code = "__import__('time').sleep(60)"
    provider_overrides = (
        f"$script:hostStatus={ps_quote(accepted)} | ConvertFrom-Json; "
        "$script:pythonStatus=[pscustomobject]@{ compatible=$true }; "
        "$script:artifactStatus=[pscustomobject]@{ artifactReady=$true }; "
        "$script:opensslStatus=[pscustomobject]@{ available=$true }; "
        "function Get-WindowsHostStatus { return $script:hostStatus }; "
        "function Get-PythonRuntimeStatus { return $script:pythonStatus }; "
        "function Get-ArtifactRouteStatus { return $script:artifactStatus }; "
        "function Get-OpenSslRuntimeStatus { return $script:opensslStatus }; "
    )
    winner_command = (
        f". {ps_quote(LAUNCHER)}; "
        f"$root = {ps_quote(repository)}; "
        f"$acquired = {ps_quote(acquired)}; "
        f"$release = {ps_quote(release)}; "
        f"$statePath = {ps_quote(state_path)}; "
        f"$runtimeDir = {ps_quote(runtime_directory)}; "
        f"$childPrefix = {ps_quote(child_prefix)}; "
        f"$childExe = {ps_quote(base_python)}; "
        f"$childCode = {ps_quote(child_code)}; "
        "$Doctor=$false; $Capture=$false; $RestartGateway=$false; "
        "$SkipInstall=$false; "
        + provider_overrides
        + "function Test-Java17 { throw 'mode hook not dispatched' }; "
        "$hooks=@{ ModeOperation={ param($observedMode,$context) "
        "[IO.File]::WriteAllText($acquired, 'ready'); "
        "$deadline = [DateTime]::UtcNow.AddSeconds(20); "
        "while ((-not (Test-Path -LiteralPath $release)) -and "
        "[DateTime]::UtcNow -lt $deadline) { Start-Sleep -Milliseconds 50 }; "
        "if (-not (Test-Path -LiteralPath $release)) { throw 'release timeout' }; "
        "[void](New-Item -ItemType Directory -Path $runtimeDir -Force); "
        "$owners=[ordered]@{}; $records=[ordered]@{}; "
        "foreach ($role in @('gateway','edge','logcat')) { "
        "$marker=\"$childPrefix-$role\"; "
        "$child=Start-Process -FilePath $childExe "
        "-ArgumentList @('-c',$childCode,$marker) "
        "-WorkingDirectory $root -WindowStyle Hidden -PassThru; "
        "$owner=New-ProcessOwnershipRecord -ProcessId ([int]$child.Id); "
        "$owners[$role]=$owner; "
        "$stdout=Join-Path $runtimeDir \"$role.stdout.log\"; "
        "$stderr=Join-Path $runtimeDir \"$role.stderr.log\"; "
        "[IO.File]::WriteAllText($stdout,'test-owned stdout'); "
        "[IO.File]::WriteAllText($stderr,'test-owned stderr'); "
        "if ($role -ne 'logcat') { "
        "$port=if ($role -eq 'gateway') { 41001 } else { 41002 }; "
        "$health=if ($role -eq 'gateway') { '/health' } else { '/__health' }; "
        "$body=if ($role -eq 'gateway') { "
        "'{\"ok\":true,\"service\":\"spiralwarrior-local-server\"}' "
        "} else { '{\"ok\":true,\"service\":\"spiral-edge\"}' }; "
        "$spec=[pscustomobject]@{ role=$role; port=$port; "
        "healthPath=$health; expectedHealthBody=$body; "
        "launchFilePath=$childExe; "
        "arguments=@('-c',$childCode,$marker); workingDirectory=$root }; "
        "$records[$role]=New-ServiceStateRecord -Specification $spec "
        "-OwnershipRecord $owner -StdoutPath $stdout -StderrPath $stderr "
        "} }; "
        "$logcatOut=Join-Path $runtimeDir 'logcat.stdout.log'; "
        "$logcatErr=Join-Path $runtimeDir 'logcat.stderr.log'; "
        "$state=[ordered]@{ schemaVersion=2; gateway=$records.gateway; "
        "edge=$records.edge; logcatPid=[int]$owners.logcat.ProcessId; "
        "adbPath=$childExe; executablePath=$owners.logcat.ExecutablePath; "
        "normalizedCommandLine=$owners.logcat.NormalizedCommandLine; "
        "creationDate=$owners.logcat.CreationDate; "
        "creationFileTimeUtc=$owners.logcat.CreationFileTimeUtc; "
        "serial='emulator-5556'; "
        "arguments=@('-s','emulator-5556','logcat','-v','time'); "
        "stdout=$logcatOut; stderr=$logcatErr }; "
        "Write-AtomicState -StatePath $statePath -State $state; "
        "return [ordered]@{ winner=$true; mode=$observedMode; "
        "pids=@([int]$owners.gateway.ProcessId,"
        "[int]$owners.edge.ProcessId,[int]$owners.logcat.ProcessId) } } }; "
        "Invoke-Launcher -TestHooks $hooks"
    )
    winner = subprocess.Popen(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            winner_command,
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not acquired.exists():
            if winner.poll() is not None:
                raise AssertionError(winner.stderr.read())
            time.sleep(0.05)
        assert acquired.exists()

        doctor_command = (
            f". {ps_quote(LAUNCHER)}; "
            f"$root={ps_quote(repository)}; "
            f"$statePath={ps_quote(state_path)}; "
            f"$runtimeDir={ps_quote(runtime_directory)}; "
            "$Doctor=$true; $Capture=$false; $RestartGateway=$false; "
            "$SkipInstall=$false; "
            + provider_overrides
            + "$script:counters=[ordered]@{ doctorBody=0; stateRead=0; "
            "stateWrite=0; serviceStart=0; serviceStop=0 }; "
            "function Get-DoctorResult { $script:counters.doctorBody++; "
            "throw 'Doctor body must be bypassed' }; "
            "function Read-LauncherState { $script:counters.stateRead++ }; "
            "function Write-AtomicState { $script:counters.stateWrite++ }; "
            "function Start-OwnedPersistentProcess { "
            "$script:counters.serviceStart++ }; "
            "function Stop-OwnedProcesses { $script:counters.serviceStop++ }; "
            "$hooks=@{ ModeOperation={ param($observedMode,$context) "
            "return [ordered]@{ mode=$observedMode; lockFree=$true } } }; "
            "Invoke-Launcher -TestHooks $hooks; "
            "[Console]::Out.WriteLine(($script:counters | "
            "ConvertTo-Json -Compress))"
        )
        doctor_started = time.monotonic()
        doctor = run_powershell_command(doctor_command)
        doctor_elapsed = time.monotonic() - doctor_started
        assert doctor.returncode == 0, doctor.stderr
        assert doctor_elapsed < 3
        doctor_lines = doctor.stdout.splitlines()
        assert json.loads(doctor_lines[0]) == {
            "mode": "Doctor",
            "lockFree": True,
        }
        assert json.loads(doctor_lines[1]) == {
            "doctorBody": 0,
            "stateRead": 0,
            "stateWrite": 0,
            "serviceStart": 0,
            "serviceStop": 0,
        }
        assert state_path.read_bytes() == sentinel_state

        contenders: list[tuple[str, Path, subprocess.Popen[str]]] = []
        for mode in ("Normal", "Capture", "RestartGateway"):
            counter_path = tmp_path / f"{mode}.counters.json"
            flags = {
                "Normal": (
                    "$Doctor=$false; $Capture=$false; "
                    "$RestartGateway=$false; "
                ),
                "Capture": (
                    "$Doctor=$false; $Capture=$true; "
                    "$RestartGateway=$false; "
                ),
                "RestartGateway": (
                    "$Doctor=$false; $Capture=$false; "
                    "$RestartGateway=$true; "
                ),
            }[mode]
            contender_command = (
                f". {ps_quote(LAUNCHER)}; "
                f"$root={ps_quote(repository)}; "
                f"$statePath={ps_quote(state_path)}; "
                f"$runtimeDir={ps_quote(runtime_directory)}; "
                + flags
                + "$SkipInstall=$false; "
                + provider_overrides
                + "$script:counters=[ordered]@{ modeOperation=0; stateRead=0; "
                "stateWrite=0; serviceStart=0; serviceStop=0 }; "
                "function Read-LauncherState { $script:counters.stateRead++ }; "
                "function Write-AtomicState { $script:counters.stateWrite++ }; "
                "function Start-OwnedPersistentProcess { "
                "$script:counters.serviceStart++ }; "
                "function Stop-OwnedProcesses { $script:counters.serviceStop++ }; "
                "$hooks=@{ ModeOperation={ param($observedMode,$context) "
                "$script:counters.modeOperation++; "
                "throw 'loser entered mode operation' } }; "
                "try { Invoke-Launcher -TestHooks $hooks; exit 91 } catch { "
                f"[IO.File]::WriteAllText({ps_quote(counter_path)},"
                "($script:counters | ConvertTo-Json -Compress)); "
                "[Console]::Error.WriteLine($_.Exception.Message); exit 9 }"
            )
            contender = subprocess.Popen(
                [
                    POWERSHELL,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    contender_command,
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            contenders.append((mode, counter_path, contender))
        started = time.monotonic()
        canonical_root = str(repository.resolve()).rstrip("\\/").upper()
        digest = hashlib.sha256(canonical_root.encode("utf-8")).hexdigest()
        expected_mutex = rf"Local\SpiralWarriorLauncher-{digest}"
        expected_error = (
            f"launcher mutex timeout after 5000 ms: {expected_mutex}"
        )
        for mode, counter_path, contender in contenders:
            stdout, stderr = contender.communicate(timeout=10)
            assert contender.returncode == 9
            assert stdout == ""
            assert stderr.splitlines() == [expected_error]
            assert json.loads(counter_path.read_text(encoding="utf-8")) == {
                "modeOperation": 0,
                "stateRead": 0,
                "stateWrite": 0,
                "serviceStart": 0,
                "serviceStop": 0,
            }, mode
        elapsed = time.monotonic() - started
        assert 4.0 <= elapsed <= 9.0
        assert state_path.read_bytes() == sentinel_state

        release.write_text("release", encoding="ascii")
        stdout, stderr = winner.communicate(timeout=10)
        assert winner.returncode == 0, stderr
        winner_result = json.loads(stdout)
        assert winner_result["winner"] is True
        assert winner_result["mode"] == "Normal"
        recorded_pids = {int(value) for value in winner_result["pids"]}
        assert len(recorded_pids) == 3
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["schemaVersion"] == 2
        assert {state["gateway"]["role"], state["edge"]["role"]} == {
            "gateway",
            "edge",
        }
        assert int(state["logcatPid"]) in recorded_pids
        live_marker_pids = set(_test_process_ids_with_marker(child_prefix))
        assert live_marker_pids == recorded_pids
    finally:
        if not release.exists():
            release.write_text("release", encoding="ascii")
        if winner.poll() is None:
            winner.terminate()
            winner.wait(timeout=10)
        _stop_test_processes_with_marker(child_prefix)


def test_service_stop_requires_creation_file_time():
    sleeper = subprocess.Popen(
        [POWERSHELL, "-NoProfile", "-Command", "Start-Sleep -Seconds 60"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        completed = run_powershell_command(
            f". {ps_quote(LAUNCHER)}; "
            f"$live = Get-ProcessDetails -ProcessId {sleeper.pid}; "
            "$record = [pscustomobject]@{ "
            "Role='gateway'; ProcessId=$live.ProcessId; "
            "ExecutablePath=$live.ExecutablePath; "
            "NormalizedCommandLine=$live.NormalizedCommandLine; "
            "CreationDate=$live.CreationDate }; "
            "Stop-OwnedProcesses -Records @($record); "
            f"if (-not (Get-Process -Id {sleeper.pid} "
            "-ErrorAction SilentlyContinue)) { exit 92 }"
        )
        assert completed.returncode == 0, completed.stderr
        assert sleeper.poll() is None
    finally:
        if sleeper.poll() is None:
            sleeper.terminate()
            sleeper.wait(timeout=10)


def _mock_identity_ps(variable: str, process_id: int, label: str) -> str:
    executable = str(Path(sys.executable).resolve())
    return (
        f"${variable} = [pscustomobject]@{{ "
        f"ProcessId={process_id}; ParentProcessId=1; "
        f"ExecutablePath={ps_quote(executable)}; "
        f"CommandLine={ps_quote(f'{executable} -c {label}')}; "
        f"NormalizedCommandLine={ps_quote(f'{executable} -c {label}')}; "
        f"CreationDate={ps_quote(f'2026-07-25T00:00:{process_id % 60:02d}.0000000Z')}; "
        f"CreationFileTimeUtc={ps_quote(str(134294112000000000 + process_id * 10))} "
        "}; "
    )


@pytest.mark.parametrize("mismatch_field", RESTART_MISMATCH_FIELDS)
def test_restart_gateway_refuses_mismatched_owned_service(
    tmp_path: Path,
    mismatch_field: str,
):
    sleeper = subprocess.Popen(
        [POWERSHELL, "-NoProfile", "-Command", "Start-Sleep -Seconds 60"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    state_path = tmp_path / "launcher-state.json"
    stdout_path = tmp_path / "old.stdout.log"
    stderr_path = tmp_path / "old.stderr.log"
    stdout_path.write_text("old stdout", encoding="utf-8")
    stderr_path.write_text("old stderr", encoding="utf-8")
    port = 40123
    spec = _service_spec_ps(role="gateway", port=port, working_directory=tmp_path)
    mutation = {
        "processId": "$record.processId = [int]$record.processId + 1; ",
        "executablePath": "$record.executablePath = 'C:\\tampered\\python.exe'; ",
        "normalizedCommandLine": "$record.normalizedCommandLine += ' tampered'; ",
        "creationDate": "$record.creationDate = 'tampered-date'; ",
        "creationFileTimeUtc": "$record.creationFileTimeUtc = '134294112999999999'; ",
        "role": "$record.role = 'edge'; ",
        "port": "$record.port = [int]$record.port + 1; ",
        "healthPath": "$record.healthPath = '/tampered'; ",
        "expectedHealthBody": "$record.expectedHealthBody = '{\"tampered\":true}'; ",
        "launchFilePath": "$record.launchFilePath = 'C:\\tampered\\python.exe'; ",
        "arguments": "$record.arguments = @('-c','tampered'); ",
        "workingDirectory": "$record.workingDirectory = 'C:\\tampered'; ",
    }[mismatch_field]
    try:
        command = (
            f". {ps_quote(LAUNCHER)}; "
            f"$spec = {spec}; "
            f"$live = Get-ProcessDetails -ProcessId {sleeper.pid}; "
            "$record = New-ServiceStateRecord -Specification $spec "
            "-OwnershipRecord $live "
            f"-StdoutPath {ps_quote(stdout_path)} "
            f"-StderrPath {ps_quote(stderr_path)}; "
            f"{mutation}"
            "$state = [ordered]@{ schemaVersion=2; gateway=$record; edge=$null }; "
            f"Write-AtomicState -StatePath {ps_quote(state_path)} -State $state; "
            "$script:stopCalls=0; $script:startCalls=0; "
            "$hooks = @{ "
            f"ObservePort={{ param($observedPort) if ($observedPort -eq {port}) "
            "{ return $live }; return $null }; "
            "GetProcess={ param($observedPid) return $live }; "
            "StopOwned={ param($records) $script:stopCalls++ }; "
            "WaitGone={ param($observedPid,$observedPort) }; "
            "StartService={ param($serviceSpec,$outLog,$errLog) "
            "$script:startCalls++; throw 'replacement must not start' }; "
            "WaitHealth={ throw 'health must not run' } }; "
            "try { "
            "Invoke-RestartGatewayTransaction "
            f"-StatePath {ps_quote(state_path)} -Specification $spec "
            f"-RuntimeDirectory {ps_quote(tmp_path)} -EdgePort {port + 1} "
            "-Hooks $hooks; exit 93 "
            "} catch { "
            "if ($_.Exception.Message -match 'not recognized') { exit 96 }; "
            "[ordered]@{ stopCalls=$script:stopCalls; "
            "startCalls=$script:startCalls } | ConvertTo-Json -Compress; exit 0 }"
        )
        completed = run_powershell_command(command)
        assert completed.returncode == 0, completed.stderr
        assert json.loads(completed.stdout) == {"stopCalls": 0, "startCalls": 0}
        assert sleeper.poll() is None
    finally:
        if sleeper.poll() is None:
            sleeper.terminate()
            sleeper.wait(timeout=10)


def test_restart_gateway_revalidates_identity_at_signal_boundary(
    tmp_path: Path,
):
    sleeper = subprocess.Popen(
        [POWERSHELL, "-NoProfile", "-Command", "Start-Sleep -Seconds 60"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    state_path = tmp_path / "launcher-state.json"
    stdout_path = tmp_path / "old.stdout.log"
    stderr_path = tmp_path / "old.stderr.log"
    stdout_path.touch()
    stderr_path.touch()
    port = 40124
    spec = _service_spec_ps(role="gateway", port=port, working_directory=tmp_path)
    try:
        command = (
            f". {ps_quote(LAUNCHER)}; "
            f"$spec = {spec}; "
            f"$live = Get-ProcessDetails -ProcessId {sleeper.pid}; "
            "$record = New-ServiceStateRecord -Specification $spec "
            "-OwnershipRecord $live "
            f"-StdoutPath {ps_quote(stdout_path)} "
            f"-StderrPath {ps_quote(stderr_path)}; "
            "$state = [ordered]@{ schemaVersion=2; gateway=$record; edge=$null }; "
            f"Write-AtomicState -StatePath {ps_quote(state_path)} -State $state; "
            "$changed = $live.PSObject.Copy(); "
            "$changed.CreationFileTimeUtc = '134294112999999999'; "
            "$script:stopCalls=0; $script:startCalls=0; "
            "$hooks = @{ "
            f"ObservePort={{ param($observedPort) if ($observedPort -eq {port}) "
            "{ return $live }; return $null }; "
            "GetProcess={ param($observedPid) return $changed }; "
            "StopOwned={ param($records) $script:stopCalls++ }; "
            "WaitGone={ param($observedPid,$observedPort) }; "
            "StartService={ param($serviceSpec,$outLog,$errLog) "
            "$script:startCalls++; throw 'must not start' }; "
            "WaitHealth={ throw 'must not health-check' } }; "
            "try { "
            "Invoke-RestartGatewayTransaction "
            f"-StatePath {ps_quote(state_path)} -Specification $spec "
            f"-RuntimeDirectory {ps_quote(tmp_path)} -EdgePort {port + 1} "
            "-Hooks $hooks; exit 94 "
            "} catch { "
            "if ($_.Exception.Message -match 'not recognized') { exit 96 }; "
            "[ordered]@{ stopCalls=$script:stopCalls; "
            "startCalls=$script:startCalls } | ConvertTo-Json -Compress; exit 0 }"
        )
        completed = run_powershell_command(command)
        assert completed.returncode == 0, completed.stderr
        assert json.loads(completed.stdout) == {"stopCalls": 0, "startCalls": 0}
        assert sleeper.poll() is None
    finally:
        if sleeper.poll() is None:
            sleeper.terminate()
            sleeper.wait(timeout=10)


@pytest.mark.parametrize("corrupt_kind", ("invalid-json", "unknown-schema", "incomplete"))
def test_corrupt_service_state_never_authorizes_termination(
    tmp_path: Path,
    corrupt_kind: str,
):
    sleeper = subprocess.Popen(
        [POWERSHELL, "-NoProfile", "-Command", "Start-Sleep -Seconds 60"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    state_path = tmp_path / "launcher-state.json"
    if corrupt_kind == "invalid-json":
        state_path.write_text("{not-json", encoding="utf-8")
    elif corrupt_kind == "unknown-schema":
        state_path.write_text(
            json.dumps({"schemaVersion": 99, "gateway": None, "edge": None}),
            encoding="utf-8",
        )
    else:
        state_path.write_text(
            json.dumps(
                {
                    "schemaVersion": 2,
                    "gateway": {"processId": sleeper.pid},
                    "edge": None,
                }
            ),
            encoding="utf-8",
        )
    before = state_path.read_bytes()
    port = 40125
    spec = _service_spec_ps(role="gateway", port=port, working_directory=tmp_path)
    try:
        command = (
            f". {ps_quote(LAUNCHER)}; "
            f"$spec = {spec}; "
            f"$live = Get-ProcessDetails -ProcessId {sleeper.pid}; "
            "$script:stopCalls=0; $script:startCalls=0; "
            "$hooks = @{ "
            "ObservePort={ param($observedPort) return $live }; "
            "GetProcess={ param($observedPid) return $live }; "
            "StopOwned={ param($records) $script:stopCalls++ }; "
            "WaitGone={ param($observedPid,$observedPort) }; "
            "StartService={ param($serviceSpec,$outLog,$errLog) "
            "$script:startCalls++ }; "
            "WaitHealth={ return $live } }; "
            "try { "
            "Invoke-RestartGatewayTransaction "
            f"-StatePath {ps_quote(state_path)} -Specification $spec "
            f"-RuntimeDirectory {ps_quote(tmp_path)} -EdgePort {port + 1} "
            "-Hooks $hooks; exit 95 "
            "} catch { "
            "if ($_.Exception.Message -match 'not recognized') { exit 96 }; "
            "[ordered]@{ stopCalls=$script:stopCalls; "
            "startCalls=$script:startCalls } | ConvertTo-Json -Compress; exit 0 }"
        )
        completed = run_powershell_command(command)
        assert completed.returncode == 0, completed.stderr
        assert json.loads(completed.stdout) == {"stopCalls": 0, "startCalls": 0}
        assert state_path.read_bytes() == before
        assert sleeper.poll() is None
    finally:
        if sleeper.poll() is None:
            sleeper.terminate()
            sleeper.wait(timeout=10)


def test_partial_schema2_logcat_never_authorizes_gateway_stop(tmp_path: Path):
    state_path = tmp_path / "launcher-state.json"
    old_stdout = tmp_path / "old.stdout.log"
    old_stderr = tmp_path / "old.stderr.log"
    old_stdout.touch()
    old_stderr.touch()
    gateway_port = 40134
    edge_port = 40135
    spec = _service_spec_ps(
        role="gateway", port=gateway_port, working_directory=tmp_path
    )
    command = (
        f". {ps_quote(LAUNCHER)}; "
        f"$spec = {spec}; "
        + _mock_identity_ps("oldLive", 1601, "old-gateway")
        + "$record = New-ServiceStateRecord -Specification $spec "
        "-OwnershipRecord $oldLive "
        f"-StdoutPath {ps_quote(old_stdout)} "
        f"-StderrPath {ps_quote(old_stderr)}; "
        "$state = [ordered]@{ schemaVersion=2; gateway=$record; edge=$null; "
        "adbPath='C:\\partial\\adb.exe' }; "
        f"Write-AtomicState -StatePath {ps_quote(state_path)} -State $state; "
        "$script:stopCalls=0; $script:startCalls=0; "
        "$hooks = @{ "
        f"ObservePort={{ param($observedPort) if ($observedPort -eq {gateway_port}) "
        "{ return $oldLive }; return $null }; "
        "GetProcess={ param($observedPid) return $oldLive }; "
        "StopOwned={ param($records) $script:stopCalls++ }; "
        "WaitGone={ param($observedPid,$observedPort) }; "
        "StartService={ param($serviceSpec,$outLog,$errLog) "
        "$script:startCalls++; throw 'must not start' }; "
        "WaitHealth={ throw 'must not health-check' } }; "
        "try { "
        "Invoke-RestartGatewayTransaction "
        f"-StatePath {ps_quote(state_path)} -Specification $spec "
        f"-RuntimeDirectory {ps_quote(tmp_path)} -EdgePort {edge_port} "
        "-Hooks $hooks; exit 99 "
        "} catch { "
        "if ($_.Exception.Message -match 'not recognized') { exit 96 }; "
        "[ordered]@{ stopCalls=$script:stopCalls; "
        "startCalls=$script:startCalls } | ConvertTo-Json -Compress; exit 0 }"
    )
    completed = run_powershell_command(command)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {"stopCalls": 0, "startCalls": 0}


def test_restart_gateway_observes_unowned_edge_identity_without_adoption(
    tmp_path: Path,
):
    state_path = tmp_path / "launcher-state.json"
    old_stdout = tmp_path / "old.stdout.log"
    old_stderr = tmp_path / "old.stderr.log"
    old_stdout.touch()
    old_stderr.touch()
    gateway_port = 40126
    edge_port = 40127
    spec = _service_spec_ps(
        role="gateway", port=gateway_port, working_directory=tmp_path
    )
    command = (
        f". {ps_quote(LAUNCHER)}; "
        f"$spec = {spec}; "
        + _mock_identity_ps("oldLive", 1101, "old-gateway")
        + _mock_identity_ps("newLive", 1102, "new-gateway")
        + _mock_identity_ps("edgeBefore", 2101, "legacy-edge")
        + "$edgeAfter = $edgeBefore.PSObject.Copy(); "
        "$record = New-ServiceStateRecord -Specification $spec "
        "-OwnershipRecord $oldLive "
        f"-StdoutPath {ps_quote(old_stdout)} "
        f"-StderrPath {ps_quote(old_stderr)}; "
        "$state = [ordered]@{ schemaVersion=2; gateway=$record; edge=$null }; "
        f"Write-AtomicState -StatePath {ps_quote(state_path)} -State $state; "
        "$script:edgeCalls=0; $script:stopRoles=@(); $script:startRoles=@(); "
        "$hooks = @{ "
        f"ObservePort={{ param($observedPort) if ($observedPort -eq {edge_port}) "
        "{ $script:edgeCalls++; if ($script:edgeCalls -eq 1) "
        "{ return $edgeBefore }; return $edgeAfter }; return $oldLive }; "
        "GetProcess={ param($observedPid) return $oldLive }; "
        "StopOwned={ param($records) "
        "$script:stopRoles += [string]$records[0].role }; "
        "WaitGone={ param($observedPid,$observedPort) }; "
        "StartService={ param($serviceSpec,$outLog,$errLog) "
        "$script:startRoles += [string]$serviceSpec.role; "
        "[IO.File]::WriteAllText($outLog,'fresh stdout'); "
        "[IO.File]::WriteAllText($errLog,'fresh stderr'); "
        "return [pscustomobject]@{ ProcessId=$newLive.ProcessId; "
        "OwnershipRecord=$newLive; Records=@($newLive); "
        "StdoutPath=$outLog; StderrPath=$errLog } }; "
        "WaitHealth={ param($serviceSpec,$outLog,$errLog) return $newLive } }; "
        "$result = Invoke-RestartGatewayTransaction "
        f"-StatePath {ps_quote(state_path)} -Specification $spec "
        f"-RuntimeDirectory {ps_quote(tmp_path)} -EdgePort {edge_port} "
        "-Hooks $hooks; "
        f"$after = Read-LauncherState -StatePath {ps_quote(state_path)}; "
        "[ordered]@{ result=$result; after=$after; "
        "stopRoles=$script:stopRoles; startRoles=$script:startRoles } "
        "| ConvertTo-Json -Depth 16 -Compress"
    )
    completed = run_powershell_command(command)
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["result"]["gatewayRestarted"] is True
    assert payload["result"]["edgeIdentityRetained"] is True
    assert payload["result"]["edgePid"] == 2101
    assert payload["after"]["edge"] is None
    assert payload["stopRoles"] == ["gateway"]
    assert payload["startRoles"] == ["gateway"]


@pytest.mark.parametrize(
    ("observation_number", "failure_kind"),
    (
        (1, "throw"),
        (1, "vanish"),
        (2, "throw"),
        (2, "vanish"),
    ),
    ids=(
        "first-throws",
        "first-vanishes",
        "second-throws",
        "second-vanishes",
    ),
)
def test_restart_gateway_edge_observation_failure_is_nonfatal_and_read_only(
    tmp_path: Path,
    observation_number: int,
    failure_kind: str,
):
    state_path = tmp_path / "launcher-state.json"
    gateway_stdout = tmp_path / "gateway-old.stdout.log"
    gateway_stderr = tmp_path / "gateway-old.stderr.log"
    edge_stdout = tmp_path / "edge.stdout.log"
    edge_stderr = tmp_path / "edge.stderr.log"
    for path in (
        gateway_stdout,
        gateway_stderr,
        edge_stdout,
        edge_stderr,
    ):
        path.touch()
    gateway_port = 40134
    edge_port = 40135
    gateway_spec = _service_spec_ps(
        role="gateway",
        port=gateway_port,
        working_directory=tmp_path,
    )
    edge_spec = _service_spec_ps(
        role="edge",
        port=edge_port,
        working_directory=tmp_path,
        health_body='{"ok":true,"service":"spiral-edge"}',
    )
    failed_observation = (
        "throw 'injected edge observation ambiguity'"
        if failure_kind == "throw"
        else "return $null"
    )
    command = (
        f". {ps_quote(LAUNCHER)}; "
        f"$gatewaySpec = {gateway_spec}; $edgeSpec = {edge_spec}; "
        + _mock_identity_ps("oldGateway", 1601, "old-gateway")
        + _mock_identity_ps("newGateway", 1602, "new-gateway")
        + _mock_identity_ps("edgeLive", 2601, "owned-edge")
        + "$gatewayRecord = New-ServiceStateRecord "
        "-Specification $gatewaySpec -OwnershipRecord $oldGateway "
        f"-StdoutPath {ps_quote(gateway_stdout)} "
        f"-StderrPath {ps_quote(gateway_stderr)}; "
        "$edgeRecord = New-ServiceStateRecord "
        "-Specification $edgeSpec -OwnershipRecord $edgeLive "
        f"-StdoutPath {ps_quote(edge_stdout)} "
        f"-StderrPath {ps_quote(edge_stderr)}; "
        "$edgeRecord | Add-Member -NotePropertyName metadata "
        "-NotePropertyValue ([pscustomobject]@{ "
        "sentinel='preserve-edge'; nested=@(1,@(2,3)) }); "
        "$state = [ordered]@{ schemaVersion=2; "
        "gateway=$gatewayRecord; edge=$edgeRecord }; "
        f"Write-AtomicState -StatePath {ps_quote(state_path)} -State $state; "
        f"$before = Read-LauncherState -StatePath {ps_quote(state_path)}; "
        "$script:edgeCalls=0; $script:stopRoles=@(); "
        "$hooks = @{ "
        f"ObservePort={{ param($observedPort) if ($observedPort -eq {edge_port}) "
        "{ $script:edgeCalls++; "
        f"if ($script:edgeCalls -eq {observation_number}) "
        f"{{ {failed_observation} }}; return $edgeLive "
        "}; return $oldGateway }; "
        "GetProcess={ param($observedPid) return $oldGateway }; "
        "StopOwned={ param($records) "
        "$script:stopRoles += [string]$records[0].role }; "
        "WaitGone={ param($observedPid,$observedPort) }; "
        "StartService={ param($serviceSpec,$outLog,$errLog) "
        "[IO.File]::WriteAllText($outLog,'fresh stdout'); "
        "[IO.File]::WriteAllText($errLog,'fresh stderr'); "
        "return [pscustomobject]@{ ProcessId=$newGateway.ProcessId; "
        "OwnershipRecord=$newGateway; Records=@($newGateway); "
        "StdoutPath=$outLog; StderrPath=$errLog } }; "
        "WaitHealth={ param($serviceSpec,$outLog,$errLog) "
        "return $newGateway } }; "
        "$result = Invoke-RestartGatewayTransaction "
        f"-StatePath {ps_quote(state_path)} -Specification $gatewaySpec "
        f"-RuntimeDirectory {ps_quote(tmp_path)} -EdgePort {edge_port} "
        "-Hooks $hooks; "
        f"$after = Read-LauncherState -StatePath {ps_quote(state_path)}; "
        "[ordered]@{ result=$result; before=$before; after=$after; "
        "edgeCalls=$script:edgeCalls; stopRoles=$script:stopRoles } "
        "| ConvertTo-Json -Depth 16 -Compress"
    )
    completed = run_powershell_command(command)
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["result"]["gatewayRestarted"] is True
    assert payload["result"]["gatewayPid"] == 1602
    assert payload["result"]["gatewayOwned"] is True
    assert payload["result"]["edgeIdentityRetained"] is False
    assert payload["result"]["edgePid"] is None
    assert payload["after"]["gateway"]["processId"] == 1602
    assert payload["after"]["edge"] == payload["before"]["edge"]
    assert payload["edgeCalls"] == 2
    assert payload["stopRoles"] == ["gateway"]


@pytest.mark.parametrize(
    "identity_field",
    (
        "ProcessId",
        "ExecutablePath",
        "NormalizedCommandLine",
        "CreationDate",
        "CreationFileTimeUtc",
    ),
)
def test_restart_gateway_edge_identity_change_emits_no_retained_pid(
    tmp_path: Path,
    identity_field: str,
):
    state_path = tmp_path / "launcher-state.json"
    old_stdout = tmp_path / "old.stdout.log"
    old_stderr = tmp_path / "old.stderr.log"
    old_stdout.touch()
    old_stderr.touch()
    gateway_port = 40128
    edge_port = 40129
    spec = _service_spec_ps(
        role="gateway", port=gateway_port, working_directory=tmp_path
    )
    mutation = {
        "ProcessId": "$edgeAfter.ProcessId = 2202; ",
        "ExecutablePath": "$edgeAfter.ExecutablePath = 'C:\\changed\\edge.exe'; ",
        "NormalizedCommandLine": "$edgeAfter.NormalizedCommandLine += ' changed'; ",
        "CreationDate": "$edgeAfter.CreationDate = 'changed-date'; ",
        "CreationFileTimeUtc": (
            "$edgeAfter.CreationFileTimeUtc = '134294112999999999'; "
        ),
    }[identity_field]
    command = (
        f". {ps_quote(LAUNCHER)}; "
        f"$spec = {spec}; "
        + _mock_identity_ps("oldLive", 1201, "old-gateway")
        + _mock_identity_ps("newLive", 1202, "new-gateway")
        + _mock_identity_ps("edgeBefore", 2201, "legacy-edge")
        + "$edgeAfter = $edgeBefore.PSObject.Copy(); "
        + mutation
        + "$record = New-ServiceStateRecord -Specification $spec "
        "-OwnershipRecord $oldLive "
        f"-StdoutPath {ps_quote(old_stdout)} "
        f"-StderrPath {ps_quote(old_stderr)}; "
        "$state = [ordered]@{ schemaVersion=2; gateway=$record; edge=$null }; "
        f"Write-AtomicState -StatePath {ps_quote(state_path)} -State $state; "
        "$script:edgeCalls=0; $script:stopRoles=@(); "
        "$hooks = @{ "
        f"ObservePort={{ param($observedPort) if ($observedPort -eq {edge_port}) "
        "{ $script:edgeCalls++; if ($script:edgeCalls -eq 1) "
        "{ return $edgeBefore }; return $edgeAfter }; return $oldLive }; "
        "GetProcess={ param($observedPid) return $oldLive }; "
        "StopOwned={ param($records) "
        "$script:stopRoles += [string]$records[0].role }; "
        "WaitGone={ param($observedPid,$observedPort) }; "
        "StartService={ param($serviceSpec,$outLog,$errLog) "
        "[IO.File]::WriteAllText($outLog,'fresh stdout'); "
        "[IO.File]::WriteAllText($errLog,'fresh stderr'); "
        "return [pscustomobject]@{ ProcessId=$newLive.ProcessId; "
        "OwnershipRecord=$newLive; Records=@($newLive); "
        "StdoutPath=$outLog; StderrPath=$errLog } }; "
        "WaitHealth={ param($serviceSpec,$outLog,$errLog) return $newLive } }; "
        "$result = Invoke-RestartGatewayTransaction "
        f"-StatePath {ps_quote(state_path)} -Specification $spec "
        f"-RuntimeDirectory {ps_quote(tmp_path)} -EdgePort {edge_port} "
        "-Hooks $hooks; "
        "[ordered]@{ result=$result; stopRoles=$script:stopRoles } "
        "| ConvertTo-Json -Depth 16 -Compress"
    )
    completed = run_powershell_command(command)
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["result"]["gatewayRestarted"] is True
    assert payload["result"]["edgeIdentityRetained"] is False
    assert payload["result"]["edgePid"] is None
    assert payload["stopRoles"] == ["gateway"]


def test_restart_gateway_replaces_only_gateway_and_preserves_state(
    tmp_path: Path,
):
    state_path = tmp_path / "launcher-state.json"
    old_stdout = tmp_path / "old.stdout.log"
    old_stderr = tmp_path / "old.stderr.log"
    edge_stdout = tmp_path / "edge.stdout.log"
    edge_stderr = tmp_path / "edge.stderr.log"
    for path in (old_stdout, old_stderr, edge_stdout, edge_stderr):
        path.touch()
    gateway_port = 40130
    edge_port = 40131
    gateway_spec = _service_spec_ps(
        role="gateway", port=gateway_port, working_directory=tmp_path
    )
    edge_spec = _service_spec_ps(
        role="edge",
        port=edge_port,
        working_directory=tmp_path,
        health_body='{"ok":true,"service":"spiral-edge"}',
    )
    command = (
        f". {ps_quote(LAUNCHER)}; "
        f"$spec = {gateway_spec}; $edgeSpec = {edge_spec}; "
        + _mock_identity_ps("oldLive", 1301, "old-gateway")
        + _mock_identity_ps("newLive", 1302, "new-gateway")
        + _mock_identity_ps("edgeLive", 2301, "owned-edge")
        + "$gatewayRecord = New-ServiceStateRecord -Specification $spec "
        "-OwnershipRecord $oldLive "
        f"-StdoutPath {ps_quote(old_stdout)} "
        f"-StderrPath {ps_quote(old_stderr)}; "
        "$edgeRecord = New-ServiceStateRecord -Specification $edgeSpec "
        "-OwnershipRecord $edgeLive "
        f"-StdoutPath {ps_quote(edge_stdout)} "
        f"-StderrPath {ps_quote(edge_stderr)}; "
        "$edgeRecord | Add-Member -NotePropertyName metadata "
        "-NotePropertyValue ([pscustomobject]@{ nested=@(@(1,2),@(3,4)) }); "
        "$state = [ordered]@{ schemaVersion=2; gateway=$gatewayRecord; "
        "edge=$edgeRecord; logcatPid=4301; adbPath='C:\\fixture\\adb.exe'; "
        "executablePath='C:\\fixture\\adb.exe'; "
        "normalizedCommandLine='\"C:\\fixture\\adb.exe\" -s emulator-5556 logcat -v time'; "
        "creationDate='2026-07-25T00:00:00.0000000Z'; "
        "creationFileTimeUtc='134294112000000000'; "
        "serial='emulator-5556'; "
        "arguments=@('-s','emulator-5556','logcat','-v','time'); "
        "stdout='C:\\fixture\\capture.log'; stderr='C:\\fixture\\capture.err.log'; "
        "logcatMetadata=[pscustomobject]@{ nested=@([pscustomobject]@{v=1}) } }; "
        f"Write-AtomicState -StatePath {ps_quote(state_path)} -State $state; "
        f"$before = Read-LauncherState -StatePath {ps_quote(state_path)}; "
        "$hooks = @{ "
        f"ObservePort={{ param($observedPort) if ($observedPort -eq {edge_port}) "
        "{ return $edgeLive }; return $oldLive }; "
        "GetProcess={ param($observedPid) return $oldLive }; "
        "StopOwned={ param($records) }; "
        "WaitGone={ param($observedPid,$observedPort) }; "
        "StartService={ param($serviceSpec,$outLog,$errLog) "
        "[IO.File]::WriteAllText($outLog,'fresh stdout'); "
        "[IO.File]::WriteAllText($errLog,'fresh stderr'); "
        "return [pscustomobject]@{ ProcessId=$newLive.ProcessId; "
        "OwnershipRecord=$newLive; Records=@($newLive); "
        "StdoutPath=$outLog; StderrPath=$errLog } }; "
        "WaitHealth={ param($serviceSpec,$outLog,$errLog) return $newLive } }; "
        "$result = Invoke-RestartGatewayTransaction "
        f"-StatePath {ps_quote(state_path)} -Specification $spec "
        f"-RuntimeDirectory {ps_quote(tmp_path)} -EdgePort {edge_port} "
        "-Hooks $hooks; "
        f"$after = Read-LauncherState -StatePath {ps_quote(state_path)}; "
        "[ordered]@{ result=$result; before=$before; after=$after } "
        "| ConvertTo-Json -Depth 16 -Compress"
    )
    completed = run_powershell_command(command)
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    result = payload["result"]
    assert result["gatewayRestarted"] is True
    assert result["previousGatewayPid"] == 1301
    assert result["gatewayPid"] == 1302
    assert result["gatewayOwned"] is True
    assert Path(result["gatewayLog"]).is_file()
    assert Path(result["gatewayErrorLog"]).is_file()
    assert payload["after"]["gateway"]["processId"] == 1302
    assert payload["after"]["edge"] == payload["before"]["edge"]
    for key in (
        "logcatPid",
        "adbPath",
        "executablePath",
        "normalizedCommandLine",
        "creationDate",
        "creationFileTimeUtc",
        "serial",
        "arguments",
        "stdout",
        "stderr",
        "logcatMetadata",
    ):
        assert payload["after"][key] == payload["before"][key]


def test_restart_gateway_start_failure_leaves_gateway_unowned(tmp_path: Path):
    reservation = socket.socket()
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        reservation.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_EXCLUSIVEADDRUSE,
            1,
        )
    reservation.bind(("127.0.0.1", 0))
    gateway_port = int(reservation.getsockname()[1])
    claim_now = tmp_path / "claim-now"
    claim_ready = tmp_path / "claim-ready"
    claimant: subprocess.Popen[str] | None = None
    transaction: subprocess.Popen[str] | None = None
    state_path = tmp_path / "launcher-state.json"
    old_stdout = tmp_path / "old.stdout.log"
    old_stderr = tmp_path / "old.stderr.log"
    old_stdout.touch()
    old_stderr.touch()
    edge_port = 40133
    spec = _service_spec_ps(
        role="gateway", port=gateway_port, working_directory=tmp_path
    )
    try:
        command = (
            f". {ps_quote(LAUNCHER)}; "
            f"$spec = {spec}; "
            + _mock_identity_ps("oldLive", 1401, "old-gateway")
            + "$record = New-ServiceStateRecord -Specification $spec "
            "-OwnershipRecord $oldLive "
            f"-StdoutPath {ps_quote(old_stdout)} "
            f"-StderrPath {ps_quote(old_stderr)}; "
            "$state = [ordered]@{ schemaVersion=2; gateway=$record; edge=$null }; "
            f"Write-AtomicState -StatePath {ps_quote(state_path)} -State $state; "
            "$script:stopRoles=@(); $script:startStateWasNull=$false; "
            "$script:observedClaimantPid=$null; "
            "$hooks = @{ "
            f"ObservePort={{ param($observedPort) if ($observedPort -eq {gateway_port}) "
            "{ return $oldLive }; return $null }; "
            "GetProcess={ param($observedPid) return $oldLive }; "
            "StopOwned={ param($records) "
            "$script:stopRoles += [string]$records[0].role }; "
            "WaitGone={ param($observedPid,$observedPort) }; "
            "StartService={ param($serviceSpec,$outLog,$errLog) "
            f"$during = Read-LauncherState -StatePath {ps_quote(state_path)}; "
            "$script:startStateWasNull = ($null -eq $during.gateway); "
            "if (-not $script:startStateWasNull) { "
            "throw 'gateway was still owned at start boundary' }; "
            f"[IO.File]::WriteAllText({ps_quote(claim_now)},'claim'); "
            "$deadline=[DateTime]::UtcNow.AddSeconds(10); "
            f"while ((-not (Test-Path -LiteralPath {ps_quote(claim_ready)})) "
            "-and [DateTime]::UtcNow -lt $deadline) { "
            "Start-Sleep -Milliseconds 25 }; "
            f"if (-not (Test-Path -LiteralPath {ps_quote(claim_ready)})) "
            "{ throw 'real claimant coordination timeout' }; "
            f"$claimantOwner=Get-TcpListenerOwner -Port {gateway_port}; "
            "if (-not $claimantOwner) { throw 'real claimant was not listening' }; "
            "$script:observedClaimantPid=[int]$claimantOwner.ProcessId; "
            "throw 'deterministic replacement failure after real claimant' }; "
            "WaitHealth={ throw 'health must not run' } }; "
            "try { "
            "Invoke-RestartGatewayTransaction "
            f"-StatePath {ps_quote(state_path)} -Specification $spec "
            f"-RuntimeDirectory {ps_quote(tmp_path)} -EdgePort {edge_port} "
            "-Hooks $hooks; exit 97 "
            "} catch { "
            "if ($_.Exception.Message -notmatch 'replacement failure') { exit 98 }; "
            f"$after = Read-LauncherState -StatePath {ps_quote(state_path)}; "
            "[ordered]@{ stopRoles=$script:stopRoles; "
            "startStateWasNull=$script:startStateWasNull; "
            "observedClaimantPid=$script:observedClaimantPid; "
            "gateway=$after.gateway } "
            "| ConvertTo-Json -Depth 16 -Compress; exit 0 }"
        )
        transaction = subprocess.Popen(
            [
                POWERSHELL,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not claim_now.exists():
            if transaction.poll() is not None:
                raise AssertionError(transaction.stderr.read())
            time.sleep(0.025)
        assert claim_now.exists()

        reservation.close()
        claimant, claimed_port = _start_health_server(
            tmp_path,
            port=gateway_port,
        )
        assert claimed_port == gateway_port
        listener_pid = _netstat_listener_pid(gateway_port)
        assert listener_pid == claimant.pid
        claim_ready.write_text("ready", encoding="ascii")

        stdout, stderr = transaction.communicate(timeout=15)
        assert transaction.returncode == 0, stderr
        payload = json.loads(stdout)
        assert payload == {
            "stopRoles": ["gateway"],
            "startStateWasNull": True,
            "observedClaimantPid": listener_pid,
            "gateway": None,
        }
        assert claimant.poll() is None
        assert _netstat_listener_pid(gateway_port) == listener_pid
        persisted = json.loads(state_path.read_text(encoding="utf-8"))
        assert persisted["gateway"] is None
    finally:
        reservation.close()
        if not claim_ready.exists():
            claim_ready.write_text("ready", encoding="ascii")
        if transaction is not None and transaction.poll() is None:
            transaction.terminate()
            transaction.wait(timeout=10)
        if claimant is not None and claimant.poll() is None:
            claimant.terminate()
            claimant.wait(timeout=10)


def test_restart_gateway_stdout_is_one_json_document():
    accepted = json.dumps(_supported_host_status(), separators=(",", ":"))
    expected = {
        "gatewayRestarted": True,
        "previousGatewayPid": 1501,
        "gatewayPid": 1502,
        "gatewayOwned": True,
        "gatewayLog": r"C:\fixture\gateway.stdout.log",
        "gatewayErrorLog": r"C:\fixture\gateway.stderr.log",
        "edgeIdentityRetained": True,
        "edgePid": 2501,
    }
    encoded = json.dumps(expected, separators=(",", ":"))
    command = (
        f". {ps_quote(LAUNCHER)}; "
        "$RestartGateway=$true; $Doctor=$false; $Capture=$false; "
        "$SkipInstall=$false; "
        f"function Get-WindowsHostStatus {{ return "
        f"({ps_quote(accepted)} | ConvertFrom-Json) }}; "
        "function Assert-SupportedWindowsHost { param($Status) }; "
        "function Get-PythonRuntimeStatus { "
        "return [pscustomobject]@{ compatible=$true } }; "
        "function Invoke-WithLauncherMutex { "
        "param($Mode,$RepositoryRoot,$Operation,$TimeoutMilliseconds); "
        "return (& $Operation) }; "
        "function Invoke-RestartGatewayTransaction { "
        f"return ({ps_quote(encoded)} | ConvertFrom-Json) }}; "
        "Invoke-Launcher"
    )
    completed = run_powershell_command(command)
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    assert len(completed.stdout.splitlines()) == 1
    assert json.loads(completed.stdout) == expected


def test_missing_logcat_pid_is_not_treated_as_a_live_owner(tmp_path: Path):
    """A state file with no recorded logcat must not block -Capture.

    [int]$null is 0, and Windows resolves PID 0 to the System Idle Process, so
    a bare PID lookup reports a "live" owner with an empty executable and
    permanently refuses to replace the state.
    """
    state = tmp_path / "launcher-state.json"
    state.write_text(
        json.dumps({"schemaVersion": 2, "gateway": None, "edge": None}),
        encoding="utf-8",
    )
    completed = run_powershell_command(
        f". {ps_quote(LAUNCHER)}; "
        f"$owner = Test-RecordedLogcatStillOwned -StatePath {ps_quote(state)}; "
        "if ($null -ne $owner) { exit 91 }"
    )
    assert completed.returncode == 0, completed.stderr


def test_recycled_logcat_pid_is_not_treated_as_a_live_owner(tmp_path: Path):
    """A recycled PID belongs to somebody else, so the record is stale."""
    sleeper = subprocess.Popen(
        [POWERSHELL, "-NoProfile", "-Command", "Start-Sleep -Seconds 60"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    state = tmp_path / "launcher-state.json"
    state.write_text(
        json.dumps(
            {
                "schemaVersion": 2,
                "logcatPid": sleeper.pid,
                "adbPath": r"C:\definitely-not-the-live-process.exe",
                "executablePath": r"C:\definitely-not-the-live-process.exe",
                "normalizedCommandLine": "adb.exe -s emulator-5556 logcat -v time",
                "creationDate": "2026-07-30T00:00:00.0000000Z",
                "serial": "emulator-5556",
                "arguments": ["-s", "emulator-5556", "logcat", "-v", "time"],
            }
        ),
        encoding="utf-8",
    )
    try:
        completed = run_powershell_command(
            f". {ps_quote(LAUNCHER)}; "
            f"$owner = Test-RecordedLogcatStillOwned -StatePath {ps_quote(state)}; "
            "if ($null -ne $owner) { exit 92 }"
        )
        assert completed.returncode == 0, completed.stderr
        assert sleeper.poll() is None
    finally:
        sleeper.terminate()
        sleeper.wait(timeout=10)
