#!/data/data/com.termux/files/usr/bin/bash
set -u

# Disconnect only desktop X clients. Do not kill unrelated PRoot sessions,
# including the local T3 server.
pkill -f 'termux-x11.*:1' 2>/dev/null || true
pkill -f 'virgl_test_server_android' 2>/dev/null || true
pulseaudio --kill 2>/dev/null || true
am broadcast -a com.termux.x11.ACTION_STOP -p com.termux.x11 >/dev/null 2>&1 || true
termux-wake-unlock 2>/dev/null || true
echo "Pixel Desktop stopped."
