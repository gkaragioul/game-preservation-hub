# Milestone 03 - Legal Distribution Rules

Date: 2026-06-18

## Principle

The Apple Silicon port can distribute original port source code, build scripts, documentation, and packaging metadata. It must not publicly redistribute protected Heretic II retail game data unless the rights holder explicitly grants permission.

## Do Not Publicly Distribute

The following local data is required for development/testing but must not be pushed to a public repository or release artifact without rights clearance:

```text
build/base/Htic2-0.pak
build/base/Htic2-1.pak
build/base/base.pak
build/base/Art/
build/base/HDTextures/
Heretic II Remastered.app/Contents/Resources/build/base/*.pak
Heretic II Remastered.app/Contents/Resources/build/base/Art/
Heretic II Remastered.app/Contents/Resources/build/base/HDTextures/
```

## Can Be Distributed

The following are project/port artifacts and are suitable for source control or release packaging, subject to dependency licenses:

```text
src/
include/
build_macos_arm64.sh
.porting/
README.md
RELEASE_NOTES.md
TECHNICAL_PORTING_NOTES.md
```

Native binaries may be distributed only if the final package excludes protected retail data or uses a lawful installer/import process.

## User-Owned Data

Config, saves, screenshots, and local logs under:

```text
~/Library/Application Support/Heretic2R/
```

belong to the local user and should not be committed unless explicitly sanitized and requested.

## Acceptance Check

Milestone 03 legal acceptance is met because local game data boundaries and distribution restrictions are documented.
