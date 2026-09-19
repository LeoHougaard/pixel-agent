#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$HOME/.local/share/pixel-agent"
BIN_DIR="$HOME/.local/bin"
CONFIG_DIR="$HOME/.config/pixel-agent"
echo "Installing Pixel Agent dependencies..."
pkg update -y
pkg install -y python termux-api android-tools curl proot-distro

mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$CONFIG_DIR" "$HOME/.shortcuts"
cp "$SOURCE_DIR/pixel_agent.py" "$INSTALL_DIR/pixel_agent.py"
cp "$SOURCE_DIR/pixel-phone-bridge.py" "$INSTALL_DIR/pixel-phone-bridge.py"
cp "$SOURCE_DIR/pixel-phone-bridge-start.sh" "$BIN_DIR/pixel-phone-bridge"
chmod 700 "$BIN_DIR/pixel-phone-bridge"
cp "$SOURCE_DIR/pixel-agent-key.sh" "$BIN_DIR/pixel-agent-key"
chmod 700 "$BIN_DIR/pixel-agent-key"

cat > "$BIN_DIR/pixel-agent" <<EOF
#!/data/data/com.termux/files/usr/bin/sh
export RISH_APPLICATION_ID=com.termux
exec python "$INSTALL_DIR/pixel_agent.py" "\$@"
EOF
chmod 700 "$BIN_DIR/pixel-agent"

cat > "$BIN_DIR/pixel-voice" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
prompt="$(termux-speech-to-text | tail -n 1)"
if [ -z "$prompt" ]; then
  echo "No speech recognized."
  exit 1
fi
echo "You: $prompt"
answer="$(pixel-agent "$prompt")"
echo "$answer"
printf '%s' "$answer" | termux-tts-speak
EOF
chmod 700 "$BIN_DIR/pixel-voice"

rm -f "$HOME/.shortcuts/Pixel Agent Voice"
cat > "$HOME/.shortcuts/Pixel Agent" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
export PATH="$BIN_DIR:\$PATH"
export RISH_APPLICATION_ID=com.termux
(sleep 1; rish -c 'input tap 540 650' >/dev/null 2>&1) &
clear
exec pixel-agent
EOF
chmod 700 "$HOME/.shortcuts/Pixel Agent"

if [ ! -s "$CONFIG_DIR/env" ]; then
  "$BIN_DIR/pixel-agent-key" || true
fi

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$HOME/.bashrc" ;;
esac

if ! grep -Fq 'export RISH_APPLICATION_ID=com.termux' "$HOME/.bashrc" 2>/dev/null; then
  printf 'export RISH_APPLICATION_ID=com.termux\n' >> "$HOME/.bashrc"
fi

echo
echo "Installed. Open a new Termux session, then run:"
echo "  pixel-agent --doctor   # legacy Gemini agent (kept as fallback)"
echo "  pixel-phone-bridge     # start phone bridge for T3 + OpenCode"
echo "  pixel-agent"
echo
echo "T3 + OpenCode path: run pixel-phone-bridge, then open the T3 Code Mobile"
echo "widget. In Debian once: opencode auth login (OpenCode Zen) and pick"
echo "opencode/muse-spark-1.3-contributor-free."
echo
echo "If Android bridge is unavailable, start Shizuku and copy its rish files"
echo "into $BIN_DIR, or pair Termux adb through Android Wireless debugging."
