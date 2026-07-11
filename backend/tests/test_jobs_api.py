from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import jobs
from app.main import app
from app.services.jobs_store import JobsStore


client = TestClient(app)


@pytest.fixture(autouse=True)
def isolate_jobs_store(tmp_path: Path) -> None:
    original_store = jobs.jobs_store
    jobs.jobs_store = JobsStore(base_dir=tmp_path / "data")
    try:
        yield
    finally:
        jobs.jobs_store = original_store


def test_jobs_api_lists_and_reads_jobs() -> None:
    job = jobs.jobs_store.create_job(session_id="sess_demo", type="analysis", status="running")

    list_response = client.get("/api/v1/jobs?session_id=sess_demo")
    get_response = client.get(f"/api/v1/jobs/{job.id}")

    assert list_response.status_code == 200
    assert list_response.json()["jobs"][0]["id"] == job.id
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "running"


def test_jobs_api_returns_events() -> None:
    job = jobs.jobs_store.create_job(session_id="sess_demo", type="analysis")
    jobs.jobs_store.append_event(job.id, type="step_finished", payload={"step": "load_dataset"})

    response = client.get(f"/api/v1/jobs/{job.id}/events")

    assert response.status_code == 200
    assert [event["sequence"] for event in response.json()["events"]] == [1, 2]


def test_jobs_api_cancel_and_retry() -> None:
    job = jobs.jobs_store.create_job(session_id="sess_demo", type="analysis", status="running")

    cancel_response = client.post(f"/api/v1/jobs/{job.id}/cancel")
    retry_response = client.post(f"/api/v1/jobs/{job.id}/retry")

    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "canceled"
    assert retry_response.status_code == 200
    assert retry_response.json()["status"] == "queued"
    assert retry_response.json()["result_json"] == {"retry_of": job.id}


def test_jobs_api_missing_job_returns_404() -> None:
    response = client.get("/api/v1/jobs/job_missing")

    assert response.status_code == 404
