from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID


# ── Auth ──────────────────────────────────────────────────────────────────────

class OTPRequest(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, v: str) -> str:
        cleaned = "".join(filter(str.isdigit, v.replace("+", "")))
        if len(cleaned) < 10:
            raise ValueError("Invalid phone number")
        return cleaned


class OTPVerify(BaseModel):
    phone: str
    otp_code: str

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, v: str) -> str:
        cleaned = "".join(filter(str.isdigit, v.replace("+", "")))
        if len(cleaned) < 10:
            raise ValueError("Invalid phone number")
        return cleaned


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: UUID
    is_new_user: bool


# ── User ──────────────────────────────────────────────────────────────────────

class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    diabetes_status: Optional[str] = None


class UserOut(BaseModel):
    id: UUID
    phone: str
    name: Optional[str]
    age: Optional[int]
    gender: Optional[str]
    diabetes_status: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class DoctorTargetIn(BaseModel):
    fasting_min: int = 70
    fasting_max: int = 99
    post_meal_max: int = 140


class DoctorTargetOut(BaseModel):
    fasting_min: int
    fasting_max: int
    post_meal_max: int

    model_config = {"from_attributes": True}


# ── Glucose ───────────────────────────────────────────────────────────────────

class ManualReadingIn(BaseModel):
    value: int
    context: str = "random"  # fasting | post_meal | random
    notes: Optional[str] = None


class ReadingOut(BaseModel):
    id: UUID
    value: int
    context: str
    status: str
    severity: str
    color: str
    insight: Optional[str]
    ocr_confidence: Optional[float]
    is_manual: bool
    notes: Optional[str]
    recorded_at: datetime

    model_config = {"from_attributes": True}


class OCRResult(BaseModel):
    success: bool
    value: Optional[int]
    confidence: float
    reading: Optional[ReadingOut] = None
    error: Optional[str] = None


# ── Insights ──────────────────────────────────────────────────────────────────

class TrendPoint(BaseModel):
    date: str
    avg_value: float
    count: int
    status_breakdown: dict


class InsightSummary(BaseModel):
    period_days: int
    total_readings: int
    avg_glucose: Optional[float]
    readings_in_range_pct: Optional[float]
    trend: str  # improving | stable | worsening | insufficient_data
    highlights: List[str]
    recommendations: List[str]
    daily_trend: List[TrendPoint]
