from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional

class Gender(str, Enum):
    male = "male"
    female = "female"
    unknown = "unknown"

class PetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    age: int = Field(ge=0, le=20)
    pet_type: str = Field(min_length=1, max_length=50)
    gender: Gender
    photoUri: str = None

class PetResponse(BaseModel):
    id: str
    name: str
    age: int
    pet_type: str
    gender: Gender
    photoUri: str
    owner_id: str

    class Config:
        from_attributes = True

class PetUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    age: Optional[int] = Field(default=None, ge=0, le=20)
    pet_type: Optional[str] = Field(default=None, min_length=1, max_length=50)
    gender: Optional[Gender] = None
    photoUri: Optional[str] = None
