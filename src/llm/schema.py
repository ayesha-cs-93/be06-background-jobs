"""
Stage 1 — the output contract. Anything a model returns that doesn't
fit this shape is rejected, not trusted.
"""
from enum import Enum
from typing import List
from pydantic import BaseModel, Field, ConfigDict


class Category(str, Enum):
    fiction = "fiction"
    non_fiction = "non_fiction"
    childrens = "childrens"
    poetry = "poetry"
    biography = "biography"
    other = "other"


class QualityFlag(str, Enum):
    missing_description = "missing_description"
    price_suspicious = "price_suspicious"
    title_too_short = "title_too_short"
    availability_unclear = "availability_unclear"


class BookInput(BaseModel):
    """Stage 1 — input validation. Rejected before any model call is made."""
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=300)
    price: str = Field(..., min_length=1, max_length=50)
    description: str = Field("", max_length=2000)
    availability: str = Field(..., min_length=1, max_length=200)


class EnrichedBook(BaseModel):
    """Stage 1/3 — the only shape this endpoint is allowed to return."""
    category: Category
    summary: str = Field(..., max_length=200)
    quality_flags: List[QualityFlag] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
