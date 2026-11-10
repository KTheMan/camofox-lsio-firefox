ARG BASE_IMAGE=camofox-bitwarden:2026.10.2-4ad5a5b931ed
FROM ${BASE_IMAGE}
USER root
COPY --chown=911:911 release/assets/policies.json release/assets/bitwarden_password_manager-2026.7.0.xpi /opt/camofox-cache/camoufox/distribution/
RUN chown -R 911:911 /opt/camofox-cache \
 && chmod 444 /opt/camofox-cache/camoufox/distribution/policies.json /opt/camofox-cache/camoufox/distribution/bitwarden_password_manager-2026.7.0.xpi
COPY --chown=911:911 . /opt/camofox-browser/
COPY --chown=911:911 release/desktop/ /opt/camofox-desktop/
COPY release/desktop/nginx.conf /defaults/default.conf
COPY release/desktop/startwm.sh /defaults/startwm.sh
COPY release/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 444 /opt/camofox-browser/plugins/bitwarden-unlock/passkey-blacklist.json \
 && python3 /opt/camofox-browser/release/patch-firefox-customization.py \
 && node /opt/camofox-browser/release/patch-playwright-snapshot.cjs /opt/camofox-browser/node_modules/playwright-core \
 && chmod 755 /usr/local/bin/entrypoint.sh /opt/camofox-desktop/*.sh
ENV CAMOFOX_REQUIRE_PRIVATE_SNAPSHOTS=true
ARG CANDIDATE_SOURCE_SHA256
LABEL org.opencontainers.image.version="1.18.1-homelab.4" \
      io.knnygrdn.camofox.source-sha256="${CANDIDATE_SOURCE_SHA256}" \
      org.opencontainers.image.description="Isolated homelab candidate: authenticated control, private snapshots, human handoff and local vault broker" \
      com.centurylinklabs.watchtower.enable="false"
