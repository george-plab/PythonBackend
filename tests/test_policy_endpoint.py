import importlib
import sys

import pytest
from starlette.requests import Request
from starlette.responses import Response


def _make_request(cookie_header: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if cookie_header is not None:
        headers.append((b"cookie", cookie_header.encode("ascii")))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "method": "GET",
        "path": "/api/me/policy",
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


def _import_main(monkeypatch, *, anon_limit: str = "10", auth_limit: str = "100"):
    import dotenv

    original_load_dotenv = dotenv.load_dotenv
    noop_load_dotenv = lambda *args, **kwargs: True
    monkeypatch.setattr(dotenv, "load_dotenv", noop_load_dotenv)
    llmsettings_mod = sys.modules.get("services.llmsettings")
    if llmsettings_mod is not None:
        monkeypatch.setattr(llmsettings_mod, "load_dotenv", noop_load_dotenv)
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    monkeypatch.setenv("COOKIE_NAME", "oms_session")
    monkeypatch.setenv("SESSIOM_MAX_AGE_SECONDS", "86400")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("ANON_MESSAGE_LIMIT", anon_limit)
    monkeypatch.setenv("AUTH_MESSAGE_LIMIT", auth_limit)

    sys.modules.pop("main", None)
    main = importlib.import_module("main")
    main.load_dotenv = original_load_dotenv
    llmsettings_mod = sys.modules.get("services.llmsettings")
    if llmsettings_mod is not None:
        llmsettings_mod.load_dotenv = original_load_dotenv
    return main


def _extract_cookie_value(set_cookie_header: str, *, cookie_name: str) -> str:
    prefix = f"{cookie_name}="
    parts = set_cookie_header.split(";", 1)[0]
    assert parts.startswith(prefix)
    return parts[len(prefix) :]


def test_policy_returns_anon_limits_when_not_authenticated(monkeypatch):
    main = _import_main(monkeypatch, anon_limit="7", auth_limit="99")
    payload = main.get_me_policy(_make_request())

    assert payload["ok"] is True
    assert payload["isAuthenticated"] is False
    assert payload["maxMessages"] == 7
    assert payload["limits"]["anon"]["messages"] == 7
    assert payload["limits"]["auth"]["messages"] == 99
    assert "user" not in payload


def test_policy_returns_auth_limits_and_user_when_authenticated(monkeypatch):
    main = _import_main(monkeypatch, anon_limit="7", auth_limit="99")
    user = {"email": "a@example.com", "name": "Alice", "picture": "https://example.com/p.png"}
    resp = Response()
    main.auth_service.set_session_cookie(resp, user)
    cookie_value = _extract_cookie_value(resp.headers["set-cookie"], cookie_name="oms_session")

    payload = main.get_me_policy(_make_request(f"oms_session={cookie_value}"))

    assert payload["ok"] is True
    assert payload["isAuthenticated"] is True
    assert payload["maxMessages"] == 99
    assert payload["limits"]["anon"]["messages"] == 7
    assert payload["limits"]["auth"]["messages"] == 99
    assert payload["user"]["email"] == "a@example.com"
    assert payload["user"]["name"] == "Alice"
    assert payload["user"]["picture"] == "https://example.com/p.png"


def test_policy_never_raises_when_auth_service_missing(monkeypatch):
    main = _import_main(monkeypatch, anon_limit="7", auth_limit="99")
    main.auth_service = None

    payload = main.get_me_policy(_make_request("oms_session=anything"))

    assert payload["ok"] is True
    assert payload["isAuthenticated"] is False
    assert payload["maxMessages"] == 7
