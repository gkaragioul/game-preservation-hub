# Release Notes

## Version 1.0

First Apple Silicon baseline for Heretic II Remastered: a native macOS arm64 build of the Heretic2R source port.

### Current State

- Native macOS arm64 build path is working.
- App launches through SDL3/Cocoa with the GL3/OpenGL renderer by default.
- GL3 runs on macOS OpenGL 4.1.
- CoreAudio/SDL3 sound backend is active.
- Gameplay is playable with remastered assets and original game data supplied locally.
- Windowed mode, fullscreen switching, and manual resizing are supported.
- Performance overlay is available for frame, GPU, CPU, memory, render, and particle stats.
- Two graphics profiles are available:
  - Full Power: richer visual path with a fixed 120 FPS target where supported.
  - Power Saver: lighter visual path with a fixed 60 FPS target for lower power use.
- Custom FPS cap override is available in graphics options.
- The OpenGL spell-combat route has been verified in both profiles, including spell cooking, spell release, hit FX, alpha particles, and normal gameplay movement.
- The previous square/diamond particle-card artifacts during charged spell effects have been removed in both Power Saver and Full Power.
- Frame pacing evidence exists for the final spell-combat route:
  - Power Saver 60 FPS: p50 `16.726 ms`, p95 `16.786 ms`, p99 `16.796 ms`.
  - Full Power 120 FPS: p50 `8.391 ms`, p95 `8.445 ms`, p99 `9.225 ms`.
- Audio underrun handling has been hardened to avoid stale-buffer crackle.
- macOS press-and-hold accent picker is disabled for the game bundle.

### Packaging Notes

- Generated builds, `.app` bundles, and proprietary PAK files are intentionally excluded from git.
- Required game data must be supplied from a legally owned Heretic II install/remastered asset package.
- The repository is intended as the source and porting history for the Apple Silicon app, not a binary distribution archive.

### Known Constraints

- GL3 fallback is limited to macOS OpenGL 4.1.
- Apple Silicon may report `GL_VERSION: 4.1 Metal - 90.5`; this is Apple's OpenGL compatibility layer, not a native Metal renderer in this release.
- 120 FPS can still show rare route spikes and should continue to be tuned through OpenGL entity/alpha ordering and frame pacing work.
- Some inherited compiler warnings remain.
- Save compatibility with older 32-bit builds is not guaranteed.
