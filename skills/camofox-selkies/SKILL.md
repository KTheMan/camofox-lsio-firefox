---
name: camofox-selkies
description: Build, inspect, test, and deploy the Camofox browser on the LSIO Selkies desktop, including its native Bitwarden extension broker and human handoff.
---

Use the repository's pinned Camofox commit and LSIO image digest. `pins/camofox-ref`
and `pins/selkies-image` update independently; a published image is not automatically
a deployed image. Confirm the running immutable image, Compose inputs, bind mounts,
and profile volume before modifying a deployment. Baked files can be shadowed by
mounts.

The Camofox API listens on container 9377; Selkies HTTP is container 3000. Keep the
API private and authenticate the desktop proxy and WebSocket path. Newer Selkies
uses `/api/websockets`; older versions use `/websockets`. Read the bundled dashboard
or smoke-test both rather than assuming a path. The browser and desktop must share
the same X11 display (`PIXELFLUX_WAYLAND=false`, `CAMOFOX_INTERACTIVE=desktop`).

For build changes run `scripts/build-image.sh` and `scripts/smoke-image.sh` against
an isolated candidate. These validate the ordinary LSIO baseline. Rebuilding a custom native
release requires the archived `release/Dockerfile` and the separately versioned host
packages described in the extension reference. Runtime tests require a uniquely named container/network,
a fresh profile, bounded resources, and no live profile or credential mounts. Do
not attach one profile to two running Firefox processes. Use disposable credentials
and controlled HTTPS fixtures for extension/passkey testing.

For native Bitwarden control, read [the extension reference](references/bitwarden.md).
Keep credentials out of model tools, HTTP payloads, screenshots, diagnostics, and
command arguments. The normal extension UI performs vault unlock and passkey
cryptography; the driver does not export private keys or call internal SDK methods.
The reference records the exact deployed version. R4 adds user-authorized automatic
passkey sign-in approval under an administrator blacklist that starts empty.
Unlock before starting the website request, approve through the fixed native tool,
verify website login, then explicitly lock. Registration and ambiguous prompts
require separate handling. Never treat a delivered approval as proof of login.

Promote each completed, tested and reviewed aspect when the current user request
authorizes rollout. Preserve rollback image/configuration, stage with a fresh
profile, then verify API, visible desktop, stream, and relevant broker behavior.
Do not promote a passing subtest as proof that an unfinished ceremony works.
Update this skill/reference and the deployment runbook with the actual result.
A failed or uncertain relock must continue to block browser automation.

Use the environment's established connection method. Kenny's homelab uses the
separate `homelab-connect` skill; connection metadata does not authorize unrelated
service or credential changes.
