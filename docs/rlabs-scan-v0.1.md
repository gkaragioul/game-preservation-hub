# `rlabs-scan` v0.1 — Interface specification

## Purpose

`rlabs-scan` is a planned, standalone Windows command-line tool. It inspects a user-selected Windows executable and produces a local, machine-readable compatibility report. It is not implemented in this repository; this document fixes the first public interface before a dedicated repository is created.

The tool helps turn a basic question — “why does this executable not run here?” — into inspectable facts about its architecture, imports, declared runtime dependencies, and missing local dependencies.

## Scope

Version 0.1 targets Portable Executable (PE) files on Windows. It reads metadata and dependency declarations without executing the target program.

It will identify:

- PE architecture (`x86`, `x64`, `arm64`, or unknown);
- PE subsystem and machine type;
- imported DLL names and delay-loaded DLL names when present;
- common runtime signals for .NET, Visual C++ runtime, DirectX, and Unreal Engine;
- dependency files that are adjacent to the executable when they can be identified without loading code;
- obvious missing imports from configured search locations.

It will not decompile binaries, patch executables, bypass protection, extract game content, inspect live process memory, upload files, or claim that a title is compatible merely because its metadata was read.

## Command

```text
rlabs-scan scan <executable> [--output <report.json>] [--format json] [--search-path <directory>...]
```

- `<executable>` is a local `.exe` file.
- `--output` writes the JSON result to a chosen path; without it, JSON is written to standard output.
- `--format json` is the only v0.1 output format and is retained to make the interface explicit.
- `--search-path` adds read-only locations used when checking declared DLL names. The executable's directory is always searched first.

Exit codes:

| Code | Meaning |
| --- | --- |
| `0` | Scan completed; the result may still contain warnings or missing dependencies. |
| `2` | Invalid arguments or target path. |
| `3` | Target is unreadable or not a supported PE file. |
| `4` | Output could not be written. |
| `5` | Unexpected scanner failure. |

## Output contract

The scan result is a discovery document, not automatically a published compatibility report. It contains an `observations` section with deterministic inspection results and a `compatibility` skeleton that maps to [`../compatibility/schema.json`](../compatibility/schema.json).

```json
{
  "scanner": { "name": "rlabs-scan", "version": "0.1.0" },
  "target": { "path": "C:\\Games\\Example\\Example.exe", "sha256": "…" },
  "observations": {
    "fileFormat": "pe",
    "architecture": "x64",
    "subsystem": "windows-gui",
    "imports": ["KERNEL32.dll", "VCRUNTIME140.dll"],
    "delayImports": [],
    "runtimeSignals": ["msvc-runtime"],
    "missingDependencies": ["VCRUNTIME140.dll"]
  },
  "compatibility": {
    "id": "example-windows-x64",
    "software": { "title": "Example", "kind": "application" },
    "environment": { "operatingSystem": "Windows", "architecture": "x64" },
    "assessment": {
      "status": "research",
      "summary": "Generated from static inspection; runtime behavior has not been tested."
    },
    "evidence": { "source": "rlabs-scan 0.1.0", "observedOn": "YYYY-MM-DD" }
  }
}
```

Before committing a report, a contributor replaces the generated placeholder title, date, and summary with verified test information. The scanner must preserve raw observations even when it cannot confidently classify a runtime.

## Privacy and safety

Scanning is local by default. `rlabs-scan` makes no network request, sends no hash or file path to a remote service, and never runs the inspected executable. Output may reveal local paths, executable names, hashes, and DLL names; users review and redact those fields before sharing a report.

## Implementation constraints for the future repository

- Use a read-only PE parser; do not invoke Windows loader APIs on the target.
- Keep the parser and JSON writer independently testable with benign PE fixtures.
- Test malformed, truncated, non-PE, x86, x64, and arm64 input samples.
- Validate generated `compatibility` output against the hub schema in continuous integration.
- Publish the scanner under its own repository only after this output contract remains stable through real test reports.
