#!/usr/bin/env bash
set -eo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BUILD="$ROOT/build/macos-arm64"
OBJ="$BUILD/obj"
mkdir -p "$OBJ" "$ROOT/build/base"

if [[ -d "$ROOT/addons" ]]; then
	cp -R "$ROOT/addons/." "$ROOT/build/"
fi

CC="${CC:-clang}"
CXX="${CXX:-clang++}"
SDL_PREFIX="$(brew --prefix sdl3 2>/dev/null || true)"
OPENAL_PREFIX="$(brew --prefix openal-soft 2>/dev/null || true)"
SDL_INCLUDE="$ROOT/include"
SDL_DYLIB=""
OPENAL_INCLUDE="$ROOT/include"
OPENAL_DYLIB=""

if [[ -n "$SDL_PREFIX" && -d "$SDL_PREFIX/include" ]]; then
	SDL_INCLUDE="$SDL_PREFIX/include"
fi

if [[ -n "$SDL_PREFIX" && -f "$SDL_PREFIX/lib/libSDL3.0.dylib" ]]; then
	SDL_DYLIB="$SDL_PREFIX/lib/libSDL3.0.dylib"
elif [[ -f "$ROOT/build/libSDL3.0.dylib" ]]; then
	SDL_DYLIB="$ROOT/build/libSDL3.0.dylib"
elif [[ -f "$ROOT/Heretic II Remastered.app/Contents/Resources/build/libSDL3.0.dylib" ]]; then
	SDL_DYLIB="$ROOT/Heretic II Remastered.app/Contents/Resources/build/libSDL3.0.dylib"
fi

if [[ -z "$SDL_DYLIB" ]]; then
	echo "Could not find libSDL3.0.dylib. Install SDL3 or keep the bundled dylib in the app." >&2
	exit 1
fi

if [[ -n "$OPENAL_PREFIX" && -d "$OPENAL_PREFIX/include" ]]; then
	OPENAL_INCLUDE="$OPENAL_PREFIX/include"
fi

if [[ -n "$OPENAL_PREFIX" && -f "$OPENAL_PREFIX/lib/libopenal.1.dylib" ]]; then
	OPENAL_DYLIB="$OPENAL_PREFIX/lib/libopenal.1.dylib"
elif [[ -f "$ROOT/build/libopenal.1.dylib" ]]; then
	OPENAL_DYLIB="$ROOT/build/libopenal.1.dylib"
elif [[ -f "$ROOT/Heretic II Remastered.app/Contents/Resources/build/libopenal.1.dylib" ]]; then
	OPENAL_DYLIB="$ROOT/Heretic II Remastered.app/Contents/Resources/build/libopenal.1.dylib"
fi

if [[ -z "$OPENAL_DYLIB" ]]; then
	echo "Could not find libopenal.1.dylib. Install openal-soft or keep the bundled dylib in the app." >&2
	exit 1
fi

COMMON_INCLUDES=(
	-I"$ROOT/include"
	-I"$ROOT/src/posix"
	-I"$ROOT/src/qcommon"
	-I"$ROOT/src/game"
	-I"$ROOT/src/Player"
	-I"$ROOT/src/client"
	-I"$ROOT/src/server"
	-I"$ROOT/src/win32"
	-I"$SDL_INCLUDE"
	-I"$OPENAL_INCLUDE"
)

COMMON_FLAGS=(
	-arch arm64
	-O2
	-DNDEBUG
	-D__MACOS_NATIVE__
	-include "$ROOT/src/posix/win_compat.h"
	-fvisibility=default
	-Wno-deprecated-declarations
	-Wno-incompatible-pointer-types
	-Wno-int-conversion
	-Wno-format
	-Wno-microsoft-anon-tag
	-Wno-pragma-pack
	-Wno-unknown-pragmas
)

CFLAGS=(-std=gnu11 "${COMMON_FLAGS[@]}" "${COMMON_INCLUDES[@]}")
CXXFLAGS=(-std=gnu++17 "${COMMON_FLAGS[@]}" "${COMMON_INCLUDES[@]}")
OBJCFLAGS=("${COMMON_FLAGS[@]}" "${COMMON_INCLUDES[@]}")
LDFLAGS=(-arch arm64)
SDL_LIBS=("$SDL_DYLIB")
OPENAL_LIBS=("$OPENAL_DYLIB")

fix_install_names() {
	install_name_tool -id "@loader_path/H2Common.dylib" "$ROOT/build/H2Common.dylib"
	install_name_tool -id "@loader_path/ref_gl3.dylib" "$ROOT/build/ref_gl3.dylib"
	install_name_tool -id "@loader_path/snd_sdl3.dylib" "$ROOT/build/snd_sdl3.dylib"
	install_name_tool -id "@loader_path/base/Player.dylib" "$ROOT/build/base/Player.dylib"
	install_name_tool -id "@loader_path/base/Client Effects.dylib" "$ROOT/build/base/Client Effects.dylib"
	install_name_tool -id "@loader_path/base/gamex86.dylib" "$ROOT/build/base/gamex86.dylib"

	for bin in "$ROOT/build/Heretic2R" "$ROOT/build/ref_gl3.dylib" "$ROOT/build/snd_sdl3.dylib"; do
		install_name_tool -change "$ROOT/build/H2Common.dylib" "@loader_path/H2Common.dylib" "$bin" || true
		install_name_tool -change "$SDL_DYLIB" "@loader_path/libSDL3.0.dylib" "$bin" || true
		install_name_tool -change "$OPENAL_DYLIB" "@loader_path/libopenal.1.dylib" "$bin" || true
	done

	for bin in "$ROOT/build/base/Player.dylib" "$ROOT/build/base/Client Effects.dylib" "$ROOT/build/base/gamex86.dylib"; do
		install_name_tool -change "$ROOT/build/H2Common.dylib" "@loader_path/../H2Common.dylib" "$bin" || true
	done
}

read_project_sources() {
	local project="$1"
	python3 - "$ROOT" "$project" <<'PY'
import pathlib, sys, xml.etree.ElementTree as ET
root = pathlib.Path(sys.argv[1])
project = pathlib.Path(sys.argv[2])
ns = {'ms': 'http://schemas.microsoft.com/developer/msbuild/2003'}
tree = ET.parse(project)
base = project.parent
for node in tree.findall('.//ms:ClCompile', ns):
    inc = node.attrib.get('Include')
    if not inc or inc == 'None':
        continue
    path = (base / inc.replace('\\', '/')).resolve()
    try:
        print(path.relative_to(root))
    except ValueError:
        print(path)
PY
}

compile_source() {
	local target="$1"
	local src="$2"
	shift 2
	local defs=("$@")
	local obj="$OBJ/$target/${src//\//__}.o"
	mkdir -p "$(dirname "$obj")"
	if [[ "$src" == *.m ]]; then
		"$CC" "${OBJCFLAGS[@]}" "${defs[@]}" -c "$ROOT/$src" -o "$obj" >&2 || return 1
	elif [[ "$src" == *.cpp || "$src" == *.cc || "$src" == *.cxx ]]; then
		"$CXX" "${CXXFLAGS[@]}" "${defs[@]}" -c "$ROOT/$src" -o "$obj" >&2 || return 1
	else
		"$CC" "${CFLAGS[@]}" "${defs[@]}" -c "$ROOT/$src" -o "$obj" >&2 || return 1
	fi
	printf '%s\n' "$obj"
}

build_shared() {
	local target="$1"
	local out="$2"
	shift 2
	local objects=("$@")
	"$CXX" "${LDFLAGS[@]}" -dynamiclib -undefined dynamic_lookup "${objects[@]}" -o "$out"
}

collect_sources() {
	local project="$1"
	shift
	local exclude=("$@")
	local src
	while IFS= read -r src; do
		local skip=0
		for pattern in "${exclude[@]}"; do
			if [[ "$src" == "$pattern" ]]; then
				skip=1
				break
			fi
		done
		[[ "$skip" == 0 ]] && printf '%s\n' "$src"
	done < <(read_project_sources "$ROOT/$project")
}

build_target() {
	local target="$1"
	local project="$2"
	local out="$3"
	shift 3
	local defs=()
	local libs=()
	local excludes=()
	local mode="defs"
	for arg in "$@"; do
		case "$arg" in
			--) mode="libs" ;;
			---) mode="excludes" ;;
			*) if [[ "$mode" == "defs" ]]; then defs+=("$arg"); elif [[ "$mode" == "libs" ]]; then libs+=("$arg"); else excludes+=("$arg"); fi ;;
		esac
	done

	local sources=()
	local line
	while IFS= read -r line; do
		sources+=("$line")
	done < <(collect_sources "$project" "${excludes[@]}")
	local objects=()
	local src
	for src in "${sources[@]}"; do
		local obj_path
		obj_path="$(compile_source "$target" "$src" "${defs[@]}")" || exit 1
		objects+=("$obj_path")
	done
		"$CXX" "${LDFLAGS[@]}" -dynamiclib -undefined dynamic_lookup "${objects[@]}" "${libs[@]}" -o "$out"
}

echo "Building H2Common.dylib"
build_target H2Common src/H2Common/H2Common.vcxproj "$ROOT/build/H2Common.dylib" \
	-DH2COMMON

echo "Building Player.dylib"
build_target Player src/Player/Player.vcxproj "$ROOT/build/base/Player.dylib" \
	-DPLAYER_DLL -- "$ROOT/build/H2Common.dylib"

echo "Building Client Effects.dylib"
build_target client_effects "src/client effects/Client Effects.vcxproj" "$ROOT/build/base/Client Effects.dylib" \
	-- "$ROOT/build/H2Common.dylib"

echo "Building gamex86.dylib"
build_target game src/game/game.vcxproj "$ROOT/build/base/gamex86.dylib" \
	-DGAME_DLL -- "$ROOT/build/H2Common.dylib"

echo "Building ref_gl3.dylib"
ref_gl3_sources=()
while IFS= read -r line; do
	ref_gl3_sources+=("$line")
done < <(collect_sources src/ref_gl3/ref_gl3.vcxproj "include/glad-GL3.3/glad.c")
ref_gl3_sources+=("src/ref_gl3/src/gl3_Glad.c")
objects=()
for src in "${ref_gl3_sources[@]}"; do
	obj_path="$(compile_source ref_gl3 "$src")" || exit 1
	objects+=("$obj_path")
done
"$CXX" "${LDFLAGS[@]}" -dynamiclib -undefined dynamic_lookup "${objects[@]}" "$ROOT/build/H2Common.dylib" "${SDL_LIBS[@]}" -framework OpenGL -o "$ROOT/build/ref_gl3.dylib"

echo "Building snd_sdl3.dylib"
build_target snd_sdl3 src/snd_sdl3/snd_sdl3.vcxproj "$ROOT/build/snd_sdl3.dylib" \
	-- "$ROOT/build/H2Common.dylib" "${SDL_LIBS[@]}" "${OPENAL_LIBS[@]}"

echo "Building Heretic2R"
quake_sources=()
while IFS= read -r line; do
	quake_sources+=("$line")
done < <(collect_sources src/win32/quake2.vcxproj \
	"src/win32/sys_win.c" \
	"src/win32/q_shwin.c" \
	"src/win32/net_wins.c" \
	"src/win32/cd_audio.c" \
	"src/qcommon/cd_detect.c" \
	"src/qcommon/pak_detect.c")
quake_sources+=(
	"src/posix/main.c"
	"src/posix/sys_posix.c"
	"src/posix/q_shposix.c"
	"src/posix/net_posix.c"
	"src/posix/cd_audio.c"
	"src/posix/cd_detect_stub.c"
)
objects=()
for src in "${quake_sources[@]}"; do
	obj_path="$(compile_source quake2 "$src" -DQUAKE2_DLL)" || exit 1
	objects+=("$obj_path")
done
"$CXX" "${LDFLAGS[@]}" -Wl,-export_dynamic "${objects[@]}" "$ROOT/build/H2Common.dylib" "${SDL_LIBS[@]}" -framework OpenGL -framework AppKit -ldl -o "$ROOT/build/Heretic2R"

fix_install_names

echo "Native macOS arm64 build complete: $ROOT/build/Heretic2R"
