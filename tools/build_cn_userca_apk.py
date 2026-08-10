#!/usr/bin/env python3
"""Build the deterministic CN APK variant that trusts Android user CAs."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
import zlib
from pathlib import Path
from typing import NoReturn, Sequence


sys.path.insert(0, str(Path(__file__).resolve().parent))

import cn_client_patch  # noqa: E402
import cocos_jsc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
# The derivation starts at the immutable published archive. An earlier chain
# sourced a locally rebuilt "partsuit" APK that silently replaced the shipped
# empty data/PartSuit table with 64 filler bytes, which decodes as protobuf
# wire type 7 and aborts the client boot sequence.
DEFAULT_SOURCE = ROOT / "cn_9game.apk"
DEFAULT_OUTPUT = (
    ROOT / "patched" / "LuoXuanWarrior_cn_partsuit_userca_debug.apk"
)
DEFAULT_KEYSTORE = ROOT / "build" / "debug.keystore"
DEFAULT_SDK_ROOT = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "SpiralWarrior"
    / "AndroidSdk"
)

SOURCE_SHA256 = (
    "4e02fbc9adf4e31051140194b55b8004"
    "c1272c74d76293208d6b1809c77358d5"
)
KEYSTORE_SHA256 = (
    "7ae2671c9d4b3a35d1197cd7ca4c417a"
    "cc2398a39da2e59e25b7df65098c266b"
)
SIGNER_SHA256 = (
    "7ae2aa16d63e204b4a6ebe2aec06f49e"
    "57e13a9c8107cd6c68db37d9d86f0233"
)
COMPILED_MEMBER_SHA256 = (
    "be19b1947c55c92325d53643a5a4aaed"
    "16f4b241dd7a7c9a522d25287107cec4"
)
OUTPUT_SHA256 = (
    "341795584abcbd0997f1e396f56c3de7"
    "e90ff889768866eac4f04fe442415414"
)

PACKAGE = "com.dianhun.lxys.aligames"
VERSION_CODE = "1004"
VERSION_NAME = "1.1.0.133"
MIN_SDK = "21"
TARGET_SDK = "30"
BUILD_TOOLS_VERSION = "30.0.3"
TARGET_MEMBER = "res/xml/lebian_network_security_config.xml"
BUNDLE_MEMBER = "assets/assets/main/index.jsc"
BUNDLE_MEMBER_SHA256 = (
    "0770fe5fdcafde95ccb90b833034078c"
    "e358c74e223b9040c32b4cc0ec050880"
)
MANIFEST_MEMBER = "META-INF/MANIFEST.MF"
SIGNATURE_BLOCK_SUFFIXES = (".SF", ".RSA", ".DSA", ".EC")


def is_signature_member(name: str) -> bool:
    """Report whether a ZIP member belongs to the archive's JAR signature."""
    if name == MANIFEST_MEMBER:
        return True
    if not name.startswith("META-INF/"):
        return False
    return name.upper().endswith(SIGNATURE_BLOCK_SUFFIXES)

NETWORK_SECURITY_XML = """<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
  <base-config cleartextTrafficPermitted="true">
    <trust-anchors>
      <certificates src="system" />
      <certificates src="user" />
    </trust-anchors>
  </base-config>
</network-security-config>
"""

MINIMAL_MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.dianhun.lxys.aligames">
  <uses-sdk android:minSdkVersion="21" android:targetSdkVersion="30" />
  <application
      android:networkSecurityConfig="@xml/lebian_network_security_config" />
</manifest>
"""


class BuildError(RuntimeError):
    """An expected, user-actionable builder failure."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def fail(message: str) -> NoReturn:
    raise BuildError(message)


def require_file(path: Path, description: str) -> None:
    if not path.is_file():
        fail(f"{description} is missing: {path}")


def require_hash(
    path: Path,
    expected: str,
    description: str,
) -> str:
    require_file(path, description)
    actual = sha256_file(path)
    if actual != expected:
        fail(
            f"{description} SHA-256 mismatch: expected {expected}, "
            f"got {actual} ({path})"
        )
    return actual


def run_checked(
    arguments: Sequence[str | os.PathLike[str]],
    description: str,
    *,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    encoded = [os.fspath(argument) for argument in arguments]
    try:
        completed = subprocess.run(
            encoded,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            env=environment,
        )
    except OSError as exc:
        fail(f"{description} could not start: {exc}")
    if completed.returncode != 0:
        fail(
            f"{description} failed with exit code {completed.returncode}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed


def resolve_java17() -> tuple[Path, dict[str, str]]:
    candidates: list[Path] = []
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        candidates.append(Path(java_home) / "bin" / "java.exe")
    java_on_path = shutil.which("java")
    if java_on_path:
        candidates.append(Path(java_on_path))
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    candidates.extend(
        sorted(
            (
                program_files / "Eclipse Adoptium"
            ).glob("jdk-17*\\bin\\java.exe"),
            reverse=True,
        )
    )

    seen: set[str] = set()
    for candidate in candidates:
        normalized = os.path.normcase(os.path.abspath(candidate))
        if normalized in seen or not candidate.is_file():
            continue
        seen.add(normalized)
        completed = run_checked([candidate, "-version"], "Java version probe")
        version_text = completed.stdout + completed.stderr
        match = re.search(r'version\s+"(?P<major>\d+)', version_text)
        if not match or match.group("major") != "17":
            continue
        resolved = candidate.resolve()
        home = resolved.parent.parent
        keytool = resolved.with_name("keytool.exe")
        if not keytool.is_file():
            continue
        environment = os.environ.copy()
        environment["JAVA_HOME"] = os.fspath(home)
        environment["PATH"] = (
            os.fspath(resolved.parent)
            + os.pathsep
            + environment.get("PATH", "")
        )
        return resolved, environment
    fail("Java 17 with keytool.exe is required")


def require_runtime() -> None:
    if sys.version_info[:2] != (3, 12):
        fail(
            "Python 3.12 is required; got "
            f"{sys.version_info.major}.{sys.version_info.minor}"
        )
    compile_version = getattr(zlib, "ZLIB_VERSION", "")
    runtime_version = getattr(zlib, "ZLIB_RUNTIME_VERSION", compile_version)
    if compile_version != "1.3.1" or runtime_version != "1.3.1":
        fail(
            "zlib 1.3.1 is required; got "
            f"compile={compile_version!r} runtime={runtime_version!r}"
        )


def property_value(path: Path, key: str) -> str | None:
    require_file(path, f"{path.parent.name} metadata")
    for line in path.read_text(encoding="utf-8").splitlines():
        name, separator, value = line.partition("=")
        if separator and name.strip() == key:
            return value.strip()
    return None


def resolve_toolchain(sdk_root: Path) -> dict[str, Path]:
    build_tools = sdk_root / "build-tools" / BUILD_TOOLS_VERSION
    platform = sdk_root / "platforms" / "android-30"
    if property_value(build_tools / "source.properties", "Pkg.Revision") != (
        BUILD_TOOLS_VERSION
    ):
        fail(f"build-tools must be exactly {BUILD_TOOLS_VERSION}: {build_tools}")
    if property_value(platform / "source.properties", "AndroidVersion.ApiLevel") != (
        "30"
    ):
        fail(f"Android platform must be exactly API 30: {platform}")
    tools = {
        "aapt2": build_tools / "aapt2.exe",
        "zipalign": build_tools / "zipalign.exe",
        "apksigner": build_tools / "apksigner.bat",
        "android_jar": platform / "android.jar",
    }
    for name, path in tools.items():
        require_file(path, name)
    return tools


def export_and_validate_signer(
    java: Path,
    environment: dict[str, str],
    keystore: Path,
    temporary: Path,
) -> str:
    signer_der = temporary / "signer.der"
    keytool = java.with_name("keytool.exe")
    run_checked(
        [
            keytool,
            "-exportcert",
            "-alias",
            "androiddebugkey",
            "-keystore",
            keystore,
            "-storepass",
            "android",
            "-file",
            signer_der,
        ],
        "debug signer certificate export",
        environment=environment,
    )
    actual = sha256_file(signer_der)
    if actual != SIGNER_SHA256:
        fail(
            f"signer certificate SHA-256 mismatch: expected {SIGNER_SHA256}, "
            f"got {actual}"
        )
    return actual


def compile_network_security_member(
    temporary: Path,
    tools: dict[str, Path],
    environment: dict[str, str],
) -> bytes:
    resource_directory = temporary / "res" / "xml"
    resource_directory.mkdir(parents=True)
    resource = resource_directory / "lebian_network_security_config.xml"
    resource.write_text(NETWORK_SECURITY_XML, encoding="utf-8", newline="\n")
    manifest = temporary / "AndroidManifest.xml"
    manifest.write_text(MINIMAL_MANIFEST, encoding="utf-8", newline="\n")
    compiled = temporary / "compiled.zip"
    config_apk = temporary / "config.apk"
    run_checked(
        [
            tools["aapt2"],
            "compile",
            "--dir",
            temporary / "res",
            "-o",
            compiled,
        ],
        "network-security resource compilation",
        environment=environment,
    )
    run_checked(
        [
            tools["aapt2"],
            "link",
            "-I",
            tools["android_jar"],
            "--manifest",
            manifest,
            "--min-sdk-version",
            MIN_SDK,
            "--target-sdk-version",
            TARGET_SDK,
            "-o",
            config_apk,
            compiled,
        ],
        "network-security resource link",
        environment=environment,
    )
    try:
        with zipfile.ZipFile(config_apk) as archive:
            matches = [
                info
                for info in archive.infolist()
                if info.filename == TARGET_MEMBER
            ]
            if len(matches) != 1:
                fail(
                    f"compiled APK must contain exactly one {TARGET_MEMBER}; "
                    f"found {len(matches)}"
                )
            compiled_member = archive.read(matches[0])
    except zipfile.BadZipFile as exc:
        fail(f"aapt2 produced an invalid config APK: {exc}")
    actual = hashlib.sha256(compiled_member).hexdigest()
    if actual != COMPILED_MEMBER_SHA256:
        fail(
            "compiled network-security member SHA-256 mismatch: expected "
            f"{COMPILED_MEMBER_SHA256}, got {actual}"
        )
    return compiled_member


def rewrite_source(
    source_path: Path,
    destination: Path,
    replacements: dict[str, bytes],
) -> None:
    try:
        with zipfile.ZipFile(source_path, "r") as source:
            infos = source.infolist()
            counts = {
                name: sum(info.filename == name for info in infos)
                for name in (*replacements, MANIFEST_MEMBER)
            }
            invalid = {name: count for name, count in counts.items() if count != 1}
            if invalid:
                details = ", ".join(
                    f"{name}={count}" for name, count in invalid.items()
                )
                fail(f"source APK has missing or duplicate required members: {details}")
            blocks = sorted(
                info.filename
                for info in infos
                if info.filename != MANIFEST_MEMBER
                and is_signature_member(info.filename)
            )
            if not any(name.upper().endswith(".SF") for name in blocks):
                fail("source APK has no JAR signature file to replace")

            with zipfile.ZipFile(
                destination,
                "w",
                compression=zipfile.ZIP_STORED,
                allowZip64=True,
            ) as rewritten:
                rewritten.comment = source.comment
                for info in infos:
                    if is_signature_member(info.filename):
                        continue
                    data = replacements.get(info.filename)
                    if data is None:
                        data = source.read(info)
                    preserved = copy.copy(info)
                    rewritten.writestr(
                        preserved,
                        data,
                        compress_type=info.compress_type,
                        compresslevel=6 if info.compress_type == zipfile.ZIP_DEFLATED else None,
                    )
    except zipfile.BadZipFile as exc:
        fail(f"source APK is not a valid ZIP archive: {exc}")


def sign_apk(
    unsigned: Path,
    signed: Path,
    tools: dict[str, Path],
    keystore: Path,
    environment: dict[str, str],
    temporary: Path,
) -> None:
    aligned = temporary / "aligned.apk"
    run_checked(
        [tools["zipalign"], "-f", "-p", "4", unsigned, aligned],
        "APK alignment",
        environment=environment,
    )
    run_checked(
        [
            tools["apksigner"],
            "sign",
            "--ks",
            keystore,
            "--ks-key-alias",
            "androiddebugkey",
            "--ks-pass",
            "pass:android",
            "--key-pass",
            "pass:android",
            "--v1-signing-enabled",
            "true",
            "--v2-signing-enabled",
            "true",
            "--v3-signing-enabled",
            "true",
            "--v4-signing-enabled",
            "false",
            "--out",
            signed,
            aligned,
        ],
        "APK signing",
        environment=environment,
    )


def verify_output(
    apk: Path,
    tools: dict[str, Path],
    environment: dict[str, str],
) -> None:
    require_hash(apk, OUTPUT_SHA256, "derived CN APK")
    expected_members = {
        TARGET_MEMBER: COMPILED_MEMBER_SHA256,
        BUNDLE_MEMBER: BUNDLE_MEMBER_SHA256,
    }
    digests: dict[str, str] = {}
    try:
        with zipfile.ZipFile(apk) as archive:
            for name in expected_members:
                members = [
                    info for info in archive.infolist() if info.filename == name
                ]
                if len(members) != 1:
                    fail(
                        f"derived APK must contain exactly one {name}; "
                        f"found {len(members)}"
                    )
                digests[name] = hashlib.sha256(archive.read(members[0])).hexdigest()
    except zipfile.BadZipFile as exc:
        fail(f"derived APK is not a valid ZIP archive: {exc}")
    for name, expected in expected_members.items():
        if digests[name] != expected:
            fail(
                f"derived APK {name} SHA-256 mismatch: expected "
                f"{expected}, got {digests[name]}"
            )
    run_checked(
        [tools["zipalign"], "-c", "-p", "4", apk],
        "APK alignment verification",
        environment=environment,
    )
    signature = run_checked(
        [
            tools["apksigner"],
            "verify",
            "--verbose",
            "--print-certs",
            apk,
        ],
        "APK signature verification",
        environment=environment,
    )
    signature_text = signature.stdout + signature.stderr
    for scheme in ("v1", "v2", "v3"):
        if not re.search(
            rf"Verified using {scheme} scheme .*:\s*true",
            signature_text,
            flags=re.IGNORECASE,
        ):
            fail(f"derived APK is not verified with {scheme} signing")
    signer_match = re.search(
        r"Signer #1 certificate SHA-256 digest:\s*([0-9a-f]{64})",
        signature_text,
        flags=re.IGNORECASE,
    )
    if not signer_match or signer_match.group(1).lower() != SIGNER_SHA256:
        fail("derived APK signer certificate SHA-256 does not match")

    badging = run_checked(
        [tools["aapt2"], "dump", "badging", apk],
        "APK package metadata verification",
        environment=environment,
    ).stdout
    expected_patterns = (
        rf"package:\s+name='{re.escape(PACKAGE)}'",
        rf"\bversionCode='{VERSION_CODE}'",
        rf"\bversionName='{re.escape(VERSION_NAME)}'",
        rf"(?m)^sdkVersion:'{MIN_SDK}'$",
        rf"(?m)^targetSdkVersion:'{TARGET_SDK}'$",
    )
    for pattern in expected_patterns:
        if not re.search(pattern, badging):
            fail(f"derived APK metadata does not match pattern {pattern!r}")

    tree = run_checked(
        [
            tools["aapt2"],
            "dump",
            "xmltree",
            apk,
            "--file",
            TARGET_MEMBER,
        ],
        "network-security XML verification",
        environment=environment,
    ).stdout
    if tree.count("E: certificates") != 2:
        fail("derived APK network-security XML must contain two trust anchors")
    for anchor in ("system", "user"):
        if not re.search(
            rf'A:\s+src="{anchor}"',
            tree,
            flags=re.IGNORECASE,
        ):
            fail(
                "derived APK network-security XML is missing "
                f"the {anchor!r} trust anchor"
            )


def build_offline_bundle(source_path: Path) -> bytes:
    """Recover, patch, and repack the Cocos bundle from the source archive."""
    try:
        with zipfile.ZipFile(source_path) as archive:
            packed = archive.read(BUNDLE_MEMBER)
    except KeyError:
        fail(f"source APK is missing {BUNDLE_MEMBER}")
    except zipfile.BadZipFile as exc:
        fail(f"source APK is not a valid ZIP archive: {exc}")
    try:
        patched = cn_client_patch.apply_offline_patches(
            cocos_jsc.unpack_jsc(packed, cocos_jsc.bundle_key())
        )
    except cn_client_patch.PatchError as exc:
        fail(f"offline client patch failed: {exc}")
    return cocos_jsc.pack_jsc(patched, cocos_jsc.bundle_key())


def build_result(
    source: Path,
    output: Path,
    signer_digest: str,
) -> dict[str, object]:
    return {
        "source": os.fspath(source),
        "output": os.fspath(output),
        "sourceSha256": SOURCE_SHA256,
        "outputSha256": OUTPUT_SHA256,
        "compiledMemberSha256": COMPILED_MEMBER_SHA256,
        "bundleMemberSha256": BUNDLE_MEMBER_SHA256,
        "signerSha256": signer_digest,
        "package": PACKAGE,
        "ready": True,
    }


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the deterministic user-CA-trusting CN APK"
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sdk-root", type=Path, default=DEFAULT_SDK_ROOT)
    parser.add_argument("--keystore", type=Path, default=DEFAULT_KEYSTORE)
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    source = arguments.source.resolve()
    output = arguments.output.resolve()
    sdk_root = arguments.sdk_root.resolve()
    keystore = arguments.keystore.resolve()

    require_runtime()
    if source == output:
        fail("source and output APK paths must be different")
    tools = resolve_toolchain(sdk_root)
    java, environment = resolve_java17()

    if output.is_file():
        try:
            verify_output(output, tools, environment)
        except BuildError as exc:
            print(
                f"existing derived APK is not reusable: {exc}",
                file=sys.stderr,
            )
        else:
            print(
                json.dumps(
                    build_result(source, output, SIGNER_SHA256),
                    separators=(",", ":"),
                )
            )
            return 0

    require_hash(source, SOURCE_SHA256, "source CN APK")
    require_hash(keystore, KEYSTORE_SHA256, "debug keystore")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".spiral-cn-userca-",
        dir=output.parent,
    ) as temporary_name:
        temporary = Path(temporary_name)
        signer_digest = export_and_validate_signer(
            java,
            environment,
            keystore,
            temporary,
        )
        compiled_member = compile_network_security_member(
            temporary,
            tools,
            environment,
        )

        unsigned = temporary / "rewritten.apk"
        signed = temporary / "signed.apk"
        rewrite_source(
            source,
            unsigned,
            {
                TARGET_MEMBER: compiled_member,
                BUNDLE_MEMBER: build_offline_bundle(source),
            },
        )
        sign_apk(
            unsigned,
            signed,
            tools,
            keystore,
            environment,
            temporary,
        )
        verify_output(signed, tools, environment)
        os.replace(signed, output)

    print(
        json.dumps(
            build_result(source, output, signer_digest),
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BuildError as exc:
        print(f"CN user-CA builder failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
