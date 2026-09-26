#!/bin/zsh
set -e

cd "$(dirname "$0")/build"

exec ./Heretic2R \
  +set vid_display_index 3 \
  +set vid_ref gl3 \
  +set vid_mode 0 \
  +set vid_fullscreen 0 \
  +set scr_frame_spike_log 0
