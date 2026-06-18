# Milestone 00 — Risk Register

## Active Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R01 | macOS OpenGL 4.1 is frozen — Apple will never ship newer OpenGL | Certain | Renderer cannot use GL 4.5+ features | ref_metal path exists; ref_gl3 must stay within 4.1 limits |
| R02 | OpenGL 4.1 on Apple Silicon is a Metal translation layer (not native GL) | Certain | GPU queries, fence objects, and sync may behave differently than on real GL4.1 hardware | Validate all GL calls work correctly; test with `gpu_frame_ms` and frame timing |
| R03 | FBO resize loop causes stutter/jank on every resolution change | High | Poor user experience, invisible cost on battery | Fix resize guard in gl3_SDL.c/gl3_Main.c to avoid redundant FBO recreation |
| R04 | No hardware video decode for cinematic MP4/SMK files | High | Cinematics may be broken or CPU-heavy | Stub path already exists; verify SMK decoder works correctly on arm64 |
| R05 | Frame pacing spikes degrade 60 FPS lock stability | Medium | Power Saver mode fails its core promise | Profile main loop; identify whether spikes are GPU or CPU-bound |
| R06 | Fullscreen transitions glitch (resolution switch, black frames) | Medium | Bad first impression, window manager fights | Test windowed→fullscreen→windowed cycle; log all resize events |
| R07 | Game data (PAK files) not tracked in git — no reproducibility | Medium | Cannot roll back asset changes | Document PAK versions; keep base.pak hash in notes |
| R08 | Ad-hoc code signing — Mac Gatekeeper blocks on other machines | Medium | App cannot be distributed easily | Will need Developer ID + notarization for distribution |
| R09 | Metal renderer unused but maintained — divergence risk | Medium | gl3 fixes not ported to metal; metal fixes not tested | Keep ref_metal building alongside once it's ready |
| R10 | 120 FPS target may be GPU-limited on M1/M2 base models | Medium | Full Power mode cannot deliver on older Silicon | Test on M1, M2, M3, M4; adjust default profile per GPU |
| R11 | Widescreen rendering may stretch or misproject HUD/game elements | Medium | Visual correctness failure | Test HUD alignment, weapon models, FOV at 16:9, 16:10, 21:9 |
| R12 | Audio underrun/crackle on underpowered or loaded systems | Low | Audio quality degrades | snd_sdl3 has hardening; stress-test during heavy combat scenes |
| R13 | Game save compatibility across versions | Low | Users lose progress | Keep save structs stable; test load of existing saves |
| R14 | Original Windows .dll files (Player.dll, Client Effects.dll, gamex64.dll) present in build/base/ alongside .dylib | Low | Engine might accidentally load wrong module | Confirm engine dynamic loading uses .dylib on macOS |

## Retired Risks

None yet.

## Risk Mitigation Tracking

- R03: Will investigate gl3_SDL.c `GL3_HandleResize()` and `R_SetMode()` guards
- R04: Test `cl_smk.c` path with a known SMK file; confirm palettized decode works
- R05: Run `+set scr_perf_overlay 1 +map ssdocks` and capture 30s+ of frame pacing
- R11: Test HUD at 1710x1107 (built-in), 2560x1440 (external), 1920x1080
