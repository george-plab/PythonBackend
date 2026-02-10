import uuid

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from services.service_usage import UsageService


def _make_request(cookie_header: str | None = None) -> Request:
    headers = []
    if cookie_header is not None:
        headers.append((b"cookie", cookie_header.encode("ascii")))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "method": "POST",
        "path": "/api/chat",
        "headers": headers,
        "query_string": b"",
        "client": ("testclient", 123),
        "server": ("testserver", 80),
        "scheme": "http",
        "root_path": "",
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


def test_ensure_guest_id_sets_cookie_when_missing():
    usage = UsageService(debug=True, guest_cookie_name="oms_guest")
    request = _make_request()
    response = Response()
    guest_id = usage.ensure_guest_id(request, response)
    uuid.UUID(guest_id)
    set_cookie = response.headers.get("set-cookie")
    assert set_cookie is not None
    set_cookie_lower = set_cookie.lower()
    assert "oms_guest=" in set_cookie_lower
    assert "httponly" in set_cookie_lower
    assert "samesite=lax" in set_cookie_lower
    assert "secure" not in set_cookie_lower


def test_ensure_guest_id_returns_existing_cookie_without_setting_new():
    usage = UsageService(debug=True, guest_cookie_name="oms_guest")
    request = _make_request("oms_guest=existing-123")
    response = Response()
    guest_id = usage.ensure_guest_id(request, response)
    assert guest_id == "existing-123"
    assert response.headers.get("set-cookie") is None


def test_count_user_turns_counts_history_plus_one():
    usage = UsageService()
    history = [
        {"role": "assistant", "content": "a"},
        {"role": "user", "content": "u1"},
        {"role": "user", "content": "u2"},
    ]
    assert usage.count_user_turns(history) == 3


def test_enforce_anon_limit_raises_402_with_paywall_payload():
    usage = UsageService(anon_message_limit=10)
    with pytest.raises(HTTPException) as excinfo:
        usage.enforce_anon_limit(11)
    exc = excinfo.value
    assert exc.status_code == 402
    assert isinstance(exc.detail, dict)
    assert exc.detail["error"] == "PAYWALL"
    assert exc.detail["reason"] == "ANON_LIMIT_REACHED"
    assert exc.detail["anon_limit"]["messages"] == 10
    assert exc.detail["usage"]["messages"] == 11


def test_ensure_guest_id_prod_cookie_has_secure_and_none_samesite():
    usage = UsageService(debug=False, guest_cookie_name="oms_guest")
    request = _make_request()
    response = Response()
    usage.ensure_guest_id(request, response)
    set_cookie = response.headers.get("set-cookie")
    assert set_cookie is not None
    set_cookie_lower = set_cookie.lower()
    assert "samesite=none" in set_cookie_lower
    assert "secure" in set_cookie_lower
