"""Typed native Bitwarden and human-control tools; no credentials cross this API.

The host dispatcher is an administrator-installed, fixed program. Its only inputs
are broker-issued opaque identifiers; its output is never returned to the model.
"""
from __future__ import annotations

import json
import subprocess
import threading
import uuid
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

from . import camofox_client as client

DISPATCHER = "/opt/camofox-extension-broker/request-unlock.py"
DISPATCH_TIMEOUT = 90
_BW_STATES = frozenset({"locked", "logged_out", "login_start", "unlocked", "two_factor_required",
    "invalid_master_password", "unknown", "unavailable", "lock_failed", "awaiting_secret",
    "unlocking", "passkey_pending", "failed", "cancelled", "expired"})
_HANDOFF_STATES = frozenset({"automation", "needs_human", "human_control", "expired", "ready_to_resume"})
_PASSKEY_STATES = frozenset({"approval_sent", "verification_required", "approval_uncertain", "rejected"})
_PASSKEY_ERRORS = frozenset({"blacklist_denied", "approval_unavailable", "ambiguous_account",
    "already_attempted", "unlock_lease_required", "prompt_mismatch", "registration_not_allowed",
    "policy_invalid", "policy_changed", "verification_required", "approval_uncertain", "browser_busy"})
_REASONS = frozenset({"captcha", "login", "mfa", "manual"})
_ERRORS = frozenset({"driver_unavailable", "driver_timeout", "driver_failed", "extension_unavailable",
    "server_mismatch", "account_mismatch", "invalid_master_password", "two_factor_required", "lock_failed",
    "invalid_request", "unsupported_action", "operation_not_found", "operation_unavailable", "browser_busy",
    "browser_vault_busy", "lock_required", "operation_limit", "human_control_active", "handoff_lease_mismatch",
    "bitwarden_unavailable", "owner_delivery_setup_required", "approval_unavailable", "cleanup_failed"})
_RULES = {
    "bitwarden_status": ({}, set()),
    "bitwarden_unlock": ({"ttlSeconds": (30, 300)}, set()),
    "bitwarden_operation": ({"operationId": "uuid"}, {"operationId"}),
    "bitwarden_cancel": ({"operationId": "uuid"}, {"operationId"}),
    "bitwarden_approve_passkey": ({"operationId": "uuid", "accountHint": "account_hint"}, {"operationId"}),
    "bitwarden_lock": ({}, set()),
    "handoff_status": ({}, set()),
    "request_handoff": ({"reason": "reason", "ttlSeconds": (30, 1800)}, set()),
    "renew_handoff": ({"leaseId": "uuid", "ttlSeconds": (30, 1800)}, {"leaseId"}),
    "resume_handoff": ({"leaseId": "uuid", "humanConfirmed": "confirmed"}, {"leaseId", "humanConfirmed"}),
    "focus_tab": ({}, set()),
}
_protected_tasks: dict[tuple[str, str], set[str]] = {}
_protection_lock = threading.Lock()
_core_mode = False


def configure_core_mode(bundled: bool) -> None:
    """No identity may be invented alongside an unverified legacy core backend."""
    global _core_mode
    _core_mode = bundled


def _uuid(value: Any) -> bool:
    try:
        return isinstance(value, str) and len(value) == 36 and str(uuid.UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def _failure(code: str) -> dict[str, Any]:
    return {"success": False, "errorCode": code}


def _valid_args(action: str, args: Any) -> bool:
    rules, required = _RULES[action]
    if not isinstance(args, dict) or set(args) - rules.keys() or not required <= args.keys():
        return False
    for key, value in args.items():
        rule = rules[key]
        if isinstance(rule, tuple):
            if type(value) is not int or not rule[0] <= value <= rule[1]:
                return False
        elif rule == "uuid" and not _uuid(value):
            return False
        elif rule == "reason" and (not isinstance(value, str) or value not in _REASONS):
            return False
        elif rule == "confirmed" and value is not True:
            return False
        elif rule == "account_hint" and (not isinstance(value, str) or not value or len(value) > 512
                or value != value.strip() or any(ord(ch) < 0x20 or ord(ch) == 0x7f for ch in value)):
            return False
    return True


def _timestamp(value: Any) -> bool:
    if not isinstance(value, str) or len(value) > 64:
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


def _desktop_url(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 32 for c in value):
        return None
    try:
        url = urlsplit(value)
        if url.scheme not in {"http", "https"} or not url.hostname or url.username is not None or url.password is not None:
            return None
        return urlunsplit((url.scheme, url.netloc, url.path, "", ""))
    except ValueError:
        return None


def _challenge(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result = {k: value[k] for k in ("detected", "visibleChallenge", "completionSignal", "inspectionIncomplete")
              if type(value.get(k)) is bool}
    if isinstance(value.get("verification"), str) and value["verification"] in {"unknown", "completion_signal", "human_confirmation_required"}:
        result["verification"] = value["verification"]
    signals = value.get("signals")
    if isinstance(signals, list):
        result["signals"] = [{"provider": s["provider"], **{k: s[k] for k in ("visible", "challenge") if type(s.get(k)) is bool}}
            for s in signals[:20] if isinstance(s, dict) and isinstance(s.get("provider"), str) and s["provider"] in
            {"recaptcha", "hcaptcha", "turnstile", "arkose", "perimeterx", "challenge"}]
    return result


def _result(data: Any, *, handoff: bool = False, operation_id: str | None = None) -> dict[str, Any]:
    states = _HANDOFF_STATES if handoff else _BW_STATES
    if (not isinstance(data, dict) or type(data.get("ok")) is not bool
            or not isinstance(data.get("state"), str) or data["state"] not in states):
        return _failure("invalid_response")
    if operation_id is not None and data.get("operationId") != operation_id:
        return _failure("invalid_response")
    result: dict[str, Any] = {"success": data["ok"] and data["state"] != "expired", "state": data["state"]}
    if data.get("scope") == "browser":
        result["scope"] = "browser"
    for key in ("operationId", "browserInstance", "leaseId"):
        if _uuid(data.get(key)):
            result[key] = data[key]
    if data.get("expiresAt") is None and handoff:
        result["expiresAt"] = None
    elif _timestamp(data.get("expiresAt")):
        result["expiresAt"] = data["expiresAt"]
    if isinstance(data.get("errorCode"), str) and data["errorCode"] in _ERRORS:
        result["errorCode"] = data["errorCode"]
    elif data["ok"] is False:
        result["errorCode"] = "control_failed"
    if handoff:
        if isinstance(data.get("reason"), str) and data["reason"] in _REASONS:
            result["reason"] = data["reason"]
        if type(data.get("focused")) is bool:
            result["focused"] = data["focused"]
        if data.get("verification") == "human_confirmed":
            result["verification"] = "human_confirmed"
        desktop = _desktop_url(data.get("desktopUrl"))
        if desktop:
            result["desktopUrl"] = desktop
        if isinstance(data.get("challenge"), dict):
            result["challenge"] = _challenge(data["challenge"])
        if data["state"] in {"needs_human", "human_control", "expired"}:
            result["instructions"] = "Keep this tab open for the human. Renew its lease as needed; resume only after explicit human confirmation."
    return result


def preserve_task(task_id: str | None = None) -> bool:
    """Retain this task's tab across turn cleanup while the human owns it."""
    with _protection_lock:
        return client._session_key(task_id) in _protected_tasks


def _protect(task_id: str | None, reason: str, protected: bool) -> None:
    with _protection_lock:
        key = client._session_key(task_id)
        if protected:
            _protected_tasks.setdefault(key, set()).add(reason)
        elif key in _protected_tasks:
            _protected_tasks[key].discard(reason)
            if not _protected_tasks[key]:
                del _protected_tasks[key]


def _claim_protection(task_id: str | None, reason: str) -> bool:
    """Atomically add a hold only if another call has not already claimed it."""
    with _protection_lock:
        key = client._session_key(task_id)
        reasons = _protected_tasks.setdefault(key, set())
        if reason in reasons:
            return False
        reasons.add(reason)
        return True


def _track(task_id: str | None, result: dict[str, Any], *, handoff: bool = False) -> dict[str, Any]:
    """Only verified terminal state clears its own protection reason."""
    state = result.get("state")
    if handoff:
        if state in {"needs_human", "human_control", "expired"}:
            _protect(task_id, "handoff", True)
        elif result.get("success") and state in {"automation", "ready_to_resume"}:
            _protect(task_id, "handoff", False)
    elif state in {"two_factor_required", "awaiting_secret", "unlocking", "unlocked", "passkey_pending", "lock_failed"}:
        _protect(task_id, "bitwarden", True)
    # An old operation can be cancelled while a newer operation owns the browser.
    # Cancellation alone is therefore insufficient evidence to drop this hold.
    elif result.get("success") and state in {"locked", "logged_out", "login_start"}:
        _protect(task_id, "bitwarden", False)
        # A verified terminal vault state proves no native passkey prompt still
        # needs this task's browser context. Website-human leases remain separate.
        _protect(task_id, "passkey", False)
    cancelled = result.get("cancelled")
    if isinstance(cancelled, dict):
        _track(task_id, cancelled)
    return result


def _track_passkey(task_id: str | None, result: dict[str, Any]) -> dict[str, Any]:
    state = result.get("state")
    if state in {"verification_required", "approval_uncertain"}:
        _protect(task_id, "passkey", True)
    elif state in {"approval_sent", "rejected"}:
        _protect(task_id, "passkey", False)
    return result


def _passkey_result(data: Any) -> dict[str, Any]:
    allowed = {"ok", "state", "attemptId", "errorCode", "scope"}
    if (not isinstance(data, dict) or set(data) - allowed or type(data.get("ok")) is not bool
            or data.get("state") not in _PASSKEY_STATES):
        return {**_failure("approval_uncertain"), "state": "approval_uncertain"}
    state = data["state"]
    if data["ok"] is not (state == "approval_sent"):
        return {**_failure("approval_uncertain"), "state": "approval_uncertain"}
    result = {"success": state == "approval_sent", "state": state}
    if "attemptId" in data:
        if not _uuid(data["attemptId"]):
            return {**_failure("approval_uncertain"), "state": "approval_uncertain"}
        result["attemptId"] = data["attemptId"]
    if "scope" in data:
        if data["scope"] != "browser":
            return {**_failure("approval_uncertain"), "state": "approval_uncertain"}
        result["scope"] = "browser"
    if "errorCode" in data:
        if not isinstance(data["errorCode"], str) or data["errorCode"] not in _PASSKEY_ERRORS:
            return {**_failure("approval_uncertain"), "state": "approval_uncertain"}
        if ((data["errorCode"] == "verification_required" and state != "verification_required")
                or (data["errorCode"] == "approval_uncertain" and state != "approval_uncertain")
                or (state == "approval_sent")):
            return {**_failure("approval_uncertain"), "state": "approval_uncertain"}
        result["errorCode"] = data["errorCode"]
    if state == "approval_sent":
        result["siteAuthenticated"] = False
    elif state == "verification_required" and "errorCode" not in result:
        result["errorCode"] = "verification_required"
    elif state == "approval_uncertain" and "errorCode" not in result:
        result["errorCode"] = "approval_uncertain"
    return result


def _passkey_http_failure(exc: Exception) -> dict[str, Any]:
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            data = response.json()
        except Exception:
            data = None
        if isinstance(data, dict):
            # A typed route response is still an approval outcome even when HTTP
            # uses a non-2xx status; never return any other server fields.
            if data.get("state") in _PASSKEY_STATES:
                return _passkey_result(data)
            code = data.get("errorCode")
            if isinstance(code, str) and code in _PASSKEY_ERRORS:
                state = ("verification_required" if code == "verification_required" else
                         "approval_uncertain" if code == "approval_uncertain" else "rejected")
                result = {"success": False, "state": state, "errorCode": code}
                if state == "approval_uncertain":
                    result["errorCode"] = "approval_uncertain"
                return result
    # Transport errors can occur after the UI click; never retry or claim rejection.
    return {"success": False, "state": "approval_uncertain", "errorCode": "approval_uncertain"}


def _http_failure(exc: Exception, *, handoff: bool = False, operation_id: str | None = None) -> dict[str, Any]:
    """Read only finite typed fields from an HTTP error, never its message/body text."""
    response = getattr(exc, "response", None)
    if response is None:
        return _failure("control_unavailable")
    try:
        data = response.json()
    except Exception:
        data = None
    if isinstance(data, dict):
        code = data.get("errorCode", data.get("code"))
        if data.get("ok") is False and isinstance(data.get("state"), str):
            result = _result(data, handoff=handoff, operation_id=operation_id)
            if result.get("errorCode") != "invalid_response":
                return result
        if isinstance(code, str) and code in _ERRORS:
            return _failure(code)
    return _failure("authentication_required" if getattr(response, "status_code", None) == 401 else "control_unavailable")


def _cancel(user_id: str, operation_id: str) -> dict[str, Any]:
    try:
        return _result(client.post("/bitwarden/cancel", {"userId": user_id, "operationId": operation_id}), operation_id=operation_id)
    except Exception as exc:
        return _http_failure(exc, operation_id=operation_id)


def _unlock(user_id: str, args: dict[str, Any]) -> dict[str, Any]:
    data = client.post("/bitwarden/unlock", {"userId": user_id, **args})
    op = data.get("operationId") if isinstance(data, dict) else None
    browser = data.get("browserInstance") if isinstance(data, dict) else None
    pending = _result(data)
    if pending.get("success") is not True:
        if pending.get("errorCode") == "invalid_response" and _uuid(op):
            pending["cancelled"] = _cancel(user_id, op)
        return pending
    if data.get("state") != "awaiting_secret" or not _uuid(op) or not _uuid(browser):
        result = _failure("invalid_response")
        if _uuid(op):
            result["cancelled"] = _cancel(user_id, op)
        return result
    try:
        proc = subprocess.run(["/usr/bin/python3", DISPATCHER, "--operation-id", op, "--browser-instance", browser],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=DISPATCH_TIMEOUT, check=False)
        failure = "owner_delivery_failed" if proc.returncode != 0 else None
    except subprocess.TimeoutExpired:
        failure = "owner_delivery_timeout"
    except OSError:
        failure = "owner_delivery_unavailable"
    except Exception:
        failure = "owner_delivery_failed"
    if failure:
        return {**_failure(failure), "operationId": op, "cancelled": _cancel(user_id, op)}
    try:
        current = client.get(f"/bitwarden/operations/{op}", params={"userId": user_id})
        result = _result(current, operation_id=op)
        if result.get("errorCode") == "invalid_response" or current.get("browserInstance") != browser:
            return {**_failure("invalid_response"), "operationId": op, "cancelled": _cancel(user_id, op)}
        return result
    except Exception as exc:
        return {**_http_failure(exc, operation_id=op), "operationId": op, "cancelled": _cancel(user_id, op)}


def native_control(action: str, args: dict[str, Any], task_id: str | None = None) -> dict[str, Any]:
    """Run one allowlisted action using the current task's identity and existing tab."""
    if not isinstance(action, str) or action not in _RULES:
        return _failure("unsupported_action")
    if not _valid_args(action, args):
        return _failure("invalid_request")
    if _core_mode:
        return _failure("unsupported_core_backend")
    try:
        session = client.get_session(task_id)
        user_id = session["user_id"]
        if not isinstance(user_id, str) or not user_id:
            return _failure("invalid_response")
        if action == "bitwarden_unlock":
            _protect(task_id, "bitwarden", True)
            return _track(task_id, _unlock(user_id, args))
        if action == "bitwarden_operation":
            op = args["operationId"]
            return _track(task_id, _result(client.get(f"/bitwarden/operations/{op}", params={"userId": user_id}), operation_id=op))
        if action == "bitwarden_cancel":
            return _track(task_id, _cancel(user_id, args["operationId"]))
        if action in {"bitwarden_status", "bitwarden_lock"}:
            return _track(task_id, _result(client.post("/bitwarden/" + action.removeprefix("bitwarden_"), {"userId": user_id})))
        tab_id = session.get("tab_id")
        if not isinstance(tab_id, str) or not tab_id:
            return _failure("no_current_tab")
        path = f"/tabs/{quote(tab_id, safe='')}/"
        if action == "bitwarden_approve_passkey":
            if not _claim_protection(task_id, "passkey"):
                return {"success": False, "state": "approval_uncertain", "errorCode": "approval_uncertain"}
            body = {"userId": user_id, "operationId": args["operationId"]}
            if "accountHint" in args:
                body["accountHint"] = args["accountHint"]
            try:
                data = client.post(path + "passkey/approve", body)
                result = _passkey_result(data)
            except Exception as exc:
                result = _passkey_http_failure(exc)
            return _track_passkey(task_id, result)
        if action == "handoff_status":
            data = client.get(path + "handoff", params={"userId": user_id})
        else:
            # The server may acquire the lease even when the response is lost.
            _protect(task_id, "handoff", True)
            suffix = {"request_handoff": "handoff", "renew_handoff": "handoff/renew",
                      "resume_handoff": "handoff/resume", "focus_tab": "focus"}[action]
            data = client.post(path + suffix, {"userId": user_id, **args})
        result = _result(data, handoff=True)
        return _track(task_id, result, handoff=True)
    except Exception as exc:
        return _track(task_id, _http_failure(exc, handoff=not action.startswith("bitwarden_"),
            operation_id=args.get("operationId")), handoff=not action.startswith("bitwarden_"))


def make_handler(action: str):
    def handler(args: dict, **kw: Any) -> str:
        return json.dumps(native_control(action, args, task_id=kw.get("task_id")), ensure_ascii=False)
    return handler
