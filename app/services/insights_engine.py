"""
Insights Engine — generates human-readable insights from a classification
and trend analysis from reading history.

All logic is rule-based and explainable. No black-box ML in V1.
"""

from typing import Optional
from app.services.rules_engine import THRESHOLDS


# ── Single-reading insight ────────────────────────────────────────────────────

def generate_insight(value: int, status: str, context: str, user_profile: dict = None) -> str:
    """Return a 1-2 sentence plain-English insight for a single reading."""
    context_label = {
        "fasting":    "fasting",
        "post_meal":  "after your meal",
        "random":     "",
    }.get(context, "")

    ctx_str = f" {context_label}" if context_label else ""

    if status == "low":
        return (
            f"Your glucose{ctx_str} is {value} mg/dL — that's below the safe range. "
            "Please eat or drink something sugary right away and rest."
        )

    if status == "normal":
        return (
            f"Your glucose{ctx_str} is {value} mg/dL — well within the healthy range. "
            "Keep up your current routine."
        )

    if status == "prediabetes":
        diabetes_type = (user_profile or {}).get("diabetes_status", "unknown")
        if diabetes_type in ("type1", "type2"):
            return (
                f"Your glucose{ctx_str} is {value} mg/dL — slightly above your target. "
                "Consider a short walk or reviewing your last meal."
            )
        return (
            f"Your glucose{ctx_str} is {value} mg/dL — in the borderline range. "
            "Try to reduce refined carbs and stay active today."
        )

    if status == "high":
        if value >= 300:
            return (
                f"Your glucose{ctx_str} is very high at {value} mg/dL. "
                "Please contact your doctor or seek medical attention if you feel unwell."
            )
        return (
            f"Your glucose{ctx_str} is {value} mg/dL — higher than the recommended range. "
            "Drink water, avoid carbs for now, and check again in 2 hours."
        )

    return f"Your glucose{ctx_str} is {value} mg/dL."


# ── Trend analysis ────────────────────────────────────────────────────────────

def analyse_trend(readings: list) -> dict:
    """
    readings: list of GlucoseReading ORM objects (most recent first)
    Returns an InsightSummary-compatible dict.
    """
    if not readings:
        return _empty_summary(7)

    period_days = 7
    total = len(readings)

    values = [r.value for r in readings]
    avg = round(sum(values) / total, 1)

    normal_count = sum(1 for r in readings if r.status == "normal")
    in_range_pct = round((normal_count / total) * 100, 1) if total else None

    trend = _compute_trend(readings)
    highlights = _build_highlights(avg, in_range_pct, readings, trend)
    recommendations = _build_recommendations(avg, in_range_pct, readings)

    daily_trend = _daily_breakdown(readings)

    return {
        "period_days": period_days,
        "total_readings": total,
        "avg_glucose": avg,
        "readings_in_range_pct": in_range_pct,
        "trend": trend,
        "highlights": highlights,
        "recommendations": recommendations,
        "daily_trend": daily_trend,
    }


def _compute_trend(readings: list) -> str:
    if len(readings) < 4:
        return "insufficient_data"

    # Compare first half average vs second half average (oldest → newest)
    ordered = list(reversed(readings))  # oldest first
    mid = len(ordered) // 2
    older_avg = sum(r.value for r in ordered[:mid]) / mid
    newer_avg = sum(r.value for r in ordered[mid:]) / (len(ordered) - mid)

    diff = newer_avg - older_avg
    if abs(diff) <= 5:
        return "stable"
    return "worsening" if diff > 0 else "improving"


def _build_highlights(avg: float, in_range_pct: Optional[float], readings: list, trend: str) -> list:
    h = []
    if in_range_pct is not None:
        h.append(f"{in_range_pct}% of your readings were in the normal range this week")
    if trend == "improving":
        h.append("Your glucose levels are trending downward — great progress")
    elif trend == "worsening":
        h.append("Your readings have been creeping up over the last few days")
    elif trend == "stable":
        h.append("Your levels have been consistent over the past week")

    high_count = sum(1 for r in readings if r.status == "high")
    if high_count:
        h.append(f"{high_count} reading{'s' if high_count > 1 else ''} were in the high range")

    low_count = sum(1 for r in readings if r.status == "low")
    if low_count:
        h.append(f"{low_count} low reading{'s' if low_count > 1 else ''} detected — watch for hypoglycemia")

    return h


def _build_recommendations(avg: float, in_range_pct: Optional[float], readings: list) -> list:
    recs = []

    if avg > 180:
        recs.append("Your weekly average is high — consider speaking with your doctor about your current plan")
    elif avg > 130:
        recs.append("Focus on reducing refined carbs at your main meals this week")

    if in_range_pct is not None and in_range_pct < 50:
        recs.append("Try to log readings at consistent times — fasting and 2 hours after meals give the clearest picture")

    if len(readings) < 5:
        recs.append("Aim for at least one reading per day to get meaningful trend data")

    if not recs:
        recs.append("You're doing well — keep logging consistently and maintaining your current habits")

    return recs


def _daily_breakdown(readings: list) -> list:
    from collections import defaultdict
    from datetime import timezone

    days: dict = defaultdict(list)
    for r in readings:
        day = r.recorded_at.strftime("%Y-%m-%d")
        days[day].append(r)

    result = []
    for day in sorted(days.keys()):
        day_readings = days[day]
        day_values = [r.value for r in day_readings]
        breakdown = {}
        for r in day_readings:
            breakdown[r.status] = breakdown.get(r.status, 0) + 1
        result.append({
            "date": day,
            "avg_value": round(sum(day_values) / len(day_values), 1),
            "count": len(day_readings),
            "status_breakdown": breakdown,
        })
    return result


def _empty_summary(period_days: int) -> dict:
    return {
        "period_days": period_days,
        "total_readings": 0,
        "avg_glucose": None,
        "readings_in_range_pct": None,
        "trend": "insufficient_data",
        "highlights": ["No readings found for this period — start scanning to see your trends"],
        "recommendations": ["Take your first glucose reading to get started"],
        "daily_trend": [],
    }
