# Milestone 20 - OpenGL Performance Gate

Date: 2026-06-18
Renderer: `ref_gl3.dylib`
Machine: Apple M4
Target display: SDL Display 3, `LG ULTRAGEAR (2)`, 1920x1080 at 144 Hz, windowed
Route: `+map ssdocks`, no-input deterministic start camera, 45 seconds, first 10 seconds excluded from analysis

## Guardrail

No Metal implementation was done in this milestone. All work stayed on the OpenGL renderer.

## Route

The controlled route launches directly on the user's left 1080p LG UltraGear monitor:

```text
+set vid_display_index 3
+set vid_ref gl3
+set vid_mode 0
+set vid_fullscreen 0
+map ssdocks
```

This is a deterministic baseline route rather than a worst-case spell-combat route. It is useful for comparing profile caps, phase timing, audio counters, alpha/particle counts, and presentation stability on the same map/camera. A later route should add recorded input or a scripted combat/spell scene for heavier FX coverage.

## Evidence Files

- Build with phase timing: `.porting/build_logs/m20_phase_timing_build.log`
- Power Saver vsync default fix: `.porting/build_logs/m20_powersaver_vsync_cap_build.log`
- Phase post timing fix: `.porting/build_logs/m20_phase_post_fix_build.log`
- Particle alpha-globe upload fix: `.porting/build_logs/fix_particle_alpha_globe_upload_build.log`
- 60 FPS runtime log: `.porting/runtime_logs/m20_60_display3.log`
- 120 FPS runtime log: `.porting/runtime_logs/m20_120_display3.log`
- 60 FPS frame CSV: `.porting/performance/m20_60_frame_log.csv`
- 120 FPS frame CSV: `.porting/performance/m20_120_frame_log.csv`
- Parsed analysis: `.porting/performance/m20_opengl_phase_analysis.json`
- FX proof: `.porting/renderer/particle_alpha_globe_upload_mask.png`

Both runtime logs show:

- `Refresh: OpenGL 4.1`
- `Window display target: 3`
- `GL_RENDERER: Apple M4`
- `GL_VERSION: 4.1 Metal - 90.5`
- `Map: ssdocks`

The `GL_VERSION` string is Apple's OpenGL compatibility layer. It is not this project running a Metal renderer.

## 60 FPS Power Saver Result

Profile: `r_graphics_profile 1`
Cap: `vid_maxfps 60`, `cl_maxfps 60`
Features: bloom off, SSAO off, shadows off, reflections off, detail 1, vsync 0
Samples after warm-up: 1995

- Average frame: 16.749 ms, effective 59.70 FPS
- p50: 16.730 ms
- p95: 16.787 ms
- p99: 16.793 ms
- Max: 41.208 ms
- Frames over 17.0 ms: 6
- Frames over 20 ms: 3
- Frames over 33.34 ms: 1
- GPU p95: 2.439 ms
- GPU p99: 2.641 ms
- Audio underruns: 0
- Max alpha entities: 6
- Max particles: 35 normal, 596 additive/alpha

Phase p95:

- Total renderer CPU phase: 1.741 ms
- World: 0.776 ms
- Entities: 0.831 ms
- Alpha: 0.241 ms
- Particles: 0.044 ms
- Post: 0.034 ms

Verdict for Power Saver: stable enough for the 60 FPS battery target in this baseline route. The exact frame average sits slightly above the mathematical 16.667 ms budget because the limiter is conservative, but only 6 frames exceed a 2 percent tolerance and audio stayed clean.

## 120 FPS Full Power Result

Profile: `r_graphics_profile 0`
Cap: `vid_maxfps 120`, `cl_maxfps 120`
Features: bloom on, SSAO off, shadows off, reflections off, detail 2, vsync 0
Samples after warm-up: 4107

- Average frame: 8.422 ms, effective 118.73 FPS
- p50: 8.397 ms
- p95: 8.455 ms
- p99: 8.461 ms
- Max: 37.422 ms
- Frames over 8.5 ms: 32
- Frames over 20 ms: 2
- Frames over 33.34 ms: 2
- GPU p95: 2.492 ms
- GPU p99: 2.811 ms
- Audio underruns: 0
- Max alpha entities: 139
- Max particles: 45 normal, 832 additive/alpha

Phase p95:

- Total renderer CPU phase: 1.402 ms
- World: 0.622 ms
- Entities: 0.690 ms
- Alpha: 0.353 ms
- Particles: 0.024 ms
- Post: 0.093 ms

Verdict for Full Power: the route is mostly steady at 120 FPS, with rare large outliers. The phase correlations are weak: particles, alpha particles, alpha entities, and GPU time do not explain the general frame cadence in this baseline route. The rare maximums do show occasional spikes in GPU/post/entity timing, so the next investigation should use a heavier spell-combat route to catch whether those are asset/cache, presentation, or specific FX bursts.

## Root Cause Findings

- The OpenGL renderer is not CPU-bound in this baseline route. Renderer CPU p95 is below 2 ms in both profiles.
- Particle draw is not the steady-state bottleneck here. Particle p95 is below 0.05 ms at 60 FPS and below 0.03 ms at 120 FPS.
- Alpha entity count rises much higher in Full Power, but it does not strongly correlate with frame time in this route.
- Audio counters stayed clean, with zero underruns in both runs.
- Power Saver default vsync was causing unreliable direct-map startup and noisy pacing analysis. Power Saver now defaults to fixed 60 engine cap with vsync off unless an explicit test override is used.
- The cooking-spell diamond/card issue was not profile logic. It was source alpha in `particle.m32`'s alpha-globe tile. The upload-time mask removes it for both profiles.

## Acceptance Criteria Check

- Deterministic OpenGL route defined: met.
- Test launches on SDL Display 3, left 1080p LG, windowed: met.
- Fixed 60 and 120 FPS frame logs captured on the same route: met.
- CPU frame time, GPU time, feature flags, particles, alpha entities, and audio underruns separated: met.
- CPU-side timing around major GL phases added: met.
- Correlation of misses with render phases checked: met.
- Spell-cooking alpha route preserved: met, with an additional upload-level alpha-globe mask.
- Evidence-backed verdict produced: met.

## Verdict

Continue OpenGL optimization. Do not reopen Metal now.

The baseline evidence says the renderer can hold 60 FPS Power Saver comfortably on this route and can run a mostly steady 120 FPS Full Power route on the M4, but the rare spikes need a heavier recorded route before claiming console-like stability. The next practical milestone should be a spell-combat benchmark route with reproducible input and screenshot/video proof for the corrected cooking-spell particles.
