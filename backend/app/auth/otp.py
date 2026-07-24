"""
OTP (one-time password) generation and verification for email verification
and password reset.

Security properties, per the spec:
  - 6-digit numeric code.
  - Only the HMAC-SHA256 of the code is stored, never the raw code (same
    "never store the secret itself" principle as password_hash) - keyed by
    JWT_SECRET so a stolen DB alone isn't enough to brute-force it offline.
  - Expires after OTP_EXPIRE_MINUTES.
  - Only one active (unconsumed) code per user+purpose at a time - creating
    a new one immediately invalidates any previous one for that purpose.
  - Verification is attempt-limited (OTP_MAX_ATTEMPTS); exceeding it
    invalidates the code and the user must request a new one.
  - Resending is cooldown-limited (OTP_RESEND_COOLDOWN_SECONDS) and rate
    limited (OTP_MAX_REQUESTS_PER_HOUR per email and per IP), reusing the
    app's existing in-memory check_rate_limit - see app/auth/core.py's
    module docstring for the single-process caveat, which applies here too.
  - Expired codes are opportunistically deleted whenever a new one is
    created, rather than needing a separate cleanup cron.

Never log the raw code anywhere (API responses, application logs, etc).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import secrets

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth.core import check_rate_limit
from app.core.config import settings
from app.models.database import OtpCode, User

PURPOSE_VERIFY_EMAIL = "verify_email"
PURPOSE_RESET_PASSWORD = "reset_password"


def _generate_code() -> str:
    return f"{secrets.randbelow(10 ** settings.otp_length):0{settings.otp_length}d}"


def _hash_code(code: str) -> str:
    return hmac.new(settings.jwt_secret.encode("utf-8"), code.encode("utf-8"), hashlib.sha256).hexdigest()


def _cleanup_expired(db: Session, user_id: str, purpose: str) -> None:
    now = dt.datetime.utcnow()
    db.query(OtpCode).filter(
        OtpCode.user_id == user_id,
        OtpCode.purpose == purpose,
        OtpCode.expires_at < now,
    ).delete(synchronize_session=False)


def create_otp(db: Session, user: User, purpose: str, ip: str) -> str:
    """
    Generates and stores a new OTP for `user`/`purpose`, enforcing the
    resend cooldown and hourly rate limits. Returns the raw code (to be
    emailed - never persisted or returned via this function's caller to
    the HTTP client).
    """
    check_rate_limit(f"otp-request:{purpose}:{user.email}", max_attempts=settings.otp_max_requests_per_hour, window_seconds=3600)
    check_rate_limit(f"otp-request:{purpose}:{ip}", max_attempts=settings.otp_max_requests_per_hour, window_seconds=3600)

    _cleanup_expired(db, user.id, purpose)

    active = (
        db.query(OtpCode)
        .filter(OtpCode.user_id == user.id, OtpCode.purpose == purpose, OtpCode.consumed_at.is_(None))
        .order_by(OtpCode.created_at.desc())
        .first()
    )
    if active is not None:
        elapsed = (dt.datetime.utcnow() - active.created_at).total_seconds()
        if elapsed < settings.otp_resend_cooldown_seconds:
            wait = int(settings.otp_resend_cooldown_seconds - elapsed)
            raise HTTPException(429, f"Please wait {wait} seconds before requesting another code.")
        # Resending invalidates the previous code - only one active code at a time.
        active.consumed_at = dt.datetime.utcnow()

    code = _generate_code()
    now = dt.datetime.utcnow()
    db.add(OtpCode(
        user_id=user.id,
        purpose=purpose,
        code_hash=_hash_code(code),
        attempts=0,
        created_at=now,
        expires_at=now + dt.timedelta(minutes=settings.otp_expire_minutes),
    ))
    db.commit()
    return code


def verify_otp(db: Session, user: User, purpose: str, code: str) -> None:
    """Raises HTTPException on any failure; returns None (and consumes the
    code) on success."""
    row = (
        db.query(OtpCode)
        .filter(OtpCode.user_id == user.id, OtpCode.purpose == purpose, OtpCode.consumed_at.is_(None))
        .order_by(OtpCode.created_at.desc())
        .first()
    )
    if row is None:
        raise HTTPException(400, "No active code found for this request. Please request a new code.")

    if row.expires_at < dt.datetime.utcnow():
        raise HTTPException(400, "This code has expired. Please request a new one.")

    if row.attempts >= settings.otp_max_attempts:
        row.consumed_at = dt.datetime.utcnow()
        db.commit()
        raise HTTPException(429, "Too many incorrect attempts. Please request a new code.")

    if not hmac.compare_digest(row.code_hash, _hash_code(code.strip())):
        row.attempts += 1
        db.commit()
        raise HTTPException(400, "Invalid code. Please check the code and try again.")

    row.consumed_at = dt.datetime.utcnow()
    db.commit()
