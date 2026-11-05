# Camofox on LSIO Firefox / Selkies

This repository builds a replacement for the LSIO Firefox container that keeps the Selkies-based desktop experience, but runs **Camofox** as the browser runtime.

## Why this exists

- preserve the LSIO/headed browser workflow
- avoid noVNC as the primary live-view path
- keep Firefox-style profile/cookie storage mounted in the same place
- synchronize automatically against both upstream projects

## Upstreams

- LSIO Selkies desktop base: https://github.com/linuxserver/docker-baseimage-selkies
- Camofox browser server: https://github.com/jo-inc/camofox-browser

## How it works

- The image uses the exact LSIO manifest in `pins/selkies-image` and the exact Camofox commit in `pins/camofox-ref`.
- Camofox runs as the desktop user on the Selkies X11 display using upstream's `CAMOFOX_INTERACTIVE=desktop` setting.
- API clients can create tabs even when nobody is connected to the Selkies desktop.
- `/config` remains the persistent state volume

## Default ports

- `3000` — Selkies desktop HTTP origin for a local connection or authenticated TLS proxy
- `9377` — Camofox API/browser server for local automation

## Build and run

```bash
bash scripts/build-image.sh -t camofox-lsio-firefox:candidate
bash scripts/smoke-image.sh camofox-lsio-firefox:candidate
```

The CI check uses the [Selkies desktop integration files](deploy/homelab/desktop).

## Upstream sync policy

The daily sync resolves the LSIO `ubunturesolute` image digest and the newest
stable Camofox `vX.Y.Z` tag separately. It opens one PR per changed pin. Each PR
touches only its own file, so the two updates can merge independently.

CI builds the pinned pair, opens and snapshots a headed browser tab with no
viewer, checks that its window is on the Selkies X11 display, and verifies the
WebSocket upgrade against the deployment's nginx config. The publish workflow
repeats those checks before pushing an image to GHCR. Deploy an immutable image
tag to staging before changing the live stack. Publishing alone does not deploy.

Enable **Allow GitHub Actions to create and approve pull requests** in the
repository's Actions settings for the default workflow token. The sync dispatches
CI on each updated branch explicitly with this token. The separate PR event may
still display GitHub's approval prompt for bot-created pull requests. If the
setting stays disabled, supply a repository-scoped fine-grained PAT with
contents and pull requests write access as `UPSTREAM_SYNC_TOKEN`. With that
token, GitHub starts CI through the normal PR event.

The initial LSIO pin matches the deployed browser-first base. The nginx overlay
supports the original `/websockets` route and the newer `/api/websockets` route.
CI reads the bundled dashboard to select the route to verify.

## Notes

- Do **not** mount the same Firefox profile into two live browser processes at once.
- If you want to share cookies, mount the whole profile directory, not just `cookies.sqlite`.
- This repo is intentionally public so upstream sync changes are visible.
