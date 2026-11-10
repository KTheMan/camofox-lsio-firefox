"""Native Bitwarden controls stay task-bound, typed, and private at the plugin boundary."""

from __future__ import annotations

import subprocess
import threading
import uuid

import pytest
import requests


@pytest.fixture
def native(monkeypatch):
    from camofox_plugin import native_controls as controls

    controls.configure_core_mode(False)
    with controls._protection_lock:
        controls._protected_tasks.clear()

    sessions = {
        "task-a": {"user_id": "user-a", "tab_id": "tab-a", "session_key": "task_task-a"},
        "task-b": {"user_id": "user-b", "tab_id": "tab-b", "session_key": "task_task-b"},
        "empty": {"user_id": "user-empty", "tab_id": None, "session_key": "task_empty"},
    }
    session_calls = []
    http_calls = []
    responses = {}

    def get_session(task_id):
        session_calls.append(task_id)
        return sessions[task_id]

    def get(path, **kwargs):
        http_calls.append(("GET", path, kwargs))
        response = responses.get(("GET", path))
        if isinstance(response, Exception):
            raise response
        if response is None:
            raise AssertionError(f"unexpected GET {path}")
        return response

    def post(path, body=None, **kwargs):
        http_calls.append(("POST", path, {"body": body, **kwargs}))
        response = responses.get(("POST", path))
        if isinstance(response, Exception):
            raise response
        if response is None:
            raise AssertionError(f"unexpected POST {path}")
        return response

    monkeypatch.setattr(controls.client, "get_session", get_session)
    monkeypatch.setattr(controls.client, "get", get)
    monkeypatch.setattr(controls.client, "post", post)
    yield controls, sessions, session_calls, http_calls, responses
    with controls._protection_lock:
        controls._protected_tasks.clear()
    controls.configure_core_mode(False)


def _j(control, action, args=None, task_id="task-a"):
    return control.native_control(action, args or {}, task_id=task_id)


@pytest.mark.parametrize("field,value", [
    ("userId", "attacker-user"),
    ("tabId", "attacker-tab"),
    ("email", "person@example.test"),
    ("password", "secret-value"),
    ("masterPassword", "secret-value"),
    ("host", "https://attacker.invalid"),
    ("command", "arbitrary-command"),
])
def test_rejects_identity_secret_destination_and_unknown_fields_before_io(native, field, value):
    control, _sessions, _session_calls, http_calls, _responses = native
    result = _j(control, "bitwarden_unlock", {field: value})
    assert result["success"] is False
    assert result.get("errorCode") == "invalid_request"
    assert http_calls == []
    assert value not in repr(result)


def test_focus_uses_only_the_current_hermes_tasks_owned_tab(native):
    control, _sessions, session_calls, http_calls, responses = native
    responses[("POST", "/tabs/tab-b/focus")] = {
        "ok": True, "state": "automation", "focused": True,
    }

    result = _j(control, "focus_tab", {}, task_id="task-b")

    assert result["success"] is True
    assert session_calls == ["task-b"]
    assert [(method, path) for method, path, _ in http_calls] == [
        ("POST", "/tabs/tab-b/focus")
    ]
    body = http_calls[0][2]["body"]
    assert body["userId"] == "user-b"
    assert all("user-a" not in repr(call) for call in http_calls)


def test_focus_does_not_create_or_select_a_tab_when_current_task_has_none(native):
    control, _sessions, session_calls, http_calls, _responses = native

    result = _j(control, "focus_tab", {}, task_id="empty")

    assert result["success"] is False
    assert result.get("errorCode") == "no_current_tab"
    assert session_calls == ["empty"]
    assert http_calls == []


def test_operation_lookup_never_dispatches_and_expired_operation_is_not_success(native, monkeypatch):
    control, _sessions, _session_calls, http_calls, responses = native
    operation_id = str(uuid.uuid4())
    responses[("GET", f"/bitwarden/operations/{operation_id}")] = {
        "ok": False, "state": "expired", "operationId": operation_id,
    }
    executed = []
    monkeypatch.setattr(control.subprocess, "run", lambda *a, **kw: executed.append((a, kw)))

    result = _j(control, "bitwarden_operation", {"operationId": operation_id})

    assert result["success"] is False
    assert result["state"] == "expired"
    assert executed == []
    assert http_calls[0][1] == f"/bitwarden/operations/{operation_id}"
    assert http_calls[0][2].get("params", {}).get("userId") == "user-a"


def test_success_flag_cannot_turn_an_expired_server_operation_into_success(native):
    control, _sessions, _session_calls, _http_calls, responses = native
    operation_id = str(uuid.uuid4())
    responses[("GET", f"/bitwarden/operations/{operation_id}")] = {
        "ok": True, "state": "expired", "operationId": operation_id,
    }

    result = _j(control, "bitwarden_operation", {"operationId": operation_id})

    assert result["success"] is False
    assert result["state"] == "expired"


def test_noncanonical_operation_uuid_is_rejected_without_http_or_dispatch(native, monkeypatch):
    control, _sessions, _session_calls, http_calls, _responses = native
    executed = []
    monkeypatch.setattr(control.subprocess, "run", lambda *a, **kw: executed.append((a, kw)))

    result = _j(control, "bitwarden_operation", {"operationId": "../unlock"})

    assert result["success"] is False
    assert result.get("errorCode") == "invalid_request"
    assert http_calls == []
    assert executed == []


@pytest.mark.parametrize("field,value", [
    ("operationId", "not-a-uuid"),
    ("userId", "attacker-user"),
    ("tabId", "attacker-tab"),
    ("origin", "https://attacker.invalid"),
    ("blacklist", {"blockedOrigins": []}),
    ("accountHint", "\nalice@example.test"),
    ("accountHint", "x" * 513),
])
def test_passkey_approval_rejects_bad_args_before_session_or_http(native, field, value):
    control, _sessions, session_calls, http_calls, _responses = native
    args = {"operationId": str(uuid.uuid4()), field: value}
    result = _j(control, "bitwarden_approve_passkey", args)
    assert result == {"success": False, "errorCode": "invalid_request"}
    assert session_calls == [] and http_calls == []


def test_passkey_approval_uses_current_task_tab_and_private_minimal_body(native):
    control, _sessions, session_calls, http_calls, responses = native
    operation_id, attempt_id = str(uuid.uuid4()), str(uuid.uuid4())
    path = "/tabs/tab-b/passkey/approve"
    responses[("POST", path)] = {
        "ok": True, "state": "approval_sent", "attemptId": attempt_id,
        "scope": "browser", "privateAccountInventory": ["must not escape"],
    }
    # Extra server fields are rejected into a generic uncertain state, never exposed.
    result = _j(control, "bitwarden_approve_passkey",
                {"operationId": operation_id, "accountHint": "Alice@example.test"}, task_id="task-b")
    assert result["success"] is False and result["state"] == "approval_uncertain"
    assert result["errorCode"] == "approval_uncertain"
    assert "privateAccountInventory" not in repr(result)
    assert session_calls == ["task-b"]
    assert [(method, path) for method, path, _ in http_calls] == [("POST", path)]
    assert http_calls[0][2]["body"] == {
        "userId": "user-b", "operationId": operation_id, "accountHint": "Alice@example.test",
    }


def test_passkey_approval_refuses_when_current_task_has_no_tab(native):
    control, _sessions, session_calls, http_calls, _responses = native
    result = _j(control, "bitwarden_approve_passkey", {"operationId": str(uuid.uuid4())}, task_id="empty")
    assert result == {"success": False, "errorCode": "no_current_tab"}
    assert session_calls == ["empty"] and http_calls == []


def test_passkey_approval_sent_is_not_site_authentication_or_local_dispatch(native, monkeypatch):
    control, _sessions, _session_calls, http_calls, responses = native
    op, attempt = str(uuid.uuid4()), str(uuid.uuid4())
    path = "/tabs/tab-a/passkey/approve"
    responses[("POST", path)] = {"ok": True, "state": "approval_sent", "attemptId": attempt}

    def no_child(*_args, **_kwargs):
        raise AssertionError("passkey approval uses the current browser route, not a local dispatcher")

    monkeypatch.setattr(control.subprocess, "run", no_child)
    result = _j(control, "bitwarden_approve_passkey", {"operationId": op})
    assert result == {"success": True, "state": "approval_sent", "attemptId": attempt,
                      "siteAuthenticated": False}
    assert len(http_calls) == 1


@pytest.mark.parametrize("state,code", [
    ("verification_required", "verification_required"),
    ("approval_uncertain", "approval_uncertain"),
])
def test_passkey_verification_or_uncertainty_preserves_task_cleanup(native, state, code):
    control, _sessions, _session_calls, _http_calls, responses = native
    path = "/tabs/tab-a/passkey/approve"
    responses[("POST", path)] = {"ok": False, "state": state}
    result = _j(control, "bitwarden_approve_passkey", {"operationId": str(uuid.uuid4())})
    assert result["success"] is False and result["state"] == state
    assert result["errorCode"] == code
    assert control.preserve_task("task-a") is True


def test_contradictory_verification_error_cannot_clear_task_protection(native):
    control, _sessions, _session_calls, _http_calls, responses = native
    responses[("POST", "/tabs/tab-a/passkey/approve")] = {
        "ok": False, "state": "rejected", "errorCode": "verification_required",
    }
    result = _j(control, "bitwarden_approve_passkey", {"operationId": str(uuid.uuid4())})
    assert result["state"] == "approval_uncertain"
    assert result["errorCode"] == "approval_uncertain"
    assert control.preserve_task("task-a") is True


def test_passkey_timeout_is_uncertain_never_retried_and_keeps_task(native, monkeypatch):
    control, _sessions, _session_calls, http_calls, _responses = native
    calls = []

    def timeout(path, body=None, **_kwargs):
        calls.append((path, body))
        assert control.preserve_task("task-a") is True
        raise requests.Timeout("private timeout detail")

    monkeypatch.setattr(control.client, "post", timeout)
    result = _j(control, "bitwarden_approve_passkey", {"operationId": str(uuid.uuid4())})
    assert result == {"success": False, "state": "approval_uncertain", "errorCode": "approval_uncertain"}
    assert len(calls) == 1 and http_calls == []
    assert control.preserve_task("task-a") is True
    assert "private timeout detail" not in repr(result)


def test_existing_passkey_hold_cannot_be_cleared_by_later_rejection(native):
    control, _sessions, _session_calls, http_calls, responses = native
    approve_path = "/tabs/tab-a/passkey/approve"
    responses[("POST", approve_path)] = {"ok": False, "state": "approval_uncertain"}
    first = _j(control, "bitwarden_approve_passkey", {"operationId": str(uuid.uuid4())})
    assert first["state"] == "approval_uncertain"
    calls_after_first = len(http_calls)

    # A stale operation that would be rejected cannot erase an earlier uncertain-click hold.
    second = _j(control, "bitwarden_approve_passkey", {"operationId": str(uuid.uuid4())})
    assert second["state"] == "approval_uncertain"
    assert len(http_calls) == calls_after_first
    assert control.preserve_task("task-a") is True


def test_concurrent_approval_calls_atomically_claim_task_hold(native, monkeypatch):
    control, _sessions, _session_calls, _http_calls, _responses = native
    started, finish = threading.Event(), threading.Event()
    http_calls = []

    def slow_uncertain(path, body=None, **_kwargs):
        http_calls.append((path, body))
        started.set()
        assert finish.wait(timeout=3)
        return {"ok": False, "state": "approval_uncertain"}

    monkeypatch.setattr(control.client, "post", slow_uncertain)
    first = []
    thread = threading.Thread(target=lambda: first.append(
        _j(control, "bitwarden_approve_passkey", {"operationId": str(uuid.uuid4())})))
    thread.start()
    assert started.wait(timeout=2)
    second = _j(control, "bitwarden_approve_passkey", {"operationId": str(uuid.uuid4())})
    assert second == {"success": False, "state": "approval_uncertain", "errorCode": "approval_uncertain"}
    assert len(http_calls) == 1
    finish.set()
    thread.join(timeout=3)
    assert not thread.is_alive()
    assert first[0]["state"] == "approval_uncertain"
    assert control.preserve_task("task-a") is True


def test_passkey_rejection_clears_only_its_own_protection_reason(native):
    control, _sessions, _session_calls, _http_calls, responses = native
    control._protect("task-a", "bitwarden", True)
    op = str(uuid.uuid4())
    responses[("POST", "/tabs/tab-a/passkey/approve")] = {
        "ok": False, "state": "rejected", "errorCode": "blacklist_denied",
    }
    result = _j(control, "bitwarden_approve_passkey", {"operationId": op})
    assert result == {"success": False, "state": "rejected", "errorCode": "blacklist_denied"}
    assert control.preserve_task("task-a") is True
    control._protect("task-a", "bitwarden", False)
    assert control.preserve_task("task-a") is False


@pytest.mark.parametrize("code,state", [
    ("blacklist_denied", "rejected"),
    ("ambiguous_account", "rejected"),
    ("unlock_lease_required", "rejected"),
    ("verification_required", "verification_required"),
    ("approval_uncertain", "approval_uncertain"),
])
def test_passkey_http_errors_return_only_typed_allowlisted_outcomes(native, code, state):
    control, _sessions, _session_calls, _http_calls, responses = native

    class FakeResponse:
        status_code = 409

        @staticmethod
        def json():
            return {"errorCode": code, "privateDetail": "must not be returned"}

    failure = requests.HTTPError("private HTTP body")
    failure.response = FakeResponse()
    responses[("POST", "/tabs/tab-a/passkey/approve")] = failure
    result = _j(control, "bitwarden_approve_passkey", {"operationId": str(uuid.uuid4())})
    assert result["success"] is False and result["state"] == state
    assert result["errorCode"] == code
    assert "privateDetail" not in repr(result) and "private HTTP body" not in repr(result)


def test_verified_vault_lock_releases_passkey_hold_but_preserves_human_handoff(native):
    control, _sessions, _session_calls, _http_calls, responses = native
    responses[("POST", "/tabs/tab-a/handoff")] = {
        "ok": True, "state": "needs_human", "leaseId": str(uuid.uuid4()),
        "reason": "mfa", "expiresAt": "2030-01-01T00:00:00Z",
    }
    assert _j(control, "request_handoff", {"reason": "mfa"})["state"] == "needs_human"
    responses[("POST", "/tabs/tab-a/passkey/approve")] = {
        "ok": False, "state": "verification_required",
    }
    assert _j(control, "bitwarden_approve_passkey", {"operationId": str(uuid.uuid4())})["state"] == "verification_required"
    assert control.preserve_task("task-a") is True

    responses[("POST", "/bitwarden/status")] = {"ok": True, "state": "locked"}
    assert _j(control, "bitwarden_status", {})["state"] == "locked"
    assert control.preserve_task("task-a") is True  # The website handoff is a separate reason.

    responses[("GET", "/tabs/tab-a/handoff")] = {"ok": True, "state": "automation"}
    assert _j(control, "handoff_status", {})["success"] is True
    assert control.preserve_task("task-a") is False


@pytest.mark.parametrize("bad_field,bad_value", [
    ("operationId", "not-a-uuid"),
    ("browserInstance", "not-a-uuid"),
])
def test_unlock_refuses_nonopaque_server_ids_before_helper(native, monkeypatch, bad_field, bad_value):
    control, _sessions, _session_calls, http_calls, responses = native
    payload = {
        "ok": True, "state": "awaiting_secret",
        "operationId": str(uuid.uuid4()), "browserInstance": str(uuid.uuid4()),
    }
    payload[bad_field] = bad_value
    responses[("POST", "/bitwarden/unlock")] = payload
    executed = []
    monkeypatch.setattr(control.subprocess, "run", lambda *a, **kw: executed.append((a, kw)))

    result = _j(control, "bitwarden_unlock", {})

    assert result["success"] is False
    assert result.get("errorCode") == "invalid_response"
    assert executed == []
    expected_paths = ["/bitwarden/unlock"]
    if bad_field == "browserInstance":
        expected_paths.append("/bitwarden/cancel")
        responses[("POST", "/bitwarden/cancel")] = {
            "ok": True, "state": "cancelled", "operationId": payload["operationId"],
        }
    assert [path for _method, path, _kwargs in http_calls] == expected_paths


def test_unlock_dispatch_uses_fixed_argv_and_never_returns_child_output(native, monkeypatch):
    control, _sessions, _session_calls, http_calls, responses = native
    operation_id, browser_instance = str(uuid.uuid4()), str(uuid.uuid4())
    responses[("POST", "/bitwarden/unlock")] = {
        "ok": True, "state": "awaiting_secret", "operationId": operation_id,
        "browserInstance": browser_instance,
    }
    responses[("GET", f"/bitwarden/operations/{operation_id}")] = {
        "ok": True, "state": "unlocked", "operationId": operation_id,
        "browserInstance": browser_instance,
    }
    child_calls = []

    def run(argv, **kwargs):
        child_calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout="private child stdout", stderr="private child stderr")

    monkeypatch.setattr(control.subprocess, "run", run)
    result = _j(control, "bitwarden_unlock", {"ttlSeconds": 90})

    assert result["success"] is True and result["state"] == "unlocked"
    assert "private child stdout" not in repr(result)
    assert "private child stderr" not in repr(result)
    assert child_calls == [(
        ["/usr/bin/python3", "/opt/camofox-extension-broker/request-unlock.py",
         "--operation-id", operation_id, "--browser-instance", browser_instance],
        {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
         "stderr": subprocess.DEVNULL, "timeout": 90, "check": False},
    )]
    assert http_calls[0][1] == "/bitwarden/unlock"
    assert http_calls[0][2]["body"] == {"userId": "user-a", "ttlSeconds": 90}
    assert http_calls[1][1] == f"/bitwarden/operations/{operation_id}"


def test_passkey_pending_status_is_valid_and_keeps_bitwarden_task_protection(native):
    control, _sessions, _session_calls, _http_calls, responses = native
    responses[("POST", "/bitwarden/status")] = {
        "ok": True, "state": "passkey_pending", "scope": "browser",
    }

    pending = _j(control, "bitwarden_status")

    assert pending["success"] is True and pending["state"] == "passkey_pending"
    assert control.preserve_task("task-a") is True

    responses[("POST", "/bitwarden/status")] = {
        "ok": True, "state": "locked", "scope": "browser",
    }
    locked = _j(control, "bitwarden_status")
    assert locked["success"] is True and locked["state"] == "locked"
    assert control.preserve_task("task-a") is False


def test_controller_arm_failure_code_survives_unlock_status_sanitization(native, monkeypatch):
    control, _sessions, _session_calls, http_calls, responses = native
    operation_id, browser_instance = str(uuid.uuid4()), str(uuid.uuid4())
    responses[("POST", "/bitwarden/unlock")] = {
        "ok": True, "state": "awaiting_secret", "operationId": operation_id,
        "browserInstance": browser_instance,
    }
    responses[("GET", f"/bitwarden/operations/{operation_id}")] = {
        "ok": False, "state": "unavailable", "errorCode": "approval_unavailable",
        "operationId": operation_id, "browserInstance": browser_instance,
    }
    monkeypatch.setattr(control.subprocess, "run", lambda *_a, **_k: subprocess.CompletedProcess([], 0))

    result = _j(control, "bitwarden_unlock", {})

    assert result["success"] is False
    assert result["state"] == "unavailable"
    assert result["errorCode"] == "approval_unavailable"
    assert control.preserve_task("task-a") is True
    assert [path for _method, path, _kwargs in http_calls] == [
        "/bitwarden/unlock", f"/bitwarden/operations/{operation_id}"
    ]


@pytest.mark.parametrize("failure", [
    subprocess.TimeoutExpired("fixed", 90, output="raw timeout output", stderr="raw timeout error"),
    OSError("raw dispatcher failure"),
])
def test_dispatch_failure_is_sanitized_and_cancels_the_created_operation(native, monkeypatch, failure):
    control, _sessions, _session_calls, http_calls, responses = native
    operation_id, browser_instance = str(uuid.uuid4()), str(uuid.uuid4())
    responses[("POST", "/bitwarden/unlock")] = {
        "ok": True, "state": "awaiting_secret", "operationId": operation_id,
        "browserInstance": browser_instance,
    }
    responses[("POST", "/bitwarden/cancel")] = {
        "ok": True, "state": "cancelled", "operationId": operation_id,
    }

    def fail(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr(control.subprocess, "run", fail)
    result = _j(control, "bitwarden_unlock", {})

    assert result["success"] is False
    assert result.get("errorCode") in {
        "owner_delivery_timeout", "owner_delivery_failed", "owner_delivery_unavailable",
    }
    assert "raw" not in repr(result)
    assert [path for _method, path, _kwargs in http_calls] == [
        "/bitwarden/unlock", "/bitwarden/cancel"
    ]
    assert http_calls[-1][2]["body"] == {"userId": "user-a", "operationId": operation_id}


def test_resume_requires_both_human_confirmation_and_the_canonical_live_lease(native):
    control, _sessions, _session_calls, http_calls, responses = native
    lease_id = str(uuid.uuid4())
    path = "/tabs/tab-a/handoff/resume"
    responses[("POST", path)] = {
        "ok": True, "state": "ready_to_resume", "leaseId": lease_id,
        "focused": True, "verification": {"confirmed": True},
    }

    missing_confirmation = _j(control, "resume_handoff", {"leaseId": lease_id})
    false_confirmation = _j(control, "resume_handoff", {"leaseId": lease_id, "humanConfirmed": False})
    bad_lease = _j(control, "resume_handoff", {"leaseId": "not-a-uuid", "humanConfirmed": True})
    assert missing_confirmation["success"] is False
    assert false_confirmation["success"] is False
    assert bad_lease["success"] is False
    assert http_calls == []

    accepted = _j(control, "resume_handoff", {"leaseId": lease_id, "humanConfirmed": True})
    assert accepted["success"] is True
    assert http_calls[-1][1] == path
    assert http_calls[-1][2]["body"] == {
        "userId": "user-a", "leaseId": lease_id, "humanConfirmed": True,
    }


def test_renewal_requires_lease_and_request_uses_supported_handoff_reason(native):
    control, _sessions, _session_calls, http_calls, responses = native
    lease_id = str(uuid.uuid4())
    responses[("POST", "/tabs/tab-a/handoff")] = {
        "ok": True, "state": "needs_human", "leaseId": lease_id,
        "reason": "mfa", "expiresAt": "2030-01-01T00:00:00Z",
    }
    responses[("POST", "/tabs/tab-a/handoff/renew")] = {
        "ok": True, "state": "human_control", "leaseId": lease_id,
        "expiresAt": "2030-01-01T00:01:00Z",
    }

    no_lease = _j(control, "renew_handoff", {})
    bad_reason = _j(control, "request_handoff", {"reason": "arbitrary"})
    assert no_lease["success"] is False
    assert bad_reason["success"] is False
    assert http_calls == []

    requested = _j(control, "request_handoff", {"reason": "mfa", "ttlSeconds": 60})
    renewed = _j(control, "renew_handoff", {"leaseId": lease_id, "ttlSeconds": 90})
    assert requested["success"] is True and requested["state"] == "needs_human"
    assert renewed["success"] is True and renewed["state"] == "human_control"
    assert [path for _method, path, _kwargs in http_calls] == [
        "/tabs/tab-a/handoff", "/tabs/tab-a/handoff/renew"
    ]


@pytest.mark.parametrize("action,path,method,args,response", [
    ("bitwarden_status", "/bitwarden/status", "POST", {}, {"ok": True, "state": "locked"}),
    ("bitwarden_lock", "/bitwarden/lock", "POST", {}, {"ok": True, "state": "locked"}),
    ("handoff_status", "/tabs/tab-a/handoff", "GET", {}, {"ok": True, "state": "automation"}),
    ("focus_tab", "/tabs/tab-a/focus", "POST", {},
     {"ok": True, "state": "automation", "focused": True}),
])
def test_native_actions_use_canonical_routes(native, action, path, method, args, response):
    control, _sessions, _session_calls, http_calls, responses = native
    responses[(method, path)] = response

    result = _j(control, action, args)

    assert result["success"] is True
    assert [(m, p) for m, p, _ in http_calls] == [(method, path)]
    if method == "POST":
        assert http_calls[0][2]["body"].get("userId") == "user-a"


@pytest.mark.parametrize("action,path,response", [
    ("bitwarden_status", "/bitwarden/status", {"ok": True}),
    ("bitwarden_status", "/bitwarden/status", {"ok": True, "state": "imaginary"}),
    ("handoff_status", "/tabs/tab-a/handoff", {"ok": True, "state": "complete"}),
])
def test_unknown_or_incomplete_server_states_fail_closed(native, action, path, response):
    control, _sessions, _session_calls, http_calls, responses = native
    method = "GET" if action == "handoff_status" else "POST"
    responses[(method, path)] = response

    result = _j(control, action, {})

    assert result["success"] is False
    assert result.get("errorCode") == "invalid_response"
    assert len(http_calls) == 1


def test_server_extras_are_not_exposed_to_the_model(native):
    control, _sessions, _session_calls, _http_calls, responses = native
    responses[("POST", "/bitwarden/status")] = {
        "ok": True, "state": "locked", "scope": "current", "privateDiagnostic": "sensitive-server-detail",
    }

    result = _j(control, "bitwarden_status", {})

    assert result["success"] is True
    assert result["state"] == "locked"
    assert "privateDiagnostic" not in result
    assert "sensitive-server-detail" not in repr(result)


def test_http_error_decoding_preserves_typed_cleanup_failure(native):
    control, _sessions, _session_calls, _http_calls, responses = native

    class FakeResponse:
        status_code = 409

        @staticmethod
        def json():
            return {"ok": False, "state": "lock_failed", "errorCode": "cleanup_failed"}

    failure = requests.HTTPError("sensitive error response detail")
    failure.response = FakeResponse()
    responses[("POST", "/bitwarden/lock")] = failure

    result = _j(control, "bitwarden_lock", {})

    assert result == {"success": False, "state": "lock_failed", "errorCode": "cleanup_failed"}
    assert "sensitive error response detail" not in repr(result)


def test_handoff_protection_starts_before_uncertain_http_and_tracks_independently(native, monkeypatch):
    control, _sessions, _session_calls, _http_calls, responses = native
    original_post = control.client.post

    def timeout_after_protection(path, body=None, **kwargs):
        if path == "/tabs/tab-a/handoff":
            assert control.preserve_task("task-a") is True
            raise requests.Timeout("private timeout detail")
        return original_post(path, body, **kwargs)

    monkeypatch.setattr(control.client, "post", timeout_after_protection)
    uncertain = _j(control, "request_handoff", {"reason": "mfa"})
    assert uncertain["success"] is False
    assert uncertain.get("errorCode") == "control_unavailable"
    assert "private timeout detail" not in repr(uncertain)
    assert control.preserve_task("task-a") is True

    # Bitwarden 2FA and the website's human handoff own separate cleanup holds.
    responses[("POST", "/bitwarden/status")] = {"ok": True, "state": "two_factor_required"}
    assert _j(control, "bitwarden_status", {})["state"] == "two_factor_required"
    assert control.preserve_task("task-a") is True

    responses[("POST", "/bitwarden/status")] = {"ok": True, "state": "cancelled"}
    assert _j(control, "bitwarden_status", {})["success"] is True
    assert control.preserve_task("task-a") is True

    responses[("GET", "/tabs/tab-a/handoff")] = {"ok": True, "state": "automation"}
    handoff = _j(control, "handoff_status", {})
    assert handoff["success"] is True
    assert control.preserve_task("task-a") is True

    responses[("POST", "/bitwarden/status")] = {"ok": True, "state": "locked"}
    assert _j(control, "bitwarden_status", {})["success"] is True
    assert control.preserve_task("task-a") is False


@pytest.mark.parametrize("status,payload,expected", [
    (409, {"ok": False, "state": "lock_failed", "errorCode": "cleanup_failed"}, "cleanup_failed"),
    (401, {"error": "secret response detail"}, "authentication_required"),
    (503, {"error": "secret response detail"}, "control_unavailable"),
])
def test_http_failures_return_only_allowlisted_typed_codes(native, status, payload, expected):
    control, _sessions, _session_calls, _http_calls, responses = native

    class FakeResponse:
        status_code = status

        def json(self):
            return payload

    failure = requests.HTTPError("private response text and secret detail")
    failure.response = FakeResponse()
    responses[("POST", "/bitwarden/status")] = failure

    result = _j(control, "bitwarden_status", {})

    assert result["success"] is False
    assert result.get("errorCode") == expected
    assert "private response text" not in repr(result)
    assert "secret response detail" not in repr(result)


def test_uncertain_handoff_is_protected_before_http_and_independent_of_bitwarden_2fa(native, monkeypatch):
    control, _sessions, _session_calls, _http_calls, responses = native
    original_post = control.client.post

    def timeout_after_protection(path, body=None, **kwargs):
        if path == "/tabs/tab-a/handoff":
            assert control.preserve_task("task-a") is True
            raise requests.Timeout("private timeout detail")
        return original_post(path, body, **kwargs)

    monkeypatch.setattr(control.client, "post", timeout_after_protection)
    uncertain = _j(control, "request_handoff", {"reason": "mfa"})
    assert uncertain["success"] is False
    assert uncertain.get("errorCode") == "control_unavailable"
    assert "private timeout detail" not in repr(uncertain)
    assert control.preserve_task("task-a") is True

    # Bitwarden 2FA is tracked separately; a verified web handoff clear must not release its hold.
    responses[("POST", "/bitwarden/status")] = {"ok": True, "state": "two_factor_required"}
    status = _j(control, "bitwarden_status", {})
    assert status["state"] == "two_factor_required"
    assert control.preserve_task("task-a") is True

    responses[("GET", "/tabs/tab-a/handoff")] = {"ok": True, "state": "automation"}
    handoff_status = _j(control, "handoff_status", {})
    assert handoff_status["success"] is True
    assert control.preserve_task("task-a") is True

    responses[("POST", "/bitwarden/status")] = {"ok": True, "state": "locked"}
    locked = _j(control, "bitwarden_status", {})
    assert locked["success"] is True
    assert control.preserve_task("task-a") is False
