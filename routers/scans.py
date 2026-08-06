import os
import re
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from database.database import get_db, SessionLocal
from database.models import Pet, Scan, User
from dependencies import get_current_user
from schemas.scans import ScanResponse
from gemini_client import analyze_pet_video, GeminiAnalysisError

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

SCAN_RATE_LIMIT_COUNT = 5
SCAN_RATE_LIMIT_WINDOW = timedelta(hours=1)


def analyze_video(scan_id: str, video_path: str):
    """Runs in the background after upload. Opens its own DB session rather
    than reusing the request-scoped one, since get_db() closes that session
    once the response is sent, which can race with this task."""
    db = SessionLocal()
    try:
        scan = db.execute(select(Scan).where(Scan.id == scan_id)).scalar_one_or_none()
        if not scan:
            return

        try:
            result = analyze_pet_video(video_path)
            scan.status = "complete"
            scan.mood_result = result.mood
            scan.confidence = result.confidence
            scan.summary = result.summary
        except GeminiAnalysisError as e:
            scan.status = "failed"
            scan.error_message = str(e)
        except Exception:
            scan.status = "failed"
            scan.error_message = "Unexpected error during analysis"

        db.commit()
    finally:
        db.close()
        if os.path.exists(video_path):
            os.remove(video_path)


@router.post("/{pet_id}/scans", response_model=ScanResponse, status_code=201)
def create_scan(
    pet_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. check pet belongs to current user
    pet = db.execute(
        select(Pet).where(Pet.id == pet_id, Pet.owner_id == current_user.id)
    ).scalar_one_or_none()
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")

    # 2. validate content type
    if file.content_type not in ALLOWED_VIDEO_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported video format: {file.content_type}")

    # 3. per-user rate limit, since each scan costs a Gemini API call
    window_start = datetime.utcnow() - SCAN_RATE_LIMIT_WINDOW
    recent_scan_count = db.execute(
        select(func.count(Scan.id))
        .join(Pet, Scan.pet_id == Pet.id)
        .where(Pet.owner_id == current_user.id, Scan.created_at >= window_start)
    ).scalar_one()
    if recent_scan_count >= SCAN_RATE_LIMIT_COUNT:
        raise HTTPException(status_code=429, detail="Scan limit reached, please try again later")

    # 4. save video under a server-generated filename (never trust the client's filename for a path)
    scan_id = str(uuid.uuid4())
    raw_ext = os.path.splitext(file.filename or "")[1]
    extension = raw_ext if SAFE_EXTENSION_RE.fullmatch(raw_ext) else ".mp4"
    video_path = f"{UPLOAD_DIR}/{scan_id}{extension}"

    size = 0
    with open(video_path, "wb") as buffer:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_VIDEO_SIZE_BYTES:
                buffer.close()
                os.remove(video_path)
                raise HTTPException(status_code=400, detail="Video exceeds maximum size of 50MB")
            buffer.write(chunk)

    # 5. create scan record with status "processing"
    new_scan = Scan(
        id=scan_id,
        pet_id=pet_id,
        status="processing",
        video_path=video_path
    )
    db.add(new_scan)
    db.commit()
    db.refresh(new_scan)

    # 6. run AI analysis in background
    background_tasks.add_task(analyze_video, new_scan.id, video_path)

    # 7. return immediately with status "processing"
    return new_scan


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
