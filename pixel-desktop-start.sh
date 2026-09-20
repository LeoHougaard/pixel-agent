#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

STATE_DIR="$HOME/.local/state/pixel-desktop"
LOG_FILE="$STATE_DIR/session.log"
DISPLAY_NUMBER=1
mkdir -p "$STATE_DIR"
# Keep Android's navigation available even if a Linux app is full screen.
termux-x11-preference 'fullscreen:false' </dev/null >/dev/null 2>&1 || true

# Termux's am wrapper supplies the app identity required by Android. The
# /system/bin/am command claims to be com.android.shell and is rejected.
# Detach the session so closing the shortcut's terminal cannot kill the GUI.
if [ "${1:-}" != "--session" ]; then
  nohup flock --nonblock --close "$STATE_DIR/session.lock" "$0" --session \
    </dev/null >>"$LOG_FILE" 2>&1 &
  am start --user 0 -n com.termux.x11/com.termux.x11.MainActivity
  termux-x11-preference 'fullscreen:false' </dev/null >/dev/null 2>&1 || true
  exit 0
fi

exec >>"$LOG_FILE" 2>&1
# flock stays outside the session so daemon children cannot inherit its lock.
echo "$(date -Iseconds) starting Pixel Desktop"

if [ "${PIXEL_DESKTOP_MANAGED:-0}" != 1 ]; then termux-wake-lock 2>/dev/null || true; fi
pkill -f 'termux-x11.*:1' 2>/dev/null || true
pkill -f 'virgl_test_server_android' 2>/dev/null || true
pulseaudio --kill 2>/dev/null || true
if [ "${PIXEL_DESKTOP_MANAGED:-0}" = 1 ]; then
  pulseaudio --daemonize=no --exit-idle-time=-1 >"$STATE_DIR/audio.log" 2>&1 &
else
  pulseaudio --start --exit-idle-time=-1
fi

GPU_ENV='export LIBGL_ALWAYS_SOFTWARE=1'
if [ "${PIXEL_DESKTOP_GPU:-0}" = "1" ] && command -v virgl_test_server_android >/dev/null 2>&1; then
  virgl_test_server_android >"$STATE_DIR/virgl.log" 2>&1 &
  echo $! > "$STATE_DIR/virgl.pid"
  sleep 1
  if kill -0 "$(cat "$STATE_DIR/virgl.pid")" 2>/dev/null; then
    GPU_ENV='export GALLIUM_DRIVER=virpipe; export MESA_GL_VERSION_OVERRIDE=4.5; unset LIBGL_ALWAYS_SOFTWARE'
  fi
fi

termux-x11 ":$DISPLAY_NUMBER" -dpi 96 -legacy-drawing >"$STATE_DIR/x11.log" 2>&1 &
echo $! > "$STATE_DIR/x11.pid"
sleep 2

SESSION_COMMAND="export DISPLAY=:$DISPLAY_NUMBER; export PULSE_SERVER=127.0.0.1; $GPU_ENV; dbus-run-session -- pixel-desktop-session"
proot-distro login debian --user pixel --shared-tmp -- /bin/bash -lc "$SESSION_COMMAND" &
echo $! > "$STATE_DIR/debian.pid"
wait "$(cat "$STATE_DIR/debian.pid")"
