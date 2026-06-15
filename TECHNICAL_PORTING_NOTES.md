# Heretic II Remastered macOS Apple Silicon Port

## Target

This project was ported and packaged for native macOS Apple Silicon on an M4 MacBook Air. The target runtime is a self-contained desktop app:

- `Heretic II Remastered.app`
- Native arm64 executable and dynamic libraries
- Spacefarer Heretic II Remastered R8_00 assets
- Original Heretic II retail PAK data
- OpenGL 4.1 Core Profile through Apple's OpenGL-over-Metal stack
- SDL3 Cocoa video/input and CoreAudio sound
- 60 fps cap with vsync for smooth pacing and better battery life

## Source And Asset Investigation

The workspace contained the retail Heretic II disc image, Spacefarer Remastered source/assets, older Windows fixes, and several mod/map folders. The graphics enhancement that mattered was Spacefarer's Heretic II Remastered package, not the older ModDB-style add-ons. The app bundle now includes:

- `base/base.pak`: Spacefarer Remastered asset pack, about 1.9 GB
- `base/Htic2-0.pak`: original retail Heretic II data
- `base/Htic2-1.pak`: original retail Heretic II data
- `base/HDTextures`: 159 detected HD replacement textures
- Native arm64 game modules:
  - `H2Common.dylib`
  - `ref_gl3.dylib`
  - `snd_sdl3.dylib`
  - `base/Player.dylib`
  - `base/Client Effects.dylib`
  - `base/gamex86.dylib`

The Spacefarer Remastered release used for the assets was:

- `downloads/HereticIIRemastered_R8_0.7z`
- Release version reported by the engine: `Heretic 2 Remastered R8_00`

## Native macOS Compatibility Layer

The original codebase is Windows-oriented. I added a small POSIX/macOS compatibility layer instead of using Wine or Rosetta. Key additions include:

- Minimal Windows compatibility headers in `include/`
  - `windows.h`
  - `direct.h`
  - `io.h`
  - `VersionHelpers.h`
  - `shlobj.h`
  - `wininet.h`
- macOS/POSIX platform files in `src/posix/`
  - `main.c`
  - `sys_posix.c`
  - `q_shposix.c`
  - `net_posix.c`
  - `cd_audio.c`
  - `cd_audio.h`
  - `cd_detect_stub.c`
  - `win_compat.h`
  - `Quake2Main.h`

The compatibility layer provides Windows-style types, dynamic-library loading helpers, filesystem helpers, safe string shims, find-first/find-next directory iteration, timing, user-directory handling, and macOS dynamic loading.

## Build System

I added `build_macos_arm64.sh`, a direct clang/clang++ build script for Apple Silicon. It reads the existing Visual Studio project source lists, filters Windows-only files, and builds native arm64 outputs.

Homebrew dependencies used:

- SDL3 from `/opt/homebrew/opt/sdl3`
- OpenAL Soft from `/opt/homebrew/opt/openal-soft`

The build script produces:

- `build/Heretic2R`
- `build/H2Common.dylib`
- `build/ref_gl3.dylib`
- `build/snd_sdl3.dylib`
- `build/base/Player.dylib`
- `build/base/Client Effects.dylib`
- `build/base/gamex86.dylib`

All of these were verified as `Mach-O 64-bit arm64` binaries.

## Renderer Port

Spacefarer's renderer is named `ref_gl3` but originally requested an OpenGL 4.6 Core context. macOS only exposes OpenGL 4.1, even on Apple Silicon. I changed the macOS context request to OpenGL 4.1 and verified the renderer initializes successfully on Apple M4:

- `GL_VENDOR: Apple`
- `GL_RENDERER: Apple M4`
- `GL_VERSION: 4.1 Metal - 90.5`
- GL3 shaders initialized
- HDR framebuffer initialized
- Bloom framebuffers initialized
- SSAO initialized
- Reflection framebuffer initialized
- Dynamic stencil shadows initialized
- 9 renderer worker threads created
- 159 HD replacement textures detected

I also changed the renderer title on macOS to report `OpenGL 4.1` instead of the misleading `OpenGL 4.6` label.

## Runtime Fixes

Several Windows assumptions had to be fixed for native macOS:

- Added macOS constructors/destructors for `H2Common` initialization so resource managers are ready before server/map spawn.
- Replaced Windows memory allocation paths in the GL hunk allocator with portable aligned allocation.
- Stubbed Windows-only MP4/update-check paths where they were not portable.
- Added or corrected type declarations in game/client-effect headers.
- Fixed safe-string compatibility shims.
- Fixed a user-config path buffer issue that prevented writing `config.cfg` under:
  - `~/Library/Application Support/Heretic2R/base/config.cfg`
- Cleaned stale menu/config labels that produced unknown-command noise at startup.
- Switched default renderer config from `gl1` to `gl3`.

## Renderer Crash Fix After Initial Loading

After packaging, a user crash report showed:

- Exception: `EXC_BAD_ACCESS`
- Crashing module: `ref_gl3.dylib`
- Crashing function: `R_RenderLightmappedPoly`
- Call path: `R_DrawWorld` -> `RI_RenderFrame` -> `V_RenderView`

This meant the app bundle, signing, and dynamic-library loading were already working; the crash was inside world rendering while drawing lightmapped map surfaces.

I hardened the GL3 renderer in these areas:

- Added polygon sanity validation before lightmapped, alpha, and warp/water draw calls.
- Initialized `glpoly_t.chain` to `NULL` when allocating world and warp polygons. This was the root cause of the lightmap crash: `R_RenderLightmappedPoly` walks this chain, but some newly allocated polygons inherited random pointer data.
- Prevented fixed 64-vertex stack buffers from being drawn with an uncapped original vertex count.
- Added safe bounds checks for lightmap texture indices.
- Added safe bounds checks for dynamic lightmap dimensions.
- Fixed an out-of-bounds lightstyle read when the scan reaches `MAXLIGHTMAPS` without a `255` terminator.
- Added lower-level guards in `GL3_DrawLMPoly`, `GL3_Draw3DPoly`, and `GL3_DrawWaterPoly` so invalid vertex uploads are ignored instead of crashing.

During diagnosis, the lightmapped world fast path was temporarily bypassed, which made the game look much brighter than intended. That was still the native GL3 renderer, not software mode. After the uninitialized-chain bug was fixed, the lightmap fast path was restored so the world uses the intended shaded/lightmapped appearance again.

The patched app was rebuilt, copied back into the `.app`, had bundle-relative install names reapplied, and was re-signed.

## Performance And Battery Tuning

The default Mac launch profile is:

- `vid_ref gl3`
- `vid_mode 0`
- `r_vsync 1`
- `vid_maxfps 60`

`vid_mode 0` uses the laptop's current desktop-scaled display mode. On the tested M4 MacBook Air this resolved to `1710x1107`, which is a good balance for the built-in panel: sharp, native-looking, and much lighter than forcing full physical Retina pixels.

The original POSIX frame loop was busy-spinning between frames. I replaced that with a short `Sys_Nanosleep(500000)` yield. In the same 60-second `ssdocks` map test, CPU use dropped from about 75% of one core to about 32% of one core while the game stayed stable at the same 60 fps/vsync profile. This is important for battery life and thermals on a fanless MacBook Air.

## App Bundle Packaging

The final app is self-contained:

- `Heretic II Remastered.app`
- App icon: `Contents/Resources/Heretic2.icns`
- Bundled game build: `Contents/Resources/build`
- Bundled SDL3: `Contents/Resources/build/libSDL3.0.dylib`
- Bundled OpenAL Soft: `Contents/Resources/build/libopenal.1.dylib`

The app wrapper lives at:

- `Contents/MacOS/Heretic II Remastered`

It changes directory into the bundled build and launches:

```sh
./Heretic2R +set vid_ref gl3 +set vid_mode 0 +set r_vsync 1 +set vid_maxfps 60
```

The copied dynamic libraries originally had absolute install names pointing back to the build folder and Homebrew. I rewrote them with `install_name_tool` to bundle-relative paths:

- `@executable_path/H2Common.dylib`
- `@executable_path/libSDL3.0.dylib`
- `@loader_path/H2Common.dylib`
- `@loader_path/libopenal.1.dylib`
- `@loader_path/../H2Common.dylib`

After path rewriting, all app binaries and libraries were signed ad-hoc with:

```sh
codesign --force --sign -
codesign --force --deep --sign - "Heretic II Remastered.app"
```

This fixed Launch Services killing the bundled executable because of invalid copied-library signatures.

## Verification Performed

Native architecture:

- `Heretic2R`: arm64
- `ref_gl3.dylib`: arm64
- `snd_sdl3.dylib`: arm64
- `gamex86.dylib`: arm64
- `Player.dylib`: arm64
- `Client Effects.dylib`: arm64

Boot verification:

- App loads bundled Remastered and retail PAKs.
- App initializes SDL3 Cocoa video.
- App initializes Apple M4 OpenGL 4.1 renderer.
- App initializes SDL3/CoreAudio sound.
- App loads HD textures.
- App reaches the menu/startup path and remains running.

Gameplay verification:

- Direct map launch tested with `ssdocks`.
- The engine loaded `Silverspring Docks`.
- Client effects and player modules loaded.
- The first in-game line appeared:
  - `This isn't right. Where is everyone?`
- The game remained running for stability passes and shut down cleanly when terminated.
- After the `R_RenderLightmappedPoly` crash fix and restored lightmap path, the packaged app's `ssdocks` render path stayed alive for 120 seconds and progressed through multiple in-game messages without generating a new crash report.

App verification:

- The self-contained bundle build launches from inside `Heretic II Remastered.app`.
- Finder-style `open -n "Heretic II Remastered.app"` starts the native game process.
- App bundle passes ad-hoc code-sign verification.
- After the crash fix, normal Finder-style app startup remained alive for 75 seconds, beyond the crash timing shown in the report.

## Known Notes

The game uses Apple's deprecated but still available OpenGL stack. This is native arm64 execution, not Rosetta and not Wine. A future Metal renderer would be a larger renderer rewrite; the current port keeps the Remastered GL renderer and adapts it to macOS OpenGL 4.1.

The app is locally ad-hoc signed, not notarized with an Apple Developer ID. On a different Mac, Gatekeeper may still require the usual right-click Open or privacy approval for locally built unsigned apps.
