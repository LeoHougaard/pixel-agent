#!/bin/bash
set -e
app="$HOME/.local/opt/orcaslicer/squashfs-root/AppRun"
if [ ! -x "$app" ]; then
  echo 'OrcaSlicer is not installed. Run install-orcaslicer.' >&2
  exit 1
fi
export WEBKIT_DISABLE_DMABUF_RENDERER=1
export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
exec "$app" "$@"
