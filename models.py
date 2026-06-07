from typing import List
from sqlalchemy import String, Integer, DateTime, ForeignKey, Enum as SAEnum, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

import uuid

def generate_uuid():
    return str(uuid.uuid4())

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)

    # server_default maps safely to DateTime
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    # Use List["Pet"] type hinting inside Mapped for your 1-to-many relationship
    pets: Mapped[List["Pet"]] = relationship("Pet", back_populates="owner", cascade="all, delete-orphan")

class Pet(Base):
    __tablename__ = "pets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    pet_type: Mapped[str] = mapped_column(String(50), nullable=False)
    gender: Mapped[str] = mapped_column(SAEnum("male", "female", "unknown", name="gender_enum"), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    owner_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    owner: Mapped["User"] = relationship("User", back_populates="pets")
