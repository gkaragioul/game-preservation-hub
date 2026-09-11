# Oni Modern

A Windows 11 compatibility launcher for a **user-owned local installation** of *Oni*. Oni Modern makes a classic retail installation easier to use on current Windows systems without redistributing the game, its assets, or third-party community runtime packages.

> [!IMPORTANT]
> **Oni Modern includes no game files, game executable, game data, Daodan package, OniX package, or OniSplit package.** You need a lawfully obtained copy of *Oni* and must select its existing installation folder yourself.

> [!WARNING]
> This is an independent community project. It is not affiliated with or endorsed by Bungie, Take-Two Interactive, Rockstar Games, or the Oni community projects cited below. See [NOTICE.md](NOTICE.md) for content policy, provenance, and attribution.

## Download this project

- **Simple download:** [Download the complete Game Preservation Hub as a ZIP](https://github.com/gkaragioul/game-preservation-hub/archive/refs/heads/main.zip). Extract it, then open `projects/oni-modern`.
- **Only this project:** run the commands below to download just the Oni Modern folder.

```powershell
git clone --filter=blob:none --sparse https://github.com/gkaragioul/game-preservation-hub.git
Set-Location game-preservation-hub
git sparse-checkout set projects/oni-modern
```

## Installation guide

Three steps: build the launcher once, get a Daodan package, then set up and play. No pre-built download exists yet, so Step 1 is required even for non-developers — it's copy/paste, not programming.

### Step 1 — Build the launcher (one time)

Requirements: [.NET SDK 9.0](https://dotnet.microsoft.com/download/dotnet/9.0) and Windows.

```powershell
git clone https://github.com/gkaragioul/OniModern.git
cd OniModern
dotnet build src/OniModern.Launcher/OniModern.Launcher.csproj -c Release
```

This produces `OniModern.Launcher.exe` under `src/OniModern.Launcher/bin/Release/net9.0-windows/`.

### Step 2 — Get a Daodan runtime package (recommended)

Daodan is what actually lets 2001-era Oni run well on Windows 11. Oni Modern does not include or download it — get `DaodanDLL.zip` yourself:

- **http://mods.oni2.net/node/438** (Oni Mod Depot, the community's own site)

Place it at `.runtime/runtime/DaodanDLL.zip`, next to the launcher — no unzipping needed, Oni Modern reads the archive directly and only deploys the `Oni.exe` and `fps/` files it expects.

> [!NOTE]
> Skip this step only if your Oni installation already has Daodan applied. Don't use the "Anniversary Edition Mod" installer executable as a source — it bundles an unrelated, unscriptable Java tool instead of Daodan itself.

### Step 3 — Set up and play

You need your own lawfully obtained copy of *Oni* already installed (retail disc, GOG, or similar) — Oni Modern does not provide the game.

1. Run `OniModern.Launcher.exe`.
2. Click **Browse** and select your Oni folder (the one with `Oni.exe` and `GameDataFolder`).
3. Click **Validate** to confirm it's recognized.
4. Click **Install Runtime** if you placed a Daodan package in Step 2, or **Apply Profile** to just modernize controls/resolution on an install that already has Daodan.
5. First time only: the launcher will ask you to reach Oni's main menu and Quit, so the game can write its own settings file — then it continues automatically.
6. Click **Launch** to play.

Everything changed is backed up under `OniModern Backups` inside your Oni folder — nothing is one-way.

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

## Frame rate

Daodan has no built-in frame-rate cap — confirmed from its own `-help` output, which lists every configuration option it supports. Oni's game logic (movement speed, jump height, weapon cooldowns, AI timing) is tied to frame rate: above 60 Hz, gameplay speeds up roughly in proportion to your refresh rate, not just visuals.

If your display runs above 60 Hz, cap Oni's frame rate externally before playing — a GPU driver per-application frame limiter (e.g., AMD Radeon Software's Frame Rate Target Control, NVIDIA's per-app FPS cap) or a tool like RTSS (RivaTuner Statistics Server). Oni Modern does not do this for you, since Daodan exposes no setting to control it.

## Running the tests

For contributors, or anyone who wants to verify the core logic before trusting it with their install. The cross-platform core tests run anywhere .NET 9 does, no Windows or Oni installation required:

```powershell
dotnet test tests/OniModern.Core.Tests/OniModern.Core.Tests.csproj
```

(The launcher build command is in [Step 1 of the installation guide](#step-1--build-the-launcher-one-time) above.)

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
