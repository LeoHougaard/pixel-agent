#!/bin/bash
set -eu
# This dedicated profile is for the phone's local T3 service. PRoot cannot
# provide Chromium's namespace sandbox; Android still isolates Termux itself.
exec chromium --no-sandbox --disable-dev-shm-usage --disable-gpu \
  --no-first-run --no-default-browser-check --password-store=basic \
  --start-maximized \
  --user-data-dir="$HOME/.local/share/t3-browser" \
  --app="${1:-http://127.0.0.1:3773}"
