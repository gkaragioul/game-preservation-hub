# Milestone Completion Audit

Date: 2026-06-18

## Scope

This audit checks the Heretic II Apple Silicon milestone list from `HERETIC II APPLE SILICON PORTING MILESTONES` against current repository evidence.

The original milestone list contains a conditional Metal path:

- M19 decides whether Metal should proceed.
- M20 is titled `METAL FOUNDATION, ONLY IF APPROVED`.
- M21 depends on the Metal path being active.

Current project decision:

- M19 decision is **DELAY Metal implementation**.
- The active renderer remains OpenGL `ref_gl3.dylib`.
- Therefore original M20/M21 Metal implementation milestones are **not activated** in the current sequence.
- A later OpenGL-specific M21 spell-combat gate was created and completed to handle the user's FX/performance concerns without violating the OpenGL-only instruction.

## Final Build Evidence

Current source build completed:

- Build log: `.porting/build_logs/milestone_final_audit_build.log`
- Output checked:
  - `build/Heretic2R`
  - `build/ref_gl3.dylib`
  - `build/snd_sdl3.dylib`
- Build log ends with: `Native macOS arm64 build complete`

Warnings remain from inherited source declarations/nonportable include casing, but the build produces the native arm64 runtime.

## Milestone Status

| Milestone | Status | Evidence |
| --- | --- | --- |
| M00 Project Intake | Complete | `.porting/discovery.md`, `.porting/current_goal.md`, `.porting/risk_register.md`, `.porting/legal_asset_boundaries.md` |
| M01 Clean Workspace Map | Complete | `.porting/workspace_map.md`, `.porting/memory.md`, `.porting/known_issues.md` |
| M02 Build Baseline | Complete | `.porting/build_logs/latest_build.log`, `.porting/build_logs/milestone_final_audit_build.log`, `.porting/build_plan.md`, `.porting/dependency_map.md` |
| M03 Data And App Validation | Complete | `.porting/data_validation.md`, `.porting/legal_distribution_rules.md`, `.porting/legal_distribution.md` |
| M04 Boot To macOS Window | Complete | `.porting/boot_notes.md`, `.porting/runtime_logs/boot.log` |
| M05 OpenGL Renderer Baseline | Complete | `.porting/renderer/opengl_baseline.md` |
| M06 Window, Fullscreen, And Aspect Correctness | Complete | `.porting/renderer/display_modes.md` |
| M07 Visual FX Correctness | Complete | `.porting/renderer/fx_correctness.md`, `.porting/performance/m21_spell_combat_route.md` |
| M08 Audio Baseline | Complete | `.porting/audio/audio_baseline.md` |
| M09 Gameplay Baseline | Complete | `.porting/gameplay_baseline.md` |
| M10 Power Saver 60 FPS Mode | Complete | `.porting/performance/power_saver_60fps.md`, `.porting/performance/m10_power_saver_60fps_ultragear2_final_frame_log.csv` |
| M11 Full Power 120 FPS Mode | Complete with documented caveats | `.porting/performance/full_power_120fps.md`, `.porting/performance/m11_full_power_120_display3_analysis.json` |
| M12 Frame Pacing Benchmark | Complete | `.porting/performance/frame_pacing.md`, `.porting/performance/m12_frame_pacing_analysis.json` |
| M13 OpenGL Optimization Pass | Complete | `.porting/performance/opengl_optimization.md`, `.porting/performance/m13_opengl_optimization_same_window_analysis.json` |
| M14 Graphics Options UX | Complete | `.porting/ui/graphics_options.md` |
| M15 Loading Screen And Menu Correctness | Complete | `.porting/ui/loading_menu.md` |
| M16 macOS Experience Pass | Complete | `.porting/macos_experience.md` |
| M17 App Bundle Packaging | Complete | `.porting/packaging.md`, `.porting/packaging/m17_otool_L.txt` |
| M18 QA And Stability Pass | Complete | `.porting/qa/qa_report.md`, `.porting/performance/m18_10min_powersaver_frame_log.csv` |
| M19 Metal Feasibility Audit | Complete | `.porting/metal/metal_feasibility.md`; decision is **DELAY** |
| M20 Metal Foundation, Only If Approved | Not activated | M19 did not approve Metal; `.porting/metal/metal_feasibility.md` explicitly says do not proceed into Metal implementation |
| M21 Metal Game Render Prototype | Not activated | Depends on M20/Metal approval; replaced in current OpenGL-only sequence by the completed OpenGL spell-combat M21 route |
| M21 OpenGL Spell-Combat FX Performance Route | Complete | `.porting/performance/m21_spell_combat_route.md`, `.porting/performance/m21_60_finalroute_frame_log.csv`, `.porting/performance/m21_120_finalroute_frame_log.csv` |
| M22 Public / GitHub / Release Notes | Complete | `README.md`, `RELEASE_NOTES.md`, `TECHNICAL_PORTING_NOTES.md`, `.porting/public_summary.md`, `.porting/legal_distribution.md`, `.porting/m22_public_acceptance.md` |

## Acceptance Notes

### OpenGL Renderer

The active renderer is OpenGL GL3:

- Runtime evidence in current milestone logs reports `Refresh: OpenGL 4.1`.
- `GL_VERSION: 4.1 Metal - 90.5` is Apple's OpenGL compatibility implementation, not this project's native Metal renderer.
- `ref_gl3.dylib` is the active renderer artifact.

### Display Rule

Recent runtime gates used SDL Display 3, the 1080p LG UltraGear target display:

- M10/M11/M12/M18/M20/M21 runtime logs include Display 3 evidence.
- M21 final route logs include `Window display target: 3`.

### Performance

Power Saver 60 FPS is the stable low-resource target:

- M18 10-minute evidence: average `16.731 ms`, p95 `16.787 ms`, p99 `16.793 ms`, 0 audio underruns.
- M21 final spell route: p50 `16.726 ms`, p95 `16.786 ms`, p99 `16.796 ms`.

Full Power 120 FPS is implemented and tested:

- M11/M12/M13 document the fixed-target 120 FPS behavior and remaining caveats.
- M21 final spell route: p50 `8.391 ms`, p95 `8.445 ms`, p99 `9.225 ms`.
- Rare 120 FPS route spikes remain documented for future OpenGL entity/alpha and presentation tuning.

### FX Correctness

The visible square/diamond spell-card artifact is fixed in the active OpenGL path:

- M21 final proof screenshots: `.porting/screenshots/m21/60_nocards_H2R-0002.png`, `.porting/screenshots/m21/120_nocards_H2R-0002.png`.
- M21 final route logs prove both profiles ran on the same route.

### Legal/Public State

Protected retail/remastered game data is excluded from repository distribution:

- `.gitignore` excludes `build/`, `.app`, archives, and packaged deliverables.
- `README.md`, `.porting/legal_distribution.md`, and `.porting/legal_distribution_rules.md` document user-supplied game data requirements.

## Final Verdict

All active and approved milestones in the current OpenGL-first milestone sequence are complete and have evidence.

The original Metal implementation milestones M20/M21 are intentionally not complete because M19's accepted decision is **DELAY**, and M20 is explicitly conditional on approval. Completing them now would contradict the milestone decision and the user's OpenGL-only direction.
