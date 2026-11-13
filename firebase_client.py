import json
import logging
from typing import Optional

import firebase_admin
from firebase_admin import credentials, messaging

from config import FIREBASE_KEY, FIREBASE_KEY_JSON

logger = logging.getLogger(__name__)

_initialized = False


def init_firebase() -> None:
    """Initializes the Firebase Admin SDK from the service-account key, given either
    as JSON content (FIREBASE_CRED_JSON) or a file path (FIREBASE_CRED). Soft-fails — logs a warning and returns rather than
    raising — if the credential is unset or invalid, so scan analysis keeps
    working even without push notifications configured. Mirrors how
    GEMINI_API_KEY is treated in main.py's lifespan."""
    global _initialized
    if not FIREBASE_KEY_JSON and not FIREBASE_KEY:
        logger.warning(
            "Neither FIREBASE_CRED_JSON nor FIREBASE_CRED is set — push notifications will be skipped."
        )
        return
    try:
        source = json.loads(FIREBASE_KEY_JSON) if FIREBASE_KEY_JSON else FIREBASE_KEY
        cred = credentials.Certificate(source)
        firebase_admin.initialize_app(cred)
        _initialized = True
        logger.info("Firebase Admin SDK initialized — push notifications enabled.")
    except Exception as e:
        # Don't log e for JSON input: a parse error message can echo part of the key.
        detail = "invalid FIREBASE_CRED_JSON" if FIREBASE_KEY_JSON else str(e)
        logger.warning(f"Failed to initialize Firebase Admin SDK: {detail}")


def send_scan_notification(
    token: str,
    title: str,
    body: str,
    pet_id: Optional[str] = None,
    scan_id: Optional[str] = None,
) -> None:
    """Sends a single push notification. Never raises — this is called from the
    scan background task, and a failed or skipped send must not affect
    scan.status/error_message, which are already committed by the time this runs.

    pet_id/scan_id ride along as the FCM data payload (data values must be
    strings) so the Android client can deep-link straight to that scan's
    result on tap instead of just opening the app cold — see
    PetMoodFirebaseMessagingService.onMessageReceived."""
    if not _initialized:
        return
    try:
        data = {}
        if pet_id is not None:
            data["pet_id"] = pet_id
        if scan_id is not None:
            data["scan_id"] = scan_id
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data,
            token=token,
        )
        messaging.send(message)
    except Exception as e:
        logger.warning(f"Failed to send push notification: {e}")
