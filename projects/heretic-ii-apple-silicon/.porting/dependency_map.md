# Milestone 02 - Dependency Map

Date: 2026-06-18

## Native Runtime Dependencies

| Binary | Dependency | Resolution |
|---|---|---|
| `build/Heretic2R` | `@loader_path/H2Common.dylib` | Bundled |
| `build/Heretic2R` | `@loader_path/libSDL3.0.dylib` | Bundled |
| `build/Heretic2R` | `OpenGL.framework` | macOS system framework |
| `build/Heretic2R` | `AppKit.framework` | macOS system framework |
| `build/ref_gl3.dylib` | `@loader_path/H2Common.dylib` | Bundled |
| `build/ref_gl3.dylib` | `@loader_path/libSDL3.0.dylib` | Bundled |
| `build/ref_gl3.dylib` | `OpenGL.framework` | macOS system framework |
| `build/snd_sdl3.dylib` | `@loader_path/H2Common.dylib` | Bundled |
| `build/snd_sdl3.dylib` | `@loader_path/libSDL3.0.dylib` | Bundled |
| `build/snd_sdl3.dylib` | `@loader_path/libopenal.1.dylib` | Bundled |

## Build-Time Dependencies

| Dependency | Use |
|---|---|
| clang / clang++ | Native arm64 compilation |
| SDL3 | Windowing, OpenGL context, input, platform services |
| OpenAL Soft | Audio output |
| macOS OpenGL.framework | GL3 renderer backend |
| AppKit.framework | macOS app/window integration |
| stb_image | PNG/HD texture loading |
| glad GL3.3 | OpenGL function loading |

## Game Runtime Modules

| Module | Path | Notes |
|---|---|---|
| Player module | `build/base/Player.dylib` | Native arm64 dylib |
| Client effects module | `build/base/Client Effects.dylib` | Native arm64 dylib |
| Game logic module | `build/base/gamex86.dylib` | Native arm64 dylib despite legacy filename |
| Renderer | `build/ref_gl3.dylib` | Active renderer |
| Sound | `build/snd_sdl3.dylib` | Active sound backend |

## Renderer Strategy

OpenGL GL3 is the active renderer for milestones 00-14. `src/ref_metal/` may exist as future work, but the build script removes `ref_metal.dylib` from `build/` and from the app bundle so it cannot be mistaken for the active renderer.

## Acceptance Check

Milestone 02 dependency acceptance is met when all native dylibs resolve through `@loader_path` or macOS system frameworks, with no Homebrew absolute paths required at runtime.
