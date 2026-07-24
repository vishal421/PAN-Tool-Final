from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.core import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE, csrf_token_for
from app.core.config import settings
from app.core.logging_config import configure_logging
from app.models.database import init_db
from app.api.routes import router as api_router
from app.api.auth_routes import router as auth_router
from app.api.track_routes import router as track_router
from app.admin.routes_users import router as admin_users_router
from app.admin.routes_analytics import router as admin_analytics_router
from app.admin.routes_seo import router as admin_seo_router

configure_logging()
logger = logging.getLogger("app.main")

_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Tracking endpoints are intentionally callable by fully anonymous visitors
# (that's the point) and navigator.sendBeacon (used for the pagehide beacon)
# has no way to attach a custom header at all, so a CSRF token can't apply
# to them regardless. None of them perform a sensitive account-level
# mutation - worst case is a visitor corrupting their own analytics, not a
# real security issue - so they're the one deliberate, narrow exemption.
_CSRF_EXEMPT_PREFIXES = (f"{settings.api_prefix}/track/",)


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Two independent layers, since the session moved from a Bearer header
    (immune to CSRF by construction) to an auto-attached cookie:

      1. Origin/Referer allow-listing - rejects any state-changing request
         whose declared origin isn't one of our own frontends. A browser
         cannot forge these headers; only a real cross-site request is
         rejected here, never same-site or same-origin (incl. non-browser
         clients with no Origin/Referer at all, e.g. curl/Postman using a
         Bearer token, which aren't CSRF-able anyway and are left alone).
      2. Double-submit CSRF token - required only when the request is
         actually riding on our session cookie (no Authorization header
         present). A cross-site attacker's page can make the cookie get
         sent, but can't read fwc_csrf (blocked by the same-origin policy),
         so it can never produce a header value that matches.
    """

    async def dispatch(self, request: Request, call_next):
        if request.method in _UNSAFE_METHODS and not request.url.path.startswith(_CSRF_EXEMPT_PREFIXES):
            origin = request.headers.get("origin")
            referer = request.headers.get("referer")
            candidate = origin
            if candidate is None and referer:
                parsed = urlparse(referer)
                candidate = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else None
            if candidate and candidate.rstrip("/") not in settings.cors_origins:
                return JSONResponse({"detail": "Cross-site request blocked."}, status_code=403)

            if "authorization" not in request.headers:
                session_token = request.cookies.get(SESSION_COOKIE)
                if session_token:
                    header_token = request.headers.get(CSRF_HEADER)
                    if not header_token or not _constant_time_eq(header_token, csrf_token_for(session_token)):
                        return JSONResponse({"detail": "Missing or invalid CSRF token."}, status_code=403)
        return await call_next(request)


def _constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if settings.jwt_secret == "dev-only-insecure-secret-change-me":
        logger.warning(
            "JWT_SECRET is using the insecure development default. Set a real "
            "JWT_SECRET environment variable before deploying this anywhere "
            "reachable by real users - anyone who knows the default can forge "
            "login tokens for any account."
        )
    yield


app = FastAPI(
    title=settings.app_name,
    description="Deterministic multi-vendor firewall configuration to Palo Alto Networks CLI converter.",
    version="0.12.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CSRFMiddleware)

app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(track_router, prefix=settings.api_prefix)
app.include_router(admin_users_router, prefix=settings.api_prefix)
app.include_router(admin_analytics_router, prefix=settings.api_prefix)
app.include_router(admin_seo_router, prefix=settings.api_prefix)
app.include_router(api_router)


@app.get("/")
def root():
    return {
        "name": settings.app_name,
        "status": "running",
        "docs": "/api/docs",
    }
