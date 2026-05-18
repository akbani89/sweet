import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)          # male | female | other
    diabetes_status = Column(String(30), nullable=True) # type1 | type2 | prediabetes | none | unknown
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    readings = relationship("GlucoseReading", back_populates="user", cascade="all, delete")
    otp_sessions = relationship("OTPSession", back_populates="user", cascade="all, delete")
    doctor_target = relationship("DoctorTarget", back_populates="user", uselist=False, cascade="all, delete")


class OTPSession(Base):
    __tablename__ = "otp_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    otp_code = Column(String(6), nullable=False)
    is_used = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="otp_sessions")


class GlucoseReading(Base):
    __tablename__ = "glucose_readings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    value = Column(Integer, nullable=False)              # mg/dL
    context = Column(String(20), default="random")      # fasting | post_meal | random
    status = Column(String(20), nullable=False)         # low | normal | prediabetes | high
    severity = Column(String(20), nullable=False)       # good | warning | critical
    color = Column(String(10), nullable=False)          # green | yellow | red
    insight = Column(Text, nullable=True)               # plain-language insight
    ocr_confidence = Column(Float, nullable=True)       # 0.0 - 1.0
    image_key = Column(String(500), nullable=True)      # S3/local path for the scan image
    is_manual = Column(Boolean, default=False)          # manually entered vs scanned
    notes = Column(Text, nullable=True)                 # user notes
    recorded_at = Column(DateTime, default=datetime.utcnow)  # when the reading was taken
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="readings")


class DoctorTarget(Base):
    __tablename__ = "doctor_targets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    fasting_min = Column(Integer, default=70)
    fasting_max = Column(Integer, default=99)
    post_meal_max = Column(Integer, default=140)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="doctor_target")
