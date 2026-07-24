"""Admin -> SEO Page Analytics (spec sections 5 & 8): per-landing-page stats
and cross-page SEO insights (organic vs direct vs referral, entry/exit pages)."""

from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.admin.routes_analytics import _country_name, _daily_buckets, _monthly_buckets, _top_n, _weekly_buckets
from app.auth.core import require_admin
from app.models.database import PageView, Visitor, VisitorSession, get_db
from app.models.schemas import SeoInsightsOut, SeoPageStatsOut

router = APIRouter(prefix="/admin/seo", tags=["admin-seo"], dependencies=[Depends(require_admin)])

# The specific SEO landing pages called out in the spec, in display order.
TRACKED_PAGES: dict[str, str] = {
    "/": "Home Page",
    "/fortigate-to-palo-alto-migration": "Fortigate-to-Palo-Alto-Migration",
    "/checkpoint-to-palo-alto-migration": "Checkpoint-to-Palo-Alto-Migration",
    "/cisco-to-palo-alto-migration": "Cisco-to-Palo-Alto-Migration",
    "/sophos-to-palo-alto-migration": "Sophos-to-Palo-Alto-Migration",
}


def _page_stats(db: Session, path: str, label: str) -> SeoPageStatsOut:
    page_views = db.query(PageView).filter(PageView.path == path).all()
    total_views = len(page_views)
    visitor_ids = {pv.visitor_id for pv in page_views}
    logged_in_users = len({pv.user_id for pv in page_views if pv.user_id})
    anonymous_users = len({pv.visitor_id for pv in page_views if not pv.user_id})

    returning_visitors = 0
    if visitor_ids:
        returning_visitors = (
            db.query(Visitor).filter(Visitor.id.in_(visitor_ids), Visitor.total_visits > 1).count()
        )

    durations = [pv.time_on_page_seconds for pv in page_views if pv.time_on_page_seconds is not None]
    avg_time = sum(durations) / len(durations) if durations else 0.0
    scrolls = [pv.scroll_depth_pct for pv in page_views if pv.scroll_depth_pct is not None]
    avg_scroll = (sum(scrolls) / len(scrolls)) if scrolls else None

    landing_sessions = db.query(VisitorSession).filter(VisitorSession.entry_page == path).all()
    bounce_rate = 0.0
    if landing_sessions:
        bounce_rate = sum(1 for s in landing_sessions if s.is_bounce) / len(landing_sessions) * 100.0

    country_counter = Counter(s.country for s in landing_sessions if s.country)
    city_counter = Counter(f"{s.city}, {s.country}" for s in landing_sessions if s.city)
    source_counter = Counter(s.traffic_source or "Direct" for s in landing_sessions)

    viewed_at_list = [pv.viewed_at for pv in page_views]

    return SeoPageStatsOut(
        path=path, label=label, total_views=total_views, unique_visitors=len(visitor_ids),
        returning_visitors=returning_visitors, logged_in_users=logged_in_users, anonymous_users=anonymous_users,
        avg_time_on_page_seconds=round(avg_time, 1), bounce_rate_pct=round(bounce_rate, 1),
        avg_scroll_depth_pct=round(avg_scroll, 1) if avg_scroll is not None else None,
        top_countries=_top_n(country_counter, 5, _country_name),
        top_cities=_top_n(city_counter, 5),
        traffic_sources=_top_n(source_counter, 5),
        daily_views=_daily_buckets(viewed_at_list, 30),
        weekly_views=_weekly_buckets(viewed_at_list, 12),
        monthly_views=_monthly_buckets(viewed_at_list, 12),
    )


@router.get("/pages", response_model=list[SeoPageStatsOut])
def seo_pages(db: Session = Depends(get_db)):
    return [_page_stats(db, path, label) for path, label in TRACKED_PAGES.items()]


@router.get("/pages/{path:path}", response_model=SeoPageStatsOut)
def seo_page_detail(path: str, db: Session = Depends(get_db)):
    normalized = "/" + path.lstrip("/") if path != "/" else "/"
    label = TRACKED_PAGES.get(normalized, normalized)
    return _page_stats(db, normalized, label)


@router.get("/insights", response_model=SeoInsightsOut)
def seo_insights(db: Session = Depends(get_db)):
    all_sessions = db.query(VisitorSession).all()
    total = len(all_sessions)

    entry_counter = Counter(s.entry_page for s in all_sessions if s.entry_page)
    exit_counter = Counter(s.exit_page for s in all_sessions if s.exit_page)
    source_counter = Counter(s.traffic_source or "Direct" for s in all_sessions)

    organic = sum(v for k, v in source_counter.items() if "search" in k.lower() or k in (
        "Google Search", "Bing", "Yahoo", "DuckDuckGo", "Baidu", "Yandex"))
    direct = source_counter.get("Direct", 0)
    email_traffic = source_counter.get("Email Campaign", 0)
    referral = sum(v for k, v in source_counter.items() if k not in (
        "Direct", "Email Campaign", "Google Search", "Bing", "Yahoo", "DuckDuckGo", "Baidu", "Yandex"))

    returning_pct = 0.0
    if total:
        returning_sessions = sum(1 for s in all_sessions if s.visitor_id and _is_returning(db, s.visitor_id))
        returning_pct = returning_sessions / total * 100.0

    avg_duration = (sum(s.time_on_site_seconds for s in all_sessions) / total) if total else 0.0
    avg_pages = (sum(s.page_view_count for s in all_sessions) / total) if total else 0.0

    most_visited = entry_counter.most_common(1)
    best_converting = _best_converting_landing_page(db)

    return SeoInsightsOut(
        most_visited_landing_page=most_visited[0][0] if most_visited else None,
        best_converting_landing_page=best_converting,
        organic_search_traffic=organic, direct_traffic=direct, referral_traffic=referral,
        email_traffic=email_traffic, returning_users_pct=round(returning_pct, 1),
        avg_session_duration_seconds=round(avg_duration, 1), avg_pages_per_session=round(avg_pages, 2),
        top_entry_pages=_top_n(entry_counter, 10),
        top_exit_pages=_top_n(exit_counter, 10),
    )


_returning_cache: dict[str, bool] = {}


def _is_returning(db: Session, visitor_id: str) -> bool:
    if visitor_id not in _returning_cache:
        visitor = db.get(Visitor, visitor_id)
        _returning_cache[visitor_id] = bool(visitor and visitor.total_visits > 1)
    return _returning_cache[visitor_id]


def _best_converting_landing_page(db: Session) -> str | None:
    """'Best converting' = highest (sessions that logged a migration_completed
    event / sessions landing on that page) ratio, among pages with >=5 landings."""
    from app.models.database import UserActivityEvent

    landings = Counter(
        row[0] for row in db.query(VisitorSession.entry_page).filter(VisitorSession.entry_page.isnot(None)).all()
    )
    conversions = Counter(
        row[0] for row in (
            db.query(VisitorSession.entry_page)
            .join(UserActivityEvent, UserActivityEvent.session_id == VisitorSession.id)
            .filter(UserActivityEvent.event_type == "migration_completed", VisitorSession.entry_page.isnot(None))
            .all()
        )
    )
    best_page, best_rate = None, 0.0
    for page, landing_count in landings.items():
        if landing_count < 5:
            continue
        rate = conversions.get(page, 0) / landing_count
        if rate > best_rate:
            best_page, best_rate = page, rate
    return best_page
