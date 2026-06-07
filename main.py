from fastapi import FastAPI
from database.database import engine, Base
from routers import auth, pets
import database.models

app = FastAPI()
Base.metadata.create_all(bind=engine)
app.include_router(auth.router)
app.include_router(pets.router)

@app.get("/")
def root():
    return {"message": "PetMood API is running"}