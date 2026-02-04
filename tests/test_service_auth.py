import os

import pytest
from fastapi import HTTPException, Response

os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("DEBUG", "false")

from services import service_auth


def test_missing_session_secret_raises_500(monkeypatch):
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    with pytest.raises(HTTPException) as excinfo:
        service_auth.AuthService()
    assert excinfo.value.status_code == 500
    assert excinfo.value.detail == "SESSION_SECRET missing"


def test_cookie_params_debug_mode(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "debug-secret")
    monkeypatch.setenv("DEBUG", "true")
    auth = service_auth.AuthService()
    params = auth._cookie_params()
    assert params["secure"] is False
    assert params["samesite"] == "lax"
    assert params["path"] == "/"
    assert params["httponly"] is True


def test_cookie_params_prod_mode(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "prod-secret")
    monkeypatch.setenv("DEBUG", "false")
    auth = service_auth.AuthService()
    params = auth._cookie_params()
    assert params["secure"] is True
    assert params["samesite"] == "none"
    assert params["path"] == "/"
    assert params["httponly"] is True


def test_session_roundtrip_load_ok(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "roundtrip-secret")
    auth = service_auth.AuthService()
    user = {"sub": "123", "email": "test@example.com"}
    cookie_value = auth._serializer.dumps(user)
    loaded = auth._load_session_from_cookie(cookie_value)
    assert loaded == user


def test_load_session_invalid_returns_none(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "invalid-secret")
    auth = service_auth.AuthService()
    assert auth._load_session_from_cookie("not-a-valid-cookie") is None


def test_require_auth_raises_401_when_no_user(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "auth-secret")
    auth = service_auth.AuthService()
    with pytest.raises(HTTPException) as excinfo:
        auth.require_auth(None)
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "Not authenticated"


def test_logout_deletes_cookie(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "logout-secret")
    monkeypatch.setenv("DEBUG", "false")
    auth = service_auth.AuthService()
    response = Response()
    auth.logout(response)
    header = response.headers.get("set-cookie")
    assert header is not None
    assert service_auth.COOKIE_NAME in header
    header_lower = header.lower()
    assert "max-age=0" in header_lower or "expires=" in header_lower
    assert "path=/" in header_lower
    assert "samesite=none" in header_lower
    assert "secure" in header_lower
