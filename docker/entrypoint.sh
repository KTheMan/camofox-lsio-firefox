#!/usr/bin/with-contenv bash
set -euo pipefail

chown -R abc:abc /opt/camofox-cache
if [[ $CAMOFOX_INTERACTIVE == desktop ]]; then
  # The upstream server prewarms its browser as soon as it starts.
  for attempt in {1..30}; do
    if s6-setuidgid abc xset q >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  if ! s6-setuidgid abc xset q >/dev/null 2>&1; then
    printf 'Camoufox could not connect to the Selkies X11 display %s.\n' "${DISPLAY:-<unset>}" >&2
    exit 1
  fi
fi

cd /opt/camofox-browser
exec s6-setuidgid abc node server.js
