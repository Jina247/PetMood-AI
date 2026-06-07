from pydantic import BaseModel, EmailStr, Field

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)

class RegisterResponse(BaseModel):
    user_id: str
    name: str
    email: str