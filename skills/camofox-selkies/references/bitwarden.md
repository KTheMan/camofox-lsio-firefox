# Native Bitwarden route

Validated research on November 9, 2026 used the signed Firefox extension 2026.10.2
and disposable Vaultwarden 1.37.5. This is candidate evidence, not proof that the
same client works with an older deployed Vaultwarden generation.

The managed self-hosted environment should normally set only `base` to the exact
HTTPS vault origin. Setting every service URL to the bare origin produced 404s for
prelogin/config paths in the fixture. If explicit overrides are needed, use the
extension's canonical service paths and validate every override before password
entry; checking only `base` can conceal a different credential destination.

The base-only managed URL correction was promoted to the homelab on 2026-11-09,
retaining its existing image and profile mount. The loaded Firefox policy, API,
desktop HTTP and `/api/websockets` upgrade passed. No real credential login was
used. This deployment does not make the native broker or passkey API available.

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

The isolated native prototype passed two master-password unlock/lock cycles,
registration and an ES256 assertion verified by the RP. UP was checked and UV was
true for that preferred-verification request. These were disposable credentials;
Google sign-in and the sealed release are not claimed by that prototype result.
No autonomous passkey approval API is enabled. Human approval remains in the
Bitwarden prompt. Do not reload a pending prompt: its ConnectResponse handshake
is accepted once. Abort an old request through normal UI before a fresh ceremony.
An SDK/cache explanation for earlier empty prompts was not established.

A default master-password lock requests a browser-extension process reload. Its
background waits for extension popups to close. Close the broker-owned toolbar
before waiting for a new active/running extension generation; an immediate
verification reopen can block that reload. Do not retain the old background
context strongly while observing a restart. The candidate uses weak metadata
references and one later verification open; sealed native acceptance is still pending.

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
