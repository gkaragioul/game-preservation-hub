# Current Goal - Active Milestone Sequence Complete

Date: 2026-06-18

## Status

All active and approved milestones in the OpenGL-first Apple Silicon milestone sequence are complete.

Authoritative completion audit:

- `.porting/milestone_completion_audit.md`

## Renderer Direction

The active renderer remains OpenGL GL3:

- `ref_gl3.dylib`
- macOS OpenGL 4.1

Apple Silicon may report `GL_VERSION: 4.1 Metal - 90.5`; that is Apple's OpenGL compatibility implementation, not this project's native Metal renderer.

## Metal Status

Metal implementation is delayed by the accepted M19 feasibility decision:

- `.porting/metal/metal_feasibility.md`

Original M20/M21 Metal implementation milestones are not activated because M20 is explicitly conditional on approval, and M19 decided **DELAY**.

## Final Completed Active Gates

- M21 OpenGL spell-combat FX/performance route: `.porting/performance/m21_spell_combat_route.md`
- M22 public/GitHub/release notes readiness: `.porting/m22_public_acceptance.md`

## Next Recommended Work

Future work should be opened as a new explicit goal, likely one of:

- OpenGL entity/alpha draw ordering and 120 FPS presentation pacing.
- Broader QA/release candidate testing.
- Optional Metal prototype only if explicitly approved later.
