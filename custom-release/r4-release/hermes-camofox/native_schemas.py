"""Native-control schemas mirror the server contracts and bind identity locally."""


def _schema(name, description, properties=None, required=()):
    return {"name": name, "description": description, "parameters": {
        "type": "object", "properties": properties or {}, "required": list(required),
        "additionalProperties": False}}


_TTL_UNLOCK = {"type": "integer", "minimum": 30, "maximum": 300}
_TTL_HANDOFF = {"type": "integer", "minimum": 30, "maximum": 1800}
_UUID = {"type": "string", "format": "uuid", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"}

NATIVE_SCHEMAS = {
    "bitwarden_status": _schema("browser_bitwarden_status",
        "Read typed browser-wide native Bitwarden state. Separate from website login and Hermes browser_vault. Never request a master password."),
    "bitwarden_unlock": _schema("browser_bitwarden_unlock",
        "Request a short-lived native Bitwarden unlock through the fixed local owner dispatcher. This prearms the native passkey controller; unlock before triggering the website passkey, and use a fresh normal navigation after a page reload. Accepts no account, password or credential. Returns typed operation state; approval is a separate GET-only action checked against the host administrator's denylist.",
        {"ttlSeconds": _TTL_UNLOCK}),
    "bitwarden_operation": _schema("browser_bitwarden_operation",
        "Read an opaque native Bitwarden unlock operation owned by this task identity. Returns typed state only, never vault contents.",
        {"operationId": _UUID}, ("operationId",)),
    "bitwarden_cancel": _schema("browser_bitwarden_cancel",
        "Cancel an owned unlock operation and request verified relock. Inspect the typed result for lock failure.",
        {"operationId": _UUID}, ("operationId",)),
    "bitwarden_approve_passkey": _schema("browser_bitwarden_approve_passkey",
        "Attempt one eligible passkey GET approval in the current task tab under the host administrator's exact-site, RP and account denylist. Requires the opaque unlock operation ID; optional accountHint is an exact visible username used only to disambiguate rows. approval_sent means the extension click was sent, not that the site authenticated.",
        {"operationId": _UUID, "accountHint": {"type": "string", "minLength": 1, "maxLength": 512}},
        ("operationId",)),
    "bitwarden_lock": _schema("browser_bitwarden_lock",
        "Relock the browser-wide native Bitwarden extension. Do not claim successful lock after a failure."),
    "handoff_status": _schema("browser_handoff_status",
        "Read the current task tab's human-control lease and non-secret challenge signals. Does not create a tab or capture the human login."),
    "request_handoff": _schema("browser_request_handoff",
        "Pause automation and focus the current existing tab for the human to handle CAPTCHA, login, MFA, or a real passkey prompt. Preserve this tab and renew its lease; do not create replacements or automate approval.",
        {"reason": {"type": "string", "enum": ["captcha", "login", "mfa", "manual"]}, "ttlSeconds": _TTL_HANDOFF}),
    "renew_handoff": _schema("browser_renew_handoff",
        "Renew the current tab's same human-control lease while the person works, preserving the original tab.",
        {"leaseId": _UUID, "ttlSeconds": _TTL_HANDOFF}, ("leaseId",)),
    "resume_handoff": _schema("browser_resume_handoff",
        "Return the current tab to automation only after the human explicitly confirms completion. Never infer consent from a timeout or CAPTCHA visibility.",
        {"leaseId": _UUID, "humanConfirmed": {"type": "boolean", "enum": [True]}}, ("leaseId", "humanConfirmed")),
    "focus_tab": _schema("browser_focus_tab",
        "Focus the current task's existing tab in the shared desktop without creating a replacement or releasing human control."),
}
