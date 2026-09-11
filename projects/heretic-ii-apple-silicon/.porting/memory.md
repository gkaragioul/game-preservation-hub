# Milestone 01 — AI Workspace Memory

## Project Identity

**Heretic II Remastered — Apple Silicon native macOS port**
- Source port: Heretic2R (Quake 2 engine fork)
- Asset pack: Spacefarer Heretic II Remastered R8_00
- Current version: R8.00-macos-arm64
- Git: Single commit `74e6473` branch `main`

## Renderer Status

| | |
|---|---|
| **Active renderer** | OpenGL 4.1 via `ref_gl3.dylib` (built, bundled) |
| **Runtime GL identity** | `GL_RENDERER: Apple M4`, `GL_VERSION: 4.1 Metal - 90.5` |
| **Metal renderer** | `src/ref_metal/metal_Main.m` (6916 lines, full impl) — NOT built |
| **Build script** | Explicitly deletes `ref_metal.dylib` on every build (line 8) |
| **Default config** | `vid_ref gl3`, `vid_mode 0`, `vid_fullscreen 0`, `r_vsync 1`, `vid_maxfps 60` |
| **Capabilities** | HDR FBO, bloom, SSAO, reflections, stencil shadows, 9 job threads, 159 HD textures |

## Build System

- Single `build_macos_arm64.sh` script
- Source lists extracted from `.vcxproj` files (MSBuild XML → Python parser)
- macOS POSIX replacements for Windows-only source files (sys_win.c → sys_posix.c, etc.)
- Compiler: clang/clang++ for arm64
- Frameworks: OpenGL, AppKit
- Dependencies: SDL3 + OpenAL (Homebrew or bundled)
- Outputs land in `build/`, synced to app bundle via `sync_app_bundle()`

## Quick Commands

```
./build_macos_arm64.sh              # Full rebuild
./build/Heretic2R +map ssdocks      # Direct launch
./build/Heretic2R +set r_perf_overlay 1 +map ssdocks  # With perf HUD
```
Config lives at `~/Library/Application Support/Heretic2R/base/config.cfg`

## Data Paths

| What | Where |
|---|---|
| Source code | `src/` |
| Build output | `build/` (gitignored) |
| App bundle | `Heretic II Remastered.app/` (gitignored) |
| User config/saves | `~/Library/Application Support/Heretic2R/base/` |
| Porting artifacts | `.porting/` (tracked in git) |
| Build logs → | `.porting/build_logs/` |
| Runtime logs → | `.porting/runtime_logs/` |
| Screenshots → | `.porting/screenshots/` |
| Performance data → | `.porting/performance/` |

## Key Files for Common Tasks

| Task | File |
|---|---|
| Fix OpenGL renderer | `src/ref_gl3/src/gl3_Main.c`, `gl3_Draw.c`, `gl3_SDL.c`, `gl3_Surface.c`, `gl3_Shaders.c` |
| Fix window/display | `src/ref_gl3/src/gl3_SDL.c`, `src/client/glimp_sdl3.c`, `src/win32/vid_dll.c` |
| Fix sound | `src/snd_sdl3/src/snd_sdl3.c`, `snd_main.c` |
| Fix frame pacing | `src/client/cl_main.c`, `src/client/cl_screen.c`, `src/posix/sys_posix.c` |
| Fix menus/UI | `src/client/menus/menu_video.c`, `src/client/menu.c` |
| Fix build script | `build_macos_arm64.sh` |
| Add Metal build | `build_macos_arm64.sh`, `src/ref_metal/src/metal_Main.m` |

## Active Risk (top 3)

1. **FBO resize loop** — Repeated HDR/bloom/SSAO FBO recreation on every window resize event (visible in log spam)
2. **Frame pacing** — Frame spikes recorded in `frame_spikes.log` (107K); 60 FPS lock stability unverified
3. **Widescreen correctness** — Untested at different aspect ratios

## Legal

- No proprietary assets in git
- PAK files user-supplied from retail Heretic II + Spacefarer Remastered
- GPL-compatible source port
- Patch 1.06 in `stuff/` (included in repo)
