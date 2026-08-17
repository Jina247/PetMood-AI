from typing import Optional
from pydantic import BaseModel

class FcmTokenUpdate(BaseModel):
    fcm_token: Optional[str] = None
