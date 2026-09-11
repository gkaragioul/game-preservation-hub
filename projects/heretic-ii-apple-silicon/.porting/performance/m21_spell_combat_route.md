# M21 Spell-Combat FX Route

Date: 2026-06-18

## Route

Route config: `.porting/routes/m21_spell_combat_route.cfg`

Launch constraints:
- OpenGL renderer only (`vid_ref gl3`)
- SDL display index 3, the 1080p LG UltraGear test display
- Windowed mode
- Map: `ssdocks`
- Exec gated through `cl_exec_on_active` so the route starts after the map is active

## Cooking Card Artifact Root Cause

The visible diamond/card artifacts were not one single path. They came from several old FX layers that render particle or sprite billboard cards:

- `FXSpellHands`: charged/cooking hand trails used spark-style particle cells.
- `FXSpellChange`: spell selection spawned additive spark bits, including blue sphere bits, right before cooking.
- `FXSphereOfAnnihilationGlowballs`: sphere cooking spawned glowball sprite cards and trailing sprite cards.

The permanent fix removes visible billboard-card particles from the cooking/selection layers:

- `src/client effects/fx_spellhands.c`: hand cooking trail carrier remains alive for timing, but no longer emits visible particle cards.
- `src/client effects/fx_spellchange.c`: selection feedback keeps the fading light pulse but no longer emits visible spark/mist particles.
- `src/client effects/fx_sphereofannihlation.c`: sphere cooking glowball carriers are hidden and no longer emit visible mote/trailing sprite-card layers.

Renderer-side safeguards from the previous pass remain in place:

- `src/ref_gl3/src/gl3_Image.c`: sprite/additive particle uploads avoid mip/card bleed and soften selected particle atlas cells.
- `src/ref_gl3/src/gl3_Main.c`: guarded particle atlas sampling remains active.

## Evidence

Build:
- `.porting/build_logs/m21_no_cooking_card_particles_build.log`

Power Saver:
- Runtime log: `.porting/runtime_logs/m21_60_spell_combat_nocookcards_display3.log`
- Frame log: `.porting/performance/m21_60_spell_combat_nocookcards_frame_log.csv`
- Screenshots: `.porting/screenshots/m21/60_nocookcards_H2R-0000.png` through `H2R-0006.png`
- Log confirms: `Refresh: OpenGL 4.1`, profile `1`, `vid_maxfps 60`, `cl_maxfps 60`, display refresh `144.0 Hz`, route exec marker.

Full Power:
- Runtime log: `.porting/runtime_logs/m21_120_spell_combat_nocookcards_display3.log`
- Frame log: `.porting/performance/m21_120_spell_combat_nocookcards_frame_log.csv`
- Screenshots: `.porting/screenshots/m21/120_nocookcards_H2R-0000.png` through `H2R-0006.png`
- Log confirms: `Refresh: OpenGL 4.1`, profile `0`, `vid_maxfps 120`, `cl_maxfps 120`, display refresh `144.0 Hz`, route exec marker.

Frame analysis:
- Raw: `.porting/performance/m21_nocookcards_analysis.json`
- Filtered runtime summary: `.porting/performance/m21_nocookcards_filtered_analysis.json`

Filtered runtime summary:
- 60 Power Saver: average `16.759 ms`, p95 `16.788 ms`, p99 `16.793 ms`, average `59.67 FPS`.
- 120 Full Power: average `8.434 ms`, p95 `8.456 ms`, p99 `8.475 ms`, average `118.57 FPS`.

## Notes

The automated route's distant first screenshot contains some fixed scene/map specks that did not respond to the spell FX changes and should not be treated as the reported close-up cooking-card artifact. The actual card-producing cooking/selection FX sources have been removed from both profiles.

## Follow-Up: Strict OpenGL No-Card FX Guard

User testing still exposed diamond/card specks during spell cooking after the first effect-specific cleanup. The follow-up probe showed that the remaining artifacts were broader than one spell effect: old OpenGL particle atlas cells such as 4x4 sparkle points, 8x8 X/circle/diamond glyphs, 16x16 sparks/stars/fire, 32x32 fire cells, and `PART_32x32_ALPHA_GLOBE` could all read as visible cards when scaled or tinted during spell FX.

Permanent OpenGL guard added:
- `src/ref_gl3/src/gl3_Main.c`: hides the card-prone particle atlas family at render time for all profiles.
- `src/ref_gl3/src/gl3_Shaders.c`: adds a gated particle soft-mask uniform for particle batches.
- `src/ref_gl3/src/gl3_Sprite.c`: skips the decorative `sprites/fx/ripple_add.sp2` card sprite.

Fresh evidence:
- Build: `.porting/build_logs/m21_all_spark_cards_hide_build.log`
- Power Saver proof: `.porting/screenshots/m21/60_nocards_H2R-0002.png`
- Full Power proof: `.porting/screenshots/m21/120_nocards_H2R-0002.png`

Result:
- Power Saver route no longer shows the floating diamond/card particle family.
- Full Power route no longer shows the old diamond/card particles; the visible spell burst is a line/starburst effect, not the previous square/diamond particle-card artifact.

## Final Gate Evidence

The final route was rerun after the strict OpenGL no-card guard. Frame logging uses the engine's `scr_frame_log 1` cvar and writes to the fixed macOS path `~/Library/Application Support/Heretic2R/frame_log.csv`; the generated CSV is copied into `.porting/performance/` after each run.

Power Saver final route:
- Runtime log: `.porting/runtime_logs/m21_60_finalroute_display3_v2.log`
- Frame log: `.porting/performance/m21_60_finalroute_frame_log.csv`
- Rows: `6621`
- Runtime confirms: SDL Display 3, `Window display target: 3`, `Refresh: OpenGL 4.1`, profile `1`, `vid_maxfps 60`, `cl_maxfps 60`, route markers from `M21_ROUTE_BEGIN` through `M21_ROUTE_END`.

Full Power final route:
- Runtime log: `.porting/runtime_logs/m21_120_finalroute_display3_v2.log`
- Frame log: `.porting/performance/m21_120_finalroute_frame_log.csv`
- Rows: `13601`
- Runtime confirms: SDL Display 3, `Window display target: 3`, `Refresh: OpenGL 4.1`, profile `0`, `vid_maxfps 120`, `cl_maxfps 120`, route markers from `M21_ROUTE_BEGIN` through `M21_ROUTE_END`.

Final analysis:
- Raw analysis: `.porting/performance/m21_finalroute_analysis.json`
- Filtered analysis: `.porting/performance/m21_finalroute_filtered_analysis.json`
- Filtering excludes terminal/load outliers above 4x frame budget so the forced test shutdown does not distort gameplay pacing.

Filtered results:
- 60 FPS spell route: average `16.773 ms`, p50 `16.726 ms`, p95 `16.786 ms`, p99 `16.796 ms`, max retained route spike `59.581 ms`, `0.59%` over 105% of the frame budget.
- 120 FPS spell route: average `8.427 ms`, p50 `8.391 ms`, p95 `8.445 ms`, p99 `9.225 ms`, max retained route spike `32.572 ms`, `1.56%` over 105% of the frame budget.

M20 comparison:
- 60 FPS spell route versus M20 static route: average `+0.024 ms`, p99 `+0.003 ms`.
- 120 FPS spell route versus M20 static route: average `+0.018 ms`, p99 `+0.764 ms`.

Spike correlation verdict:
- The final 60 FPS route is effectively locked for normal gameplay; retained spikes are rare and do not correlate strongly with particle count.
- The 120 FPS route remains playable but more sensitive. The strongest observed correlations are with entity and alpha phases, not particle atlas cards and not post-processing.
- GPU frame time stays well below budget for p95/p99 in both routes, so the next OpenGL performance focus should be entity/alpha draw ordering and presentation/frame pacing rather than further particle-card suppression.

M21 acceptance status:
- Repeatable spell-combat route: met.
- Spell cooking, release, hit FX, alpha particles, and gameplay movement: met by `.porting/routes/m21_spell_combat_route.cfg`.
- Visual no-card proof in Power Saver and Full Power: met by `60_nocards_H2R-0002.png` and `120_nocards_H2R-0002.png`.
- Fixed-target 60 and 120 frame logs on the same route: met.
- M20 comparison: met.
- Spike correlation verdict: met.
- OpenGL-only guardrail: met; runtime reports OpenGL 4.1. The Apple `GL_VERSION: 4.1 Metal - 90.5` string is Apple's OpenGL compatibility implementation, not our Metal renderer.
- Display 3 launch rule: met in both final runtime logs.
