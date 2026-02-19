from pydantic import BaseModel
from typing import List, Optional

class AuditRequest(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = None
    domain: str = "Economics"
