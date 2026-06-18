# Milestone 15 - Loading Screen And Menu Correctness

## Status

Accepted.

## Root Cause / Fix

The random text/glyph issue was caused by the console notify renderer being able to draw recent console lines during normal play when `con_drawnotify` had been left enabled from testing. That debug path is now gated behind `developer`, so normal play cannot show those stray console lines even if `con_drawnotify` is set.

Changed:

- `src/client/console.c`

## Verification

All runtime captures were launched directly on SDL display 3, the 1920x1080 LG UltraGear test display.

Evidence files:

- Build log: `.porting/build_logs/m15_loading_menu_build.log`
- Runtime log: `.porting/runtime_logs/m15_clean_display3.log`
- First-boot menu screenshot: `.porting/ui/m15_clean_first_boot.png`
- Loading screenshot: `.porting/ui/m15_clean_loading.png`
- Gameplay after load screenshot: `.porting/ui/m15_final_game.png`

Runtime proof:

```text
Window display target: 3
Display refresh 144.0 Hz: profile 1, vid_maxfps 60, cl_maxfps 60
Window drawable: requested 1920x1080, drawable 1920x1018
GL_VERSION: 4.1 Metal - 90.5
```

The final clean launch deliberately used `con_drawnotify 1` with `developer 0`; no random console notify text appeared.

## Observations

- First-boot menu is centered and no longer appears lifted upward.
- Menu borders and page art are stable on first launch.
- Loading screen appears immediately with starfield, centered Loading label, and progress bar.
- Direct `map ssdocks` loading completed without blank half-loading.
- Post-load gameplay frame was stable and not vertically shifted.
- No random top-left console glyphs appeared in normal/developer-off mode.
- The direct-load path did not keep the world map art visible long enough for an automated screenshot before gameplay; the loading fallback remains visually correct and not blank.

## Acceptance Checklist

- [x] Loading screen appears immediately and correctly.
- [x] Map/menu art is not distorted in verified menu captures.
- [x] Menu alignment, borders, and text are stable.
- [x] Menu-to-game transition was verified by direct map launch.
- [x] First-boot lifted-menu regression was not present.
- [x] Stray console glyph/text leak is fixed for normal play.
- [x] Build completed successfully.
- [x] Runtime evidence captured on SDL display 3.
- [x] First-boot and loading screenshots captured on the 1080p display.
