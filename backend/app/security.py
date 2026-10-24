from __future__ import annotations

import hmac
import os
from typing import Callable

from fastapi import Depends, HTTPException, Request, Response

from app.services.auth import lookup_session

SESSION_COOKIE = "trustflow_session"


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=os.getenv("TRUSTFLOW_ENV", "development").lower() == "production",
        samesite="lax",
        path="/",
        max_age=12 * 3600,
    )


def get_current_user(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    user = lookup_session(token) if token else None
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_csrf(
    request: Request, user: dict = Depends(get_current_user)
) -> dict:
    supplied = request.headers.get("x-csrf-token", "")
    expected = user.get("csrf_token", "")
    if not supplied or not expected or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=403, detail="CSRF validation failed")
    origin = request.headers.get("origin")
    if origin:
        allowed = {
            item.strip()
            for item in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",")
            if item.strip()
        }
        if origin not in allowed:
            raise HTTPException(status_code=403, detail="Origin is not allowed")
    return user


def require_role(role: str) -> Callable:
    def dependency(user: dict = Depends(require_csrf)) -> dict:
        if user["role"] != role:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user

    return dependency
