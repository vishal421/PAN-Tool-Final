"""
SQLite persistence layer.

We persist conversion *jobs*, not the raw uploaded configs (those live
briefly on disk under storage/uploads and can be purged). A job row
tracks vendor, filename, status, stats, and paths to the generated
output artifacts so the frontend can re-download without re-converting.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import create_engine, String, DateTime, Integer, Text, JSON, inspect, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _new_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    plan: Mapped[str] = mapped_column(String(20), default="free")  # free | pro
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    mobile_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    organization_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # --- Registration profile fields ---------------------------------
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(150), nullable=True)
    city: Mapped[str | None] = mapped_column(String(150), nullable=True)
    state: Mapped[str | None] = mapped_column(String(150), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)  # ISO2, e.g. "US"
    # Dial code for mobile_number, e.g. "+1". Defaults from `country` on the
    # frontend but can be overridden manually (some users have a mobile
    # number from a different country than the one they live/work in).
    mobile_country_code: Mapped[str | None] = mapped_column(String(8), nullable=True)

    # --- Admin / roles --------------------------------------------------
    is_admin: Mapped[bool] = mapped_column(default=False)

    # --- Account activity (cheap counters kept on the row itself; richer
    # per-session/per-page detail lives in the tracking tables below) ----
    # False until the signup verification OTP is confirmed (see
    # app/auth/otp.py + /auth/verify-email). Login is blocked until true.
    email_verified: Mapped[bool] = mapped_column(default=False)
    last_login_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    login_count: Mapped[int] = mapped_column(Integer, default=0)


class OtpCode(Base):
    """
    One row per OTP ever issued, for both email-verification and
    password-reset codes (`purpose` distinguishes them - see
    app/auth/otp.py's PURPOSE_* constants). Only the HMAC of the code is
    stored, never the raw code. `attempts` enforces the max-attempts
    lockout; `consumed_at` marks a code used (successfully verified) or
    invalidated (superseded by a resend, or attempts exhausted) so it can
    never be verified again either way.
    """
    __tablename__ = "otp_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    purpose: Mapped[str] = mapped_column(String(32), index=True)  # verify_email | reset_password
    code_hash: Mapped[str] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime)
    consumed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class ConversionJob(Base):
    __tablename__ = "conversion_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    job_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    vendor: Mapped[str] = mapped_column(String(50))
    original_filename: Mapped[str] = mapped_column(String(255))
    # pending|parsing|awaiting_mapping|completed|failed
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    # The parsed-but-not-yet-mapped NormalizedConfig, serialized to JSON, so
    # it survives between the /parse request and the later /mapping request
    # (see app/normalizer/serialization.py). Cleared once generation completes.
    normalized_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    interface_mapping_json: Mapped[list | None] = mapped_column(JSON, nullable=True)

    stats_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    issues_json: Mapped[list | None] = mapped_column(JSON, nullable=True)

    cli_output_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    csv_output_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    json_output_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class Visitor(Base):
    """
    One row per browser (identified by a long-lived first-party `fwc_vid`
    cookie/localStorage id issued by the frontend on first pageview - see
    app/tracking/service.py). Anonymous visitors and logged-in users share
    this table; `user_id` is filled in once/if the visitor signs up or logs
    in during a session, but the visitor row itself is never duplicated.
    """
    __tablename__ = "visitors"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # client-generated visitor id
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    first_seen_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    last_seen_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    total_visits: Mapped[int] = mapped_column(Integer, default=0)  # incremented once per session


class VisitorSession(Base):
    """One browser tab/window's worth of browsing until ~30 min idle or tab close."""
    __tablename__ = "visitor_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # client-generated session id
    visitor_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    started_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    last_seen_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    entry_page: Mapped[str | None] = mapped_column(String(500), nullable=True)
    exit_page: Mapped[str | None] = mapped_column(String(500), nullable=True)
    page_view_count: Mapped[int] = mapped_column(Integer, default=0)
    time_on_site_seconds: Mapped[int] = mapped_column(Integer, default=0)
    is_bounce: Mapped[bool] = mapped_column(default=True)  # flips false on 2nd pageview

    # --- Location (GeoIP, looked up once per session from the first
    # request's IP - see app/tracking/geoip.py) --------------------------
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    region: Mapped[str | None] = mapped_column(String(150), nullable=True)
    city: Mapped[str | None] = mapped_column(String(150), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # --- Device -----------------------------------------------------------
    browser: Mapped[str | None] = mapped_column(String(64), nullable=True)
    browser_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    os: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_type: Mapped[str | None] = mapped_column(String(32), nullable=True)  # desktop|mobile|tablet|bot
    screen_resolution: Mapped[str | None] = mapped_column(String(32), nullable=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Traffic source ----------------------------------------------------
    referrer: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    traffic_source: Mapped[str | None] = mapped_column(String(64), nullable=True)  # classified bucket, see traffic_source.py
    utm_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String(200), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(200), nullable=True)
    utm_content: Mapped[str | None] = mapped_column(String(200), nullable=True)


class PageView(Base):
    __tablename__ = "page_views"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    visitor_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    path: Mapped[str] = mapped_column(String(500), index=True)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    viewed_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow, index=True)
    # Filled in retroactively by a "beacon" sent when the user navigates away
    # or closes the tab (navigator.sendBeacon), so it may briefly be null.
    time_on_page_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scroll_depth_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)


class UserActivityEvent(Base):
    """
    Discrete product events for the user-journey funnel: login, logout,
    tool_opened, config_uploaded, migration_started, migration_completed,
    download_cli, download_report, signup_completed. `event_data` is a
    small free-form JSON payload (e.g. {"vendor": "fortigate"}).
    """
    __tablename__ = "user_activity_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    visitor_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    event_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow, index=True)


class LoginHistory(Base):
    """One row per successful login, for the admin Users detail view."""
    __tablename__ = "login_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    browser: Mapped[str | None] = mapped_column(String(64), nullable=True)
    os: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    method: Mapped[str] = mapped_column(String(20), default="password")


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """
    Creates tables that don't exist yet, then patches in any columns that
    were added to a model after a persistent DB file was first created.

    Base.metadata.create_all() only issues CREATE TABLE for tables that are
    missing - it never alters an existing table's columns. In deployments
    with a persistent volume (see docker-compose.yml / render.yaml), that
    means every model field added after the volume's first run is silently
    absent from the on-disk schema, and any query touching that column
    blows up with "no such column: ..." the first time it's used. This is
    a stand-in for a real migration tool (e.g. Alembic), sufficient for our
    purposes: add-only, no renames/drops/type changes.

    Runs once per worker process (Gunicorn's FastAPI lifespan startup fires
    per-worker, not once for the whole app - see WEB_CONCURRENCY in
    docker-compose.yml), so multiple processes can legitimately race to
    CREATE TABLE / ADD COLUMN at the same moment on first boot. Rather than
    a cross-process lock, each statement below just treats "someone else
    already did this" as success: the end state is identical either way,
    and the alternative (a lock file/advisory lock) adds real complexity
    for a migration step that only ever matters on the very first startup
    after a schema change.
    """
    try:
        Base.metadata.create_all(bind=engine)
    except (OperationalError, ProgrammingError) as exc:
        if "already exists" not in str(exc).lower():
            raise

    inspector = inspect(engine)
    for table in Base.metadata.sorted_tables:
        if table.name not in inspector.get_table_names():
            continue  # a concurrent worker's create_all() call lost the race and will retry next boot
        existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing_columns:
                continue
            ddl_type = column.type.compile(dialect=engine.dialect)
            try:
                with engine.begin() as conn:
                    conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {ddl_type}'))
            except (OperationalError, ProgrammingError) as exc:
                message = str(exc).lower()
                if "duplicate column" not in message and "already exists" not in message:
                    raise


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
