import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60 * 24
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./petmood.db")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Firebase service-account key: either the JSON content itself (FIREBASE_CRED_JSON — use this on
# Azure, where deploys don't include the gitignored key file) or a path to the file (FIREBASE_CRED,
# handy for local dev). JSON content wins if both are set.
FIREBASE_KEY_JSON = os.getenv("FIREBASE_CRED_JSON")
FIREBASE_KEY = os.getenv("FIREBASE_CRED")
