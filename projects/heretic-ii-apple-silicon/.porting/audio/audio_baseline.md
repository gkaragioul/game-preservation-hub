# Milestone 08 - Audio Baseline

Date: 2026-06-18

## Goal

Make audio reliable enough to move forward from the baseline porting phase.

## Acceptance Criteria

- No missing menu audio.
- No missing intro/cinematic audio path.
- No repeatable crackling/stutter caused by SDL/CoreAudio underruns.

## Changes Made

- Increased the default SDL mixer lookahead from `0.14` to `0.20` seconds in `src/snd_sdl3/src/snd_main.c`.
- Increased the SDL ring buffer allocation from `samples * channels * 10` to `samples * channels * 16` in `src/snd_sdl3/src/snd_sdl3.c`.
- Added callback-side buffer top-up in `SNDSDL3_FillSDL3AudioBuffer()`. If CoreAudio asks for more frames than the engine has painted, the callback now paints ahead before copying instead of emitting silence and logging an underrun.
- Kept the existing loading-screen behavior that pauses playback and clears the dirty buffer while `disable_screen` is active.

## Evidence

### Build

Build log:

- `.porting/build_logs/m08_audio_build_after_callback_topup.log`

Result:

- `Native macOS arm64 build complete`

### Menu Audio

Runtime log:

- `.porting/runtime_logs/m08_audio_menu_after_callback_topup.log`

Evidence:

- CoreAudio initialized through SDL3.
- Sound sampling rate reported.
- `misc/menu1.wav` played repeatedly through the local sound path.
- No `SDL audio underrun`.
- No `SDL_Update: overflow`.
- No `can't cache` or `Failed to load sound`.

### Gameplay, Ambient, Spell/Weapon Sounds, Positional Effects

Runtime log:

- `.porting/runtime_logs/m08_audio_gameplay_after_callback_topup.log`

Evidence:

- `ssdocks` loaded.
- Explicit samples `weapons/HellFire.wav` and `weapons/bowdraw2.wav` played.
- Ambient samples including `ambient/waterlap.wav` and `ambient/ocean.wav` were active.
- Positional sound path is covered by `S_Update()` listener updates and `SNDSDL3_Spatialize()` before channel mixing.
- No `SDL audio underrun`.
- No `SDL_Update: overflow`.
- No `can't cache` or `Failed to load sound`.

Before the callback top-up fix, the same gameplay startup scenario logged:

- `SDL audio underrun: needed 1024 frames, had 628`
- repeated `SDL audio underrun: needed 1024 frames, had 0`
- `SDL_Update: overflow`

After the fix, those repeatable startup/map-load underruns are gone in the same scenario.

### Intro/Cinematic Audio

Runtime log:

- `.porting/runtime_logs/m08_audio_intro_gamemap.log`

Evidence:

- Triggered through the real server cinematic path with `gamemap "intro.smk+ssdocks"` using the local `lanius/video/intro.smk` asset.
- The client opened `intro.smk` through `SCR_PlayCinematic()`.
- `cl_smk.c` enables `SMK_AUDIO_TRACK_0`, reads the SMK audio metadata, and sends cinematic audio chunks through `se.RawSamples()`.
- No `SDL audio underrun`.
- No `SDL_Update: overflow`.

Note:

- `+cinematic splash.smk` is not a valid public console command in this build. Cinematics are driven by server map/cinematic state, so the validation used `gamemap`.

### Music

Evidence:

- Base PAKs contain `music/Track02.ogg` through `music/Track15.ogg`.
- Menu code calls `se.MusicPlay(CDTRACK_MENU_MAIN, 0, true)`.
- OGG music streams through `OGG_Stream()` into `S_RawSamples()`, the same raw mixer path used by cinematics.
- Runtime checks showed no OGG/music decode errors.

## Result

M08 audio baseline passes the acceptance criteria from the automated smoke checks:

- Menu audio path present and clean.
- Intro/cinematic audio path present and clean.
- Gameplay, ambient, and spell/weapon sounds present and clean.
- No repeatable SDL/CoreAudio underrun or overflow remains in the tested startup/map-load scenario.

## Remaining Manual QA

- Listen through the intro on real speakers/headphones once after launching normally from the app bundle.
- Play 10-15 minutes with spell-heavy combat and confirm there is no human-audible crackle.
- Test minimized/unfocused app behavior once, because `S_StopAllSounds()` intentionally clears old buffered audio when focus changes.
