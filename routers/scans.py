import os
import re
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from database.database import get_db, SessionLocal
from database.models import Pet, Scan, User
from dependencies import get_current_user
from schemas.scans import ScanResponse
from gemini_client import analyze_pet_scan, GeminiAnalysisError
from firebase_client import send_scan_notification

router = APIRouter(prefix="/pets", tags=["scans"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_VIDEO_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
ALLOWED_VIDEO_CONTENT_TYPES = {
    "video/mp4",
    "video/mpeg",
    "video/quicktime",
    "video/webm",
    "video/3gpp",
}
SAFE_EXTENSION_RE = re.compile(r"\.[a-zA-Z0-9]{1,5}$")

MAX_PHOTO_SIZE_BYTES = 4 * 1024 * 1024  # 4MB per photo
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}
MAX_PHOTOS = 3  # optional supporting photos alongside the (required) video; no minimum
MAX_DESCRIPTION_LENGTH = 1000

SCAN_RATE_LIMIT_COUNT = 5
SCAN_RATE_LIMIT_WINDOW = timedelta(hours=1)


def _check_rate_limit(db: Session, user_id: str):
    window_start = datetime.utcnow() - SCAN_RATE_LIMIT_WINDOW
    recent_scan_count = db.execute(
        select(func.count(Scan.id))
        .join(Pet, Scan.pet_id == Pet.id)
        .where(Pet.owner_id == user_id, Scan.created_at >= window_start)
    ).scalar_one()
    if recent_scan_count >= SCAN_RATE_LIMIT_COUNT:
        raise HTTPException(status_code=429, detail="Scan limit reached, please try again later")


def analyze_scan(scan_id: str, video_path: str, photo_paths: List[str], description: Optional[str]):
    """Runs in the background after upload. Opens its own DB session rather
    than reusing the request-scoped one, since get_db() closes that session
    once the response is sent, which can race with this task."""
    db = SessionLocal()
    try:
        scan = db.execute(select(Scan).where(Scan.id == scan_id)).scalar_one_or_none()
        if not scan:
            return

        try:
            result = analyze_pet_scan(video_path, photo_paths, description)
            scan.status = "complete"
            scan.mood_result = result.mood
            scan.confidence = result.confidence
            scan.summary = result.summary
            scan.suggestions = result.suggestions
        except GeminiAnalysisError as e:
            scan.status = "failed"
            scan.error_message = str(e)
        except Exception:
            scan.status = "failed"
            scan.error_message = "Unexpected error during analysis"

        db.commit()

        # scan.pet / Pet.owner are existing relationships, lazy-loaded in this
        # same session — never let a notification failure affect the result
        # already committed above (send_scan_notification swallows internally).
        owner_token = scan.pet.owner.fcm_token
        if owner_token:
            if scan.status == "complete":
                send_scan_notification(owner_token, "Analysis complete", "Your pet's mood analysis is ready.")
            else:
                send_scan_notification(owner_token, "Analysis failed", scan.error_message or "Something went wrong.")
    finally:
        db.close()
        if os.path.exists(video_path):
            os.remove(video_path)
        for path in photo_paths:
            if os.path.exists(path):
                os.remove(path)


@router.post("/{pet_id}/scans", response_model=ScanResponse, status_code=201)
def create_scan(
    pet_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    photos: List[UploadFile] = File(default=[]),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. check pet belongs to current user
    pet = db.execute(
        select(Pet).where(Pet.id == pet_id, Pet.owner_id == current_user.id)
    ).scalar_one_or_none()
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")

    # 2. validate video content type
    if file.content_type not in ALLOWED_VIDEO_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported video format: {file.content_type}")

    # 3. validate optional photos: count + content type
    if len(photos) > MAX_PHOTOS:
        raise HTTPException(status_code=400, detail=f"Expected at most {MAX_PHOTOS} photos, got {len(photos)}")
    for photo in photos:
        if photo.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise HTTPException(status_code=400, detail=f"Unsupported photo format: {photo.content_type}")

    # 4. validate optional description length
    if description is not None and len(description) > MAX_DESCRIPTION_LENGTH:
        raise HTTPException(status_code=400, detail=f"Description exceeds maximum length of {MAX_DESCRIPTION_LENGTH} characters")

    # 5. per-user rate limit, since each scan costs a Gemini API call
    _check_rate_limit(db, current_user.id)

    # 6. save video + any photos under server-generated filenames (never trust the client's
    # filename for a path), cleaning up everything written so far if any step fails partway.
    scan_id = str(uuid.uuid4())
    video_path = f"{UPLOAD_DIR}/{scan_id}{_safe_extension(file.filename, '.mp4')}"
    photo_paths: List[str] = []
    try:
        _stream_to_disk(file, video_path, MAX_VIDEO_SIZE_BYTES, "Video exceeds maximum size of 50MB")

        for index, photo in enumerate(photos):
            photo_path = f"{UPLOAD_DIR}/{scan_id}_{index}{_safe_extension(photo.filename, '.jpg')}"
            _stream_to_disk(photo, photo_path, MAX_PHOTO_SIZE_BYTES, "Photo exceeds maximum size of 4MB")
            photo_paths.append(photo_path)
    except HTTPException:
        if os.path.exists(video_path):
            os.remove(video_path)
        for path in photo_paths:
            if os.path.exists(path):
                os.remove(path)
        raise

    # 7. create scan record with status "processing"
    new_scan = Scan(
        id=scan_id,
        pet_id=pet_id,
        status="processing",
        video_path=video_path,
        photo_paths=photo_paths or None,
        description=description
    )
    db.add(new_scan)
    db.commit()
    db.refresh(new_scan)

    # 8. run AI analysis in background
    background_tasks.add_task(analyze_scan, new_scan.id, video_path, photo_paths, description)

    # 9. return immediately with status "processing"
    return new_scan


def _safe_extension(filename: Optional[str], fallback: str) -> str:
    raw_ext = os.path.splitext(filename or "")[1]
    return raw_ext if SAFE_EXTENSION_RE.fullmatch(raw_ext) else fallback


def _stream_to_disk(upload: UploadFile, path: str, max_bytes: int, size_error_detail: str):
    size = 0
    with open(path, "wb") as buffer:
        while chunk := upload.file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                buffer.close()
                os.remove(path)
                raise HTTPException(status_code=400, detail=size_error_detail)
            buffer.write(chunk)


@router.get("/{pet_id}/scans/{scan_id}", response_model=ScanResponse)
def get_scan(
    pet_id: str,
    scan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # verify pet ownership first
    pet = db.execute(
        select(Pet).where(Pet.id == pet_id, Pet.owner_id == current_user.id)
    ).scalar_one_or_none()
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")

    scan = db.execute(
        select(Scan).where(Scan.id == scan_id, Scan.pet_id == pet_id)
    ).scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    return scan


@router.get("/{pet_id}/scans", response_model=list[ScanResponse])
def get_scans(
    pet_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    pet = db.execute(
        select(Pet).where(Pet.id == pet_id, Pet.owner_id == current_user.id)
    ).scalar_one_or_none()
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")

    scans = db.execute(
        select(Scan).where(Scan.pet_id == pet_id)
    ).scalars().all()

    return scans

@router.get("/{pet_id}/latest-scan", response_model=ScanResponse)
def get_latest_scan(
    pet_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    pet = db.execute(
        select(Pet).where(Pet.id == pet_id, Pet.owner_id == current_user.id)
    ).scalar_one_or_none()
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")

    scan = db.execute(
        select(Scan)
        .where(Scan.pet_id == pet_id)
        .order_by(Scan.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if not scan:
        raise HTTPException(status_code=404, detail="No scans found")

    return scan
