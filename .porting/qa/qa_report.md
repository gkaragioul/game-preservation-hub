# Milestone 18 - QA And Stability Pass

## Status

Accepted.

## Scope

This pass focused on controlled OpenGL/Power Saver stability on the required 1080p LG UltraGear display, plus review of evidence gathered in the previous milestone passes.

## 10-Minute Power Saver Soak

Launch:

```text
vid_display_index 3
vid_ref gl3
vid_mode 0
vid_fullscreen 0
r_graphics_profile 1
r_custom_maxfps 0
scr_adaptive_fps 0
scr_frame_log 1
map ssdocks
```

Runtime evidence:

- Log: `.porting/runtime_logs/m18_10min_powersaver_display3.log`
- Frame log: `.porting/performance/m18_10min_powersaver_frame_log.csv`
- Raw summary: `.porting/qa/m18_10min_powersaver_summary.json`
- Steady-state summary: `.porting/qa/m18_10min_powersaver_steady_summary.json`
- 5-minute process sample: `.porting/runtime_logs/m18_10min_powersaver_ps_5min.txt`
- 10-minute process sample: `.porting/runtime_logs/m18_10min_powersaver_ps_10min.txt`
- Valid gameplay window capture: `.porting/ui/m18_window_capture.png`

Process samples:

```text
5 min:  ./Heretic2R  14.1% CPU  1.4% MEM  05:00
10 min: ./Heretic2R  12.8% CPU  1.4% MEM  10:00
```

Runtime log:

```text
Window display target: 3
Display refresh 144.0 Hz: profile 1, vid_maxfps 60, cl_maxfps 60
Window drawable: requested 1920x1080, drawable 1920x1018
GL_VERSION: 4.1 Metal - 90.5
Map: ssdocks
```

Frame log:

```text
rows: 35586
avg frame: 16.758 ms
p50 frame: 16.729 ms
p95 frame: 16.787 ms
p99 frame: 16.793 ms
audio underruns: 0 -> 0
audio callbacks: 25627
```

Steady-state after first 10 seconds:

```text
rows: 35268
avg frame: 16.731 ms
p50 frame: 16.729 ms
p95 frame: 16.787 ms
p99 frame: 16.793 ms
max frame: 32.059 ms
frames over 20 ms: 4
frames over 33.34 ms: 0
avg GPU: 1.759 ms
p95 GPU: 3.267 ms
p99 GPU: 4.217 ms
```

## Visual Capture Note

`screencapture -D 3` became unreliable during the long run and captured a different display surface. The actual game process stayed alive, continued logging frames, and was later captured correctly by locating the game window with CoreGraphics window metadata:

```text
owner=Heretic2R
name=Heretic 2 Remastered
bounds={ Width = 1920; Height = 1050; X = -1920; Y = 230; }
```

Valid window capture:

- `.porting/ui/m18_window_capture.png`

## Coverage

- Boot: covered by M15/M16 first-boot captures and M18 launch logs.
- Menu: covered by M15 clean first-boot menu and M16 Finder-style launch.
- Gameplay: covered by M18 `ssdocks` 10-minute run and window capture.
- Spells/particles: covered by M07/M14 FX fixes and prior spell-cooking captures; no new particle regression observed in code path.
- Audio: M18 frame log ended with 0 audio underruns after 25,627 callbacks.
- Profile changes: covered by M14 profile UX/runtime evidence and M18 Power Saver runtime cap.
- Resize: covered by prior display/window tests; current window capture confirms stable 1920-wide window placement.
- Fullscreen/windowed transition: windowed launch remains stable; fullscreen behavior remains a focused QA item for future manual pass if needed.
- 5-minute run: process sample captured at 05:00.
- 10-minute run: process sample captured at 10:00 with full frame log.

## Known Issues / Follow-Ups

- `screencapture -D 3` is not reliable enough as a sole visual evidence method in this multi-monitor setup. Window-ID capture should be preferred for future visual QA.
- The current Power Saver scene is extremely stable, but this was a controlled standing scene rather than a full 10-minute combat route.
- Gatekeeper notarization remains outside this QA milestone and belongs to release/distribution work.
- Full Power 120 remains less stable than Power Saver 60 and should stay in performance/optimization tracking.

## Acceptance Checklist

- [x] Boot covered.
- [x] Menu covered.
- [x] Gameplay covered.
- [x] Spells/particles covered by current renderer/FX fixes and previous evidence.
- [x] Audio covered with 0 underruns in the 10-minute frame log.
- [x] Profile behavior covered.
- [x] Resize/window behavior covered.
- [x] Fullscreen/windowed controls documented; no new blocker found.
- [x] 5-minute evidence captured.
- [x] 10-minute evidence captured.
- [x] Known issues documented.
- [x] No major Power Saver 60 blocker hidden by this pass.
