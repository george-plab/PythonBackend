from __future__ import annotations

import os
from uuid import uuid4

from fastapi import HTTPException, Request, Response

class UsageService:
    def __init__(
        self,
        *,
        debug: bool | None = None,
        guest_cookie_name: str = "oms_guest",
        anon_message_limit: int = 10,
        auth_message_limit: int =100,
    ) -> None:
        self.debug = (os.getenv("DEBUG", "").lower() == "true") if debug is None else debug
        self.guest_cookie_name = guest_cookie_name
        self.anon_message_limit = anon_message_limit
        self.auth_message_limit = auth_message_limit

    def _cookie_params(self) -> dict:
        if self.debug:
            secure = False
            samesite = "lax"
        else:
            secure = True
            samesite = "none"
        return {
            "path": "/",
            "httponly": True,
            "secure": secure,
            "samesite": samesite,
        }

    def ensure_guest_id(self, request: Request, response: Response) -> str:
        guest_id = request.cookies.get(self.guest_cookie_name)
        if guest_id:
            return guest_id
        guest_id = str(uuid4())
        response.set_cookie(key=self.guest_cookie_name, value=guest_id, **self._cookie_params())
        return guest_id

    def count_user_turns(self, history: list[dict]) -> int:
        turns = 1
        if isinstance(history, list):
            turns += sum(1 for h in history if isinstance(h, dict) and h.get("role") == "user")
        return turns

    def enforce_anon_limit(self, user_turns: int) -> None:
        if user_turns <= self.anon_message_limit:
            return

        paywall_payload = {
            "error": "PAYWALL",
            "reason": "ANON_LIMIT_REACHED",
            "anon_limit": {"messages": self.anon_message_limit},
            "usage": {"messages": user_turns},
            "actions": ["LOGIN", "WAITLIST", "UPGRADE"],
            "plans": {
                "start": {"price_eur": "17-29"},
                "premium": {"price_eur": "45"},
            },
        }
        raise HTTPException(status_code=402, detail=paywall_payload)
    
    def enforce_auth_limit(self, user_turns: int) -> None:
        if user_turns <= self.auth_message_limit:
            return

        paywall_payload = {
            "error": "PAYWALL",
            "reason": "AUTH_LIMIT_REACHED",
            "anon_limit": {"messages": self.auth_message_limit},
            "usage": {"messages": user_turns},
            "actions": ["LOGIN", "WAITLIST", "UPGRADE"],
            "plans": {
                "start": {"price_eur": "17-29"},
                "premium": {"price_eur": "45"},
            },
        }
        raise HTTPException(status_code=402, detail=paywall_payload)