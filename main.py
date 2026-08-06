import logging
import os
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI

from config import GEMINI_API_KEY
from routers import auth, pets, scans

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

logger = logging.getLogger(__name__)


def run_migrations() -> None:
    alembic_cfg = Config(os.path.join(BASE_DIR, "alembic.ini"))
    command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is not set — scan analysis will fail until it's configured.")
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(auth.router)
app.include_router(pets.router)
app.include_router(scans.router)
@app.get("/")
def root():
    return {"message": "PetMood API is running"}