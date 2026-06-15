#!/bin/zsh
set -e

cd "$(dirname "$0")/build"

exec ./Heretic2R \
  +set vid_ref gl3 \
  +set vid_mode 0 \
  +set r_vsync 1 \
  +set vid_maxfps 60
