#!/bin/bash
set -eu
# Run in the new desktop's D-Bus session, before the panel starts.
setprop() {
  xfconf-query -c "$1" -p "$2" -n -t "$3" -s "$4"
}
setprop xsettings /Net/ThemeName string Greybird-dark
setprop xsettings /Net/IconThemeName string Papirus-Dark
setprop xsettings /Gtk/FontName string 'Noto Sans 11'
setprop xsettings /Gtk/MonospaceFontName string 'Monospace 11'
setprop xsettings /Gtk/CursorThemeName string Adwaita
setprop xsettings /Gtk/CursorThemeSize int 24
setprop xsettings /Net/DoubleClickTime int 500
setprop xfwm4 /general/theme string Greybird-dark
setprop xfwm4 /general/title_font string 'Noto Sans Bold 11'
setprop xfwm4 /general/use_compositing bool false
setprop xfwm4 /general/workspace_count int 1
setprop xfce4-session /general/SaveOnExit bool false
setprop xfce4-desktop /desktop-icons/icon-size int 48
setprop xfce4-desktop /desktop-icons/font-size double 11
setprop xfce4-desktop /desktop-icons/use-custom-font-size bool true
setprop xfce4-desktop /desktop-icons/file-icons/show-filesystem bool false
setprop xfce4-desktop /desktop-icons/file-icons/show-home bool false
setprop xfce4-desktop /desktop-icons/file-icons/show-trash bool false
setprop xfce4-desktop /desktop-icons/single-click bool true
for monitor in monitor0 monitor1 monitorXWAYLAND0 monitorscreen monitorbuiltin; do
  base="/backdrop/screen0/$monitor/workspace0"
  setprop xfce4-desktop "$base/last-image" string /usr/local/share/pixel-desktop/wallpaper.svg
  setprop xfce4-desktop "$base/image-style" int 5
done
# Replace the two default panels with one vertical, icon-only taskbar.
xfconf-query -c xfce4-panel -p /panels -r -R 2>/dev/null || true
xfconf-query -c xfce4-panel -p /plugins -r -R 2>/dev/null || true
xfconf-query -c xfce4-panel -p /panels -n -a -t int -s 1
setprop xfce4-panel /panels/dark-mode bool true
setprop xfce4-panel /panels/panel-1/mode int 2
setprop xfce4-panel /panels/panel-1/position string 'p=7;x=0;y=0'
setprop xfce4-panel /panels/panel-1/position-locked bool true
setprop xfce4-panel /panels/panel-1/size int 44
setprop xfce4-panel /panels/panel-1/length uint 100
setprop xfce4-panel /panels/panel-1/length-adjust bool false
setprop xfce4-panel /panels/panel-1/autohide-behavior int 0
xfconf-query -c xfce4-panel -p /panels/panel-1/plugin-ids -n -a \
  -t int -s 1 -t int -s 2 -t int -s 3 -t int -s 4 \
  -t int -s 5 -t int -s 6 -t int -s 7 -t int -s 8
setprop xfce4-panel /plugins/plugin-1 string applicationsmenu
setprop xfce4-panel /plugins/plugin-1/button-title string Apps
setprop xfce4-panel /plugins/plugin-1/button-icon string view-grid-symbolic
setprop xfce4-panel /plugins/plugin-1/show-button-title bool false
number=2
for app in files t3-code orcaslicer mousepad; do
  setprop xfce4-panel "/plugins/plugin-$number" string launcher
  xfconf-query -c xfce4-panel -p "/plugins/plugin-$number/items" -n -a \
    -t string -s "/home/pixel/.local/share/applications/$app.desktop"
  number=$((number+1))
done
setprop xfce4-panel /plugins/plugin-6 string tasklist
setprop xfce4-panel /plugins/plugin-6/show-handle bool false
setprop xfce4-panel /plugins/plugin-6/show-labels bool false
setprop xfce4-panel /plugins/plugin-6/flat-buttons bool true
setprop xfce4-panel /plugins/plugin-6/grouping uint 1
setprop xfce4-panel /plugins/plugin-7 string separator
setprop xfce4-panel /plugins/plugin-7/expand bool true
setprop xfce4-panel /plugins/plugin-7/style uint 0
setprop xfce4-panel /plugins/plugin-8 string clock
setprop xfce4-panel /plugins/plugin-8/digital-format string '%H:%M'
setprop xfce4-panel /plugins/plugin-8/digital-time-format string '%H:%M'
setprop xfce4-panel /plugins/plugin-8/digital-layout uint 3
