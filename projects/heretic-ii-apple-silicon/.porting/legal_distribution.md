# Legal Distribution Notes

Date: 2026-06-18

## Summary

This repository may contain source code, compatibility code, build scripts, project documentation, and local development notes for the Apple Silicon port.

It must not publicly distribute protected Heretic II retail data, remastered PAKs, HD textures, videos, generated app bundles, or generated builds containing those assets unless rights clearance is explicitly obtained.

## Do Not Commit Or Publish

```text
build/
*.app/
release/
*.dmg
*.zip
*.7z
base/*.pak
base/HDTextures/
base/Art/
base/HDVideos/
Heretic II Remastered.app/
```

Important local runtime files that must remain user-supplied:

```text
Htic2-0.pak
Htic2-1.pak
base.pak
HDTextures/
HDVideos/
```

## Suitable For Repository

```text
src/
include/
build_macos_arm64.sh
README.md
RELEASE_NOTES.md
TECHNICAL_PORTING_NOTES.md
.porting/
```

Native binaries may be shared only through a lawful distribution flow that excludes protected game data or imports it from a user's legally owned copy.

## Public Wording

Use wording such as:

> This project requires a legally owned copy of Heretic II and compatible remastered assets supplied by the user. Protected game data is not included.

Avoid wording that implies the repository distributes the full commercial game.

## Acceptance Check

M22 legal distribution criteria are met when README/release docs explain the user-supplied data requirement and `.gitignore` excludes generated builds, app bundles, archives, and packaged deliverables.
