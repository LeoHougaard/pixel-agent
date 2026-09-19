#!/data/data/com.termux/files/usr/bin/bash
set -eu
source_dir=/sdcard/Download/pixel-agent
install -m 700 "$source_dir/pixel-desktop-start.sh" "$HOME/.local/bin/pixel-desktop"
install -m 700 "$source_dir/pixel-desktop-stop.sh" "$HOME/.local/bin/pixel-desktop-stop"
termux-x11-preference list > /sdcard/Download/x11-preferences.txt 2>&1 || true
printf 'Launcher installed.\n'
