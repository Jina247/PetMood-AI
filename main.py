from fastapi import FastAPI
from database import engine, Base
from routers import auth
from models import User, Pet
app = FastAPI()
Base.metadata.create_all(bind=engine)
app.include_router(auth.router)

@app.get("/")
def root():
    return {"message": "PetMood API is running"}