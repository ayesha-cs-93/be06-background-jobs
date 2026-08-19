"""
Stage 1: POST /enrich
Add this router to your existing FastAPI app with:
    from src.routes.enrich import router as enrich_router
    app.include_router(enrich_router)
"""
from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from src.llm.schema import BookInput, EnrichedBook
from src.llm.client import enrich_book

router = APIRouter()


@router.post("/enrich", response_model=EnrichedBook)
def enrich(payload: dict):
    # Explicit validation before any model call — reject garbage before spending a call
    try:
        book = BookInput.model_validate(payload)
    except ValidationError as e:
        # 400 naming the offending field
        first_error = e.errors()[0]
        field = ".".join(str(p) for p in first_error["loc"])
        raise HTTPException(status_code=400, detail=f"Invalid field '{field}': {first_error['msg']}")

    try:
        return enrich_book(book)
    except ValueError as e:
        # Model output could not be repaired into a valid shape
        raise HTTPException(status_code=422, detail=str(e))
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Model call timed out")
