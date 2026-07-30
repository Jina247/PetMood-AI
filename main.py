from fastapi import FastAPI
from routers import auth, pets, scans

app = FastAPI()
app.include_router(auth.router)
app.include_router(pets.router)
app.include_router(scans.router)
@app.get("/")
def root():
    return {"message": "PetMood API is running"}