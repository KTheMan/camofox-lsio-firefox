# Camofox on LSIO Firefox / Selkies

A public, auto-updating container overlay that replaces the stock LSIO Firefox app with the Camofox browser server, while retaining the LSIO Selkies remote-access stack.

## Upstreams

- LSIO Firefox: https://github.com/linuxserver/docker-firefox
- Camofox browser server: https://github.com/jo-inc/camofox-browser

## Goals

- Keep the LSIO remote desktop ergonomics
- Use Camofox as the browser runtime
- Reuse the existing Firefox profile/cookie volume when possible
- Build and publish automatically when either upstream changes

## Status

This repo is scaffolded for the swap architecture and CI/CD synchronization workflow.

## License

MIT
