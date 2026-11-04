from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.repository import transaction, read_connection

try:
    from argon2 import PasswordHasher, exceptions as argon_errors

    _password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
except ImportError:  # Local/offline development fallback; Argon2 is preferred in deployed installs.
    _password_hasher = None
    PasswordHasher = None
    argon_errors = None

SESSION_TTL_HOURS = 12
LOGIN_LIMIT = 8
LOGIN_WINDOW_MINUTES = 15


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    if _password_hasher:
        return _password_hasher.hash(password)
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**15, r=8, p=1, dklen=64, maxmem=128 * 1024 * 1024)
    return f"scrypt$32768$8$1${salt.hex()}${derived.hex()}"


_dummy_hash = hash_password("trustflow-dummy-password-for-timing")


def verify_password(encoded: str | None, password: str) -> bool:
    if (encoded or _dummy_hash).startswith("scrypt$"):
        try:
            _, n_value, r_value, p_value, salt_hex, expected_hex = (encoded or _dummy_hash).split("$", 5)
            actual = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex), n=int(n_value), r=int(r_value), p=int(p_value), dklen=len(bytes.fromhex(expected_hex)), maxmem=128 * 1024 * 1024)
            return hmac.compare_digest(actual.hex(), expected_hex) and bool(encoded)
        except (ValueError, TypeError):
            return False
    if not _password_hasher:
        return False
    candidate = encoded or _password_hasher.hash("dummy-password-for-timing")
    try:
        valid = _password_hasher.verify(candidate, password)
        return bool(valid and encoded)
    except (argon_errors.VerifyMismatchError, argon_errors.InvalidHashError):
        return False


def public_user(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "name": row.get("display_name") or "",
        "email": row["email"],
        "role": row["role"],
        "email_verified": bool(row.get("email_verified", True)),
    }


def create_user(email: str, name: str, password: str, role: str) -> tuple[dict, str, str]:
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    password_hash = hash_password(password)
    with transaction() as connection:
        row = connection.execute(
            """INSERT INTO users(email, display_name, password_hash, role)
               VALUES (%s, %s, %s, %s)
               RETURNING id, email, display_name, role""",
            (email, name, password_hash, role),
        ).fetchone()
        connection.execute(
            """INSERT INTO auth_sessions(session_hash, csrf_token, user_id, expires_at)
               VALUES (%s, %s, %s, %s)""",
            (_hash_token(token), csrf, row["id"], datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)),
        )
    return public_user(row), token, csrf


def create_pending_user(email: str, name: str, password: str, role: str) -> tuple[dict, str]:
    verification_token = secrets.token_urlsafe(32)
    password_hash = hash_password(password)
    with transaction() as connection:
        row = connection.execute(
            """INSERT INTO users(email, display_name, password_hash, role, email_verified)
               VALUES (%s, %s, %s, %s, FALSE)
               RETURNING id, email, display_name, role, email_verified""",
            (email, name, password_hash, role),
        ).fetchone()
        connection.execute(
            """INSERT INTO email_verification_tokens(token_hash, user_id, expires_at)
               VALUES (%s, %s, %s)""",
            (_hash_token(verification_token), row["id"], datetime.now(timezone.utc) + timedelta(hours=24)),
        )
    return public_user(row), verification_token


def mark_verification_email_sent(token: str) -> None:
    with transaction() as connection:
        connection.execute(
            "UPDATE email_verification_tokens SET sent_at = NOW() WHERE token_hash = %s",
            (_hash_token(token),),
        )


def create_verification_token(email: str) -> tuple[str, str] | None:
    """Return (display name, raw token), enforcing a one-minute resend cooldown."""
    with transaction() as connection:
        row = connection.execute(
            """SELECT id, display_name, email_verified FROM users
               WHERE lower(email) = lower(%s) FOR UPDATE""",
            (email,),
        ).fetchone()
        if row is None or row["email_verified"]:
            return None
        recent = connection.execute(
            """SELECT 1 FROM email_verification_tokens
               WHERE user_id = %s AND sent_at > NOW() - INTERVAL '1 minute'
               ORDER BY sent_at DESC LIMIT 1""",
            (row["id"],),
        ).fetchone()
        if recent:
            return None
        connection.execute(
            "UPDATE email_verification_tokens SET consumed_at = COALESCE(consumed_at, NOW()) WHERE user_id = %s",
            (row["id"],),
        )
        token = secrets.token_urlsafe(32)
        connection.execute(
            """INSERT INTO email_verification_tokens(token_hash, user_id, expires_at)
               VALUES (%s, %s, %s)""",
            (_hash_token(token), row["id"], datetime.now(timezone.utc) + timedelta(hours=24)),
        )
        return row.get("display_name") or "", token


def verify_email_token(token: str) -> bool:
    with transaction() as connection:
        row = connection.execute(
            """SELECT t.user_id, t.consumed_at, t.expires_at, u.email_verified
               FROM email_verification_tokens t JOIN users u ON u.id = t.user_id
               WHERE t.token_hash = %s FOR UPDATE OF t, u""",
            (_hash_token(token),),
        ).fetchone()
        if row is None:
            return False
        if row["email_verified"]:
            return True
        if row["consumed_at"] is not None or row["expires_at"] <= datetime.now(timezone.utc):
            return False
        updated = connection.execute(
            "UPDATE users SET email_verified = TRUE WHERE id = %s RETURNING id",
            (row["user_id"],),
        ).fetchone()
        if updated is None:
            return False
        connection.execute(
            "UPDATE email_verification_tokens SET consumed_at = NOW() WHERE user_id = %s AND consumed_at IS NULL",
            (row["user_id"],),
        )
    return True


def create_password_reset_token(email: str) -> tuple[str, str] | None:
    """Create a short-lived reset token for a verified account, if one may be sent."""
    with transaction() as connection:
        user = connection.execute(
            """SELECT id, display_name FROM users
               WHERE lower(email) = lower(%s) AND email_verified = TRUE FOR UPDATE""",
            (email,),
        ).fetchone()
        if user is None:
            return None
        recent = connection.execute(
            """SELECT 1 FROM password_reset_tokens
               WHERE user_id = %s AND sent_at > NOW() - INTERVAL '2 minutes'
               ORDER BY sent_at DESC LIMIT 1""",
            (user["id"],),
        ).fetchone()
        if recent:
            return None
        connection.execute(
            """UPDATE password_reset_tokens SET consumed_at = COALESCE(consumed_at, NOW())
               WHERE user_id = %s AND consumed_at IS NULL""",
            (user["id"],),
        )
        connection.execute(
            """DELETE FROM password_reset_tokens
               WHERE user_id = %s AND (expires_at < NOW() - INTERVAL '7 days'
                   OR consumed_at < NOW() - INTERVAL '7 days')""",
            (user["id"],),
        )
        token = secrets.token_urlsafe(32)
        connection.execute(
            """INSERT INTO password_reset_tokens(token_hash, user_id, expires_at)
               VALUES (%s, %s, %s)""",
            (_hash_token(token), user["id"], datetime.now(timezone.utc) + timedelta(minutes=30)),
        )
        return user.get("display_name") or "", token


def mark_password_reset_email_sent(token: str) -> None:
    with transaction() as connection:
        connection.execute(
            "UPDATE password_reset_tokens SET sent_at = NOW() WHERE token_hash = %s",
            (_hash_token(token),),
        )


def reset_password(token: str, password: str) -> bool:
    token_hash = _hash_token(token)
    with transaction() as connection:
        row = connection.execute(
            """SELECT user_id, expires_at, consumed_at FROM password_reset_tokens
               WHERE token_hash = %s FOR UPDATE""",
            (token_hash,),
        ).fetchone()
        if row is None or row["consumed_at"] is not None or row["expires_at"] <= datetime.now(timezone.utc):
            return False
        password_hash = hash_password(password)
        connection.execute("UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, row["user_id"]))
        connection.execute(
            "UPDATE password_reset_tokens SET consumed_at = NOW() WHERE user_id = %s AND consumed_at IS NULL",
            (row["user_id"],),
        )
        connection.execute(
            "UPDATE auth_sessions SET revoked_at = NOW() WHERE user_id = %s AND revoked_at IS NULL",
            (row["user_id"],),
        )
    return True


def _ip_hash(ip: str) -> str:
    pepper = os.getenv("SESSION_HASH_SALT", "trustflow-development-only")
    return hashlib.sha256(f"{pepper}:{ip}".encode()).hexdigest()


def check_login_rate(email: str, ip: str) -> bool:
    with transaction() as connection:
        row = connection.execute(
            """INSERT INTO auth_login_attempts(email, ip_hash, window_started_at, attempts)
               VALUES (%s, %s, NOW(), 1)
               ON CONFLICT (email, ip_hash) DO UPDATE SET
                 attempts = CASE
                   WHEN auth_login_attempts.window_started_at < NOW() - (%s * INTERVAL '1 minute') THEN 1
                   ELSE auth_login_attempts.attempts + 1 END,
                 window_started_at = CASE
                   WHEN auth_login_attempts.window_started_at < NOW() - (%s * INTERVAL '1 minute') THEN NOW()
                   ELSE auth_login_attempts.window_started_at END
               RETURNING attempts""",
            (email, _ip_hash(ip), LOGIN_WINDOW_MINUTES, LOGIN_WINDOW_MINUTES),
        ).fetchone()
    return row["attempts"] <= LOGIN_LIMIT


def clear_login_rate(email: str, ip: str) -> None:
    with transaction() as connection:
        connection.execute(
            "DELETE FROM auth_login_attempts WHERE email = %s AND ip_hash = %s",
            (email, _ip_hash(ip)),
        )


def authenticate(email: str, password: str) -> dict | None:
    with read_connection() as connection:
        row = connection.execute(
            "SELECT id, email, display_name, role, password_hash, email_verified FROM users WHERE lower(email) = lower(%s)",
            (email,),
        ).fetchone()
    valid_password = verify_password(row.get("password_hash") if row else None, password)
    if not row or not valid_password:
        return None
    if _password_hasher and row.get("password_hash") and not row["password_hash"].startswith("$argon2"):
        with transaction() as connection:
            connection.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (hash_password(password), row["id"]),
            )
    elif _password_hasher and row.get("password_hash") and _password_hasher.check_needs_rehash(row["password_hash"]):
        with transaction() as connection:
            connection.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (hash_password(password), row["id"]),
            )
    return public_user(row)


def create_session(user_id: str) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    with transaction() as connection:
        connection.execute(
            """INSERT INTO auth_sessions(session_hash, csrf_token, user_id, expires_at)
               VALUES (%s, %s, %s, %s)""",
            (_hash_token(token), csrf, user_id, datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)),
        )
    return token, csrf


def lookup_session(token: str | None) -> dict | None:
    if not token:
        return None
    with read_connection() as connection:
        row = connection.execute(
            """SELECT u.id, u.email, u.display_name, u.role, u.email_verified, s.csrf_token
               FROM auth_sessions s JOIN users u ON u.id = s.user_id
               WHERE s.session_hash = %s AND s.revoked_at IS NULL AND s.expires_at > NOW()
                 AND u.email_verified = TRUE""",
            (_hash_token(token),),
        ).fetchone()
    if row is None:
        return None
    return {**public_user(row), "csrf_token": row["csrf_token"]}


def revoke_session(token: str | None) -> None:
    if not token:
        return
    with transaction() as connection:
        connection.execute(
            "UPDATE auth_sessions SET revoked_at = NOW() WHERE session_hash = %s AND revoked_at IS NULL",
            (_hash_token(token),),
        )


def change_account(user: dict, name: str, current_password: str, new_password: str | None, session_token: str | None) -> tuple[dict, str, str]:
    if not session_token or not name.strip():
        raise ValueError("invalid account update")
    with read_connection() as connection:
        row = connection.execute("SELECT password_hash FROM users WHERE id = %s", (user["id"],)).fetchone()
    if row is None or not verify_password(row.get("password_hash"), current_password):
        raise ValueError("current password mismatch")
    new_hash = hash_password(new_password) if new_password else row["password_hash"]
    current_hash = _hash_token(session_token)
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    with transaction() as connection:
        updated = connection.execute(
            "UPDATE users SET display_name = %s, password_hash = %s WHERE id = %s RETURNING id, email, display_name, role",
            (name.strip(), new_hash, user["id"]),
        ).fetchone()
        connection.execute("UPDATE auth_sessions SET revoked_at = NOW() WHERE user_id = %s AND revoked_at IS NULL", (user["id"],))
        connection.execute(
            "INSERT INTO auth_sessions(session_hash, csrf_token, user_id, expires_at) VALUES (%s, %s, %s, %s)",
            (_hash_token(token), csrf, user["id"], datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)),
        )
    return public_user(updated), token, csrf
