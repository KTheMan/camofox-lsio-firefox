# syntax=docker/dockerfile:1

FROM node:22-bookworm-slim AS camofox-builder
ARG CAMOFOX_REPO=https://github.com/jo-inc/camofox-browser.git
ARG CAMOFOX_REF=master
WORKDIR /src
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates   && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch "${CAMOFOX_REF}" "${CAMOFOX_REPO}" /src/camofox-browser
WORKDIR /src/camofox-browser
RUN npm ci && npm run build

FROM ghcr.io/linuxserver/baseimage-selkies:ubunturesolute

ARG BUILD_DATE
ARG VERSION
ARG LSIO_FIREFOX_REPO=https://github.com/linuxserver/docker-firefox.git
ARG LSIO_FIREFOX_REF=master
ARG NODE_MAJOR=22
ARG CAMOFOX_REPO=https://github.com/jo-inc/camofox-browser.git
ARG CAMOFOX_REF=master

LABEL org.opencontainers.image.title="Camofox LSIO Firefox Overlay"       org.opencontainers.image.description="Selkies-based Firefox container replaced with Camofox"       org.opencontainers.image.source="https://github.com/KTheMan/camofox-lsio-firefox"       org.opencontainers.image.version="${VERSION}"       build_version="Camofox LSIO overlay version:- ${VERSION} Build-date:- ${BUILD_DATE}"       maintainer="KTheMan"

ENV TITLE=Camofox     PIXELFLUX_WAYLAND=true     NODE_ENV=production     CAMOFOX_PORT=9377     CAMOFOX_REPO=${CAMOFOX_REPO}     CAMOFOX_REF=${CAMOFOX_REF}     LSIO_FIREFOX_REPO=${LSIO_FIREFOX_REPO}     LSIO_FIREFOX_REF=${LSIO_FIREFOX_REF}

RUN apt-get update && apt-get install -y --no-install-recommends       ca-certificates       curl       git       gnupg       xz-utils     && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash -     && apt-get update     && apt-get install -y --no-install-recommends nodejs     && rm -rf /var/lib/apt/lists/*

# Keep the LSIO Selkies stack, but swap the browser application itself for Camofox.
COPY --from=camofox-builder /src/camofox-browser /opt/camofox-browser
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 9377
VOLUME /config

CMD ["/usr/local/bin/entrypoint.sh"]
