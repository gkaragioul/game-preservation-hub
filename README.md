# RLabs — Compatibility, Recovery & Preservation

![RLabs game preservation projects](assets/recompile-labs-banner.png)

RLabs is open infrastructure for understanding how older or disrupted game and software environments behave today: what starts, what fails, what depends on an unavailable service or runtime, and what evidence supports a recovery path.

This hub brings together public preservation projects, machine-readable compatibility knowledge, and contribution guidance. It does not publish Condemned 2 code, private RLabs research, original game files, proprietary assets, clients, credentials, keys, or circumvention material.

## Compatibility knowledge

The [`compatibility/`](compatibility/) directory is the shared public data layer.

- [`compatibility/schema.json`](compatibility/schema.json) defines an evidence-led JSON Schema for compatibility reports.
- [`compatibility/records/`](compatibility/records/) contains initial reports grounded in the projects already hosted here.
- [`docs/rlabs-scan-v0.1.md`](docs/rlabs-scan-v0.1.md) defines the planned standalone Windows inspection CLI that will produce compatible report data.

The data format is deliberately separate from `rlabs-scan`: projects can publish findings by hand, through another tool, or through the scanner once its interface is stable.

## Public projects

| Project | Focus |
| --- | --- |
| [World War 3 — Offline Preservation Toolkit](projects/world-war-3/) | Local preservation research for a lawfully owned Windows client after service shutdown. |
| [Spiral Warrior — Offline Preservation Toolkit](projects/spiral-warrior/) | Local-service preservation research for a user-owned mobile client. |
| [Heretic II Apple Silicon](projects/heretic-ii-apple-silicon/) | Native macOS Apple Silicon port and packaging work. |
| [Theme Hospital Apple Silicon](projects/theme-hospital-apple-silicon/) | Apple Silicon and Metal compatibility work for CorsixTH with user-provided data. |
| [Oni Modern](projects/oni-modern/) | Windows compatibility launcher and configuration work for a user-owned installation. |
| [OpenJKDF2 Modern](projects/openjkdf2-modern/) | Windows 11-oriented modern engine and compatibility work. |

Project documentation, requirements, and updates live inside each project folder. The previous standalone repositories remain public historical references where applicable.

## Contribute

You can help by testing lawfully obtained software, submitting reproducible compatibility reports, improving fixes, and documenting what you learn. Start with [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Rights and safety boundary

RLabs publishes research, source code, configuration, and documentation only. It does not host or distribute original games, commercial assets, proprietary clients, decrypted source, credentials, keys, or cracked binaries. Reports should describe observations without including private data or copyrighted game content.
