#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"

apt-get update
apt-get dist-upgrade -y
apt-get install -y --no-install-recommends \
  xfce4 xfce4-terminal thunar dbus-x11 sudo ca-certificates curl wget git jq \
  xdg-utils desktop-file-utils fonts-noto fonts-noto-color-emoji mesa-utils \
  libgl1-mesa-dri libopengl0 libglu1-mesa libwebkit2gtk-4.1-0 \
  libasound2t64 libgtk-3-0 libfuse2t64 file procps build-essential python3 \
  chromium greybird-gtk-theme papirus-icon-theme mousepad librsvg2-common locales
apt-get install -y --no-install-recommends xdotool wmctrl scrot xclip
localedef -i en_US -f UTF-8 en_US.UTF-8
apt-get clean

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

npm install --global @openai/codex
npm install --global opencode-ai
# npm's trusted-scripts model can skip opencode's postinstall (which fetches
# its binary). If the binary doesn't run, re-install with scripts allowed.
if ! opencode --version >/dev/null 2>&1; then
  npm install --global --allow-scripts=opencode-ai opencode-ai
fi

# Install once, not at shortcut launch. PRoot needs a locally built PTY addon.
su - pixel -c 'npm install --prefix "$HOME/.local/share/t3-code" t3@0.0.38'
su - pixel -c 'npm_config_build_from_source=true npm rebuild --prefix "$HOME/.local/share/t3-code" node-pty'

bash "$SOURCE_DIR/pixel-opencode-setup.sh"

install -d -o pixel -g pixel /home/pixel/.local/bin /home/pixel/.local/share/applications

su - pixel -c 'curl -fsSL https://github.com/zen-browser/updates-server/raw/refs/heads/main/install.sh | bash'
zen_binary="$(find /home/pixel/.tarball-installations/zen -type f -name zen -perm /111 2>/dev/null | head -n 1)"
if [ -z "$zen_binary" ]; then
  echo 'Zen installation did not produce an executable.' >&2
  exit 1
fi
install -m 755 "$SOURCE_DIR/zen-wrapper.sh" /usr/local/bin/zen

install -m 755 "$SOURCE_DIR/pixel-t3-server.sh" /usr/local/bin/pixel-t3-server
install -m 755 "$SOURCE_DIR/pixel-t3-desktop.sh" /usr/local/bin/pixel-t3
for script in pixel-desktop-session pixel-desktop-style pixel-t3-browser; do
  install -m 755 "$SOURCE_DIR/$script.sh" "/usr/local/bin/$script"
done
install -d /usr/local/share/pixel-desktop
install -m 644 "$SOURCE_DIR/pixel-wallpaper.svg" /usr/local/share/pixel-desktop/wallpaper.svg
install -m 644 "$SOURCE_DIR/pixel-t3.svg" /usr/local/share/pixel-desktop/t3.svg

install -m 755 "$SOURCE_DIR/orca-slicer-wrapper.sh" /usr/local/bin/orca-slicer-pixel

cat > /usr/local/bin/install-orcaslicer <<'EOF'
#!/bin/bash
set -euo pipefail
install_dir="$HOME/.local/opt/orcaslicer"
mkdir -p "$install_dir"
asset_url="$(curl -fsSL https://api.github.com/repos/OrcaSlicer/OrcaSlicer/releases/latest | jq -r '.assets[] | select(.name | test("Linux.*aarch64.*AppImage$"; "i")) | .browser_download_url' | head -n 1)"
if [ -z "$asset_url" ]; then
  echo 'The latest OrcaSlicer release has no ARM64 AppImage.' >&2
  exit 1
fi
cd "$install_dir"
curl -fL "$asset_url" -o OrcaSlicer.AppImage
chmod 700 OrcaSlicer.AppImage
rm -rf squashfs-root
./OrcaSlicer.AppImage --appimage-extract >/dev/null
rm OrcaSlicer.AppImage
echo 'OrcaSlicer installed.'
EOF
chmod 755 /usr/local/bin/install-orcaslicer

su - pixel -c 'mkdir -p ~/.local/state ~/.config/xfce4/xfconf/xfce-perchannel-xml'
su - pixel -c 'rm -rf ~/.cache/sessions'
su - pixel -c 'install-orcaslicer'

cat > /home/pixel/.local/share/applications/zen.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Zen Browser
Exec=/usr/local/bin/zen %U
Icon=web-browser
Categories=Network;WebBrowser;
EOF
cat > /home/pixel/.local/share/applications/t3-code.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=T3 Code
Exec=pixel-t3
Icon=/usr/local/share/pixel-desktop/t3.svg
Categories=Development;
EOF
cat > /home/pixel/.local/share/applications/orcaslicer.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=OrcaSlicer
Exec=orca-slicer-pixel %F
Icon=applications-graphics
Categories=Graphics;3DGraphics;
EOF
chown -R pixel:pixel /home/pixel/.local

cat > /home/pixel/.config/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<channel name="xsettings" version="1.0">
  <property name="Xft" type="empty">
    <property name="DPI" type="int" value="96"/>
    <property name="Antialias" type="int" value="1"/>
    <property name="Hinting" type="int" value="1"/>
  </property>
</channel>
EOF
chown -R pixel:pixel /home/pixel/.config

echo 'Guest setup complete.'
