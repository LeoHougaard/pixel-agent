#!/bin/bash
# Minimal Debian-guest setup for T3 + OpenCode phone dev. No XFCE, no browsers,
# no OrcaSlicer. Runs as root inside `proot-distro login debian`.
# Re-run later as: proot-distro login debian --shared-tmp -- /bin/bash <this>
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"

apt-get update
apt-get dist-upgrade -y
apt-get install -y --no-install-recommends \
  sudo ca-certificates curl wget git jq gh python3 build-essential

if ! id pixel >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash pixel
fi
printf 'pixel ALL=(ALL) NOPASSWD: ALL\n' > /etc/sudoers.d/pixel
chmod 440 /etc/sudoers.d/pixel

install_node() {
  local version archive base
  version="$(curl -fsSL https://nodejs.org/dist/index.json | jq -r '[.[] | select(.version | startswith("v24."))][0].version')"
  archive="node-${version}-linux-arm64.tar.xz"
  base="https://nodejs.org/dist/${version}"
  cd /tmp
  curl -fLO "$base/$archive"
  curl -fsSL "$base/SHASUMS256.txt" | grep " $archive\$" | sha256sum -c -
  tar -xJf "$archive" -C /usr/local --strip-components=1
  rm -f "$archive"
}

if ! command -v node >/dev/null 2>&1 || [ "$(node -p 'Number(process.versions.node.split(`.`)[0])')" -lt 24 ]; then
  install_node
fi

npm install --global opencode-ai
# npm's trusted-scripts model can skip opencode's postinstall (which fetches
# its binary). If the binary doesn't run, re-install with scripts allowed.
if ! opencode --version >/dev/null 2>&1; then
  npm install --global --allow-scripts=opencode-ai opencode-ai
fi

# T3 Code, installed once. PRoot needs a locally built PTY addon.
su - pixel -c 'npm install --prefix "$HOME/.local/share/t3-code" t3@0.0.38'
su - pixel -c 'npm_config_build_from_source=true npm rebuild --prefix "$HOME/.local/share/t3-code" node-pty'

install -m 755 "$SOURCE_DIR/pixel-t3-server.sh" /usr/local/bin/pixel-t3-server
install -m 755 "$SOURCE_DIR/pixel-phone.sh" /usr/local/bin/pixel-phone

bash "$SOURCE_DIR/pixel-opencode-setup.sh"
apt-get clean

cat <<'EOF'

Minimal phone setup complete (no desktop).
Next (once, inside Debian as pixel):
  1. proot-distro login debian --user pixel --shared-tmp
  2. opencode auth login   # OpenCode Zen, key from https://opencode.ai/auth
  3. cd ~/projects && gh auth login && gh repo clone <you>/<repo>
Then just open T3 Code Mobile. In Termux, start the phone bridge first:
pixel-phone-bridge (the T3 shortcut does this automatically).

EOF
