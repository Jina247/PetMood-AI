from pydantic import BaseModel, EmailStr

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    name: str
    email: EmailStr
    access_token: str
    token_type: str = "bearer"