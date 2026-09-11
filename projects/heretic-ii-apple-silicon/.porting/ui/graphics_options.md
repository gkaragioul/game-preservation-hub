# Milestone 14 - Graphics Options UX

## Status

Accepted.

## What Changed

- The primary video menu now exposes two graphics profiles:
  - Full Power
  - Power Saver
- The old Battery Saver label was renamed to Power Saver.
- The custom FPS field was renamed to Custom FPS Cap.
- The on-screen helper text now explains profile benefits in player language:
  - Full Power is for plugged-in Macs and fast displays.
  - Power Saver is for MacBooks on battery or cooler play.
  - Blank Custom FPS uses the selected profile.
  - Custom FPS overrides the selected profile.
- The helper text was moved upward so all three lines fit on a 1920x1080 window.
- README, release notes, and technical notes now match the real profile behavior.

## Behavior Preserved

- Full Power targets 120 FPS by default and clamps to the display refresh.
- Power Saver targets 60 FPS by default and clamps to the display refresh.
- Custom FPS Cap overrides either profile when set to 30 FPS or higher.
- Applying either profile disables adaptive FPS hopping by setting `scr_adaptive_fps` to 0.
- Legacy/tuning-heavy items remain hidden from the primary video menu.

## Evidence

- Build log: `.porting/build_logs/m14_graphics_options_build.log`
- Runtime log: `.porting/runtime_logs/m14_graphics_options_display3.log`
- Menu screenshot: `.porting/ui/m14_graphics_options_menu.png`

Runtime evidence:

```text
Refresh: OpenGL 4.1
Window display target: 3
Display refresh 144.0 Hz: profile 1, vid_maxfps 60, cl_maxfps 60
GL_VERSION: 4.1 Metal - 90.5
```

The screenshot was captured from display 3 at 1920x1080 and shows the Power Saver profile, Custom FPS Cap field, renderer/resolution controls, and all three helper lines.

## Acceptance Checklist

- [x] Exposes only two main graphics profiles.
- [x] Full Power is present.
- [x] Power Saver is present.
- [x] Optional custom FPS override is present.
- [x] Custom FPS override behavior is explained in the menu.
- [x] Benefits are explained in simple language.
- [x] Confusing legacy graphics toggles are hidden from the primary menu.
- [x] Actual renderer/client profile behavior is preserved.
- [x] Build completed successfully.
- [x] Runtime proof captured on SDL display 3.
- [x] Menu screenshot captured on the 1080p display.
