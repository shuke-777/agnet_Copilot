from pydantic import BaseModel


class PolicySource(BaseModel):
    source_id: str
    title: str
    content: str
    score: float
