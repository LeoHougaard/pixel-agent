#!/bin/bash
# Debian-side (user pixel): thin CLI over the Termux Pixel Phone bridge.
# Used by OpenCode custom tools and for manual checks from T3 terminal.
#   pixel-phone health
#   pixel-phone run [--priv] [--timeout 60] -- <command>
#   pixel-phone screenshot [--out path] [--width-only]
#   pixel-phone tap <x> <y> | swipe <sx> <sy> <ex> <ey> [ms] | key <NAME> | type [--enter] <text...> | open <app> | apps
# Coordinates default to 0-1000 normalized; pass --px for absolute pixels.
set -euo pipefail
BASE="${PIXEL_PHONE_URL:-http://127.0.0.1:18080}"
TOKEN_FILE="${PIXEL_PHONE_TOKEN_FILE:-$HOME/.config/pixel-phone/bridge-token}"
token() {
  if [ -n "${PIXEL_PHONE_TOKEN:-}" ]; then printf '%s' "$PIXEL_PHONE_TOKEN"; return; fi
  [ -f "$TOKEN_FILE" ] || { echo "Missing bridge token at $TOKEN_FILE. Run pixel-phone-bridge in Termux first." >&2; exit 1; }
  tr -d '\r\n[:space:]' < "$TOKEN_FILE"
}
auth=( -H "Authorization: Bearer $(token)" )
cmd="${1:-help}"; shift || true
case "$cmd" in
  health) curl -fsS --max-time 5 "${auth[@]}" "$BASE/health"; echo;;
  run)
    priv=false; timeout=60
    while [ $# -gt 0 ]; do case "$1" in
      --priv) priv=true; shift;; --timeout) timeout="$2"; shift 2;;
      --) shift; break;; *) break;;
    esac; done
    payload="$(python3 -c 'import json,sys; print(json.dumps({"command": sys.argv[1], "privileged": sys.argv[2]=="true", "timeout": int(sys.argv[3])}))' "$*" "$priv" "$timeout")"
    curl -fsS --max-time "$((timeout + 10))" "${auth[@]}" -H 'Content-Type: application/json' -d "$payload" "$BASE/run"; echo;;
  screenshot)
    out=""; width_only=false
    while [ $# -gt 0 ]; do case "$1" in
      --out) out="$2"; shift 2;; --width-only) width_only=true; shift;; *) break;; esac; done
    tmp="${out:-$(mktemp /tmp/pixel-screen-XXXXXX.png)}"
    curl -fsS --max-time 30 "${auth[@]}" -o "$tmp" "$BASE/screenshot"
    if $width_only; then printf '%s\n' "$tmp";
    else dim="$(python3 -c 'import struct,sys; d=open(sys.argv[1],"rb").read(); print("%dx%d" % struct.unpack(">II", d[16:24]))' "$tmp")"
      echo "{\"path\": \"$tmp\", \"size\": \"$dim\"}"; fi;;
  apps) curl -fsS --max-time 30 "${auth[@]}" "$BASE/apps"; echo;;
  open) payload="$(python3 -c 'import json,sys; print(json.dumps({"app": sys.argv[1]}))' "$*")"
    curl -fsS --max-time 40 "${auth[@]}" -H 'Content-Type: application/json' -d "$payload" "$BASE/open_app"; echo;;
  tap|swipe|key|type)
    norm=true; [ "${1:-}" = "--px" ] && { norm=false; shift; }
    payload="$(python3 - "$cmd" "$norm" "$@" <<'PY'
import json,sys
cmd, norm, rest = sys.argv[1], sys.argv[2]=="true", sys.argv[3:]
if cmd=="tap": print(json.dumps({"x": float(rest[0]), "y": float(rest[1]), "normalized": norm}))
elif cmd=="swipe": print(json.dumps({"sx": float(rest[0]), "sy": float(rest[1]), "ex": float(rest[2]), "ey": float(rest[3]), "duration_ms": int(rest[4]) if len(rest)>4 else 500, "normalized": norm}))
elif cmd=="key": print(json.dumps({"key": " ".join(rest)}))
elif cmd=="type":
  enter = rest[:1]==["--enter"];  r=rest[1:] if enter else rest
  print(json.dumps({"text": " ".join(r), "press_enter": enter}))
PY
)"
    endpoint="$cmd"; [ "$cmd" = "tap" ] && endpoint="tap"; [ "$cmd" = "type" ] && endpoint="type"
    curl -fsS --max-time 40 "${auth[@]}" -H 'Content-Type: application/json' -d "$payload" "$BASE/$endpoint"; echo;;
  *) cat >&2 <<'EOF'
usage: pixel-phone health | run [--priv] [--timeout N] -- <cmd> | screenshot [--out p] | apps | open <app> | tap [--px] x y | swipe [--px] sx sy ex ey [ms] | key <NAME> | type [--enter] <text>
EOF
    exit 1;;
esac
