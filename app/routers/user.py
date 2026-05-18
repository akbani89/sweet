from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User, DoctorTarget
from app.schemas.schemas import UserProfileUpdate, UserOut, DoctorTargetIn, DoctorTargetOut
from app.utils.auth import get_current_user

router = APIRouter(prefix="/user", tags=["user"])


@router.get("/me", response_model=UserOut)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserOut)
def update_profile(
    body: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    allowed = {"name", "age", "gender", "diabetes_status"}
    for field, value in body.model_dump(exclude_unset=True).items():
        if field in allowed and value is not None:
            setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/doctor-targets", response_model=DoctorTargetOut)
def get_doctor_targets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = db.query(DoctorTarget).filter(DoctorTarget.user_id == current_user.id).first()
    if not target:
        # Return ADA defaults if none set
        return DoctorTargetOut(fasting_min=70, fasting_max=99, post_meal_max=140)
    return target


@router.put("/doctor-targets", response_model=DoctorTargetOut)
def upsert_doctor_targets(
    body: DoctorTargetIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = db.query(DoctorTarget).filter(DoctorTarget.user_id == current_user.id).first()
    if target:
        target.fasting_min = body.fasting_min
        target.fasting_max = body.fasting_max
        target.post_meal_max = body.post_meal_max
    else:
        target = DoctorTarget(
            user_id=current_user.id,
            fasting_min=body.fasting_min,
            fasting_max=body.fasting_max,
            post_meal_max=body.post_meal_max,
        )
        db.add(target)
    db.commit()
    db.refresh(target)
    return target


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.is_active = False
    db.commit()
