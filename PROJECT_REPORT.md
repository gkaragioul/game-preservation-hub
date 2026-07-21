# Oni Modern — Project Report

## Outcome

Oni Modern is a Windows 11 compatibility launcher for an existing retail Oni installation. It prepares a reversible modern runtime/profile, configures modern controls and graphics preferences, and starts the game. The project deliberately uses the player's local game files rather than bundling game media or assets.

## What has been delivered

- A WPF launcher with installation validation, runtime installation, profile application, and game launch actions.
- Validation that the selected folder contains both `Oni.exe` and `GameDataFolder` before changing it.
- Timestamped backups of every file the launcher manages before profile or runtime changes.
- Deployment of the supplied Daodan/FPS runtime package, including archive-path validation to prevent writing outside the chosen game folder.
- A managed `daodan.ini` profile providing:
  - Borderless-window operation with Alt+Tab support.
  - DaodanGL, sky/UI/subtitle fixes, and improved corpse limit.
  - 90-degree first-person FOV, sprint support, checkpoint saves, and selected gameplay fixes.
  - ODE physics/ragdoll options.
- Modern mouse-and-keyboard bindings: WASD movement, mouse aim/fire, Shift sprint, Ctrl crouch, Space jump, E action, Q swap, R reload, and other common controls.
- Graphics preference writing to `persist.dat`: high detail, subtitles enabled, 32-bit colour, and a resolution selected from the user’s display.

## Native-resolution fullscreen behaviour

The launcher determines the physical resolution of the primary display and writes that resolution to Oni’s preferences. It accounts for Windows DPI scaling, where an OS-reported logical size can differ from the monitor’s actual pixel dimensions.

On the verified machine, Windows exposed a scaled 1920×1080 coordinate space while the panel was physically 2560×1440. The launcher correctly selected 2560×1440. Oni was then verified running at position `(0,0)`, size `2560×1440`, with no caption or window borders: effectively borderless fullscreen.

For other users, the same logic chooses their primary monitor’s physical native resolution rather than a fixed 2K setting.

## Safety and reversibility

- Backups are placed in `OniModern Backups/profile-<UTC timestamp>` inside the selected installation.
- Managed files include the executable/runtime files plus `daodan.ini`, `key_config.txt`, and `persist.dat`.
- The launcher does not alter arbitrary game files and rejects invalid installations and unsafe archive paths.

## Verification

- Automated tests: **9 passing**.
- Launcher build: successful with **0 warnings and 0 errors**.
- Live verification: Oni launched successfully, remained responsive, and filled the physical 2560×1440 display in borderless mode.

## Current scope and limitations

- The launcher operates on the primary display. Moving an already running game to another monitor does not dynamically retarget the resolution; reapply the profile after changing the primary display.
- The runtime package is expected at `.runtime/runtime/DaodanDLL.zip` within this private workspace. A distributable release would need a separate, authorized runtime acquisition/install path.
- The original game’s menus and artwork retain their original-era layout even when the game window itself uses a modern native display resolution.

## Main project locations

- `src/OniModern.Launcher` — Windows launcher UI and startup flow.
- `src/OniModern.Core` — installation checks, backup, deployment, profile, controls, and resolution logic.
- `tests/OniModern.Core.Tests` — automated coverage for the core features.
