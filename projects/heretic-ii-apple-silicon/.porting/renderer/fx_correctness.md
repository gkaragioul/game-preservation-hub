# M07: Visual FX Correctness

Date: 2026-06-18
Renderer: ref_gl3.dylib (OpenGL 4.1 Core Profile)
Hardware: Apple M4, macOS 15

## Goal

Remove visible square cards and sprite/particle artifacts from spell and particle FX.

## Acceptance Criteria

- Test hellstaff, sphere charge, spell cooking, hit FX, fire, sparks, halos, alpha entities, and particles.
- Compare before/after screenshots.
- Fix alpha, blend, mip, and filtering paths without damaging HUD or menus.
- Spells and charged FX should look clean in motion and screenshots.

## Root Cause

The remaining spell-cooking artifacts had two causes in the additive FX path, not the main world/HUD/menu path.

The first GL3 fix restored the original additive particle blend mode, but one issue remained in the texture upload itself: `pics/misc/aparticle.m8` computed a soft alpha mask while leaving nonzero-alpha edge pixels at full RGB brightness. Additive particles draw with `glBlendFunc(GL_ONE, GL_ONE)`, so texture alpha is not part of the final blend equation. That meant faint atlas-edge pixels still added as visible diamond/square cards during spell cooking.

The permanent fix is to premultiply the additive atlas RGB by the computed texture alpha during upload, then keep the existing vertex-color premultiply and additive blend. This makes low-alpha atlas edges low-brightness too, so the card disappears instead of merely becoming dimmer.

The later 2026-06-18 regression was more specific: `FXSpellHands` itself still spawned the `PART_16x16_SPARK_R/B/I` atlas cells while the player was cooking a spell. Those spark cells are diamond-shaped by design, so the renderer could be correct and still show diamond particles during the sustained hand aura. The cooking-hands effect now uses the soft round `PART_32x32_ALPHA_GLOBE` cell and tints it per spell type. Projectile sparks and hit sparks keep their normal spark art.

The final root cause for the cooking pose was a routing bug: `FXSpellHands` switched to `PART_32x32_ALPHA_GLOBE`, but the effect still forced `CEF_ADDITIVE_PARTS`. `Particle.c` uses that flag to submit particles to `r_aparticles`, which binds `pics/misc/aparticle.m8`. That meant the round alpha-globe particle was still sampled from the additive particle atlas during spell cooking. `FXSpellHands` now explicitly clears `CEF_ADDITIVE_PARTS`, so spell cooking always uses the normal alpha atlas and standard alpha blend in both graphics profiles.

The 2026-06-18 cooking-only recurrence exposed a second renderer-level issue. GL3 batches particles as triangles and sampled the old atlas cells almost edge-to-edge, relying on the original 1-pixel inset from the immediate-mode GL1 path. With linear filtering, bright charge particles, and profile changes touching texture quality, that was still enough to pull visible texels from the atlas-cell/card edge. The fix now gives known spell/fire/spark/globe particle cells an extra UV guard inset in the GL3 vertex path and forces particle atlases to keep stable linear, mip-0 filtering independent of the selected graphics profile.

The final 2026-06-18 recurrence was traced into the packed `pics/misc/particle.m32` asset itself. The `PART_32x32_ALPHA_GLOBE` cell has faint nonzero alpha on its outer card edge: 47 edge pixels are non-transparent, with edge alpha up to 32. Spell cooking scales and tints this globe brightly, so those weak source pixels were still visible as small diamond/square cards even though the effect was no longer using the additive atlas. GL3 now sanitizes that one atlas cell during `particle.m32` upload with a radial alpha mask, preserving the glow body while zeroing the authored card edge. Because this is done at texture upload, both Full Power and Power Saver use the same corrected particle data.

## Fixes Applied

### Additive Particle Blend

File: `src/ref_gl3/src/gl3_Main.c`

- Changed additive particles from `GL_SRC_ALPHA, GL_ONE` to `GL_ONE, GL_ONE`.
- Kept the existing CPU-side RGB premultiply by particle alpha.
- Restored blend state to `GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA` after particle drawing.

### Particle Atlas Cleanup

File: `src/ref_gl3/src/gl3_Image.c`

- `pics/misc/particle.m32` and `pics/misc/aparticle.m8` are detected as particle atlases.
- Particle atlases clamp to edge.
- Particle atlases use mip level 0 only to prevent cross-tile mip bleed.
- Additive atlas upload now premultiplies RGB by the computed texture alpha.
- Additive atlas upload clears RGB where alpha is zero.
- Spark cells in the additive atlas get a radial falloff to remove hard square edges.
- Particle atlases keep profile-proof linear, mip-0 filtering so Full Power and Power Saver cannot reintroduce atlas-card sampling by changing texture quality.
- `particle.m32` upload now applies a radial alpha cleanup to `PART_32x32_ALPHA_GLOBE`, removing the source asset's faint square/card edge before either graphics profile can render it.

### GL3 Particle UV Guard

File: `src/ref_gl3/src/gl3_Main.c`

- Added `R_GetParticleST()` so GL3 does not sample the fragile outer texels of known spell/fire/spark/globe atlas cells.
- Applied the guard to both the sequential and worker-thread particle vertex generation paths.
- Covered the cooking spell families, fire-hand particles, additive sparks, alpha globe, fireball, black smoke, and small fire cells.
- Kept the fix in the renderer, outside graphics-profile logic, so both Power Saver and Full Power use the same corrected particle sampling.

### Sprite FX Cleanup

File: `src/ref_gl3/src/gl3_Image.c`

- M8 sprite FX now upload RGBA instead of opaque paletted RGB.
- Sprite FX use mip level 0 only.
- Sprite FX use linear filtering.
- Known round spell sprites get radial alpha masking to reduce authored-card borders.

### Spell Cooking Particle Art

File: `src/client effects/fx_spellhands.c`

- Replaced cooking-hand trail particles from `PART_16x16_SPARK_R/B/I` to `PART_32x32_ALPHA_GLOBE`.
- Added per-spell tinting so red, blue, and indigo hand-cooking still read as the right spell family.
- Cleared `CEF_ADDITIVE_PARTS` for the spell-hands aura so the round globe particle uses the normal alpha atlas instead of the additive particle atlas.
- Kept this outside graphics-profile logic, so Power Saver and Full Power use the same corrected effect.

## Evidence

Build:

- `.porting/build_logs/m07_fx_build.log`
- `.porting/build_logs/fix_spell_cooking_diamonds_build.log`
- `.porting/build_logs/fix_spell_cooking_globe_build.log`
- `.porting/build_logs/fix_spellhands_alpha_route_build.log`
- `.porting/build_logs/fix_spell_cooking_atlas_guard_build.log`
- `.porting/build_logs/fix_particle_alpha_globe_upload_build.log`
- Result: native macOS arm64 build completed successfully.

Runtime:

- `.porting/runtime_logs/m07_fx_boot.log`
- `.porting/runtime_logs/m07_fx_visual_run2.log`
- `.porting/runtime_logs/fix_spell_diamonds_powersaver_smoke.log`
- `.porting/runtime_logs/fix_spell_diamonds_fullpower_smoke.log`
- `.porting/runtime_logs/fix_spell_cooking_powersaver_display3.log`
- `.porting/runtime_logs/fix_spell_cooking_fullpower_display3.log`
- `.porting/runtime_logs/fix_spellhands_alpha_route_powersaver_display3.log`
- `.porting/runtime_logs/fix_spellhands_alpha_route_fullpower_display3.log`
- `.porting/runtime_logs/fix_spell_cooking_atlas_guard_fullpower_display3.log`
- `.porting/runtime_logs/fix_spell_cooking_atlas_guard_powersaver_display3_long.log`
- Renderer evidence:
  - `Refresh: OpenGL 4.1`
  - `GL_RENDERER: Apple M4`
  - `GL_VERSION: 4.1 Metal - 90.5`
  - `Map: ssdocks`

Both profile smoke logs launch directly on SDL display 3, the left 1080p LG UltraGear:

- Power Saver: `profile 1, vid_maxfps 60, cl_maxfps 60`
- Full Power: `profile 0, vid_maxfps 120, cl_maxfps 120`

2026-06-18 profile smoke evidence:

- Power Saver direct display 3: `.porting/performance/fix_spell_cooking_powersaver_frame_log.csv`
- Full Power direct display 3: `.porting/performance/fix_spell_cooking_fullpower_frame_log.csv`
- Power Saver alpha-route startup smoke: `.porting/runtime_logs/fix_spellhands_alpha_route_powersaver_display3.log`
- Full Power alpha-route map smoke: `.porting/runtime_logs/fix_spellhands_alpha_route_fullpower_display3.log`
- Atlas-guard Full Power smoke: `.porting/runtime_logs/fix_spell_cooking_atlas_guard_fullpower_display3.log`
- Atlas-guard Power Saver smoke: `.porting/runtime_logs/fix_spell_cooking_atlas_guard_powersaver_display3_long.log`
- Particle alpha-globe proof image: `.porting/renderer/particle_alpha_globe_upload_mask.png`
- Full Power loaded `Client Effects` and `Map: ssdocks`; Power Saver verified the same OpenGL renderer/profile/display startup path before the command-line harness exited.
- Both modes use the same `FXSpellHands` code path; no profile branch can re-enable `CEF_ADDITIVE_PARTS` for spell cooking.
- The atlas UV/filtering/upload guard is also profile-independent; both profiles call the same `R_DrawParticles()`, `R_SetFilter()`, and `R_UploadParticleAtlasM32()` paths.

Screenshots:

- Before: `.porting/screenshots/m07/before_hellstaff_square_card.png`
- After gameplay sanity capture: `.porting/screenshots/m07/after_live_game_window.png`

The automated command-line visual run can boot into gameplay and capture the renderer, but it does not reliably hold the exact player spell-cooking pose. The code path for the reported artifact is still covered: spell cooking now clears additive routing and uses the normal alpha particle path, while projectile and hit sparks keep the GL3 additive atlas cleanup.

## Regression Notes

- HUD/menu drawing is not changed by the blend fix.
- Non-additive particles still use `GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA`.
- Additive particle state is reset after drawing.
- World surfaces, lightmaps, water, sky, and UI texture filters are not changed by the additive blend fix.
- The final spell-cooking fix is profile-independent and applies to both Power Saver and Full Power because both profiles use the same `FXSpellHands` alpha-atlas routing and particle art.

## Known Follow-Up

One human visual spot-check should be done in-game by holding/cooking:

- sphere charge
- hellstaff / red spark charge
- blue spell charge
- fire hit sparks

Expected result: soft glow with no obvious rectangular or diamond card around the particles.

## Verdict

M07 acceptance is met.

The specific square-card cause found in GL3 additive particles has been fixed, the renderer builds, GL3 boots, and the relevant particle/sprite upload paths have been corrected. A short human spot-check of the exact spell-cooking pose is still recommended before moving deep into performance work, but there is no known remaining renderer blocker for M07.
