# Milestone 00 — Legal & Asset Boundaries

## Game Data Ownership

This repository tracks source code, build scripts, documentation, and project metadata only. It **does not** store proprietary game data.

## Required Runtime Data (User-Supplied)

| File | Source | Size | Status |
|---|---|---|---|
| `base/Htic2-0.pak` | Original Heretic II retail CD/DVD | 206 MB | Present (Nov 1998) |
| `base/Htic2-1.pak` | Original Heretic II retail CD/DVD | 42 MB | Present (Nov 1998) |
| `base/base.pak` | Spacefarer Heretic II Remastered R8_00 | 1.9 GB | Present (Mar 2026) |
| `base/HDTextures/` | Spacefarer Remastered (159 textures) | ~200 MB | Present |

## Data NOT in Repository

- Retail PAK files (Htic2-0.pak, Htic2-1.pak) — copyright Raven Software / Activision
- Spacefarer Remastered base.pak — owned by the Remastered project under its licensing terms
- HD texture PNGs — same as base.pak
- The built `.app` bundle (gitignored)
- The `build/` directory (gitignored)
- Heretic II icon / branding assets — property of original rights holders

## What Is In Repository

- All source code under `src/` (GPL-compatible open source port)
- Build and packaging scripts
- Compatibility headers in `include/`
- Documentation and notes
- Small stub/lib references

## Addon/MOD Content (addons/)

17 community map/mod folders are present under `addons/`. These are community-created content for Heretic II and are tracked in the repository.

## Boundary Rules

1. No proprietary asset shall be committed to the git repository
2. The `build/` directory and `*.app` are gitignored
3. Instructions for obtaining and placing game data are documented in README.md
4. The project facilitates playing legally owned Heretic II copies on Apple Silicon — it does not distribute the game
5. Attribution to Heretic2R source port and Spacefarer Remastered project must be maintained

## Version Tracking

- Spacefarer Remastered: R8_00 (from base.pak, reported by engine as "Heretic 2 Remastered R8_00")
- Retail data: 1998 original release (no patch applied — Htic2-0/Htic2-1 are base CD PAKs)
- Patch 1.06 available in `stuff/Heretic_II_Patch_106_for_H2R.zip` (not applied by default)
