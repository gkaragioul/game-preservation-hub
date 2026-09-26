# Consolidated Game Projects — Design

> **Status:** implemented, with three changes. The GitHub Pages catalogue was
> dropped: this repository's README is the catalogue. The World War 3 source
> repository stays private; only its public summary is in `projects/world-war-3`.
> The projects were imported as plain folders; their full commit history stays
> in the archived standalone repositories.

## Purpose

Make `gkaragioul/game-preservation-hub` the single active GitHub repository
for five selected game preservation and modernization projects, while retaining
the old repositories as public, read-only historical references.

## Included repositories

| Existing repository | Destination folder in the hub |
| --- | --- |
| `ww3-offline-preservation` | `projects/world-war-3` |
| `spiral-warrior-offline-preservation` | `projects/spiral-warrior` |
| `Heretic2_Apple_Silicon` | `projects/heretic-ii-apple-silicon` |
| `ThemeHospital_Apple_Silicon` | `projects/theme-hospital-apple-silicon` |
| `OniModern` | `projects/oni-modern` |

## Architecture

The public GitHub Pages catalogue remains at the repository root. Each selected
project is imported as a Git subtree under `projects/`, preserving its complete
commit history inside the hub repository. The five project cards link to their
corresponding folders in the hub rather than to separate active repositories.

The existing public repositories are not deleted. After each import is verified
on GitHub, its repository is archived. An archived repository preserves its
commits, releases, issues, pull requests, links, and clone access, but cannot
receive normal changes.

## Scope

- Import the full default-branch contents and commit history of all five
  repositories.
- Keep each project separated under its declared destination folder.
- Update the hub page and README links to the five destination folders.
- Add a concise migration note explaining that the old repositories are
  historical, read-only references.
- Verify that every imported folder is present locally and on GitHub before
  archiving the associated original repository.
- Archive the five named original repositories only after all validation passes.

## Exclusions

- No deletion of repositories, code, releases, issues, or project history.
- No change to the content, licensing, or technical behavior of any imported
  project beyond the move into its hub folder.
- No import of repositories beyond the five named above.
- No change to the GitHub Pages URL, domain, or visual design except updating
  project links and adding the migration note.

## Validation

- Each of the five `projects/` folders exists and contains its source files.
- The hub's Git log includes commit history from each imported repository.
- The public GitHub folder links load for all five projects.
- The published site still loads and directs each card to the matching hub
  folder.
- GitHub reports each original repository as archived only after the preceding
  checks pass.
