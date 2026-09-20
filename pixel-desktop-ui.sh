#!/data/data/com.termux/files/usr/bin/bash
set -eu
state_dir="$HOME/.local/state/pixel-desktop"
mkdir -p "$state_dir"
if [ ! -f "$state_dir/x11-preferences-before-ui.txt" ]; then
  termux-x11-preference list > "$state_dir/x11-preferences-before-ui.txt"
fi
termux-x11-preference 'forceOrientation:landscape' 'fullscreen:false' \
  'showAdditionalKbd:true' 'additionalKbdVisible:true' \
  'displayResolutionMode:custom' 'displayResolutionCustom:1280x720' \
  'displayStretch:false' 'displayFilteringMode:bilinear' \
  'ekbarPosition:left' 'ekbarPositionIgnoreOrientation:false' \
  "extra_keys_config:[['KEYBOARD','ESC','TAB','SHIFT','CTRL','ALT','PREFERENCES']]" \
  'touchMode:Trackpad' 'showMouseHelper:true' 'scaleTouchpad:true' \
  'tapToMove:false' 'adjustHeightForEK:false' 'enforceCharBasedInput:true'
proot-distro login debian --user pixel --shared-tmp -- bash <<'GUEST'
set -eu
export DISPLAY=:1
mkdir -p "$HOME/Desktop"
for app in zen t3-code orcaslicer; do
  install -m 755 "$HOME/.local/share/applications/$app.desktop" "$HOME/Desktop/$app.desktop"
done
cat > "$HOME/Desktop/files.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Files
Exec=thunar /sdcard/Download
Icon=system-file-manager
Terminal=false
EOF
chmod 755 "$HOME/Desktop/files.desktop"
install -m 755 "$HOME/Desktop/files.desktop" "$HOME/.local/share/applications/files.desktop"
install -m 755 /usr/share/applications/org.xfce.mousepad.desktop "$HOME/.local/share/applications/mousepad.desktop"
GUEST
