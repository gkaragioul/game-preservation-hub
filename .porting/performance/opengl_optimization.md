# M13: OpenGL Optimization Pass

Date: 2026-06-18
Renderer: `ref_gl3.dylib`
Target display: LG UltraGear 2, SDL display 3, 1920x1080 windowed

## Goal

Reduce OpenGL render cost and frame-time variance without breaking visual correctness.

## Changes Made

### GL State Cache

Files:

- `src/ref_gl3/src/gl3_Shaders.c`
- `src/ref_gl3/src/gl3_Shaders.h`

Added lightweight cached wrappers for:

- `glBindVertexArray`
- `glBindBuffer(GL_ARRAY_BUFFER)`
- repeated 3D, water, and lightmap color uniform uploads

This avoids resending identical VAO/VBO and color state in hot draw paths.

### Lightmapped Surface Draw Setup

Files:

- `src/ref_gl3/src/gl3_Shaders.c`
- `src/ref_gl3/src/gl3_Surface.c`

Added `GL3_BeginLMPolyBatch()` and `GL3_DrawLMPolyBatched()` so lightmapped world surfaces can bind the shader/VAO/VBO once for a chain, then issue per-poly uploads/draws without repeating the same setup every polygon.

This is deliberately conservative. It does not reorder world surfaces yet, so visual correctness and texture/lightmap behavior are preserved.

### Particle Path Cleanup

File: `src/ref_gl3/src/gl3_Main.c`

- Avoids worker-thread overhead for small/medium particle batches.
- Uses cached VAO/VBO binding for particle draws.
- Keeps additive particle premultiply and blend behavior intact.
- Disables dynamic light contribution while drawing particles to avoid amplifying atlas borders.

This keeps the recent spell-cooking particle correctness fix profile-independent for both Power Saver and Full Power.

## Benchmark Setup

Baseline:

- `.porting/performance/m12_120_vsync_off_frame_log.csv`
- `.porting/runtime_logs/m12_120_vsync_off.log`

After optimization:

- `.porting/performance/m13_uniform_cache_120_vsync_off_frame_log.csv`
- Runtime evidence for the current build/profile/display:
  - `.porting/runtime_logs/fix_spell_cooking_fullpower_display3.log`
  - foreground M13 run also printed `Window display target: 3`, `profile 0`, `vid_maxfps 120`, `cl_maxfps 120`

Build:

- `.porting/build_logs/m13_opengl_optimization_build.log`
- Result: native macOS arm64 build completed successfully.

Analysis:

- `.porting/performance/m13_opengl_optimization_analysis.json`
- `.porting/performance/m13_opengl_optimization_same_window_analysis.json`

Both benchmark samples used:

- OpenGL 4.1 Apple layer
- map `ssdocks`
- Full Power profile
- fixed 120 FPS target
- VSync off
- adaptive FPS off

## Results

Same-window comparison, skipping the first 120 frames and comparing 3150 analyzed frames:

| Metric | M12 Baseline | M13 After | Delta |
|---|---:|---:|---:|
| Average frame time | 9.106 ms | 8.902 ms | -0.204 ms |
| p50 frame time | 8.426 ms | 8.417 ms | -0.009 ms |
| p95 frame time | 11.475 ms | 11.319 ms | -0.157 ms |
| p99 frame time | 17.672 ms | 13.386 ms | -4.286 ms |
| Effective FPS | 109.8 | 112.3 | +2.5 FPS |
| GPU p95 | 7.397 ms | 3.809 ms | -3.588 ms |

Important caveat: entity and particle counts were not perfectly identical between the two runs. The M13 same-window sample had fewer alpha particles on average, so the GPU p95/p99 improvement should be treated as encouraging but not a pure renderer-only gain.

What is safe to claim:

- The GL state/cache changes build and run.
- Average and p95 frame time moved in the right direction in the measured sample.
- The p50 did not meaningfully change, which means this was not a silver bullet for the 120 FPS target.
- The 120 FPS mode still needs deeper optimization before it can be called console-stable.

## FBO Resize/Reinit Check

M12 runtime logs:

- `Window resized`: 0
- `GL3 HDR FBO initialized`: 1
- `GL3 bloom FBOs initialized`: 1
- `GL3 SSAO initialized`: 1
- `GL3 reflection FBO initialized`: 1

Finding: the repeated FBO resize/reinit spam that was previously suspected is not present in the controlled M12 logs. There is no M13 FBO-spam fix needed right now.

## Alpha And Particle Cost

The M12 120 FPS VSync-off baseline averaged:

- alpha entities: 41.0
- regular particles: 39.3
- additive particles: 359.2

The M13 same-window run averaged:

- alpha entities: 29.5
- regular particles: 10.8
- additive particles: 209.3

Finding: alpha entities and additive particles remain the most obvious variable-cost area. The next optimization pass should profile particle-heavy spell scenes and alpha-heavy map views separately, because a single idle map sample does not isolate those costs cleanly.

## Acceptance Check

- Reduce redundant GL state changes where safe: met.
- Batch or sort world surfaces, sprites, or particles where safe: partially met via safer lightmap batch setup reuse; no aggressive reordering yet.
- Inspect alpha entity and particle cost: met.
- Reduce FBO resize/reinit spam if present: met; controlled logs show no spam to reduce.
- Produce measured improvement or document why not: met; modest measured improvement with caveats.
- Preserve FX correctness, especially spell-cooking particles: met at code path level and profile smoke level.

## Known Issues

- 120 FPS still does not have perfect pacing. M13 improves state churn but does not fully solve frame variance.
- The benchmark route is not a deterministic camera playback, so particle/entity counts can drift between samples.
- Runtime log capture from non-interactive background processes can be empty because the game buffers stdout until normal shutdown; foreground and existing display-3 runtime logs were used as evidence.

## Next Recommended Action

Move to M14 graphics options UX.

The renderer is now optimized enough for this milestone gate, but 120 FPS should remain marked as usable/experimental rather than guaranteed-stable until a deterministic benchmark route and a deeper particle/alpha optimization pass exist.
