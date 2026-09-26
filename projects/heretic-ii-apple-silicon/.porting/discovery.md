# Milestone 00 — Project Intake: Discovery

## Repository

- **Git**: Single commit `74e6473` on branch `main` (origin/main)
- **Uncommitted changes**: 30 files modified, 1 untracked directory (`src/ref_metal/`)
- **Remote**: Origin is configured, no pending pushes
- **.gitignore**: Ignores `/build/**`, `/*.app/**`, generated build artifacts, `.DS_Store`, `*.log`

## Workspace Layout

```
.
├── Heretic II Remastered.app/     # Self-contained macOS app bundle
├── build/                          # Build output (ignored by git)
│   ├── Heretic2R                   # Main game binary (arm64, 541K)
│   ├── H2Common.dylib              # Shared engine library (73K)
│   ├── ref_gl3.dylib               # OpenGL 4.1 renderer (344K)
│   ├── snd_sdl3.dylib              # SDL3/CoreAudio sound (149K)
│   ├── libSDL3.0.dylib             # SDL3 runtime (2.4M)
│   ├── libopenal.1.dylib           # OpenAL Soft (1.6M)
│   ├── base/
│   │   ├── base.pak                # Spacefarer Remastered assets (1.9 GB)
│   │   ├── Htic2-0.pak             # Retail Heretic II data (206 MB)
│   │   ├── Htic2-1.pak             # Retail Heretic II data (42 MB)
│   │   ├── Player.dylib            # Game module (269K)
│   │   ├── Client Effects.dylib    # Effects module (298K)
│   │   ├── gamex86.dylib           # Game logic module (269K)
│   │   ├── HDTextures/             # 159 HD replacement textures (6 dirs)
│   │   ├── Art/                    # UI art assets
│   │   ├── config/                 # Control presets
│   │   └── *.cfg                   # Game configuration files
│   └── *.log                       # Smoke test logs (many)
├── src/                            # Full source tree
│   ├── posix/                      # macOS/POSIX compatibility layer
│   ├── win32/                      # Original Windows platform code
│   ├── qcommon/                    # Engine common code
│   ├── client/                     # Client (with SDL3 Cocoa glimp)
│   ├── server/                     # Server
│   ├── game/                       # Game logic (433 files)
│   ├── Player/                     # Player module
│   ├── client effects/             # Client effects module
│   ├── ref_gl3/                    # OpenGL 4.1 renderer (39 src files)
│   ├── ref_metal/                  # Metal renderer (1 file, 6916 lines)
│   ├── ref_gl1/                    # Legacy OpenGL 1.x renderer
│   ├── snd_sdl3/                   # SDL3/CoreAudio/OpenAL sound
│   ├── tools/                      # Tools
│   ├── launcher/                   # Launcher
│   └── H2Common/                   # Shared library
├── include/                        # Compatibility and third-party headers
│   ├── windows.h, io.h, direct.h   # Windows API shims
│   ├── glad-GL3.3/                 # OpenGL loader
│   ├── glad-GL4.6/                 # (unused on macOS)
│   ├── SDL3/                       # SDL3 headers (fallback)
│   └── stb/                        # stb_image
├── lib/                            # Third-party dylib stubs
│   ├── SDL3/
│   └── OpenAL/
├── addons/                         # 17 community map/mod folders
└── stuff/                          # Patch 1.06 archive
```

## App Bundle

- `Heretic II Remastered.app/Contents/Info.plist`: Bundle ID `local.heretic2.remastered.apple-silicon`, version `R8.00-macos-arm64`, min OS 13.0, Retina enabled
- `Contents/MacOS/Heretic II Remastered`: Shell script that `cd`s into Resources/build and runs `./Heretic2R +set vid_ref gl3 +set vid_mode 0 +set vid_fullscreen 0`
- `Contents/Resources/build/`: Mirrors workspace `build/` (synced by `sync_app_bundle()`)
- `Contents/Resources/Heretic2.icns`: App icon
- `Contents/_CodeSignature/`: Ad-hoc signed

## Build System

- **Script**: `build_macos_arm64.sh` (295 lines)
- **Compiler**: `clang` / `clang++`, target `-arch arm64`, optimization `-O2 -DNDEBUG`
- **Defines**: `-D__MACOS_NATIVE__`
- **Standards**: C11 (`-std=gnu11`), C++17 (`-std=gnu++17`)
- **Dependencies**: SDL3 (Homebrew or fallback), OpenAL Soft (Homebrew or fallback)
- **Frameworks**: `-framework OpenGL -framework AppKit`
- **Outputs**: 3 dylibs (H2Common, ref_gl3, snd_sdl3), main binary (Heretic2R), 3 game dylibs in base/
- **Post-processing**: `install_name_tool` for bundle-relative paths, `sync_app_bundle()` copies to `.app`
- **Build time**: Last build Jun 17 17:45

## Renderer Status

| Aspect | Verified |
|---|---|
| Active renderer | `ref_gl3` (OpenGL 4.1) |
| Build output | `ref_gl3.dylib` present, `ref_metal.dylib` explicitly deleted by build script |
| Default vid_ref | `gl3` (hardcoded in vid_dll.c line 14, menu defaults) |
| Runtime report | `GL_VERSION: 4.1 Metal - 90.5`, `GL_RENDERER: Apple M4` |
| Capabilities | HDR FBO, bloom, SSAO, reflections, stencil shadows, 9 worker threads, 159 HD textures |
| Metal renderer | Full 6916-line implementation exists in `src/ref_metal/` but is NOT built. Complete with 2D/3D/lightmap/water pipelines, bloom, SSAO, fog, flex models. |

## Configuration (active `config.cfg`)

- `vid_ref gl3`, `vid_mode 0`, `vid_fullscreen 0`
- `r_vsync 1`, `vid_maxfps 60`, `cl_maxfps 60`
- `r_graphics_profile 1` (Battery Saver)
- `r_bloom 0`, `r_ssao 0`, `r_shadows 0`, `r_reflections 0`
- `r_hd_textures 1`

## User Data Paths

- **Config & saves**: `~/Library/Application Support/Heretic2R/base/`
- **Save files**: Present at `.../base/save/`
- **Screenshots**: `.../base/screenshots/`
- **Config files**: `config.cfg`, `console_history.txt`, `console_log.txt`
- **Frame logs**: `frame_log.csv` (192K), `frame_spikes.log` (107K)

## Logs and Evidence

- `heretic2r_app.log` (Jun 14): Shows full boot + level load, no crash
- `app_opengl_only_smoke.log` (Jun 17): Empty (touch file)
- `build/opengl_only_smoke.log` (Jun 17): Successful boot to ssdocks level, shows repeated FBO resize spam
- `build/opengl_pacing_smoke.log` (Jun 17): Same as above
- `build/gl3_comparison_smoke.log`: Full boot log
- Many `metal_*.log` files: Previous Metal renderer tests

## Uncommitted Changes (since baseline)

| Area | Files | Changes |
|---|---|---|
| build_macos_arm64.sh | 1 | ref_metal cleanup, sync_app_bundle additions |
| src/client/ | cl_main.c, cl_screen.c, cl_smk.c, cl_view.c, client.h, glimp_sdl3.[ch], ref.h, screen.h, menu_video.c, menu_worldmap.c | Widescreen, frame pacing, adaptive FPS, performance overlay, menu fixes |
| src/ref_gl3/ | gl3_Draw.c, gl3_Image.c, gl3_Local.h, gl3_Main.c, gl3_Misc.c, gl3_SDL.c, gl3_Shaders.[ch], gl3_Sprite.c, gl3_Surface.c | HD texture fixes, shader updates, job system, resize handling |
| src/snd_sdl3/ | snd_main.c, snd_sdl3.[ch] | Audio underrun hardening, callback safety |
| src/win32/ | snd_dll.c, vid_dll.c | GL3 defaults, renderer loading fixes |
| src/ref_metal/ | metal_Main.m (untracked) | Full Metal renderer implementation |
| README/RELEASE/TECHNICAL | 3 files | Updated docs |

## Known Issues (observed in logs/config)

1. **Window resize loop**: FBO reinitialization fires multiple times on startup, visible as repeated "Window resized to 2560x1330" + "GL3 HDR FBO initialized" spam
2. **Frame spikes**: `frame_spikes.log` (107K) contains recorded spike events; `scr_frame_spike_log 0` was set to suppress them
3. **Battery Saver default**: `r_graphics_profile 1` disables bloom/SSAO/shadows/reflections by default
4. **No Metal build**: ref_metal.dylib is explicitly deleted by build_macos_arm64.sh line 8
5. **App bundle vs direct build**: Launch wrapper uses different args than direct build script
6. **MP4/H.264 cinematics**: Stubbed on macOS (no hardware decoder path)
