import os
import base64
import json
import sys
import types

import pytest
from fastapi import HTTPException, Response


def _ensure_itsdangerous_available() -> None:
    try:
        import itsdangerous  # noqa: F401
    except ModuleNotFoundError:
        itsdangerous = types.ModuleType("itsdangerous")

        class BadSignature(Exception):
            pass

        class SignatureExpired(Exception):
            pass

        class URLSafeTimedSerializer:
            def __init__(self, secret: str, salt: str | None = None) -> None:
                self._secret = secret
                self._salt = salt

            def dumps(self, obj: dict) -> str:
                payload = json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
                return base64.urlsafe_b64encode(payload).decode("ascii")

            def loads(self, value: str, max_age: int | None = None) -> dict:
                try:
                    payload = base64.urlsafe_b64decode(value.encode("ascii"))
                    return json.loads(payload.decode("utf-8"))
                except Exception as exc:  # pragma: no cover
                    raise BadSignature("Invalid") from exc

        itsdangerous.BadSignature = BadSignature
        itsdangerous.SignatureExpired = SignatureExpired
        itsdangerous.URLSafeTimedSerializer = URLSafeTimedSerializer
        sys.modules["itsdangerous"] = itsdangerous


def _ensure_google_auth_available() -> None:
    try:
        import google.auth.transport.requests  # noqa: F401
        import google.oauth2.id_token  # noqa: F401
    except ModuleNotFoundError:
        google = sys.modules.get("google") or types.ModuleType("google")
        sys.modules["google"] = google

        google_auth = types.ModuleType("google.auth")
        google_transport = types.ModuleType("google.auth.transport")
        google_requests = types.ModuleType("google.auth.transport.requests")

        class Request:
            pass

        google_requests.Request = Request

        google_oauth2 = types.ModuleType("google.oauth2")
        google_id_token = types.ModuleType("google.oauth2.id_token")

        def verify_oauth2_token(*args, **kwargs):
            raise ValueError("stub")

        google_id_token.verify_oauth2_token = verify_oauth2_token

        sys.modules["google.auth"] = google_auth
        sys.modules["google.auth.transport"] = google_transport
        sys.modules["google.auth.transport.requests"] = google_requests
        sys.modules["google.oauth2"] = google_oauth2
        sys.modules["google.oauth2.id_token"] = google_id_token

        google.auth = google_auth
        google_auth.transport = google_transport
        google_transport.requests = google_requests
        google.oauth2 = google_oauth2
        google_oauth2.id_token = google_id_token


_ensure_itsdangerous_available()
_ensure_google_auth_available()

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
    assert auth.cookie_name in header
    header_lower = header.lower()
    assert "max-age=0" in header_lower or "expires=" in header_lower
    assert "path=/" in header_lower
    assert "samesite=none" in header_lower
    assert "secure" in header_lower


def test_auth_google_missing_client_id_raises_500(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "google-secret")
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    auth = service_auth.AuthService()
    with pytest.raises(HTTPException) as excinfo:
        auth.auth_google(service_auth.GoogleAuthIn(credential="x"))
    assert excinfo.value.status_code == 500
    assert excinfo.value.detail == "GOOGLE_CLIENT_ID missing"


def test_auth_google_sets_session_cookie(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "google-secret")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id")

    def fake_verify(credential, request, audience):
        assert credential == "cred"
        assert audience == "client-id"
        return {
            "sub": "sub-123",
            "email": "user@example.com",
            "name": "User",
            "picture": "https://example.com/p.png",
        }

    monkeypatch.setattr(service_auth.google_id_token, "verify_oauth2_token", fake_verify)

    auth = service_auth.AuthService()
    response = auth.auth_google(service_auth.GoogleAuthIn(credential="cred"))
    set_cookie = response.headers.get("set-cookie")
    assert set_cookie is not None
    assert auth.cookie_name in set_cookie
