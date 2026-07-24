"""
Admin -> Users section: search/filter/paginate the registered-user list,
view a single user's full detail (profile + activity + login history), and
export the list as CSV or Excel. Every route here requires require_admin.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.admin.exports import rows_to_csv, rows_to_xlsx
from app.auth.core import require_admin
from app.models.database import (
    ConversionJob, LoginHistory, PageView, User, UserActivityEvent, VisitorSession, get_db,
)
from app.models.schemas import (
    AdminActivityEventRow, AdminLoginHistoryRow, AdminSetActiveIn, AdminSetAdminIn,
    AdminUserDetailOut, AdminUserListOut, AdminUserRow,
)

router = APIRouter(prefix="/admin/users", tags=["admin-users"], dependencies=[Depends(require_admin)])

_EXPORT_COLUMNS = [
    "first_name", "last_name", "email", "mobile_number", "mobile_country_code",
    "organization_name", "job_title", "city", "state", "country",
    "registration_date", "last_login", "login_count", "account_status", "email_verified",
    "total_sessions", "total_page_views", "last_activity", "ip_address", "browser", "os",
    "device_type", "referrer_source", "utm_source", "utm_medium", "utm_campaign", "utm_content",
]


def _latest_session_for(db: Session, user_id: str) -> VisitorSession | None:
    return (
        db.query(VisitorSession)
        .filter(VisitorSession.user_id == user_id)
        .order_by(VisitorSession.last_seen_at.desc())
        .first()
    )


def _build_user_row(db: Session, user: User) -> AdminUserRow:
    total_sessions = db.query(VisitorSession).filter(VisitorSession.user_id == user.id).count()
    total_page_views = db.query(PageView).filter(PageView.user_id == user.id).count()
    last_pv = (
        db.query(func.max(PageView.viewed_at)).filter(PageView.user_id == user.id).scalar()
    )
    latest_session = _latest_session_for(db, user.id)

    return AdminUserRow(
        id=user.id, first_name=user.first_name, last_name=user.last_name, email=user.email,
        mobile_number=user.mobile_number, mobile_country_code=user.mobile_country_code,
        organization_name=user.organization_name, job_title=user.job_title,
        city=user.city, state=user.state, country=user.country,
        registration_date=user.created_at, last_login=user.last_login_at, login_count=user.login_count,
        account_status="active" if user.is_active else "disabled",
        email_verified=user.email_verified, is_admin=user.is_admin, plan=user.plan,
        total_sessions=total_sessions, total_page_views=total_page_views,
        last_activity=last_pv or user.last_login_at,
        ip_address=latest_session.ip_address if latest_session else None,
        browser=latest_session.browser if latest_session else None,
        os=latest_session.os if latest_session else None,
        device_type=latest_session.device_type if latest_session else None,
        referrer_source=latest_session.traffic_source if latest_session else None,
        utm_source=latest_session.utm_source if latest_session else None,
        utm_medium=latest_session.utm_medium if latest_session else None,
        utm_campaign=latest_session.utm_campaign if latest_session else None,
        utm_content=latest_session.utm_content if latest_session else None,
    )


def _filtered_query(
    db: Session, q: str | None, plan: str | None, status: str | None, country: str | None,
):
    query = db.query(User)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(
            User.email.ilike(like), User.first_name.ilike(like), User.last_name.ilike(like),
            User.organization_name.ilike(like),
        ))
    if plan:
        query = query.filter(User.plan == plan)
    if status:
        query = query.filter(User.is_active == (status == "active"))
    if country:
        query = query.filter(User.country == country.upper())
    return query.order_by(User.created_at.desc())


@router.get("", response_model=AdminUserListOut)
def list_users(
    q: str | None = None,
    plan: str | None = None,
    status: str | None = Query(default=None, pattern="^(active|disabled)$"),
    country: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = _filtered_query(db, q, plan, status, country)
    total = query.count()
    users = query.offset((page - 1) * page_size).limit(page_size).all()
    return AdminUserListOut(
        total=total, page=page, page_size=page_size,
        users=[_build_user_row(db, u) for u in users],
    )


def _export_rows(db: Session, q: str | None, plan: str | None, status: str | None, country: str | None) -> list[dict]:
    users = _filtered_query(db, q, plan, status, country).all()
    return [_build_user_row(db, u).model_dump() for u in users]


@router.get("/export.csv")
def export_users_csv(
    q: str | None = None, plan: str | None = None,
    status: str | None = Query(default=None, pattern="^(active|disabled)$"),
    country: str | None = None, db: Session = Depends(get_db),
):
    rows = _export_rows(db, q, plan, status, country)
    csv_text = rows_to_csv(rows, _EXPORT_COLUMNS)
    return Response(
        content=csv_text, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=registered_users.csv"},
    )


@router.get("/export.xlsx")
def export_users_xlsx(
    q: str | None = None, plan: str | None = None,
    status: str | None = Query(default=None, pattern="^(active|disabled)$"),
    country: str | None = None, db: Session = Depends(get_db),
):
    rows = _export_rows(db, q, plan, status, country)
    xlsx_bytes = rows_to_xlsx(rows, _EXPORT_COLUMNS, sheet_title="Registered Users")
    return Response(
        content=xlsx_bytes, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=registered_users.xlsx"},
    )


@router.get("/{user_id}", response_model=AdminUserDetailOut)
def user_detail(user_id: str, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found.")

    job_count = db.query(ConversionJob).filter(ConversionJob.user_id == user.id).count()
    recent_logins = (
        db.query(LoginHistory).filter(LoginHistory.user_id == user.id)
        .order_by(LoginHistory.occurred_at.desc()).limit(20).all()
    )
    recent_activity = (
        db.query(UserActivityEvent).filter(UserActivityEvent.user_id == user.id)
        .order_by(UserActivityEvent.occurred_at.desc()).limit(50).all()
    )

    return AdminUserDetailOut(
        user=_build_user_row(db, user), job_count=job_count,
        recent_logins=[AdminLoginHistoryRow.model_validate(r) for r in recent_logins],
        recent_activity=[AdminActivityEventRow.model_validate(r) for r in recent_activity],
    )


@router.patch("/{user_id}/admin", response_model=AdminUserRow)
def set_admin(user_id: str, body: AdminSetAdminIn, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found.")
    user.is_admin = body.is_admin
    db.commit()
    return _build_user_row(db, user)


@router.patch("/{user_id}/status", response_model=AdminUserRow)
def set_active(user_id: str, body: AdminSetActiveIn, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found.")
    user.is_active = body.is_active
    db.commit()
    return _build_user_row(db, user)
