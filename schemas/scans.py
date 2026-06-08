from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ScanResponse(BaseModel):
    id: str
    status: str
    mood_result: Optional[str] = None
    confidence: Optional[float] = None
    created_at: datetime
    pet_id: str

    class Config:
        from_attributes = True