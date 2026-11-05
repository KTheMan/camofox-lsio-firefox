#!/usr/bin/env bash
set -euo pipefail

# Openbox keeps this card below normal windows. It uses the same manual
# launcher as the desktop menu and does not prewarm an automation session.
exec 9>/tmp/camofox-desktop-launcher.lock
flock -n 9 || exit 0

while xset q >/dev/null 2>&1; do
  result=0
  xmessage -name camofox-launcher -center -geometry 520x145 -fn 10x20 \
    -bg '#263443' -fg '#f4f7fb' -xrm '*Text.scrollVertical: never' \
    -xrm '*Command.background: #285991' -buttons 'Open Camoufox:10' \
    $'Camofox shared browser\n\nOpen a manual browser session here.\nAgent tabs appear when a job opens one.' 9>&- || result=$?
  if [[ $result == 10 ]]; then
    /bin/bash /opt/camofox-desktop/open-browser.sh 9>&- || true
  else
    sleep 1
  fi
done
