# Milestone 01 — Known Issues Catalog

## 1. FBO Resize Loop (FIXED)

**Fixed in**: `src/ref_gl3/src/gl3_Main.c` — `RI_ResizeWindow()` now guards against same-size events.

**Before**: 9 identical "Window resized to 2560x1330" events during startup + level load, each triggering full FBO shutdown+recreate cycle.

**After**: 0 unnecessary FBO recreations. The guard checks `if (width == viddef.width && height == viddef.height) return;` before any FBO work.

**Evidence**: Compare `build/opengl_only_smoke.log` (9 events, pre-fix) with current runtime logs (0 events post-init).

## 2. Frame Pacing Spikes (Medium Impact)

**Observed**: `~/Library/Application Support/Heretic2R/base/frame_spikes.log` is 107 KB, `frame_log.csv` is 192 KB.

**Evidence**: Spike detection system is actively logging events. Config contains `scr_frame_spike_log 0` and `scr_frame_spike_threshold 0.85` suggesting spikes above 85% of frame budget were being recorded.

**Impact on Milestone**: Power Saver (stable 60 FPS) cannot be confirmed until spikes are characterized.

## 3. No Metal Build (Medium Impact)

**Observed**: `build_macos_arm64.sh` line 8: `rm -f "$ROOT/build/ref_metal.dylib"` — explicit deletion. The Metal renderer (`src/ref_metal/src/metal_Main.m`, 6916 lines) is a complete implementation but is never built or tested.

**Impact on Milestone**: Metal path cannot be tested. GL3 and Metal fixes will diverge.

## 4. Stubbed Cinematic Playback (Low-Medium Impact)

**Observed**: `heretic2r_app.log` line 59-60:

```
Opening HD cinematic from PAK: 'HDVideos/bumper.mp4'...
No HD video found for 'bumper.smk', skipping cinematic.
```

**Root cause**: `src/client/cl_mp4.c` handles MP4 but likely requires platform decoder. `src/client/cl_smk.c` handles SMK via `libsmacker` but the bundled PAKs may not contain the expected SMK paths.

**Note**: 1.0 release notes mention "stubbed Windows-only MP4/update-check paths."

## 5. Widescreen Aspect Ratio Untested (Medium Impact)

**Observed**: Config has `vid_mode 0` which uses desktop mode. Tested monitor shows 2560x1440 → drawable 2560x1330 (16:9-ish). The built-in laptop display was 1710x1107 (~16:10). Different aspect ratios (21:9, 16:10 vs 16:9) may misproject HUD elements, weapon models, or FOV.

**Status**: Not yet tested since the 1.0 baseline.

## 6. Windows DLL Artifacts in Build/Base (Low Impact)

**Observed**: `build/base/` contains `Player.dll`, `Client Effects.dll`, `gamex64.dll`. These are Windows binaries from the original source and are not loaded on macOS. The engine dynamically loads `Player.dylib`, `Client Effects.dylib`, `gamex86.dylib` instead.

**Risk**: Confusion for new contributors. No functional impact.

## 7. App Bundle vs Direct Build Discrepancy (Low Impact)

**Observed**: The app bundle launch wrapper (`Heretic II Remastered.app/Contents/MacOS/Heretic II Remastered`) passes:
```
+set vid_ref gl3 +set vid_mode 0 +set vid_fullscreen 0 +set scr_frame_spike_log 0
```

The direct build launch command (`Launch Heretic II Remastered.command`) passes:
```
+set vid_ref gl3 +set vid_mode 0 +set r_vsync 1 +set vid_maxfps 60
```

The direct launch has `r_vsync 1` and `vid_maxfps 60`, the app bundle does not. These will behave differently.

## 8. Config Has Battery Saver Profile Active (Info)

**Observed**: `config.cfg` has `r_graphics_profile 1` which disables bloom, SSAO, shadows, and reflections. This is the Battery Saver profile, not Full Power.

**Impact on testing**: Visual feature testing (bloom, SSAO, reflections) requires switching to profile 0 or manually enabling the cvars.

## 9. MP4/H.264 Video Decoder Gap (Low Impact)

**Observed**: The engine tries to load `HDVideos/bumper.mp4` from PAK. macOS has no built-in H.264 decoder accessible from C. The SMK (Smacker) path via `libsmacker` should work for original cinematics, but HD MP4 videos are a gap.

## 10. Build Script Deletes Metal Output (Intentional)

**Observed**: `build_macos_arm64.sh` lines 8 and 118:
```sh
rm -f "$ROOT/build/ref_metal.dylib"
rm -f "$app_build/ref_metal.dylib"
```

This is intentional per the strategy ("Metal is a later native renderer path, only after OpenGL behavior is correct").

## Previously Fixed Issues (Historical)

From `TECHNICAL_PORTING_NOTES.md`:
- R_RenderLightmappedPoly crash (uninitialized `glpoly_t.chain`) — fixed
- Lightmap fast path bypass causing oversaturated world — fixed
- User config path buffer overflow — fixed
- Menu/config noise from stale labels — fixed
- Busy-spin frame loop replaced with nanosleep — fixed
- Homebrew absolute install names rewritten to bundle-relative — fixed
