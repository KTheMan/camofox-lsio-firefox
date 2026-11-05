#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

selkies_image=$(cat pins/selkies-image)
camofox_ref=$(cat pins/camofox-ref)
if [[ ! $selkies_image =~ ^ghcr\.io/linuxserver/baseimage-selkies:ubunturesolute@sha256:[0-9a-f]{64}$ ]]; then
  printf 'Invalid LSIO Selkies image pin.\n' >&2
  exit 1
fi
if [[ ! $camofox_ref =~ ^[0-9a-f]{40}$ ]]; then
  printf 'Invalid Camofox commit pin.\n' >&2
  exit 1
fi

exec docker build "$@" --build-arg "SELKIES_IMAGE=$selkies_image" .
