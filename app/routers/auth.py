from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models.models import User, OTPSession
from app.schemas.schemas import OTPRequest, OTPVerify, TokenResponse
from app.utils.auth import generate_otp, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/request-otp")
def request_otp(body: OTPRequest, db: Session = Depends(get_db)):
    """
    Send (or re-send) a 6-digit OTP to the given phone number.
    Creates the user record on first contact.
    In DEV_MODE the OTP is returned in the response — disable in production.
    """
    # Get or create user
    user = db.query(User).filter(User.phone == body.phone).first()
    is_new = False
    if not user:
        user = User(phone=body.phone)
        db.add(user)
        db.flush()
        is_new = True

    # Invalidate any existing unused OTPs for this user
    db.query(OTPSession).filter(
        OTPSession.user_id == user.id,
        OTPSession.is_used == False,
    ).update({"is_used": True})

    otp_code = generate_otp()
    expires = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)

    session = OTPSession(user_id=user.id, otp_code=otp_code, expires_at=expires)
    db.add(session)
    db.commit()

    # TODO: integrate Twilio/any SMS provider here
    # send_sms(body.phone, f"Your GlucoSnap code is {otp_code}")

    response = {"message": "OTP sent", "is_new_user": is_new}
    if settings.DEV_MODE:
        response["dev_otp"] = otp_code  # Remove in production

    return response


@router.post("/verify-otp", response_model=TokenResponse)
def verify_otp(body: OTPVerify, db: Session = Depends(get_db)):
    """Verify OTP and return a JWT access token."""
    user = db.query(User).filter(User.phone == body.phone).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    otp_session = (
        db.query(OTPSession)
        .filter(
            OTPSession.user_id == user.id,
            OTPSession.otp_code == body.otp_code,
            OTPSession.is_used == False,
            OTPSession.expires_at > datetime.utcnow(),
        )
        .order_by(OTPSession.created_at.desc())
        .first()
    )

    if not otp_session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP",
        )

    otp_session.is_used = True
    db.commit()

    token = create_access_token(str(user.id))
    is_new = user.name is None  # No profile set yet → treat as new

    return TokenResponse(
        access_token=token,
        user_id=user.id,
        is_new_user=is_new,
    )
