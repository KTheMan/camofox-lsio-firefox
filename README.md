# Camofox on LSIO Firefox / Selkies

This repository builds a replacement for the LSIO Firefox container that keeps the Selkies-based desktop experience, but runs **Camofox** as the browser runtime.

## Why this exists

- preserve the LSIO/headed browser workflow
- avoid noVNC as the primary live-view path
- keep Firefox-style profile/cookie storage mounted in the same place
- synchronize automatically against both upstream projects

## Upstreams

- LSIO Firefox: https://github.com/linuxserver/docker-firefox
- Camofox browser server: https://github.com/jo-inc/camofox-browser

## How it works

- The image starts from `ghcr.io/linuxserver/baseimage-selkies`
- Camofox is built from the upstream repo during the image build
- The resulting container launches `node server.js` inside the Selkies desktop environment
- `/config` remains the persistent state volume

## Default ports

- `9377` — Camofox API/browser server

## Build and run

```bash
docker build -t camofox-lsio-firefox .
docker run --rm -p 9377:9377 -v /path/to/config:/config camofox-lsio-firefox
```

## Upstream sync policy

The repository keeps an `upstream-lock.json` file with the latest pinned SHAs from:

- `linuxserver/docker-firefox`
- `jo-inc/camofox-browser`

A scheduled GitHub Actions workflow checks both repos, updates the lock file when they change, and opens a PR with the new pins.

A second workflow builds the container and publishes images to GHCR on push.

## Notes

- Do **not** mount the same Firefox profile into two live browser processes at once.
- If you want to share cookies, mount the whole profile directory, not just `cookies.sqlite`.
- This repo is intentionally public so upstream sync changes are visible.
