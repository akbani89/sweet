from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import GlucoseReading, DoctorTarget, User
from app.schemas.schemas import ReadingOut, ManualReadingIn, OCRResult
from app.services import ocr_service, rules_engine, insights_engine, storage_service
from app.utils.auth import get_current_user

router = APIRouter(prefix="/glucose", tags=["glucose"])

_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_SIZE_MB = 10


@router.post("/scan", response_model=OCRResult)
async def scan_reading(
    file: UploadFile = File(...),
    context: str = Form(default="random"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a glucometer photo.
    Returns the extracted value, classification, and a plain-English insight.
    """
    if file.content_type not in _ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type. Use: {', '.join(_ALLOWED_TYPES)}",
        )

    image_bytes = await file.read()
    if len(image_bytes) > _MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image must be under {_MAX_SIZE_MB} MB",
        )

    # ── OCR ──────────────────────────────────────────────────────────────────
    ocr = ocr_service.extract_glucose_value(image_bytes)

    if not ocr["success"]:
        return OCRResult(
            success=False,
            value=None,
            confidence=0.0,
            error=ocr.get("error", "Could not read a glucose value from this image"),
        )

    # ── Rules + insights ──────────────────────────────────────────────────────
    doctor_targets = _get_doctor_targets(current_user.id, db)
    classification = rules_engine.classify(ocr["value"], context, doctor_targets)

    user_profile = {"diabetes_status": current_user.diabetes_status}
    insight = insights_engine.generate_insight(
        ocr["value"], classification["status"], context, user_profile
    )

    # ── Persist image ─────────────────────────────────────────────────────────
    image_key = storage_service.save_image(image_bytes, str(current_user.id), file.content_type)

    # ── Persist reading ───────────────────────────────────────────────────────
    reading = GlucoseReading(
        user_id=current_user.id,
        value=ocr["value"],
        context=context,
        status=classification["status"],
        severity=classification["severity"],
        color=classification["color"],
        insight=insight,
        ocr_confidence=ocr["confidence"],
        image_key=image_key,
        is_manual=False,
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)

    return OCRResult(
        success=True,
        value=ocr["value"],
        confidence=ocr["confidence"],
        reading=ReadingOut.model_validate(reading),
    )


@router.post("/manual", response_model=ReadingOut, status_code=status.HTTP_201_CREATED)
def add_manual_reading(
    body: ManualReadingIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a manually entered glucose value (no image required)."""
    doctor_targets = _get_doctor_targets(current_user.id, db)
    classification = rules_engine.classify(body.value, body.context, doctor_targets)

    user_profile = {"diabetes_status": current_user.diabetes_status}
    insight = insights_engine.generate_insight(
        body.value, classification["status"], body.context, user_profile
    )

    reading = GlucoseReading(
        user_id=current_user.id,
        value=body.value,
        context=body.context,
        status=classification["status"],
        severity=classification["severity"],
        color=classification["color"],
        insight=insight,
        ocr_confidence=None,
        is_manual=True,
        notes=body.notes,
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return reading


@router.get("/history", response_model=List[ReadingOut])
def get_history(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    context: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return paginated reading history, newest first."""
    q = db.query(GlucoseReading).filter(GlucoseReading.user_id == current_user.id)
    if context:
        q = q.filter(GlucoseReading.context == context)
    readings = q.order_by(GlucoseReading.recorded_at.desc()).offset(offset).limit(limit).all()
    return readings


@router.get("/history/{reading_id}", response_model=ReadingOut)
def get_reading(
    reading_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reading = db.query(GlucoseReading).filter(
        GlucoseReading.id == reading_id,
        GlucoseReading.user_id == current_user.id,
    ).first()
    if not reading:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reading not found")
    return reading


@router.delete("/history/{reading_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reading(
    reading_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reading = db.query(GlucoseReading).filter(
        GlucoseReading.id == reading_id,
        GlucoseReading.user_id == current_user.id,
    ).first()
    if not reading:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reading not found")
    if reading.image_key:
        storage_service.delete_image(reading.image_key)
    db.delete(reading)
    db.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_doctor_targets(user_id, db: Session) -> Optional[dict]:
    target = db.query(DoctorTarget).filter(DoctorTarget.user_id == user_id).first()
    if not target:
        return None
    return {
        "fasting_min":   target.fasting_min,
        "fasting_max":   target.fasting_max,
        "post_meal_max": target.post_meal_max,
    }
