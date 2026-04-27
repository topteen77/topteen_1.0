from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from ..security import get_current_username

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/counselor", tags=["counselor-dashboard"])


@router.get("/{coun_id}/dashboard")
def counselor_dashboard(
    coun_id: int,
    email: str = Depends(get_current_username),
    ttv2_week_start: str | None = Query(
        default=None,
        description="Optional Monday (YYYY-MM-DD) for v2 week-scoped analytics.",
    ),
    per_page: str = Query(default="10"),
):
    """
    Data needed for the counselor dashboard (aligns with `CounselorDashboard` view context).

    **Auth:** `Authorization: Bearer <access_token>` (JWT `sub` must be a **Django user email**
    that is allowed to open this dashboard — typically the counselor user).

    **Setup:** run FastAPI with Django + MySQL client deps (see `fastapi/requirements.txt`) so
    the same `DB_*` database as the main app can be queried.
    """
    try:
        from ..django_bridge import init_django
        from ..counselor_dashboard_service import load_counselor_dashboard

        init_django()
    except Exception as e:
        logger.exception("Django bridge failed")
        raise HTTPException(
            status_code=503,
            detail=f"Django/DB not available: {e!s}. "
            "From `fastapi/`: `pip install -r ../requirements.txt` (project apps + decouple + mysqlclient) "
            "and ensure root `.env` has working `DB_*` (same as Django).",
        ) from e

    try:
        return load_counselor_dashboard(
            coun_id=coun_id,
            token_email=email,
            ttv2_week_start=ttv2_week_start,
            per_page=per_page,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Counselor dashboard data failed")
        raise HTTPException(status_code=500, detail=str(e)) from e
