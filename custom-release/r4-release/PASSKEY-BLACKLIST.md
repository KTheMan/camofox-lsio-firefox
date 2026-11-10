# Automatic native passkey sign-ins (R4)

Kenny's selected policy is default allow with an initially empty administrator blacklist.
This supersedes R3's mandatory human approval for every assertion. Hermes may approve
one unambiguous pending passkey sign-in after its own successful leased unlock.

POST `/tabs/{tabId}/passkey/approve` accepts only `userId`, `operationId` and optional
`accountHint` (the exact visible credential username). Hermes binds its current task's
existing tab locally; origin, frame, sender tab and pending request are captured and
verified by trusted server/native code. The action is GET/assertion only. It does not
register a passkey, export private key material, call the signing SDK, enter a master
password or infer that the website authenticated.

The fixed driver loads `CAMOFOX_PASSKEY_POLICY_FILE`; the built-in default is
`plugins/bitwarden-unlock/passkey-blacklist.json`. Missing/unsafe/invalid files refuse
approval. Mount the dedicated policy directory read-only so administrator atomic file replacements
are visible to the running container. Host policy is never supplied in model arguments.
The administrator JSON schema is:

```json
{"version":1,"blockedOrigins":[],"blockedRpIds":[],"blockedAccounts":[]}
```

`blockedOrigins` contains exact canonical bare HTTPS origins (including a nondefault
port when needed). `blockedRpIds` blocks that RP domain and its descendants based on
the trusted request origin. `blockedAccounts` matches the extension's visible username,
ignoring case and collapsed whitespace; it is not a cryptographic userHandle selector.
If account blocking is configured and the visible account is unavailable, approval stops.
The model cannot edit this policy through HTTP/MCP.

A private persistent native controller is armed during successful unlock, before
the website credential request. It holds one Marionette session through the lease;
attachment during an already-pending request is unsupported. Preparation binds the
pending native popup, GET-only heading, row metadata and server frame. A process-local per-browser ledger consumes the unique pending session before
the single atomic normal-DOM UI click. Browser generation changes revoke the lease.
A lost/uncertain result is never replayed; human/verification holds remain until a
verified vault lock or cancellation resolves them. Existing human tab handoffs remain
separate and require their normal explicit confirmation.

`approval_sent` means the prompt closed after the click; inspect the website separately
to verify login. Native verification, ambiguous accounts, registration, blacklist matches,
changed pages/policies, expired/unowned unlock leases and uncertain clicks stop automation.
Do not restart/reinstall to retry an uncertain ceremony.

This source is a candidate until the sealed runtime evidence and deployment manifest
confirm the exact immutable image. Authentication tests use only disposable credentials
in a separate container and fresh profile.

The pinned signed extension's toolbar history cache can rewrite the live FIDO
popout to queryless `#/tabs/current` while its original UI remains mounted.
The prearmed native progress observer captures the original committed popup URL
and exact browser/BC/inner-window identity. It accepts only that demonstrated
same-document rewrite with the same outer action marker. All other route/session
or document changes refuse approval. Strict current sender/frame/page binding
and blacklist checks still apply. The final click executes through the captured
WindowGlobal actor; the atomic DOM task also checks its private lease deadline.
Native observer state expires with that deadline, independently of the worker,
and is removed on explicit release or replacement. It is bounded and retains
only private URL/identity metadata, never provider SDK or private-key state.
See `VENDOR-ROUTING-EVIDENCE.md` for the signed package source explanation.

Equivalent FIDO URL encodings pass only when every decoded field and its presence match exactly, with valid UTF-8 and no duplicate or unknown fields.
