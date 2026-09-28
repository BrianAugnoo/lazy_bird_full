from pydantic import BaseModel, ConfigDict
from datetime import datetime

class SessionOut(BaseModel):
    id: int
    title: str
    meta: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
    
class SessionIn(BaseModel):
    title: str
    meta: dict | None = None

    model_config = ConfigDict(from_attributes=True)