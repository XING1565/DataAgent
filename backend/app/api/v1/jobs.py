from fastapi import APIRouter, HTTPException, Query

from app.schemas.jobs import JobEventsResponse, JobRecord, JobsResponse
from app.services.jobs_store import JobNotFoundError, JobsStore


router = APIRouter(prefix="/jobs", tags=["jobs"])
jobs_store = JobsStore()
jobs_store.mark_stale_running_jobs_failed()


@router.get("", response_model=JobsResponse)
def list_jobs(
    session_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> JobsResponse:
    return JobsResponse(jobs=jobs_store.list_jobs(session_id=session_id, limit=limit))


@router.get("/{job_id}", response_model=JobRecord)
def get_job(job_id: str) -> JobRecord:
    try:
        return jobs_store.get_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{job_id}/events", response_model=JobEventsResponse)
def get_job_events(job_id: str) -> JobEventsResponse:
    try:
        return JobEventsResponse(events=jobs_store.list_events(job_id))
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{job_id}/cancel", response_model=JobRecord)
def cancel_job(job_id: str) -> JobRecord:
    try:
        return jobs_store.cancel_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{job_id}/retry", response_model=JobRecord)
def retry_job(job_id: str) -> JobRecord:
    try:
        return jobs_store.retry_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
