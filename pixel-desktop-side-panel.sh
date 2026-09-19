#!/bin/bash
# Run inside the existing XFCE session so its D-Bus authentication is retained.
set -eu
backup="$HOME/.local/state/pixel-desktop-side-layout"
mkdir -p "$backup"
if [ ! -f "$backup/panel-before.txt" ]; then
  xfconf-query -c xfce4-panel -lv > "$backup/panel-before.txt"
  cp "$HOME/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml" "$backup/xfce4-panel.xml"
fi
setprop() { xfconf-query -c xfce4-panel -p "$1" -n -t "$2" -s "$3"; }
setprop /panels/panel-1/mode int 2
setprop /panels/panel-1/position string 'p=7;x=0;y=0'
setprop /panels/panel-1/size int 44
setprop /panels/panel-1/length uint 100
setprop /panels/panel-1/position-locked bool true
setprop /plugins/plugin-1/show-button-title bool false
setprop /plugins/plugin-6/show-labels bool false
xfconf-query -c xfce4-panel -lv > "$backup/panel-after.txt"
