#!/bin/bash
# Debian-guest setup for T3 + OpenCode + free Muse Spark on the Pixel.
# Runs as root inside `proot-distro login debian` (called from guest-setup),
# or re-run later as: proot-distro login debian --shared-tmp -- /bin/bash <this>
set -euo pipefail
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"

apt-get update
apt-get install -y --no-install-recommends gh jq curl python3

# OpenCode CLI (provides the agent T3 drives). Keep Codex too if present.
if ! command -v opencode >/dev/null 2>&1; then
  npm install --global opencode-ai
fi
# npm's trusted-scripts model can skip opencode's postinstall (which fetches
# its binary). If the binary doesn't run, re-install with scripts allowed.
if ! opencode --version >/dev/null 2>&1; then
  npm install --global --allow-scripts=opencode-ai opencode-ai
fi

install -m 755 "$SOURCE_DIR/pixel-phone.sh" /usr/local/bin/pixel-phone

# Per-user config: tools, model default, phone instructions, projects dir.
# NOTE: plain `su - pixel` resets the environment, so copy as root and chown.
GUEST_HOME=/home/pixel
mkdir -p "$GUEST_HOME/.config/opencode/tools" "$GUEST_HOME/.config/pixel-phone" \
  "$GUEST_HOME/.local/bin" "$GUEST_HOME/projects"
cp "$SOURCE_DIR/pixel-opencode/tools/pixel_run.ts" "$GUEST_HOME/.config/opencode/tools/pixel_run.ts"
cp "$SOURCE_DIR/pixel-opencode/tools/pixel_ui.ts" "$GUEST_HOME/.config/opencode/tools/pixel_ui.ts"
cp "$SOURCE_DIR/pixel-opencode/tools/pixel_screenshot.ts" "$GUEST_HOME/.config/opencode/tools/pixel_screenshot.ts"
cp "$SOURCE_DIR/pixel-opencode/tools/pixel_desktop.ts" "$GUEST_HOME/.config/opencode/tools/pixel_desktop.ts"
install -d /usr/local/lib/pixel-agent
install -m 644 "$SOURCE_DIR/pixel-desktop-control.py" /usr/local/lib/pixel-agent/pixel-desktop-control.py
if [ ! -f "$GUEST_HOME/.config/opencode/AGENTS.md" ]; then
  cp "$SOURCE_DIR/pixel-opencode/AGENTS.md" "$GUEST_HOME/.config/opencode/AGENTS.md"
fi
# Install global opencode.json only if the user has none (never clobber their model choice).
if [ ! -f "$GUEST_HOME/.config/opencode/opencode.json" ]; then
  cp "$SOURCE_DIR/pixel-opencode/opencode.json" "$GUEST_HOME/.config/opencode/opencode.json"
fi
chown -R pixel:pixel "$GUEST_HOME/.config/opencode" "$GUEST_HOME/.config/pixel-phone" \
  "$GUEST_HOME/.local/bin" "$GUEST_HOME/projects"
chmod 700 "$GUEST_HOME/.config/pixel-phone"
chmod 600 "$GUEST_HOME/.config/opencode/tools/"*.ts \
  "$GUEST_HOME/.config/opencode/AGENTS.md" \
  "$GUEST_HOME/.config/opencode/opencode.json"

cat <<'EOF'

Pixel OpenCode setup complete.
Next (once, inside Debian as pixel):
  1. proot-distro login debian --user pixel --shared-tmp
  2. opencode auth login   # choose OpenCode Zen, paste key from https://opencode.ai/auth
  3. opencode models       # select opencode/muse-spark-1.3-contributor-free (free contributor tier)
  4. cd ~/projects && gh auth login && gh repo clone <you>/<repo>
Then open T3 Code Mobile, pick the project, pick OpenCode + muse-spark-1.3-contributor-free, and ask.
In Termux, start the phone bridge before T3: pixel-phone-bridge

EOF
