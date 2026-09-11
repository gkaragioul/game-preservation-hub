# Installer Reliability Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make OniModern's existing three-step promise ("point this at your files, get a correctly modernized game") actually hold on a genuine first-time install, per `docs/superpowers/specs/2026-07-25-installer-reliability-fixes-design.md`.

**Architecture:** No new components. Three targeted fixes inside the existing `OniModern.Core` / `OniModern.Launcher` split: (1) `PersistSettingsWriter` stops synthesizing an untrusted `persist.dat` and instead fails loudly, (2) `MainWindow` gains a small orchestration step that launches Oni once to let it write its own trusted file before patching it, (3) `DaodanProfileWriter`'s default profile stops breaking the stock tutorial, (4) README and in-app copy point at the Daodan source that's actually reliable.

**Tech Stack:** C# / .NET 9, xUnit (`tests/OniModern.Core.Tests`), WPF (`OniModern.Launcher`).

## Global Constraints

- No bundled binaries, no automatic downloads — Daodan stays user-supplied (per spec, "Out of scope").
- No change to Oni's compiled binary or in-game Options UI — no source access (see `NOTICE.md`).
- Every `OniModern.Core` behavior change needs a passing xUnit test in `tests/OniModern.Core.Tests`; `OniModern.Launcher` (WPF) has no existing test project, so its changes are verified manually — this matches the repo's current coverage split, not a gap introduced by this plan.
- Existing tests use reflection (`Type.GetType(...).GetMethod(...).Invoke(...)`) to call `OniModern.Core` methods rather than direct references — follow that exact pattern in any new/modified test.
- Commit after each task with a message describing the fix, matching the repo's existing commit style (imperative, one paragraph).

---

## File Structure

- Modify: `src/OniModern.Core/PersistSettingsWriter.cs` — stop synthesizing a fresh `persist.dat`; throw `FileNotFoundException` with actionable guidance when the file doesn't exist yet.
- Modify: `tests/OniModern.Core.Tests/PersistSettingsWriterTests.cs` — replace the test that asserted the old synthesize-from-scratch behavior with one asserting the throw.
- Modify: `src/OniModern.Core/DaodanProfileWriter.cs` — flip the `disabledoubletapsprint` default from `true` to `false`.
- Modify: `tests/OniModern.Core.Tests/DaodanProfileTests.cs` — add an assertion locking in the new default.
- Modify: `src/OniModern.Launcher/MainWindow.xaml.cs` — add a private `EnsurePersistFileExistsAsync` helper; call it from `ApplyProfile_Click` and `InstallRuntime_Click` before `settingsWriter.ConfigureModernDisplay(...)`; improve the "runtime package not found" status message to name the actual working Daodan source.
- Modify: `README.md` — add a "Getting a Daodan runtime package" section (direct link, expected `.runtime/runtime/DaodanDLL.zip` layout) and a "Frame rate" section (no built-in cap, 60 FPS guidance).

---

## Task 1: Fix the `disabledoubletapsprint` default that breaks Oni's own tutorial

**Files:**
- Modify: `src/OniModern.Core/DaodanProfileWriter.cs:16`
- Test: `tests/OniModern.Core.Tests/DaodanProfileTests.cs`

**Interfaces:**
- Consumes: nothing new.
- Produces: no signature change — `DaodanProfileWriter.WriteModernProfile(string installationPath)` still returns `string` (the written file's path). Only the file's *content* changes.

- [ ] **Step 1: Write the failing test**

Add this assertion inside the existing test method in `tests/OniModern.Core.Tests/DaodanProfileTests.cs` (right after the other `Assert.Contains` lines, before the closing brace of the `try` block):

```csharp
            Assert.Contains("disabledoubletapsprint = false", profile);
```

The full method body should now read:

```csharp
    [Fact]
    public void WriteModernProfile_creates_borderless_controls_and_modern_graphics_settings()
    {
        var root = Path.Combine(Path.GetTempPath(), $"oni-modern-profile-{Guid.NewGuid():N}");
        Directory.CreateDirectory(root);

        try
        {
            var type = Type.GetType("OniModern.Core.DaodanProfileWriter, OniModern.Core");
            Assert.NotNull(type);

            var method = type.GetMethod("WriteModernProfile", new[] { typeof(string) });
            Assert.NotNull(method);
            var profilePath = Assert.IsType<string>(method.Invoke(Activator.CreateInstance(type), new object[] { root }));
            var profile = File.ReadAllText(profilePath);

            Assert.Contains("switch = false", profile);
            Assert.Contains("firstpersonfov = 90", profile);
            Assert.Contains("uiscale = medium", profile);
            Assert.Contains("fixsky = true", profile);
            Assert.Contains("daodangl = true", profile);
            Assert.Contains("maxcorpses = 64", profile);
            Assert.Contains("enableODE = true", profile);
            Assert.Contains("border = false", profile);
            Assert.Contains("daodaninput = true", profile);
            Assert.Contains("disabledoubletapsprint = false", profile);
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `dotnet test tests/OniModern.Core.Tests/OniModern.Core.Tests.csproj --filter WriteModernProfile_creates_borderless_controls_and_modern_graphics_settings`
Expected: FAIL — the profile currently contains `disabledoubletapsprint = true`, so `Assert.Contains("disabledoubletapsprint = false", profile)` fails.

- [ ] **Step 3: Fix the default**

In `src/OniModern.Core/DaodanProfileWriter.cs`, change line 16 from:

```csharp
            disabledoubletapsprint = true
```

to:

```csharp
            disabledoubletapsprint = false
```

`bindablesprint = true` (line 15) stays unchanged — bindable sprint remains available as an *addition*, not a replacement for the classic double-tap dash that Oni's own training level requires.

- [ ] **Step 4: Run the test to verify it passes**

Run: `dotnet test tests/OniModern.Core.Tests/OniModern.Core.Tests.csproj --filter WriteModernProfile_creates_borderless_controls_and_modern_graphics_settings`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/OniModern.Core/DaodanProfileWriter.cs tests/OniModern.Core.Tests/DaodanProfileTests.cs
git commit -m "fix: default disabledoubletapsprint to false

The stock training level requires double-tap-W to dash and will not
let the player proceed if it's disabled. bindablesprint stays on as
an addition, not a replacement."
```

---

## Task 2: Stop `PersistSettingsWriter` from synthesizing an untrusted `persist.dat`

**Files:**
- Modify: `src/OniModern.Core/PersistSettingsWriter.cs`
- Test: `tests/OniModern.Core.Tests/PersistSettingsWriterTests.cs`

**Interfaces:**
- Consumes: nothing new.
- Produces: `PersistSettingsWriter.ConfigureModernDisplay(string installationPath, short width, short height) : string` — same signature as today. New behavior: throws `System.IO.FileNotFoundException` (message explains why, `FileName` property set to the expected `persist.dat` path) when the file does not already exist, instead of creating one from a zeroed array. Task 3 consumes this by checking file existence *before* calling this method, so the throw is a defense-in-depth safety net, not the primary guard.

- [ ] **Step 1: Write the failing test**

In `tests/OniModern.Core.Tests/PersistSettingsWriterTests.cs`, replace the entire second test method (`ConfigureModernDisplay_provisions_a_full_preferences_record_when_the_game_has_not_saved_yet`, lines 38-61) with:

```csharp
    [Fact]
    public void ConfigureModernDisplay_throws_when_persist_dat_does_not_exist_yet()
    {
        var root = Path.Combine(Path.GetTempPath(), $"oni-modern-persist-{Guid.NewGuid():N}");
        Directory.CreateDirectory(root);

        try
        {
            var type = Type.GetType("OniModern.Core.PersistSettingsWriter, OniModern.Core");
            Assert.NotNull(type);
            var method = type.GetMethod("ConfigureModernDisplay", new[] { typeof(string), typeof(short), typeof(short) });
            Assert.NotNull(method);
            var instance = Activator.CreateInstance(type);

            var invocation = Assert.Throws<System.Reflection.TargetInvocationException>(
                () => method.Invoke(instance, new object[] { root, (short)1920, (short)1080 }));

            Assert.IsType<FileNotFoundException>(invocation.InnerException);
            Assert.False(File.Exists(Path.Combine(root, "persist.dat")));
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }
```

Leave the first test (`ConfigureModernDisplay_sets_high_detail_subtitles_and_a_32_bit_resolution`, lines 7-36) untouched — it already writes a `persist.dat` before invoking the method, so it exercises the "file already exists" path this task doesn't change.

The full file should now read:

```csharp
using Xunit;

namespace OniModern.Core.Tests;

public sealed class PersistSettingsWriterTests
{
    [Fact]
    public void ConfigureModernDisplay_sets_high_detail_subtitles_and_a_32_bit_resolution()
    {
        var root = Path.Combine(Path.GetTempPath(), $"oni-modern-persist-{Guid.NewGuid():N}");
        Directory.CreateDirectory(root);
        var persistPath = Path.Combine(root, "persist.dat");
        var bytes = new byte[0x60];
        bytes[0x44] = 0x02;
        File.WriteAllBytes(persistPath, bytes);

        try
        {
            var type = Type.GetType("OniModern.Core.PersistSettingsWriter, OniModern.Core");
            Assert.NotNull(type);
            var method = type.GetMethod("ConfigureModernDisplay", new[] { typeof(string), typeof(short), typeof(short) });
            Assert.NotNull(method);
            method.Invoke(Activator.CreateInstance(type), new object[] { root, (short)1920, (short)1080 });

            var configured = File.ReadAllBytes(persistPath);
            Assert.Equal(4, BitConverter.ToInt32(configured, 0x3C));
            Assert.Equal(3, BitConverter.ToInt32(configured, 0x44));
            Assert.Equal((short)1920, BitConverter.ToInt16(configured, 0x4C));
            Assert.Equal((short)1080, BitConverter.ToInt16(configured, 0x4E));
            Assert.Equal((short)32, BitConverter.ToInt16(configured, 0x50));
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    [Fact]
    public void ConfigureModernDisplay_throws_when_persist_dat_does_not_exist_yet()
    {
        var root = Path.Combine(Path.GetTempPath(), $"oni-modern-persist-{Guid.NewGuid():N}");
        Directory.CreateDirectory(root);

        try
        {
            var type = Type.GetType("OniModern.Core.PersistSettingsWriter, OniModern.Core");
            Assert.NotNull(type);
            var method = type.GetMethod("ConfigureModernDisplay", new[] { typeof(string), typeof(short), typeof(short) });
            Assert.NotNull(method);
            var instance = Activator.CreateInstance(type);

            var invocation = Assert.Throws<System.Reflection.TargetInvocationException>(
                () => method.Invoke(instance, new object[] { root, (short)1920, (short)1080 }));

            Assert.IsType<FileNotFoundException>(invocation.InnerException);
            Assert.False(File.Exists(Path.Combine(root, "persist.dat")));
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `dotnet test tests/OniModern.Core.Tests/OniModern.Core.Tests.csproj --filter ConfigureModernDisplay_throws_when_persist_dat_does_not_exist_yet`
Expected: FAIL — current code creates a zeroed `persist.dat` instead of throwing, so `Assert.Throws<TargetInvocationException>` fails (no exception is thrown) and/or `Assert.False(File.Exists(...))` fails (the file does exist).

- [ ] **Step 3: Implement the fix**

Replace the full contents of `src/OniModern.Core/PersistSettingsWriter.cs` with:

```csharp
namespace OniModern.Core;

public sealed class PersistSettingsWriter
{
    private const int HeaderSize = 0x60;

    public string ConfigureModernDisplay(string installationPath, short width, short height)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(installationPath);
        if (width < 640 || height < 480)
        {
            throw new ArgumentOutOfRangeException(nameof(width), "Oni requires a resolution of at least 640x480.");
        }

        var persistPath = Path.Combine(Path.GetFullPath(installationPath), "persist.dat");
        if (!File.Exists(persistPath))
        {
            throw new FileNotFoundException(
                "persist.dat does not exist yet. Launch Oni.exe once and quit from the main menu so " +
                "the game can write its own preferences file, then apply the profile again. A file " +
                "synthesized from scratch is not trusted by Oni's own startup code and can crash " +
                "Daodan's OpenGL initialization instead of just falling back to a default resolution.",
                persistPath);
        }

        var bytes = File.ReadAllBytes(persistPath);
        if (bytes.Length < HeaderSize)
        {
            throw new InvalidDataException("persist.dat does not contain Oni's preferences header.");
        }

        BitConverter.TryWriteBytes(bytes.AsSpan(0x3C, sizeof(int)), 4);
        var flags = BitConverter.ToInt32(bytes, 0x44) | 0x01;
        BitConverter.TryWriteBytes(bytes.AsSpan(0x44, sizeof(int)), flags);
        BitConverter.TryWriteBytes(bytes.AsSpan(0x4C, sizeof(short)), width);
        BitConverter.TryWriteBytes(bytes.AsSpan(0x4E, sizeof(short)), height);
        BitConverter.TryWriteBytes(bytes.AsSpan(0x50, sizeof(short)), (short)32);
        File.WriteAllBytes(persistPath, bytes);
        return persistPath;
    }
}
```

Note what's removed versus the current version: the `SavePointCount` / `SavePointSize` constants and the `File.Exists(persistPath) ? File.ReadAllBytes(...) : new byte[...]` fallback are gone entirely — there is no longer any code path that fabricates a `persist.dat`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `dotnet test tests/OniModern.Core.Tests/OniModern.Core.Tests.csproj --filter PersistSettingsWriterTests`
Expected: PASS (both tests in the class)

- [ ] **Step 5: Run the full Core test suite to check for regressions**

Run: `dotnet test tests/OniModern.Core.Tests/OniModern.Core.Tests.csproj`
Expected: PASS (all tests, including the ones untouched by this task)

- [ ] **Step 6: Commit**

```bash
git add src/OniModern.Core/PersistSettingsWriter.cs tests/OniModern.Core.Tests/PersistSettingsWriterTests.cs
git commit -m "fix: never synthesize persist.dat from scratch

A persist.dat we fabricate ourselves (real bytes at 5 known offsets,
zero everywhere else) is not trusted by Oni's own startup code and
can crash Daodan's OpenGL init on first launch instead of just
picking a fallback resolution. ConfigureModernDisplay now throws
FileNotFoundException with guidance instead of creating one; the
launcher (next commit) ensures a real file exists first."
```

---

## Task 3: Launcher ensures a genuine `persist.dat` exists before configuring display

**Files:**
- Modify: `src/OniModern.Launcher/MainWindow.xaml.cs`

**Interfaces:**
- Consumes: `PersistSettingsWriter.ConfigureModernDisplay` (Task 2) — now throws `FileNotFoundException` if called before this task's guard runs; `InstallationDetector`'s `InstallationStatus` record (`RootPath`, `ExecutablePath` properties, already in the codebase).
- Produces: new private method `EnsurePersistFileExistsAsync(InstallationStatus installation) : Task<bool>` — returns `true` once `persist.dat` exists at `installation.RootPath`, launching `Oni.exe` and waiting for it to exit if it doesn't yet; returns `false` (and leaves `StatusTextBlock.Text` with an explanation) if it still doesn't exist afterward, so the caller should stop rather than proceed to `ConfigureModernDisplay`.

**No automated test for this task** — `OniModern.Launcher` has no existing test project (WPF, requires a live `Oni.exe` and a real display), consistent with the rest of the file having zero coverage today. Verify manually per Step 4 below.

- [ ] **Step 1: Add the required `using` and the new helper method**

In `src/OniModern.Launcher/MainWindow.xaml.cs`, add `System.Threading.Tasks` to the `using` block at the top (after `using System.Runtime.InteropServices;`):

```csharp
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using System.Windows;
using Forms = System.Windows.Forms;
using OniModern.Core;
```

Then add this new private method anywhere inside the `MainWindow` class (e.g., directly above `private InstallationStatus? ValidateInstallation()`):

```csharp
    private async Task<bool> EnsurePersistFileExistsAsync(InstallationStatus installation)
    {
        var persistPath = Path.Combine(installation.RootPath, "persist.dat");
        if (File.Exists(persistPath))
        {
            return true;
        }

        StatusTextBlock.Text = "Launching Oni once so it can write its own settings file - " +
            "reach the main menu, then Quit, and this step will continue automatically.";

        Process? process;
        try
        {
            process = Process.Start(new ProcessStartInfo(installation.ExecutablePath)
            {
                WorkingDirectory = installation.RootPath,
                UseShellExecute = true
            });
        }
        catch (System.ComponentModel.Win32Exception ex)
        {
            StatusTextBlock.Text = $"Could not launch Oni.exe to initialize persist.dat: {ex.Message}";
            return false;
        }

        if (process is null)
        {
            StatusTextBlock.Text = "Could not launch Oni.exe to initialize persist.dat.";
            return false;
        }

        await Task.Run(() => process.WaitForExit());

        if (!File.Exists(persistPath))
        {
            StatusTextBlock.Text = "Oni exited without creating persist.dat. Launch it again, reach " +
                "the main menu, and Quit before applying the profile.";
            return false;
        }

        return true;
    }
```

- [ ] **Step 2: Wire the guard into `ApplyProfile_Click`**

Change the method signature and body. Before:

```csharp
    private void ApplyProfile_Click(object sender, RoutedEventArgs e)
    {
        var installation = ValidateInstallation();
        if (installation is null)
        {
            return;
        }

        var backupRoot = Path.Combine(installation.RootPath, "OniModern Backups");
        var backup = backupService.CreateBackup(installation.RootPath, backupRoot);
        var profile = profileWriter.WriteModernProfile(installation.RootPath);
        var display = GetNativeDisplayResolution();
        var preferences = settingsWriter.ConfigureModernDisplay(installation.RootPath, display.Width, display.Height);
        var controls = controlsWriter.WriteModernControls(installation.RootPath);
        StatusTextBlock.Text = $"Modern profile, controls, and native {display.Width}x{display.Height} graphics applied. Backup: {backup}; profile: {profile}; controls: {controls}; preferences: {preferences}";
    }
```

After:

```csharp
    private async void ApplyProfile_Click(object sender, RoutedEventArgs e)
    {
        var installation = ValidateInstallation();
        if (installation is null)
        {
            return;
        }

        var backupRoot = Path.Combine(installation.RootPath, "OniModern Backups");
        var backup = backupService.CreateBackup(installation.RootPath, backupRoot);
        var profile = profileWriter.WriteModernProfile(installation.RootPath);

        if (!await EnsurePersistFileExistsAsync(installation))
        {
            return;
        }

        var display = GetNativeDisplayResolution();
        var preferences = settingsWriter.ConfigureModernDisplay(installation.RootPath, display.Width, display.Height);
        var controls = controlsWriter.WriteModernControls(installation.RootPath);
        StatusTextBlock.Text = $"Modern profile, controls, and native {display.Width}x{display.Height} graphics applied. Backup: {backup}; profile: {profile}; controls: {controls}; preferences: {preferences}";
    }
```

- [ ] **Step 3: Wire the guard into `InstallRuntime_Click` and improve the missing-package message**

Before:

```csharp
    private void InstallRuntime_Click(object sender, RoutedEventArgs e)
    {
        var installation = ValidateInstallation();
        if (installation is null)
        {
            return;
        }

        var package = FindRuntimePackage();
        if (package is null)
        {
            StatusTextBlock.Text = "The bundled modern runtime package was not found.";
            return;
        }

        var backupRoot = Path.Combine(installation.RootPath, "OniModern Backups");
        var backup = backupService.CreateBackup(installation.RootPath, backupRoot);
        var deployed = runtimeDeployer.DeployFpsRuntime(package, installation.RootPath);
        var profile = profileWriter.WriteModernProfile(installation.RootPath);
        var display = GetNativeDisplayResolution();
        var preferences = settingsWriter.ConfigureModernDisplay(installation.RootPath, display.Width, display.Height);
        var controls = controlsWriter.WriteModernControls(installation.RootPath);
        StatusTextBlock.Text = $"Modern runtime installed ({deployed.Count} files) with modern controls and native {display.Width}x{display.Height} graphics. Backup: {backup}; profile: {profile}; controls: {controls}; preferences: {preferences}";
    }
```

After:

```csharp
    private async void InstallRuntime_Click(object sender, RoutedEventArgs e)
    {
        var installation = ValidateInstallation();
        if (installation is null)
        {
            return;
        }

        var package = FindRuntimePackage();
        if (package is null)
        {
            StatusTextBlock.Text = "The runtime package was not found at .runtime/runtime/DaodanDLL.zip. " +
                "Download it from http://mods.oni2.net/node/438 (Oni Mod Depot) and place it there.";
            return;
        }

        var backupRoot = Path.Combine(installation.RootPath, "OniModern Backups");
        var backup = backupService.CreateBackup(installation.RootPath, backupRoot);
        var deployed = runtimeDeployer.DeployFpsRuntime(package, installation.RootPath);
        var profile = profileWriter.WriteModernProfile(installation.RootPath);

        if (!await EnsurePersistFileExistsAsync(installation))
        {
            return;
        }

        var display = GetNativeDisplayResolution();
        var preferences = settingsWriter.ConfigureModernDisplay(installation.RootPath, display.Width, display.Height);
        var controls = controlsWriter.WriteModernControls(installation.RootPath);
        StatusTextBlock.Text = $"Modern runtime installed ({deployed.Count} files) with modern controls and native {display.Width}x{display.Height} graphics. Backup: {backup}; profile: {profile}; controls: {controls}; preferences: {preferences}";
    }
```

- [ ] **Step 4: Build and manually verify**

Run: `dotnet build src/OniModern.Launcher/OniModern.Launcher.csproj -c Release`
Expected: builds with 0 warnings, 0 errors (matching the project's existing standard, per `PROJECT_REPORT.md`).

Manual verification (requires a real Oni installation, run on Windows):
1. Point the launcher at an Oni installation folder with **no existing `persist.dat`**.
2. Click "Apply Profile". Confirm the status text shows the "Launching Oni once..." message and `Oni.exe` actually opens.
3. Reach the main menu in the launched game and Quit.
4. Confirm the launcher's status text updates to the normal "Modern profile... applied" message (not an error) and `persist.dat` now exists in the installation folder.
5. Launch `Oni.exe` directly (not through the launcher) and confirm it reaches the main menu at native resolution without crashing and without needing to touch Options — this is the actual fix working end to end.

- [ ] **Step 5: Commit**

```bash
git add src/OniModern.Launcher/MainWindow.xaml.cs
git commit -m "fix: launch Oni once to initialize persist.dat before patching it

ApplyProfile_Click and InstallRuntime_Click now call
EnsurePersistFileExistsAsync before ConfigureModernDisplay, which
launches Oni.exe and waits for a clean exit when persist.dat doesn't
exist yet, so the display patch always lands on a file the game
itself considers genuine. Also points the missing-runtime-package
message at the actual working Daodan source instead of leaving users
to guess."
```

---

## Task 4: Document the working Daodan source and frame-rate guidance

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing consumed by other tasks — pure documentation.

- [ ] **Step 1: Add a "Getting a Daodan runtime package" section**

In `README.md`, insert this new section immediately after the "## What it changes" section (after line 34, `It does not extract, convert, upload, or package any game asset.`, before `## Build and test`):

```markdown
## Getting a Daodan runtime package

Oni Modern does not include or download Daodan. Get `DaodanDLL.zip` yourself from the Oni community's own Mod Depot:

- **http://mods.oni2.net/node/438**

Place the downloaded file at `.runtime/runtime/DaodanDLL.zip` relative to the launcher, matching the layout the zip already ships in (a root `Oni.exe` plus an `fps/` folder) — Oni Modern deploys exactly those files and nothing else.

Do not use the "Anniversary Edition Mod" installer executable found on some mirrors as a Daodan source: it bundles a separate Java-based package manager ("AEInstaller2") rather than deploying Daodan directly, and that tool requires manual, unscriptable GUI interaction.
```

- [ ] **Step 2: Add a "Frame rate" section**

Insert this new section immediately after the "Getting a Daodan runtime package" section added in Step 1 (still before `## Build and test`):

```markdown
## Frame rate

Daodan has no built-in frame-rate cap — confirmed from its own `-help` output, which lists every configuration option it supports. Oni's game logic (movement speed, jump height, weapon cooldowns, AI timing) is tied to frame rate: above 60 Hz, gameplay speeds up roughly in proportion to your refresh rate, not just visuals.

If your display runs above 60 Hz, cap Oni's frame rate externally before playing — a GPU driver per-application frame limiter (e.g., AMD Radeon Software's Frame Rate Target Control, NVIDIA's per-app FPS cap) or a tool like RTSS (RivaTuner Statistics Server). Oni Modern does not do this for you, since Daodan exposes no setting to control it.
```

- [ ] **Step 3: Review the rendered file**

Run: `cat README.md` (or open in an editor) and confirm:
- The section order is now: Why use Oni Modern? → What it changes → Getting a Daodan runtime package → Frame rate → Build and test → Community acknowledgement → License and attribution.
- No existing section was accidentally duplicated or removed.
- Both new sections' links are plain text or correctly formed Markdown links.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document the working Daodan source and frame-rate guidance

The AE installer executable doesn't actually deploy Daodan (it drops
an unscriptable Java package manager instead) - point users at
mods.oni2.net/node/438 directly, matching what
DaodanRuntimeDeployer already expects. Also document that Daodan has
no frame-rate cap and recommend an external 60 FPS limit above 60 Hz,
since nothing else states this."
```

---

## Final verification

- [ ] Run the full test suite once more after all four tasks: `dotnet test tests/OniModern.Core.Tests/OniModern.Core.Tests.csproj` — expect all tests passing, including the two new/modified ones from Tasks 1 and 2.
- [ ] Run the full build once more: `dotnet build src/OniModern.Launcher/OniModern.Launcher.csproj -c Release` — expect 0 warnings, 0 errors.
- [ ] Re-read `docs/superpowers/specs/2026-07-25-installer-reliability-fixes-design.md` top to bottom and confirm each of its four items (Problem 1, Problem 2, Problem 3, frame-rate documentation) has a corresponding completed task above.
