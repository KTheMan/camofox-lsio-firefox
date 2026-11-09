# Native Bitwarden route

## Current R4 operation

R4 deployed to the main container on 2026-11-09; image `sha256:4ce65b65ed0827589023ed806cdd9db9a059943ce8bb1c0112fce3003041a29e`, source `be42ffad88af21f2ad338ca6231ab9873131d62f004bd0eceddebb7a2addf89e`; rollout post-check passed.

The user's selected policy is default allow with an initially empty administrator
blacklist. This supersedes R3's human-only sign-in approval. Hermes 1.0.3-passkey
adds `browser_bitwarden_approve_passkey(operationId, accountHint?)`; the canonical
MCP tool is `camofox_approve_passkey`. The API accepts only an owned task tab,
operation identity and optional exact visible username. It accepts no caller URL,
frame, selector, signing key or policy override.

Unlock through the protected broker before triggering the website's request.
Successful unlock prearms one native controller for that lease. The signed extension
handles the passkey cryptography. One unambiguous eligible GET prompt can be
approved; registration is separate. Verify website login after `approval_sent`,
then explicitly lock and confirm it. An uncertain click is never retried.
Verification, failed relock and uncertain approval keep automation protected.
Human CAPTCHA/login handoff remains independent and needs explicit return of control.

The administrator policy is `STACK/passkey-policy/blacklist.json`, mounted as a
read-only directory at `/run/camofox-passkeys`. The path setting is
`CAMOFOX_PASSKEY_POLICY_FILE=/run/camofox-passkeys/blacklist.json`.
Use root ownership, mode 0644 and atomic replacement. Its exact schema is:

```json
{"version":1,"blockedOrigins":[],"blockedRpIds":[],"blockedAccounts":[]}
```

Origins match exact canonical bare HTTPS origins; RP domains also block their
descendants. Account matching uses the extension's visible username, with case
and whitespace normalization, rather than the item title or cryptographic
userHandle. Account blocks with unavailable visible identity fail closed.
Malformed/missing/insecure policy fails closed; the model cannot edit it.

Signed 2026.7.0 has a popup route-cache bug: a passkey popout can inherit the toolbar's
`/tabs/current` hash while the original FIDO UI remains mounted. Do not accept that
route without provenance, reload the pending prompt, or loosen sender/session checks.
The prearmed native observer records the initial strict FIDO URL and exact native
popup document identity before the rewrite. Only the demonstrated queryless
`/tabs/current` rewrite is supported, with unchanged outer session marker and exact
current document, sender tab/frame and task page. The final click targets that exact
document actor. Capture failure, navigation, other route/session changes, expiry,
observer errors and overflow refuse approval. Native records self-expire with the
lease; no private key or SDK state is read.

Rebuild this custom release from its archived `release/Dockerfile` and source/host
packages with the release manifest. The repository's ordinary LSIO baseline build
does not recreate it. Runtime 2FA and Google sign-in still need their own evidence.

## Historical sealed R3 acceptance

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

R3 required human approval in the real Bitwarden prompt and had no autonomous
approval API. R4 above supersedes that approval policy. Runtime 2FA completion was not exercised, and
Google login was not tested. PIN/biometric configurations that suppress the
extension reload are rejected fail-closed. Never reload a pending passkey prompt;
its ConnectResponse handshake is accepted once. If reload or relock is uncertain,
keep automation blocked.

**Historical R3 production deployment:** deployed on 2026-11-09. It used the accepted image above,
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

Automatic approval requires the current caller's active unlocked broker operation.
A manually unlocked extension alone does not grant that lease. If the operation
identity is unavailable, preserve the UI for human completion or explicitly lock
and start a fresh authorized consuming workflow. Do not dispatch credentials
merely because status is already unlocked.

Equivalent FIDO URL encodings pass only when every decoded field and its presence match exactly, with valid UTF-8 and no duplicate or unknown fields.

For native startup maintenance, use the readiness event's `currentTarget` and
primitive `outerWindowId` with the window mediator. A JavaScript WeakRef to a
transient Chrome-window wrapper can disappear while the native window is still
alive, causing missed capture and incomplete listener cleanup. Keep this tested
against the pinned engine when changing its version.

After a completed popout closes, reset global native metadata/status checks to a
live normal Chrome window without focusing it. Keep the same prearmed Marionette
session. A closed selected popup must not kill the lease's controller or trigger
browser/extension restarts; stale closing handles are skipped during inventory.

A later sealed-fixture unlock timed out and entered protected `lock_failed`; a
credential-free explicit lock recovered it, and a fresh consuming workflow then
completed in 10.08 seconds. Do not retry an uncertain credential submission.
Inspect the operation's typed cause and obtain verified lock before a fresh
workflow. The regular unlock (60s) plus controller arming (up to 25s) can exceed
the local socket's 65s budget; this end-to-end budget remains a reliability gap,
not proof of the observed timeout's cause. Keep failed/uncertain states blocked.
