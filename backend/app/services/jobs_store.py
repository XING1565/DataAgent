from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from secrets import token_hex
from typing import Any

from app.schemas.jobs import JobEventRecord, JobRecord


TERMINAL_STATUSES = {"succeeded", "failed", "canceled"}
CANCELABLE_STATUSES = {"created", "queued", "running"}


class JobNotFoundError(ValueError):
    pass


class JobsStore:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path(__file__).resolve().parents[3] / "data"
        self.jobs_dir = self.base_dir / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.jobs_dir / "jobs.db"
        self._init_db()

    def create_job(
        self,
        *,
        session_id: str,
        type: str,
        status: str = "created",
        progress: int = 0,
        message: str = "",
        result_json: Any = None,
        error: str | None = None,
    ) -> JobRecord:
        now = self._now()
        job_id = f"job_{datetime.now().strftime('%Y%m%d%H%M%S')}_{token_hex(4)}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs(id, session_id, type, status, progress, message, result_json, error, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, session_id, type, status, progress, message, self._dump_json(result_json), error, now, now),
            )
        self.append_event(job_id, session_id=session_id, type="job_created", payload={"status": status, "message": message})
        return self.get_job(job_id)

    def update_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        progress: int | None = None,
        message: str | None = None,
        result_json: Any = None,
        error: str | None = None,
        append_event: bool = True,
    ) -> JobRecord:
        job = self.get_job(job_id)
        next_status = status if status is not None else job.status
        next_progress = progress if progress is not None else job.progress
        next_message = message if message is not None else job.message
        next_result = result_json if result_json is not None else job.result_json
        next_error = error if error is not None else job.error
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, progress = ?, message = ?, result_json = ?, error = ?, updated_at = ?
                WHERE id = ?
                """,
                (next_status, next_progress, next_message, self._dump_json(next_result), next_error, now, job_id),
            )
        updated = self.get_job(job_id)
        if append_event:
            self.append_event(
                job_id,
                session_id=updated.session_id,
                type="job_updated",
                payload={"status": updated.status, "progress": updated.progress, "message": updated.message, "error": updated.error},
            )
        return updated

    def append_event(
        self,
        job_id: str,
        *,
        session_id: str | None = None,
        type: str,
        payload: Any = None,
    ) -> JobEventRecord:
        if session_id is None:
            session_id = self.get_job(job_id).session_id
        sequence = self._next_sequence(job_id)
        now = self._now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO job_events(job_id, session_id, sequence, type, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (job_id, session_id, sequence, type, self._dump_json(payload), now),
            )
            event_id = int(cursor.lastrowid)
        event = self._event_from_row(
            {
                "id": event_id,
                "job_id": job_id,
                "session_id": session_id,
                "sequence": sequence,
                "type": type,
                "payload_json": self._dump_json(payload),
                "created_at": now,
            }
        )
        return event

    def get_job(self, job_id: str) -> JobRecord:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise JobNotFoundError(f"Job not found: {job_id}")
        return self._job_from_row(row)

    def list_jobs(self, session_id: str | None = None, limit: int = 50) -> list[JobRecord]:
        with self._connect() as conn:
            if session_id:
                rows = conn.execute(
                    "SELECT * FROM jobs WHERE session_id = ? ORDER BY updated_at DESC, created_at DESC LIMIT ?",
                    (session_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM jobs ORDER BY updated_at DESC, created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [self._job_from_row(row) for row in rows]

    def list_events(self, job_id: str) -> list[JobEventRecord]:
        self.get_job(job_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM job_events WHERE job_id = ? ORDER BY sequence ASC",
                (job_id,),
            ).fetchall()
        return [self._event_from_row(row) for row in rows]

    def cancel_job(self, job_id: str, message: str = "用户请求取消任务。") -> JobRecord:
        job = self.get_job(job_id)
        if job.status not in CANCELABLE_STATUSES:
            return job
        updated = self.update_job(job_id, status="canceled", progress=job.progress, message=message, error=None, append_event=False)
        self.append_event(job_id, session_id=updated.session_id, type="job_canceled", payload={"message": message})
        return updated

    def retry_job(self, job_id: str) -> JobRecord:
        job = self.get_job(job_id)
        retry = self.create_job(
            session_id=job.session_id,
            type=job.type,
            status="queued",
            progress=0,
            message=f"Retry requested for {job.id}.",
            result_json={"retry_of": job.id},
        )
        self.append_event(job.id, session_id=job.session_id, type="retry_requested", payload={"retry_job_id": retry.id})
        self.append_event(retry.id, session_id=retry.session_id, type="retry_created", payload={"retry_of": job.id})
        return retry

    def mark_stale_running_jobs_failed(self, older_than_seconds: int = 0) -> int:
        cutoff = datetime.now() - timedelta(seconds=older_than_seconds)
        failed = 0
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM jobs WHERE status = 'running'").fetchall()
        for row in rows:
            job = self._job_from_row(row)
            try:
                updated_at = datetime.fromisoformat(job.updated_at)
            except ValueError:
                updated_at = cutoff - timedelta(seconds=1)
            if updated_at <= cutoff:
                self.update_job(
                    job.id,
                    status="failed",
                    progress=job.progress,
                    message="任务在应用重启后被标记为失败。",
                    error="Job was running before startup and did not complete.",
                )
                failed += 1
        return failed

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    message TEXT NOT NULL DEFAULT '',
                    result_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    payload_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES jobs(id)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_session_updated ON jobs(session_id, updated_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_job_events_job_sequence ON job_events(job_id, sequence)")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _next_sequence(self, job_id: str) -> int:
        with self._connect() as conn:
            value = conn.execute("SELECT COALESCE(MAX(sequence), 0) + 1 FROM job_events WHERE job_id = ?", (job_id,)).fetchone()[0]
        return int(value)

    def _job_from_row(self, row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            id=row["id"],
            session_id=row["session_id"],
            type=row["type"],
            status=row["status"],
            progress=int(row["progress"]),
            message=row["message"],
            result_json=self._load_json(row["result_json"]),
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _event_from_row(self, row: sqlite3.Row | dict[str, Any]) -> JobEventRecord:
        return JobEventRecord(
            id=int(row["id"]),
            job_id=row["job_id"],
            session_id=row["session_id"],
            sequence=int(row["sequence"]),
            type=row["type"],
            payload_json=self._load_json(row["payload_json"]),
            created_at=row["created_at"],
        )

    def _dump_json(self, value: Any) -> str | None:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False, default=str)

    def _load_json(self, value: str | None) -> Any:
        if value is None or value == "":
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")
