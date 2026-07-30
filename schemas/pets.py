from pydantic import BaseModel, ConfigDict, Field
from enum import Enum
from typing import Optional

class Gender(str, Enum):
    male = "male"
    female = "female"
    unknown = "unknown"

class PetCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=50)
    age: int = Field(ge=0, le=20)
    pet_type: str = Field(min_length=1, max_length=50)
    gender: Gender
    photo_uri: Optional[str] = Field(default=None, alias="photoUri")

class PetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    name: str
    age: int
    pet_type: str
    gender: Gender
    photo_uri: Optional[str] = Field(default=None, alias="photoUri")
    owner_id: str

class PetUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    age: Optional[int] = Field(default=None, ge=0, le=20)
    pet_type: Optional[str] = Field(default=None, min_length=1, max_length=50)
    gender: Optional[Gender] = None
    photo_uri: Optional[str] = Field(default=None, alias="photoUri")
