from pathlib import Path

from app.services.jobs_store import JobsStore


def test_jobs_store_initializes_sqlite_database(tmp_path: Path) -> None:
    store = JobsStore(base_dir=tmp_path / "data")

    assert (tmp_path / "data" / "jobs" / "jobs.db").exists()
    assert store.list_jobs() == []


def test_create_update_and_list_job(tmp_path: Path) -> None:
    store = JobsStore(base_dir=tmp_path / "data")

    job = store.create_job(session_id="sess_demo", type="analysis", message="created")
    updated = store.update_job(job.id, status="running", progress=50, message="running", result_json={"ok": True})

    assert job.status == "created"
    assert updated.status == "running"
    assert updated.progress == 50
    assert updated.result_json == {"ok": True}
    assert store.get_job(job.id).message == "running"
    assert store.list_jobs(session_id="sess_demo")[0].id == job.id


def test_append_event_sequence_increments(tmp_path: Path) -> None:
    store = JobsStore(base_dir=tmp_path / "data")
    job = store.create_job(session_id="sess_demo", type="analysis")

    first = store.append_event(job.id, type="step", payload={"step": "a"})
    second = store.append_event(job.id, type="step", payload={"step": "b"})

    assert first.sequence < second.sequence
    assert [event.sequence for event in store.list_events(job.id)] == [1, 2, 3]


def test_cancel_job_only_changes_cancelable_status(tmp_path: Path) -> None:
    store = JobsStore(base_dir=tmp_path / "data")
    running = store.create_job(session_id="sess_demo", type="analysis", status="running")
    succeeded = store.create_job(session_id="sess_demo", type="analysis", status="succeeded")

    assert store.cancel_job(running.id).status == "canceled"
    assert store.cancel_job(succeeded.id).status == "succeeded"


def test_retry_job_creates_queued_placeholder(tmp_path: Path) -> None:
    store = JobsStore(base_dir=tmp_path / "data")
    job = store.create_job(session_id="sess_demo", type="analysis", status="failed")

    retry = store.retry_job(job.id)

    assert retry.status == "queued"
    assert retry.type == job.type
    assert retry.result_json == {"retry_of": job.id}
    assert any(event.type == "retry_requested" for event in store.list_events(job.id))


def test_mark_stale_running_jobs_failed(tmp_path: Path) -> None:
    store = JobsStore(base_dir=tmp_path / "data")
    job = store.create_job(session_id="sess_demo", type="analysis", status="running")

    count = store.mark_stale_running_jobs_failed(older_than_seconds=0)

    assert count == 1
    assert store.get_job(job.id).status == "failed"
