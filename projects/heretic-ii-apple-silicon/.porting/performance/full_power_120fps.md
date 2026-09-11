# M11 - Full Power 120 FPS Mode

Date: 2026-06-18

## Verdict

Full Power 120 FPS is accepted for the M11 gate with a pacing caveat.

The profile now locks to a fixed 120 FPS target on displays that support 120 Hz or higher, caps automatically below 120 on lower-refresh displays, uses a higher visual feature set than Power Saver, and does not live-hop between targets during play.

The measured OpenGL run is playable and recommendable as the Full Power profile, but it is not yet console-perfect. The 60-second sample held a 120 target with a median frame time near the 8.33 ms budget, while p95/p99 still show occasional pacing spikes. Those spikes are documented as follow-up optimization work rather than hidden by adaptive target changes.

## Profile Behavior

Full Power is `r_graphics_profile 0`.

| Setting | Value | User benefit |
| --- | ---: | --- |
| FPS target | 120 when display supports it | High-refresh feel without chasing unstable 144 FPS. |
| Lower-refresh displays | Capped to detected display refresh | Avoids asking 60/72/90 Hz screens to draw impossible targets. |
| Frame budget | 8.33 ms | Correct budget for 120 FPS. |
| VSync | Off | Avoids missed-vblank stalls while OpenGL pacing is being tuned. |
| Adaptive FPS | Off | Prevents target hopping during play. |
| HD textures | On | Keeps the remastered look. |
| Bloom | On | Adds visible Full Power glow/lighting richness. |
| Detail level | 2 | Higher scene detail than Power Saver. |
| SSAO | Off | Still too expensive/subtle for the current OpenGL profile. |
| Dynamic shadows | Off | Avoids major spikes in heavy scenes. |
| Reflections | Off | Avoids extra render passes. |

## Code Changes

| Area | Change |
| --- | --- |
| `src/client/menus/menu_video.c` | Full Power now resolves to `min(120, display_refresh)` instead of chasing the monitor's maximum refresh. |
| `src/ref_gl3/src/gl3_SDL.c` | Renderer-side profile enforcement now uses the same fixed 120 cap and logs the resolved display/profile cap. |
| `src/ref_gl3/src/gl3_SDL.c` | Full Power keeps bloom enabled and detail level higher than Power Saver while retaining the expensive-feature cuts needed for stable OpenGL play. |

## Evidence Files

| Artifact | Path |
| --- | --- |
| 120 FPS frame log | `.porting/performance/m11_full_power_120_display3_frame_log.csv` |
| 120 FPS process sample | `.porting/performance/m11_full_power_120_display3_process.csv` |
| 120 FPS analysis | `.porting/performance/m11_full_power_120_display3_analysis.json` |
| 120 FPS runtime log | `.porting/runtime_logs/m11_full_power_120_display3.log` |
| 120 FPS screenshot | `.porting/screenshots/m11_full_power_120_display3.png` |
| Build log | `.porting/build_logs/m11_full_power_120_build.log` |

## Display Target Proof

The test was launched directly on the required left 1080p LG UltraGear monitor using `vid_display_index 3`. No post-launch window move was used.

| Check | Result |
| --- | --- |
| Target display | `LG ULTRAGEAR (2)` |
| SDL display index | `3` |
| Display mode | `1920x1080 @ 144 Hz` |
| Game mode | Windowed |
| Requested mode | `1920x1080` |
| Actual drawable | `1920x1018` |
| Renderer | `OpenGL 4.1` |

Runtime proof:

```text
Window display target: 3
Display refresh 144.0 Hz: profile 0, vid_maxfps 120, cl_maxfps 120
Window drawable: requested 1920x1080, drawable 1920x1018
Actual drawable mode: 1920x1018
```

The `1920x1018` drawable is expected in normal macOS resizable windowed mode because the title bar consumes part of the physical 1080p screen height.

## Frame Pacing Results

Primary 60-second run on `ssdocks`, Full Power profile, frame logging enabled:

| Metric | All frames | Steady after 5s |
| --- | ---: | ---: |
| Frames logged | 6,198 | 6,177 |
| Duration | 58.0 s | 53.0 s |
| Target FPS values seen | 120 only | 120 only |
| Effective average FPS | 113.98 | 116.05 |
| Average frame time | 8.774 ms | 8.617 ms |
| Median frame time | 8.397 ms | 8.397 ms |
| 95th percentile | 9.281 ms | 9.277 ms |
| 99th percentile | 13.301 ms | 13.223 ms |
| Frames over 9 ms | 367 | 365 |
| Frames over 10 ms | 198 | 196 |
| Frames over 12 ms | 108 | 106 |
| Audio underruns | 0 | 0 |

The median is close to the 120 FPS budget, but p95/p99 are above budget. That means the mode feels high refresh most of the time, but it still has pacing spikes that should be tackled in follow-up renderer work.

## GPU And Resource Behavior

| Metric | Result |
| --- | ---: |
| GPU average frame cost | 3.14 ms |
| GPU 95th percentile | 4.79 ms |
| GPU 99th percentile | 6.69 ms |
| GPU max | 43.06 ms |
| Process CPU average | 70.1% of one core |
| Process CPU 95th percentile | 88.7% of one core |
| RSS average | 582.5 MB |
| RSS max | 1022.6 MB |

GPU time is usually well under the 8.33 ms frame budget, which suggests many of the remaining 120 FPS pacing misses are likely CPU, driver, synchronization, asset/cache, or bursty render-state behavior rather than pure shader cost alone. The 43 ms GPU max still needs investigation because it can correspond to a visible hitch.

## Visual Acceptance

Full Power is visibly above Power Saver:

- Bloom is enabled.
- Detail level is higher.
- HD textures remain enabled.
- FPS target is doubled from Power Saver's 60 FPS to 120 FPS on high-refresh displays.

The profile intentionally leaves SSAO, dynamic shadows, and reflections off for now because those features are less important than stable frame delivery in OpenGL and have historically contributed to spikes.

## Acceptance Checklist

| Criterion | Status | Evidence |
| --- | --- | --- |
| Lock target to 120 FPS on 120+ Hz displays | Pass | Runtime log shows 144 Hz display resolving to `vid_maxfps 120`, `cl_maxfps 120`. |
| Cap below 120 on lower-refresh displays | Pass | Resolver uses `min(120, display_refresh)`. |
| Higher quality than Power Saver | Pass | Bloom on, detail level 2. |
| Avoid live target hopping | Pass | Frame log target values are `120` only; no adaptive Full Power target changes in runtime log. |
| Measure frame pacing | Pass | Full frame CSV and JSON analysis recorded. |
| Stable enough to recommend or blockers documented | Pass with caveat | Recommendable as Full Power 120, but p95/p99 spikes are documented for follow-up. |

## Known Issues

- The 120 FPS profile is not yet a perfect locked-120 experience. Median pacing is close, but p95/p99 exceed the 8.33 ms budget.
- CPU cost is higher than Power Saver, as expected, but should still be profiled for avoidable per-frame churn.
- Occasional large GPU samples remain. These may come from transient OpenGL driver work, FBO/state churn, particle/alpha bursts, or texture/cache activity.
- This was a controlled 60-second sample, not a 10-minute soak across multiple heavy maps.

## Next Action

Move to the next performance milestone with a focus on removing the remaining 120 FPS spikes:

- Add a repeatable heavy-scene route so 60, 90, and 120 FPS modes can be compared on identical camera paths.
- Profile CPU-side render submission and redundant OpenGL state updates.
- Keep alpha particles and spell effects under review, because the sampled scene averaged about 107 alpha-particle entries.
- Investigate the rare high GPU samples separately from the normal 3-7 ms GPU frame cost.
