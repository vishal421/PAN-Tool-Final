from __future__ import annotations

import datetime as dt
import re
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

# Password complexity requirements (mirrors the frontend checklist in
# AuthScreen.jsx): at least 8 characters, one uppercase, one lowercase, one
# number, one special character.
_PASSWORD_RULES = (
    (re.compile(r"[A-Z]"), "at least one uppercase letter"),
    (re.compile(r"[a-z]"), "at least one lowercase letter"),
    (re.compile(r"[0-9]"), "at least one number"),
    (re.compile(r"[^A-Za-z0-9]"), "at least one special character"),
)


def _validate_password_complexity(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    missing = [desc for pattern, desc in _PASSWORD_RULES if not pattern.search(value)]
    if missing:
        raise ValueError("Password must contain " + ", ".join(missing) + ".")
    return value


# Digits only, 7-15 characters (the country/dial code is captured
# separately) - matches the frontend's phone-number validation.
_PHONE_RE = re.compile(r"^\d{7,15}$")


def _validate_phone_number(value: str) -> str:
    if not _PHONE_RE.match(value):
        raise ValueError("Mobile number must contain only digits (7-15 digits).")
    return value


def _validate_optional_phone_number(value: Optional[str]) -> Optional[str]:
    if value is None or value.strip() == "":
        return value
    if not _PHONE_RE.match(value.strip()):
        raise ValueError("Mobile number must contain only digits (7-15 digits).")
    return value


# --- Auth --------------------------------------------------------------
class SignupIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    mobile_number: str = Field(min_length=3, max_length=32)
    mobile_country_code: str = Field(min_length=1, max_length=8)  # e.g. "+1"
    organization_name: str = Field(min_length=1, max_length=200)
    city: str = Field(min_length=1, max_length=150)
    state: Optional[str] = Field(default=None, max_length=150)
    country: str = Field(min_length=2, max_length=2)  # ISO2

    _check_password = field_validator("password")(_validate_password_complexity)
    _check_phone = field_validator("mobile_number")(_validate_phone_number)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8, max_length=128)

    _check_password = field_validator("new_password")(_validate_password_complexity)


class VerifyEmailIn(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6)


class EmailOnlyIn(BaseModel):
    """Used by the resend-verification and resend-password-otp endpoints."""
    email: EmailStr


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    _check_password = field_validator("new_password")(_validate_password_complexity)


class MessageOut(BaseModel):
    message: str


class UserOut(BaseModel):
    id: str
    email: str
    plan: str
    created_at: dt.datetime
    job_count: int = 0
    job_limit: Optional[int] = None  # None = unlimited (pro plan)
    email_verified: bool = False
    mobile_number: Optional[str] = None
    mobile_country_code: Optional[str] = None
    organization_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    job_title: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    is_admin: bool = False
    last_login_at: Optional[dt.datetime] = None
    login_count: int = 0

    class Config:
        from_attributes = True


class UpdateProfileIn(BaseModel):
    mobile_number: Optional[str] = Field(default=None, max_length=32)
    mobile_country_code: Optional[str] = Field(default=None, max_length=8)
    organization_name: Optional[str] = Field(default=None, max_length=200)
    job_title: Optional[str] = Field(default=None, max_length=150)
    city: Optional[str] = Field(default=None, max_length=150)
    state: Optional[str] = Field(default=None, max_length=150)
    country: Optional[str] = Field(default=None, max_length=2)

    _check_phone = field_validator("mobile_number")(_validate_optional_phone_number)


# --- Visitor / session tracking ------------------------------------------
ACTIVITY_EVENT_TYPES = (
    "login", "logout", "tool_opened", "config_uploaded", "migration_started",
    "migration_completed", "download_cli", "download_report", "signup_completed",
)


class PageViewIn(BaseModel):
    visitor_id: str = Field(min_length=1, max_length=64)
    session_id: str = Field(min_length=1, max_length=64)
    is_new_session: bool = False
    path: str = Field(min_length=1, max_length=500)
    title: Optional[str] = Field(default=None, max_length=300)
    referrer: Optional[str] = Field(default=None, max_length=1000)
    utm_source: Optional[str] = Field(default=None, max_length=200)
    utm_medium: Optional[str] = Field(default=None, max_length=200)
    utm_campaign: Optional[str] = Field(default=None, max_length=200)
    utm_content: Optional[str] = Field(default=None, max_length=200)
    screen_resolution: Optional[str] = Field(default=None, max_length=32)
    language: Optional[str] = Field(default=None, max_length=32)


class BeaconIn(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    path: Optional[str] = Field(default=None, max_length=500)
    time_on_page_seconds: Optional[int] = Field(default=None, ge=0, le=86400)
    scroll_depth_pct: Optional[int] = Field(default=None, ge=0, le=100)


class TrackEventIn(BaseModel):
    visitor_id: Optional[str] = Field(default=None, max_length=64)
    session_id: Optional[str] = Field(default=None, max_length=64)
    event_type: str
    event_data: Optional[dict] = None


class CountryOut(BaseModel):
    iso2: str
    name: str
    dial_code: str
    flag: str


# --- Admin: Users management ---------------------------------------------
class AdminUserRow(BaseModel):
    id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: str
    mobile_number: Optional[str] = None
    mobile_country_code: Optional[str] = None
    organization_name: Optional[str] = None
    job_title: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    registration_date: dt.datetime
    last_login: Optional[dt.datetime] = None
    login_count: int = 0
    account_status: str  # active | disabled
    email_verified: bool = False
    is_admin: bool = False
    plan: str = "free"
    total_sessions: int = 0
    total_page_views: int = 0
    last_activity: Optional[dt.datetime] = None
    ip_address: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    device_type: Optional[str] = None
    referrer_source: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None


class AdminUserListOut(BaseModel):
    total: int
    page: int
    page_size: int
    users: list[AdminUserRow]


class AdminLoginHistoryRow(BaseModel):
    occurred_at: dt.datetime
    ip_address: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    device_type: Optional[str] = None
    method: str

    class Config:
        from_attributes = True


class AdminActivityEventRow(BaseModel):
    event_type: str
    event_data: Optional[dict] = None
    occurred_at: dt.datetime

    class Config:
        from_attributes = True


class AdminUserDetailOut(BaseModel):
    user: AdminUserRow
    job_count: int
    recent_logins: list[AdminLoginHistoryRow]
    recent_activity: list[AdminActivityEventRow]


class AdminSetAdminIn(BaseModel):
    is_admin: bool


class AdminSetActiveIn(BaseModel):
    is_active: bool


# --- Admin: analytics dashboard ------------------------------------------
class OverviewCardsOut(BaseModel):
    total_visitors: int
    unique_visitors: int
    registered_users: int
    active_users_today: int
    logged_in_users_today: int
    anonymous_visitors_today: int
    total_page_views: int
    avg_session_duration_seconds: float
    bounce_rate_pct: float
    returning_visitors: int
    new_users_today: int
    total_tool_conversions: int


class TimeseriesPoint(BaseModel):
    label: str
    value: int


class BreakdownSlice(BaseModel):
    label: str
    value: int


class AnalyticsChartsOut(BaseModel):
    daily_visitors: list[TimeseriesPoint]
    weekly_visitors: list[TimeseriesPoint]
    monthly_visitors: list[TimeseriesPoint]
    user_registrations: list[TimeseriesPoint]
    top_countries: list[BreakdownSlice]
    top_cities: list[BreakdownSlice]
    traffic_sources: list[BreakdownSlice]
    most_visited_pages: list[BreakdownSlice]
    device_breakdown: list[BreakdownSlice]
    browser_breakdown: list[BreakdownSlice]
    os_breakdown: list[BreakdownSlice]
    logged_in_vs_guest: list[BreakdownSlice]


# --- Admin: SEO page analytics --------------------------------------------
class SeoPageStatsOut(BaseModel):
    path: str
    label: str
    total_views: int
    unique_visitors: int
    returning_visitors: int
    logged_in_users: int
    anonymous_users: int
    avg_time_on_page_seconds: float
    bounce_rate_pct: float
    avg_scroll_depth_pct: Optional[float] = None
    top_countries: list[BreakdownSlice]
    top_cities: list[BreakdownSlice]
    traffic_sources: list[BreakdownSlice]
    daily_views: list[TimeseriesPoint]
    weekly_views: list[TimeseriesPoint]
    monthly_views: list[TimeseriesPoint]


class SeoInsightsOut(BaseModel):
    most_visited_landing_page: Optional[str] = None
    best_converting_landing_page: Optional[str] = None
    organic_search_traffic: int
    direct_traffic: int
    referral_traffic: int
    email_traffic: int
    returning_users_pct: float
    avg_session_duration_seconds: float
    avg_pages_per_session: float
    top_entry_pages: list[BreakdownSlice]
    top_exit_pages: list[BreakdownSlice]


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class VendorInfo(BaseModel):
    key: str
    label: str


class ConversionIssueOut(BaseModel):
    severity: str
    object_type: str
    object_name: str
    message: str
    source_line: Optional[str] = None


class ConversionStats(BaseModel):
    addresses: int = 0
    address_groups: int = 0
    services: int = 0
    service_groups: int = 0
    interfaces: int = 0
    zones: int = 0
    routes: int = 0
    nat_rules: int = 0
    policies: int = 0
    warnings: int = 0
    errors: int = 0
    unsupported: int = 0


class JobOut(BaseModel):
    id: str
    job_name: Optional[str] = None
    vendor: str
    original_filename: str
    status: str
    created_at: dt.datetime
    completed_at: Optional[dt.datetime] = None
    stats: Optional[ConversionStats] = None
    issues: list[ConversionIssueOut] = []
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class JobListItemOut(BaseModel):
    """Lightweight row for the job history / home screen list - no stats/issues payload."""
    id: str
    job_name: Optional[str] = None
    vendor: str
    original_filename: str
    status: str
    created_at: dt.datetime
    completed_at: Optional[dt.datetime] = None

    class Config:
        from_attributes = True


class UploadResponse(BaseModel):
    job: JobOut
    message: str


# --- Interface mapping wizard schemas ------------------------------------
class DetectedInterfaceOut(BaseModel):
    """An interface as detected by the parser, shown in the mapping UI for the user to confirm/edit."""
    source_interface: str          # Interface.name - the identifier referenced by policies/routes/NAT
    hardware_name: Optional[str] = None  # Cisco physical name, for display context
    suggested_zone: Optional[str] = None  # parser's best-guess zone - a prefill hint only
    ip_address: Optional[str] = None
    netmask: Optional[str] = None
    description: str = ""
    mtu: Optional[int] = None
    virtual_router: Optional[str] = None


class ParseResponse(BaseModel):
    job: JobOut
    interfaces: list[DetectedInterfaceOut] = []
    message: str


class InterfaceMappingEntryIn(BaseModel):
    source_interface: str
    pan_interface: str
    zone: str
    virtual_router: str = "default"
    interface_type: str = "layer3"  # layer3 | layer2 | vwire
    ip_address: Optional[str] = None
    netmask: Optional[str] = None
    description: str = ""
    enabled: bool = True


class MappingSubmission(BaseModel):
    mappings: list[InterfaceMappingEntryIn]
    # If true, stop after validation and return warnings/errors without
    # generating - lets the UI show a validation preview before the user
    # commits (step 8 in the wizard: "Validation Before Generation").
    validate_only: bool = False


class MappingIssueOut(BaseModel):
    severity: str
    object_type: str
    object_name: str
    message: str


class MappingValidationOut(BaseModel):
    blocking: bool
    issues: list[MappingIssueOut]


class MappingResponse(BaseModel):
    job: JobOut
    validation: MappingValidationOut
    message: str


# --- Configuration summary (post-parse inventory) --------------------------
class ConfigSummaryOut(BaseModel):
    counts: ConversionStats
    tables: dict[str, list[dict]]


# --- Editable object grids (Address/Group/Service/Interface/Policy tables) --
EDITABLE_CATEGORIES = (
    "addresses", "address_groups", "services", "service_groups", "interfaces", "policies", "routes", "zones",
    "nat_rules",
)


class ObjectRowsOut(BaseModel):
    category: str
    rows: list[dict]


class ObjectRowsIn(BaseModel):
    rows: list[dict]


class ObjectRowsSaveOut(BaseModel):
    category: str
    rows: list[dict]
    issues: list[ConversionIssueOut]
    stats: ConversionStats


# --- Policy Profiles (Log Forwarding / Security Profile Group names) ------
class ProfilesOut(BaseModel):
    log_forwarding_profiles: list[str]
    security_profile_groups: list[str]


class ProfilesIn(BaseModel):
    log_forwarding_profiles: list[str]
    security_profile_groups: list[str]


# --- Configuration Cleanup ---------------------------------------------
class CleanupFindingOut(BaseModel):
    category: str
    object_type: str
    name: str
    message: str
    related: list[str] = []


class CleanupOut(BaseModel):
    findings: list[CleanupFindingOut]
    counts: dict[str, int]


class CleanupDeleteIn(BaseModel):
    object_type: str
    names: list[str]


# --- Validation Center -------------------------------------------------------
class ValidationOut(BaseModel):
    issues: list[ConversionIssueOut]
    stats: ConversionStats


# --- Selective export --------------------------------------------------------
EXPORT_SECTIONS = (
    "addresses", "address_groups", "services", "service_groups", "interfaces",
    "zones", "virtual_routers", "routes", "nat_rules", "security_rules",
)


class ExportSectionsIn(BaseModel):
    # None/omitted/["all"] = everything, matching the "Everything" checkbox
    sections: Optional[list[str]] = None


class ExportPreviewOut(BaseModel):
    cli: str
    command_count: int
    sections: list[str]
