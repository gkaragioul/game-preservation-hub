# M02 — OpenGL Renderer Characterization

## FBO Resize Loop Fix

**File changed:** `src/ref_gl3/src/gl3_Main.c` — `RI_ResizeWindow()` added early-return guard

**Before:** 9 identical "Window resized to 2560x1330" events logged during startup + level load (`opengl_only_smoke.log`), each triggering full FBO shutdown+recreate cycle (HDR, bloom, SSAO, reflection).

**After:** 0 unnecessary FBO recreations during startup + level load (verified 6/17/2026). Guard checks `width == viddef.width && height == viddef.height` before any FBO work.

**Evidence:**
- `build/opengl_only_smoke.log` (pre-fix): 9 resize events at same dimensions
- Current runtime logs: 0 resize events post-init

## Power Saver Profile (r_graphics_profile 1)

| Metric | Value |
|--------|-------|
| Resolution | 2560x1378 drawable |
| Target FPS | 60 (lock) |
| Avg frame time | 16.724 ms |
| Effective FPS | 59.8 |
| GPU time | 2.5-4.3 ms |
| Bloom/SSAO/Shadows/Reflections | Off (profile 1) |
| VSync | On |
| Audio underruns | 0 |
| Frame time jitter | 16.66-16.78ms (99%) |
| Notable drops (>17ms) | 5 frames / 406 (1.2%) |

**Status: STABLE 60 FPS.** Frame times are tightly clustered within 0.12ms of target. No significant frame pacing issues. Massive GPU headroom (13ms idle per frame).

## Full Power Profile (r_graphics_profile 0)

| Metric | Value |
|--------|-------|
| Resolution | 2560x1378 drawable |
| Target FPS | 144 (display refresh) |
| Avg frame time | 7.06 ms |
| Effective FPS | ~142 |
| GPU time | 2.4-2.8 ms |
| Bloom/SSAO/Shadows/Reflections | Off (default cvar values) |
| VSync | Off |
| Audio underruns | 0 |
| Frame time jitter | 6.94-7.06ms (main cluster) |

**Status: GOOD.** Consistently near 144 FPS. ~143 FPS effective. Minor deviation from perfect 144Hz (6.944ms) due to present overhead. Note: bloom/SSAO/shadows/reflections are all currently disabled even on Full Power — the profile cvars default to 0.

## Widescreen Rendering

**Architecture** (no changes needed):
- **3D FOV**: Hor+ scaling via `CalcFov()` in `cl_view.c:141`. Fixes vertical FOV to 82% of horizontal, expands horizontal for wider aspect ratios.
- **HUD**: Centered in 4:3 region via `SCR_UpdateUIScale()` in `cl_screen.c:672`. All coordinates scaled by `ui_scale`.
- **Menus**: Widescreen book background (`WidescreenBook.m32`) with 60px offset for menu items.
- **Cinematics**: Letterboxed to preserve original aspect ratio.
- **Console/Loading**: Fullscreen starfield background with centered 4:3 content.

**Aspect ratio tested:** 2560x1378 (~16:8.6, wider than 16:9). No visual artifacts observed. HUD correctly centered, FOV correctly expanded.

## Launch Args Alignment

- App bundle and direct launch already consistent with profile system
- Profile auto-configures vsync and max FPS
- Direct launch's explicit `r_vsync 1` / `vid_maxfps 60` is redundant with profile 1

**Evidence files:**
- `.porting/performance/powersaver_60fps_log.csv` — 441 frames at 60 FPS
- `.porting/performance/fullpower_144fps_log.csv` — 4678 frames at 144 FPS
- `.porting/screenshots/gl3_ssdocks_powersaver.jpg` — Screenshot at "Silverspring Docks"
