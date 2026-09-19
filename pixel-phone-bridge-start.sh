#!/data/data/com.termux/files/usr/bin/bash
# Termux-side: keep the Pixel Phone bridge running and sync its token
# into the Debian guest so OpenCode (under T3) can call it.
set -euo pipefail
PORT="${PIXEL_PHONE_PORT:-18080}"
STATE_DIR="$HOME/.local/state/pixel-phone"
INSTALL_DIR="$HOME/.local/share/pixel-agent"
mkdir -p "$STATE_DIR"

if [ -f "$STATE_DIR/bridge.pid" ] && kill -0 "$(cat "$STATE_DIR/bridge.pid")" 2>/dev/null; then
  echo "Pixel Phone bridge already running (pid $(cat "$STATE_DIR/bridge.pid"))."
else
  export RISH_APPLICATION_ID=com.termux
  nohup python "$INSTALL_DIR/pixel-phone-bridge.py" >"$STATE_DIR/bridge.log" 2>&1 &
  echo $! > "$STATE_DIR/bridge.pid"
  sleep 1
fi

# Wait for health (bridge may report unavailable backend until Shizuku/adb ready).
for _ in $(seq 1 10); do
  if curl -fsS --max-time 2 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then break; fi
  sleep 1
done
curl -fsS --max-time 3 "http://127.0.0.1:$PORT/health" || {
  echo "Bridge did not become ready; see $STATE_DIR/bridge.log" >&2; exit 1; }

# Sync token into Debian guest home so the OpenCode tools can read it.
TOKEN_FILE="$HOME/.config/pixel-agent/bridge-token"
if [ -f "$TOKEN_FILE" ] && command -v proot-distro >/dev/null 2>&1 \
   && proot-distro login debian -- /bin/true >/dev/null 2>&1; then
  proot-distro login debian --user pixel --shared-tmp -- /bin/bash -c \
    'mkdir -p "$HOME/.config/pixel-phone" && chmod 700 "$HOME/.config/pixel-phone"' 2>/dev/null || true
  # Push via stdin to avoid token appearing in process lists on either side.
  proot-distro login debian --user pixel --shared-tmp -- \
    /bin/bash -c 'cat > "$HOME/.config/pixel-phone/bridge-token" && chmod 600 "$HOME/.config/pixel-phone/bridge-token"' \
    < "$TOKEN_FILE" 2>/dev/null || echo "Note: could not sync token into Debian; copy it manually." >&2
fi
echo "Pixel Phone bridge ready on 127.0.0.1:$PORT."
