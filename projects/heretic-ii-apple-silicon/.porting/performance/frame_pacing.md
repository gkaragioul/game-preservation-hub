# M12 - Frame Pacing Benchmark

Date: 2026-06-18

## Verdict

M12 is accepted.

The project now has full-frame pacing evidence for fixed 60 FPS and fixed 120 FPS runs, with VSync both on and off. The existing `scr_frame_log 1` benchmark path logs every frame to CSV, including target FPS, CPU-visible frame time, GPU time, profile flags, particle counts, and audio counters.

The evidence confirms Power Saver 60 FPS is stable. Full Power 120 FPS is target-locked, but the frame-time data shows it is not yet console-stable, which becomes the focus for M13.

## Benchmark Mode

Benchmark logging uses `scr_frame_log 1`.

CSV columns include:

- frame index
- timestamp
- target FPS
- frame time
- GPU time
- entity/particle counts
- graphics profile flags
- VSync state
- audio underrun counters

The benchmark logs every rendered frame, not only spikes.

## Test Matrix

All runs were launched directly on the required left 1080p LG UltraGear monitor using `vid_display_index 3`.

| Case | Profile | Custom cap | VSync override | Map |
| --- | --- | ---: | ---: | --- |
| `m12_60_vsync_on` | Power Saver | 60 | On | `ssdocks` |
| `m12_60_vsync_off` | Power Saver | 60 | Off | `ssdocks` |
| `m12_120_vsync_off` | Full Power | 120 | Off | `ssdocks` |
| `m12_120_vsync_on` | Full Power | 120 | On | `ssdocks` |

Runtime display proof is present in every log:

```text
Window display target: 3
Window drawable: requested 1920x1080, drawable 1920x1018
Actual drawable mode: 1920x1018
```

The 60 FPS runs resolved to:

```text
Display refresh 144.0 Hz: profile 1, vid_maxfps 60, cl_maxfps 60
```

The 120 FPS runs resolved to:

```text
Display refresh 144.0 Hz: profile 0, vid_maxfps 120, cl_maxfps 120
```

## Evidence Files

| Artifact | Path |
| --- | --- |
| Analysis JSON | `.porting/performance/m12_frame_pacing_analysis.json` |
| 60 FPS VSync on frame log | `.porting/performance/m12_60_vsync_on_frame_log.csv` |
| 60 FPS VSync off frame log | `.porting/performance/m12_60_vsync_off_frame_log.csv` |
| 120 FPS VSync off frame log | `.porting/performance/m12_120_vsync_off_frame_log.csv` |
| 120 FPS VSync on frame log | `.porting/performance/m12_120_vsync_on_frame_log.csv` |
| 60 FPS VSync on runtime log | `.porting/runtime_logs/m12_60_vsync_on.log` |
| 60 FPS VSync off runtime log | `.porting/runtime_logs/m12_60_vsync_off.log` |
| 120 FPS VSync off runtime log | `.porting/runtime_logs/m12_120_vsync_off.log` |
| 120 FPS VSync on runtime log | `.porting/runtime_logs/m12_120_vsync_on.log` |
| Process samples | `.porting/performance/m12_*_process.csv` |

## Core Frame-Time Results

The table below uses the stable comparison window: first 5 seconds trimmed and final 1 second trimmed to avoid startup and shutdown/kill artifacts.

| Case | Frames | Effective FPS | Avg ms | P50 ms | P95 ms | P99 ms | GPU P95 ms | CPU avg |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 60 FPS, VSync on | 1,652 | 57.50 | 17.391 | 16.721 | 16.777 | 16.782 | 2.998 | 27.0% |
| 60 FPS, VSync off | 1,734 | 59.50 | 16.806 | 16.725 | 16.779 | 16.892 | 4.187 | 30.0% |
| 120 FPS, VSync off | 3,111 | 110.37 | 9.060 | 8.424 | 11.258 | 17.624 | 7.338 | 66.6% |
| 120 FPS, VSync on | 2,749 | 95.63 | 10.457 | 8.776 | 14.651 | 19.978 | 4.495 | 45.8% |

## Findings

Power Saver 60 FPS is the stable profile:

- Median and p95 frame times sit essentially on the 16.67 ms budget.
- VSync on lowers GPU cost and average CPU cost.
- VSync off gives slightly better effective FPS but somewhat higher GPU P95.
- Audio underruns stayed at 0 in all runs.

Full Power 120 FPS is not yet stable enough to call console-like:

- The target remains fixed at 120 and does not live-hop.
- Median frame time is near 8.33 ms.
- P95/P99 are above budget, especially with VSync on.
- VSync on at 120 is worse for frame pacing in this sample, likely because missed presentation intervals amplify timing variance.
- VSync off is the better current 120 FPS testing mode, but it still needs optimization.

## Acceptance Checklist

| Criterion | Status | Evidence |
| --- | --- | --- |
| Logs every frame, not only spikes | Pass | `scr_frame_log 1` CSVs include every frame. |
| Fixed 60 FPS test | Pass | `m12_60_vsync_on/off_frame_log.csv`. |
| Fixed 120 FPS test | Pass | `m12_120_vsync_on/off_frame_log.csv`. |
| Same map/camera start | Pass | All runs launch `map ssdocks` through the same command harness. |
| VSync on/off tested briefly | Pass | Separate VSync on/off samples for 60 and 120. |
| Written evidence report | Pass | This file plus JSON analysis. |

## Known Issues

- The route is a consistent idle/map start, not a deterministic recorded camera path. M13 should add a more controlled heavy-scene route if possible.
- The 120 FPS profile is still limited by pacing spikes, not by target selection.
- Raw max frame times include startup/shutdown artifacts, so optimization decisions should use both raw and trimmed/core analysis.

## Next Action

Move to M13: reduce OpenGL render cost and frame-time variance without damaging visual correctness. Priority areas:

- redundant OpenGL state changes
- alpha entity and particle bursts
- texture/lightmap/material batching
- FBO resize/reinit behavior
- VSync and frame limiter interaction at 120 FPS
