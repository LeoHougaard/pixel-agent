#!/data/data/com.termux/files/usr/bin/bash
# Minimal Pixel Phone setup: Debian + T3 + OpenCode + phone bridge.
# No XFCE, no Termux:X11, no browsers, no OrcaSlicer. Daily use is just
# the "T3 Code Mobile" widget shortcut.
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="$HOME/.local/bin"
SHORTCUT_DIR="$HOME/.shortcuts"
STATE_DIR="$HOME/.local/state/pixel-desktop"
INSTALL_DIR="$HOME/.local/share/pixel-agent"

if [ "$(uname -o 2>/dev/null || true)" != "Android" ]; then
  echo "Run this installer inside Termux on the Pixel."
  exit 1
fi

mkdir -p "$HOME/.termux"
if ! grep -q '^allow-external-apps *= *true' "$HOME/.termux/termux.properties" 2>/dev/null; then
  printf '\nallow-external-apps = true\n' >> "$HOME/.termux/termux.properties"
  termux-reload-settings
fi
termux-wake-lock 2>/dev/null || true
trap 'termux-wake-unlock 2>/dev/null || true' EXIT

available_kb="$(df -Pk "$HOME" | awk 'NR == 2 {print $4}')"
if [ "${available_kb:-0}" -lt 3145728 ]; then
  echo "Pixel Phone needs at least 3 GB free. Free some storage and try again."
  exit 1
fi

echo "Installing Android-side packages..."
apt-get update
apt-get -y -o Dpkg::Options::="--force-confold" full-upgrade
pkg install -y proot-distro termux-api git curl python android-tools

if ! proot-distro login debian -- /bin/true >/dev/null 2>&1; then
  echo "Installing Debian ARM64 (minimal, no desktop)..."
  proot-distro install debian
fi

mkdir -p "$BIN_DIR" "$SHORTCUT_DIR" "$STATE_DIR" "$INSTALL_DIR"
cp "$SOURCE_DIR/pixel-phone-bridge.py" "$INSTALL_DIR/pixel-phone-bridge.py"
cp "$SOURCE_DIR/pixel-phone-bridge-start.sh" "$BIN_DIR/pixel-phone-bridge"
cp "$SOURCE_DIR/pixel-t3-mobile.sh" "$BIN_DIR/pixel-t3-mobile"
chmod 700 "$BIN_DIR/pixel-phone-bridge" "$BIN_DIR/pixel-t3-mobile"

echo "Setting up the Debian guest (T3 + OpenCode, no desktop)..."
proot-distro login debian --shared-tmp --bind "$SOURCE_DIR:/run/pixel-setup" -- \
  /bin/bash /run/pixel-setup/pixel-phone-guest-setup.sh

cat > "$SHORTCUT_DIR/T3 Code Mobile" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
export PATH="$BIN_DIR:\$PATH"
exec pixel-t3-mobile
EOF
chmod 700 "$SHORTCUT_DIR/T3 Code Mobile"
bash "$SOURCE_DIR/apply-pixel-power.sh"

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$HOME/.bashrc" ;;
esac

if ! grep -Fq 'export RISH_APPLICATION_ID=com.termux' "$HOME/.bashrc" 2>/dev/null; then
  printf 'export RISH_APPLICATION_ID=com.termux\n' >> "$HOME/.bashrc"
fi

echo
echo "Pixel Phone is installed (no desktop)."
echo "Once, in Debian: proot-distro login debian --user pixel --shared-tmp"
echo "  then: opencode auth login   (OpenCode Zen key from https://opencode.ai/auth)"
echo "  then: cd ~/projects && gh auth login && gh repo clone <you>/<repo>"
echo "Daily use: open the Termux:Widget 'T3 Code Mobile' shortcut."
echo "Phone UI control also needs Shizuku/rish or paired Termux adb."
