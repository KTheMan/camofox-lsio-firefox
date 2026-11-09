# Native Bitwarden route

## Sealed R3 acceptance

On November 9, 2026, the isolated sealed R3 candidate passed 34 general acceptance
checks and 19 short-idle lease checks. The idle run waited 65 seconds with no API
calls; cleanup reaped the unleased control session and retained the exact leased
human tab and session. The sealed candidate completed two opaque broker
unlock/status/lock cycles. One ES256 passkey assertion was verified by the RP with
UP and UV true.

The candidate used signed Bitwarden Firefox extension 2026.7.0, SHA256
`11836eb9d2abc9914bb337b57e20c5a09cf44f24fa572f7e886384fd350a5112`, and image
`sha256:cbd23bee1331e338d40fbc5fed96dbaa71cb02de7897839c30c01c1d2db130d3` from
custom source snapshot `ccb6fef25af7bb244651b25a6c2939ecc3366a8ec13599ceb1a7ae53d04117c9`.
There were no code overlays. The repository's ordinary LSIO build is a baseline
upstream overlay; it does not recreate this custom R3 release. The archived R3
source uses `release/Dockerfile` over immutable base image
`sha256:202ef6061a786c5afdc7413a70716d5a4266389169b23a1e328d62293d21f029`.
Keep the custom source and host packages with the release manifest when rebuilding.

Human approval in the real Bitwarden passkey prompt remains the default. There is
no autonomous passkey-approval API. Runtime 2FA completion was not exercised, and
Google login was not tested. PIN/biometric configurations that suppress the
extension reload are rejected fail-closed. Never reload a pending passkey prompt;
its ConnectResponse handshake is accepted once. If reload or relock is uncertain,
keep automation blocked.

**Native broker production deployment:** deployed on 2026-11-09. The main container uses the accepted image above,
retains its existing profile volume, and passed authenticated API, desktop HTTP/
WebSocket upgrade, native login-start status, owner authorization and Hermes
activation checks without starting a real credential service. The base-only URL correction below is a separate,
previously promoted change.

Earlier exploration used signed Firefox extension 2026.10.2 and disposable
Vaultwarden 1.37.5. It does not replace the sealed R3 evidence or prove behavior
against the deployed Vaultwarden server. The public `/api/config` version is a
Bitwarden compatibility value, so it did not establish that server's actual
Vaultwarden release; no older-server explanation was confirmed.

The managed self-hosted environment should normally set only `base` to the exact
HTTPS vault origin. Setting every service URL to the bare origin produced 404s for
prelogin/config paths in the fixture. If explicit overrides are needed, use the
extension's canonical service paths and validate every override before password
entry; checking only `base` can conceal a different credential destination.

The base-only managed URL correction was promoted to the homelab on 2026-11-09,
retaining its existing image and profile mount. The loaded Firefox policy, API,
desktop HTTP and `/api/websockets` upgrade passed. No real credential login was
used. That earlier policy-only rollout did not deploy the native broker.

The original 26.7 test asset had no META-INF signatures; never weaken a signed-state
check to accept it. The official signed 26.7 artifact is available from
[Mozilla Add-ons](https://addons.mozilla.org/firefox/downloads/file/4915668/bitwarden_password_manager-2026.7.0.xpi),
SHA256 `11836eb9d2abc9914bb337b57e20c5a09cf44f24fa572f7e886384fd350a5112`.

The real toolbar popup is a remote XUL `browser.webextension-popup-browser` inside
an open Firefox panel. Opening `popup/index.html` as a normal tab is not equivalent.
On the pinned Firefox build, WebDriver frame switching into that XUL browser fails;
the internal Marionette actor can perform normal DOM reads and trusted input.
Expose only fixed broker actions, never a general extension evaluator or selector API.
Async managed-storage reads need callback-style actor execution, not serialization
of Bitwarden's Zone.js Promise.

Require exact addon ID, active state, signed state, version and packaged XPI hash.
Verify the managed server and the account's normal accessible label immediately
before password entry. A preexisting password screen for another account must
refuse input. Mark secret exposure before fill so partial-fill failures are cleaned.
Do not retry submit after a click timeout; it may already have reached the extension.

Opaque unlock operations belong to the browser generation and caller. Secret
transport is the owner-only local socket/stdin adapter; status, cancel and lock
return allowlisted state. Protected 2FA retains human control. A normal lock may
dismiss the panel: reopen once to verify the result, without repeating the action.
Keep failed cleanup/relock fail-closed.

Passkeys use a separate extension popout with a session ID, native sender tab and
sender URL. Bind all of these to the exact server-owned page; URL alone cannot
separate duplicate tabs. Playwright client Frame._id is undefined. In the pinned
in-process implementation, page._connection.toImpl(page.mainFrame())._id yields
the server frame ID; verify that bridge before relying on it across versions.
Reject multiple matching prompts/accounts/items.

A default master-password lock requests a browser-extension process reload. Its
background waits for extension popups to close. Close the broker-owned toolbar
before waiting for a new active/running extension generation; an immediate
verification reopen can block that reload. Do not retain the old background
context strongly while observing a restart. The accepted R3 candidate uses weak
metadata references and a later verification open after the generation changes.

An idle restarted server may be connected with no native browser windows.
Marionette cannot initialize there. For authorized deployment verification, hold
one fresh operator-owned blank API page during the read-only policy check, then
close that operator session. Never respond by looping restarts or opening real
login pages. Synthetic authentication tests still run in a separate container.

After extension process reload, old website content-script contexts can be stale.
The passing flow was unlock, fresh ordinary website navigation, then a new
credential request. Refresh before starting that request, never the pending Fido
prompt. Preserve an existing human/CAPTCHA lease; if navigation would discard
unfinished human work, stop and arrange the handoff instead of navigating it away.

The separately versioned Hermes 1.0.2-nativehost and host bridge packages supersede
the older host integration scripts embedded in the R3 source archive. Install the
reviewed host packages for UUIDv4 enforcement, duplicate-request ownership and the
scoped polkit grant. The fixed bridge config is
`/etc/camofox-extension-broker/config.json`; the credential service must never be
started merely for a readiness check. `collector` vault-wrapper `status` itself
starts a real CLI unlock service; use metadata-only checks for review work.

Startup readiness has intermittently returned HTTP 503 in production; its exact
first failure body was not retained, so the cause is unconfirmed. Subsequent
installed-client status succeeded, and a separate fresh-profile production-config
probe passed ten consecutive status calls. Do not call unlock while status is
unknown/unavailable. One delayed status-only retry is reasonable; then preserve
state and investigate the typed error. Never retry an uncertain credential submit,
reinstall the addon or loop container restarts. If status is already unlocked, do
not invoke the credential service again merely to establish readiness.
