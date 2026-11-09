# Native Bitwarden route

Validated research on November 9, 2026 used the signed Firefox extension 2026.10.2
and disposable Vaultwarden 1.37.5. This is candidate evidence, not proof that the
same client works with an older deployed Vaultwarden generation.

The managed self-hosted environment should normally set only `base` to the exact
HTTPS vault origin. Setting every service URL to the bare origin produced 404s for
prelogin/config paths in the fixture. If explicit overrides are needed, use the
extension's canonical service paths and validate every override before password
entry; checking only `base` can conceal a different credential destination.

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

Current limitation: real registration returned a validated RP public key, but later
ceremonies opened an empty app-fido2 picker. Assertion signature verification has
not passed. No autonomous passkey approval API is enabled. A normal Sync now did
not resolve it; an SDK/cache explanation is unproven. Do not reload a pending
prompt as recovery: its ConnectResponse handshake is accepted once. Abort the
website request and begin a fresh ceremony through normal UI instead.
