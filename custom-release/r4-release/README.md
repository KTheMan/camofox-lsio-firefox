# Camofox 1.18.1-homelab.3

Candidate image: `camofox-bitwarden:2026.11.09-native-r3`. Build and verify this
candidate separately before promotion. Building or publishing it does not change
the deployed stack. The deployment/acceptance manifest records the final image ID,
source digest, validation and promotion status.

The release contains authenticated browser control, private default snapshots,
explicit human-control leases, the canonical 21-tool MCP adapter, a Cloudflare
Access JWT verifier, and the native Bitwarden broker. The LSIO desktop and MCP
use the same browser process; website identities remain separate contexts.

## Native extension

The official signed Bitwarden 2026.7.0 package is pinned by SHA256, version,
addon ID, active state and signed state. Enterprise policy is the sole installer.
The managed self-hosted environment uses only its exact HTTPS `base` origin.
Read [EXTENSION-ROUTE.md](EXTENSION-ROUTE.md) for lifecycle and acceptance details.

Only opaque operation IDs/states cross HTTP/MCP. Master-password delivery uses
an owner-controlled local socket/stdin adapter. There is no master-password tool
argument, key-export API, internal crypto SDK call or autonomous passkey approval.
Human approval stays in the real provider prompt. Standard 2FA retains protected
control; unsupported or uncertain UI/relock states fail closed.

The native prototype passed two master-password unlock/lock cycles, real provider
registration and an RP-verified ES256 assertion with UP and UV. That result is
prototype evidence, not a substitute for the sealed-image acceptance manifest.
No real credentials or Google authentication are needed for synthetic validation.

## Build and isolated staging

Run `python3 release/build-candidate.py` on the Docker host with the verified local
base image available. The builder checks its full immutable ID and passes that ID
as BASE_IMAGE. It selects the legacy Docker builder because this local base has
a content-addressed image ID rather than a registry manifest digest; BuildKit
otherwise treats sha256 as a repository name. The build patches only the pinned Firefox customization serializer
with a null-preserving guard; every other archive entry is verified unchanged.
The signed Bitwarden XPI is never modified.

`release/compose.yaml` uses a separate candidate container, network and fresh
profile. Put an owner-restricted control key at `release/secrets/control-key`;
never commit or print it. Keep test swap disabled and resources bounded. The
browser API and desktop are published only on host loopback.

The public edge profile requires CAMOFOX_ACCESS_GATE=1, the exact CF_ACCESS_ISSUER
and CF_ACCESS_AUD for the application. Real issuer/AUD can be checked from public
Access application metadata without extracting a login cookie or JWT. The verifier
checks signature, issuer, audience and expiry. The direct LAN access policy is a
separate deployment choice; it is not authenticated by a public Access cookie.

Use the HTTPS or loopback API through the protected key-file settings. Set a stable
CAMOFOX_USER_ID and CAMOFOX_SESSION_KEY for MCP reconnects. The bundled
`release/hermes-camofox` adapter supports protected key files and human handoff;
install it through Hermes's supported idle plugin reload path when promoting.

## Owner bridge and deployment

`plugins/bitwarden-unlock/README.md` documents the fixed-destination host adapter,
request spool and systemd template. Installing/configuring the bridge does not
require fetching a master password. Do not activate it merely as a test against
real credentials. Synthetic stdin delivery is sufficient to validate the contract.

Before promotion, complete the sealed runtime checks for API authentication,
privacy, human handoff/reaper preservation, actual MCP transport, and native
broker login/relock with a disposable vault. Keep rollback image and configuration,
preserve the live profile volume, and inspect effective bind mounts so old plugins
or unsigned XPI files do not shadow the tested image. Never attach the live profile
to a second browser for testing. Update the associated skills with actual deployed
capabilities, not candidate-only promises.
