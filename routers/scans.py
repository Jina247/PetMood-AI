from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import select
import shutil
import os

from database.database import get_db
from database.models import Pet, Scan, User
from dependencies import get_current_user
from schemas.scans import ScanResponse

router = APIRouter(prefix="/pets", tags=["scans"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def analyze_video(scan_id: str, video_path: str, db: Session):
    """This runs in the background after upload."""
    try:
        # TODO: replace this with real Gemini API call later
        import time
        time.sleep(3)  # simulates AI processing time

        # fake result for now
        mood = "happy"
        confidence = 0.92

        scan = db.execute(select(Scan).where(Scan.id == scan_id)).scalar_one_or_none()
        if scan:
            scan.status = "complete"
            scan.mood_result = mood
            scan.confidence = confidence
            db.commit()

    except Exception:
        scan = db.execute(select(Scan).where(Scan.id == scan_id)).scalar_one_or_none()
        if scan:
            scan.status = "failed"
            db.commit()


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

    # 2. save video file
    video_path = f"{UPLOAD_DIR}/{pet_id}_{file.filename}"
    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 3. create scan record with status "processing"
    new_scan = Scan(
        pet_id=pet_id,
        status="processing",
        video_path=video_path
    )
    db.add(new_scan)
    db.commit()
    db.refresh(new_scan)

    # 4. run AI analysis in background
    background_tasks.add_task(analyze_video, new_scan.id, video_path, db)

    # 5. return immediately with status "processing"
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