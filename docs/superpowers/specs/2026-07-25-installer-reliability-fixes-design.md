# OniModern installer reliability fixes — design

## Context

OniModern is a C# WPF launcher/installer that orchestrates a user-owned Oni
installation: it validates the folder, backs it up, writes a modern
`daodan.ini` profile, patches `persist.dat` for native-resolution borderless
display, writes `key_config.txt`, deploys a user-supplied Daodan runtime
package, and launches the game. It deliberately bundles no game files, no
Daodan binaries, and no mod content — see `NOTICE.md`.

A live end-to-end install (E:\Retro\Oni, 2026-07-25) surfaced three concrete
bugs against real files: a resolution bug that only reproduces on a genuinely
fresh install, a broken/unreliable Daodan acquisition path, and a default
config value that breaks the game's own tutorial. This spec fixes those
three, using Daodan's own public source (`bugs.oni2.net/browser/Daodan`) to
ground the resolution fix in an actual mechanism rather than a guess.

No new features, no bundled binaries, no automatic downloads. Scope is
strictly: make the existing promise ("point this at your files, get a
correctly modernized game") actually hold on a first-time install.

## Problem 1: a synthesized persist.dat can crash Daodan's OpenGL init

### Symptom (reproduced today, isolated with a controlled A/B test)

Important correction from an earlier draft of this spec: **640×480 during
the intro cutscene is normal, happens on every launch regardless of
persist.dat state, and is not a bug** — the window correctly resizes to the
patched resolution the moment the actual main menu loads. That's not what
Problem 1 is about.

The real, isolated bug: a `persist.dat` created purely by
`PersistSettingsWriter.ConfigureModernDisplay` from a zeroed byte array
(header fields set only at offsets 0x3C/0x44/0x4C/0x4E/0x50, everything else
zero) — with no prior game-written file ever existing — causes Daodan to
throw a fatal `AUrMessageBox` ("Daodan: Failed to initialize OpenGL
contexts; Oni will now exit.") and the process exits. Verified with a
controlled test: same install, same game data, only variable was
persist.dat provenance — a genuinely game-written file (reached via one
manual Options → Close, or even just Quit from the main menu) loads
correctly every time afterward; a from-scratch synthesized file crashed on
the very next clean test. This is worse than a wrong resolution — it's a
first-launch crash risk.

### Root cause (grounded in Daodan source, not speculation)

Read directly from `Patches/GL.c` (Daodan source, rev 1000,
`bugs.oni2.net/browser/Daodan/src/Patches/GL.c`):

```c
UUtBool ONICALL DD_GLrPlatform_Initialize(void)
{
    static const M3tDisplayMode FallbackMode = { 640, 480, 16, 0 };
    if (!DD_GLrPlatform_SetDisplayMode(&gl->DisplayMode))
    {
        gl->DisplayMode = FallbackMode;
        ...
```

`DD_GLrPlatform_SetDisplayMode` (same file) only returns failure in windowed
mode when `mode->Height < 480` — a 1440-tall mode never fails that check, so
this specific fallback branch isn't what fires either. `gl->DisplayMode` and
the rest of the graphics-init state are populated from `persist.dat` by
Oni's own proprietary startup code (not Daodan, not available to us — Oni's
source was never released, unlike Daodan's). That code almost certainly
validates the header before trusting it; a header we synthesize ourselves
(real bytes at 5 known offsets, zero everywhere else — no checksum, no
version signature, no whatever else a genuine header carries in the
remaining ~80 bytes) is very likely read as corrupt rather than merely
"defaultable," which is consistent with a hard fatal error instead of a
graceful fallback.

We don't have Oni's source to confirm the exact validation logic, so this
is the best-supported hypothesis from available evidence, not a certainty —
but the fix below is correct regardless of the precise mechanism, since it
never lets the tool synthesize an untrusted header in the first place.

### Fix

`PersistSettingsWriter.ConfigureModernDisplay` must never synthesize
`persist.dat` from a zeroed array. If the file doesn't exist:

1. Launch `Oni.exe` in the target installation, wait for the process to exit
   (the user needs to reach the main menu and quit once — this can be a
   guided step in the launcher UI: "Launching Oni once to initialize its
   settings file — quit from the main menu when ready").
2. Confirm `persist.dat` now exists.
3. Apply the existing byte patch on top of that real file, as today.

If `persist.dat` already exists (e.g., re-running the profile step), patch
it directly as today — the risk is specific to synthesizing the file from
nothing.

No UI automation, no reverse-engineering the full header format needed —
this sidesteps the unknown validation entirely by always patching a file the
game itself considers genuine.

## Problem 2: Daodan acquisition path is broken

### Symptom (reproduced today)

The repo's documented/expected path is a user-supplied
`.runtime/runtime/DaodanDLL.zip`, consumed by `DaodanRuntimeDeployer`. In
practice, the only bundled acquisition flow tested today
(`Oni_Mod_Win_EN_Anniversary-Edition-Mod.exe`, an Inno Setup bootstrapper)
does not deploy Daodan at all — it drops a Java Swing package manager
("AEInstaller2") that requires a GUI wizard, a `.NET` presence check, and
manual package selection, with no accessibility API exposed (no Java Access
Bridge), making it unautomatable and unreliable as an install step.

### Fix

Drop the AE-installer flow from the documented/primary path entirely. The
correct, working source is `mods.oni2.net/node/438` (Oni Mod Depot) —
`DaodanDLL.zip`, which contains a root `Oni.exe` plus a `fps/` folder.
`DaodanRuntimeDeployer.DeployFpsRuntime` already expects exactly this
structure (it strips a `"fps/"` prefix from every entry) — confirmed by
testing today with the real downloaded file. No code change needed in
`DaodanRuntimeDeployer` itself; the fix is documentation/UI-copy only:
point users at that URL as the one supported source for
`.runtime/runtime/DaodanDLL.zip`, and remove any reference to the AE `.exe`
as a Daodan source.

## Problem 3: `disabledoubletapsprint` default breaks the tutorial

### Symptom (reproduced today)

`DaodanProfileWriter`'s default `daodan.ini` sets
`disabledoubletapsprint = true` (intending bindable-sprint as a full modern
replacement for the classic double-tap-W dash). Oni's own in-game training
level explicitly instructs the player to double-tap W to dash and will not
proceed until that succeeds — with the default profile, it's impossible to
complete the tutorial.

### Fix

Change the default to `disabledoubletapsprint = false` in
`DaodanProfileWriter`. `bindablesprint = true` stays on as an *addition*,
not a replacement — both the classic double-tap and a bindable key work.

## Documentation addition: frame rate guidance

Not a bug fix — a gap. Confirmed via Daodan's own `-help` output (the full,
authoritative option list) that there is no frame-rate cap anywhere in
Daodan. Community documentation (`wiki.oni2.net/Troubleshooting`) confirms
game logic speed scales with refresh rate above 60 Hz. Add a README section
stating this plainly and recommending an external 60 FPS cap (GPU driver
per-app frame limiter, or RTSS) for any display above 60 Hz — this is
guidance, not something OniModern can enforce, since Daodan exposes no such
setting.

## Out of scope

- Automatic downloading of Daodan (user-supplied model stays, per explicit
  decision).
- Any change to Oni's own compiled binary or in-game Options UI (no source
  access, see NOTICE.md rights boundary).
- Broadening into asset/mod-tooling (OniSplit, level editors) — a possible
  future direction, explicitly deferred.
- Contributing fixes upstream to Daodan itself.

## Testing

- `DaodanProfileWriter`/`PersistSettingsWriter`/`ModernControlsWriter` unit
  tests already exist (`tests/OniModern.Core.Tests`) and should gain cases
  for: default `disabledoubletapsprint` value, and
  `ConfigureModernDisplay` behavior when `persist.dat` is absent (should
  require/trigger the launch-first step rather than synthesizing a header).
- Manual end-to-end verification (fresh install, no pre-existing
  persist.dat → run the launch-first step → confirm no crash and correct
  resolution once the main menu loads, not during the intro cutscene) is
  the real acceptance test for Problem 1, since the root cause is in code
  we don't have access to. Explicitly re-test the crash path this fix
  removes: a from-scratch persist.dat with no launch-first step should no
  longer be reachable through the normal install flow.
