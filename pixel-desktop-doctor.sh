#!/data/data/com.termux/files/usr/bin/bash
set -u

failed=0
check_command() {
  if command -v "$1" >/dev/null 2>&1; then
    printf 'OK    %s\n' "$2"
  else
    printf 'FAIL  %s\n' "$2"
    failed=1
  fi
}

check_command termux-x11 'Termux:X11 companion'
check_command proot-distro 'PRoot Distro'
check_command pulseaudio 'PulseAudio'
check_command termux-wake-lock 'Termux:API'

if /system/bin/pm path com.termux.x11 >/dev/null 2>&1; then
  echo 'OK    Termux:X11 Android app'
else
  echo 'FAIL  Termux:X11 Android app'
  failed=1
fi

if proot-distro login debian -- /bin/true >/dev/null 2>&1; then
  echo 'OK    Debian root filesystem'
else
  echo 'FAIL  Debian root filesystem'
  failed=1
fi

if proot-distro login debian --user pixel -- /bin/bash -lc \
  'command -v xfce4-session && command -v zen && command -v pixel-t3 && command -v orca-slicer-pixel' \
  >/dev/null 2>&1; then
  echo 'OK    XFCE, Zen, T3 Code, and OrcaSlicer launchers'
else
  echo 'FAIL  One or more Linux applications are missing'
  failed=1
fi

free_gb="$(df -Pk "$HOME" | awk 'NR == 2 {printf "%.1f", $4 / 1048576}')"
echo "INFO  ${free_gb} GB free"
exit "$failed"
