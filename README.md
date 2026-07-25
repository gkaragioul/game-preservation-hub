# Oni Modern

A Windows 11 compatibility launcher for a **user-owned local installation** of *Oni*. Oni Modern makes a classic retail installation easier to use on current Windows systems without redistributing the game, its assets, or third-party community runtime packages.

> [!IMPORTANT]
> **Oni Modern includes no game files, game executable, game data, Daodan package, OniX package, or OniSplit package.** You need a lawfully obtained copy of *Oni* and must select its existing installation folder yourself.

> [!WARNING]
> This is an independent community project. It is not affiliated with or endorsed by Bungie, Take-Two Interactive, Rockstar Games, or the Oni community projects cited below. See [NOTICE.md](NOTICE.md) for content policy, provenance, and attribution.

## Why use Oni Modern?

Oni Modern focuses on the practical gap between a retail game installation and a comfortable, reversible current-PC setup:

- **Protects the original installation:** validates that the chosen folder has both `Oni.exe` and `GameDataFolder`, then creates a timestamped backup before it manages files.
- **Applies a modern control profile:** writes familiar WASD, mouse, sprint, crouch, jump, action, reload, and weapon bindings.
- **Uses the monitor’s physical native resolution:** resolves Windows DPI scaling so a scaled desktop does not accidentally select a lower logical resolution.
- **Prepares graphics preferences:** writes high-detail, 32-bit colour, subtitle, and native-resolution preferences to the game’s local settings.
- **Makes changes reversible:** managed runtime/profile, controls, and preferences are backed up under `OniModern Backups` in the selected game folder.
- **Keeps distribution rights-safe:** the project contains only original launcher/configuration code and links to community projects instead of mirroring their packages.

The optional runtime-installation code supports a package that **the user has separately obtained and is permitted to use**. No runtime package is included or downloaded by this repository.

## What it changes

The launcher can:

1. Validate a user-selected retail Oni installation.
2. Back up the files it manages.
3. Write a managed `daodan.ini` profile, `key_config.txt` modern controls, and display preferences in `persist.dat`.
4. Launch the user’s local `Oni.exe`.
5. When a separately acquired compatible runtime package is made available locally by the user, deploy only its expected runtime files after validating archive paths.

It does not extract, convert, upload, or package any game asset.

## Getting a Daodan runtime package

Oni Modern does not include or download Daodan. Get `DaodanDLL.zip` yourself from the Oni community's own Mod Depot:

- **http://mods.oni2.net/node/438**

Place the downloaded file at `.runtime/runtime/DaodanDLL.zip` relative to the launcher, matching the layout the zip already ships in (a root `Oni.exe` plus an `fps/` folder) — Oni Modern deploys exactly those files and nothing else.

Do not use the "Anniversary Edition Mod" installer executable found on some mirrors as a Daodan source: it bundles a separate Java-based package manager ("AEInstaller2") rather than deploying Daodan directly, and that tool requires manual, unscriptable GUI interaction.

## Frame rate

Daodan has no built-in frame-rate cap — confirmed from its own `-help` output, which lists every configuration option it supports. Oni's game logic (movement speed, jump height, weapon cooldowns, AI timing) is tied to frame rate: above 60 Hz, gameplay speeds up roughly in proportion to your refresh rate, not just visuals.

If your display runs above 60 Hz, cap Oni's frame rate externally before playing — a GPU driver per-application frame limiter (e.g., AMD Radeon Software's Frame Rate Target Control, NVIDIA's per-app FPS cap) or a tool like RTSS (RivaTuner Statistics Server). Oni Modern does not do this for you, since Daodan exposes no setting to control it.

## Build and test

### Requirements

- .NET SDK 9.0
- Windows to run the WPF launcher; the cross-platform core tests can run anywhere supported by .NET 9.
- A separately and lawfully obtained Oni installation to use the launcher.

```powershell
git clone https://github.com/gkaragioul/OniModern.git
cd OniModern
dotnet test tests/OniModern.Core.Tests/OniModern.Core.Tests.csproj
dotnet build src/OniModern.Launcher/OniModern.Launcher.csproj -c Release
```

## Community acknowledgement

Oni Modern is original code, but it acknowledges the Oni community projects whose documentation informed compatibility research:

- [Anniversary Edition](https://wiki.oni2.net/Anniversary_Edition)
- [Daodan DLL](https://wiki.oni2.net/Daodan_DLL)
- [OniX](https://wiki.oni2.net/OniX)
- [OniSplit](https://wiki.oni2.net/OniSplit)
- [Oni Mod Depot](http://mods.oni2.net/)

These are separate projects with their own authorship and terms. Oni Modern does not claim to be a fork of them, and it does not copy, bundle, redistribute, or grant rights to their code or binaries. Details are in [NOTICE.md](NOTICE.md) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## License and attribution

The original Oni Modern source code is released under the [MIT License](LICENSE). The license does not cover *Oni*, its assets, trademarks, or any third-party/community component referenced in this documentation. See [NOTICE.md](NOTICE.md) for the content policy and rights boundary, and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for NuGet test-dependency licensing and community-project attribution.
