# Release Notes

## Version 1.0

Initial private Apple Silicon baseline for Heretic II Remastered.

### Current State

- Native macOS arm64 build path is working.
- App launches through SDL3/Cocoa with the GL3 renderer.
- Renderer targets macOS OpenGL 4.1 on Apple Silicon.
- CoreAudio/SDL3 sound backend is active.
- Gameplay is playable with remastered assets and original game data supplied locally.
- Windowed mode, fullscreen switching, and manual resizing are supported.
- Performance overlay is available for frame, GPU, CPU, memory, render, and particle stats.
- Two graphics profiles are available:
  - Full Power: full remastered visual path and monitor-refresh frame target.
  - Battery Saver: lighter visual path with a 72 FPS cap, clamped to 60 FPS on 60 Hz Macs.
- Custom max FPS override is available in graphics options.
- Audio underrun handling has been hardened to avoid stale-buffer crackle.
- macOS press-and-hold accent picker is disabled for the game bundle.

### Packaging Notes

- Generated builds, `.app` bundles, and proprietary PAK files are intentionally excluded from git.
- Required game data must be supplied from a legally owned Heretic II install/remastered asset package.
- The repository is intended as the source and porting history for the Apple Silicon app, not a binary distribution archive.

### Known Constraints

- macOS exposes OpenGL 4.1, not 4.6, so the renderer is adapted for Apple's supported path.
- Some inherited compiler warnings remain.
- Save compatibility with older 32-bit builds is not guaranteed.
