"""
Stages 2-4: call the model, validate its answer, repair once if needed,
never crash, never leak raw model text to the caller.
"""
import json
import os
import time
import logging
from pathlib import Path

from openai import OpenAI, APITimeoutError, RateLimitError, APIStatusError
from pydantic import ValidationError

from src.llm.schema import EnrichedBook, BookInput

logger = logging.getLogger("enrich")
logging.basicConfig(level=logging.INFO)

PROMPT_VERSION = "enrich-v1"
PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / f"{PROMPT_VERSION}.md"
QUARANTINE_PATH = Path(__file__).parent.parent.parent / "logs" / "quarantine.jsonl"

TIMEOUT_SECONDS = 30.0
MAX_RETRIES_ON_TRANSIENT = 2  # our own backoff, SDK retries disabled explicitly


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _get_client() -> OpenAI:
    return OpenAI(
        base_url=os.environ["LLM_BASE_URL"],
        api_key=os.environ["LLM_API_KEY"],
        timeout=TIMEOUT_SECONDS,
        max_retries=0,  # we control retries ourselves, deliberately
    )


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()


def _call_model_once(client: OpenAI, system_prompt: str, user_content: str) -> str:
    """One HTTP call. Backoff with jitter on timeouts/429/5xx. No retry on 4xx auth errors."""
    import random

    last_err = None
    for attempt in range(MAX_RETRIES_ON_TRANSIENT + 1):
        try:
            res = client.chat.completions.create(
                model=os.environ["LLM_MODEL"],
                temperature=0.2,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
            )
            usage = res.usage
            logger.info(json.dumps({
                "event": "llm_call",
                "prompt_version": PROMPT_VERSION,
                "model": os.environ["LLM_MODEL"],
                "input_tokens": getattr(usage, "prompt_tokens", None),
                "output_tokens": getattr(usage, "completion_tokens", None),
                "attempt": attempt + 1,
            }))
            return res.choices[0].message.content
        except (APITimeoutError, RateLimitError) as e:
            last_err = e
            if attempt < MAX_RETRIES_ON_TRANSIENT:
                wait = (2 ** attempt) + random.random()
                time.sleep(wait)
                continue
            raise
        except APIStatusError as e:
            # Only retry 5xx; never retry 400/401/403 - a bad key stays a bad key
            if 500 <= e.status_code < 600 and attempt < MAX_RETRIES_ON_TRANSIENT:
                last_err = e
                wait = (2 ** attempt) + random.random()
                time.sleep(wait)
                continue
            raise
    raise last_err


def _quarantine(raw_output: str, error: str, book_input: dict):
    QUARANTINE_PATH.parent.mkdir(exist_ok=True)
    with open(QUARANTINE_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp": time.time(),
            "prompt_version": PROMPT_VERSION,
            "input": book_input,
            "raw_output": raw_output,
            "error": error,
        }) + "\n")


def enrich_book(book: BookInput) -> EnrichedBook:
    """
    Main entry point. Returns a validated EnrichedBook or raises ValueError
    (caller maps this to a 422). Never returns raw model text.
    """
    if os.environ.get("LLM_ENABLED", "true").lower() == "false":
        # Kill switch: deterministic fallback, zero model calls
        return EnrichedBook(
            category="other",
            summary="Enrichment temporarily disabled.",
            quality_flags=[],
            confidence=0.0,
        )

    if os.environ.get("LLM_STUB") == "1":
        return EnrichedBook(
            category="other",
            summary="Stub response for testing.",
            quality_flags=["missing_description"],
            confidence=0.5,
        )

    system_prompt = _load_prompt()
    user_content = json.dumps(book.model_dump())
    client = _get_client()

    raw = _call_model_once(client, system_prompt, user_content)
    cleaned = _strip_code_fence(raw)

    try:
        parsed = json.loads(cleaned)
        return EnrichedBook.model_validate(parsed)
    except (json.JSONDecodeError, ValidationError) as first_error:
        # Repair retry: hand the model its own mistake, exactly once
        repair_prompt = (
            f"Your previous answer was rejected for this reason: {first_error}\n"
            f"Your previous answer was: {raw}\n"
            "Return only corrected JSON matching the schema. No explanation, no code fence."
        )
        try:
            raw2 = _call_model_once(client, system_prompt, repair_prompt)
            cleaned2 = _strip_code_fence(raw2)
            parsed2 = json.loads(cleaned2)
            return EnrichedBook.model_validate(parsed2)
        except (json.JSONDecodeError, ValidationError) as second_error:
            _quarantine(raw, str(second_error), book.model_dump())
            raise ValueError(f"Model output failed validation twice: {second_error}")
