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
exec xfce4-session
