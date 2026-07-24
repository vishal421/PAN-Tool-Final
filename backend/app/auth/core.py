"""
Auth core: password hashing, JWT issuance/verification, and a lightweight
in-memory rate limiter for the login/signup endpoints.

Scope note: this is single-process rate limiting (an in-memory dict), which
is fine for a single backend instance but will NOT coordinate across
multiple replicas behind a load balancer. If/when this deploys with more
than one backend process, replace RATE_LIMITER with a Redis-backed limiter
(same interface: .check(key) -> bool) - everything that calls it goes
through the one `check_rate_limit()` function below, so that's a
single-point swap when the time comes.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import time
from collections import defaultdict, deque

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.database import User, get_db

_bearer_scheme = HTTPBearer(auto_error=False)

# --- Cross-subdomain session cookie + CSRF -------------------------------
# SESSION_COOKIE holds the same JWT that used to live in localStorage, but
# as HttpOnly (so page JS - including any XSS payload - can never read it)
# and Domain-scoped to settings.cookie_domain (e.g. ".pan-tool.com") so
# login.pan-tool.com, signup.pan-tool.com, and dash.pan-tool.com all get it
# automatically without the app passing the token around itself.
#
# Moving auth into an auto-attached cookie is what makes CSRF a real risk
# here (a Bearer header, by contrast, can't be forged cross-site - browsers
# won't auto-attach a custom header to a request built by another origin).
# CSRF_COOKIE is the mitigation: a value derived from the session token via
# HMAC, set as a normal (non-HttpOnly, JS-readable) cookie. The frontend
# reads it and echoes it back as the X-CSRF-Token header on every mutating
# request; app/main.py's CSRFMiddleware then checks the two match. A
# cross-site attacker's page can trigger the cookie to be *sent*, but has
# no way to *read* it (blocked by the same-origin policy) and so can never
# produce a matching header value - this is the standard "double-submit
# cookie" pattern.
SESSION_COOKIE = "fwc_session"
CSRF_COOKIE = "fwc_csrf"
CSRF_HEADER = "x-csrf-token"


def csrf_token_for(session_token: str) -> str:
    """Deterministic, stateless CSRF token tied 1:1 to a given session
    token via HMAC - no server-side session store needed to verify it."""
    return hmac.new(settings.jwt_secret.encode("utf-8"), session_token.encode("utf-8"), hashlib.sha256).hexdigest()


# Hosts that can never validly carry a Domain-scoped or Secure cookie:
# localhost/127.0.0.1 aren't real registrable domains (Domain=.pan-tool.com
# would just be silently rejected by the browser), and access to them is
# almost always over plain http:// (no cert for "localhost"), which a
# Secure cookie is never sent/stored over. Detected per-request so the same
# deployment serves both the real FQDN (full cross-subdomain, HTTPS-only
# cookie) and localhost (SSH tunnel / port-forward, plain host-only cookie)
# without needing two different builds or env files.
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _cookie_scope(request: Request) -> dict:
    host = (request.url.hostname or "").lower()
    if host in _LOCAL_HOSTS:
        return dict(secure=False, domain=None)
    return dict(secure=settings.cookie_secure, domain=settings.cookie_domain)


def set_session_cookies(response: Response, token: str, request: Request) -> None:
    cookie_kwargs = dict(
        samesite="lax",  # sent on same-site (incl. cross-subdomain) requests; not on cross-site ones
        path="/",
        max_age=settings.jwt_expire_minutes * 60,
        **_cookie_scope(request),
    )
    response.set_cookie(SESSION_COOKIE, token, httponly=True, **cookie_kwargs)
    response.set_cookie(CSRF_COOKIE, csrf_token_for(token), httponly=False, **cookie_kwargs)


def clear_session_cookies(response: Response, request: Request) -> None:
    # delete_cookie must be called with the same domain/path used to set it,
    # or the browser won't recognize it as the same cookie to remove.
    scope = _cookie_scope(request)
    response.delete_cookie(SESSION_COOKIE, domain=scope["domain"], path="/")
    response.delete_cookie(CSRF_COOKIE, domain=scope["domain"], path="/")


def _resolve_token(creds: HTTPAuthorizationCredentials | None, request: Request) -> str | None:
    """Authorization: Bearer header wins if present (API/script usage);
    otherwise falls back to the session cookie (browser usage)."""
    if creds is not None:
        return creds.credentials
    return request.cookies.get(SESSION_COOKIE)


# --- Passwords ---------------------------------------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False  # malformed stored hash - fail closed


# --- JWT -----------------------------------------------------------------
def create_access_token(user_id: str) -> str:
    now = dt.datetime.utcnow()
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + dt.timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    """Returns the user_id ('sub') from a valid token, or raises HTTPException(401)."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expired - please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid authentication token.")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(401, "Invalid authentication token.")
    return user_id


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    token = _resolve_token(creds, request)
    if token is None:
        raise HTTPException(401, "Not authenticated - please log in.")
    user_id = decode_access_token(token)
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Account not found or disabled.")
    return user


def get_current_user_optional(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """
    Like get_current_user, but returns None instead of raising for missing/
    invalid/expired tokens. Used by tracking endpoints, which must accept
    both anonymous visitors and logged-in users on the same route.
    """
    token = _resolve_token(creds, request)
    if token is None:
        return None
    try:
        user_id = decode_access_token(token)
    except HTTPException:
        return None
    user = db.get(User, user_id)
    return user if user and user.is_active else None


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Gate for every /api/admin/* route - must be authenticated AND is_admin."""
    if not user.is_admin:
        raise HTTPException(403, "Admin access required.")
    return user


# --- Rate limiting (in-memory, single-process - see module docstring) ---
_attempts: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(key: str, max_attempts: int | None = None, window_seconds: int | None = None) -> None:
    """Raises HTTPException(429) if `key` (e.g. 'login:<ip>') has exceeded
    `max_attempts` within `window_seconds` (defaults to
    settings.auth_rate_limit_attempts / auth_rate_limit_window_seconds,
    used by the login/signup endpoints; OTP request/resend limits pass
    their own values - see app/auth/otp.py)."""
    max_attempts = settings.auth_rate_limit_attempts if max_attempts is None else max_attempts
    window = settings.auth_rate_limit_window_seconds if window_seconds is None else window_seconds
    now = time.monotonic()
    bucket = _attempts[key]
    while bucket and now - bucket[0] > window:
        bucket.popleft()
    if len(bucket) >= max_attempts:
        raise HTTPException(429, "Too many attempts - please wait a few minutes and try again.")
    bucket.append(now)


def client_ip(request: Request) -> str:
    """
    Best-effort real visitor IP, used for login/signup rate limiting and
    GeoIP. Both CF-Connecting-IP and X-Forwarded-For are headers a client
    can set to whatever they want - they're ONLY trustworthy if every
    request is guaranteed to pass through Cloudflare's edge first, which
    Cloudflare rewrites unconditionally (so a client-supplied fake value
    never survives). That guarantee holds specifically because Cloudflare
    Tunnel (cloudflared) means this origin has no public inbound port at
    all - the only way in is through Cloudflare. If you ever expose this
    app's port directly to the internet alongside the tunnel, that
    guarantee breaks and TRUST_CLOUDFLARE_IP must be turned off, or an
    attacker can bypass rate limiting by hitting the origin directly with
    a forged header.
    """
    if settings.trust_cloudflare_ip:
        cf_ip = request.headers.get("cf-connecting-ip")
        if cf_ip:
            return cf_ip.strip()
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
