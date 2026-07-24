"""
Public tracking + metadata endpoints. No auth required (these run for
anonymous visitors), but if a valid Bearer token IS present the event gets
attributed to that user via get_current_user_optional.

Kept intentionally forgiving: malformed/missing visitor or session ids just
get a 202-with-no-op rather than a 4xx, since a tracking beacon failing
should never surface to the end user or spam error logs.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth.core import client_ip, get_current_user_optional
from app.core.countries import COUNTRIES
from app.models.database import User, get_db
from app.models.schemas import ACTIVITY_EVENT_TYPES, BeaconIn, CountryOut, MessageOut, PageViewIn, TrackEventIn
from app.tracking import service

router = APIRouter(tags=["tracking"])
logger = logging.getLogger("app.tracking.routes")


@router.get("/meta/countries", response_model=list[CountryOut])
def countries():
    return COUNTRIES


@router.post("/track/pageview", response_model=MessageOut)
def track_pageview(
    body: PageViewIn, request: Request,
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    try:
        if body.is_new_session:
            service.start_session(
                db, visitor_id=body.visitor_id, session_id=body.session_id, path=body.path,
                ip_address=client_ip(request), user_agent=request.headers.get("user-agent"),
                referrer=body.referrer, utm_source=body.utm_source, utm_medium=body.utm_medium,
                utm_campaign=body.utm_campaign, utm_content=body.utm_content,
                screen_resolution=body.screen_resolution, language=body.language, user=user,
            )
        service.record_pageview(
            db, session_id=body.session_id, visitor_id=body.visitor_id,
            path=body.path, title=body.title, user=user,
        )
        db.commit()
    except Exception:
        logger.exception("Pageview tracking failed (non-fatal)")
        db.rollback()
    return MessageOut(message="ok")


@router.post("/track/beacon", response_model=MessageOut)
def track_beacon(body: BeaconIn, db: Session = Depends(get_db)):
    try:
        service.record_beacon(
            db, session_id=body.session_id, path=body.path,
            time_on_page_seconds=body.time_on_page_seconds, scroll_depth_pct=body.scroll_depth_pct,
        )
        db.commit()
    except Exception:
        logger.exception("Beacon tracking failed (non-fatal)")
        db.rollback()
    return MessageOut(message="ok")


@router.post("/track/event", response_model=MessageOut)
def track_event(
    body: TrackEventIn,
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    if body.event_type not in ACTIVITY_EVENT_TYPES:
        return MessageOut(message="ignored")  # unknown event type - no-op rather than 422
    try:
        service.record_event(
            db, event_type=body.event_type, session_id=body.session_id,
            visitor_id=body.visitor_id, event_data=body.event_data, user=user,
        )
        db.commit()
    except Exception:
        logger.exception("Event tracking failed (non-fatal)")
        db.rollback()
    return MessageOut(message="ok")
