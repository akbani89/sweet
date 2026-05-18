from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import GlucoseReading, User
from app.schemas.schemas import InsightSummary, TrendPoint
from app.services import insights_engine
from app.utils.auth import get_current_user

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/summary", response_model=InsightSummary)
def get_summary(
    days: int = Query(default=7, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return a trend summary for the last N days.
    Default is 7 days (the home screen weekly view).
    """
    since = datetime.utcnow() - timedelta(days=days)
    readings = (
        db.query(GlucoseReading)
        .filter(
            GlucoseReading.user_id == current_user.id,
            GlucoseReading.recorded_at >= since,
        )
        .order_by(GlucoseReading.recorded_at.desc())
        .all()
    )

    summary = insights_engine.analyse_trend(readings)
    summary["period_days"] = days

    # Coerce daily_trend dicts → TrendPoint schema
    summary["daily_trend"] = [
        TrendPoint(**point) for point in summary["daily_trend"]
    ]

    return InsightSummary(**summary)


@router.get("/latest-insight")
def latest_insight(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the insight from the most recent reading — used on the home screen."""
    reading = (
        db.query(GlucoseReading)
        .filter(GlucoseReading.user_id == current_user.id)
        .order_by(GlucoseReading.recorded_at.desc())
        .first()
    )

    if not reading:
        return {
            "has_reading": False,
            "insight": "Take your first reading to get started.",
        }

    return {
        "has_reading": True,
        "value": reading.value,
        "status": reading.status,
        "color": reading.color,
        "insight": reading.insight,
        "recorded_at": reading.recorded_at,
    }
