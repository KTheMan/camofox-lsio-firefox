#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

case "${1:-}" in
  selkies)
    path=pins/selkies-image
    source=ghcr.io/linuxserver/baseimage-selkies:ubunturesolute
    digest=$(docker buildx imagetools inspect "$source" --format '{{.Manifest.Digest}}')
    [[ $digest =~ ^sha256:[0-9a-f]{64}$ ]]
    value="$source@$digest"
    ;;
  camofox)
    path=pins/camofox-ref
    source=https://github.com/jo-inc/camofox-browser.git
    tags=$(git ls-remote --tags --sort=-version:refname "$source" 'refs/tags/v*')
    tag=$(sed -nE 's#^[0-9a-f]+[[:space:]]refs/tags/(v[0-9]+\.[0-9]+\.[0-9]+)$#\1#p' <<<"$tags" | sed -n '1p')
    [[ -n $tag ]]
    # Annotated tags list the tag object before the peeled commit.
    value=$(awk -v ref="refs/tags/$tag" '$2 == ref || $2 == ref "^{}" {commit=$1} END {print commit}' <<<"$(git ls-remote "$source" "refs/tags/$tag" "refs/tags/$tag^{}")")
    [[ $value =~ ^[0-9a-f]{40}$ ]]
    ;;
  *)
    printf 'Usage: bash scripts/update-upstream.sh {selkies|camofox}\n' >&2
    exit 2
    ;;
esac

if [[ $(cat "$path") != "$value" ]]; then
  printf '%s\n' "$value" > "$path"
fi
