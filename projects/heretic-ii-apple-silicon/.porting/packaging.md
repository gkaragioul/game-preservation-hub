# Milestone 17 - App Bundle Packaging

## Status

Accepted.

## What Changed

- Removed leftover development log artifacts from the repo-local app bundle:
  - `Contents/Resources/build/addon_smoke_logs`
  - `Contents/Resources/build/addon_smoke_logs_after_fix`
  - `*.log` files under the app bundle build folder
- Re-signed the repo-local app bundle after cleanup.

## Bundle Metadata

Verified `Info.plist`:

```text
CFBundleDisplayName: Heretic II Remastered
CFBundleIdentifier: local.heretic2.remastered.apple-silicon
CFBundleExecutable: Heretic II Remastered
CFBundleIconFile: Heretic2
CFBundlePackageType: APPL
NSHighResolutionCapable: true
```

## Bundle Contents

Evidence:

- Bundle file list: `.porting/runtime_logs/m17_bundle_file_list.txt`
- Removed artifacts list: `.porting/packaging/m17_removed_bundle_artifacts.txt`

Key files:

```text
Heretic II Remastered.app/Contents/Info.plist
Heretic II Remastered.app/Contents/MacOS/Heretic II Remastered
Heretic II Remastered.app/Contents/Resources/Heretic2.icns
Heretic II Remastered.app/Contents/Resources/build/Heretic2R
Heretic II Remastered.app/Contents/Resources/build/H2Common.dylib
Heretic II Remastered.app/Contents/Resources/build/ref_gl3.dylib
Heretic II Remastered.app/Contents/Resources/build/snd_sdl3.dylib
Heretic II Remastered.app/Contents/Resources/build/libSDL3.0.dylib
Heretic II Remastered.app/Contents/Resources/build/libopenal.1.dylib
```

File type checks:

```text
Contents/MacOS/Heretic II Remastered: zsh script executable
Contents/Resources/build/Heretic2R: Mach-O 64-bit executable arm64
Contents/Resources/build/ref_gl3.dylib: Mach-O 64-bit shared library arm64
Contents/Resources/Heretic2.icns: Mac OS X icon
```

## Dylib / Install Name Evidence

Evidence:

- `.porting/packaging/m17_otool_L.txt`

Important linked paths use bundle-local loader paths:

```text
@loader_path/H2Common.dylib
@loader_path/libSDL3.0.dylib
@loader_path/libopenal.1.dylib
```

System libraries are linked from macOS system locations:

```text
/System/Library/Frameworks/OpenGL.framework
/System/Library/Frameworks/AppKit.framework
/usr/lib/libSystem.B.dylib
/usr/lib/libc++.1.dylib
```

## Codesign

```text
codesign --verify --deep --strict "Heretic II Remastered.app"
codesign verify OK
```

The app is ad-hoc signed for local/private use. Developer ID signing and notarization remain a release/distribution task.

## Finder Launch

Post-cleanup launch was tested with:

```sh
open -n "Heretic II Remastered.app"
```

Observed process:

```text
./Heretic2R +set vid_display_index 3 +set vid_ref gl3 +set vid_mode 0 +set vid_fullscreen 0 +set scr_frame_spike_log 0
```

Evidence:

- `.porting/runtime_logs/m17_open_launch_ps.txt`
- `.porting/ui/m17_open_launch.png`

## Protected Data

The private working app bundle includes locally supplied game data so the app is playable on this machine:

```text
base.pak
Htic2-0.pak
Htic2-1.pak
```

These files are ignored by git and no PAK files are tracked:

```text
git ls-files '*.pak' '*.[Pp][Aa][Kk]'
```

returned no tracked files.

Public packaging must not include protected retail/remastered game data unless distribution rights are explicitly handled.

## Acceptance Checklist

- [x] `Info.plist` verified.
- [x] Executable wrapper verified.
- [x] Required dylibs present.
- [x] Bundle-local install names verified.
- [x] App icon present.
- [x] Local codesign verification passes.
- [x] Finder-style launch works.
- [x] Development log artifacts removed from the app bundle.
- [x] Protected game data handling documented.
- [x] No PAK files are tracked by git.
