# syntax=docker/dockerfile:1

FROM ghcr.io/linuxserver/baseimage-selkies:ubunturesolute

ARG BUILD_DATE
ARG VERSION
ARG CAMOFOX_REPO=https://github.com/jo-inc/camofox-browser.git
ARG CAMOFOX_REF=master
ARG NODE_MAJOR=22

LABEL build_version="Camofox LSIO overlay version:- ${VERSION} Build-date:- ${BUILD_DATE}"
LABEL maintainer="KTheMan"

ENV TITLE=Camofox     PIXELFLUX_WAYLAND=true     NODE_ENV=production

RUN apt-get update && apt-get install -y --no-install-recommends       ca-certificates       curl       git       gnupg       xz-utils     && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash -     && apt-get update     && apt-get install -y --no-install-recommends nodejs     && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN git clone --depth 1 --branch "${CAMOFOX_REF}" "${CAMOFOX_REPO}" camofox-browser     && cd camofox-browser     && npm install --production     && npm run build

# The upstream LSIO image already provides the Selkies desktop stack.
# We launch the Camofox server inside that environment rather than stock Firefox.
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 9377
VOLUME /config

CMD ["/usr/local/bin/entrypoint.sh"]
