from __future__ import annotations

import os
import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.observability import log_event
from app.security import SESSION_COOKIE, allowed_origins, get_current_user, require_csrf, set_session_cookie
from app.services import auth
from app.services import paypal_onboarding
from app.services.email import email_delivery_configured, send_password_reset_email, send_verification_email

router = APIRouter(prefix="/auth", tags=["auth"])
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class SignupBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)
    role: str


class LoginBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class EmailBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class VerifyEmailBody(BaseModel):
    token: str = Field(min_length=32, max_length=128)


class PasswordResetBody(BaseModel):
    token: str = Field(min_length=32, max_length=128)
    password: str = Field(min_length=12, max_length=128)


class PayPalOnboardingCompleteBody(BaseModel):
    tracking_id: str = Field(min_length=16, max_length=64)
    merchant_id: str = Field(min_length=3, max_length=64)
    permissions_granted: bool
    consent_status: bool


def _normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not EMAIL_RE.fullmatch(email):
        raise HTTPException(status_code=422, detail="Enter a valid email address")
    return email


def _check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin:
        return
    if origin.rstrip("/") not in allowed_origins():
        raise HTTPException(status_code=403, detail="Origin is not allowed")


def _auth_email_delivery_configured() -> bool:
    return email_delivery_configured()


@router.post("/signup", status_code=201)
def signup(body: SignupBody, request: Request, response: Response) -> dict:
    _check_origin(request)
    if body.role not in {"client", "freelancer"}:
        raise HTTPException(status_code=422, detail="Role must be client or freelancer")
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="Name cannot be blank")
    email = _normalize_email(body.email)
    if email_delivery_configured():
        try:
            user, verification_token = auth.create_pending_user(email, body.name.strip(), body.password, body.role)
        except Exception as error:
            if "unique" in str(error).lower() or "duplicate" in str(error).lower():
                raise HTTPException(status_code=409, detail="An account with this email already exists") from error
            raise
        try:
            sent = send_verification_email(email, user["name"], verification_token)
        except Exception:
            sent = False
        return {
            "verification_required": True,
            "email": email,
            "email_sent": sent,
            "message": "Check your inbox for a confirmation link." if sent else "Your account is ready, but the confirmation email could not be sent. Try resending it.",
        }
    if os.getenv("TRUSTFLOW_ENV", "development").lower() == "production":
        raise HTTPException(status_code=503, detail="Email confirmation is required but email delivery is not configured")
    try:
        user, token, csrf = auth.create_user(email, body.name.strip(), body.password, body.role)
    except Exception as error:
        if "unique" in str(error).lower() or "duplicate" in str(error).lower():
            raise HTTPException(status_code=409, detail="An account with this email already exists") from error
        raise
    set_session_cookie(response, token)
    return {"user": user, "csrf_token": csrf, "email_confirmation_enabled": False}


@router.post("/verify-email")
def verify_email(body: VerifyEmailBody, request: Request) -> dict:
    _check_origin(request)
    if not auth.verify_email_token(body.token):
        raise HTTPException(status_code=400, detail="This confirmation link is invalid, expired, or already used")
    return {"verified": True}


@router.post("/resend-verification", status_code=202)
def resend_verification(body: EmailBody, request: Request) -> dict:
    _check_origin(request)
    email = _normalize_email(body.email)
    token_data = auth.create_verification_token(email) if email_delivery_configured() else None
    if token_data:
        name, token = token_data
        try:
            send_verification_email(email, name, token)
        except Exception as error:
            log_event("warning", "email.verification.resend_failed", error=type(error).__name__)
    return {"message": "If that address has an unverified account, a confirmation email will be sent."}


@router.post("/password-reset/request", status_code=202)
def request_password_reset(body: EmailBody, request: Request) -> dict:
    _check_origin(request)
    email = _normalize_email(body.email)
    if _auth_email_delivery_configured():
        token_data = auth.create_password_reset_token(email)
        if token_data:
            name, token = token_data
            try:
                send_password_reset_email(email, name, token)
            except Exception as error:
                log_event("warning", "email.password_reset.failed", error=type(error).__name__)
    return {"message": "If a verified account uses that address, a password reset link will be sent."}


@router.post("/password-reset/confirm")
def confirm_password_reset(body: PasswordResetBody, request: Request) -> dict:
    _check_origin(request)
    if not auth.reset_password(body.token, body.password):
        raise HTTPException(status_code=400, detail="This password reset link is invalid, expired, or already used")
    return {"success": True}


@router.post("/login")
def login(body: LoginBody, request: Request, response: Response) -> dict:
    _check_origin(request)
    email = _normalize_email(body.email)
    ip = request.client.host if request.client else "unknown"
    allowed = auth.check_login_rate(email, ip)
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")
    user = auth.authenticate(email, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    if not user.get("email_verified", True):
        raise HTTPException(status_code=403, detail="Confirm your email before signing in")
    auth.clear_login_rate(email, ip)
    token, csrf = auth.create_session(user["id"])
    set_session_cookie(response, token)
    return {"user": user, "csrf_token": csrf}


@router.get("/me")
def current_user(user: dict = Depends(get_current_user)) -> dict:
    return {"user": {key: value for key, value in user.items() if key != "csrf_token"}, "csrf_token": user["csrf_token"]}


@router.post("/paypal/onboarding")
async def paypal_onboarding_start(user: dict = Depends(require_csrf)) -> dict:
    try:
        return await paypal_onboarding.start(user)
    except paypal_onboarding.DomainError as error:
        raise HTTPException(error.status_code, error.detail) from error


@router.post("/paypal/onboarding/complete")
async def paypal_onboarding_complete(body: PayPalOnboardingCompleteBody, user: dict = Depends(require_csrf)) -> dict:
    try:
        return await paypal_onboarding.complete(
            user, body.tracking_id, body.merchant_id, body.permissions_granted, body.consent_status,
        )
    except paypal_onboarding.DomainError as error:
        raise HTTPException(error.status_code, error.detail) from error


@router.post("/logout")
def logout(request: Request, response: Response, _user: dict = Depends(require_csrf)) -> dict:
    auth.revoke_session(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax")
    return {"success": True}
