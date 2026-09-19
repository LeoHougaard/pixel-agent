#!/bin/bash
set -e
mkdir -p "$HOME/.local/state"
exec 2>>"$HOME/.local/state/t3-desktop.log"
url="$(pixel-t3-server)"
exec pixel-t3-browser "${url:-http://127.0.0.1:3773}"
