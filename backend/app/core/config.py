from __future__ import annotations

import os
from pathlib import Path


class Settings:
    app_name: str = "Firewall Config Converter"
    api_prefix: str = "/api"

    base_dir: Path = Path(__file__).resolve().parent.parent.parent  # backend/
    storage_dir: Path = base_dir / "storage"
    uploads_dir: Path = storage_dir / "uploads"
    outputs_dir: Path = storage_dir / "outputs"

    database_url: str = os.environ.get(
        "DATABASE_URL", f"sqlite:///{base_dir / 'storage' / 'converter.db'}"
    )

    max_upload_mb: int = int(os.environ.get("MAX_UPLOAD_MB", "25"))
    allowed_extensions: tuple[str, ...] = (".conf", ".txt", ".cfg", ".log", ".xml", ".export")

    cors_origins: list[str] = os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:4757,http://127.0.0.1:4757",
    ).split(",")

    # However CORS_ORIGINS is set for production (a real FQDN, subdomains,
    # etc.), always ALSO allow the common local dev/tunnel origins, so the
    # same running deployment can be reached both via its real domain and
    # via localhost (e.g. an SSH tunnel or `docker run -p` port-forward)
    # without having to edit env vars back and forth between the two.
    _LOCAL_DEV_ORIGINS: tuple[str, ...] = (
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:4757", "http://127.0.0.1:4757",
        "http://localhost:8000", "http://127.0.0.1:8000",
    )
    for _origin in _LOCAL_DEV_ORIGINS:
        if _origin not in cors_origins:
            cors_origins.append(_origin)

    # --- Cross-subdomain session cookie --------------------------------
    # Set COOKIE_DOMAIN=".pan-tool.com" (leading dot) when the app is split
    # across subdomains (login./signup./dash.pan-tool.com) so the session
    # cookie set by one is automatically sent to the others by the browser.
    # Leave unset for single-origin/local dev - the cookie then defaults to
    # host-only scope, which is exactly what you want there.
    cookie_domain: str | None = os.environ.get("COOKIE_DOMAIN") or None
    # Cookies require Secure=True to be sent over HTTPS-only, which is the
    # case in any real deployment (Cloudflare terminates TLS in front of
    # this app). The only reason to ever set COOKIE_SECURE=false is running
    # the whole stack over plain http:// on localhost with no TLS at all.
    cookie_secure: bool = os.environ.get("COOKIE_SECURE", "true").lower() != "false"

    # --- Reverse-proxy IP trust -----------------------------------------
    # client_ip() (app/auth/core.py) uses this to decide which header to
    # trust for the real visitor IP (used for login-rate-limiting and
    # visitor GeoIP). CF-Connecting-IP is ONLY trustworthy if the origin is
    # unreachable except through Cloudflare (true for Cloudflare Tunnel,
    # since it never exposes a public inbound port) - otherwise an attacker
    # who reaches the origin directly could forge this header themselves.
    trust_cloudflare_ip: bool = os.environ.get("TRUST_CLOUDFLARE_IP", "true").lower() != "false"

    # --- Auth ---------------------------------------------------------
    # MUST be overridden via env var in any real deployment - this default
    # is only here so local/dev boots without extra setup. A fixed fallback
    # secret is a real security bug in production; the app logs a loud
    # warning at startup if this default is still in use (see main.py).
    jwt_secret: str = os.environ.get("JWT_SECRET", "dev-only-insecure-secret-change-me")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = int(os.environ.get("JWT_EXPIRE_MINUTES", "10080"))  # 7 days

    # --- Plan quotas (very simple placeholder tiers - see PLAN doc) ----
    free_plan_job_limit: int = int(os.environ.get("FREE_PLAN_JOB_LIMIT", "10"))

    # --- Basic auth-endpoint rate limiting (in-memory, single-process) -
    auth_rate_limit_attempts: int = int(os.environ.get("AUTH_RATE_LIMIT_ATTEMPTS", "10"))
    auth_rate_limit_window_seconds: int = int(os.environ.get("AUTH_RATE_LIMIT_WINDOW_SECONDS", "300"))

    # --- Password reset ------------------------------------------------
    # Where the reset link points - the FRONTEND's URL, not the API's.
    frontend_base_url: str = os.environ.get("FRONTEND_BASE_URL", "http://localhost:3000")
    password_reset_expire_minutes: int = int(os.environ.get("PASSWORD_RESET_EXPIRE_MINUTES", "30"))

    # --- Outbound email (Brevo) -----------------------------------------
    # Two delivery paths, tried in this order:
    #   1. Brevo transactional email HTTP API, if BREVO_API_KEY is set
    #      (preferred - no SMTP port to worry about, works from any host).
    #   2. Brevo SMTP relay, if the BREVO_SMTP_* vars are set instead.
    # If neither is configured, email sending is skipped and a warning is
    # logged (never the OTP/code itself - see app/auth/email_sender.py) so
    # local/dev boots without a mail provider, but nothing pretends to have
    # sent an email it didn't.
    brevo_api_key: str | None = os.environ.get("BREVO_API_KEY") or None
    brevo_smtp_host: str | None = os.environ.get("BREVO_SMTP_HOST") or None
    brevo_smtp_port: int = int(os.environ.get("BREVO_SMTP_PORT", "587"))
    brevo_smtp_username: str | None = os.environ.get("BREVO_SMTP_USERNAME") or None
    brevo_smtp_password: str | None = os.environ.get("BREVO_SMTP_PASSWORD") or None
    mail_from_name: str = os.environ.get("MAIL_FROM_NAME", "Firewall Config Converter")
    mail_from_address: str = os.environ.get("MAIL_FROM_ADDRESS", "no-reply@example.com")

    # --- OTP (email verification + password reset) -----------------------
    otp_length: int = 6
    otp_expire_minutes: int = int(os.environ.get("OTP_EXPIRE_MINUTES", "5"))
    otp_max_attempts: int = int(os.environ.get("OTP_MAX_ATTEMPTS", "5"))
    otp_resend_cooldown_seconds: int = int(os.environ.get("OTP_RESEND_COOLDOWN_SECONDS", "60"))
    otp_max_requests_per_hour: int = int(os.environ.get("OTP_MAX_REQUESTS_PER_HOUR", "5"))

    # --- Corporate-email-only registration --------------------------------
    # Additional domains to block beyond the built-in list in
    # app/auth/domains.py, comma-separated (e.g. "mycompany-competitor.com").
    # This is the "add more later via configuration" hook from the spec -
    # the built-in list covers the common free/disposable providers, this
    # env var covers anything deployment-specific without a code change.
    extra_blocked_email_domains: set[str] = {
        d.strip().lower()
        for d in os.environ.get("EXTRA_BLOCKED_EMAIL_DOMAINS", "").split(",")
        if d.strip()
    }

    # --- Admin dashboard --------------------------------------------------
    # Comma-separated emails that are auto-promoted to is_admin=True the
    # moment they sign up or log in (case-insensitive). This is the bootstrap
    # mechanism for your very first admin account - after that, admins can
    # promote other users from inside the dashboard itself. Empty by default
    # (no admins) so this is opt-in per deployment.
    admin_bootstrap_emails: set[str] = {
        e.strip().lower()
        for e in os.environ.get("ADMIN_BOOTSTRAP_EMAILS", "").split(",")
        if e.strip()
    }

    # --- Visitor / session tracking ---------------------------------------
    # A session is considered ended (and the next pageview starts a new one)
    # after this many minutes of inactivity - the industry-standard default.
    session_idle_timeout_minutes: int = int(os.environ.get("SESSION_IDLE_TIMEOUT_MINUTES", "30"))

    # --- GeoIP --------------------------------------------------------------
    # "none" disables location lookups entirely (country/city stay null).
    # "ip-api" uses the free http://ip-api.com JSON endpoint (no key
    # required, rate-limited to 45 req/min - fine for low/moderate traffic;
    # swap in a MaxMind GeoLite2 lookup here later for higher volume without
    # touching any calling code, since everything reads through
    # app/tracking/geoip.py's single `lookup(ip)` function).
    geoip_provider: str = os.environ.get("GEOIP_PROVIDER", "ip-api")
    geoip_timeout_seconds: float = float(os.environ.get("GEOIP_TIMEOUT_SECONDS", "1.5"))

    def ensure_dirs(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
