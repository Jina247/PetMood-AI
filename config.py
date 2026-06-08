import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
TOKEN_EXPIRATION = 60 * 24
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./petmood.db")