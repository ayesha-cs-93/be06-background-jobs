from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from db import get_db, engine, Base
from models import Job
from schemas import ChatRequest, JobCreatedResponse, JobStatusResponse

app = FastAPI(title="Sehat Sahara — Background Jobs (BE-06)")

# For dev convenience. In real deployments, use Alembic migrations instead.
Base.metadata.create_all(bind=engine)


@app.post("/chat", status_code=202, response_model=JobCreatedResponse)
def create_chat_job(req: ChatRequest, db: Session = Depends(get_db)):
    key = req.resolved_idempotency_key()

    existing = db.query(Job).filter_by(idempotency_key=key).first()
    if existing:
        # Same request seen before (client retry, network glitch, double-click) —
        # return the existing job instead of creating a duplicate. This is the
        # idempotency guarantee: calling this endpoint twice with the same
        # input never results in two AI calls.
        return JobCreatedResponse(job_id=str(existing.id), status=existing.status)

    job = Job(
        idempotency_key=key,
        input={"message": req.message, "language": req.language},
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return JobCreatedResponse(job_id=str(job.id), status=job.status)


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        status=job.status,
        result=job.result if job.status == "done" else None,
        error=job.error if job.status == "failed" else None,
    )


@app.get("/health")
def health():
    return {"status": "ok"}
