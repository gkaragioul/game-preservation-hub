# Third-Party Notices

This port's own source is released under the GNU General Public License,
version 3 (see `LICENSE`). It also includes, or links against, the
third-party components listed below. Each one stays under its own licence;
the notices in the files themselves are the authoritative text.

| Component | Where | Licence |
| --- | --- | --- |
| SDL 3 (3.4.4), Sam Lantinga and contributors | `include/SDL3/` headers, `lib/SDL3/` Windows import libraries; macOS builds link `libSDL3.0.dylib` | zlib licence |
| OpenAL Soft | `include/AL/` headers, `lib/OpenAL/` Windows import libraries; macOS builds link `libopenal.1.dylib` (Homebrew `openal-soft`) | GNU LGPL, version 2 or later |
| libsmacker, Greg Kennedy | `include/libsmacker/` (small local changes, such as compiler warning pragmas) | GNU LGPL, version 2.1 or later |
| glad 0.1.36 generated OpenGL loaders | `include/glad-GL1.3/`, `include/glad-GL3.3/` | Generated code: public domain (WTFPL or CC0-1.0); OpenGL specification data: Apache-2.0 |
| glad 2.0.6 generated OpenGL loader | `include/glad-GL4.6/`, `include/glad-GL4.6_temp/` | `(WTFPL OR CC0-1.0) AND Apache-2.0` (as stated in the files) |
| Khronos `khrplatform.h`, The Khronos Group Inc. | `include/glad-*/khrplatform.h` | Khronos MIT-style licence (in the file) |
| stb_image, stb_image_write, stb_vorbis, Sean Barrett and contributors | `include/stb/` | Public domain (Unlicense) or MIT, at your choice |

## LGPL components in packaged builds

When a packaged macOS app includes `libopenal.1.dylib`, it is the unmodified
OpenAL Soft library, loaded dynamically, so you can replace it with your own
build. OpenAL Soft source: https://github.com/kcat/openal-soft.

libsmacker is compiled into the game. Its complete source, including the local
changes, is in `include/libsmacker/`, and the rest of this port's source is in
this folder, so you can rebuild the program with a modified libsmacker.
libsmacker upstream: https://libsmacker.sourceforge.net/.

## Licence texts

- zlib licence: https://www.libsdl.org/license.php
- GNU LGPL 2.1: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html
- GNU LGPL 2.0: https://www.gnu.org/licenses/old-licenses/lgpl-2.0.html
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- CC0-1.0: https://creativecommons.org/publicdomain/zero/1.0/

## Not covered here

The fan-made add-ons in `addons/` belong to their original authors (see the
readme files in each folder). Heretic II game data is not included and must
come from your own legally owned copy.
