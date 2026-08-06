# BE-06 — Background Jobs

Moves the Sehat Sahara AI call (A6) out of the request path. `POST /chat` now
returns `202` instantly; a separate worker process does the actual Anthropic
API call; `GET /jobs/{job_id}` reports status and result.

## Why this design

**Postgres-only, no Redis/Celery.** The project already runs Postgres in
Docker. Adding a `jobs` table and a polling worker gets the full
accept-fast / work-in-background / report-status pattern without new
infrastructure. `FOR UPDATE SKIP LOCKED` makes it safe to scale to multiple
worker replicas later without code changes — that's the same mechanism
Postgres-backed queue libraries use internally.

## Architecture

```
Client → POST /chat → jobs row (status=pending) → 202 + job_id
                                ↓
                    worker.py polls every 2s
                                ↓
                    claims job (FOR UPDATE SKIP LOCKED)
                                ↓
                    calls Anthropic API
                                ↓
                    status=done + result   OR   retry / status=failed + alert

Client → GET /jobs/{job_id} → current status + result (when ready)
```

## The three non-negotiables

| Requirement | Implementation |
|---|---|
| **Idempotency** | `idempotency_key` (client-supplied or hashed from the request body) has a unique DB constraint. Same request submitted twice → same `job_id` returned, only one AI call ever happens. |
| **Retries** | `attempts` / `max_attempts` columns. A failed job goes back to `pending` and gets picked up again, up to 3 attempts. |
| **Alerts** | `alerts.py` logs an `[ALERT]` line when a job fails permanently. Stubbed for the assignment — swap in a Slack webhook or email call for production. |

## Running it

```bash
cp .env.example .env   # add your real ANTHROPIC_API_KEY
docker compose up --build
```

- API: `http://localhost:8000`
- `POST /chat` — body: `{"message": "...", "language": "roman_urdu"}` → `202` with `job_id`
- `GET /jobs/{job_id}` — poll until `status: "done"`

## Testing idempotency manually

Send the same `idempotency_key` twice — second call returns the same
`job_id` instead of creating a new job:

```bash
curl -X POST localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "sar dard ho raha hai", "idempotency_key": "test-1"}'

curl -X POST localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "sar dard ho raha hai", "idempotency_key": "test-1"}'
```

## Testing retries/failure

Temporarily set an invalid `ANTHROPIC_API_KEY` — job will retry up to 3
times, then flip to `status: failed` with an `[ALERT]` line in the worker
logs.

## What I'd change for production

- Alembic migrations instead of `create_all()`
- Replace `alerts.py` log stub with a real Slack/email webhook
- Add exponential backoff between retry attempts instead of immediate re-poll
- Move `idempotency_key` generation fully server-side if clients shouldn't control it
