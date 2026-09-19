#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

config_dir="$HOME/.config/pixel-agent"
mkdir -p "$config_dir"
printf 'Paste your Gemini API key (input stays hidden).\n'
read -r -s -p 'GEMINI_API_KEY: ' api_key
printf '\n'
if [ -z "$api_key" ]; then
  echo 'No key saved.'
  exit 1
fi

umask 077
printf 'GEMINI_API_KEY=%s\n' "$api_key" > "$config_dir/env"
chmod 600 "$config_dir/env"
unset api_key
echo 'Key saved in private Termux storage. Run: pixel-agent --doctor'
