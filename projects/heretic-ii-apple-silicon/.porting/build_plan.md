# Milestone 02 - Build Plan

Date: 2026-06-18
Workspace: `/Volumes/Work/DevWork/GameDev/HERETIC2/Heretic2Remastered-main`

## Build Entry Point

Use the native macOS build script:

```sh
./build_macos_arm64.sh
```

The script compiles the Apple Silicon build with `clang` / `clang++`, `-arch arm64`, `-O2`, and `-D__MACOS_NATIVE__`.

## Build Targets

| Target | Output | Purpose |
|---|---|---|
| H2Common | `build/H2Common.dylib` | Shared engine/common library |
| Player | `build/base/Player.dylib` | Player module |
| Client Effects | `build/base/Client Effects.dylib` | Client visual effects module |
| Game | `build/base/gamex86.dylib` | Game logic module, dylib name retained for engine compatibility |
| GL3 renderer | `build/ref_gl3.dylib` | Active OpenGL 4.1 renderer |
| SDL3 sound | `build/snd_sdl3.dylib` | Active macOS audio backend |
| Main executable | `build/Heretic2R` | Native arm64 game executable |

## Expected Bundle Output

After a successful build, `sync_app_bundle()` updates:

```text
Heretic II Remastered.app/Contents/Resources/build/
```

The app launcher runs the bundled `Heretic2R` with `+set vid_ref gl3`, so the active renderer remains OpenGL GL3.

## Verification Commands

```sh
file build/Heretic2R build/ref_gl3.dylib build/snd_sdl3.dylib build/H2Common.dylib
otool -L build/Heretic2R build/ref_gl3.dylib build/snd_sdl3.dylib
```

## Latest Evidence

- Build log: `.porting/build_logs/latest_build.log`
- Verified binary type: `Mach-O 64-bit executable arm64`
- Verified active renderer output: `build/ref_gl3.dylib`
- Verified no active Metal renderer dylib is bundled by the build script.

## Acceptance Check

Milestone 02 passes when `./build_macos_arm64.sh` completes successfully and the output binaries are arm64 with bundle-relative library paths.
