# M22 Public / GitHub / Release Notes Acceptance

Date: 2026-06-18

## Files Updated

- `README.md`
- `RELEASE_NOTES.md`
- `TECHNICAL_PORTING_NOTES.md`
- `.porting/current_goal.md`
- `.porting/public_summary.md`
- `.porting/legal_distribution.md`

## Acceptance Check

- Apple Silicon macOS port/remastering purpose is explained: met.
- User-supplied Heretic II game data requirement is explained: met.
- Protected assets and generated app/build outputs are excluded from public distribution wording: met.
- Active renderer status is clear: met. The docs state `ref_gl3.dylib` / OpenGL 4.1 is active and Apple's `GL_VERSION: 4.1 Metal - 90.5` string is not our native Metal renderer.
- Two graphics profiles are documented accurately: met. Power Saver targets 60 FPS; Full Power targets 120 FPS where supported.
- Custom FPS override is documented: met.
- Latest M21 spell-combat FX/performance verification is summarized: met.
- Known constraints and next focus are honest: met. 120 FPS rare spikes remain documented for future OpenGL entity/alpha and presentation tuning.
- Private absolute local paths in top-level public docs: checked. No `/Users/` or `/Volumes/` paths found. The only user-location reference is the generic macOS Application Support config path.

## Evidence Commands

```sh
rg -n "/Users/|/Volumes/|100\\.117|LocalModels|Library/Application Support" README.md RELEASE_NOTES.md TECHNICAL_PORTING_NOTES.md .porting/public_summary.md .porting/legal_distribution.md .porting/current_goal.md
rg -n "GL_VERSION|OpenGL 4\\.1|Metal|Power Saver|Full Power|Custom FPS|protected|game data|M21|diamond|square" README.md RELEASE_NOTES.md TECHNICAL_PORTING_NOTES.md .porting/public_summary.md .porting/legal_distribution.md
```

## Result

M22 acceptance is met for the local documentation/passive GitHub readiness scope.
