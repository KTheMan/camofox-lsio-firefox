#!/usr/bin/env bash
set -euo pipefail
mkdir -p /root/.cache/camoufox
if [ ! -f /root/.cache/camoufox/version.json ] && [ -d /config/.cache/camoufox ] && [ -f /config/.cache/camoufox/version.json ]; then
  cp -a /config/.cache/camoufox/. /root/.cache/camoufox/
fi
cd /opt/camofox-browser
exec node server.js
