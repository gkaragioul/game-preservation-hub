# Milestone 19 - Metal Feasibility Audit

Date: 2026-06-18
Current shipping renderer: `ref_gl3.dylib`
Current runtime API: OpenGL 4.1 Core Profile on Apple's OpenGL compatibility layer
Decision: **DELAY Metal implementation**

## Status

Accepted for M19.

This milestone is an audit only. The user explicitly instructed that the project is OpenGL-only for now and that Metal implementation should not proceed. The correct outcome is therefore an evidence-backed decision, not a renderer rewrite.

## Decision

**DELAY.**

Keep OpenGL as the active renderer for the current milestone sequence. Do not start M20 Metal foundation work unless the user explicitly approves a Metal comparison/prototype later.

Metal is promising for Apple Silicon because it can remove Apple OpenGL driver overhead and give the port explicit control over command buffers, render targets, and presentation. However, the existing evidence does not prove that Metal is the specific fix for the remaining Full Power 120 FPS pacing misses. Power Saver 60 FPS is already stable and efficient on OpenGL, and Full Power's misses still need a tighter CPU/driver/synchronization profile before a renderer rewrite is justified.

## Acceptance Checklist

| Criterion | Result | Evidence |
| --- | --- | --- |
| Map OpenGL renderer responsibilities | Met | Responsibility map below, `src/ref_gl3/src`, `src/client/ref.h` |
| Identify what Metal would replace | Met | Replacement map below, `src/ref_metal/src/metal_Main.m` |
| Estimate effort | Met | Effort section below |
| Estimate risk | Met | Risk section below |
| Estimate expected benefit | Met | Benefit section below |
| Decide GO / DELAY / DO NOT | Met | Decision is **DELAY** |

## Current Renderer Baseline

The active app uses OpenGL:

- Runtime title: `Refresh: OpenGL 4.1`
- GL version line: `GL_VERSION: 4.1 Metal - 90.5`
- Active app bundle renderer: `ref_gl3.dylib`

The `GL_VERSION` text includes `Metal` because Apple's OpenGL implementation is backed by Apple platform internals. It does not mean the game is using this project's Metal renderer.

### Power Saver 60 FPS Baseline

M18 proves the current OpenGL renderer can meet the battery-mode goal:

| Metric | M18 10-min steady result |
| --- | ---: |
| Average frame time | 16.731 ms |
| P50 | 16.729 ms |
| P95 | 16.787 ms |
| P99 | 16.793 ms |
| Max | 32.059 ms |
| Frames over 20 ms | 4 |
| Frames over 33.34 ms | 0 |
| Average GPU time | 1.759 ms |
| GPU P95 | 3.267 ms |
| GPU P99 | 4.217 ms |
| Audio underruns | 0 |
| 5-min CPU sample | 14.1% CPU, 1.4% MEM |
| 10-min CPU sample | 12.8% CPU, 1.4% MEM |

Evidence:

- `.porting/qa/qa_report.md`
- `.porting/qa/m18_10min_powersaver_steady_summary.json`
- `.porting/performance/m18_10min_powersaver_frame_log.csv`
- `.porting/runtime_logs/m18_10min_powersaver_display3.log`

Conclusion: Metal is **not required** to make Power Saver 60 FPS stable.

### Full Power 120 FPS Baseline

OpenGL Full Power is playable and fixed-target, but not console-stable:

| Run | Key result |
| --- | --- |
| M11 Full Power 120 | steady avg 8.617 ms, p50 8.397 ms, p95 9.277 ms, p99 13.223 ms, effective 116.0 FPS |
| M11 GPU | avg 3.138 ms, p95 4.793 ms, p99 6.693 ms, max 43.057 ms |
| M11 process | CPU avg 70.1% of one core, p95 88.7% |
| M12 120 VSync off | core avg 9.060 ms, p95 11.258 ms, p99 17.624 ms, effective 110.37 FPS |
| M12 120 VSync on | core avg 10.457 ms, p95 14.651 ms, p99 19.978 ms, effective 95.63 FPS |
| M13 state-cache pass | same-window p99 improved from 17.672 ms to 13.386 ms, GPU p95 from 7.397 ms to 3.809 ms, but 120 remained imperfect |

Evidence:

- `.porting/performance/full_power_120fps.md`
- `.porting/performance/frame_pacing.md`
- `.porting/performance/opengl_optimization.md`
- `.porting/performance/m11_full_power_120_display3_analysis.json`
- `.porting/performance/m12_frame_pacing_analysis.json`
- `.porting/performance/m13_opengl_optimization_same_window_analysis.json`

Conclusion: Full Power misses are real, but the current evidence points to mixed CPU/driver/sync/render-burst behavior rather than a proven "OpenGL alone is the bottleneck" diagnosis.

## OpenGL Renderer Responsibility Map

| Responsibility | OpenGL implementation | Notes |
| --- | --- | --- |
| Renderer API contract | `src/client/ref.h`, `src/ref_gl3/src/gl3_Main.c::GetRefAPI` | Exports registration, frame rendering, 2D drawing, cinematics, resize, context lifecycle |
| SDL/macOS window and OpenGL context | `src/client/glimp_sdl3.c`, `src/ref_gl3/src/gl3_SDL.c` | Creates the window/context, targets display 3, handles drawable size and swap interval |
| Frame lifecycle and presentation | `gl3_Main.c`, `gl3_SDL.c` | `BeginFrame`, `RenderFrame`, `EndFrame`, FBO setup, final post pass, swap |
| Image and texture loading | `gl3_Image.c` | M8/M32/HD texture upload, gamma, filtering, mip levels, particle/sprite alpha fixes |
| 2D HUD/menu/book/cinematic drawing | `gl3_Draw.c` | HUD, menus, book UI, console chars, cinematic upload/draw |
| World/BSP surface rendering | `gl3_Surface.c`, `gl3_Lightmap.c`, `gl3_Light.c`, `gl3_Shaders.c` | Lightmapped world surfaces, dynamic lights, fog, shader state |
| Models and flex models | `gl3_Model.c`, `gl3_FlexModel.c` | Entity models, skin registration, animation frames, vertex processing |
| Sprites and alpha FX | `gl3_Sprite.c`, `gl3_Main.c::R_DrawParticles` | Alpha entities, sprites, additive and non-additive particles |
| Water, sky, reflections | `gl3_Warp.c`, `gl3_Sky.c`, `gl3_Main.c` | Turbulent water, skyboxes, reflection pass |
| Post-processing | `gl3_Shaders.c`, `gl3_Main.c` | HDR FBO, bloom, SSAO, gamma/final pass |
| Screenshots and misc rendering utilities | `gl3_Misc.c`, `gl3_Draw.c` | Readback, auto screenshots, draw helpers |
| Renderer worker/state optimization | `gl3_Jobs.c`, `gl3_Local.h`, `gl3_Main.c` | Worker jobs, cached VAO/VBO/texture state, render stats |

Scope size:

- `src/ref_gl3/src`: about 16.6k lines across renderer C/H files.
- `src/ref_metal/src/metal_Main.m`: about 6.9k lines in one Objective-C/Metal file.

## What Metal Would Replace

| Current OpenGL area | Metal replacement needed |
| --- | --- |
| SDL OpenGL context | SDL Metal view / `CAMetalLayer`, device, queue, drawable lifecycle |
| GL texture objects | `MTLTexture` creation, upload, gamma conversion, atlas/mip/filter parity |
| GL framebuffers/FBOs | Metal render targets for scene, depth, bloom, SSAO, reflections, cinematics |
| GLSL shader programs | Metal pipeline states and MSL shader functions |
| GL state machine | Explicit pipeline, sampler, depth/stencil, blend, and resource bindings |
| `glDrawArrays`/surface draws | Metal command encoder draw calls and buffer management |
| `glBlendFunc` behavior | Metal blend descriptors matching alpha/additive semantics |
| OpenGL screenshots/readback | Metal blit/readback buffers with correct orientation and row alignment |
| `SDL_GL_SwapWindow` | `presentDrawable` plus command buffer commit/completion timing |
| GL timing queries | Metal command buffer timing or CPU-side instrumentation |

The existing `src/ref_metal/src/metal_Main.m` already exports many of the same `refexport_t` functions, including registration, draw calls, frame lifecycle, context lifecycle, resizing, particles, surfaces, sky, water, post effects, and cinematics. That is useful, but it is not enough to call Metal shippable: it is not the active renderer, not bundled as the only renderer, not regression-tested against M06-M18 acceptance, and not covered by the recent OpenGL FX corrections.

## Expected Benefit

Likely benefits if a Metal renderer reaches parity:

- Lower Apple-platform driver overhead than OpenGL.
- More explicit presentation and command-buffer control.
- Cleaner ownership of render targets and post-process passes.
- Better long-term Apple Silicon fit.
- Potentially better Full Power frame pacing if the dominant bottleneck is OpenGL driver/state submission overhead.
- Better future ceiling for high-refresh displays after CPU/render submission is profiled.

Benefits that are **not proven yet**:

- A guaranteed locked 120 FPS mode.
- A guaranteed 144 FPS mode.
- Lower battery use than the current OpenGL Power Saver 60 mode.
- Automatic elimination of particle/alpha visual regressions.

## Effort Estimate

Assuming the existing Metal file is used as the starting point:

| Workstream | Estimate |
| --- | ---: |
| Compile/activation audit, build flags, loader integration | 1-2 days |
| Keep OpenGL selectable while adding Metal as an optional renderer | 2-4 days |
| 2D/menu/book/cinematic parity | 3-5 days |
| Texture, palette, HD replacement, mip/filter parity | 3-5 days |
| World BSP, lightmap, fog, sky, water, reflection parity | 1-2 weeks |
| Models, flex models, sprites, alpha entities, particles, spell FX parity | 1-2 weeks |
| Frame timing, screenshots, resize/fullscreen/window transitions | 3-5 days |
| Packaging/signing/runtime QA across M06-M18 gates | 1 week |

Realistic shippable parity estimate: **4-7 weeks**.

If the existing Metal file is more complete than expected, the low end improves. If it has hidden visual or lifecycle problems, the high end is more likely.

## Risk Estimate

| Risk | Level | Why it matters |
| --- | --- | --- |
| Visual regression | High | Recent GL3 work fixed menu positioning, loading, particle cards, spell-cooking FX, water/HUD/window behavior. Metal must match all of it. |
| FX/particle regression | High | The spell-cooking bug came from subtle atlas/blend/routing behavior. Metal needs exact particle and alpha semantics. |
| Performance uncertainty | Medium-High | Metal may reduce driver overhead, but if the bottleneck is game logic, CPU submission, particles, asset/cache bursts, or timing, Metal alone will not lock 120. |
| QA burden | High | Every M06-M18 acceptance gate would need rerun for Metal. |
| Packaging complexity | Medium | A second renderer changes bundle contents, loader behavior, signing, and support surface. |
| Schedule distraction | High | Power Saver 60 is already stable; Metal now would divert from OpenGL polish and remaining milestone closure. |
| User-direction conflict | Blocking | The user explicitly said OpenGL only for now. |

## GO / DELAY / DO NOT

Decision: **DELAY.**

Rationale:

- OpenGL Power Saver 60 FPS is already stable and battery-friendly by current evidence.
- OpenGL Full Power 120 FPS is not perfect, but its evidence does not yet isolate the renderer API as the root cause.
- The existing Metal source is substantial but not active, not gated, and not parity-proven.
- Starting a Metal implementation now would violate the OpenGL-only instruction and create a large regression surface.

## Conditions To Revisit Metal

Metal becomes a better candidate if one of these becomes true:

1. The user explicitly approves a Metal comparison/prototype.
2. A deterministic 120 FPS heavy-scene route proves OpenGL driver/state submission overhead dominates frame misses.
3. OpenGL optimization reaches diminishing returns while GPU time remains low and CPU/driver submission remains high.
4. A separate Metal branch can be tested without replacing OpenGL or disturbing the stable Power Saver path.

## Recommended Next Step

Do **not** proceed into Metal implementation.

The next useful performance milestone should stay OpenGL-focused:

- Build a deterministic heavy-scene benchmark route.
- Capture CPU-side render submission timing around world, alpha entities, particles, post passes, and swap/present.
- Separate simulation, renderer submission, GPU work, and presentation waits.
- Preserve the newly fixed spell-cooking alpha path while profiling particle-heavy scenes.

Only after that evidence should the project decide whether Metal is the right next renderer milestone.
