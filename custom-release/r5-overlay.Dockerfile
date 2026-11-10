# The build wrapper passes the exact locally verified deployed R4 image ID.
ARG BASE_IMAGE=sha256:4ce65b65ed0827589023ed806cdd9db9a059943ce8bb1c0112fce3003041a29e
FROM ${BASE_IMAGE}
ARG CANDIDATE_SOURCE_SHA256
LABEL org.opencontainers.image.version="1.18.1-homelab.5"
LABEL io.knnygrdn.camofox.source-sha256="${CANDIDATE_SOURCE_SHA256}"

WORKDIR /opt/camofox-browser
COPY --chown=911:911 server.js /opt/camofox-browser/server.js
COPY --chown=911:911 package.json /opt/camofox-browser/package.json
COPY --chown=911:911 lib/evaluate-timeout-recovery.js /opt/camofox-browser/lib/evaluate-timeout-recovery.js
