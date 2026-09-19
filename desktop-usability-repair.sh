#!/data/data/com.termux/files/usr/bin/bash
set -eu
exec > /sdcard/Download/desktop-usability-repair.log 2>&1
termux-x11-preference 'showAdditionalKbd:true' 'additionalKbdVisible:true' \
  'ekbarPosition:bottom' 'ekbarPositionIgnoreOrientation:false' \
  "extra_keys_config:[['KEYBOARD','ESC','TAB','CTRL','ALT','LEFT','DOWN','UP','RIGHT','PREFERENCES']]" \
  'touchMode:Simulated touchscreen' 'adjustHeightForEK:true' \
  'displayResolutionMode:scaled' 'displayScale:180' 'enforceCharBasedInput:true'
proot-distro login debian --shared-tmp -- bash <<'GUEST'
set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends chromium greybird-gtk-theme papirus-icon-theme mousepad
GUEST
printf '\nPACKAGES_READY\n'
proot-distro login debian --user pixel --shared-tmp -- bash <<'GUEST'
printf '\nDBUS_DIAG\n'
id
timeout 8 dbus-run-session -- sh -c 'dbus-send --session --print-reply --dest=org.freedesktop.DBus / org.freedesktop.DBus.ListNames'
GUEST
