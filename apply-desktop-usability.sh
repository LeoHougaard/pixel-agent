#!/data/data/com.termux/files/usr/bin/bash
set -eu
exec > /sdcard/Download/apply-desktop-usability.log 2>&1
source_dir=/sdcard/Download/pixel-agent
install -m 700 "$source_dir/pixel-desktop-start.sh" "$HOME/.local/bin/pixel-desktop"
proot-distro login debian --shared-tmp -- bash <<'GUEST'
set -eu
source_dir=/sdcard/Download/pixel-agent
for script in pixel-desktop-session pixel-desktop-style pixel-t3-browser; do
  install -m 755 "$source_dir/$script.sh" "/usr/local/bin/$script"
done
install -m 755 "$source_dir/pixel-t3-desktop.sh" /usr/local/bin/pixel-t3
install -m 755 "$source_dir/pixel-t3-server.sh" /usr/local/bin/pixel-t3-server
install -m 755 "$source_dir/zen-wrapper.sh" /usr/local/bin/zen
# The tarball installer also adds ~/.local/bin/zen earlier in login PATH.
# Desktop entries must call the compatibility wrapper explicitly.
sed -i 's|^Exec=zen %U$|Exec=/usr/local/bin/zen %U|' /home/pixel/.local/share/applications/zen.desktop /home/pixel/Desktop/zen.desktop
install -d /usr/local/share/pixel-desktop
install -m 644 "$source_dir/pixel-wallpaper.svg" /usr/local/share/pixel-desktop/wallpaper.svg
install -m 644 "$source_dir/pixel-t3.svg" /usr/local/share/pixel-desktop/t3.svg
old=/home/pixel/.config/autostart/pixel-desktop-settings.desktop
if [ -f "$old" ]; then mv "$old" "$old.disabled"; fi
install -m 755 /home/pixel/Desktop/files.desktop /home/pixel/.local/share/applications/files.desktop
install -m 755 /usr/share/applications/org.xfce.mousepad.desktop /home/pixel/.local/share/applications/mousepad.desktop
GUEST
printf '\nREADY\n'
