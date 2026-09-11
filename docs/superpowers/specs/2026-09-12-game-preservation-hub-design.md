# Game Preservation & Modernization Hub — Design

## Purpose

Create a small public hub for George Karagioules' selected game preservation,
compatibility, and modern-port projects. The hub makes the work easier to find
without replacing the repositories, their READMEs, or their technical docs.

## Audience

- Players looking for a compatible way to use a legally owned game.
- Developers and preservation contributors looking for active research work.
- People evaluating George Karagioules' public preservation and modernization projects.

## Scope

The site is a single static GitHub Pages page. It has no sign-in, tracking,
database, contact form, downloads, game files, or build instructions copied
from the individual repositories.

### Included projects

| Project | Status | Audience-facing summary | Primary link |
| --- | --- | --- | --- |
| World War 3 — Offline Preservation Toolkit | Paused — seeking collaborators | Research and local tooling for a legitimately owned World War 3 client after official services shut down. | `gkaragioul/ww3-offline-preservation` |
| Spiral Warrior — Offline Preservation Toolkit | Paused — seeking collaborators | Local preservation research that reaches the prologue with a user-owned client and local services. | `gkaragioul/spiral-warrior-offline-preservation` |
| Heretic II Apple Silicon | Playable source port | Native Apple Silicon port and packaging work for Heretic II Remastered. | `gkaragioul/Heretic2_Apple_Silicon` |
| Theme Hospital Apple Silicon | Source project | Native Apple Silicon and Metal work for CorsixTH using user-provided Theme Hospital data. | `gkaragioul/ThemeHospital_Apple_Silicon` |
| Oni Modern | Compatibility launcher | Reversible Windows 11 launcher and configuration tool for a user-owned Oni installation. | `gkaragioul/OniModern` |

### Page sections

1. A concise hero identifying the hub as a game preservation and modernization catalogue.
2. A project grid with one card per project.
3. A rights-and-preservation statement: no original game files, assets, clients, or proprietary content are distributed by this hub.
4. A contribution note for the two paused preservation projects.
5. A compact footer linking to the GitHub profile.

## Card design

Each card contains a platform/category label, project title, honest status,
short description, and a single `View project` link. Cards may use existing,
repo-supplied project artwork only when it is already publicly distributed by
the respective repository; otherwise they use a text-led layout.

The page uses a dark, restrained visual theme appropriate to technical game
preservation. It is responsive, keyboard-accessible, and readable without
JavaScript.

## Publication

Create a public repository named `game-preservation-hub` under `gkaragioul`.
Deploy it with GitHub Pages at:

`https://gkaragioul.github.io/game-preservation-hub/`

The repository includes a GitHub Actions workflow that publishes the static
site after pushes to `main`. No custom domain is part of this first release.

## Acceptance checks

- The page builds as a static site with no errors.
- All five project cards link to the correct public repository.
- Mobile and desktop layouts remain legible.
- The rights boundary and paused-project statuses are visible.
- The deployed Pages URL loads successfully.

## Out of scope

- Mirroring repository documentation or releases.
- Hosting games, assets, APKs, installers, or binaries.
- Mod-management, downloads, analytics, comments, accounts, or a blog.
- Editing the five existing project repositories.
