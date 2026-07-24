from __future__ import annotations

import datetime as dt
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.auth.core import (
    hash_password, verify_password, create_access_token, get_current_user,
    check_rate_limit, client_ip,
    set_session_cookies, clear_session_cookies,
)
from app.auth.domains import blocked_reason
from app.auth.email_sender import send_verification_email, send_password_reset_otp_email
from app.auth.otp import create_otp, verify_otp, PURPOSE_VERIFY_EMAIL, PURPOSE_RESET_PASSWORD
from app.core.config import settings
from app.core.countries import VALID_ISO2_CODES
from app.models.database import User, ConversionJob, LoginHistory, get_db
from app.models.schemas import (
    SignupIn, LoginIn, TokenOut, UserOut,
    ForgotPasswordIn, ResetPasswordIn, VerifyEmailIn, EmailOnlyIn, MessageOut, UpdateProfileIn,
    ChangePasswordIn,
)
from app.tracking.useragent import parse_user_agent

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("app.auth.routes")


def _job_limit_for(user: User) -> int | None:
    return None if user.plan == "pro" else settings.free_plan_job_limit


def _maybe_promote_admin(user: User) -> None:
    """Auto-promotes bootstrap admin emails (ADMIN_BOOTSTRAP_EMAILS) on every
    signup/login, so adding an env var and re-deploying is enough to grant
    the first admin - no direct DB edit needed."""
    if user.email.lower() in settings.admin_bootstrap_emails and not user.is_admin:
        user.is_admin = True


def _record_login(db: Session, user: User, request: Request, method: str) -> None:
    user.last_login_at = dt.datetime.utcnow()
    user.login_count += 1
    device = parse_user_agent(request.headers.get("user-agent"))
    db.add(LoginHistory(
        user_id=user.id, ip_address=client_ip(request), browser=device.browser,
        os=device.os, device_type=device.device_type, method=method,
    ))


def _user_out(user: User, db: Session) -> UserOut:
    job_count = db.query(ConversionJob).filter(ConversionJob.user_id == user.id).count()
    return UserOut(
        id=user.id, email=user.email, plan=user.plan, created_at=user.created_at,
        job_count=job_count, job_limit=_job_limit_for(user),
        email_verified=user.email_verified,
        mobile_number=user.mobile_number,
        mobile_country_code=user.mobile_country_code,
        organization_name=user.organization_name,
        first_name=user.first_name, last_name=user.last_name, job_title=user.job_title,
        city=user.city, state=user.state, country=user.country,
        is_admin=user.is_admin, last_login_at=user.last_login_at, login_count=user.login_count,
    )


@router.post("/signup", response_model=MessageOut)
def signup(body: SignupIn, request: Request, db: Session = Depends(get_db)):
    """
    Creates the account (inactive/unverified) and emails a verification
    OTP. No session is issued here - per spec, the account only becomes
    usable for login after /auth/verify-email succeeds.
    """
    check_rate_limit(f"signup:{client_ip(request)}")

    email = body.email.lower()
    reason = blocked_reason(email)
    if reason:
        raise HTTPException(422, reason)

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        # Deliberately never re-sends an OTP for an already-registered
        # email, verified or not - an unverified user gets a resend option
        # from the login screen instead (see /auth/resend-verification).
        raise HTTPException(409, "An account with this email already exists. Please log in.")

    country = body.country.upper()
    if country not in VALID_ISO2_CODES:
        raise HTTPException(422, "Please select a valid country.")

    user = User(
        email=email, password_hash=hash_password(body.password), plan="free",
        first_name=body.first_name.strip(), last_name=body.last_name.strip(),
        mobile_number=body.mobile_number.strip(), mobile_country_code=body.mobile_country_code.strip(),
        organization_name=body.organization_name.strip(),
        city=body.city.strip(), state=(body.state or "").strip() or None,
        country=country,
        email_verified=False,
    )
    _maybe_promote_admin(user)
    db.add(user)
    db.commit()
    db.refresh(user)

    code = create_otp(db, user, PURPOSE_VERIFY_EMAIL, client_ip(request))
    send_verification_email(user.email, code)

    return MessageOut(message="Account created. We've sent a verification code to your email - enter it to activate your account.")


@router.post("/verify-email", response_model=MessageOut)
def verify_email(body: VerifyEmailIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(404, "Account not found. Please sign up first.")
    if user.email_verified:
        return MessageOut(message="This email is already verified. You can log in.")

    verify_otp(db, user, PURPOSE_VERIFY_EMAIL, body.otp)

    user.email_verified = True
    db.commit()
    return MessageOut(message="Email verified. You can now log in.")


@router.post("/resend-verification", response_model=MessageOut)
def resend_verification(body: EmailOnlyIn, request: Request, db: Session = Depends(get_db)):
    email = body.email.lower()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(404, "Account not found. Please sign up first.")
    if user.email_verified:
        return MessageOut(message="This email is already verified. You can log in.")

    code = create_otp(db, user, PURPOSE_VERIFY_EMAIL, client_ip(request))
    send_verification_email(user.email, code)
    return MessageOut(message="A new verification code has been sent to your email.")


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    check_rate_limit(f"login:{client_ip(request)}")

    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user:
        raise HTTPException(404, "Account not found. Please sign up first.")
    if not user.email_verified:
        raise HTTPException(403, "Please verify your email before logging in.")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password.")
    if not user.is_active:
        raise HTTPException(403, "This account has been disabled.")

    _maybe_promote_admin(user)
    _record_login(db, user, request, method="password")
    db.commit()

    token = create_access_token(user.id)
    set_session_cookies(response, token, request)
    return TokenOut(access_token=token, user=_user_out(user, db))


@router.post("/logout", response_model=MessageOut)
def logout(request: Request, response: Response):
    """Clears the session + CSRF cookies. Safe to call even if not
    currently logged in (idempotent)."""
    clear_session_cookies(response, request)
    return MessageOut(message="Logged out.")


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _user_out(current_user, db)


@router.patch("/me", response_model=UserOut)
def update_me(
    body: UpdateProfileIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lets a signed-in user update their own profile fields."""
    if body.mobile_number is not None:
        current_user.mobile_number = body.mobile_number.strip() or None
    if body.mobile_country_code is not None:
        current_user.mobile_country_code = body.mobile_country_code.strip() or None
    if body.organization_name is not None:
        current_user.organization_name = body.organization_name.strip() or None
    if body.job_title is not None:
        current_user.job_title = body.job_title.strip() or None
    if body.city is not None:
        current_user.city = body.city.strip() or None
    if body.state is not None:
        current_user.state = body.state.strip() or None
    if body.country is not None:
        country = body.country.upper()
        if country and country not in VALID_ISO2_CODES:
            raise HTTPException(422, "Please select a valid country.")
        current_user.country = country or None
    db.commit()
    db.refresh(current_user)
    return _user_out(current_user, db)


@router.post("/change-password", response_model=MessageOut)
def change_password(
    body: ChangePasswordIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lets a signed-in user change their own password from the Profile page."""
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(401, "Current password is incorrect.")
    current_user.password_hash = hash_password(body.new_password)
    db.commit()
    return MessageOut(message="Password updated.")


_GENERIC_OTP_MESSAGE = "If an account is registered with this email address, you will receive an OTP shortly."


@router.post("/forgot-password", response_model=MessageOut)
def forgot_password(body: ForgotPasswordIn, request: Request, db: Session = Depends(get_db)):
    """
    Sends a password-reset OTP when the account exists, but always returns
    the same generic message either way so the response never reveals
    whether a given email is registered (account-enumeration protection).
    """
    check_rate_limit(f"forgot-password:{client_ip(request)}")

    user = db.query(User).filter(User.email == body.email.lower()).first()
    if user and user.is_active:
        code = create_otp(db, user, PURPOSE_RESET_PASSWORD, client_ip(request))
        send_password_reset_otp_email(user.email, code)
    return MessageOut(message=_GENERIC_OTP_MESSAGE)


@router.post("/resend-password-otp", response_model=MessageOut)
def resend_password_otp(body: EmailOnlyIn, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(f"forgot-password:{client_ip(request)}")

    user = db.query(User).filter(User.email == body.email.lower()).first()
    if user and user.is_active:
        code = create_otp(db, user, PURPOSE_RESET_PASSWORD, client_ip(request))
        send_password_reset_otp_email(user.email, code)
    return MessageOut(message=_GENERIC_OTP_MESSAGE)


@router.post("/reset-password", response_model=MessageOut)
def reset_password(body: ResetPasswordIn, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(f"reset-password:{client_ip(request)}")

    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user or not user.is_active:
        # Same error a real account would get for a stale/missing code -
        # never reveals whether the email is registered.
        raise HTTPException(400, "No active code found for this request. Please request a new code.")

    verify_otp(db, user, PURPOSE_RESET_PASSWORD, body.otp)

    user.password_hash = hash_password(body.new_password)
    db.commit()
    return MessageOut(message="Password updated. You can now log in with your new password.")
