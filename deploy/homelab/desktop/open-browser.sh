#!/usr/bin/env bash
set -euo pipefail

# The API starts Camoufox on demand and manages this window like any other tab.
# No startup tab is created and the manual profile is separate from agent profiles.
if ! curl -fsS --max-time 45 -X POST http://127.0.0.1:9377/tabs \
  -H 'Content-Type: application/json' \
  --data '{"userId":"selkies","sessionKey":"desktop"}' >/dev/null; then
  xmessage -center 'Camoufox could not open. Wait a few seconds and try again.'
  exit 1
fi
