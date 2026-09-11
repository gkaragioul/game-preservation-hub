# Public Summary

Date: 2026-06-18

## Project

Heretic II Apple Silicon is a native macOS porting and compatibility effort for running Heretic II Remastered on Apple Silicon Macs.

The repository is intended to contain source code, build scripts, compatibility work, renderer/audio/windowing fixes, and documentation. It is not a game-data distribution repository.

## Current State

- Native arm64 build works.
- SDL3 Cocoa window/input path works.
- SDL3/CoreAudio sound path works.
- Active renderer is `ref_gl3.dylib` on macOS OpenGL 4.1.
- The Apple runtime may print `GL_VERSION: 4.1 Metal - 90.5`; this is Apple's OpenGL compatibility implementation, not a native Metal renderer.
- Core gameplay, menu navigation, HUD, particles, sprites, alpha surfaces, water/sky/lighting, screenshots, and graphics profiles have been exercised.
- Power Saver targets 60 FPS.
- Full Power targets 120 FPS where supported.
- Custom FPS cap override is available.

## Latest Verified Milestone

M21 verified the OpenGL spell-combat route:

- Repeatable `ssdocks` route with spell cooking, release, hit FX, alpha particles, and movement.
- Power Saver final frame log: `.porting/performance/m21_60_finalroute_frame_log.csv`.
- Full Power final frame log: `.porting/performance/m21_120_finalroute_frame_log.csv`.
- Visual proof shows the previous square/diamond spell-card artifacts removed in both profiles.
- 60 FPS route is effectively locked for normal gameplay.
- 120 FPS route is mostly steady but still has rare spikes that should be tuned through entity/alpha ordering and frame pacing work.

## Distribution Boundary

Protected Heretic II retail data, remastered PAKs, HD textures, videos, generated builds, and `.app` bundles should not be committed to the repository.

Users must provide legally owned game data locally.

## Next Focus

- Public documentation cleanup.
- Packaging and release notes.
- QA stability pass.
- Further OpenGL optimization around entity/alpha draw ordering and presentation pacing.
