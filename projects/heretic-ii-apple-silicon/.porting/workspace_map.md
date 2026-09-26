# Milestone 01 — Workspace Map

## Directory Layout

```
Heretic2Remastered-main/
├── .porting/                       # Porting project artifacts (AI-friendly)
│   ├── discovery.md                #   M00: Full project discovery
│   ├── current_goal.md             #   M00: Primary target & strategy
│   ├── risk_register.md            #   M00: 14 risks with mitigations
│   ├── legal_asset_boundaries.md   #   M00: Data ownership boundaries
│   ├── workspace_map.md            # [THIS FILE]
│   ├── memory.md                   #   AI session memory/primer
│   ├── known_issues.md             #   Known issues catalog
│   ├── build_logs/                 #   <-- place smoke/build logs here
│   ├── runtime_logs/               #   <-- place runtime/console logs here
│   ├── screenshots/                #   <-- place before/after captures here
│   ├── performance/                #   <-- place frame pacing/profiling data here
│   ├── qa/                         #   <-- place test results here
│   ├── renderer/                   #   <-- place renderer-specific notes here
│   ├── audio/                      #   <-- place audio-specific notes here
│   ├── packaging/                  #   <-- place packaging/distribution notes here
│   └── known_issues/               #   <-- place detailed issue reports here
│
├── src/                            # PROJECT SOURCE (tracked in git)
│   ├── H2Common/                   #   Shared library (common defs/handles)
│   ├── qcommon/                    #   Engine: files, cmds, cvars, net, pmove, etc.
│   ├── client/                     #   Client: screen, view, input, menus, cinematics
│   ├── server/                     #   Server: init, world, game, effects
│   ├── game/                       #   Game logic: AI, items, weapons, spells, script
│   ├── Player/                     #   Player module (actions, weapons, anims)
│   ├── client effects/             #   Client effects: particles, fx, lights
│   ├── ref_gl3/                    #   OpenGL 4.1 renderer (ACTIVE)
│   ├── ref_gl1/                    #   Legacy OpenGL 1.x renderer (inactive)
│   ├── ref_metal/                  #   Metal renderer (src; NOT built)
│   ├── snd_sdl3/                   #   SDL3/CoreAudio/OpenAL sound backend
│   ├── posix/                      #   macOS/POSIX compat layer
│   ├── win32/                      #   Windows platform (reference, not built)
│   ├── tools/                      #   Dev tools: MakePak, SaveConverter, DumpTextures
│   ├── launcher/                   #   Windows launcher (inactive)
│   ├── base_gamedata/              #   Additional game data references
│   └── x64/                        #   Windows x64 build artifacts (inactive)
│
├── include/                        # THIRD-PARTY & COMPAT HEADERS
│   ├── windows.h                   #   Windows API shim (fake Win32 types)
│   ├── direct.h                    #   _mkdir, _chdir shims
│   ├── io.h                        #   _access, file ops shims
│   ├── shlobj.h                    #   SHGetFolderPath stub
│   ├── wininet.h                   #   Stub (macOS no wininet)
│   ├── VersionHelpers.h            #   Version check stub
│   ├── SDL3/                       #   SDL3 headers (bundled fallback)
│   ├── AL/                         #   OpenAL headers (bundled fallback)
│   ├── glad-GL3.3/                 #   OpenGL 3.3 loader (used by ref_gl3)
│   ├── glad-GL1.3/                 #   OpenGL 1.3 loader (inactive)
│   ├── glad-GL4.6/                 #   GL4.6 loader (inactive on macOS)
│   ├── glad-GL4.6_temp/            #   Temp GL4.6 (inactive)
│   ├── libsmacker/                 #   SMK video decoder
│   └── stb/                        #   stb_image.h
│
├── lib/                            # THIRD-PARTY LIB STUBS (Windows .lib files)
│   ├── SDL3/                       #   SDL3.lib, x86_SDL3.lib
│   └── OpenAL/                     #   OpenAL32.lib
│
├── addons/                         # COMMUNITY MAP/MOD DATA (15 addons)
│   ├── andoria_waterworks/
│   ├── atlantis/
│   ├── blupipe/
│   ├── corvcron/
│   ├── gates/
│   ├── head/
│   ├── island/
│   ├── lanius/
│   ├── phantasmagoria/
│   ├── rodent_zone/
│   ├── sacrifist/
│   ├── sidol/
│   ├── ssasylum/
│   ├── trhunter/
│   └── yak1999/
│
├── stuff/                          # PATCH ARCHIVES
│   └── Heretic_II_Patch_106_for_H2R.zip
│
├── build/                          # GENERATED BUILD OUTPUT (gitignored)
│   ├── Heretic2R                   #   Main executable (arm64, Mach-O)
│   ├── H2Common.dylib              #   Shared library
│   ├── ref_gl3.dylib               #   GL3 renderer
│   ├── snd_sdl3.dylib              #   Sound backend
│   ├── libSDL3.0.dylib             #   SDL3 runtime
│   ├── libopenal.1.dylib           #   OpenAL Soft runtime
│   ├── SDL3.dll                    #   (Windows artifact, harmless)
│   ├── base/                       #   Game data + bundled game dylibs
│   │   ├── base.pak                #     Spacefarer Remastered (1.9 GB)
│   │   ├── Htic2-0.pak             #     Retail data (206 MB)
│   │   ├── Htic2-1.pak             #     Retail data (42 MB)
│   │   ├── HDTextures/             #     159 HD replacement textures (43 MB)
│   │   ├── Player.dylib            #     Player game module
│   │   ├── "Client Effects.dylib"  #     Effects module
│   │   ├── gamex86.dylib           #     Game logic module
│   │   ├── Player.dll              #     (Windows artifact, unused)
│   │   ├── "Client Effects.dll"    #     (Windows artifact, unused)
│   │   ├── gamex64.dll             #     (Windows artifact, unused)
│   │   ├── Art/                    #     UI art assets
│   │   ├── config/                 #     Control presets
│   │   └── *.cfg                   #     Config files
│   ├── macos-arm64/                #   Build objects (6.6 MB)
│   │   └── obj/                    #     .o files per module subdir
│   └── *.log                       #   Smoke test logs (see below)
│
├── "Heretic II Remastered.app/"    # GENERATED APP BUNDLE (gitignored)
│   └── Contents/
│       ├── Info.plist
│       ├── MacOS/Heretic II Remastered   # Shell launch script
│       ├── Resources/
│       │   ├── Heretic2.icns
│       │   └── build/                    # Mirrors workspace build/
│       └── _CodeSignature/              # Ad-hoc signed
│
├── build_macos_arm64.sh            # BUILD SCRIPT (uses clang/clang++)
├── "Launch Heretic II Remastered.command"  # Direct launch shortcut
│
├── *.md                            # DOCUMENTATION
│   ├── README.md
│   ├── RELEASE_NOTES.md
│   └── TECHNICAL_PORTING_NOTES.md
│
└── *.png / *.log                   # Project images + smoke logs
```

## Source vs Generated Classification

| Path | Classification | Notes |
|---|---|---|
| `src/**/*.c` | SOURCE | Engine, game, tool C sources |
| `src/**/*.cpp` | SOURCE | C++ sources (script system, 4 files) |
| `src/**/*.m` | SOURCE | ObjC sources (metal_Main.m, macos_window.m) |
| `src/**/*.h` | SOURCE | Headers |
| `src/**/*.vcxproj` | SOURCE (MSBuild) | Build definitions (Windows reference, parsed by build script) |
| `include/**/*` | SOURCE (third-party) | GL loaders, SDL headers, compat shims, stb |
| `lib/**/*.lib` | SOURCE (third-party, Win) | Windows import libs, unused on macOS |
| `build_macos_arm64.sh` | SOURCE | Build script |
| `addons/**/*` | SOURCE (community data) | 17 map/mods |
| `stuff/**/*` | SOURCE (patch) | Patch 1.06 archive |
| `.porting/*.md` | SOURCE (port docs) | Milestone deliverables |
| `build/Heretic2R` | GENERATED | Binary from clang++ |
| `build/*.dylib` | GENERATED | Shared libraries |
| `build/macos-arm64/obj/**/*.o` | GENERATED | Object files |
| `build/base/*.dylib` | GENERATED | Game module dylibs |
| `build/*.log` | GENERATED | Runtime smoke test logs |
| `Heretic II Remastered.app/**/*` | GENERATED | App bundle (copied from build/) |
| `*.log` (workspace root) | GENERATED | Runtime logs from prior runs |

## Build Targets (from `build_macos_arm64.sh`)

| Target | Project File | Output | Description |
|---|---|---|---|
| H2Common | `src/H2Common/H2Common.vcxproj` | `build/H2Common.dylib` | Shared engine library |
| Player | `src/Player/Player.vcxproj` | `build/base/Player.dylib` | Player game module |
| client_effects | `src/client effects/Client Effects.vcxproj` | `build/base/Client Effects.dylib` | Client effects module |
| game | `src/game/game.vcxproj` | `build/base/gamex86.dylib` | Game logic module |
| ref_gl3 | `src/ref_gl3/ref_gl3.vcxproj` (+ `gl3_Glad.c`) | `build/ref_gl3.dylib` | OpenGL 4.1 renderer |
| snd_sdl3 | `src/snd_sdl3/snd_sdl3.vcxproj` | `build/snd_sdl3.dylib` | SDL3 sound backend |
| Heretic2R | `src/win32/quake2.vcxproj` (+ POSIX replacements) | `build/Heretic2R` | Main game executable |

## Where To Log Evidence

| Evidence Type | Place In |
|---|---|
| Build output | `.porting/build_logs/` (copy from terminal) |
| Runtime console log | `.porting/runtime_logs/` (from `heretic2r_app.log` or `script` capture) |
| Screenshots | `.porting/screenshots/` |
| Frame pacing / perf data | `.porting/performance/` |
| Test results / QA | `.porting/qa/` |
| Renderer-specific notes | `.porting/renderer/` |
| Audio-specific notes | `.porting/audio/` |
| Packaging / distribution notes | `.porting/packaging/` |
| Detailed issue reports | `.porting/known_issues/` |

## Launch Commands

```sh
# Direct launch (from workspace)
./build/Heretic2R +set vid_ref gl3 +set vid_mode 0 +set vid_fullscreen 0

# Quick test with map + overlay
./build/Heretic2R +set vid_ref gl3 +set vid_fullscreen 0 +set vid_mode 0 +set r_perf_overlay 1 +map ssdocks

# App bundle launch
open -n "Heretic II Remastered.app"

# Launch script
./Launch\ Heretic\ II\ Remastered.command

# Build (after changes)
./build_macos_arm64.sh
```

## Configuration Locations

| Path | Purpose |
|---|---|
| `~/Library/Application Support/Heretic2R/base/config.cfg` | Active game config |
| `~/Library/Application Support/Heretic2R/base/save/` | Save games |
| `~/Library/Application Support/Heretic2R/base/screenshots/` | Screenshots |
| `~/Library/Application Support/Heretic2R/base/console_log.txt` | Console log |
| `~/Library/Application Support/Heretic2R/base/frame_log.csv` | Frame timing log |
| `~/Library/Application Support/Heretic2R/base/frame_spikes.log` | Frame spike events |
