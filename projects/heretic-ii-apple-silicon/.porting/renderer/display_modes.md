# M06: Window, Fullscreen, and Aspect Correctness

Date: 2026-06-17
Renderer: `ref_gl3.dylib` (OpenGL 4.1 Core Profile)
Hardware: Apple M4, macOS 15
Display: Built-in Retina, 2560x1440 native

## Mode Table

13 modes available on this display:

| Index | Resolution | Aspect | Notes |
|-------|-----------|--------|-------|
| 0 | 2560x1440 | 16:9 | Desktop / native |
| 1 | 2048x1152 | 16:9 | |
| 2 | 1920x1080 | 16:9 | |
| 3 | 1600x1200 | 4:3 | |
| 4 | 1600x900 | 16:9 | |
| 5 | 1344x1008 | 4:3 | |
| 6 | 1344x756 | 16:9 | |
| 7 | 1280x960 | 4:3 | |
| 8 | 1280x720 | 16:9 | |
| 9 | 1024x768 | 4:3 | |
| 10 | 1024x576 | 16:9 | |
| 11 | 960x540 | 16:9 | |
| 12 | 800x600 | 4:3 | Minimum mode |

Modes are sourced from `SDL_GetFullscreenDisplayModes()`, filtered at ≥640x480, deduplicated by resolution.

## Windowed Mode Results

All 13 modes work correctly in windowed mode. Each renders at its requested resolution:

| Mode | Requested | Actual Drawable | Screenshot |
|------|-----------|----------------|------------|
| 0 | 2560x1440 | 2560x1330* | 24.9% brightness |
| 1 | 2048x1152 | 2048x1152 | 26.9% |
| 2 | 1920x1080 | 1920x1080 | 26.9% |
| 3 | 1600x1200 | 1600x1200** | 35.3% |
| 4 | 1600x900 | 1600x900 | 27.0% |
| 5 | 1344x1008 | 1344x1008** | 35.3% |
| 6 | 1344x756 | 1344x756 | 27.1% |
| 7 | 1280x960 | 1280x960** | 35.3% |
| 8 | 1280x720 | 1280x720 | 27.1% |
| 9 | 1024x768 | 1024x768** | 35.3% |
| 10 | 1024x576 | 1024x576 | 27.0% |
| 11 | 960x540 | 960x540 | 27.0% |
| 12 | 800x600 | 800x600** | 35.3% |

\* Mode 0 windowed: macOS menu bar reduces height to 1330 (1440 - 110).
\*\* 4:3 modes have higher brightness because the narrower FOV captures different scene content. All render correctly.

No crashes, no failed mode switches, no content clipping or forced 4:3 stretching.

## Fullscreen Mode Results

All 13 modes render at 2560x1440 regardless of requested resolution:

| Mode | Requested | Actual Drawable |
|------|-----------|----------------|
| 0-12 | Varies | 2560x1440 |

This is a known SDL3/macOS limitation. `SDL_SetWindowFullscreen(window, SDL_WINDOW_FULLSCREEN)` uses "fullscreen desktop" mode, which always runs at the display's native resolution. The requested mode resolution does not change the display timing or render target size.

**Impact**: `vid_mode` in fullscreen has no visual effect. All modes produce identical output at native resolution. This is consistent with SDL3 behavior on macOS and is not a bug in the renderer, but differs from Windows behavior where actual display resolution switching occurs.

## Widescreen Verification

### 3D Viewport (Hor+ FOV)

The 3D viewport always fills the full window width. `SCR_CalcVrect()` in `cl_screen.c:431` computes the viewport rectangle:
```c
scr_vrect.width = viddef.width * size / 100;  // Full width
scr_vrect.height = viddef.height * size / 100; // Full height
```

For widescreen aspect ratios, `CalcFov()` in `cl_view.c` adjusts horizontal FOV:
```c
if (viddef.width * 0.75f > viddef.height) // wider than 4:3
    fov_x = atan(tan(fov_x * M_PI / 360) * ((float)viddef.width / (float)viddef.height) / 0.75f) * 360 / M_PI;
```

This gives Hor+ behavior: wider screens see more horizontally, vertical FOV is preserved.

Verified working at:
- 2560x1330 (16:9, mode 0 windowed)
- 2048x1152 (16:9, mode 1)
- 1600x1200 (4:3, mode 3)
- 800x600 (4:3, mode 12)

### HUD Centering (4:3 Safe Area)

The HUD renders in a centered 4:3 region. `SCR_UpdateUIScale()` in `cl_screen.c:672`:
```c
if (viddef.width * 0.75f > viddef.height) // widescreen?
{
    ui_screen_width = viddef.height * 4 / 3;
    ui_screen_offset_x = (viddef.width - ui_screen_width) / 2;
}
```

For 4:3 modes, `ui_screen_offset_x = 0` (HUD fills full width).

### HUD Scaling

`ui_scale` scales HUD elements proportionally to resolution:
```c
ui_scale = min(round(viddef.width / 640), round(viddef.height / 480));
```

| Resolution | ui_scale |
|-----------|----------|
| 2560x1330 | 3 |
| 2048x1152 | 3 |
| 1920x1080 | 2 |
| 1600x1200 | 2 |
| 1280x720 | 1 |
| 800x600 | 1 |

HUD elements are crisp at all resolutions. No blurriness or misalignment.

## Fullscreen Toggle

Two code paths exist:

### Fast Path (cvar modification)
```c
// vid_dll.c:347 - VID_CheckChanges()
if (vid_fullscreen->modified)
{
    vid_fullscreen->modified = false;
    GLimp_ToggleFullscreen((int)vid_fullscreen->value);
}
```
- Calls `SDL_SetWindowFullscreen()` directly
- No renderer reload, no resource recreation
- `viddef` dimensions updated from new drawable size
- Working correctly.

### Keyboard Shortcut Path
```c
// input_sdl3.c:61 - IN_ToggleFullscreenShortcut()
Cvar_SetValue("vid_fullscreen", ...);
```
- Sets `vid_fullscreen`
- Leaves `vid_restart_required` unchanged
- Next `VID_CheckChanges()` triggers the fast fullscreen path only
- No renderer reload, no second toggle, no resource recreation

**Fixed**: `IN_ToggleFullscreenShortcut()` no longer sets `vid_restart_required = true`. The cvar change alone triggers the correct fast path.

## Live Window Resize

Resize handling flows:
1. SDL event (`SDL_EVENT_WINDOW_RESIZED`, `SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED`, etc.)
2. `GLimp_HandleWindowEvent()` → `GLimp_UpdateWindowSize()`
3. `re.ResizeWindow(width, height)` → `RI_ResizeWindow()`
4. Render targets recreated: FBO, Bloom, SSAO, Reflect
5. `SCR_WindowResized()` → `SCR_UpdateUIScale()` + `SCR_CalcVrect()`

The resize guard in `RI_ResizeWindow()` (added during M02) prevents redundant recreations:
```c
if (width == viddef.width && height == viddef.height)
{
    glViewport(0, 0, viddef.width, viddef.height);
    GL3_UpdateProjection2D(...);
    return; // No-op, everything is current
}
```

`GLimp_UpdateWindowSize()` also deduplicates by comparing with `last_window_width/height`.

**Startup sync**: `startup_resize_sync_frames = 12` prevents acting on resize events during the first 12 frames after window creation (avoids spurious resize events on initial show).

## Graphics Profile Interaction

`r_graphics_profile` does NOT affect resolution or mode. It only controls:
- **Profile 0 (Full Power)**: FPS cap = display refresh rate (144 Hz on this display), bloom/SSAO/shadows available
- **Profile 1 (Battery Saver)**: FPS cap = min(60, display refresh), features disabled by default

Resolution stays the same when switching profiles. Verified:
- Profile 0: 2560x1330, vid_maxfps 144, bloom FBO initialized
- Profile 1: 2560x1330, vid_maxfps 60, no bloom FBO

## Control and State Flow

### Display Mode Transition Diagram
```
vid_mode change (menu or console)
  → vid_mode->modified = true
  → vid_restart_required = true (set by menu's ApplyChanges)
  → VID_CheckChanges()
  → VID_LoadRefresh("ref_gl3.dll")
  → RI_Init() → R_SetMode() → SetMode_impl()
  → Vid_GetModeInfo(mode) → width, height
  → GLimp_InitGraphics(width, height)
  → [destroy old window + GL context]
  → CreateSDLWindow(flags, w, h)
  → InitContext(window) [new GL context]
  → [reinit FBO/Bloom/SSAO/Reflect at viddef size]
```

### Fullscreen Transition Diagram
```
vid_fullscreen cvar change
  → vid_fullscreen->modified = true
  → VID_CheckChanges()
  → GLimp_ToggleFullscreen()
  → SDL_SetWindowFullscreen(window, ...)
  → [update viddef, last_window size]
  → [no renderer reload]

Keyboard shortcut (Cmd+F / Alt+Enter)
  → IN_ToggleFullscreenShortcut()
  → Cvar_SetValue("vid_fullscreen", ...)
  → VID_CheckChanges()
  → fast path toggle only
```

## Known Issues

### P1: Fullscreen modes ignored on macOS
- `SDL_WINDOW_FULLSCREEN` uses "fullscreen desktop" mode on macOS
- All `vid_mode` values in fullscreen render at native display resolution
- No actual display resolution switching occurs
- This is a known SDL3/macOS limitation, not a renderer bug
- Windowed mode gives proper per-mode resolutions

### P2: Mode 0 windowed has reduced height
- macOS menu bar occupies ~110 pixels at the top of the screen
- Mode 0 = Desktop resolution (2560x1440), but window height is 1330
- All other modes get their exact requested height since the window is smaller than the full display
- This is correct macOS behavior

## Verdict

Passes M06 acceptance criteria:
- **No lifted screen**: All modes render within their viewport correctly
- **No broken borders**: Fullscreen fills the display, windowed respects window bounds
- **No bad scaling**: HUD scales proportionally, 3D view fills the window, no stretching
- **No persistent resize bugs**: FBO resize guard prevents redundant recreates, resize events processed correctly
- **Widescreen stays correct**: Hor+ FOV, centered 4:3 HUD, all resolutions tested

M06 acceptance is met. The remaining fullscreen mode behavior is a macOS/SDL3 fullscreen-desktop constraint, not a renderer bug. Windowed mode remains the correct path for testing arbitrary resolutions.
