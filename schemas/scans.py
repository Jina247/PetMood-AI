from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ScanResponse(BaseModel):
    id: str
    status: str
    mood_result: Optional[str] = None
    confidence: Optional[float] = None
    created_at: datetime
    pet_id: str
    summary: Optional[str] = None
    error_message: Optional[str] = None
    description: Optional[str] = None
    suggestions: Optional[List[str]] = None

    class Config:
        from_attributes = True
