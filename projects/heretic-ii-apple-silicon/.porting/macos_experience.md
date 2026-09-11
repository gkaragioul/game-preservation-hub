# Milestone 16 - macOS Experience Pass

## Status

Accepted.

## What Changed

- Updated the repo-local `Launch Heretic II Remastered.command` helper so it no longer hard-forces `vid_maxfps 60`.
- The helper now matches the app bundle launcher more closely:
  - display 3
  - GL3 renderer
  - desktop/windowed mode
  - no frame-spike logging by default
- Updated technical notes to describe the current profile-driven frame cap behavior.

## App Metadata

Info.plist values verified:

```text
CFBundleDisplayName: Heretic II Remastered
CFBundleIdentifier: local.heretic2.remastered.apple-silicon
CFBundleExecutable: Heretic II Remastered
CFBundleIconFile: Heretic2
NSHighResolutionCapable: true
ApplePressAndHoldEnabled: false
```

## Launch Behavior

Finder-style launch was tested with:

```sh
open -n "Heretic II Remastered.app"
```

Observed process:

```text
./Heretic2R +set vid_display_index 3 +set vid_ref gl3 +set vid_mode 0 +set vid_fullscreen 0 +set scr_frame_spike_log 0
```

The app opened on the 1920x1080 LG UltraGear display and showed the correct macOS menu bar app name/window title.

## Runtime Evidence

- Direct bundle runtime log: `.porting/runtime_logs/m16_bundle_direct_display3.log`
- Direct bundle screenshot: `.porting/ui/m16_bundle_direct.png`
- Finder-style launch process log: `.porting/runtime_logs/m16_open_launch_ps.txt`
- Finder-style launch screenshot: `.porting/ui/m16_open_launch.png`

Runtime proof:

```text
Refresh: OpenGL 4.1
Window display target: 3
Display refresh 144.0 Hz: profile 1, vid_maxfps 60, cl_maxfps 60
Window drawable: requested 1920x1080, drawable 1920x1018
GL_VERSION: 4.1 Metal - 90.5
```

## Signing And Gatekeeper

```text
codesign --verify --deep --strict "Heretic II Remastered.app"
codesign verify OK
```

Gatekeeper `spctl` rejects the app because this is an ad-hoc signed private local build, not a Developer ID signed and notarized public build. That is expected for the current stage and should be handled in the packaging/release milestones.

## Config Path

User config path verified:

```text
/Users/georgekarangioules/Library/Application Support/Heretic2R/base
```

The folder contains `config.cfg`, `configs`, `console_history.txt`, `console_log.txt`, `save`, and `screenshots`.

## CPU Observation

Short active-menu process sample:

```text
./Heretic2R  27.2% CPU  1.3% MEM
```

This was an active 60 FPS menu render sample, not a paused/background-idle sample.

## Acceptance Checklist

- [x] App name is correct.
- [x] App icon is present.
- [x] Dock/Finder-style launch works from the repo-local app bundle.
- [x] Menu bar shows the correct app name.
- [x] Windowed launch works on the required 1080p display.
- [x] Fullscreen/windowed controls are configured through SDL/app settings.
- [x] Resize behavior remains stable from prior display tests.
- [x] Config path is correct under Application Support.
- [x] Active menu CPU sample was captured.
- [x] App bundle signature verifies locally.
- [x] Gatekeeper notarization gap is documented for packaging/release.
