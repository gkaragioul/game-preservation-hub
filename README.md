[![RecompileLabs — Old games. New possibilities. Check your game. Free to use, no account, files stay on your device.](assets/recompilelabs-site-header.png)](https://recompilelabs.com/#scanner)

**[Check your game →](https://recompilelabs.com/#scanner)**

[Website](https://recompilelabs.com/) · [Projects](#different-games-shared-lessons) · [Scanner & CLI](https://github.com/gkaragioul/rlabs-scan) · [Contribute](CONTRIBUTING.md)

---

## Compatibility knowledge

**[Check your game online with RLabs Scan](https://recompilelabs.com/#scanner)** — choose a Windows game folder; no account, Python installation, or terminal required.

The scan runs locally inside your browser. It lists the selected folder's filenames and inspects one executable, rather than uploading or reading the entire game installation. If several executables are found, you choose which one to inspect. As disclosed before folder selection, the website automatically sends a small technical report: executable SHA-256, architecture, import count and allowlisted component observations. Game files, filenames, folder paths and usernames are not uploaded. The file hash identifies a build, so this is not an anonymity guarantee. Saved or copied reports are richer local exports; review them before sharing. The Python CLI does not submit reports.

Current limits: 128 MB per executable, 30,000 files per selected folder, and a 30-second scan timeout. Results describe static clues, not tested compatibility. The browser cannot determine whether a dependency is installed elsewhere in Windows.

The [`compatibility/`](compatibility/) directory is the shared public data layer.

- [`compatibility/schema.json`](compatibility/schema.json) defines an evidence-led JSON Schema for compatibility reports.
- [`compatibility/records/`](compatibility/records/) contains initial reports grounded in the projects already hosted here.
- [`RLabs Scan`](https://github.com/gkaragioul/rlabs-scan) documents the browser experience and hosts the original Python CLI for advanced use. The [`v0.1 interface specification`](docs/rlabs-scan-v0.1.md) describes the original CLI design, not the browser interface.

The hub schema is separate from scanner exports. Browser downloads use `rlabs-browser-scan` version 1 and are supporting evidence, not ready-to-merge compatibility records. Add your test environment and actual observations when contributing a record under the hub schema.

## Different games. Shared lessons.

Recovery, native ports, and compatibility work. Each project adds evidence to a growing body of public knowledge.

<table>
<tr>
<td width="50%" valign="top">
<a href="projects/world-war-3/"><img src="projects/world-war-3/assets/project-cover.jpg" alt="World War 3" width="480" /></a>
<h3><a href="projects/world-war-3/">World War 3</a></h3>
<p>Offline preservation · Understanding a Windows client after its online services disappear.</p>
</td>
<td width="50%" valign="top">
<a href="projects/spiral-warrior/"><img src="projects/spiral-warrior/assets/project-cover.jpg" alt="Spiral Warrior" width="480" /></a>
<h3><a href="projects/spiral-warrior/">Spiral Warrior</a></h3>
<p>Service recovery · Documenting local-service preservation for a mobile game.</p>
</td>
</tr>
<tr>
<td width="50%" valign="top">
<a href="projects/heretic-ii-apple-silicon/"><img src="projects/heretic-ii-apple-silicon/assets/project-cover.png" alt="Heretic II" width="480" /></a>
<h3><a href="projects/heretic-ii-apple-silicon/">Heretic II Apple Silicon</a></h3>
<p>Native macOS · Bringing a classic to modern Apple hardware.</p>
</td>
<td width="50%" valign="top">
<a href="projects/theme-hospital-apple-silicon/"><img src="projects/theme-hospital-apple-silicon/assets/project-cover.png" alt="Theme Hospital" width="480" /></a>
<h3><a href="projects/theme-hospital-apple-silicon/">Theme Hospital Apple Silicon</a></h3>
<p>Apple Silicon &amp; Metal · Compatibility work for CorsixTH with your own game data.</p>
</td>
</tr>
<tr>
<td width="50%" valign="top">
<a href="projects/oni-modern/"><img src="projects/oni-modern/assets/project-cover.jpg" alt="Oni Modern" width="480" /></a>
<h3><a href="projects/oni-modern/">Oni Modern</a></h3>
<p>Windows compatibility · Launcher and configuration work for existing installations.</p>
</td>
<td width="50%" valign="top">
<a href="projects/openjkdf2-modern/"><img src="projects/openjkdf2-modern/assets/project-cover.png" alt="OpenJKDF2 Modern" width="480" /></a>
<h3><a href="projects/openjkdf2-modern/">OpenJKDF2 Modern</a></h3>
<p>Engine modernization · A modern engine path with a focus on Windows 11.</p>
</td>
</tr>
</table>

Project documentation, requirements, and updates live inside each project folder. The previous standalone repositories remain public historical references where applicable.

## Your findings can help the next player.

You can help by testing lawfully obtained software, submitting reproducible compatibility reports, improving fixes, and documenting what you learn. Start with [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Rights and safety boundary

RLabs publishes research, source code, configuration, and documentation only. It does not host or distribute original games, commercial assets, proprietary clients, decrypted source, credentials, keys, or cracked binaries. Reports should describe observations without including private data or copyrighted game content.

Condemned 2 and private RLabs research remain separate from this public infrastructure.
