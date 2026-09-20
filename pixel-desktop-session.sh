#!/bin/bash
set -eu
export NO_AT_BRIDGE=1
export GTK_THEME=Greybird-dark
export XDG_CURRENT_DESKTOP=XFCE
export XDG_SESSION_TYPE=x11
export XDG_RUNTIME_DIR="$HOME/.cache/pixel-runtime"
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
if [ ! -e "$HOME/.config/pixel-desktop-style-v2" ]; then
  backup="$HOME/.local/state/pixel-desktop-style-backup"
  mkdir -p "$backup"
  if [ -d "$HOME/.config/xfce4" ] && [ ! -d "$backup/xfce4" ]; then
    cp -a "$HOME/.config/xfce4" "$backup/xfce4"
  fi
  pixel-desktop-style
  touch "$HOME/.config/pixel-desktop-style-v2"
fi
# This process stays inside the desktop tree, so shutdown also closes the monitor.
python3 /usr/local/lib/pixel-agent/pixel-desktop-activity.py &
monitor=$!
trap 'kill "$monitor" 2>/dev/null || true' EXIT
python3 /usr/local/lib/pixel-agent/pixel-desktop-navigation.py
xfce4-session
