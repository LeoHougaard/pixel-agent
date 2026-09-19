#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
umask 077
state_dir="$HOME/.local/state/pixel-t3"
runtime="$HOME/.local/share/pixel-agent/pixel-t3-runtime.py"
mkdir -p "$state_dir"
exec 9>"$state_dir/launch.lock"
flock -w 610 9 || { echo 'Startup is still busy. Use Stop Pixel Agent to cancel it.' >&2; exit 1; }

# The runtime holds this lock until all of its children have stopped.
if flock -n "$state_dir/runtime.lock" true; then
  rm -f "$state_dir/status.json" "$state_dir/stop"
  nohup python "$runtime" </dev/null >"$state_dir/runtime.log" 2>&1 9>&- &
fi
touch "$state_dir/use"
echo 'Starting Pixel Agent. This can take up to 10 minutes.'
echo 'Stop Pixel Agent works even if chat cannot connect.'
deadline=$((SECONDS + 610))
while :; do
  phase="$(python - "$state_dir/status.json" <<'PYTHON'
import json,sys
try: print(json.load(open(sys.argv[1])).get('phase', 'starting'))
except (OSError, ValueError): print('starting')
PYTHON
)"
  case "$phase" in
    ready) break;;
    error|stopped)
      python - "$state_dir/status.json" <<'PYTHON'
import json,sys
print(json.load(open(sys.argv[1])).get('message', 'Pixel Agent stopped.'))
PYTHON
      exit 1;;
  esac
  [ "$SECONDS" -lt "$deadline" ] || { pixel-t3-stop; echo 'Startup timed out.' >&2; exit 1; }
  sleep 2
done

# Use the web UI shipped with this exact server version and a fresh local
# pairing link. No saved remote address or native-client version is involved.
url="$(timeout 60 proot-distro login debian --user pixel --shared-tmp -- \
  /bin/bash -lc 'pixel-t3-server --pair-only' 2>"$state_dir/pair.log")" || {
    echo 'Could not open chat. Use Stop Pixel Agent, then tap T3 Code Mobile to retry.' >&2
    exit 1
  }
case "$url" in
  http://127.0.0.1:3773/*) ;;
  *) echo 'T3 did not return a phone-local pairing link.' >&2; exit 1;;
esac
touch "$state_dir/use"
termux-open-url "$url"
