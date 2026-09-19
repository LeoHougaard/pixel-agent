#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="$HOME/.local/bin"
SHORTCUT_DIR="$HOME/.shortcuts"
STATE_DIR="$HOME/.local/state/pixel-desktop"

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
if [ "${available_kb:-0}" -lt 10485760 ]; then
  echo "Pixel Desktop needs at least 10 GB free. Free some storage and try again."
  exit 1
fi

echo "Installing the Android-side desktop packages..."
apt-get update
apt-get -y -o Dpkg::Options::="--force-confold" full-upgrade
pkg install -y x11-repo
pkg install -y proot-distro termux-x11-nightly pulseaudio virglrenderer-android termux-api git curl python android-tools

if ! proot-distro login debian -- /bin/true >/dev/null 2>&1; then
  echo "Installing Debian ARM64..."
  proot-distro install debian
fi

mkdir -p "$BIN_DIR" "$SHORTCUT_DIR" "$STATE_DIR"
cp "$SOURCE_DIR/pixel-desktop-start.sh" "$BIN_DIR/pixel-desktop"
cp "$SOURCE_DIR/pixel-desktop-stop.sh" "$BIN_DIR/pixel-desktop-stop"
cp "$SOURCE_DIR/pixel-desktop-doctor.sh" "$BIN_DIR/pixel-desktop-doctor"
cp "$SOURCE_DIR/pixel-t3-mobile.sh" "$BIN_DIR/pixel-t3-mobile"
chmod 700 "$BIN_DIR/pixel-desktop" "$BIN_DIR/pixel-desktop-stop" "$BIN_DIR/pixel-desktop-doctor" "$BIN_DIR/pixel-t3-mobile"

proot-distro login debian --shared-tmp -- \
  /bin/bash "$SOURCE_DIR/pixel-desktop-guest-setup.sh"
bash "$SOURCE_DIR/pixel-desktop-ui.sh"

cat > "$SHORTCUT_DIR/Pixel Desktop" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
export PATH="$BIN_DIR:\$PATH"
exec pixel-desktop
EOF
chmod 700 "$SHORTCUT_DIR/Pixel Desktop"

cat > "$SHORTCUT_DIR/Stop Pixel Desktop" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
export PATH="$BIN_DIR:\$PATH"
exec pixel-desktop-stop
EOF
chmod 700 "$SHORTCUT_DIR/Stop Pixel Desktop"

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

echo
echo "Pixel Desktop is installed."
echo "Run pixel-desktop-doctor, then add the Termux:Widget 'Pixel Desktop' shortcut."
echo "T3 Code uses the package installed locally during setup."
