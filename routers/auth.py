from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from pwdlib import PasswordHash
from jose import jwt
from datetime import datetime, timedelta

from database.database import get_db
from database.models import User
from schemas.login import LoginResponse, LoginRequest
from schemas.register import RegisterRequest, RegisterResponse
from config import SECRET_KEY, ALGORITHM, TOKEN_EXPIRE_MINUTES


router = APIRouter(prefix="/auth", tags=["auth"])
password_hash = PasswordHash.recommended()

@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):

    # 1. Check email not already taken
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    if len(body.password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=400,
            detail="Password must be 72 bytes or less"
        )

    # 2. Hash the password
    hashed = password_hash.hash(body.password)

    # 3. Save new user
    new_user = User(
        name=body.name,
        email=body.email,
        hashed_password=hashed
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # 4. Return safe response
    return RegisterResponse(
        user_id=new_user.id,
        name=new_user.name,
        email=new_user.email
    )

def create_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    statement = select(User).where(User.email == body.email)
    user = db.execute(statement).scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not password_hash.verify(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_token(user.id)
    name = user.name
    return LoginResponse(name=name, email=body.email, access_token=token)