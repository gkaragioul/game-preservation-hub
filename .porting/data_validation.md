# Milestone 03 - Data And App Validation

Date: 2026-06-18

## Active Data Paths

The running app uses the bundled build data path:

```text
Heretic II Remastered.app/Contents/Resources/build/base/
```

The workspace build uses:

```text
build/base/
```

## Required Game Data Present Locally

| Path | Purpose |
|---|---|
| `build/base/Htic2-0.pak` | Retail Heretic II data |
| `build/base/Htic2-1.pak` | Retail Heretic II data |
| `build/base/base.pak` | Remastered/base data |
| `build/base/HDTextures/` | Local HD replacement textures |
| `build/base/Art/` | UI/book/menu art |
| `build/base/config/` | Control presets |
| `build/base/*.cfg` | Runtime/default config files |

## Generated Native Modules In Data Folder

| Path | Purpose |
|---|---|
| `build/base/Player.dylib` | Player module |
| `build/base/Client Effects.dylib` | Client visual effects module |
| `build/base/gamex86.dylib` | Game module, legacy filename retained |

## User Config And Saves

User-owned runtime files live under:

```text
~/Library/Application Support/Heretic2R/
```

Observed active files include:

```text
~/Library/Application Support/Heretic2R/base/config.cfg
~/Library/Application Support/Heretic2R/base/console_history.txt
~/Library/Application Support/Heretic2R/base/screenshots/
~/Library/Application Support/Heretic2R/frame_log.csv
~/Library/Application Support/Heretic2R/frame_spikes.log
```

## Validation Result

The app has access to local Heretic II data and local user config/save paths. The data is present for local testing, but it is not treated as public repository content.

## Acceptance Check

Milestone 03 passes because active data folders, runtime config/save folders, and distribution boundaries are known.
