# syntax=docker/dockerfile:1
# check=skip=InvalidDefaultArgInFrom

ARG SELKIES_IMAGE
FROM ${SELKIES_IMAGE}

ARG SELKIES_IMAGE
ARG BUILD_DATE
ARG VERSION
ARG NODE_MAJOR=22

LABEL org.opencontainers.image.title="Camofox LSIO Firefox Overlay" \
      org.opencontainers.image.description="LSIO Selkies base with upstream Camofox browser server" \
      org.opencontainers.image.source="https://github.com/KTheMan/camofox-lsio-firefox" \
      org.opencontainers.image.base.name="${SELKIES_IMAGE}" \
      org.opencontainers.image.version="${VERSION}" \
      build_version="Camofox LSIO overlay version:- ${VERSION} Build-date:- ${BUILD_DATE}" \
      maintainer="KTheMan"

ENV TITLE=Camofox \
    PIXELFLUX_WAYLAND=false \
    NODE_ENV=production \
    CAMOFOX_INTERACTIVE=desktop \
    CAMOFOX_PORT=9377 \
    HOME=/config \
    XDG_CACHE_HOME=/opt/camofox-cache \
    CAMOUFOX_INSTALL_DIR=/opt/camofox-cache/camoufox

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      git \
      gnupg \
      libdbus-glib-1-2 \
      xz-utils \
      python3-minimal \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash - \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/camofox-browser
COPY pins/camofox-ref /opt/camofox-ref
RUN --mount=type=cache,target=/config/.npm,sharing=locked set -eux; \
    ref=$(cat /opt/camofox-ref); \
    git init -q; \
    git fetch --depth 1 https://github.com/jo-inc/camofox-browser.git "$ref"; \
    git checkout --quiet --detach FETCH_HEAD; \
    test "$(git rev-parse HEAD)" = "$ref"; \
    apt-get update; \
    apt-get install -y --no-install-recommends build-essential python3; \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm ci --omit=dev --fetch-retries=4; \
    test -s "$XDG_CACHE_HOME/camoufox/version.json"; \
    test -x "$XDG_CACHE_HOME/camoufox/camoufox-bin"; \
    apt-get purge -y --auto-remove build-essential; \
    rm -rf /var/lib/apt/lists/*

COPY --chmod=0755 docker/entrypoint.sh /usr/local/bin/entrypoint.sh

EXPOSE 9377
VOLUME /config

CMD ["/usr/local/bin/entrypoint.sh"]
