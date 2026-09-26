# World War 3 research update — 26 September 2026

This is a public summary of private research notes dated 21–24 September 2026. The underlying archive was supplied for review; its tests have **not** been independently reproduced for this page. No client files, game assets, server code, packet captures, credentials, or raw account data are published here.

## Loadouts and customization

- **40-weapon roster:** A 22 September note records a user-run client session in which weapons and multiple customization options were used, and reports that the tested weapons functioned normally. A separate local backend inventory check found 40 of 40 roster entries present and at their progression-tree maximum. The client-use claim is the note's report, not a public, reproducible test or proof of a working offline match.
- **211 active weapon blueprints:** A local backend check found 211 visible blueprint definitions for the 40 active weapon groups and ownership entries for all 211. The note explicitly called for a fresh in-game check of the Blueprints and Configs screens. It therefore establishes **backend catalog and ownership state only**, not that all 211 were visible or usable in the client.
- **Save-state persistence:** Another note records a loadout and one customization change surviving a restart of the local REST services, with the saved profile file still containing the change. A second client launch after that restart was **not** verified.

These are bounded observations from the supplied notes, not a claim that progression, customization, or persistence is complete across every client workflow.

## Match status is unchanged

The archived project README still identifies the transition from the deploy screen to first-person spawn as blocked. The existing [project overview](README.md) describes a one-map, one-client replay harness, not a simulated multiplayer game server. None of the loadout, blueprint, or persistence findings resolves that blocker.

The private archive and its raw evidence remain outside the tracked, public repository content because they include material unsuitable for public redistribution or disclosure.
