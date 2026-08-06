from datetime import datetime
from typing import List
from sqlalchemy import String, Integer, DateTime, ForeignKey, Enum as SAEnum, func, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

import uuid

from database.database import Base


def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    pets: Mapped[List["Pet"]] = relationship("Pet", back_populates="owner", cascade="all, delete-orphan")

class Pet(Base):
    __tablename__ = "pets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    pet_type: Mapped[str] = mapped_column(String(50), nullable=False)
    gender: Mapped[str] = mapped_column(SAEnum("male", "female", "unknown", name="gender_enum"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    photo_uri: Mapped[str] = mapped_column(String, nullable=True)
    owner_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    owner: Mapped["User"] = relationship("User", back_populates="pets")
    scans: Mapped[List["Scan"]] = relationship("Scan", back_populates="pet", cascade="all, delete-orphan")

class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    status: Mapped[str] = mapped_column(
        SAEnum("processing", "complete", "failed", name="scan_status"),
        default="processing"
    )
    mood_result: Mapped[str] = mapped_column(String, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=True)
    video_path: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    summary: Mapped[str] = mapped_column(String, nullable=True)
    error_message: Mapped[str] = mapped_column(String, nullable=True)

    pet_id: Mapped[str] = mapped_column(String, ForeignKey("pets.id"), nullable=False)
    pet: Mapped["Pet"] = relationship("Pet", back_populates="scans")