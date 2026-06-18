# M10 - Power Saver 60 FPS Mode

Date: 2026-06-18

## Verdict

Power Saver 60 FPS is accepted for the M10 gate.

The profile locks the renderer and client to a fixed 60 FPS target, disables adaptive target hopping, keeps VSync enabled, and uses a visually conservative feature set that keeps the game looking like the remaster while removing the expensive extras that are least obvious during play.

## Profile Behavior

Power Saver is `r_graphics_profile 1`.

| Setting | Value | User benefit |
| --- | ---: | --- |
| FPS target | 60 | Stable battery-friendly frame pacing. |
| Frame budget | 16.67 ms | Correct budget for 60 FPS. |
| VSync | On | Avoids tearing and reduces unnecessary present churn. |
| Adaptive FPS | Off | Prevents live target hopping during play. |
| HD textures | On | Keeps the remastered look. |
| Antialiasing | Off | Saves GPU cost; acceptable at 1080p/1440p. |
| Bloom | Off | Saves post-process cost; not essential for gameplay readability. |
| SSAO | Off | Saves post-process cost; subtle visual loss. |
| Dynamic shadows | Off | Saves render work; original-lighting look remains acceptable. |
| Reflections | Off | Saves render work; not essential in normal play. |
| Detail level | 1 | Keeps scene readable while lowering extra detail cost. |

## Evidence Files

| Artifact | Path |
| --- | --- |
| Corrected direct-display frame log | `.porting/performance/m10_powersaver_direct_display3_frame_log.csv` |
| Corrected direct-display process sample | `.porting/performance/m10_powersaver_direct_display3_process.csv` |
| Corrected direct-display analysis | `.porting/performance/m10_powersaver_direct_display3_analysis.json` |
| Corrected direct-display screenshot | `.porting/screenshots/m10_powersaver_direct_display3.png` |
| Corrected direct-display runtime log | `.porting/runtime_logs/m10_powersaver_direct_display3.log` |
| Clean notify visual check | `.porting/screenshots/con_drawnotify_visual_check.png` |
| Clean notify runtime log | `.porting/runtime_logs/con_drawnotify_visual_check.log` |
| Direct app-wrapper display proof | `.porting/screenshots/display_target_app_wrapper_ultragear2.png` |
| Direct app-wrapper display log | `.porting/runtime_logs/display_target_app_wrapper.log` |
| Historical/supporting analysis | `.porting/performance/m10_power_saver_60fps_analysis.json` |

## Frame Pacing Results

Corrected 60-second direct-display run:

| Metric | Result |
| --- | ---: |
| Display | Left 1080p LG UltraGear, SDL display 3 |
| Launch method | Direct engine target, no post-launch window move |
| Target FPS values seen | 60 only |
| Total frames logged | 3,165 |
| Total duration | 57.8 seconds |
| Steady-state frames | 3,137 |
| Steady-state duration | 52.8 seconds |
| Average frame time | 16.848 ms |
| Effective average FPS | 59.36 |
| Median frame time | 16.724 ms |
| 95th percentile | 16.777 ms |
| 99th percentile | 16.817 ms |
| Frames over 17 ms | 29 / 3,137 |
| Frames over 18 ms | 19 / 3,137 |
| Frames over 20 ms | 11 / 3,137 |
| Audio underruns | 0 |

Historical supporting runs also showed target `60` only and similar median/p95 pacing. Those earlier samples are no longer used as the primary gate because at least one used a post-launch window move while the display-target work was still incomplete.

## Resource Behavior

Corrected direct-display run:

| Metric | Result |
| --- | ---: |
| GPU average frame cost | 2.04 ms |
| GPU 95th percentile | 4.95 ms |
| GPU max, steady-state | 20.77 ms |
| Process CPU average | 35.4% of one core |
| Process CPU 95th percentile | 70.4% of one core |
| RSS average | 373.8 MB |
| RSS max | 1086.8 MB |

On macOS, `%CPU` is measured relative to one CPU core, so the process average is below half a core during the stable samples. GPU time is comfortably below the 16.67 ms budget, leaving large GPU headroom.

## Visual Acceptance

The Power Saver image remains visually acceptable because the profile keeps HD textures enabled and only removes optional post-process / extra-lighting work. The direct-display screenshots show the game presenting correctly in windowed mode on the requested 1080p display.

Console notify text is now disabled in normal play via `con_drawnotify 0`, so renderer/loading logs no longer paint yellow debug text over the top-left of the game. The full console and runtime logs still keep those messages for debugging.

Known visual tradeoffs:

- No bloom glow in Power Saver.
- No SSAO contact darkening.
- No dynamic shadows/reflections.
- Detail level is reduced from Full Power.

These are acceptable for a battery/laptop profile because geometry, texture quality, HUD, lighting readability, and gameplay visibility remain intact.

## Display Target Correction

Earlier M10 sampling used a post-launch window move as a workaround, which is not acceptable for the project test rule. The engine now has an explicit `vid_display_index` target-display path, and both the repo launcher and repo-local app bundle wrapper pass `+set vid_display_index 3`.

Verified app-wrapper launch:

| Check | Result |
| --- | --- |
| Target display | `LG ULTRAGEAR (2)` |
| SDL display index | `3` |
| Display bounds | `1920x1080` |
| Mode 0 | `1920x1080` |
| Window display target | `3` |
| Resizable window drawable | `1920x1018` |

The `1920x1018` drawable is expected for normal resizable windowed mode on macOS because the title bar and system-reserved usable area are removed from the physical 1080p display. Full physical 1920x1080 requires fullscreen or borderless-window behavior.

## Caveats

- Direct wattage, battery drain, fan speed, and temperature were not measured in this desktop test environment. M10 uses CPU, RSS, GPU-frame-time, and disabled-feature evidence as power proxies.
- The corrected run is a 60-second sample. A future soak test should use a dedicated safe camera/test map or a deterministic demo route for 10-minute unattended validation.
- The screenshot captured during the corrected run landed on a loading/map transition; the runtime and frame logs continued into the run and are the primary acceptance evidence.
- Local Ollama worker review was attempted but failed with `Ollama returned HTTP 400: {"error":"model is required"}`. The report is based on direct CSV/runtime evidence.

## Acceptance Checklist

| Criterion | Status | Evidence |
| --- | --- | --- |
| Lock target to 60 FPS | Pass | Frame logs show only target `60`. |
| Verify 16.67 ms pacing | Pass | Corrected run median/p95 are 16.724/16.777 ms. |
| Reduce expensive features acceptably | Pass | Bloom, SSAO, shadows, reflections, AA off; HD textures stay on. |
| Measure CPU/GPU/resource behavior | Pass | GPU, CPU, RSS logs recorded. |
| Low-resource battery-friendly behavior | Pass with caveat | GPU headroom is strong; CPU is under half a core on average; direct watt/thermal still needs hardware measurement. |
| Visually acceptable | Pass | Direct-display screenshots captured; remastered texture quality remains enabled. |

## Next Action

Create a safe automated performance route for future milestones: no enemy damage, fixed camera path, optional particle/spell trigger points, and a guaranteed 10-minute unattended run on the left 1080p UltraGear.
