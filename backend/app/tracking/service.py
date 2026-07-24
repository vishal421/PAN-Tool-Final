"""
Core tracking write-path. Kept separate from the route handlers so the
same logic is reusable/testable without spinning up FastAPI, and so
route handlers stay thin (parse request -> call service -> return ack).

Everything here is deliberately best-effort: a tracking failure must never
surface as a user-facing error, since it runs on every pageview of the real
product. Route handlers wrap calls to this module and swallow exceptions
after logging.
"""

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy.orm import Session

from app.models.database import PageView, User, UserActivityEvent, Visitor, VisitorSession
from app.tracking import geoip
from app.tracking.traffic_source import classify_traffic_source
from app.tracking.useragent import parse_user_agent

logger = logging.getLogger("app.tracking.service")


def _get_or_create_visitor(db: Session, visitor_id: str, user: User | None) -> Visitor:
    visitor = db.get(Visitor, visitor_id)
    now = dt.datetime.utcnow()
    if visitor is None:
        visitor = Visitor(id=visitor_id, user_id=user.id if user else None, first_seen_at=now, last_seen_at=now, total_visits=0)
        db.add(visitor)
    else:
        visitor.last_seen_at = now
        if user and not visitor.user_id:
            visitor.user_id = user.id  # a returning anonymous visitor just logged in - link it
    return visitor


def start_session(
    db: Session,
    *,
    visitor_id: str,
    session_id: str,
    path: str,
    ip_address: str | None,
    user_agent: str | None,
    referrer: str | None,
    utm_source: str | None,
    utm_medium: str | None,
    utm_campaign: str | None,
    utm_content: str | None,
    screen_resolution: str | None,
    language: str | None,
    user: User | None,
) -> VisitorSession:
    visitor = _get_or_create_visitor(db, visitor_id, user)
    visitor.total_visits += 1

    device = parse_user_agent(user_agent)
    location = geoip.lookup(ip_address)
    source = classify_traffic_source(referrer, utm_source, utm_medium)

    session = VisitorSession(
        id=session_id,
        visitor_id=visitor_id,
        user_id=user.id if user else None,
        entry_page=path,
        exit_page=path,
        page_view_count=0,  # the caller's record_pageview() call increments this
        is_bounce=True,
        ip_address=ip_address,
        country=location.country,
        region=location.region,
        city=location.city,
        timezone=location.timezone,
        browser=device.browser,
        browser_version=device.browser_version,
        os=device.os,
        device_type=device.device_type,
        screen_resolution=screen_resolution,
        language=language,
        user_agent=user_agent,
        referrer=referrer,
        traffic_source=source,
        utm_source=utm_source,
        utm_medium=utm_medium,
        utm_campaign=utm_campaign,
        utm_content=utm_content,
    )
    db.add(session)
    db.flush()
    return session


def record_pageview(
    db: Session,
    *,
    session_id: str,
    visitor_id: str,
    path: str,
    title: str | None,
    user: User | None,
) -> PageView:
    page_view = PageView(session_id=session_id, visitor_id=visitor_id, user_id=user.id if user else None,
                          path=path, title=title)
    db.add(page_view)

    session = db.get(VisitorSession, session_id)
    if session is not None:
        session.page_view_count += 1
        session.exit_page = path
        session.last_seen_at = dt.datetime.utcnow()
        if session.page_view_count > 1:
            session.is_bounce = False
        if user and not session.user_id:
            session.user_id = user.id

    visitor = db.get(Visitor, visitor_id)
    if visitor is not None:
        visitor.last_seen_at = dt.datetime.utcnow()

    return page_view


def record_beacon(
    db: Session,
    *,
    session_id: str,
    path: str | None,
    time_on_page_seconds: int | None,
    scroll_depth_pct: int | None,
) -> None:
    """Fired via navigator.sendBeacon on pagehide/visibilitychange - fills
    in the duration/scroll-depth for the most recent matching page view and
    extends the session's total time-on-site."""
    query = db.query(PageView).filter(PageView.session_id == session_id)
    if path:
        query = query.filter(PageView.path == path)
    page_view = query.order_by(PageView.viewed_at.desc()).first()
    if page_view is not None:
        if time_on_page_seconds is not None:
            page_view.time_on_page_seconds = time_on_page_seconds
        if scroll_depth_pct is not None:
            page_view.scroll_depth_pct = max(page_view.scroll_depth_pct or 0, scroll_depth_pct)

    session = db.get(VisitorSession, session_id)
    if session is not None and time_on_page_seconds:
        session.time_on_site_seconds += max(0, time_on_page_seconds)
        session.last_seen_at = dt.datetime.utcnow()


def record_event(
    db: Session,
    *,
    event_type: str,
    session_id: str | None,
    visitor_id: str | None,
    event_data: dict | None,
    user: User | None,
) -> UserActivityEvent:
    event = UserActivityEvent(
        session_id=session_id, visitor_id=visitor_id, user_id=user.id if user else None,
        event_type=event_type, event_data=event_data or {},
    )
    db.add(event)
    return event
