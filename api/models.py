from pydantic import BaseModel
from typing import List, Optional

class AuditRequest(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = None
    domain: str = "Economics"

class DataAnchor(BaseModel):
    claim: str
    source: str
    official_value: str
    variance: str

class LogicFlaw(BaseModel):
    flaw_type: str
    lawyers_note: str
    quote: str
    severity: str

class AuditResponse(BaseModel):
    theses: List[str]
    logical_flaws: List[LogicFlaw]
    data_anchors: List[DataAnchor]
    unresolved_conflicts: List[str]
    next_steps: List[str]