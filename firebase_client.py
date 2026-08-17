import logging

import firebase_admin
from firebase_admin import credentials, messaging

from config import FIREBASE_KEY

logger = logging.getLogger(__name__)

_initialized = False


def init_firebase() -> None:
    """Initializes the Firebase Admin SDK from a local service-account key file
    path (FIREBASE_CRED). Soft-fails — logs a warning and returns rather than
    raising — if the credential is unset or invalid, so scan analysis keeps
    working even without push notifications configured. Mirrors how
    GEMINI_API_KEY is treated in main.py's lifespan."""
    global _initialized
    if not FIREBASE_KEY:
        logger.warning("FIREBASE_CRED is not set — push notifications will be skipped.")
        return
    try:
        cred = credentials.Certificate(FIREBASE_KEY)
        firebase_admin.initialize_app(cred)
        _initialized = True
    except Exception as e:
        logger.warning(f"Failed to initialize Firebase Admin SDK: {e}")


def send_scan_notification(token: str, title: str, body: str) -> None:
    """Sends a single push notification. Never raises — this is called from the
    scan background task, and a failed or skipped send must not affect
    scan.status/error_message, which are already committed by the time this runs."""
    if not _initialized:
        return
    try:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            token=token,
        )
        messaging.send(message)
    except Exception as e:
        logger.warning(f"Failed to send push notification: {e}")
