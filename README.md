# Heretic II Apple Silicon

Native macOS Apple Silicon port and app packaging work for **Heretic II Remastered**, based on the Heretic2R source port and the Spacefarer Remastered asset/runtime direction.

This repository tracks the source, macOS compatibility work, build scripts, and project notes for the Apple Silicon version. It does **not** store the generated `.app` bundle or proprietary game-data PAK files.

![Heretic II Remastered](Logo.png)

## Current State

Version `1.0` is a playable native arm64 build for Apple Silicon Macs.

Tested target:

- macOS on Apple Silicon
- Apple M4 GPU
- SDL3 Cocoa window/input
- SDL3/CoreAudio sound
- OpenGL 4.1 Core Profile through Apple's OpenGL-over-Metal stack
- Self-contained `.app` packaging outside git

The current build can launch, reach the menu, enter gameplay, render the GL3 remastered path, play audio, save configuration under the user's Application Support folder, and run in resizable windowed mode.

## Highlights

- Native `arm64` executable and dynamic libraries.
- macOS/POSIX compatibility layer for the original Windows-oriented code.
- SDL3 video, input, gamepad, and CoreAudio backend integration.
- GL3 renderer adapted to macOS OpenGL 4.1.
- High-refresh display support with refresh-aware frame caps.
- Two simplified graphics profiles:
  - **Full Power**: full remastered visuals, targets the monitor refresh up to what the machine/display can handle.
  - **Battery Saver**: lighter visuals, caps at 72 FPS, and automatically clamps to 60 FPS on 60 Hz Macs.
- Custom max FPS override in the graphics options.
- Performance overlay for FPS, frame time, GPU time, CPU, memory, render stats, particles, and target health.
- Improved audio callback safety to avoid stale-buffer crackles during underruns.
- App bundle launch wrapper with bundle-local runtime paths.
- Disable macOS press-and-hold accent picker while playing.

## Repository Contents

- `src/` - engine, client, renderer, game, sound, platform, and tool source.
- `include/` - compatibility and third-party headers used by the port.
- `lib/` - small local library/import assets used by the project.
- `addons/` - add-on/map support files retained with the project.
- `build_macos_arm64.sh` - native Apple Silicon build script.
- `TECHNICAL_PORTING_NOTES.md` - deeper implementation notes and verification history.
- `Logo.png`, `CorvusNight.png`, `EnterThePalace.png`, `HereticVideoOverLay.png` - project images used by the README and documentation.

Generated directories such as `build/` and `Heretic II Remastered.app/` are ignored intentionally.

## Game Data

Heretic II requires original game data. This repository does not include proprietary retail or remastered PAK files.

Expected runtime data, placed under the app/build `base/` directory:

- `Htic2-0.pak`
- `Htic2-1.pak`
- `base.pak` for remastered assets where available
- Optional `HDTextures/` and HD video folders

Use data from a legally owned copy of Heretic II and the appropriate remastered asset package.

## Building

Install dependencies with Homebrew:

```sh
brew install sdl3 openal-soft
```

Build the native Apple Silicon runtime:

```sh
./build_macos_arm64.sh
```

The script produces arm64 binaries under `build/`, including:

- `Heretic2R`
- `H2Common.dylib`
- `ref_gl3.dylib`
- `snd_sdl3.dylib`
- `base/Player.dylib`
- `base/Client Effects.dylib`
- `base/gamex86.dylib`

## Running Locally

After building and placing required game data in `build/base/`, run:

```sh
./build/Heretic2R +set vid_ref gl3 +set vid_mode 0 +set vid_fullscreen 0
```

The packaged app wrapper uses the same runtime and launches the GL3 renderer by default.

## Graphics Profiles

The video settings menu now exposes two user-facing profiles:

| Profile | Purpose | Default FPS behavior |
|---|---|---|
| Full Power | Uses the Mac's full graphics power and full remastered effects. | Targets the active display refresh, capped internally for sanity. |
| Battery Saver | Reduces power use and heat. | Caps at 72 FPS, or lower if the display cannot present 72 Hz. |

`Custom Max FPS` overrides both profiles. Leaving it blank uses the selected profile's default. Entering a number caps both render and client frame rates, while still respecting the active display refresh.

## Version 1.0 Status

The `1.0` tag represents the current Apple Silicon baseline:

- Native arm64 build path is working.
- GL3 renderer starts on macOS OpenGL 4.1.
- Core gameplay loop is playable.
- SDL3 windowed mode and fullscreen switching are supported.
- Resizable window mode is supported.
- Performance overlay is available.
- Two-profile graphics model is implemented.
- Audio underrun handling has been hardened.
- The app bundle can be copied, signed, and launched locally.

Known constraints:

- Retail/remastered PAK data is not stored in git.
- The generated `.app` bundle is not stored in git.
- macOS OpenGL is limited to 4.1, so the renderer is adapted around that target.
- Some original codebase warnings remain and are tracked as technical debt.

## Attribution

This project builds on the work of the Heretic2R source port and the wider Heretic II Remastered effort. Heretic II is the property of its respective rights holders. This repository is for preservation, porting, and compatibility work and does not grant rights to the original commercial game data.
