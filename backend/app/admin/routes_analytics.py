"""
Admin -> Dashboard Analytics: the overview cards + every chart on section 7
of the spec. Time-bucketing is done in Python rather than per-dialect SQL
date functions, since this backend needs to run unmodified on both SQLite
(default/dev) and Postgres (see docker-compose.yml) - simplest thing that
works correctly on both. Fine at this app's expected scale; if visitor
volume grows into the millions of rows, swap the bucket helpers below for
a proper GROUP BY with a dialect-specific date_trunc/strftime.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.core import require_admin
from app.models.database import (
    PageView, User, UserActivityEvent, Visitor, VisitorSession, get_db,
)
from app.models.schemas import AnalyticsChartsOut, BreakdownSlice, OverviewCardsOut, TimeseriesPoint

router = APIRouter(prefix="/admin/analytics", tags=["admin-analytics"], dependencies=[Depends(require_admin)])

_COUNTRY_NAMES = None  # lazy import to avoid a circular import at module load


def _country_name(iso2: str | None) -> str:
    global _COUNTRY_NAMES
    if not iso2:
        return "Unknown"
    if _COUNTRY_NAMES is None:
        from app.core.countries import COUNTRY_BY_ISO2
        _COUNTRY_NAMES = COUNTRY_BY_ISO2
    return _COUNTRY_NAMES.get(iso2, {}).get("name", iso2)


def _daily_buckets(timestamps: list[dt.datetime], days: int = 30) -> list[TimeseriesPoint]:
    today = dt.datetime.utcnow().date()
    keys = [(today - dt.timedelta(days=i)) for i in range(days - 1, -1, -1)]
    counts = Counter(ts.date() for ts in timestamps)
    return [TimeseriesPoint(label=k.isoformat(), value=counts.get(k, 0)) for k in keys]


def _week_start(d: dt.date) -> dt.date:
    return d - dt.timedelta(days=d.weekday())


def _weekly_buckets(timestamps: list[dt.datetime], weeks: int = 12) -> list[TimeseriesPoint]:
    this_week = _week_start(dt.datetime.utcnow().date())
    keys = [(this_week - dt.timedelta(weeks=i)) for i in range(weeks - 1, -1, -1)]
    counts = Counter(_week_start(ts.date()) for ts in timestamps)
    return [TimeseriesPoint(label=k.isoformat(), value=counts.get(k, 0)) for k in keys]


def _month_key(d: dt.date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _monthly_buckets(timestamps: list[dt.datetime], months: int = 12) -> list[TimeseriesPoint]:
    now = dt.datetime.utcnow().date()
    keys = []
    y, m = now.year, now.month
    for _ in range(months):
        keys.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    keys.reverse()
    counts = Counter(_month_key(ts.date()) for ts in timestamps)
    return [TimeseriesPoint(label=k, value=counts.get(k, 0)) for k in keys]


def _top_n(counter: Counter, n: int = 10, label_fn=lambda x: x) -> list[BreakdownSlice]:
    return [BreakdownSlice(label=label_fn(k) or "Unknown", value=v) for k, v in counter.most_common(n)]


@router.get("/overview", response_model=OverviewCardsOut)
def overview(db: Session = Depends(get_db)):
    today_start = dt.datetime.combine(dt.datetime.utcnow().date(), dt.time.min)

    total_visitors = db.query(Visitor).count()
    unique_visitors = total_visitors  # Visitor rows are already 1-per-browser
    registered_users = db.query(User).count()

    active_users_today = (
        db.query(func.count(func.distinct(VisitorSession.user_id)))
        .filter(VisitorSession.user_id.isnot(None), VisitorSession.last_seen_at >= today_start)
        .scalar() or 0
    )
    logged_in_users_today = active_users_today
    anonymous_visitors_today = (
        db.query(func.count(func.distinct(VisitorSession.visitor_id)))
        .filter(VisitorSession.user_id.is_(None), VisitorSession.last_seen_at >= today_start)
        .scalar() or 0
    )
    total_page_views = db.query(PageView).count()

    all_sessions_count = db.query(VisitorSession).count()
    avg_duration = db.query(func.avg(VisitorSession.time_on_site_seconds)).scalar() or 0.0
    bounces = db.query(VisitorSession).filter(VisitorSession.is_bounce.is_(True)).count()
    bounce_rate = (bounces / all_sessions_count * 100.0) if all_sessions_count else 0.0

    returning_visitors = db.query(Visitor).filter(Visitor.total_visits > 1).count()
    new_users_today = db.query(User).filter(User.created_at >= today_start).count()
    total_tool_conversions = (
        db.query(UserActivityEvent).filter(UserActivityEvent.event_type == "migration_completed").count()
    )

    return OverviewCardsOut(
        total_visitors=total_visitors, unique_visitors=unique_visitors, registered_users=registered_users,
        active_users_today=active_users_today, logged_in_users_today=logged_in_users_today,
        anonymous_visitors_today=anonymous_visitors_today, total_page_views=total_page_views,
        avg_session_duration_seconds=round(float(avg_duration), 1), bounce_rate_pct=round(bounce_rate, 1),
        returning_visitors=returning_visitors, new_users_today=new_users_today,
        total_tool_conversions=total_tool_conversions,
    )


@router.get("/charts", response_model=AnalyticsChartsOut)
def charts(db: Session = Depends(get_db)):
    session_starts = [row[0] for row in db.query(VisitorSession.started_at).all()]
    signup_dates = [row[0] for row in db.query(User.created_at).all()]

    since_90d = dt.datetime.utcnow() - dt.timedelta(days=90)
    recent_sessions = db.query(VisitorSession).filter(VisitorSession.started_at >= since_90d).all()

    country_counter = Counter(s.country for s in recent_sessions if s.country)
    city_counter = Counter(f"{s.city}, {s.country}" for s in recent_sessions if s.city)
    source_counter = Counter(s.traffic_source or "Direct" for s in recent_sessions)
    device_counter = Counter(s.device_type or "unknown" for s in recent_sessions)
    browser_counter = Counter(s.browser or "Unknown" for s in recent_sessions)
    os_counter = Counter(s.os or "Unknown" for s in recent_sessions)
    logged_vs_guest = Counter("Logged-in" if s.user_id else "Guest" for s in recent_sessions)

    page_counter = Counter(
        row[0] for row in db.query(PageView.path).filter(PageView.viewed_at >= since_90d).all()
    )

    return AnalyticsChartsOut(
        daily_visitors=_daily_buckets(session_starts, 30),
        weekly_visitors=_weekly_buckets(session_starts, 12),
        monthly_visitors=_monthly_buckets(session_starts, 12),
        user_registrations=_daily_buckets(signup_dates, 30),
        top_countries=_top_n(country_counter, 10, _country_name),
        top_cities=_top_n(city_counter, 10),
        traffic_sources=_top_n(source_counter, 10),
        most_visited_pages=_top_n(page_counter, 10),
        device_breakdown=_top_n(device_counter, 10),
        browser_breakdown=_top_n(browser_counter, 10),
        os_breakdown=_top_n(os_counter, 10),
        logged_in_vs_guest=_top_n(logged_vs_guest, 2),
    )
