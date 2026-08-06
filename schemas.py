from pydantic import BaseModel, Field
from typing import Optional, Any
import hashlib


class ChatRequest(BaseModel):
    message: str
    language: str = "roman_urdu"
    idempotency_key: Optional[str] = Field(
        default=None,
        description="Client-supplied key to dedupe retries. If omitted, one is derived from the message."
    )

    def resolved_idempotency_key(self) -> str:
        if self.idempotency_key:
            return self.idempotency_key
        # Fallback: hash the input so identical retried requests collapse to one job.
        raw = f"{self.message}:{self.language}"
        return hashlib.sha256(raw.encode()).hexdigest()


class JobCreatedResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None
