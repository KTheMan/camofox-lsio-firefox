# Homelab R5 source overlay

This directory records the custom server changes used by the deployed
`1.18.1-homelab.5` release. It is separate from this repository's ordinary
LSIO image build. Apply the patch to `jo-inc/camofox-browser` commit
`39c82094013480b373df6600d44c7f036f58356e` on a Linux checkout:

```sh
git clone https://github.com/jo-inc/camofox-browser.git
cd camofox-browser
git checkout --detach 39c82094013480b373df6600d44c7f036f58356e
git apply --check /path/to/camofox-1.18.1-homelab-r5.patch
git apply /path/to/camofox-1.18.1-homelab-r5.patch
```

The patch includes the R4 native broker, passkey controls, access and human
handoff changes, plus R5 evaluate-timeout recovery and its unit tests. The R5
`server.js`, `package.json`, and `lib/evaluate-timeout-recovery.js` were checked
against the deployed image. Instance-specific account and vault defaults have
been replaced with examples; configure them explicitly before use. Do not use
example names or endpoints in production.

## Build limitations

`r4-release/` retains release scripts and templates, and
`r5-overlay.Dockerfile` shows the actual R5 overlay. These are historical build
inputs, not a self-contained reproducible image: the R4 Dockerfile requires the
older local base image, the signed Bitwarden XPI, site-specific Firefox policy,
and separately packaged native Python dependencies. The R5 Dockerfile then
requires the exact R4f image. Do not assume the base image remains available.
The XPI and bundled third-party binaries are intentionally not committed.
Provision the signed Firefox extension from its official publisher and verify
its SHA-256 (`11836eb9d2abc9914bb337b57e20c5a09cf44f24fa572f7e886384fd350a5112`);
construct and validate a site-specific policy, and supply independently verified
native dependencies. The host bridge and Hermes adapter are separately versioned.

The accepted exact source archives are recorded by SHA-256 for provenance:

- R4f source: `7ea1c7deff9749ce609908414b9418d8971afe7c7206f885b9a06544f796437a`
- R5 overlay: `fa924bb4244493e91f7ca3702a009baebc3efa8651b4348e90d902602f34ebc3`
- Deployed R5 image: `sha256:b3466ab2c04b7aa7127dbe8eb22e57e79d0743c3d10564a1fe5412cc41bc4d55`

The public patch is sanitized and is not byte-identical to those private
archives. Test builds in an isolated container with a fresh profile; never
attach the live profile or credential material to a candidate. The upstream
Camofox Browser source and its license are obtained from its pinned repository.

The source lockfile retains the R4 package version because the deployed R5
overlay replaced `package.json` but did not replace the lockfile.
