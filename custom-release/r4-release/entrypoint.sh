#!/usr/bin/with-contenv bash
set -euo pipefail
# Cache ownership is fixed once in the image, rather than recursively chowned
# on every startup. User profile initialization remains the LSIO init's job.
if [[ ${CAMOFOX_INTERACTIVE:-off} == desktop ]]; then
  for attempt in {1..30}; do
    s6-setuidgid abc xset q >/dev/null 2>&1 && break
    sleep 1
  done
  s6-setuidgid abc xset q >/dev/null 2>&1 || exit 1
fi
cd /opt/camofox-browser
exec s6-setuidgid abc node server.js
