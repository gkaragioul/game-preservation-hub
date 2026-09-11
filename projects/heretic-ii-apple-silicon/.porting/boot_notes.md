# Milestone 04 - Boot To macOS Window

Date: 2026-06-18

## Launch Paths

Supported local launch methods:

```sh
open -n "Heretic II Remastered.app"
```

```sh
./build/Heretic2R +set vid_ref gl3 +set vid_mode 0 +set vid_fullscreen 0
```

## Expected Runtime

| Check | Expected |
|---|---|
| Architecture | Native arm64, no Rosetta |
| Renderer | `ref_gl3.dylib` |
| OpenGL version | macOS OpenGL 4.1 Apple compatibility layer |
| Window mode | SDL3/Cocoa window |
| App bundle data path | `Heretic II Remastered.app/Contents/Resources/build/` |
| Quit/relaunch | Supported |

## Current Evidence

| Evidence | Path |
|---|---|
| Build log | `.porting/build_logs/latest_build.log` |
| Boot log | `.porting/runtime_logs/boot.log` |
| Main menu screenshot | `.porting/screenshots/menu_main.jpg` |
| GL3 gameplay screenshot | `.porting/screenshots/gl3_ssdocks_baseline.jpg` |

## Known Caveats

- The active OpenGL runtime reports `GL_VERSION: 4.1 Metal - 90.5`; this is Apple's OpenGL compatibility layer, not the app's Metal renderer.
- MP4/HD cinematic playback is not part of this boot gate.

## Acceptance Check

Milestone 04 passes when the app launches natively, creates a real macOS window, loads `ref_gl3.dylib`, and produces menu/gameplay output without Rosetta.
