# syntax=docker/dockerfile:1

FROM ghcr.io/linuxserver/baseimage-selkies:ubunturesolute

ARG BUILD_DATE
ARG VERSION
ARG NODE_MAJOR=22
ARG CAMOFOX_REPO=https://github.com/jo-inc/camofox-browser.git
ARG CAMOFOX_REF=master

LABEL org.opencontainers.image.title="Camofox LSIO Firefox Overlay" \
      org.opencontainers.image.description="LSIO Selkies base with upstream Camofox browser server" \
      org.opencontainers.image.source="https://github.com/KTheMan/camofox-lsio-firefox" \
      org.opencontainers.image.version="${VERSION}" \
      build_version="Camofox LSIO overlay version:- ${VERSION} Build-date:- ${BUILD_DATE}" \
      maintainer="KTheMan"

ENV TITLE=Camofox \
    PIXELFLUX_WAYLAND=true \
    NODE_ENV=production \
    CAMOFOX_PORT=9377 \
    CAMOFOX_REPO=${CAMOFOX_REPO} \
    CAMOFOX_REF=${CAMOFOX_REF} \
    HOME=/config

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      git \
      gnupg \
      xz-utils \
      python3-minimal \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash - \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN git clone --depth 1 --branch "${CAMOFOX_REF}" "${CAMOFOX_REPO}" camofox-browser
WORKDIR /opt/camofox-browser
RUN npm ci

RUN mkdir -p /config/.cache/camoufox
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 9377
VOLUME /config

CMD ["/usr/local/bin/entrypoint.sh"]
