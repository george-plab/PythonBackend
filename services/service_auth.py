"""Authentication and session utilities for FastAPI."""
from __future__ import annotations

import os


from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token


class GoogleAuthIn(BaseModel):
    """Payload for Google authentication."""

    credential: str


class AuthService:
    """Handle session serialization, cookies, and auth helpers."""

    def __init__(
        self,
        *,
        debug: bool | None = None,
        cookie_name: str = "oms_session",
        session_max_age_seconds: int = 7 * 24 * 60 * 60,
    ) -> None:
        self.debug = (os.getenv("DEBUG", "").lower() == "true") if debug is None else debug
        self.cookie_name = cookie_name
        self.session_max_age_seconds = session_max_age_seconds
        self._serializer = self._build_serializer()

    def _build_serializer(self) -> URLSafeTimedSerializer:
        secret = os.getenv("SESSION_SECRET")
        if not secret:
            raise HTTPException(status_code=500, detail="SESSION_SECRET missing")
        return URLSafeTimedSerializer(secret, salt="oms-session")

    def _cookie_base_params(self) -> dict:
        if self.debug:
            secure = False
            samesite = "lax"
        else:
            secure = True
            samesite = "none"
        return {
            "secure": secure,
            "samesite": samesite,
            "path": "/",
        }

    def _cookie_params(self) -> dict:
        params = self._cookie_base_params()
        params["httponly"] = True
        return params

    def _cookie_delete_params(self) -> dict:
        return self._cookie_base_params()

    def _load_session_from_cookie(self, cookie_value: str | None) -> dict | None:
        if not cookie_value:
            return None
        try:
            return self._serializer.loads(cookie_value, max_age=self.session_max_age_seconds)
        except (BadSignature, SignatureExpired):
            return None

    def get_current_user(self, request: Request) -> dict | None:
        """Return current user from session cookie, if any."""

        return self._load_session_from_cookie(request.cookies.get(self.cookie_name))

    def require_auth(self, user: dict | None) -> dict:
        """Require an authenticated user or raise 401."""

        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return user

    def set_session_cookie(self, response: Response, user: dict) -> None:
        session_value = self._serializer.dumps(user)
        response.set_cookie(key=self.cookie_name, value=session_value, **self._cookie_params())

    def clear_session_cookie(self, response: Response) -> None:
        response.delete_cookie(key=self.cookie_name, **self._cookie_delete_params())

    def auth_google(self, payload: GoogleAuthIn) -> Response:
        """Validate Google credential and issue session cookie."""

        client_id = os.getenv("GOOGLE_CLIENT_ID")
        if not client_id:
            raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID missing")

        try:
            id_info = google_id_token.verify_oauth2_token(
                payload.credential,
                google_requests.Request(),
                audience=client_id,
            )
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid Google credential")

        user = {
            "sub": id_info.get("sub"),
            "email": id_info.get("email"),
            "name": id_info.get("name"),
            "picture": id_info.get("picture"),
        }

        response = JSONResponse({"ok": True, "user": user})
        self.set_session_cookie(response, user)
        return response

    def get_me(self, user: dict) -> dict:
        """Return the current user payload."""

        return {"ok": True, "user": user}

    def logout(self, response: Response) -> dict:
        """Clear session cookie and return ok."""

        self.clear_session_cookie(response)
        return {"ok": True}
