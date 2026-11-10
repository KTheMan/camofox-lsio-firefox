# Native extension route

This release drives the actual Firefox toolbar popup through a fixed DOM bridge
in the pinned browser's Marionette actor. An ordinary `popup/index.html` tab is
not equivalent. No generic extension evaluator/selector API is exposed to agents.

The official signed Bitwarden 2026.7.0 package SHA256 is
`11836eb9d2abc9914bb337b57e20c5a09cf44f24fa572f7e886384fd350a5112`.
The driver requires its addon ID, version, active state and signedState 2, and checks
the packaged bytes. Enterprise policy is the only installer. Readiness waits are
bounded and never install/reinstall an extension. The original unsigned test asset
is not accepted. Retaining 26.7 follows validated client behavior, not an inference
from Vaultwarden's advertised Bitwarden compatibility version.

Before master entry, validate the complete managed environment and exact current
account label or broker-entered email stage. Fill only pinned master-password
controls. Structural `/2fa` / app-two-factor-auth screens stop before master fill,
including password-shaped YubiKey inputs. Cleanup clears only master fields.
Never retry a submit after an uncertain click; partial fill and cleanup failures
are failures. Status polling during protected 2FA does not refocus or dismiss UI.

A default master-password lock asks Bitwarden to reload its process, which waits
for all its popups to close. The driver records weak references to the current
policy/background context, sends one lock action, closes its own toolbar, waits
for an observed active signed/running replacement and then opens once to verify
locked state. It does not invoke reload directly or retain old key-bearing contexts.
PIN/biometric no-reload modes are not accepted; no transition returns lock_failed.

The Firefox null guard fixes an observed customization serializer crash on null
values. It preserves JSON null semantics; the build hash-gates both source/archive
states, preserves ZIP entry metadata and verifies every other entry unchanged.
See firefox-customization-nullguard.json for the exact pinned patch manifest.

After a completed extension reload, old website content-script contexts can be
stale. The passing prototype used unlock, fresh ordinary RP navigation, then its
next credential request. Never reload a pending Fido prompt: its handshake is
one-shot. Preserve unfinished human/CAPTCHA work and arrange a handoff rather
than automatically navigating it away.

The isolated prototype used an internal Docker network, generated test CA,
disposable Vaultwarden account, actual signed extension and HTTPS RP. Two native
unlock/lock cycles and provider registration/assertion passed. The RP verified
challenge, origin, RP hash, credential ID, ES256 signature, UP, user handle and
counter; UV was true for a preferred-verification request. No private passkey was
exported or virtual authenticator used. Sealed-image acceptance is recorded in
its separate release manifest; Google and real-account sign-in are not claimed.

The pending-prompt URL/frame parsing contract has focused tests. The trusted
in-process Playwright native frame ID is
`page._connection.toImpl(page.mainFrame())._id`; client Frame._id is undefined.
The native sender tab/session/origin must match the exact owned page. The fixture
approval harness is not a public production API. Default production approval is
human interaction in Bitwarden's prompt; HTTP/MCP expose only status, opaque
unlock request/polling, cancellation and verified lock.
