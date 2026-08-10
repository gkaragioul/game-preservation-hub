# Dual-Edition Launcher

## Decision

The edition is chosen before the app starts, not toggled in game.

```text
中文     -> Chinese 9game build, package com.dianhun.lxys.aligames   (primary)
English  -> International/global build, package com.oversea.spinarena (reference)
```

## Why the builds stay separate

The Chinese and international clients differ in more than text:

- package names;
- SDK/login hosts;
- distribution channel wrappers;
- resource/download behaviour;
- bundled Cocos assets;
- backend protocol/version expectations.

Merging them into one APK before the runtime and protocol work is complete
would add instability for no benefit. Keeping both builds intact gives faster
iteration and clearer debugging.

## Commands

The accepted operator platform is 64-bit Windows 11 under Windows PowerShell
5.1 Desktop. `dist\launcher.ps1` is the sole supported entry point.

```powershell
dist\launcher.ps1 -Edition cn -Doctor           # read-only preflight, one JSON document
dist\launcher.ps1 -Edition cn -Capture          # full stack + logcat capture
dist\launcher.ps1 -Edition cn -RestartGateway   # restart the gateway only
dist\launcher.ps1 -Edition cn -SkipInstall      # reuse the installed package
dist\launcher.ps1 -Edition en                   # international build (reference only)
```

`-Capture` records the client log under `research\launch_logcat\`; the launcher
state file records which log belongs to the current run.

## Backend relationship

One local backend serves both editions from `server/`. The Chinese path is the
implemented one: discovery, logic token, WebSocket gateway and profile
persistence. The English edition currently exercises only the manifest and
health surface.

## Current runtime status

- **Chinese build**: reaches the lobby, completes an Adventure battle, and
  reloads the result after a restart. See `docs/STATUS.md` for the evidence
  table and `docs/BLOCKERS.md` for what is still open.
- **International build**: installs and starts, but its Cocos scene/resource
  path still needs work. It is not a completion gate.
