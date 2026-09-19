#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

pixel-desktop-stop 2>/dev/null || true
proot-distro remove debian
rm -f "$PREFIX/bin/pixel-desktop" "$PREFIX/bin/pixel-desktop-stop" "$PREFIX/bin/pixel-desktop-doctor" "$PREFIX/bin/pixel-t3-mobile"
rm -f "$HOME/.shortcuts/Pixel Desktop" "$HOME/.shortcuts/Stop Pixel Desktop" "$HOME/.shortcuts/T3 Code Mobile"
rm -rf "$HOME/.local/state/pixel-desktop"

echo "Pixel Desktop and its Debian filesystem were removed. Termux and Termux:X11 were left installed."
