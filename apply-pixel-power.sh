#!/data/data/com.termux/files/usr/bin/bash
# Upgrade the existing installation without package upgrades or account changes.
set -euo pipefail
if [ "$(uname -o 2>/dev/null || true)" != Android ]; then
  echo 'Run this update in Termux on the Pixel.' >&2
  exit 1
fi
for dependency in python proot-distro termux-notification flock; do
  command -v "$dependency" >/dev/null || { echo "Missing $dependency. Run install-pixel-phone.sh first." >&2; exit 1; }
done
source_dir="$(cd "$(dirname "$0")" && pwd)"
bin_dir="$HOME/.local/bin"
install_dir="$HOME/.local/share/pixel-agent"
app_id="${PIXEL_APP_ID:-$(cat "$HOME/.config/pixel-agent/app-id" 2>/dev/null || echo dev.pixelagent.app)}"
case "$app_id" in *[!a-z0-9._]*) echo 'Invalid app ID' >&2; exit 1;; esac
mkdir -p "$HOME/.config/pixel-agent"
printf '%s\n' "$app_id" > "$HOME/.config/pixel-agent/app-id"
mkdir -p "$bin_dir" "$install_dir" "$HOME/.shortcuts" "$HOME/.shortcuts/tasks"
install -m 700 "$source_dir/pixel-t3-mobile.sh" "$bin_dir/pixel-t3-mobile"
install -m 600 "$source_dir/pixel-t3-runtime.py" "$install_dir/pixel-t3-runtime.py"
install -m 600 "$source_dir/pixel-app-control.py" "$install_dir/pixel-app-control.py"
install -m 600 "$source_dir/pixel-phone-bridge.py" "$install_dir/pixel-phone-bridge.py"
install -m 700 "$source_dir/pixel-phone-bridge-start.sh" "$bin_dir/pixel-phone-bridge"
install -m 700 "$source_dir/pixel-desktop-start.sh" "$bin_dir/pixel-desktop"
cat > "$bin_dir/pixel-t3-stop" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
export PATH="$bin_dir:\$PATH"
exec python "$install_dir/pixel-t3-runtime.py" stop
EOF
chmod 700 "$bin_dir/pixel-t3-stop"
cat > "$bin_dir/pixel-app-open" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
export PATH="$bin_dir:\$PATH"
if pm list packages "$app_id" 2>/dev/null | grep -q "$app_id"; then
  am start -n "$app_id/.MainActivity" >/dev/null 2>&1
else
  exec pixel-t3-mobile
fi
EOF
chmod 700 "$bin_dir/pixel-app-open"
cat > "$HOME/.shortcuts/T3 Code Mobile" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
export PATH="$bin_dir:\$PATH"
exec pixel-t3-mobile
EOF
cat > "$HOME/.shortcuts/Stop Pixel Agent" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
export PATH="$bin_dir:\$PATH"
exec pixel-t3-stop
EOF
chmod 700 "$HOME/.shortcuts/T3 Code Mobile" "$HOME/.shortcuts/Stop Pixel Agent"
cp "$HOME/.shortcuts/Stop Pixel Agent" "$HOME/.shortcuts/tasks/Stop Pixel Agent"
proot-distro login debian --shared-tmp --bind "$source_dir:/run/pixel-setup" -- /bin/bash -s -- /run/pixel-setup <<'GUEST'
set -eu
install -d /usr/local/lib/pixel-agent
install -m 644 "$1/pixel-t3-watch.mjs" /usr/local/lib/pixel-agent/pixel-t3-watch.mjs
install -m 755 "$1/pixel-t3-server.sh" /usr/local/bin/pixel-t3-server
install -m 644 "$1/pixel-desktop-control.py" /usr/local/lib/pixel-agent/pixel-desktop-control.py
install -m 644 "$1/pixel-projects.py" /usr/local/lib/pixel-agent/pixel-projects.py
install -m 644 "$1/pixel-project-register.mjs" /usr/local/lib/pixel-agent/pixel-project-register.mjs
install -m 644 "$1/pixel-checkpoint.py" /usr/local/lib/pixel-agent/pixel-checkpoint.py
install -d -o pixel -g pixel /home/pixel/.config/opencode/tools
for file in "$1"/pixel-opencode/tools/*.ts; do
  install -m 600 -o pixel -g pixel "$file" /home/pixel/.config/opencode/tools/
done
if [ ! -f /home/pixel/.config/opencode/AGENTS.md ]; then
  install -m 600 -o pixel -g pixel "$1/pixel-opencode/AGENTS.md" /home/pixel/.config/opencode/AGENTS.md
fi
python3 - <<'PY'
from pathlib import Path
import json,shutil
home=Path('/home/pixel'); config=home/'.config/opencode/opencode.json'
if config.exists():
    data=json.loads(config.read_text())
    old=data.get('instructions',[])
    new=[p for p in old if p!='~/.config/opencode/pixel-phone.md']
    if old!=new:
        backup=home/'.local/state/pixel-agent-before-v2';backup.mkdir(parents=True,exist_ok=True)
        shutil.copy2(config,backup/'opencode.json')
        if new:data['instructions']=new
        else:data.pop('instructions',None)
        config.write_text(json.dumps(data,indent=2)+'\n')
        old_file=home/'.config/opencode/pixel-phone.md'
        if old_file.exists():shutil.move(str(old_file),str(backup/'pixel-phone.md'))
parent=home/'projects/AGENTS.md'
old_text='# Phone projects (Pixel 10 Debian guest)\n\nProjects here are driven from T3 Code mobile with OpenCode + muse-spark-1.3-contributor-free.\nKeep diffs small, run tests before pushing, never commit secrets or bridge tokens.\nPhone actions go through pixel_run / pixel_ui_* / pixel_screenshot tools.\n'
if parent.exists() and parent.read_text()==old_text:
    backup=home/'.local/state/pixel-agent-before-v2';backup.mkdir(parents=True,exist_ok=True)
    shutil.move(str(parent),str(backup/'projects-AGENTS.md'))
PY
GUEST
echo 'Installed. Tap T3 Code Mobile to start. Add the Stop Pixel Agent widget shortcut.'
echo 'The Pixel Agent notification also has Stop agent, independent of the chat connection.'
