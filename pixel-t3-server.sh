#!/bin/bash
set -e
port=3773
log="$HOME/.local/state/t3-code.log"
mkdir -p "$HOME/.local/state"
# Launch the already-installed ARM64 package. npx t3@latest can otherwise
# perform a network lookup on every cold launch and stall offline.
entry_file="$HOME/.local/state/t3-code-entry"
entry="$(cat "$entry_file" 2>/dev/null || true)"
if [ -f "$HOME/.local/share/t3-code/node_modules/t3/dist/bin.mjs" ]; then
  entry="$HOME/.local/share/t3-code/node_modules/t3/dist/bin.mjs"
fi
if [ ! -f "$entry" ]; then
  entry=''
  for candidate in "$HOME"/.npm/_npx/*/node_modules/t3/dist/bin.mjs; do
    if [ -f "$candidate" ]; then entry="$candidate"; break; fi
  done
  if [ -z "$entry" ]; then
    echo 'The local T3 package is missing. Reinstall T3 Code while online.' >&2
    exit 1
  fi
  printf '%s\n' "$entry" > "$entry_file"
fi
# The mobile launcher keeps this foreground process in its own detached PRoot
# session. Background children of a short-lived PRoot session do not survive it.
if [ "${1:-}" = "--serve" ]; then
  exec node "$entry" serve --host 127.0.0.1 --port "$port"
fi
if [ "${1:-}" = "--watch" ]; then
  exec node /usr/local/lib/pixel-agent/pixel-t3-watch.mjs "$entry"
fi
exec 9>"$HOME/.local/state/t3-code-start.lock"
flock -w 60 9 || { echo 'T3 startup is already busy. Try again in a minute.' >&2; exit 1; }
ready() { curl --noproxy '*' --connect-timeout 1 --max-time 2 -fsS "http://127.0.0.1:$port" >/dev/null 2>&1; }
if ! ready; then
  if [ "${1:-}" = "--pair-only" ]; then
    echo 'The managed T3 server stopped before pairing.' >&2
    exit 1
  fi
  nohup node "$entry" serve --host 127.0.0.1 --port "$port" </dev/null >"$log" 2>&1 9>&- &
  for _ in $(seq 1 45); do
    ready && break
    sleep 1
  done
fi
if ! ready; then
  echo 'T3 Code did not become ready; see ~/.local/state/t3-code.log.' >&2
  exit 1
fi
# Pairing links expire after five minutes and can only be used once.
# Mint a fresh link for each launch, including launches in Android's browser.
umask 077
pair_log="$HOME/.local/state/t3-pair.log"
timeout 15 node "$entry" pair --label 'Pixel shortcut' >"$pair_log" 2>&1
url="$(sed -n 's/^Pairing URL: //p' "$pair_log" | tail -n 1)"
[ -n "$url" ] || { echo 'Could not create a T3 pairing link.' >&2; exit 1; }
printf '%s\n' "$url"
