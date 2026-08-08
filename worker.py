"""
Background worker — runs as a separate process (separate container in Docker).
Polls the jobs table, picks up pending work, calls the Anthropic API,
handles retries, and alerts on permanent failure.

Run standalone:  python worker.py
"""
import time
import json
import logging
from sqlalchemy import text

from db import SessionLocal, engine, Base
from anthropic_client import call_anthropic
from alerts import send_alert
import models

Base.metadata.create_all(bind=engine)

Base.metadata.create_all(bind=engine)
Base.metadata.create_all(bind=engine)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("worker")

POLL_INTERVAL_SECONDS = 2


def claim_next_job(db):
    """
    Grabs one pending job and locks the row so a second worker process
    (if you ever scale to >1 worker) can't grab the same job.
    FOR UPDATE SKIP LOCKED is the key piece — it's what makes this safe
    to run with multiple worker replicas later.
    """
    row = db.execute(text("""
        SELECT id, input, attempts, max_attempts
        FROM jobs
        WHERE status = 'pending'
        ORDER BY created_at
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    """)).first()

    if row is None:
        return None

    db.execute(
        text("UPDATE jobs SET status = 'running', attempts = attempts + 1, updated_at = now() WHERE id = :id"),
        {"id": row.id},
    )
    db.commit()
    return row


def mark_done(db, job_id, result: dict):
    db.execute(
        text("UPDATE jobs SET status = 'done', result = :result, error = NULL, updated_at = now() WHERE id = :id"),
        {"result": json.dumps(result), "id": job_id},
    )
    db.commit()


def mark_failed_or_retry(db, job_id, attempts: int, max_attempts: int, error: str):
    if attempts >= max_attempts:
        db.execute(
            text("UPDATE jobs SET status = 'failed', error = :error, updated_at = now() WHERE id = :id"),
            {"error": error, "id": job_id},
        )
        db.commit()
        send_alert(f"Job {job_id} failed permanently after {attempts} attempts: {error}")
    else:
        # Back to pending — will be retried on a future poll.
        db.execute(
            text("UPDATE jobs SET status = 'pending', error = :error, updated_at = now() WHERE id = :id"),
            {"error": error, "id": job_id},
        )
        db.commit()
        logger.warning(f"Job {job_id} failed attempt {attempts}/{max_attempts}, will retry: {error}")


def process_one():
    db = SessionLocal()
    try:
        job = claim_next_job(db)
        if job is None:
            return False  # nothing to do

        logger.info(f"Processing job {job.id} (attempt {job.attempts}/{job.max_attempts})")
        try:
            result = call_anthropic(
                message=job.input["message"],
                language=job.input.get("language", "roman_urdu"),
            )
            mark_done(db, job.id, result)
            logger.info(f"Job {job.id} done")
        except Exception as e:
            mark_failed_or_retry(db, job.id, job.attempts, job.max_attempts, str(e))
        return True
    finally:
        db.close()


def run_forever():
    logger.info("Worker started, polling for jobs...")
    while True:
        did_work = process_one()
        if not did_work:
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_forever()
