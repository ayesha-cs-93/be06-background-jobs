
---

# BE-07 / A17 — /enrich Endpoint (LLM behind the API)

Enriches a scraped book record (title, price, description, availability) with
a validated category, a one-sentence summary, and data-quality flags — using
an LLM behind a schema-validated, closed-output endpoint.

## Try it

Valid request:
```bash
curl -X POST http://localhost:8000/enrich \
  -H "Content-Type: application/json" \
  -d '{"title":"A Light in the Attic","price":"51.77","description":"A classic collection of poems and drawings.","availability":"In stock"}'
```

Response:
```json
{"category":"poetry","summary":"A classic illustrated poetry collection for readers of all ages.","quality_flags":[],"confidence":0.9}
```

Broken request (missing field, returns 400):
```bash
curl -X POST http://localhost:8000/enrich \
  -H "Content-Type: application/json" \
  -d '{"price":"51.77"}'
```

## Job card
See `JOB-CARD.md` — input/output shape, closed category list, "must never" rules.

## Provider
- Provider: OpenRouter (free tier, `openrouter/free` model)
- Env vars to swap provider: `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`

## Reliability choices
- Timeout: 30s (SDK's 10-minute default explicitly overridden)
- Retries: exponential backoff + jitter on timeouts, 429, 5xx only — never on 400/401/403
- Repair retry: exactly one, on validation/parse failure, before returning a 422 and logging to `logs/quarantine.jsonl`
- Kill switch: `LLM_ENABLED=false` → deterministic fallback, zero model calls
- Stub mode: `LLM_STUB=1` → fixed fake response for local dev, zero model calls

## Eval results
Score: 7/8 — prompt version `enrich-v1` — date: 2026-08-19

Failed case: "The Art of War" was classified as `other` instead of `non_fiction` — an ambiguous historical/military text the model was unsure about.

## What I'd fix with another day
Add a couple more few-shot examples covering historical/military non-fiction to the prompt, so ambiguous cases like "The Art of War" don't default to "other".